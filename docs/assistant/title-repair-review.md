# Title repair candidate for review

This page records the v1 title-only candidate. The approved author-decoding and
classification rebuild now has its own v2 file and report in
`candidate-extension-review.md`. Neither candidate has been activated.

The active database is unchanged. The separate candidate at
The historical intermediate file `database/candidates/dblp-titles-v1.duckdb` repaired title extraction from the retained
local DBLP XML and DTD. It has not replaced the active database, and no application
configuration points to it.

| Check | Active database | Candidate |
| --- | ---: | ---: |
| Publication records | 8,738,331 | 8,738,331 |
| Nonempty titles eligible for indexing | 8,730,137 | 8,738,331 |
| Empty-title exclusions | 8,194 | 0 |
| Titles changed from the active file | 0 | 205,674 |

The repair resolves local XML character entities and concatenates nested title
text, then applies the original whitespace normalization. Publication 2,
`ms/Ley2006`, now contains its full XML title rather than stopping at
`Retentionsma`. Publication 460 includes the italicized `BehaviorScan` text and
the trailing period. The candidate's `_candidate_title_changes` table records
every changed publication ID, verified DBLP key, old title, and new title.
This audit table is not an assistant evidence source.

All 8,738,331 source records passed publication-ID, DBLP-key, type, and year checks
before the update. An independent read-only comparison found zero unexpected
changes to publication metadata, raw metadata, author IDs/names, authorship links,
or venues, and zero unexpected title changes. The builder checked the active
database SHA-256 before and after preparation; it did not change.

Preparation took 413.87 seconds. The candidate file occupies 3,243,520,000 bytes
(about 3.02 GiB). Windows process counters reported a peak working set of
8,959,987,712 bytes (about 8.35 GiB) for the builder. This is a process memory
measurement, not the total laptop memory footprint. Independent verification took
13.39 seconds. These measurements do not predict embedding speed.

## Author extraction needs a separate review

Correct XML entity handling changes the source author-name strings on 1,185,299
publication records. This is a count of publication records with a differing author
string, not a count of distinct affected people. For example, the retained raw
string `Hans-J&ouml;rg Kreowski` differs from the XML-resolved `Hans-Jörg Kreowski`.

The title candidate deliberately preserves author names, IDs, and links. The next
review should map original name tokens to resolved XML names, count collisions and
one-to-many mappings, and preserve IDs wherever the mapping is unambiguous. Never
merge records simply because corrected names match. Existing name-based homonym
merging cannot be undone safely from a title-only repair.

## Activation is not approved

Legacy title classifications, topic aggregates, narratives, and hash embeddings
remain copied from the active file. They are stale relative to repaired titles.
They are excluded from assistant evidence, but the dashboard still uses some of
them. The candidate is therefore a review artifact, not a ready database swap.

Before activation, review the author-name migration and the title-dependent
dashboard rebuild plan, rerun regressions, and bind every new index/cache to the
selected database version. The old parser still needs a reviewed extraction fix
so a future import does not reintroduce the problem. No activation command is
included in these scripts.

The candidate changes the eligibility baseline. If this corpus is approved, the
full-title build must index all 8,738,331 eligible candidate IDs. If the active file
remains selected, its target stays 8,730,137 with 8,194 exclusions. A candidate index
must never be silently attached to the active database.

## Artifacts and repeatable checks

`database/candidates/dblp-titles-v1.manifest.json` records source/candidate hashes,
counts, title examples, author differences, and the review-only state.
`reports/assistant/title-repair-verification-v1.json` contains the independent
comparison results. `reports/assistant/title-repair-resources-v1.json` records the
process-memory measurement.

```powershell
venv/Scripts/python.exe scripts/verify_title_repair_candidate.py
venv/Scripts/python.exe -m unittest backend.tests.test_title_repair
```

To prepare another candidate, use `scripts/prepare_title_repair_candidate.py` with
a new `--output` path. It refuses to overwrite an existing candidate or the active
file. It also refuses a source with a pending write-ahead log. External XML
dependencies and network resources are rejected.
