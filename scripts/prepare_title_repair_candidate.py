"""Prepare (never activate) an ID-preserving title repair in a separate database.

Only title columns change in raw_publications/publications. All legacy derived
tables stay untouched and must be reviewed/rebuilt before a database swap.
No network access; the XML resolver accepts only the named XML and local DTD.
"""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
from time import perf_counter
from urllib.parse import urlsplit
from urllib.request import url2pathname

import duckdb
from lxml import etree
import pyarrow as pa

ROOT = Path(__file__).resolve().parents[1]
TAGS = ("article", "inproceedings", "proceedings", "book", "incollection", "phdthesis", "mastersthesis")


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8*1024*1024), b""):
            digest.update(block)
    return digest.hexdigest()


class LocalXMLOnly(etree.Resolver):
    def __init__(self, xml, dtd):
        self.paths = {xml.resolve(), dtd.resolve()}
        self.dtd = dtd.resolve()

    def resolve(self, url, pubid, context):
        parts = urlsplit(url)
        if url == self.dtd.name:
            path = self.dtd
        elif parts.scheme == "file" and not parts.netloc:
            path = Path(url2pathname(parts.path)).resolve()
        elif parts.scheme and len(parts.scheme) != 1:
            raise ValueError("Unapproved XML dependency")
        else:
            path = Path(url).resolve()
        if path not in self.paths:
            raise ValueError("Unapproved XML dependency")
        return self.resolve_filename(str(path), context)


def normalized_text(elem):
    return " ".join("".join(elem.itertext()).split()) if elem is not None else ""


def source_rows(xml, dtd):
    with xml.open('rb') as stream:
        context = etree.iterparse(stream, events=("end",), tag=TAGS,
                                 load_dtd=True, resolve_entities=True, no_network=True)
        context.resolvers.add(LocalXMLOnly(xml, dtd))
        for i, (_, elem) in enumerate(context, 1):
            authors = ["".join(a.itertext()).strip() for a in elem.findall("author")]
            year = elem.findtext("year")
            yield {"publication_id": i, "db_key": elem.get("key", ""),
                   "title": normalized_text(elem.find("title")),
                   "authors": "|||".join(a for a in authors if a), "type": elem.tag,
                   "year": int(year) if year and year.isdigit() else None}
            elem.clear()
            while elem.getprevious() is not None:
                del elem.getparent()[0]


def prepare(source, xml, dtd, output, batch_size=250000):
    start = perf_counter()
    source, output = source.resolve(), output.resolve()
    if source == output or output.exists():
        raise ValueError("Candidate path must be new and separate from the active database")
    if Path(str(source)+'.wal').exists():
        raise ValueError('Source has a write-ahead log; use a closed checkpointed source for copying')
    report_path = output.with_suffix(".manifest.json")
    if report_path.exists():
        raise ValueError("Candidate manifest already exists")
    source_stat = source.stat()
    source_hash = sha256(source)
    report = {"version": 1, "state": "building_not_active", "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_database": str(source), "source_sha256": source_hash, "candidate_database": str(output),
        "xml_sha256": sha256(xml), "dtd_sha256": sha256(dtd), "batch_size": batch_size,
        "author_identity_changed": False, "active_database_modified": False}
    output.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    # Copy a closed, static local file. Verify source stability and copied bytes.
    shutil.copyfile(source, output)
    if sha256(output) != source_hash:
        raise ValueError("Source changed while copying; candidate is invalid")
    with closing(duckdb.connect(str(output), config={"memory_limit":"6GB", "threads":"6"})) as db:
        db.execute("""CREATE TABLE _candidate_title_changes (
            publication_id BIGINT PRIMARY KEY, db_key VARCHAR, old_title VARCHAR, new_title VARCHAR)""")
        initial = db.execute("""SELECT count(*),count(*) FILTER(WHERE length(trim(title))>0),
            count(*) FILTER(WHERE title IS NULL OR length(trim(title))=0) FROM publications""").fetchone()
        seen = 0
        author_differences = 0
        author_examples = []
        def flush(batch):
            nonlocal seen, author_differences
            db.register("repair_batch", pa.Table.from_pylist(batch))
            try:
                matched, invalid = db.execute("""SELECT count(*),count(*) FILTER(WHERE
                    p.publication_id IS NULL OR r.id IS NULL OR p.db_key IS DISTINCT FROM b.db_key
                    OR r.db_key IS DISTINCT FROM b.db_key OR p.type IS DISTINCT FROM b.type
                    OR p.year IS DISTINCT FROM b.year)
                    FROM repair_batch b LEFT JOIN publications p USING(publication_id)
                    LEFT JOIN raw_publications r ON b.publication_id=r.id""").fetchone()
                if matched != len(batch) or invalid:
                    raise ValueError("XML publication IDs/keys/types/years do not match the active database")
                db.execute("""INSERT INTO _candidate_title_changes
                    SELECT b.publication_id,b.db_key,p.title,b.title FROM repair_batch b
                    JOIN publications p USING(publication_id) WHERE p.title IS DISTINCT FROM b.title""")
                author_differences += db.execute("""SELECT count(*) FROM repair_batch b
                    JOIN raw_publications r ON b.publication_id=r.id WHERE r.authors IS DISTINCT FROM b.authors""").fetchone()[0]
                if len(author_examples)<10:
                    author_examples.extend(db.execute("""SELECT b.publication_id,b.db_key,r.authors,b.authors
                        FROM repair_batch b JOIN raw_publications r ON b.publication_id=r.id
                        WHERE r.authors IS DISTINCT FROM b.authors ORDER BY b.publication_id LIMIT ?""",
                        [10-len(author_examples)]).fetchall())
                seen += len(batch)
                print(f"Compared {seen:,} XML records",flush=True)
            finally:
                db.unregister("repair_batch")
        batch=[]
        with closing(source_rows(xml,dtd)) as parsed:
            for row in parsed:
                batch.append(row)
                if len(batch)>=batch_size:
                    flush(batch)
                    batch=[]
        if batch:
            flush(batch)
        if seen != initial[0]:
            raise ValueError("XML/core record-count mismatch; candidate is invalid")
        db.execute("BEGIN TRANSACTION")
        try:
            db.execute("""UPDATE publications SET title=c.new_title FROM _candidate_title_changes c
                WHERE publications.publication_id=c.publication_id""")
            db.execute("""UPDATE raw_publications SET title=c.new_title FROM _candidate_title_changes c
                WHERE raw_publications.id=c.publication_id""")
            mismatch = db.execute("""SELECT count(*) FROM publications p JOIN raw_publications r
                ON p.publication_id=r.id WHERE p.title IS DISTINCT FROM r.title""").fetchone()[0]
            if mismatch:
                raise ValueError("Candidate normalized/raw title mismatch")
            db.execute("COMMIT")
        except Exception:
            db.execute("ROLLBACK")
            raise
        final = db.execute("""SELECT count(*),count(*) FILTER(WHERE length(trim(title))>0),
            count(*) FILTER(WHERE title IS NULL OR length(trim(title))=0) FROM publications""").fetchone()
        report.update({"state":"candidate_review_only", "xml_records_compared":seen,
            "before":{"publications":initial[0],"eligible_titles":initial[1],"empty_title_exclusions":initial[2]},
            "after":{"publications":final[0],"eligible_titles":final[1],"empty_title_exclusions":final[2]},
            "changed_titles":db.execute("SELECT count(*) FROM _candidate_title_changes").fetchone()[0],
            "title_change_examples":db.execute("SELECT * FROM _candidate_title_changes ORDER BY publication_id LIMIT 12").fetchall(),
            "source_author_string_differences":author_differences, "author_difference_examples":author_examples,
            "stale_derived_tables":"All title-dependent classifications, summaries, narratives and legacy embeddings require review/rebuild. Candidate is not approved for activation.",
            "source_quality_limit":"Author-name strings/IDs and venue extraction are unchanged; title repair alone does not resolve homonyms or all XML import defects."})
        db.execute("CHECKPOINT")
    after=source.stat()
    if (source_stat.st_size,source_stat.st_mtime_ns)!=(after.st_size,after.st_mtime_ns) or sha256(source)!=source_hash:
        raise ValueError("Active database changed during preparation; candidate must be reviewed again")
    report["candidate_sha256"]=sha256(output)
    report["candidate_bytes"]=output.stat().st_size
    report["seconds"]=perf_counter()-start
    report_path.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    return report


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source",type=Path,default=ROOT/"database/dblp.duckdb")
    parser.add_argument("--xml",type=Path,default=ROOT/"data/dblp.xml")
    parser.add_argument("--dtd",type=Path,default=ROOT/"data/dblp.dtd")
    parser.add_argument("--output",type=Path,default=ROOT/"database/candidates/dblp-titles-v1.duckdb")
    args=parser.parse_args()
    result=prepare(args.source,args.xml,args.dtd,args.output)
    print(json.dumps({k:result[k] for k in ("state","changed_titles","before","after","source_author_string_differences","seconds")}))
