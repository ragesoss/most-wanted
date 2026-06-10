#!/usr/bin/env python3
"""Compile raw Wikidata 'missing image' rows into geo-sharded want bundles.

Input: JSON files in --raw, each {"rows": [...]} as produced by
fetch_wikidata.py (or any source matching that row shape):

    {
      "item": "Q1354391",            # bare QID
      "itemLabel": "Fremont Troll",
      "coord": "Point(-122.34728 47.650955)",   # WKT, lon lat
      "sitelinks": "8",
      "classes": "Q860861|Q179700",  # P31 QIDs, pipe-joined (may be absent)
      "endDate": "2002-01-01T00:00:00Z"  # optional, min P576 (dissolved/demolished)
    }

The same item may appear in several rows (multiple P625 values, paging
overlap); rows are grouped by QID and classes are unioned.

Output in --out:
    bundles/<geohash>.json   one bundle per occupied cell (schema/bundle.schema.json)
    index.json               cell -> want count, plus compile stats
    report.json              what was excluded and why, and every class QID
                             the class map doesn't know yet (decision counts
                             by class, so the map can be grown deliberately)

Filtering philosophy (see PLAN.md): precision over recall. Items are only
emitted as wants when at least one of their classes is an explicit
'include' in class_map.json. Unknown classes land in the report, not in
bundles.
"""

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from geohash import encode as geohash_encode

FORMAT_VERSION = "0.1"
PUBLISHER = "wikimedia/wikidata-p18-missing"
WANT_ID_PREFIX = "wd-p18"


def parse_point(wkt):
    # "Point(-122.34728 47.650955)" -> (lat, lon)
    inner = wkt.strip()[len("Point(") : -1]
    lon_s, lat_s = inner.split()
    return float(lat_s), float(lon_s)


def load_items(raw_dir):
    """Group raw rows by QID, unioning classes and keeping the first coord."""
    items = {}
    for path in sorted(Path(raw_dir).glob("*.json")):
        rows = json.loads(path.read_text())["rows"]
        for row in rows:
            qid = row["item"]
            entry = items.setdefault(
                qid,
                {
                    "qid": qid,
                    "label": row.get("itemLabel", qid),
                    "coord": row["coord"],
                    "sitelinks": int(row.get("sitelinks", 0)),
                    "classes": set(),
                    "end_date": row.get("endDate"),
                },
            )
            classes = row.get("classes") or ""
            entry["classes"].update(c for c in classes.split("|") if c)
            entry["sitelinks"] = max(entry["sitelinks"], int(row.get("sitelinks", 0)))
            if not entry.get("end_date") and row.get("endDate"):
                entry["end_date"] = row["endDate"]
    return items


def decide(entry, class_map):
    """Return (decision, detail). exclude_privacy > include > exclude > review."""
    classes = class_map["classes"]
    decisions = {qid: classes.get(qid, {}).get("decision", "unknown") for qid in entry["classes"]}

    if "exclude_privacy" in decisions.values():
        return "exclude_privacy", None
    included = [qid for qid, d in decisions.items() if d == "include"]
    if included:
        return "include", included
    if not entry["classes"]:
        return "no_class", None
    if all(d == "exclude" for d in decisions.values()):
        return "exclude", None
    return "review", None


def build_want(entry, included_classes, class_map):
    classes = class_map["classes"]
    classifier_labels = []
    radii = []
    historical = False
    for qid in included_classes:
        spec = classes[qid]
        for lab in spec.get("classifier_labels", []):
            if lab not in classifier_labels:
                classifier_labels.append(lab)
        if "radius_m" in spec:
            radii.append(spec["radius_m"])
        historical = historical or spec.get("historical", False)
    # A class radius overrides the default; with several classes, the most
    # permissive (largest) wins so no geo candidate is dropped prematurely.
    radius = max(radii) if radii else class_map["default_radius_m"]

    lat, lon = parse_point(entry["coord"])
    want = {
        "id": f"{WANT_ID_PREFIX}/{entry['qid']}",
        "publisher": PUBLISHER,
        "type": "photo",
        "subject": {
            "wikidata_qid": entry["qid"],
            "label": entry["label"],
            "classes": sorted(entry["classes"]),
            "classifier_labels": classifier_labels,
        },
        "geo": {"lat": lat, "lon": lon, "radius_m": radius},
        "priority": {"sitelinks": entry["sitelinks"]},
        "constraints": {
            "license_required": "CC-BY-SA-4.0",
            "sensitivity": ["strip_gps_homes", "flag_faces"],
        },
        "fulfillment": {
            "endpoint": "commons_upload",
            "structured_data": {"depicts": entry["qid"]},
        },
        "status_check": {
            "sparql_ask": f"ASK {{ wd:{entry['qid']} wdt:P18 [] }}"
        },
    }
    if historical or entry.get("end_date"):
        tw = {}
        if entry.get("end_date"):
            tw["before"] = entry["end_date"][:10]
        else:
            tw["historical"] = True
        want["time_window"] = tw
    return want


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--raw", default="data/raw", help="directory of raw row files")
    ap.add_argument("--out", default="data/bundles", help="output directory")
    ap.add_argument("--class-map", default=str(Path(__file__).parent / "class_map.json"))
    ap.add_argument("--precision", type=int, default=5, help="geohash precision for sharding")
    args = ap.parse_args()

    class_map = json.loads(Path(args.class_map).read_text())
    items = load_items(args.raw)

    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    shards = {}
    stats = Counter()
    unmapped = Counter()  # class QID -> item count, for growing the map
    excluded = {"exclude": [], "exclude_privacy": [], "review": [], "no_class": [], "unlabeled": []}

    for entry in items.values():
        decision, included_classes = decide(entry, class_map)
        if decision == "include" and entry["label"] == entry["qid"]:
            # No English label: the donor would be shown a bare QID and the
            # classifier gets no help; precision-over-recall says skip.
            decision = "unlabeled"
        if decision != "include":
            stats[decision] += 1
            excluded[decision].append(entry["qid"])
            for qid in entry["classes"]:
                if qid not in class_map["classes"]:
                    unmapped[qid] += 1
            continue
        stats["include"] += 1
        want = build_want(entry, included_classes, class_map)
        cell = geohash_encode(want["geo"]["lat"], want["geo"]["lon"], args.precision)
        shards.setdefault(cell, []).append(want)

    out = Path(args.out)
    bundles_dir = out / "bundles"
    bundles_dir.mkdir(parents=True, exist_ok=True)
    for old in bundles_dir.glob("*.json"):
        old.unlink()

    index = {
        "format_version": FORMAT_VERSION,
        "generated": generated,
        "publisher": PUBLISHER,
        "geohash_precision": args.precision,
        "bundles": {},
        "stats": dict(stats, total_items=len(items)),
    }
    for cell in sorted(shards):
        wants = sorted(shards[cell], key=lambda w: -w["priority"]["sitelinks"])
        bundle = {
            "format_version": FORMAT_VERSION,
            "geohash": cell,
            "generated": generated,
            "wants": wants,
        }
        path = bundles_dir / f"{cell}.json"
        path.write_text(json.dumps(bundle, indent=1, ensure_ascii=False) + "\n")
        index["bundles"][cell] = {"count": len(wants), "bytes": path.stat().st_size}

    (out / "index.json").write_text(json.dumps(index, indent=1, ensure_ascii=False) + "\n")
    report = {
        "generated": generated,
        "excluded_items": excluded,
        "unmapped_classes": dict(unmapped.most_common()),
    }
    (out / "report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")

    total_bytes = sum(b["bytes"] for b in index["bundles"].values())
    print(f"items in: {len(items)}")
    for k in ("include", "exclude", "exclude_privacy", "review", "no_class", "unlabeled"):
        print(f"  {k}: {stats.get(k, 0)}")
    print(f"bundles: {len(index['bundles'])} cells at precision {args.precision}, {total_bytes} bytes total")
    if unmapped:
        print(f"unmapped classes: {len(unmapped)} (see report.json)")


if __name__ == "__main__":
    main()
