#!/usr/bin/env python3
"""Fetch geocoded items missing an image (P18) from Wikidata for a bounding box.

Pages through query.wikidata.org and writes {"rows": [...]} JSON compatible
with compile_wants.py. Run this where you have network access to WDQS;
results are committed under data/raw/ so compilation is reproducible offline.

Example (the Seattle test box):
    python3 compiler/fetch_wikidata.py \
        --bbox -122.46 47.48 -122.22 47.74 \
        --out data/raw/seattle-p18-missing.json
"""

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request

ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "most-wanted-compiler/0.1 (https://github.com/ragesoss/most-wanted)"

QUERY = """\
SELECT ?item ?itemLabel ?coord ?sitelinks
       (GROUP_CONCAT(DISTINCT STRAFTER(STR(?class), "/entity/"); separator="|") AS ?classes)
       (MIN(?end) AS ?endDate)
WHERE {{
  SERVICE wikibase:box {{
    ?item wdt:P625 ?coord .
    bd:serviceParam wikibase:cornerSouthWest "Point({west} {south})"^^geo:wktLiteral .
    bd:serviceParam wikibase:cornerNorthEast "Point({east} {north})"^^geo:wktLiteral .
  }}
  MINUS {{ ?item wdt:P18 [] }}
  ?item wikibase:sitelinks ?sitelinks .
  OPTIONAL {{ ?item wdt:P31 ?class . }}
  OPTIONAL {{ ?item wdt:P576 ?end . }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
GROUP BY ?item ?itemLabel ?coord ?sitelinks
ORDER BY ?item
LIMIT {limit} OFFSET {offset}
"""

WD_ENTITY_PREFIX = "http://www.wikidata.org/entity/"


def run_query(sparql, retries=4):
    data = urllib.parse.urlencode({"query": sparql, "format": "json"}).encode()
    req = urllib.request.Request(ENDPOINT, data=data, headers={"User-Agent": USER_AGENT})
    delay = 2
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                return json.load(resp)
        except Exception as exc:  # noqa: BLE001 - retry whatever WDQS throws
            if attempt == retries:
                raise
            print(f"query failed ({exc}); retrying in {delay}s", file=sys.stderr)
            time.sleep(delay)
            delay *= 2
    raise AssertionError("unreachable")


def simplify(binding):
    row = {}
    for var, cell in binding.items():
        value = cell["value"]
        if value.startswith(WD_ENTITY_PREFIX):
            value = value[len(WD_ENTITY_PREFIX) :]
        row[var] = value
    return row


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--bbox", nargs=4, type=float, required=True,
                    metavar=("WEST", "SOUTH", "EAST", "NORTH"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--page-size", type=int, default=200)
    ap.add_argument("--sleep", type=float, default=2.0,
                    help="seconds between pages (be polite to WDQS)")
    args = ap.parse_args()

    west, south, east, north = args.bbox
    rows = []
    offset = 0
    while True:
        sparql = QUERY.format(west=west, south=south, east=east, north=north,
                              limit=args.page_size, offset=offset)
        result = run_query(sparql)
        page = [simplify(b) for b in result["results"]["bindings"]]
        rows.extend(page)
        print(f"offset {offset}: {len(page)} rows")
        if len(page) < args.page_size:
            break
        offset += args.page_size
        time.sleep(args.sleep)

    with open(args.out, "w") as fh:
        json.dump({"rows": rows}, fh, indent=1, ensure_ascii=False)
    print(f"wrote {len(rows)} rows to {args.out}")


if __name__ == "__main__":
    main()
