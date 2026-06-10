# Demand-signal sources — research survey

*Researched June 2026 via parallel web research. The build environment could not
fetch most primary sites directly (Wikimedia, Toolforge, and many project sites
403'd the fetch proxy), so some claims rest on search-engine extracts of the
primary pages. Anything not confirmed against primary text is flagged
⚠ unverified, with the URL to check. See the [verification checklist](#verification-checklist)
at the end.*

PLAN.md lists six v1 signals (geocoded P18-missing, other image properties,
WikiShootMe, requested-photo categories, WLM lists, image-suggestions
pipeline). This survey maps the full landscape — Wikimedia and beyond — and
ranks what to add next.

## Scoring axes

Every source is judged on:

1. **Specificity** — "photo of THIS plaque, from here" vs. "any photo of a church"
2. **Machine readability** — API/SPARQL/dump vs. wikitext scraping vs. free text
3. **Geocodability + identifiers** — native coords and stable IDs vs. place-name strings
4. **Volume / freshness**
5. **Auto-expiry** — does fulfillment mechanically close the want?
6. **License compatibility** — can a CC photo upload satisfy it, and can one photo serve both this source and Commons?
7. **Intent strength** — a human asked > a campaign endorses > a curated list implies > a derived gap

The single most useful framing that emerged: **intent strength is a spectrum
the schema should encode** (`human_request` > `campaign` > `curated_list` >
`derived_gap`), because everything else (review friction, auto-suggest
eligibility, ranking) can hang off it.

## Headline ranking

**Add next (beyond the current six), in order:**

| # | Source | Why |
|---|--------|-----|
| 1 | **de.wiki `{{Bilderwunsch}}`** via bldrwnsch | The strongest human-asserted signal in the movement: shot-level requests with explicit lat/lon + free-text shot description ("pinkes Haus an der Ecke"), scope rules that pre-exclude unfulfillable wants, and an existing bulk GeoJSON/GPX/KML export. |
| 2 | **Wikidata media-property family beyond P18** | P1442 (grave), P5775 (interior), P1801 (plaque), P9906 (inscription), P9721 (entrance), P3451/P5252 (night/winter view), P8592 (aerial), P1766 (place-name sign). Pure SPARQL, auto-closing, native to the existing compiler. The schema already anticipated these. |
| 3 | **Open Plaques unphotographed lists** | First confirmed non-Wikimedia source with *explicit* per-object want lists (`/unphotographed`), JSON/GeoJSON API, stable IDs cross-walked to Wikidata (P1893) and OSM, CC-only photo policy, and auto-fulfillment via Flickr machine tags / Commons — one upload closes both wants. The v2 federation pilot. |
| 4 | **en.wiki `{{photo requested}}` tree** (+ ja/fr/ru analogs) | High intent, large (~20k+ root alone), but stale by construction — usable only with a "still unillustrated?" recompute and article-coordinate join at compile time. |
| 5 | **Lingua Libre / P443 pronunciation wants** | Turnkey audio wants: Olafbot publishes lemmas-without-audio lists for 72 languages, daily, demand-ranked by Wiktionary count, self-closing. Sharding key is language area, not coordinates — a schema stretch worth doing (PLAN.md already calls audio "a plausible early add"). |

**Confirmed traps** (look promising, don't build on them):

| Trap | Why it fails |
|------|--------------|
| Macaulay Library / eBird "Most Wanted" | Explicit curated lists (≈302 species missing photos), but submissions are non-CC (Cornell NC sublicensing). Demand signal only; the asset can't dual-serve Commons. |
| Open Library covers, MusicBrainz Cover Art Archive | Covers/cover art are copyrighted artwork — a CC photo of one is still derivative. Also non-geo. Exclude. |
| iNaturalist (as fulfillment target) | Default license CC BY-NC — not Commons-compatible. Only useful when the uploader opts into BY/BY-SA/CC0. (Pl@ntNet, by contrast, publishes validated observations CC BY-SA.) |
| OSM "POI missing `image=*`" | Image-tag coverage is so sparse (≪1% of POIs) that absence is the default state, not a signal. Only meaningful intersected with heritage/wikidata tags — at which point the real want is the Wikidata gap. |
| WMF Image Suggestions pipeline (as a feed) | Inverse direction (matches *existing* Commons images to articles); the suggestion store is internal (Cassandra/Hive, 3-week TTL). But see [the subtraction trick](#the-subtraction-trick) — its public search keyword is valuable. |
| Fixed-station monitoring (CoastSnap, Chronolog) | Superb geo fit (station lists = ready-made shards) but wants are *prospective and recurring* (next shot from a cradle/bracket — a retrospective camera-roll scan can't fulfill them), and submission licenses are unverified/likely non-CC. Wrong shape for this app. |
| KartaView, re.photos, HistoryPin, FotoQuest Go, LandSense, Picture Post | Stagnant, no want concept, or concluded. (Ajapaik — open-source rephotography with Wikimedia ties — flagged for a future look.) |

---

## Wikimedia signals

### 1. Wikidata media-property family (the native substrate)

All confirmed datatype `commonsMedia`. The compiler can generate each want type
from a SPARQL shape; adding the statement closes the want.

**Field-photography wants (core):**

| Property | Label | Trigger population / SPARQL shape |
|----------|-------|------------------------------------|
| P18 | image | The universal want. Current compiler input. |
| P1442 | image of grave | human ∧ dead (P570) ∧ burial place (P119) → **geo-shard via the cemetery's P625**, not the person's. The property's own constraint block (requires P119/P570, type=human…) is machine-readable spec for the trigger population. |
| P5775 | image of interior | Best as second-order want: building *has* exterior P18 but no P5775 — P18 presence confirms a real, photographable building. Caveat: interiors often not publicly accessible. |
| P3451 / P5252 | nighttime / winter view | Given P18 exists. Huge theoretical volume, weak per-item intent — class-gate hard. Winter view is climate-gated (a geo-sharded registry can encode that). |
| P8592 / P4291 / P5282 | aerial / panoramic / 360° view | Located features. |
| P9721 | image of entrance | Buildings, stations, venues. |
| P1801 | commemorative plaque image | High-precision trigger: items holding an Open Plaques ID (P1430). |
| P9906 | inscription image | Monuments/artworks with inscription (P1684). |
| P1766 | place name sign | Settlements; very photographable. |

**Not field-photography** (route elsewhere, don't put in photo bundles):
emblem/document images (P94 coat of arms, P41 flag, P109 signature, P3311
"image of design plans" — fulfilled from archives or by illustrators); map/
diagram properties (P15, P242, P1846, P181, …) — drawing wants, machine-
generatable.

**Audio/AV:** P443 pronunciation (see §5), P51 audio (anthems, animal calls —
genuine field-recording want), P990 voice of person (hard), P10 video (low
usage).

**Special: P4765 "Commons compatible image available at URL"** — a want that
carries its own fulfillment. WikiProject Sum of All Paintings runs a bot twice
daily that uploads provably-PD P4765 images, adds P18, removes P4765 — a fully
automated close loop. Not a field want, but the model for `status_check` +
auto-expiry mechanics.

**Published scale figures** (dated, ⚠ re-verify live):
- 2018: ~2.2M of 40M items had P18 (~5.5%); 17% of human items.
  ([WMF blog](https://wikimediafoundation.org/news/2018/03/14/machine-learning-visually-enriching-wikidata/))
- Oct 2018: 6.77M items with P625. ([addshore](https://addshore.com/2018/10/wikidata-map-october-2018/))
- No published current count of geocoded-missing-P18; WikiShootMe renders it
  but doesn't publish totals. One WDQS query away.

#### Precision rules (the compiler must adopt these)

The biggest precision killer: **missing P18 ≠ no photo exists.**

1. **Anti-want join:** exclude/down-rank items with P373 (Commons category),
   P935 (Commons gallery), or a sitelinked article that has images. WD-FIST
   exists precisely because this population is large — those are
   couch-fulfillable ("link the existing photo"), not field wants.
2. **Impossibility gates:** demolished/dissolved (P576, P3999, P5816);
   pre-photography death dates (P570 < ~1840 ⇒ the P18 want is really an
   artwork-digitization want); cremated/unknown burial for P1442; living
   people (BLP/consent — route to event photography, never auto-suggest).
3. **Coordinate quality:** P625 precision varies wildly (admin centroids put
   pins km off). WikiShootMe's fallback — use P131's coordinates when the item
   has none — is a useful recall lever but must cap the confidence tier.
4. **Class-gate the view-type wants** (P3451 etc.) or volume swamps intent.

### 2. Human-asserted requests (highest intent, smallest volume)

**de.wiki `{{Bilderwunsch}}` — best-in-class, the model to generalize.**
- In-article template (not talk page). First param is location mode: `hier`
  (article's own coordinates), `Koordinaten` (explicit lat/lon + ISO region +
  free-text shot description), `egal` (location-independent).
- Doc-page scope rules pre-filter exactly the noise our impossibility gates
  target: no demolished buildings, no FOP-impossible subjects, living people
  routed to event boards, organisms routed to Redaktion Biologie, museum
  objects routed to GLAM wishlist.
- **[bldrwnsch](https://bldrwnsch.toolforge.org/)** ([source](https://github.com/simon04/bldrwnsch))
  extracts all geocoded wishes from the dewiki replica (categorylinks ×
  geo_tags) and publishes **bulk `Bilderwuensche.geojson` / `.gpx` / `.kml`** —
  essentially a ready-made wants feed. Actively maintained.
- Cautionary tale attached: its predecessor **bwAPI died mid-2019**
  (single-maintainer registry). Don't depend on bldrwnsch at runtime —
  replicate its SQL in our compiler, or vendor its output.
- ⚠ Volume unverified (likely 10³–10⁴). First action:
  `curl https://bldrwnsch.toolforge.org/Bilderwuensche.geojson | jq '.features | length'`
- Closure: template removed on fulfillment → next extract drops it. Manual but
  reliably coupled.

**en.wiki `{{Image requested}}` / `{{photo requested}}` tree.**
- Talk-page templates → `Category:Wikipedia requested photographs` by-location
  and by-subject trees (root alone ~20,212 pages; full tree likely hundreds of
  thousands ⚠ — one PetScan run, ns=1, gives the real number).
- Geo is **category-by-place strings**, no coordinates — join the article's
  geo_tags / Wikidata P625/P131 (exactly what bldrwnsch does for dewiki).
- **Structurally stale**: nothing removes the template when an image lands;
  there's a maintenance category "Articles which may no longer need images"
  and no purge bot. Rule: treat as intent signal only; recompute "still
  unillustrated" at compile time.

**Other languages:** ja.wiki 画像提供依頼 (prefecture-level categories, dated
reasons, modest volume); fr.wiki `Article à illustrer` (thematic, not geo;
single subcats >12k pages); ru.wiki `Статьи без иллюстраций` (auto-derived,
fresh, with facets for "Wikidata has an image but article doesn't" — that
facet is an anti-want list for us). es.wiki: no maintained system found.

**Commons:File requests** (the renamed Picture requests): a few requests/week,
free text, manual `{{Done}}` closure, sporadic inline coordinates. Highest
intent, lowest machine readability. Worth a periodic LLM-assisted parse, not a
pipeline. (The page itself points seekers to Wikidata missing-media lists.)

**Commons Photo challenge / Wiki Loves Folklore / Africa / Science:** theme
buckets with deadlines, not enumerable wants. Usable only as seasonal intent
multipliers.

### 3. Campaign and curated lists

**Wiki Loves Monuments monuments database** — >1.6M listings, >50 countries
([Commons:Monuments database](https://commons.wikimedia.org/wiki/Commons:Monuments_database)),
mid-migration: the wikitext-harvest pipeline (ErfgoedBot) is legacy; Wikidata
is canonical, and post-migration ErfgoedBot harvests *from* Wikidata via
SPARQL. API (`heritage.toolforge.org/api/`) + fresh SQL dumps each run.
Identifiers: P2186 (WLM ID) + national heritage-register external-ID
properties (cataloged at WikiProject Built heritage/Data sources). For our
compiler the practical move is **Wikidata-side: heritage-register ID present ∧
no P18** — campaign-endorsed intent, self-expiring, no dependency on the
legacy DB. No published global unphotographed count ⚠ (per-country stats
exist).

**Wiki Loves Earth** — the other campaign with enumerable lists: national
protected-area tables with coords + unique IDs, seeded from WDPA/Protected
Planet. Enumerable-but-leaky (out-of-list submissions allowed).

**Wiki Loves Public Art 2013** — dormant, but its residue (public-art items
with IDs/coords on Wikidata) remains mineable.

**Campaign time windows:** UploadWizard campaigns are **JSON pages in Commons'
`Campaign:` namespace with `enabled`/`start`/`end`** — machine-readable,
fetchable via API. Model: perennial want (unphotographed monument) × seasonal
intent multiplier (campaign window). This slots directly into the schema's
`time_window`.

**Listeria lists** (e.g. `Category:Wikidata items missing media` topical
lists, Sum of All Paintings "…without image" / "…with image possible") —
daily SPARQL regeneration means **fulfillment auto-closes on next bot run**,
the only wikitext mechanism with auto-expiry. Treat the underlying SPARQL as
the source, the wiki page as evidence of human curation (intent tier:
curated_list).

**GLAM wishlists:** `Commons:GLAM/Wish list` is ~17 items and stale; GLAM
flows run supply-direction. No systematic "photograph our objects" publishing
pattern exists. Don't build for it; revisit if a partner materializes.

### 4. Image Suggestions pipeline — inverse signal, one valuable byproduct

Confirmed: ALIS/SLIS matches **existing Commons images** to unillustrated
articles (P18 / Commons category / other-language lead image / MediaSearch
cascade), regenerated weekly, internal Cassandra store with 3-week TTL. Public
surfaces: `hasrecommendation:image` CirrusSearch keyword, `growthtasks`
generator, `growthimagesuggestiondata` prop. Newcomer acceptance ≈80% good
matches with quality gates; +24% mobile newcomer retention (Mar 2024
analysis). No public dump found ⚠.

<a name="the-subtraction-trick"></a>**The subtraction trick:** the set
`unillustrated MINUS hasrecommendation:image` is computable today entirely
from public APIs, and it means: *article needs an image and Commons
demonstrably has nothing suitable — a new photo is the only fix.* That is
arguably the strongest derived prioritization signal available and costs two
API calls per article set. Use it to boost want priority rather than as a
standalone source.

### 5. Audio wants: Lingua Libre / P443

- Olafbot maintains `Lemmas-without-audio-sorted-by-number-of-wiktionaries`
  lists for **72 languages, updated daily**, removing lemmas once *any*
  Commons pronunciation audio exists (self-closing), ranked by Wiktionary
  count (built-in demand score).
  ([Help:Querying Lingua Libre](https://lingualibre.org/wiki/Help:Querying_Lingua_Libre))
- Lingua Libre Bot writes P443 (with P407 language qualifier) to Wikidata and
  pushes to Wiktionaries — the close loop already exists.
- **Sharding key is language area, not coordinates.** Supporting it means the
  bundle index needs a non-geo axis (locale). Small files, low privacy risk,
  high fulfillment density (one session = hundreds of recordings) — but it's a
  *prospective* want (record now), not retrospective scanning. Fits a future
  "create mode," or matching against existing voice memos is a stretch.

---

## Beyond Wikimedia (v2 federation candidates)

### Strong candidates

**Open Plaques** — the best non-Wikimedia source found.
- Explicit `unphotographed` browsable lists per area (e.g. `/places/gb/unphotographed`).
- API: append `.json`/`.geojson`/`.csv` to URLs; bbox queries; ad-hoc dumps
  (stale: 2021–2023). ⚠ Whether `unphotographed` filters in the JSON API needs
  a live test; worst case filter the dump's photo field.
- Stable plaque IDs, cross-walked: Wikidata **P1893**, OSM `openplaques:id`.
- License: requires CC photos; data PD/CC0. **Auto-fulfillment already built:**
  they poll Flickr for machine tag `openplaques:id=NNN` (CC-checked) and pull
  from Commons — one Commons upload can close both the Wikimedia and Open
  Plaques want. Combine with Wikidata P1801 for a high-precision plaque want
  type.
- Liveness: "alive but low-energy" (volunteer-thin, stale dumps).

**OpenBenches** — ~42k memorial benches, full GeoJSON API
(`/api/benches`, `/api/nearest/`), **all photos CC BY-SA 4.0**, actively
maintained. Benches are *created by* photo upload so "zero photos" barely
exists; derived wants: missing media *type* (has inscription shot, lacks
"view" shot — media-type metadata exists) and **OSM memorial benches not yet
in OpenBenches** (`openbenches:id` crosswalk exists). Medium intent, single
active maintainer who wants it.

**Historic England — Missing Pieces Project** — explicit solicitation of
photos for **every NHLE entry (~400k)**, stable list-entry numbers +
coordinates: excellent shard material. License is a custom non-exclusive grant
to HE (not CC), so the *same photographer* can dual-upload to Commons under
CC — feasible, but HE fulfillment doesn't auto-satisfy Commons or vice versa.
⚠ "Entries lacking a photo" enumerability unverified. Note: NHLE IDs are on
Wikidata (P1216), so the *Wikimedia-side* version of this want (NHLE ID ∧ no
P18) is available in v1 without any federation.

**US NRHP via WikiProject NRHP** — ~95k+ listings, stable refnums + coords,
"percent illustrated" tracking by county, **Commons-native** (the want is
defined as a missing Commons image). Effectively a curated, campaign-adjacent
slice of the Wikidata signal — fold into v1 class-gating rather than treating
as a separate source.

### Different matching modality (not geo)

**Open Food Facts** — explicit typed photo wants in the states taxonomy
(`en:photos-to-be-uploaded`, plus front/ingredients/nutrition/packaging
photo-to-be-selected states), queryable via Search API
(`?states_tags=en:photos-to-be-uploaded`), full dumps, direct image-upload API
that auto-updates states. License: photos CC BY-SA *within OFF*, but packaging
shots are generally **not Commons-acceptable** (derivative of label art) — so
OFF is a separate fulfillment destination, and the matching modality is
barcode-in-shop, not camera-roll geo. A clean v2+ "barcode bundle" type if the
schema grows a non-geo shard axis. Typed sub-wants (front/ingredients/...)
are also the best existing example of **view-type want vocabulary** — same
idea as P5775/P3451.

**Street-level imagery (Panoramax, Mapillary)** — wants must be derived
(road network minus coverage); no public want feeds (Mapillary capture
projects are org-private ⚠). Panoramax is the v2-friendly one: federated,
STAC API, open licenses (CC-BY-SA/CC-BY/LO), MapComplete now uploads POI
photos there (CC0 default, ~85% of uploads) and writes `panoramax=*` OSM tags.
Low intent (derived) but unbounded volume and auto-closing coverage. A
"street-imagery coverage" want type is plausible later; not a v2 priority.

**OSM notes mentioning photos** — genuinely human-asked, geocoded (note ID +
lat/lon), full dumps + search API, but needle-in-haystack multilingual free
text and manual closure. A fun LLM-filtering experiment, not a pipeline.

### Demand-only sources (license-incompatible — the want is real, the asset can't dual-serve)

- **Macaulay Library / eBird "Most Wanted"**: curated Google Sheets (~302
  species missing photos, ~805 audio holes); Cornell license is non-exclusive
  but NC-sublicensed — not Commons-compatible. Could still *inform* priority
  on Wikidata taxa-missing-P18 wants (the photographer can upload separately
  to Commons).
- **IWM War Memorials Register**: explicit per-memorial solicitation, NC
  license.
- **BillionGraves**: geocoded photo-request system with claim/expiry mechanics
  (14-day claims — interesting prior art, as is Find a Grave's), proprietary
  license. Study the mechanics, skip the source.

### Biodiversity note

Wikidata taxa missing P18 is the v1-native version of the whole category and
overlaps iNat/GBIF/EOL gaps via external-ID properties. Of the external
ecosystems, only **Pl@ntNet** publishes validated observations under a
Commons-compatible license (CC BY-SA, exported to GBIF). Species wants are
range-geocodable at best — coarse shards, better treated as non-geo "subject
wants" with the classifier doing the work. Xeno-canto (~1,000 species with no
recordings) is the audio analog, mixed CC with heavy NC.

---

## Design implications for the registry

1. **Add `intent` to the want schema** (`human_request` | `campaign` |
   `curated_list` | `derived_gap`) and let tiering thresholds, review
   friction, and ranking key off it. Bilderwunsch wants can carry the
   requester's shot description into the UI; derived P3451 wants should never
   auto-suggest.
2. **Anti-want joins are as important as wants.** Compile-time exclusions:
   P373/P935/sitelink-image present (couch-fulfillable), WD-FIST candidates,
   ru.wiki's "Wikidata-has-image" facets, P4765 present. These aren't merely
   noise — they're a different want type (link/curate, not photograph) the
   registry could eventually serve to a different client.
3. **Expiry mechanics now have concrete models:** P18 write-back (Commons app
   Nearby), Listeria daily regen, Open Plaques Flickr machine-tag polling,
   Olafbot's Commons-audio check, SoAP's P4765→P18 bot. `status_check` should
   support "re-run the source query" (SPARQL wants) and "poll an external
   endpoint" (federated wants).
4. **Coordinate fallback chain:** P625 → burial-place/venue P625 (for P1442-
   style indirect wants) → P131 admin-entity coords (capped confidence) —
   WikiShootMe precedent.
5. **Time windows:** campaign JSON `start`/`end` from the Commons `Campaign:`
   namespace is the machine-readable source for seasonal multipliers; lists
   themselves are perennial.
6. **Non-geo shard axes are coming:** language (pronunciation), barcode
   (products), taxon (species). Keep the bundle index from hard-coding
   geohash-only. (Schema impact, not v1 work.)
7. **Single-maintainer risk is the pattern, not the exception** (bwAPI died
   2019; Monumental unmaintained since ~2022; Open Plaques dumps stale;
   FIST/WikiShootMe are one person). The registry should *compile from
   primary stores* (replicas, SPARQL, dumps) and treat Toolforge tools as
   reference implementations, not dependencies.
8. **View-type vocabulary** (interior/night/aerial/entrance/front-of-package)
   recurs across Wikidata, Open Food Facts, and OpenBenches media types —
   worth a controlled `view` field in the schema rather than burying it in
   labels.

## Verification checklist

Things asserted from secondary evidence; each is one request once outside the
restricted network:

- [ ] `curl https://bldrwnsch.toolforge.org/Bilderwuensche.geojson | jq '.features | length'` — Bilderwunsch volume
- [ ] WDQS: current counts — items with P625; geocoded ∧ ¬P18; per-property usage for P1442/P5775/P3451/P5252/P8592/P9721/P9906/P1801
- [ ] PetScan: full size of en.wiki `Category:Wikipedia requested photographs` tree (ns=1, depth ≥5)
- [ ] Open Plaques: does `?filter=unphotographed` (or equivalent) work on the JSON API; current total/unphotographed counts
- [ ] `https://world.openfoodfacts.org/state/photos-to-be-uploaded.json` → `count`
- [ ] heritage.toolforge.org dump listing + per-country unillustrated stats; WLM Wikidata-migration status table
- [ ] Historic England: NHLE "entries without a photo" enumerability; exact Missing Pieces contribution-terms wording
- [ ] Macaulay "Most Wanted" Google Sheet URLs (from the media-target-species page)
- [ ] analytics.wikimedia.org published datasets — any image_suggestions snapshot?
- [ ] Lingua Libre WDQS federation status (T284137 outcome)
- [ ] taginfo counts for `image` / `wikimedia_commons` keys
- [ ] Mapillary API v4: are capture-project tasks exposed?
- [ ] P1442 constraint block re-pull (readout came from a 2020 archived dump)
- [ ] Ajapaik (rephotography, Wikimedia ties) — dedicated look
