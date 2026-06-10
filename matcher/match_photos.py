#!/usr/bin/env python3
"""Step 2 matcher prototype: spatial-join a photo folder against want bundles.

For every JPEG in --photos, reads EXIF (GPS position, capture time, compass
heading) and finds wants from --bundles whose geo circle contains the photo.
Candidates are placed in confidence tiers per PLAN.md:

    auto_suggest   geo well inside the radius AND heading points at the
                   subject — or the photo is near-field (within ~30 m) of
                   the only matching want, where heading carries no signal.
                   When a semantic backend is active (--semantic), the
                   classifier must also agree before this tier is allowed.
    worth_a_look   inside the radius; heading unknown or inconclusive, or
                   the classifier is unsure, or the position was inferred
                   rather than read from EXIF
    long_shot      just outside the radius, heading points away, or the
                   photo's timestamp falls after a time_window 'before' date
                   (EXIF dates on scanned photos are unreliable, so this
                   demotes rather than rejects)

Candidates the classifier actively rejects ("want says church; photo is a
selfie") are dropped entirely and counted in stats.semantic_rejected.

No-GPS fallback (burst clustering): photos without GPS but with a
timestamp inherit the position of the nearest-in-time geotagged photo
within --time-window-min (people photograph in bursts from one place).
Inferred positions get extra distance slack proportional to the time gap
(walking drift) and are never auto-suggested. Photos with neither GPS nor
a usable neighbor land in the 'no_gps' pile.

Output: JSON report on stdout or --out, one entry per photo, candidates
sorted best-first.

Dependencies: piexif (pure Python); --semantic clip additionally needs
torch + open_clip_torch and network access for weights on first use.
HEIC is not handled; export/convert to JPEG first.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import piexif

sys.path.insert(0, str(Path(__file__).parent))
from geo import angle_diff_deg, haversine_m, initial_bearing_deg
from semantic import build_checker

GPS_SLACK_M = 60  # typical phone GPS error allowance
HEADING_AGREE_DEG = 50
HEADING_DISAGREE_DEG = 120
HEADING_NEAR_FIELD_M = 30  # standing on top of the subject: heading means little
DRIFT_M_PER_MIN = 25  # walking-pace position uncertainty for inferred GPS
DRIFT_CAP_M = 500


def rational_to_float(value):
    num, den = value
    return num / den if den else 0.0


def dms_to_deg(dms, ref):
    deg = rational_to_float(dms[0]) + rational_to_float(dms[1]) / 60 + rational_to_float(dms[2]) / 3600
    return -deg if ref in (b"S", b"W", "S", "W") else deg


def read_exif(path):
    """Return {'lat', 'lon', 'heading', 'taken'} (each may be None)."""
    out = {"lat": None, "lon": None, "heading": None, "taken": None}
    try:
        exif = piexif.load(str(path))
    except Exception:
        return out
    gps = exif.get("GPS", {})
    if piexif.GPSIFD.GPSLatitude in gps and piexif.GPSIFD.GPSLongitude in gps:
        out["lat"] = dms_to_deg(gps[piexif.GPSIFD.GPSLatitude], gps.get(piexif.GPSIFD.GPSLatitudeRef, b"N"))
        out["lon"] = dms_to_deg(gps[piexif.GPSIFD.GPSLongitude], gps.get(piexif.GPSIFD.GPSLongitudeRef, b"E"))
    if piexif.GPSIFD.GPSImgDirection in gps:
        out["heading"] = rational_to_float(gps[piexif.GPSIFD.GPSImgDirection])
    dto = exif.get("Exif", {}).get(piexif.ExifIFD.DateTimeOriginal)
    if dto:
        try:
            out["taken"] = datetime.strptime(dto.decode(), "%Y:%m:%d %H:%M:%S")
        except ValueError:
            pass
    return out


def load_wants(bundles_dir):
    wants = []
    for path in sorted(Path(bundles_dir, "bundles").glob("*.json")):
        wants.extend(json.loads(path.read_text())["wants"])
    return wants


def evaluate_candidate(photo, want, photo_path, checker, extra_slack_m=0):
    """Score one (photo, want) pair; None = not a candidate, 'rejected' = semantic reject."""
    geo = want["geo"]
    dist = haversine_m(photo["lat"], photo["lon"], geo["lat"], geo["lon"])
    reach = geo["radius_m"] + GPS_SLACK_M + extra_slack_m
    if dist > 2 * reach:
        return None

    # Spatial join first, semantic rejection second (PLAN.md pipeline order):
    # the classifier only ever sees geo candidates.
    semantic = checker(photo_path, want) if checker else None
    if semantic is False:
        return "rejected"

    heading_status = "unknown"
    if photo["heading"] is not None:
        diff = angle_diff_deg(
            photo["heading"], initial_bearing_deg(photo["lat"], photo["lon"], geo["lat"], geo["lon"])
        )
        if dist <= HEADING_NEAR_FIELD_M:
            # Too close for heading to confirm anything (GPS error swamps the
            # geometry), but a heading pointing flatly away still blocks the
            # near-field promotion below — it must not *count for* the match.
            heading_status = "near_field" if diff < HEADING_DISAGREE_DEG else "near_field_away"
        elif diff <= HEADING_AGREE_DEG:
            heading_status = "agree"
        elif diff >= HEADING_DISAGREE_DEG:
            heading_status = "disagree"
        else:
            heading_status = "inconclusive"

    time_status = "ok"
    notes = []
    tw = want.get("time_window")
    if tw:
        if tw.get("historical"):
            time_status = "historical_subject"
            notes.append("subject no longer exists; older photos preferred — do not go photograph the site")
        if tw.get("before") and photo["taken"]:
            if photo["taken"].date().isoformat() > tw["before"]:
                time_status = "after_end_date"
                notes.append(f"photo dated after subject's end date {tw['before']} (EXIF date may be wrong for scans)")

    classifier = "not_run"
    if checker is not None:
        classifier = "agree" if semantic else "unsure"

    inside = dist <= reach
    if not inside or heading_status == "disagree" or time_status == "after_end_date":
        tier = "long_shot"
    elif (
        heading_status == "agree"
        and dist <= geo["radius_m"] + extra_slack_m
        and classifier in ("agree", "not_run")
    ):
        tier = "auto_suggest"
    else:
        tier = "worth_a_look"

    score = max(0.0, 1 - dist / reach)
    score += {"agree": 0.4, "near_field": 0.1, "near_field_away": -0.2, "disagree": -0.5}.get(heading_status, 0.0)
    score += {"agree": 0.2, "unsure": -0.1}.get(classifier, 0.0)
    score += min(want.get("priority", {}).get("sitelinks", 0), 10) * 0.01

    return {
        "want_id": want["id"],
        "label": want["subject"]["label"],
        "tier": tier,
        "distance_m": round(dist, 1),
        "radius_m": geo["radius_m"],
        "heading": heading_status,
        "time": time_status,
        "classifier": classifier,
        "score": round(score, 3),
        "notes": notes,
    }


def infer_position(photo, geotagged, window_min):
    """Nearest-in-time geotagged neighbor within the window, or None."""
    if photo["taken"] is None:
        return None
    best, best_gap = None, None
    for name, other in geotagged:
        if other["taken"] is None:
            continue
        gap = abs((photo["taken"] - other["taken"]).total_seconds())
        if gap <= window_min * 60 and (best_gap is None or gap < best_gap):
            best, best_gap = (name, other), gap
    if best is None:
        return None
    name, other = best
    return {"lat": other["lat"], "lon": other["lon"], "from": name, "gap_min": best_gap / 60}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--photos", required=True, help="folder of JPEGs")
    ap.add_argument("--bundles", default="data/bundles", help="compiler output directory")
    ap.add_argument("--out", help="write JSON report here instead of stdout")
    ap.add_argument("--max-candidates", type=int, default=5, help="per photo")
    ap.add_argument("--semantic", default="off", choices=["off", "clip", "exif-tag"],
                    help="semantic-rejection backend (exif-tag is test-only)")
    ap.add_argument("--time-window-min", type=float, default=45,
                    help="burst window for inferring positions of GPS-less photos")
    args = ap.parse_args()

    checker = build_checker(args.semantic)
    semantic_active = checker is not None
    wants = load_wants(args.bundles)
    report = {"photos": [], "no_gps": [], "stats": {"wants_loaded": len(wants), "semantic_rejected": 0}}

    paths = sorted(p for p in Path(args.photos).iterdir() if p.suffix.lower() in (".jpg", ".jpeg"))
    photos = [(p, read_exif(p)) for p in paths]
    geotagged = [(p.name, e) for p, e in photos if e["lat"] is not None]

    for path, exif in photos:
        photo = dict(exif)
        gps_source = "exif"
        extra_slack = 0
        inferred_from = None
        if photo["lat"] is None:
            inferred = infer_position(photo, geotagged, args.time_window_min)
            if inferred is None:
                report["no_gps"].append(path.name)
                continue
            photo["lat"], photo["lon"] = inferred["lat"], inferred["lon"]
            photo["heading"] = None  # heading is meaningless at a borrowed position
            gps_source = "inferred"
            extra_slack = min(DRIFT_CAP_M, DRIFT_M_PER_MIN * inferred["gap_min"])
            inferred_from = {"file": inferred["from"], "gap_min": round(inferred["gap_min"], 1)}

        candidates = []
        for want in wants:
            cand = evaluate_candidate(photo, want, path, checker, extra_slack)
            if cand == "rejected":
                report["stats"]["semantic_rejected"] += 1
            elif cand:
                candidates.append(cand)
        candidates.sort(key=lambda c: -c["score"])

        if gps_source == "inferred":
            # An inferred position is never strong enough to auto-suggest.
            for c in candidates:
                if c["tier"] == "auto_suggest":
                    c["tier"] = "worth_a_look"
        else:
            # Near-field promotion: standing within HEADING_NEAR_FIELD_M of the
            # subject is the strongest geo evidence available, and heading is
            # geometrically meaningless there. Promote to auto_suggest only when
            # unambiguous (no other want's circle also contains the photo),
            # heading is not actively contrary ('near_field_away'), and the
            # classifier — if running — agrees.
            inside = [c for c in candidates if c["tier"] != "long_shot"]
            if (
                len(inside) == 1
                and inside[0]["heading"] in ("near_field", "unknown")
                and inside[0]["distance_m"] <= HEADING_NEAR_FIELD_M
                and inside[0]["classifier"] in ("agree", "not_run")
            ):
                inside[0]["tier"] = "auto_suggest"

        entry = {
            "file": path.name,
            "taken": photo["taken"].isoformat() if photo["taken"] else None,
            "heading": photo["heading"],
            "gps": gps_source,
            "candidates": candidates[: args.max_candidates],
        }
        if inferred_from:
            entry["inferred_from"] = inferred_from
        report["photos"].append(entry)

    tiers = [c["tier"] for p in report["photos"] for c in p["candidates"]]
    report["stats"].update(
        photos_scanned=len(paths),
        photos_with_gps=len(geotagged),
        photos_inferred_gps=sum(1 for p in report["photos"] if p["gps"] == "inferred"),
        photos_without_gps=len(report["no_gps"]),
        candidates={t: tiers.count(t) for t in ("auto_suggest", "worth_a_look", "long_shot")},
    )

    text = json.dumps(report, indent=1, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(text + "\n")
        print(f"wrote {args.out}: {report['stats']}")
    else:
        print(text)


if __name__ == "__main__":
    main()
