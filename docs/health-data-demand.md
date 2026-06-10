# Health-data demand — research survey

*Researched June 2026 via parallel web research. The build environment 403'd most
primary sites (openhumans.org and Wayback included), so several figures rest on
search-engine extracts; those are flagged ⚠ unverified with a way to confirm.
See the [verification checklist](#verification-checklist).*

PLAN.md defers health data to v2+ ("harder consent, PII scrubbing, and licensing
problems"). This survey answers the **demand-side** question that can be settled
now: *is there stuff on a typical phone that Open Humans — or anyone — actually
wants, and is that demand addressable?* It's a companion to
[demand-signals.md](demand-signals.md) (the photos→Wikimedia survey).

## Bottom line

The honest answer is **"yes, but narrowly, and the registry framing barely
applies."**

- **What's on the phone is exportable** (Apple Health ZIP, Android Health
  Connect cloud backup, Fitbit→Takeout, Oura CSV) — the plumbing exists and is
  improving.
- **But only ~3 data families have an addressable want today** — a standing
  project that will ingest a public donation with a consent flow: **activity/
  sleep/heart-rate** (All of Us BYOD, Open Humans), **CGM/glucose** (OpenAPS
  Data Commons), and **consumer-genome files** (Open Humans 23andMe/Ancestry
  upload). Everything else is valuable-but-closed or aspirational.
- **Open Humans is the closest thing to a demand registry that exists** — and
  it's small enough (a few dozen projects, a handful active) that you'd
  hand-curate it, not crawl it. It's a *schema model and a seed*, not a
  firehose.
- **The whole field is siloed**: there is **no machine-readable cross-platform
  enumeration of open data-donation studies anywhere.** That's the same gap the
  photos registry attacks — so a health-data wants registry would be genuinely
  novel infrastructure, but the supply of wants to fill it is thin.
- **The licensing model is fundamentally different from photos.** Photos→Commons
  is irreversible CC publication (a one-way door). Every durable health-donation
  platform instead uses **scoped, revocable, authorization-based** fulfillment —
  a donation is "an authorized transfer into a specific use context," not a
  public release. openSNP's 2025 shutdown is the cautionary tale for the
  CC-commons model applied to health data.

## How health wants differ structurally from photo wants

This is the load-bearing finding for the schema. The photo registry assumes:
public CC publication, self-expiry when fulfilled (item gets its P18), geo
sharding, and implicit trust (Wikimedia-derived). Health wants invert almost
all of it:

| Dimension | Photo want (v1) | Health-data want |
|-----------|-----------------|------------------|
| Fulfillment | Public CC upload to Commons | Authorized transfer into a use context (private by default) |
| Reversibility | Irreversible (one-way door) | Revocable — member can withdraw, cutting access |
| Expiry | Self-expiring (P18 lands → want closes) | **Open-ended** — every new donor is a fresh fulfillment; the want never closes |
| Sharding key | Geohash | Data type + platform (Fitbit, HealthKit…); not geographic |
| Trust model | Implicit (Wikimedia) | Per-project consent + (uneven) IRB; requester identity matters |
| Sensitivity | Location leakage is the main risk | The data *is* the risk; re-identifiable even when "anonymized" |
| Matching | EXIF geo + on-device classifier | Local extract + filter of an export, then per-donation consent |

The schema's `signed_by`/`publisher` placeholder and `status_check` field were
designed for exactly this kind of extension, but a health want needs four
things a photo want doesn't: **(i)** requesting party + use scope, **(ii)** the
consent/authorization mechanism, **(iii)** revocability terms, **(iv)** a
fulfillment-semantics flag (public-commons vs. authorized-ingest — the latter
being the norm). PLAN.md's instinct to defer this is right: it's not a label
change, it's a second trust-and-consent model.

## Open Humans — the demand source, assessed

**Status:** online, code maintained but in maintenance-only mode (recent commits
are spam/security cleanup by a single committer). Director of Research Bastian
Greshake Tzovaras resigned mid-2024; Mad Price Ball remains Executive Director.
Small 501(c)(3) (~$233K assets), no confirmed current major grant. ⚠ Live
blog/totals unverified (site 403'd). **Sustainability risk is real — snapshot
its metadata, don't build a live dependency.**

**It is machine-readable.** The public API
(`https://www.openhumans.org/api/public/projects/`, paginated JSON) exposes per
project, via `ProjectDataSerializer`:
`name, leader, organization, is_study, is_academic_or_nonprofit,
requested_sources, registered_datatypes, authorized_members, active, approved,
info_url`. That's a demand record out of the box: **`requested_sources` +
`registered_datatypes` = what each project wants; `authorized_members` =
fulfillment count.** A Python client (`OpenHumans/open-humans-api`) exists. ⚠
Could not fetch live JSON here — confirm the endpoint and current active count.

**The demand model** (from the 2019 GigaScience paper, Members/Projects/Data):
a Project requests authorization to read existing data and/or write new data;
members join selectively and can withdraw instantly. A clean "want → authorize
→ fulfill" loop — but **fulfillment is open-ended**: donating increments
`authorized_members`, it never closes the want.

**Connector inventory** (phone-relevant subset; full table in raw notes). The
phone-*origin* connectors are the most fragile: Apple Health (a DIY HealthKit
export tool, last touched 2023), Google Fit (Google deprecating the APIs
industry-wide), Google location/Takeout (Timeline moved on-device in 2024),
Overland GPS (actively updated). The robust, high-value demand is cloud/device
health: Fitbit/Oura/Withings (maintained 2024) and genome uploads
(23andMe/Ancestry, 2024). Dead connectors: Moves (2018), uBiome (2019),
Twitter (post-API-lockdown). **Open Humans has essentially zero photo demand** —
it's orthogonal to v1, relevant only to the deferred health expansion.

**Flagship projects (real demand vs. long tail):** the distribution is heavily
long-tailed — a handful of projects carry all the activity:
- **OpenAPS Data Commons** (type-1 diabetes, closed-loop/CGM; admin Dana Lewis)
  — the one project that proves the model produces science. Donor cohort grew
  n=80 (2019, ~19.5k CGM-days) → n=122 (2022, ~46k days, >10M CGM points),
  "largest freely available diabetes dataset," multiple peer-reviewed papers.
  Still accepting donations.
- **Nightscout Data Transfer (Automated)** — companion CGM pipeline. Live.
- **Quantified Flu** — wearable + symptom tracking; JMIR paper 2021; repo still
  maintained, but its research moment was COVID-era.
- Genome uploads (23andMe Upload had 1,054 members; Harvard PGP 816; Genevieve
  749 — Genevieve now effectively dead).
- Keating Memorial Self Research — an annual self-research ritual, not a single
  data want.

2019 paper: ~30 active + 12 finished projects. About page now claims ~11,983
members / ~40 activities ⚠. **Realistic count of projects actively soliciting
right now: a few dozen, maybe a handful genuinely active** — small enough to
hand-curate.

## What's on the phone (and whether anyone will take it)

Exportable phone-resident health data and its demand status:

| Data type | Export path | Addressable want today? |
|-----------|-------------|--------------------------|
| Steps / HR / sleep | Apple Health ZIP; Health Connect cloud backup; Fitbit→Takeout; Oura CSV | **YES** — All of Us BYOD; Open Humans |
| CGM / glucose | Dexcom/Libre export; Nightscout | **YES (niche)** — OpenAPS Data Commons |
| Genome (23andMe/Ancestry) | File upload | **YES** — Open Humans |
| Menstrual / cycle | HealthKit; Clue | **NO open ingest** — demand real (Apple Women's Health Study, Clue) but closed/internal |
| Voice biomarker | Phone audio / voice memos | **NO standing endpoint** — studies (mPower, SMARTSPEECH) enroll, don't ingest files |
| Location / mobility | Google Timeline (**on-device only since 2024**) | **NO**, and it got *harder* — plus catastrophic sensitivity |
| Hearing / audiogram | Apple hearing test; Mimi | **NO** — Apple Hearing Study is enroll-only |
| Food / weight / BP | MyFitnessPal ZIP; device exports | **NO dedicated commons** — diffuse demand |
| Typing dynamics | — | **NO** — research-stage only |

**Export mechanics worth knowing:** Apple Health's `export.zip` (`export.xml` +
ECG folder) has no published schema, changes silently between iOS versions, and
routinely needs an XML→CSV normalization step — plan for a parsing layer, the
raw ZIP isn't directly ingestible. Android Health Connect added scheduled
backup/restore in Nov 2024 but it's *cloud-backup oriented* (no clean local
"download my file" flow). GDPR Art. 20 / CCPA portability is the fallback
extraction lever for apps without native export.

**Closed cohorts = evidence of value, not addressable wants.** Apple's
Research-app studies (Heart & Movement ~500k target, Hearing 150k, Women's
Health 1M, a new holistic Health Study launched Feb 2025) produce real findings
but are Apple-only and **enroll-not-donate** — you cannot feed them an outside
export. Same for Clue's menstrual research (routed through its own internal
consent). For reproductive data specifically, there is **no open analog** that
ingests an exported cycle file.

## The broader ecosystem (beyond Open Humans)

**openSNP shut down April 2025** — confirmed. ~13,000 users' genetic + phenotype
data deleted; founder cited 23andMe's collapse, authoritarian-misuse risk, and
law-enforcement genetic-genealogy. The reflection that matters for us: *"the
risk/benefit calculus of providing free & open access to individual genetic
data in 2025 is very different compared to 14 years ago."* Irreversible open
publication of identifiable health data is a one-way door whose downside risk
grew over the platform's lifetime. **This is the strongest argument against a
CC-commons model for health data** — and a reason the photos UI should make the
one-way-door nature of *any* irreversible contribution explicit.

**Cooperatives:** only **MIDATA.coop** (Switzerland, data-trustee model,
member-elected ethics board, runs real studies) is robustly alive; Salus Coop
(Spain) is marginal; healthbank, LunaDNA (closed Jan 2024), and DNA.land (closed
2019) are dead. None expose a machine-readable feed of open requests.

**Academic data-donation infrastructure — the most relevant prior art.** The
field (Zurich's Data Donation Lab, Utrecht-led D3I / datadonation.eu) runs
**study-scoped wants**: a researcher opens a study soliciting a specific
platform export (WhatsApp, Instagram, Google Takeout), participants donate, the
study closes. The key tool is **PORT (Eyra) → now the "Next" platform**: it has
the participant request their GDPR export, then **runs Python in the browser
(Pyodide/WASM) to extract and filter locally — only researcher-relevant features
leave the device; the raw export never uploads.** The participant inspects the
extracted features and consents per donation.

> **This local-extract-filter-then-consent flow is direct prior art for our
> on-device matching design.** It's the same privacy property the photo matcher
> has (match locally, surface only candidates, upload only what the user
> approves) — applied to structured data exports. Worth studying
> `d3i-infra/data-donation-task` before any health work. Note `eyra/port` and
> `port-poc` are deprecated; "Next" is current.

But: **no central listing of open donation studies exists** — each is a
separately deployed instance recruited ad hoc. The field's own literature
concedes standards "have not yet been established."

**Open cohorts:** All of Us (NIH) ingests Fitbit/HealthKit via BYOD + a
device-shipping sub-study — the strongest steps/HR/sleep want — **but data goes
into a controlled-access Researcher Workbench, not a commons** (fulfillment =
authorized ingest into a gated pool). Scripps DETECT proved device-agnostic
willingness (~30k, Fitbit/Apple/Garmin) ⚠ current enrollment unverified.
Evidation (commercial, >5M users, pays cash) is the incentivized counterexample
to altruistic donation. Sage Bionetworks' mPower (Parkinson's phone-sensor
study) proved phone-sensor donation + credentialed data release works, and
surfaced the binding constraint: **steep early retention drop-off**.

**What the big experiments proved:** Germany's **Corona-Datenspende reached
540k+ donors, 120k+ sustained ~2.5 years** — population-scale altruistic
device-data donation is achievable when motivation is high and friction is low
(passive sync). DETECT replicated cross-device willingness. mPower showed
retention, not sign-up, is the hard part. Net: **acquiring donations is
solvable; sustaining them and aggregating demand across silos is not.**

## Sensitivity and re-identification

Steps and sleep are *not* anonymous. The re-identification literature is stark:
a 2025 AsiaCCS paper ("Slice it up") hit 100% re-ID on one smartwatch dataset
and >93% on synthetic data from short segments with no training data; gait/IMU
and walking patterns re-identify from very little data. There's no canonical
"donation sensitivity tier" standard — healthcare uses 3–4 tier schemes and
ethics literature treats reproductive/mental-health/location data as the
high-harm tier. **A "low sensitivity" label on steps/gait/location is
misleading without a de-identification strategy** (noise injection helps with
modest utility loss). Catastrophic tier: location/mobility, reproductive (acute
legal risk post-*Dobbs*), mental health.

## Recommendation

**Keep health data deferred, but for a sharper reason than PLAN.md states.** It's
not just that consent/PII are hard (they are) — it's that:

1. **Addressable demand is thin.** Three data families, two-to-three standing
   platforms. That doesn't need a registry; it needs a hand-curated list of a
   handful of endpoints (OpenAPS, Open Humans, All of Us).
2. **The fulfillment model is incompatible with v1's.** Authorized-ingest +
   revocable + open-ended + non-geo is a different trust-and-consent system, not
   a new want `type`. Building it means a second consent UX and a
   requester-identity/signing model the photos path explicitly defers.
3. **The one-way-door risk is worse.** openSNP is the proof that irreversible
   open health data ages badly. If health is ever added, it should default to
   authorized-ingest semantics, never CC publication.

**What's worth borrowing now, while still deferring the data type:**

- **PORT/Next's local-extract-then-consent architecture** validates and
  sharpens the on-device-matching privacy story — cite it as prior art.
- **Open Humans' project serializer** is a good concrete model for an
  authorized-ingest want record (`requested_sources` / `registered_datatypes` /
  `authorized_members`); worth mirroring those fields if the schema ever grows a
  federated, non-Commons publisher.
- **The intent/fulfillment-semantics axis** the photo survey already recommends
  (`human_request` / `campaign` / `curated_list` / `derived_gap`) should grow a
  parallel **fulfillment-semantics** flag (`public_commons` / `authorized_ingest`)
  — designing that field now keeps the schema from painting itself into a corner,
  which is exactly what PLAN.md's `signed_by` placeholder was meant to avoid.

If health is ever picked up, the first actionable beachhead is **CGM data via
OpenAPS/Nightscout** (a real, science-producing, still-open commons with a niche
but committed donor base) — not the broad "scan your Health app" play, which has
no waiting recipient for most of what it would find.

## Verification checklist

- [ ] `GET https://www.openhumans.org/api/public/projects/` — live project list, current active count, exact serializer fields
- [ ] Open Humans current member/activity totals (~11,983 / ~40 are search-surfaced) and latest blog post date
- [ ] Open Humans 2024 IRS 990 / current funding status
- [ ] Per-connector live auth status (Apple Health, Google Fit, Overland) — inferred from repo recency, not tested
- [ ] openSNP AI-training motive — verify verbatim at https://tzovar.as/sunsetting-opensnp/ (403'd here)
- [ ] Scripps DETECT current (2025–26) enrollment status
- [ ] Google Health Studies status (at-risk given health-division dissolution + Fit sunset)
- [ ] Apple Research-app studies live open/closed status as of mid-2026 (enrollment numbers are targets)
- [ ] healthbank liveness (PitchBook says "Out of Business"; conflicting self-description)
- [ ] Whoop export availability (sources conflict: "no export" vs. "CSV export exists")
- [ ] Apple HealthKit retention depth (no published Apple spec; the "5–10yr / 200–500MB" figures are secondary-sourced)
- [ ] MIDATA / Salus active-request lists — confirmed no machine-readable feed, but worth a direct check
