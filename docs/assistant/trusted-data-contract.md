# DBLP assistant: historical trusted data review v1

> **Superseded for current assistant routing (2026-10-03).** This document records
> an earlier evidence policy and implementation snapshot. The current primary
> assistant is the schema-aware local Agentic RAG path in
> `backend/app/services/agentic_rag.py`; it may query `institutions`,
> `author_institutions`, `publication_citations`, `topics`, and
> `publication_topics` as well as core publication tables. Do not use the old
> exclusions below to refuse those user questions. Generated SQL remains
> read-only and is bounded by the current execution guard. The older fixed
> intent/interpreter routes are offline fallback behavior only.

The audit observations and source-fidelity caveats in this file remain historical
records of the inspected database at that time. They are not a reason for the
current primary path to suppress a query; answer from returned rows and describe
the evidence represented by those rows accurately.

This contract applies to the replacement assistant. The existing dashboard still
uses legacy analytical services; its metrics are not automatically assistant evidence.
The active file is `database/dblp.duckdb`, unless `DBLP_DB_PATH` selects another file.
Request handlers open it read-only. No database contents changed in milestone 1.

## What the application currently does

The Python FastAPI application registers entity, analytics, search, and assistant
routes. Its DuckDB helper opens read-only connections, interrupts queries after 45
seconds, and caches up to 128 results for ten minutes. Cache keys contain SQL and
parameters but no database version. That helper is not an assistant SQL sandbox:
checking whether text starts with SELECT or WITH does not constrain its evidence.

React, TypeScript, and Vite provide the dashboard. `App.tsx` handles local navigation
with the browser history API, lazy-loaded entity pages, and normal anchor links.
There is no mounted assistant page. Keep the existing `/papers/:id`, `/authors/:id`,
`/venues/:id`, and `/topics/:id` links. The legacy institution routes also stay intact.

Unified search uses title/name text matching. It orders papers by generated
citations. The separate semantic endpoint combines keyword matches, hash vectors,
and generated citations, and can return assigned institutions. It is not trusted
assistant retrieval. Its claimed BM25 stage actually uses ILIKE.

The initializer writes 64-component hash vectors under the misleading
`scibert-semantic-v1` label. The runtime query vector uses a different hash/domain
algorithm. The stored pool contains only 4,965 publications in the inspected file;
runtime search reads at most 600. Neither algorithm runs SciBERT or another learned
embedding model. No local embedding or language-model runtime is installed in the
project virtual environment at inspection time.

Previously, the assistant selected scripted narratives by keywords and emitted
fallback names, numbers, charts, forecasts, and briefs. Milestone 1 removes those
responses. The same POST URL now returns a structured temporary `unavailable`
result. This intentionally changes the assistant response shape; no mounted
dashboard component consumes the old shape. The remaining dashboard routes and
search behaviors have not changed.

## Allowed fields and calculations

| Source | Eligible fields | Qualification |
| --- | --- | --- |
| publications | publication_id, db_key, type, title, year, venue_id | Local IDs depend on database version. Titles are imported strings, potentially incomplete. |
| authors | author_id, name | Name groups, not verified person identities. Homonyms may merge. |
| venues | venue_id, name | Exact imported journal/booktitle strings; abbreviations are not automatically the same venue. |
| publication_authors | publication_id, author_id | Deduplicate pairs and verify both endpoints against core tables. |
| topics | topic_id, topic_name, category | Only with the words “title-based project classification”. |
| topic_keywords | topic_id, keyword | Project rules, not DBLP-supplied subjects or paper-content evidence. |

`evidence_contract.py` denies unknown tables and columns. These permissions alone
do not prove a supplied row is true. Later bounded tools must read these projections
themselves, resolve actual IDs, construct evidence packets, and validate claims.
The temporary assistant emits no factual claims while that path is unavailable.

Corpus counts include all stored publication types, including proceedings, books,
theses, and empty-title records. Do not casually call this an article count.
Title-index eligibility is exactly `title IS NOT NULL AND length(trim(title)) > 0`.
Index every eligible publication ID, including duplicate titles; report exclusions.

Author/venue counts use distinct publication IDs. Coauthorship means distinct shared
publication records, never a citation or proof that two ambiguous names identify
particular people. Rankings use publication counts with a deterministic ID tie-break.
Comparisons apply the same inclusive year filters to every entity. Annual trends
exclude and disclose missing years. Null data is unavailable, not zero.

For title classification, recompute literal case-insensitive keyword matches and
deduplicate IDs. Disclose the keyword rules and year filters. Do not reuse stored
classification confidence, topic descriptions, growth, or summary counts as paper
facts. The old builder restricts matches to year >=1970 and retains two keyword
rows per publication, which can repeat a topic. Its ties lack a stable tie-break.

Every future aggregate source must carry the database fingerprint, contract/tool
version, exact calculation, bound filters, inclusive date range, null/empty-title
handling, and observed result. External links may only use a verified DBLP key and
a validated DBLP URL rule; no fabricated DOI, ORCID, or other provider URL is valid.

## Schema-aware natural-language queries

The assistant now has a generic local query-planning path for questions that miss
the existing exact handlers. The local model emits a constrained JSON plan over
`publications`, `authors`, `venues`, and `publication_authors`; it never emits SQL.
The compiler owns the SQL identifiers and relationship joins, validates every
field against the evidence contract, binds every user/model value as a parameter,
and applies the existing read-only connection, row cap, and timeout.

The plan supports projected fields, equality and text filters, year comparisons,
counts and other bounded aggregates, grouping, ordering, and limited result sets.
Paper counts use distinct publication IDs, and author or venue name aggregates
retain their IDs so same-name records remain separate. Topic discovery can select
the existing semantic-plus-keyword full-title index; returned publication IDs are
still resolved against canonical DuckDB before display.

The same local Phi-3 Mini runtime drafts the final answer from the query result.
The response includes the exact plan and returned rows in its calculation evidence;
numeric claim validation still runs before display. Existing deterministic paths
remain first, and the older fixed-intent interpreter remains a fallback when the
generic plan is unavailable or invalid. This implementation has not yet passed a
reviewed broad-question evaluation, so it does not establish arbitrary phrasing
accuracy or answer quality.

This path only covers trusted bibliographic fields. It cannot answer from abstracts,
full text, affiliations, or observed citation links because those fields are not
available as approved DBLP evidence here. A title search can find likely records;
it cannot establish what a paper did or concluded.

## Excluded evidence

`publication_citations` uses publication-ID hashes, age weights, and venue tiers.
`author_impact_stats` derives citation totals and h-index from those numbers.
`author_institutions` assigns institutions with a hash modulo 50. All institution
tables and their aggregates are excluded. These are not observed affiliations.

`paper_citation_lineage` connects selected papers by chronology and topic; it does
not store observed paper references. `topic_forecast_signals` contains seeded and
category-default forecasts. `external_ecosystem_metadata` constructs provider IDs,
URLs, and repeated metric values. Exclude all of them, including their narratives.

Legacy embedding tables, momentum, field statistics, classifications, dashboard
summaries, author/venue/year summaries, and materialized collaboration tables are
not assistant evidence. Some contain reproducible calculations, but recomputing
from core tables avoids mixed-trust fields, stale summaries, duplicate counts, and
sampled collaboration coverage. `raw_publications` serves offline provenance audits,
not runtime assistant answers. Any new table remains denied until reviewed.

## Inspection results and source fidelity

See `reports/assistant/trusted-data-v1.json` for a timestamp, schema, file SHA-256,
SQL checks, sample checks, and durations. Counts are observations, never constants
in retrieval code. Inspection found 8,738,331 publications; 8,730,137 eligible stored
titles; 8,194 empty-title exclusions; 4,301,538 author-name records; and 21,224 venue
names. Three publications lack a year; stored years range from 1936 to 2027.

The initial checks found 303 repeated authorship pairs and 29,414 repeated
publication-topic pairs. Publication IDs and DBLP keys are unique in this file.
Normalized publication metadata agrees with the retained raw rows. That agreement
does not prove complete XML extraction.

`parse_dblp.py` uses `findtext('title')` with unresolved entities. For example,
publication 2, key `ms/Ley2006`, stores only
`Der Einfluss kleiner naturnaher Retentionsma`; its XML continues through character
entities and more text. Nested title markup has the same extraction risk. Author
names also need an entity-resolution audit. Never fill in missing text from a model.

A full structural scan of all 8,738,331 supported XML records found 205,674 titles
with child nodes, including 8,194 with an empty stored prefix. See
`reports/assistant/xml-title-fidelity-v1.json`; repeat with
`venv/Scripts/python.exe scripts/audit_xml_title_fidelity.py`. This measured
extraction risk does not count validated repaired titles. The scan took 99.23 seconds.

A reviewed repair would first build a separate candidate corpus from the retained
local XML and DTD, preserving publication IDs by DBLP key and checking all changed
titles and author mappings. It would compare counts and entity links before any
database swap. Author IDs must not silently change. Full indexing would then bind
to the selected database fingerprint. That repair is not part of this milestone,
and no repair or database swap has run.

## Milestone gates

1. Trusted contract: read-only audit, denied-evidence tests, assistant fail-closed
   tests, and existing dashboard/API regressions. No claim that this supplies RAG.
2. Feasibility: benchmark learned local embeddings on a deterministic sample spanning
   publication IDs, years, types, and title lengths. Measure cold load separately
   from batched throughput. Compare lexical/vector candidates and exact-neighbor
   recall; estimate full disk/RAM/time with explicit uncertainty. Setup downloads
   are permitted; inference and evidence stay local. No full build before the report.
3. Full retrieval: all eligible IDs, duplicate/orphan checks, explicit exclusions,
   atomic sidecar activation, fingerprint validation, and rebuild tests. No sampling
   disguised as full coverage.
4. Bounded tools: developer-owned parameterized SQL, row limits, deadlines, exact
   entity resolution, ambiguity and refusal states. Never accept model-written SQL.
5. Local explanation: measure compact local models; validate structured claims,
   values, relationships, and source links before any answer appears.
6. UI and operations: one-question nonstreaming form, nearby sources, clear states,
   versioned bounded caches, timing/error diagnostics without question text.
7. Release: evaluate the reviewed question set and report measured mean/p95 latency,
   correctness, grounding, refusals, resource use, and remaining limitations.

The parser uses million-row Arrow batches, ten DuckDB threads, and a 25 GB database
memory setting. Its log records a 4.46-minute import. This is not an embedding speed
measurement. Neither the few-day delivery goal nor the 10-second response p95 has
been established. The 25–28 GB memory target and 40–60 GB build allowance still need
measured embedding/index work. No external model API is part of this design.

## Reproduce milestone 1

From `C:\DBLP_Project`:

```powershell
venv/Scripts/python.exe scripts/audit_trusted_data.py
venv/Scripts/python.exe -m unittest backend.tests.test_trusted_boundary backend.tests.test_api
cd dashboard
npm run build
```

The audit writes only its JSON report. Its 10,000-record XML prefix sample confirms
the original extraction rules, not random corpus-wide fidelity. The full-table SQL
checks cover their stated properties across the active database. Future correctness
remains an evaluation obligation; passing these tests does not guarantee no errors.

Milestone-1 validation on this workspace: all 61 distinct tests in
`test_trusted_boundary`, `test_api`, `test_final_intelligence`, and
`test_strategic_intelligence` passed. The dashboard TypeScript/Vite production
build passed. The fixture suite required an unsandboxed run because Windows denied
access to the sandbox-created temporary DuckDB directory. No active-database write
occurred. The read-only provenance audit took 9.99 seconds. This is not assistant
response latency. Legacy tests passing does not make their synthetic data trusted.
