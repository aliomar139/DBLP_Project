"""Read-only milestone-1 provenance audit; writes a versioned JSON report only.

Run from the repository root: venv/Scripts/python.exe scripts/audit_trusted_data.py
The XML sample follows the ORIGINAL parser's extraction settings. It also checks
whether title child nodes were lost. No network, database repair, or model call.
"""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from time import perf_counter

import duckdb
from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.services.evidence_contract import (  # noqa: E402
    CLASSIFICATION_FIELDS, CONTRACT_VERSION, CORE_FIELDS, EXCLUDED_TABLES,
)


def file_hash(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def audit(db_path: Path, xml_path: Path | None, sample_size: int = 10000):
    started = perf_counter()
    before = db_path.stat()
    report = {"contract_version": CONTRACT_VERSION, "audit_version": 1,
              "observed_at_utc": datetime.now(timezone.utc).isoformat(),
              "database_path": str(db_path.resolve()), "database_bytes": before.st_size,
              "database_sha256": file_hash(db_path), "checks": {}, "timings_seconds": {}}
    with closing(duckdb.connect(str(db_path), read_only=True,
                               config={"memory_limit": "4GB", "threads": "4"})) as db:
        def check(name, sql, params=()):
            t = perf_counter()
            result = db.execute(sql, params)
            columns = [x[0] for x in result.description]
            rows = [dict(zip(columns, row)) for row in result.fetchall()]
            report["checks"][name] = rows
            report["timings_seconds"][name] = round(perf_counter() - t, 6)
            return rows

        schema = check("schema", """SELECT table_name, column_name, data_type
            FROM information_schema.columns ORDER BY table_name, ordinal_position""")
        report["table_policy"] = {
            t: ("core_fields_only" if t in CORE_FIELDS else "labeled_classification_fields_only"
                if t in CLASSIFICATION_FIELDS else "excluded" if t in EXCLUDED_TABLES else "unreviewed_denied")
            for t in sorted({r["table_name"] for r in schema})}
        check("corpus", """SELECT count(*) AS publications,
            count(*) FILTER(WHERE title IS NULL OR length(trim(title))=0) AS empty_title_exclusions,
            count(*) FILTER(WHERE length(trim(title))>0) AS eligible_titles,
            count(*) FILTER(WHERE year IS NULL) AS missing_years, min(year) AS min_year, max(year) AS max_year
            FROM publications""")
        check("core_sizes", """SELECT (SELECT count(*) FROM authors) AS author_name_records,
            (SELECT count(*) FROM venues) AS venue_name_records,
            (SELECT count(*) FROM publication_authors) AS authorship_rows""")
        check("duplicate_publication_identifiers", """SELECT
            count(*)-count(DISTINCT publication_id) AS repeated_ids,
            count(*)-count(DISTINCT db_key) AS repeated_or_null_keys FROM publications""")
        check("raw_normalized_mismatches", """SELECT count(*) AS mismatches FROM publications p
            FULL JOIN raw_publications r ON p.publication_id=r.id LEFT JOIN venues v ON p.venue_id=v.venue_id
            WHERE p.publication_id IS NULL OR r.id IS NULL OR p.title IS DISTINCT FROM r.title
            OR p.db_key IS DISTINCT FROM r.db_key OR p.year IS DISTINCT FROM r.year
            OR p.type IS DISTINCT FROM r.type OR coalesce(v.name,'') IS DISTINCT FROM r.venue""")
        check("orphan_authorship", """SELECT count(*) AS orphan_rows FROM publication_authors pa
            LEFT JOIN publications p USING(publication_id) LEFT JOIN authors a USING(author_id)
            WHERE p.publication_id IS NULL OR a.author_id IS NULL""")
        check("duplicate_authorship", """SELECT count(*) AS repeated_pairs, coalesce(sum(n-1),0) AS extra_rows
            FROM (SELECT count(*) n FROM publication_authors GROUP BY publication_id,author_id HAVING count(*)>1)""")
        check("duplicate_classification", """SELECT count(*) AS repeated_pairs, coalesce(sum(n-1),0) AS extra_rows
            FROM (SELECT count(*) n FROM publication_topics GROUP BY publication_id,topic_id HAVING count(*)>1)""")
        check("legacy_embedding_pool", """SELECT model_name, dimensions, count(*) AS vectors,
            min(array_length(embedding_vector)) AS min_dimensions, max(array_length(embedding_vector)) AS max_dimensions
            FROM paper_embeddings GROUP BY ALL""")
        check("year_stats_mismatches", """WITH actual AS (SELECT year,count(*) AS n FROM publications
            WHERE year IS NOT NULL GROUP BY year) SELECT count(*) AS mismatches FROM actual a
            FULL JOIN publication_year_stats s USING(year) WHERE a.n IS DISTINCT FROM s.publication_count""")
        check("author_count_samples", """WITH chosen AS (SELECT author_id FROM authors ORDER BY author_id LIMIT 8)
            SELECT a.author_id,a.name,count(DISTINCT p.publication_id) AS distinct_publications,
                count(p.publication_id) AS authorship_rows, max(s.publication_count) AS legacy_count
            FROM chosen JOIN authors a USING(author_id) LEFT JOIN publication_authors pa USING(author_id)
            LEFT JOIN publications p USING(publication_id) LEFT JOIN author_stats s ON a.author_id=s.author_id
            GROUP BY a.author_id,a.name ORDER BY a.author_id""")
        if xml_path:
            # Parse the retained XML exactly as the import did. Never load outside DTDs.
            context = etree.iterparse(str(xml_path), events=("end",),
                tag=("article", "inproceedings", "proceedings", "book", "incollection", "phdthesis", "mastersthesis"),
                load_dtd=False, resolve_entities=False, no_network=True)
            rows, incomplete = [], []
            for i, (_, elem) in enumerate(context, 1):
                title = elem.find("title")
                stored = " ".join((elem.findtext("title") or "").split())
                yr = elem.findtext("year")
                names = ["".join(a.itertext()).strip() for a in elem.findall("author")]
                rows.append((i, elem.get("key", ""), elem.tag, stored,
                             int(yr) if yr and yr.isdigit() else None,
                             (elem.findtext("journal") or elem.findtext("booktitle") or "").strip(),
                             "|||".join(n for n in names if n)))
                if title is not None and len(title):
                    if len(incomplete) < 10:
                        incomplete.append({"publication_id": i, "db_key": elem.get("key"),
                            "stored_title": stored, "xml_title": etree.tostring(title, encoding="unicode").strip()})
                elem.clear()
                while elem.getprevious() is not None:
                    del elem.getparent()[0]
                if i >= sample_size:
                    break
            import pyarrow as pa
            table = pa.Table.from_pylist([dict(zip(("id", "db_key", "type", "title", "year", "venue", "authors"), r)) for r in rows])
            db.register("xml_sample", table)
            check("xml_raw_sample", """SELECT count(*) AS checked_records,
                count(*) FILTER(WHERE r.id IS NULL OR x.db_key IS DISTINCT FROM r.db_key
                OR x.type IS DISTINCT FROM r.type OR x.title IS DISTINCT FROM r.title
                OR x.year IS DISTINCT FROM r.year OR x.venue IS DISTINCT FROM r.venue
                OR x.authors IS DISTINCT FROM r.authors) AS mismatches
                FROM xml_sample x LEFT JOIN raw_publications r USING(id)""")
            db.unregister("xml_sample")
            report["xml_sample"] = {"strategy": "first N supported XML records; not a random sample",
                "records": len(rows), "title_child_loss_examples": incomplete,
                "limitation": "Confirms parser reproducibility, not complete source fidelity. Author XML entities can also be unresolved."}
    after = db_path.stat()
    report["database_unchanged"] = (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
    report["total_seconds"] = round(perf_counter() - started, 6)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path(os.environ.get("DBLP_DB_PATH", ROOT / "database/dblp.duckdb")))
    parser.add_argument("--xml", type=Path, default=ROOT / "data/dblp.xml")
    parser.add_argument("--sample-size", type=int, default=10000)
    parser.add_argument("--output", type=Path, default=ROOT / "reports/assistant/trusted-data-v1.json")
    args = parser.parse_args()
    if not 1 <= args.sample_size <= 100000:
        parser.error("sample size must be between 1 and 100000")
    if args.output.resolve() in {args.db.resolve(), args.xml.resolve()}:
        parser.error("output must not replace a source file")
    result = audit(args.db, args.xml, args.sample_size)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(args.output), "corpus": result["checks"]["corpus"],
                      "database_unchanged": result["database_unchanged"], "seconds": result["total_seconds"]}))


if __name__ == "__main__":
    main()
