# most-wanted

An app that scans the data already on your device (starting with photos) and
surfaces the specific items that open knowledge projects actively want —
matched privately on-device, reviewed by you, and uploaded with clean
metadata. See [PLAN.md](PLAN.md) for the full project plan.

The **demand registry is the real project**: a compiler turns existing
Wikimedia demand signals (Wikidata items missing an image, etc.) into a
standard "want" format, distributed as dumb, static, geo-sharded JSON
bundles. The mobile app is one client of that registry.

## Status

- **Step 1 (compiler spike): done** — see below.
- **Step 2 (matcher prototype): logic built and tested synthetically;
  the real falsification test (precision on a real camera roll) is still
  pending.** `matcher/match_photos.py` reads EXIF (GPS, capture time,
  compass heading) from a folder of JPEGs, spatial-joins against the
  bundles, and tiers candidates per the plan (`auto_suggest` /
  `worth_a_look` / `long_shot`). It includes:

  - **Semantic rejection** (`--semantic clip`): zero-shot open_clip scoring
    of each geo candidate against its want's `classifier_labels` vs. fixed
    negative prompts (selfie, food, pet, screenshot...). Rejected
    candidates are dropped; "unsure" caps a candidate at `worth_a_look`;
    `auto_suggest` requires classifier agreement. Spatial join always runs
    first — the classifier only sees geo candidates. (`ViT-B-32` is a
    desktop stand-in for the MobileCLIP-class model a mobile client would
    ship. CLIP inference is wired but not yet validated end-to-end: the
    build environment couldn't download model weights. `--semantic
    exif-tag` is a test-only backend that exercises the same code paths
    using ground-truth labels planted by the test generator.)
  - **No-GPS burst clustering**: photos without GPS but with a timestamp
    inherit the position of the nearest-in-time geotagged photo within a
    window (default 45 min), with extra distance slack for walking drift.
    Inferred positions are never auto-suggested.

  Since no real photo library was available, `matcher/make_test_library.py`
  fabricates one — tiny JPEGs whose EXIF is planted relative to actual
  Seattle wants (isolated hits, dense-cluster hits, reversed headings,
  semantic mismatches, burst-clustered GPS-less photos, far decoys) — and
  `matcher/evaluate.py` scores the matcher against that ground truth:
  21/21 scenarios pass across 10 random seeds.

  ```sh
  pip install Pillow piexif      # piexif alone suffices for match_photos.py
  pip install torch open_clip_torch   # only for --semantic clip
  python3 matcher/make_test_library.py                 # writes data/test-library/
  python3 matcher/match_photos.py --photos data/test-library --semantic exif-tag --out report.json
  python3 matcher/evaluate.py --report report.json --manifest data/test-library/manifest.json
  ```

  To run against a real library: point `--photos` at any folder of JPEGs
  (HEIC must be converted first) and use `--semantic clip` (or `off`).

## Step 1 (compiler spike) — done

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
   393-item fixture compiles to 301 wants across 30 geohash-5 cells,
   ~236 KB pretty-printed total; the densest cell (downtown, `c23nb`) is
   119 wants / 90 KB. Extrapolated to the full 910 items that's roughly
   half a megabyte uncompressed for all of Seattle — easily within "client
   downloads a broad region" budget.

2. **The raw signal is noisy; the class map is load-bearing.** The single
   most common P31 class among P18-missing items in the box is *nonprofit
   organization* (97 of 910), followed by other org-shaped classes that
   geocode to office addresses. Electoral districts, sports seasons,
   murders, telephone area codes, and timelines also carry coordinates.
   About a quarter of fixture items are excluded or held for review by
   `class_map.json` (now 200 classes; every class observed in the fixture
   is mapped). A compiler without class filtering would ship junk wants
   and poison donor trust on first scan.

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

7. **(From the matcher work) Most urban wants are not isolated.** Only
   71 of the 301 Seattle wants have no other want's match circle within
   plant distance — downtown storefront rows and nested park/dam circles
   overlap heavily. So in cities, the dominant matcher mode is "rank a
   handful of candidates and let the human pick," exactly as the plan
   assumed; strict auto-suggest is reserved for heading agreement or
   unambiguous near-field (<30 m) positions, and a heading that points
   *away* blocks auto-suggest even at near-field (precision over recall).

8. **Semantic rejection is what keeps dense clusters usable.** Around Pike
   Place Market the bundles hold a restaurant, a doughnut stand, a comics
   shop, and the Giant Shoe Museum within ~30 m of each other; in
   classifier-off test runs the right want sometimes falls below the
   top-5 display cut, while even coarse category labels (restaurant vs.
   museum vs. bookstore) restore it. The classifier isn't polish — in
   dense areas it's what makes the candidate list short enough to swipe.

## Next (per PLAN.md build sequence)

2. **Finish the matcher falsification test:** run `match_photos.py
   --semantic clip` on a real camera roll (export from Photos/Takeout,
   convert HEIC → JPEG) and measure precision. First run downloads CLIP
   weights, which also validates the clip backend end-to-end; the
   agree/reject thresholds in `matcher/semantic.py` will need calibration
   against real photos.
3. **Schema hardening:** tiering thresholds, `status_check` semantics,
   revisit the 16 review-pile items in `data/bundles/report.json`.
4. **Mobile client** / **5. Upload path** / **6. Community engagement**
   as planned.
