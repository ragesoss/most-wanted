#!/usr/bin/env python3
"""Score a matcher report against the synthetic library's ground truth.

Checks, per scenario:
    hit                   isolated want: expected is the top candidate at
                          auto_suggest
    hit_dense /           expected want appears at worth_a_look or better;
    hit_no_heading        rank among near neighbors is allowed to vary, since
                          a dense block legitimately yields several candidates
                          for the human to pick from
    wrong_heading         expected want may appear but must NOT be auto_suggest
    far_decoy             no candidates at any tier
    no_gps                photo routed to the no-GPS pile
"""

import argparse
import json
from collections import Counter
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--report", required=True)
    ap.add_argument("--manifest", required=True)
    args = ap.parse_args()

    report = json.loads(Path(args.report).read_text())
    manifest = json.loads(Path(args.manifest).read_text())["photos"]
    by_file = {p["file"]: p for p in report["photos"]}

    results = Counter()
    failures = []

    def check(name, ok, detail=""):
        results["pass" if ok else "fail"] += 1
        if not ok:
            failures.append(f"{name}: {detail}")

    for truth in manifest:
        name, scenario, expected = truth["file"], truth["scenario"], truth["expected_want_id"]
        if scenario == "no_gps":
            check(name, name in report["no_gps"], "should be in no_gps pile")
            continue
        entry = by_file.get(name)
        if entry is None:
            check(name, False, "missing from report")
            continue
        cands = entry["candidates"]
        top = cands[0] if cands else None
        if scenario == "far_decoy":
            check(name, not cands, f"expected no candidates, got {top and top['want_id']}")
        elif scenario == "hit":
            ok = top and top["want_id"] == expected and top["tier"] == "auto_suggest"
            check(name, ok, f"expected {expected}@auto_suggest, got {top and (top['want_id'], top['tier'])}")
        elif scenario in ("hit_dense", "hit_no_heading"):
            ok = any(
                c["want_id"] == expected and c["tier"] in ("auto_suggest", "worth_a_look")
                for c in cands
            )
            check(name, ok, f"expected {expected} among candidates, got {[c['want_id'] for c in cands]}")
        elif scenario == "wrong_heading":
            bad = any(c["want_id"] == expected and c["tier"] == "auto_suggest" for c in cands)
            check(name, not bad, "expected want must not be auto_suggest with reversed heading")

    print(f"pass: {results['pass']}  fail: {results['fail']}")
    for f in failures:
        print("  FAIL", f)
    raise SystemExit(1 if results["fail"] else 0)


if __name__ == "__main__":
    main()
