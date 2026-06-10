# Raw fixture provenance

Real results from query.wikidata.org (June 10, 2026) for geocoded items
missing an image (P18) in the Seattle test box, SW corner
(−122.46, 47.48) to NE corner (−122.22, 47.74).

The full box contains **910** distinct items; these files hold a sample of
393 (result-set offsets 0–198 and 500–694, ordered by QID) — the pages
that survived response-size limits in the tooling used to fetch them. The
sample spans the whole box geographically and is sufficient for the spike;
rerun `compiler/fetch_wikidata.py` with the bbox above to refetch the
complete set (it also adds the `endDate` column from P576, which this
fixture lacks).

Row shape is documented in `compiler/compile_wants.py`.
