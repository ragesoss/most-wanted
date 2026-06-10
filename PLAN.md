# Personal Data Donator — Project Plan

## One-line pitch

An app that scans the data already on your device (starting with photos) and surfaces the specific items that open knowledge projects actively want — matched privately on-device, reviewed by you, and uploaded with clean metadata.

The inversion that makes this novel: instead of asking volunteers to go *create* contributions, mine the value sitting in years of camera rolls. Nobody does retrospective scanning today (Commons app "Nearby" only prompts new photos; Open Humans is manual; Common Voice only collects what it asks you to create).

## Scope for v1

- **Receiving project:** Wikimedia Commons / Wikipedia only.
- **Data type:** photos only. (Health data and AI transcripts are explicitly deferred — harder consent, PII scrubbing, and licensing problems.)
- **Demand signals:** compiled from existing Wikimedia sources only (implicit trust; no federation/signing machinery yet).

## Architecture: three components

```
[Wants Compiler] --> static geo-sharded JSON bundles --> [On-device Matcher] --> [Review/Upload Client] --> Commons API
   (server-side,           (CDN/HTTP, dumb)                (private, local)        (staging queue,
    batch jobs)                                                                     consent, receipts)
```

The **demand registry is the real project**. The app is one client of it. Get the wants format and compiler right, and many clients can exist.

### Component 1: Wants registry + compiler

A "want" = a query + fulfillment instructions. Draft schema:

```yaml
want:
  id, publisher, signed_by        # trust chain (v1: implicit, Wikimedia-derived only)
  type: photo
  subject:
    wikidata_qid: Q123            # or a class constraint ("instance of lighthouse")
    labels: [church, building]    # controlled vocabulary FOR THE CLASSIFIER, mapped centrally
  geo: {lat, lon, radius_m}       # optional
  time_window: {before: 2019}     # retrospective wants, e.g. demolished buildings
  constraints:
    license_required: CC-BY-SA-4.0
    min_resolution, no_screenshots
    sensitivity: [strip_gps_homes, flag_faces]
  fulfillment:
    endpoint: commons_upload
    structured_data: {depicts: Q123}   # closes the loop; enables auto-expiry + dedup
  status_check: <how client verifies want is still open>
```

Key design decisions:

1. **Distribution is dumb**: static, geo-sharded JSON bundles over HTTP (like map tiles). Client downloads a broad region and matches locally — the registry never learns user location or library contents.
2. **`time_window` is the secret weapon**: only a retrospective registry can ask for "photos of X before its demolition."
3. **Fulfillment carries structured data** (`depicts` QID) so wants auto-expire and curators get deduplicatable submissions.
4. **Label vocabulary is mapped once, centrally** (Wikidata class → classifier label), not improvised per client.

Demand signals to compile (v1 is a *compiler over existing signals*, not a new social process — see [docs/demand-signals.md](docs/demand-signals.md) for the full source survey and ranking):

- Wikidata items missing image (P18), geocoded via P625 — the motherlode, SPARQL-queryable.
- Other image properties: grave photo, interior view, nighttime view, audio pronunciation — each a precise want type.
- WikiShootMe (Magnus Manske) — existing aggregation of nearby image-less items; proof of signal.
- Per-wiki "requested photographs in <place>" categories — messy but high-intent.
- Campaign lists (Wiki Loves Monuments heritage registers) — natural publishers with IDs, coords, deadlines, review pipelines.
- Wikimedia image-suggestions pipeline (unillustrated-article candidates).

### Component 2: On-device matcher

Three stacked problems: candidate generation → disambiguation → confidence presentation. **Geo is the backbone; classifiers are the filter.**

Pipeline order:

1. **Spatial join first.** GPS EXIF within want radius + compatible timestamp = strong candidate before any ML runs.
2. **Semantic rejection second.** On-device classifier only needs to reject mismatches ("want says church; photo is a selfie"). It does NOT need identity — it confirms "church-shaped photo 80m from where St. Olaf's is."
3. **Heading data (EXIF compass direction)** to disambiguate dense urban areas with many nearby wants — underused, high value.
4. **Identity, when needed:** image embeddings compared against *existing* Commons photos of the candidate item. Caveat: the most valuable wants (zero existing images) have nothing to compare against — geo + category + human confirmation is the ceiling there, and that's acceptable.

Hard cases:

- **No GPS** (older photos, anything through messaging apps): cluster ungeotagged photos with geotagged neighbors from the same hour (burst behavior); pure visual matching as weak fallback.
- **Dense areas**: rank candidates, use heading, let the human pick.

Design stance: **the human is the final matcher.** The app generates candidates; the photographer who was there confirms in two seconds. Confidence tiers, not binary:

- *Auto-suggest*: geo + heading + category all agree
- *Worth a look*: geo agrees, classifier unsure
- *Long shots*: browsable pile for motivated users

**Precision over recall.** A few great suggestions per scan builds trust; a hundred junk candidates kills the app on first use.

Stack notes: platform photo indexes (Apple/Google landmark recognition) are mostly locked away from third parties. Run our own pipeline: read EXIF + Core ML / TensorFlow Lite, MobileCLIP-class embedding models. ~10k photos = one-time overnight scan on a modern phone, then incremental. Own pipeline = portable and auditable, which fits the privacy story.

### Component 3: Review & upload client

Two jobs in tension: fast enough that people donate; consent real enough that nobody regrets an irrevocable license.

- **Split "is it a match?" from "should it leave the device?"** Fast swipe-through match confirmation → items land in a **staging queue** → one deliberate release review of the whole batch *as it will appear publicly* (license, stripped metadata, final filename). One meaningful consent decision instead of twenty hollow ones.
- **License education once, then ambient.** First donation: plain-words explanation of CC-BY-SA irrevocability ("anyone, forever, including commercially; you cannot take it back; could end up in a textbook or an ad"). Afterward: persistent badge on the staging screen. Never bury irrevocability to boost donations — trust is the brand.
- **Faces get deliberate friction.** On-device face detection routes photos with recognizable people to a separate pile that *cannot* be batch-approved. Per-photo: skip, or blur where appropriate. Identifiable children: hard reject, no override. Most wants (buildings, monuments, nature) don't need people in frame, so strictness is cheap.
- **Location leakage is a dial.** Infer "home"/"work" clusters (fitness-app style: where do night photos cluster?); warn or round coordinates near them. Note that heading + position publishes the *camera's* location, not the subject's — "this photo reveals where you were standing" warning for near-home items.
- **Dry-run preview** before upload: exact image, title, depicts statement, stripped-vs-kept metadata diff. "Here's what leaves, here's what we removed" — inspectable, not asserted.
- **Receipts and impact loop** after upload: contribution list with links; eventually "your photo is now on the Wikipedia article for X." The biggest retention lever — Commons uploads usually vanish into a void.
- **Quality gates are MVP, not polish**: resolution floor, blur detection, dedup against existing Commons images for the QID. When donor convenience and curator trust conflict, **err toward curators** — the app will be judged by its worst uploads.

## Build sequence (proposed)

1. **Compiler spike**: SPARQL query for geocoded P18-missing items in one test region → normalize to the wants schema → emit geo-sharded JSON. Validate bundle sizes and sharding scheme.
2. **Matcher prototype (desktop first)**: CLI that takes a folder of photos, reads EXIF, does the spatial join against a bundle, runs an embedding model for category rejection. Measure precision on a real personal library — this validates the core thesis before any mobile work.
3. **Schema hardening**: label vocabulary mapping (Wikidata class → classifier labels), tiering thresholds, status_check semantics.
4. **Mobile client**: scan + match + staging queue + face/home detection + dry-run preview.
5. **Upload path**: Commons API + structured data (`depicts`), dedup check, receipts.
6. **Community engagement** (parallel to 4–5): talk to Commons curators *before* the first upload ships. See open questions.

Step 2 is the cheapest falsification test: if matching precision on real camera rolls is bad, the whole concept needs rethinking before any app exists.

## Open questions / risks

- **Community reception**: Commons has a fraught history with mass-upload tools; curators resent junk floods. Research how past tools (e.g. bulk upload campaigns, Flickr imports) were received and what made the difference. Engage early; consider an opt-in review queue for the app's first uploads.
- **Commons API behavior**: confirm upload + structured-data pipeline works as assumed (rate limits, OAuth for third-party apps, structured data on upload vs. post-edit).
- **Matching precision in practice**: dense-urban disambiguation, EXIF heading availability rates across devices, GPS-stripped photo prevalence in real libraries.
- **Legal variance on bystanders/personality rights** by country — affects how strict the face gate must be.
- **Future federation**: signing/trust model for non-Wikimedia want publishers (air quality, oral history) — explicitly out of scope for v1 but the schema should not paint us into a corner (`signed_by` placeholder).
- **Naming/positioning**: "donator" framing vs. "your photos are wanted" framing — the latter tested better in similar projects (worth validating).

## Deferred (v2+)

- Health data donation (consent + PII problems are much harder)
- AI transcript donation for open datasets (PII scrubbing pipeline required)
- Non-Wikimedia want publishers + federation/signing
- Audio wants (pronunciations) — actually a plausible early add: small files, low privacy risk
