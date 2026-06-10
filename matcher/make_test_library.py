#!/usr/bin/env python3
"""Generate a synthetic photo library with real EXIF for matcher testing.

Until a real camera roll is available, this fabricates the *metadata*
conditions the matcher must handle: small JPEGs whose EXIF GPS, compass
heading, and timestamp are planted relative to actual wants sampled from
the compiled bundles. A ground-truth content label is planted in EXIF
UserComment for the test-only `--semantic exif-tag` backend. Scenarios:

    hit              photo 15-100 m from an *isolated* want (no other want's
                     circle can contain the photo), heading pointed at it,
                     content label matching
                     (expected: top candidate at auto_suggest)
    hit_dense        same, but the want has overlapping neighbors — downtown
                     storefront rows, nested park/dam circles. Several
                     candidates are legitimately plausible; expected want
                     must appear among them (the human picks, per PLAN.md)
    hit_no_heading   near a want, no GPSImgDirection tag (loose expectation)
    wrong_heading    near a want but camera pointed the opposite way
                     (expected: demoted, never auto_suggest)
    semantic_mismatch near an isolated want, heading correct, but content
                     label is 'selfie' (expected: dropped by the semantic
                     backend, absent from candidates)
    no_gps_burst     no GPS tags, but timestamped 8 minutes after a 'hit'
                     photo (expected: position inferred from the burst
                     neighbor; want found at worth_a_look, never
                     auto_suggest)
    far_decoy        >=300 m clear of every want's reach (expected: no
                     candidates at all)
    no_gps           no GPS tags and no temporal neighbor (expected: routed
                     to the no-GPS pile)

Writes photos plus manifest.json with ground truth for evaluate.py.
This tests the spatial/heading/tier/semantic plumbing only — it says
nothing about matching precision on real libraries, which is the actual
step-2 falsification test and still requires a real camera roll.

Dependencies: Pillow, piexif.
"""

import argparse
import json
import math
import random
import sys
from pathlib import Path

import piexif
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent))
from geo import EARTH_RADIUS_M, haversine_m


def offset_point(lat, lon, bearing_deg, dist_m):
    """Destination point given start, bearing, and distance."""
    br = math.radians(bearing_deg)
    p1 = math.radians(lat)
    l1 = math.radians(lon)
    ang = dist_m / EARTH_RADIUS_M
    p2 = math.asin(math.sin(p1) * math.cos(ang) + math.cos(p1) * math.sin(ang) * math.cos(br))
    l2 = l1 + math.atan2(
        math.sin(br) * math.sin(ang) * math.cos(p1),
        math.cos(ang) - math.sin(p1) * math.sin(p2),
    )
    return math.degrees(p2), math.degrees(l2)


def deg_to_dms(deg):
    deg = abs(deg)
    d = int(deg)
    m = int((deg - d) * 60)
    s = round((deg - d - m / 60) * 3600 * 1000)
    return ((d, 1), (m, 1), (s, 1000))


def make_jpeg(path, text, lat=None, lon=None, heading=None,
              taken="2021:07:14 15:00:00", content_label=None):
    img = Image.new("RGB", (320, 240), (random.randint(40, 200),) * 3)
    ImageDraw.Draw(img).text((10, 110), text, fill=(255, 255, 0))
    exif_dict = {"0th": {}, "Exif": {piexif.ExifIFD.DateTimeOriginal: taken.encode()}, "GPS": {}}
    if content_label:
        exif_dict["Exif"][piexif.ExifIFD.UserComment] = b"ASCII\x00\x00\x00" + content_label.encode()
    if lat is not None:
        exif_dict["GPS"] = {
            piexif.GPSIFD.GPSLatitudeRef: b"N" if lat >= 0 else b"S",
            piexif.GPSIFD.GPSLatitude: deg_to_dms(lat),
            piexif.GPSIFD.GPSLongitudeRef: b"E" if lon >= 0 else b"W",
            piexif.GPSIFD.GPSLongitude: deg_to_dms(lon),
        }
        if heading is not None:
            exif_dict["GPS"][piexif.GPSIFD.GPSImgDirectionRef] = b"T"
            exif_dict["GPS"][piexif.GPSIFD.GPSImgDirection] = (round(heading % 360 * 100), 100)
    img.save(path, "JPEG", exif=piexif.dump(exif_dict))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--bundles", default="data/bundles")
    ap.add_argument("--out", default="data/test-library")
    ap.add_argument("--hits", type=int, default=10)
    ap.add_argument("--seed", type=int, default=20260610)
    args = ap.parse_args()

    random.seed(args.seed)
    wants = []
    for path in sorted(Path(args.bundles, "bundles").glob("*.json")):
        wants.extend(json.loads(path.read_text())["wants"])
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.jpg"):
        old.unlink()

    manifest = []

    def is_isolated(want):
        """No other want's reach circle can contain a photo planted <=100 m away."""
        g = want["geo"]
        return all(
            o is want
            or haversine_m(g["lat"], g["lon"], o["geo"]["lat"], o["geo"]["lon"])
            > o["geo"]["radius_m"] + 60 + 100 + 50
            for o in wants
        )

    isolated = [w for w in wants if is_isolated(w)]
    dense = [w for w in wants if w not in isolated]
    n_iso = min(args.hits // 2 + 1, len(isolated))
    hit_wants = random.sample(isolated, n_iso) + random.sample(dense, args.hits - n_iso)
    used = set(map(id, hit_wants))
    wrong_heading_wants = random.sample([w for w in wants if id(w) not in used], 2)
    used.update(map(id, wrong_heading_wants))
    mismatch_wants = random.sample([w for w in isolated if id(w) not in used], 2)

    def plant(want, name, scenario, heading_offset=0.0, with_heading=True,
              content_label=None, taken=None):
        geo = want["geo"]
        bearing_from_want = random.uniform(0, 360)
        dist = random.uniform(15, min(100, geo["radius_m"]))
        lat, lon = offset_point(geo["lat"], geo["lon"], bearing_from_want, dist)
        heading = None
        if with_heading:
            # camera points back toward the want (plus scenario offset + compass noise)
            heading = (bearing_from_want + 180 + heading_offset + random.uniform(-10, 10)) % 360
        if taken is None:
            year = random.randint(2015, 2024)
            taken = f"{year}:{random.randint(1,12):02d}:{random.randint(1,28):02d} 12:00:00"
        if content_label is None:
            labels = want["subject"].get("classifier_labels") or ["building"]
            content_label = labels[0]
        make_jpeg(out / name, f"{scenario}\n{want['subject']['label'][:30]}",
                  lat, lon, heading, taken, content_label)
        manifest.append({"file": name, "scenario": scenario, "expected_want_id": want["id"]})
        return taken

    burst_anchors = []
    for i, want in enumerate(hit_wants):
        if i % 3 == 2:
            plant(want, f"hit_no_heading_{i:02d}.jpg", "hit_no_heading", with_heading=False)
        elif is_isolated(want):
            taken = plant(want, f"hit_{i:02d}.jpg", "hit")
            burst_anchors.append((want, taken))
        else:
            plant(want, f"hit_dense_{i:02d}.jpg", "hit_dense")
    for i, want in enumerate(wrong_heading_wants):
        plant(want, f"wrong_heading_{i:02d}.jpg", "wrong_heading", heading_offset=180)
    for i, want in enumerate(mismatch_wants):
        plant(want, f"semantic_mismatch_{i:02d}.jpg", "semantic_mismatch", content_label="selfie")

    # no-GPS photos taken 8 minutes after a hit photo: the burst-clustering
    # fallback should borrow the anchor's position and find the same want
    for i, (want, anchor_taken) in enumerate(burst_anchors[:2]):
        date, clock = anchor_taken.split(" ")
        h, m, s = map(int, clock.split(":"))
        taken = f"{date} {h:02d}:{m + 8:02d}:{s:02d}"
        labels = want["subject"].get("classifier_labels") or ["building"]
        name = f"no_gps_burst_{i}.jpg"
        make_jpeg(out / name, f"no_gps_burst\n{want['subject']['label'][:30]}",
                  taken=taken, content_label=labels[0])
        manifest.append({"file": name, "scenario": "no_gps_burst", "expected_want_id": want["id"]})

    # far decoys: clear of every want's 2x reach so no candidate should fire
    decoys = 0
    while decoys < 3:
        base = random.choice(wants)["geo"]
        lat, lon = offset_point(base["lat"], base["lon"], random.uniform(0, 360), random.uniform(2500, 4000))
        if all(
            haversine_m(lat, lon, w["geo"]["lat"], w["geo"]["lon"]) > 2 * (w["geo"]["radius_m"] + 60) + 300
            for w in wants
        ):
            name = f"far_decoy_{decoys}.jpg"
            make_jpeg(out / name, "far_decoy", lat, lon, random.uniform(0, 360), content_label="selfie")
            manifest.append({"file": name, "scenario": "far_decoy", "expected_want_id": None})
            decoys += 1

    # timestamped in 2009, far from every other photo, so burst clustering
    # cannot borrow a position
    for i in range(2):
        name = f"no_gps_{i}.jpg"
        make_jpeg(out / name, "no_gps", taken=f"2009:03:0{i + 1} 09:00:00")
        manifest.append({"file": name, "scenario": "no_gps", "expected_want_id": None})

    (out / "manifest.json").write_text(json.dumps({"photos": manifest}, indent=1) + "\n")
    print(f"wrote {len(manifest)} photos + manifest.json to {out}")


if __name__ == "__main__":
    main()
