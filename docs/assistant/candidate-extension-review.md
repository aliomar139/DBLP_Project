# Extended candidate: author decoding and classification rebuild

The repaired v2 database was approved as the application's DBLP source on
2026-09-28 and promoted to the canonical file `database/dblp.duckdb`. The old
database copies were removed after the canonical file matched the reviewed v2
fingerprint and passed application and index verification. The approval and
fingerprint are recorded in `database/active-source-v2.json`.

## What changed

The builder inspected author extraction across all 8,738,331 XML publication
records. It corrected 246,481 names in `authors` and the corresponding raw author
strings on 1,185,299 publications. It found no ambiguous original-to-decoded name
mappings and no collisions between different author IDs after decoding. Every
author ID and authorship relationship remains in place. These results do not
resolve homonyms already merged by the original name-based importer.

For example, author 77 remains author 77, with the name `Rogério Schmidt Feris`
instead of `Rog&eacute;rio Schmidt Feris`. The API search resolves the decoded name
to that same ID. The decoder distinguishes actual XML entity nodes from literal
text such as `&amp;ouml;`, avoiding a second, incorrect round of decoding.

The previous title repair is retained unchanged: 8,738,331 nonempty titles, zero
empty-title exclusions, and the same publication IDs and DBLP keys. No author
records were merged, split, added, or removed.

Rebuilt tables are `publication_topics`, `topics` aggregate fields,
`topic_year_stats`, `author_topics`, `venue_topics`, and `author_stats`.
`author_collaboration_dashboard_named` now uses the corrected names over the same
stored ID pairs and weights. The name, primary classification, and explanation
fields in `author_momentum` were refreshed; its inherited scores and ranks were
not recomputed and remain excluded from assistant evidence.

Topic assignments are **title-based project classification**. They are not DBLP
subject labels or evidence of a paper's contents. The rebuild retains the dashboard's
year >=1970 filter and cap of two topics per publication. It now deduplicates
publication/topic pairs, takes the maximum matching keyword weight per topic, and
breaks equal-weight ties by topic ID. The stored `confidence_score` column remains
a project keyword weight, not a calibrated probability.

There are 1,323,430 distinct publication/topic pairs. Compared with the previous
candidate's distinct pairs, 10,758 were added and 265 removed. The changes reflect
repaired title text, duplicate removal, and the deterministic two-topic selection
rule; they are not evidence of research growth. The previous table also contained
29,414 duplicate pairs.

All rebuilt counts use distinct publication IDs. This corrects the stored counts
for 241 authors whose repeated authorship rows previously inflated their totals.
The original 303 duplicate authorship pairs (304 extra rows) are retained in the
core relationship table so this migration does not silently rewrite relationships.

Year summaries retain the dashboard's 1970–2026 range; topic growth retains its
original historical-before-2016 versus 2016–2025 comparison. Author-topic and
venue-topic tables retain their minimum counts of two and five publications,
respectively. The manifest records these rules. Missing dates/growth denominators
remain null rather than receiving seeded defaults.

There are 164,325 momentum rows without a supported primary project classification.
Their primary topic is now null instead of the old `Computer Science` fallback.
The backend and frontend momentum types accept null, and the explanation identifies
the missing information. Existing non-null active-database responses are unchanged.

## Excluded legacy snapshots

The builder does not generate new citation counts, institution assignments,
forecasts, citation edges, external identifiers, or hash embeddings. Fifteen legacy
tables remain copied snapshots, explicitly listed in the manifest's
`retained_excluded_snapshots`. These include mixed-trust `field_statistics` and
`institution_topics`; neither becomes factual evidence through this migration.

Independent checks compare every row and field of those snapshots with v1 to
ensure no synthetic values were regenerated. They remain reachable by existing
legacy dashboard services if someone manually configures the candidate, so this
file is not an approved dashboard deployment. The assistant's default-deny
evidence contract and temporary unavailable response remain in effect.

## Measurements and checks

The build took 266.74 seconds: 136.68 seconds for author staging/repair and 74.69
seconds for classification/count rebuilding; the total also includes copying,
fingerprints, transaction commit, and checkpointing. The resulting file is
3,395,301,376 bytes, about 3.16 GiB.

The builder's process lifetime peak working set was 8,824,057,856 bytes, about
8.22 GiB. The sampled candidate-directory peak was 6,638,830,535 bytes, about
6.18 GiB, including the retained v1 file. Disk sampling ran once per second and
can miss shorter-lived temporary peaks. These measurements concern this migration,
not full indexing or a running language-model service.

The fixture/API/repair suites passed 41 tests. Another 26 existing backend tests
passed with `DBLP_DB_PATH` set to the v2 candidate. The frontend TypeScript/Vite
production build passed. Targeted candidate requests for decoded author search,
author detail, topics, topic detail, venue detail, publication detail, and momentum
all returned HTTP 200. Tests cover collision preservation, ambiguous mappings,
literal entity-looking text, mismatched source rejection, classification ties,
duplicate relationships, null dates, and repeatable classification builds.

The independent verifier checks full-table core invariants and aggregates, all
excluded snapshots, and a Python reference calculation for 10,000 sampled plus
1,000 repaired titles. It also reparses the complete XML with entity resolution
enabled and compares every raw author string and title with the candidate. The
completed JSON report is the authority for its pass/fail result and duration.

## Artifacts and commands

The candidate manifest contains source hashes, rules, counts, examples, timings,
and the review-only state. Reports are:

- `reports/assistant/candidate-extension-verification-v2.json`
- `reports/assistant/candidate-extension-resources-v2.json`
- `reports/assistant/candidate-extension-impact-v2.json`

```powershell
venv/Scripts/python.exe scripts/verify_extended_candidate.py
venv/Scripts/python.exe -m unittest backend.tests.test_candidate_extension
```

`scripts/extend_repair_candidate.py` builds into a new output path and refuses to
overwrite either candidate or the active file. It verifies the input database,
XML, and DTD fingerprints, applies changes transactionally, and checks both input
database hashes again after completion. Failed builds remain marked as failed and
cannot pass the verifier's readiness check. There is no activation command.

This completes the requested database repair and approves repaired v2 as the
app's canonical database at `database/dblp.duckdb`. The full-title index was
independently verified against this exact fingerprint and is now connected to
title-based assistant search. Each retrieved publication ID is reloaded from
canonical DuckDB before citation. The approval does not make retained excluded
snapshots DBLP evidence: existing dashboard pages can still display some of
those legacy values, while assistant evidence continues to deny them. Current
development measurements are recorded in
`reports/assistant/connected-title-retrieval-v1.json`; they do not establish the
10-second 95th-percentile target.
