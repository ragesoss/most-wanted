#!/usr/bin/env python3
"""Step 2 matcher prototype: spatial-join a photo folder against want bundles.

For every JPEG in --photos, reads EXIF (GPS position, capture time, compass
heading) and finds wants from --bundles whose geo circle contains the photo.
Candidates are placed in confidence tiers per PLAN.md:

    auto_suggest   geo well inside the radius AND heading points at the
                   subject — or the photo is near-field (within ~30 m) of
                   the only matching want, where heading carries no signal.
                   (When the semantic classifier lands, it must also agree
                   before this tier is allowed.)
    worth_a_look   inside the radius; heading unknown or inconclusive
    long_shot      just outside the radius, heading points away, or the
                   photo's timestamp falls after a time_window 'before' date
                   (EXIF dates on scanned photos are unreliable, so this
                   demotes rather than rejects)

Pipeline order per the plan: spatial join first, semantic rejection second.
The semantic step is a stub here (`semantic_check` returns None = unknown);
it is the integration point for a MobileCLIP-class embedding model scoring
the photo against subject.classifier_labels.

Output: JSON report on stdout or --out, one entry per photo, candidates
sorted best-first. Photos without GPS are listed under 'no_gps' — they are
the input to the plan's clustering fallback, which does not exist yet.

Dependencies: piexif (pure Python). HEIC is not handled; export/convert to
JPEG first.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import piexif

sys.path.insert(0, str(Path(__file__).parent))
from geo import angle_diff_deg, haversine_m, initial_bearing_deg

GPS_SLACK_M = 60  # typical phone GPS error allowance
HEADING_AGREE_DEG = 50
HEADING_DISAGREE_DEG = 120
HEADING_NEAR_FIELD_M = 30  # standing on top of the subject: heading means little


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


def semantic_check(photo_path, want):
    """Stub for the on-device classifier (semantic-rejection step).

    Returns True (category agrees), False (reject), or None (unknown).
    Real implementation: embed the photo, compare against
    want['subject']['classifier_labels'] with a MobileCLIP-class model.
    """
    return None


def evaluate_candidate(photo, want, photo_path):
    geo = want["geo"]
    dist = haversine_m(photo["lat"], photo["lon"], geo["lat"], geo["lon"])
    reach = geo["radius_m"] + GPS_SLACK_M
    if dist > 2 * reach:
        return None

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

    semantic = semantic_check(photo_path, want)
    if semantic is False:
        return None

    inside = dist <= reach
    if not inside or heading_status == "disagree" or time_status == "after_end_date":
        tier = "long_shot"
    elif heading_status == "agree" and dist <= geo["radius_m"]:
        # With the classifier wired in, also require semantic is True here.
        tier = "auto_suggest"
    else:
        tier = "worth_a_look"

    score = max(0.0, 1 - dist / reach)
    score += {"agree": 0.4, "near_field": 0.1, "near_field_away": -0.2, "disagree": -0.5}.get(heading_status, 0.0)
    score += min(want.get("priority", {}).get("sitelinks", 0), 10) * 0.01

    return {
        "want_id": want["id"],
        "label": want["subject"]["label"],
        "tier": tier,
        "distance_m": round(dist, 1),
        "radius_m": geo["radius_m"],
        "heading": heading_status,
        "time": time_status,
        "classifier": "not_run" if semantic is None else "agree",
        "score": round(score, 3),
        "notes": notes,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--photos", required=True, help="folder of JPEGs")
    ap.add_argument("--bundles", default="data/bundles", help="compiler output directory")
    ap.add_argument("--out", help="write JSON report here instead of stdout")
    ap.add_argument("--max-candidates", type=int, default=5, help="per photo")
    args = ap.parse_args()

    wants = load_wants(args.bundles)
    report = {"photos": [], "no_gps": [], "stats": {"wants_loaded": len(wants)}}

    paths = sorted(p for p in Path(args.photos).iterdir() if p.suffix.lower() in (".jpg", ".jpeg"))
    for path in paths:
        photo = read_exif(path)
        if photo["lat"] is None:
            report["no_gps"].append(path.name)
            continue
        candidates = []
        for want in wants:
            cand = evaluate_candidate(photo, want, path)
            if cand:
                candidates.append(cand)
        candidates.sort(key=lambda c: -c["score"])
        # Near-field promotion: standing within HEADING_NEAR_FIELD_M of the
        # subject is the strongest geo evidence available, and heading is
        # geometrically meaningless there. Promote to auto_suggest only when
        # unambiguous (no other want's circle also contains the photo) and
        # heading is not actively contrary ('near_field_away').
        inside = [c for c in candidates if c["tier"] != "long_shot"]
        if (
            len(inside) == 1
            and inside[0]["heading"] in ("near_field", "unknown")
            and inside[0]["distance_m"] <= HEADING_NEAR_FIELD_M
        ):
            inside[0]["tier"] = "auto_suggest"
        report["photos"].append(
            {
                "file": path.name,
                "taken": photo["taken"].isoformat() if photo["taken"] else None,
                "heading": photo["heading"],
                "candidates": candidates[: args.max_candidates],
            }
        )

    tiers = [c["tier"] for p in report["photos"] for c in p["candidates"]]
    report["stats"].update(
        photos_scanned=len(paths),
        photos_with_gps=len(report["photos"]),
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
