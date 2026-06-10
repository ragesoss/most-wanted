# most-wanted

An app that scans the data already on your device (starting with photos) and
surfaces the specific items that open knowledge projects actively want —
matched privately on-device, reviewed by you, and uploaded with clean
metadata. See [PLAN.md](PLAN.md) for the full project plan.

The **demand registry is the real project**: a compiler turns existing
Wikimedia demand signals (Wikidata items missing an image, etc.) into a
standard "want" format, distributed as dumb, static, geo-sharded JSON
bundles. The mobile app is one client of that registry.

## Status: step 1 (compiler spike) — done

The spike from PLAN.md's build sequence: SPARQL query for geocoded
P18-missing items in one test region (Seattle), normalized to the wants
schema, emitted as geohash-sharded JSON bundles.

```
data/raw/*.json          real Wikidata query results (fixture, see data/raw/README.md)
        |
        v
compiler/compile_wants.py  + compiler/class_map.json
        |
        v
data/bundles/bundles/<geohash>.json   one bundle per occupied geohash-5 cell
data/bundles/index.json               cell -> count/bytes, compile stats
data/bundles/report.json              exclusions + unmapped classes for triage
```

Run it:

```sh
python3 compiler/compile_wants.py --raw data/raw --out data/bundles --precision 5
```

To refetch raw data (needs network access to query.wikidata.org):

```sh
python3 compiler/fetch_wikidata.py --bbox -122.46 47.48 -122.22 47.74 \
    --out data/raw/seattle-p18-missing.json
```

No dependencies beyond Python 3 stdlib.

## Layout

- `PLAN.md` — project plan (scope, architecture, build sequence, open questions)
- `schema/want.schema.json`, `schema/bundle.schema.json` — the wants format
- `compiler/fetch_wikidata.py` — pages WDQS for P18-missing geocoded items in a bbox
- `compiler/class_map.json` — **the central vocabulary mapping** (Wikidata P31
  class → include/exclude decision + classifier labels + match radius)
- `compiler/compile_wants.py` — raw rows → wants → geohash-sharded bundles
- `data/raw/` — committed real-data fixture for the Seattle test box
- `data/bundles/` — committed compiler output for inspection

## Spike findings (Seattle test box, −122.46 47.48 → −122.22 47.74)

1. **Volume and bundle sizing validate the "map tiles" distribution model.**
   The box (~18 × 29 km) holds **910** geocoded P18-missing items. The
   393-item fixture compiles to 264 wants across 30 geohash-5 cells,
   ~207 KB pretty-printed total; the densest cell (downtown, `c23nb`) is
   104 wants / 80 KB. Extrapolated to the full 910 items that's roughly
   half a megabyte uncompressed for all of Seattle — easily within "client
   downloads a broad region" budget.

2. **The raw signal is noisy; the class map is load-bearing.** The single
   most common P31 class among P18-missing items in the box is *nonprofit
   organization* (97 of 910), followed by other org-shaped classes that
   geocode to office addresses. Electoral districts, sports seasons, and
   timelines also carry coordinates. About a third of fixture items are
   excluded or held for review by `class_map.json`. A compiler without
   class filtering would ship junk wants and poison donor trust on first
   scan.

3. **The retrospective (`time_window`) thesis shows up immediately in real
   data.** 26 items in the box are classed *destroyed building or
   structure* (e.g. the Duwamish Drive-In, the old Seattle Opera House) —
   wants that can only be fulfilled from somebody's old photo library,
   which is exactly the inversion this project is built on. The compiler
   emits `time_window` for these (`historical: true`, or `before:` when
   Wikidata has a P576 end date).

4. **Privacy interactions appear in the demand signal itself.** The box
   contains geocoded P18-missing items that are *single-family detached
   homes* (and "house of Jeff Bezos"). The class map has an
   `exclude_privacy` decision that wins over any include-class: the
   registry should not solicit photos of private residences regardless of
   notability.

5. **Compiler must group, not stream, rows.** One item arrives as multiple
   SPARQL rows (one per P31 class and per P625 coordinate — e.g. streams
   with several coordinates). Items with no English label (bare QIDs,
   often bot-created) are also skipped — a donor can't confirm a match
   against a label they can't read.

6. **Sitelink count works as a cheap priority signal.** Discovery
   Institute (20 sitelinks) vs. a long tail of 0-sitelink nonprofits;
   wants within a bundle are sorted by it.

## Next (per PLAN.md build sequence)

2. **Matcher prototype (desktop):** CLI that takes a photo folder, reads
   EXIF, spatial-joins against these bundles, runs an embedding model for
   category rejection. This is the cheapest falsification test of the
   whole concept.
3. **Schema hardening:** grow `class_map.json` (49 unmapped classes are
   already queued in `data/bundles/report.json`), tiering thresholds,
   `status_check` semantics.
