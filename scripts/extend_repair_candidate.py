"""Decode source author names and rebuild trusted classifications in a NEW candidate.

No activation, author-ID merges, external data, synthetic-metric generation, or
active database writes. Ambiguous old-name mappings keep their existing names.
"""
import argparse
from collections import Counter, defaultdict
from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import sys
from time import perf_counter

import duckdb
from lxml import etree
import pyarrow as pa

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.prepare_title_repair_candidate import LocalXMLOnly, TAGS, sha256


def decoded_text(node, entities):
    """Resolve actual entity nodes, never entity-looking literal text (double decode)."""
    if isinstance(node, etree._Entity):
        if node.name not in entities:
            raise ValueError('Unknown source XML entity')
        return entities[node.name]
    return (node.text or '') + ''.join(decoded_text(child, entities) + (child.tail or '') for child in node)


def author_rows(xml, dtd, variants):
    entities = {e.name: e.content for e in etree.DTD(str(dtd)).iterentities()}
    if any('&' in value for value in entities.values()):
        raise ValueError('Nested DTD entities require separate review')
    with xml.open('rb') as stream:
        context = etree.iterparse(stream, events=('end',), tag=TAGS,
            load_dtd=False, resolve_entities=False, no_network=True)
        context.resolvers.add(LocalXMLOnly(xml, dtd))
        for pid, (_, elem) in enumerate(context, 1):
            old_names, new_names = [], []
            for author in elem.findall('author'):
                if len(author):
                    old = ''.join(author.itertext()).strip()
                    new = decoded_text(author, entities).strip()
                else:
                    old = new = (author.text or '').strip()
                if old:
                    if not new or '|||' in new:
                        raise ValueError('Decoded name cannot be represented in retained author-string format')
                    old_names.append(old)
                    new_names.append(new)
                    # Include literal ampersands too, so one original string that
                    # represented different source strings is detected, not guessed.
                    if '&' in old or old != new:
                        variants[old][new] += 1
            yield pid, elem.get('key', ''), '|||'.join(old_names), '|||'.join(new_names)
            elem.clear()
            while elem.getprevious() is not None:
                del elem.getparent()[0]


def stage_author_changes(db, xml, dtd, batch_size=100000):
    db.execute('''CREATE TABLE _candidate_raw_author_changes(
        publication_id BIGINT PRIMARY KEY, db_key VARCHAR, old_authors VARCHAR, new_authors VARCHAR)''')
    variants = defaultdict(Counter)
    batch = []
    seen = 0
    def flush():
        db.register('author_repair_batch', pa.Table.from_pylist(batch))
        try:
            invalid = db.execute('''SELECT count(*) FROM author_repair_batch b
                LEFT JOIN raw_publications r ON b.publication_id=r.id
                WHERE r.id IS NULL OR r.db_key IS DISTINCT FROM b.db_key OR r.authors IS DISTINCT FROM b.old_authors''').fetchone()[0]
            if invalid:
                raise ValueError('Original XML author extraction does not match candidate raw records')
            db.execute('INSERT INTO _candidate_raw_author_changes SELECT * FROM author_repair_batch')
        finally:
            db.unregister('author_repair_batch')
        batch.clear()
    with closing(author_rows(xml, dtd, variants)) as rows:
        for pid, key, old, new in rows:
            seen += 1
            if old != new:
                batch.append(dict(publication_id=pid, db_key=key, old_authors=old, new_authors=new))
                if len(batch) >= batch_size:
                    flush()
            if seen % 1000000 == 0:
                print(f'Inspected author extraction on {seen:,} publications', flush=True)
    if batch:
        flush()
    if seen != db.execute('SELECT count(*) FROM publications').fetchone()[0]:
        raise ValueError('XML/publication record count mismatch')
    db.execute('''CREATE TABLE _candidate_author_name_variants(
        old_name VARCHAR, decoded_name VARCHAR, occurrences BIGINT)''')
    packed = [{'old_name':old, 'decoded_name':new, 'occurrences':count}
              for old, options in variants.items() for new, count in options.items()]
    if packed:
        db.register('name_variants_batch', pa.Table.from_pylist(packed))
        db.execute('INSERT INTO _candidate_author_name_variants SELECT * FROM name_variants_batch')
        db.unregister('name_variants_batch')
    del variants, packed
    invalid = db.execute('''SELECT count(*) FROM _candidate_author_name_variants v
        LEFT JOIN authors a ON v.old_name=a.name WHERE a.author_id IS NULL''').fetchone()[0]
    if invalid:
        raise ValueError('Source name mapping has no existing author ID')
    db.execute('''CREATE TABLE _candidate_author_changes AS
        SELECT a.author_id, a.name AS old_name,
            CASE WHEN count(*)=1 THEN min(v.decoded_name) ELSE a.name END AS new_name,
            count(*) AS source_variants,
            CASE WHEN count(*)>1 THEN 'ambiguous_preserved'
                 WHEN min(v.decoded_name)<>a.name THEN 'decoded' ELSE 'unchanged' END AS disposition
        FROM authors a JOIN _candidate_author_name_variants v ON a.name=v.old_name
        GROUP BY a.author_id,a.name''')
    db.execute('''UPDATE authors SET name=c.new_name FROM _candidate_author_changes c
        WHERE authors.author_id=c.author_id AND c.disposition='decoded' ''')
    db.execute('''UPDATE raw_publications SET authors=c.new_authors FROM _candidate_raw_author_changes c
        WHERE raw_publications.id=c.publication_id''')
    db.execute('''CREATE TABLE _candidate_author_name_collisions AS
        SELECT name AS decoded_name, list(author_id ORDER BY author_id) AS author_ids, count(*) AS id_count
        FROM authors GROUP BY name HAVING count(*)>1''')
    return {'xml_records_inspected':seen,
        'changed_raw_author_strings':db.execute('SELECT count(*) FROM _candidate_raw_author_changes').fetchone()[0],
        'changed_author_names':db.execute("SELECT count(*) FROM _candidate_author_changes WHERE disposition='decoded'").fetchone()[0],
        'ambiguous_author_ids_preserved':db.execute("SELECT count(*) FROM _candidate_author_changes WHERE disposition='ambiguous_preserved'").fetchone()[0],
        'collision_name_groups':db.execute('SELECT count(*) FROM _candidate_author_name_collisions').fetchone()[0],
        'collision_author_ids':db.execute('SELECT coalesce(sum(id_count),0) FROM _candidate_author_name_collisions').fetchone()[0]}


def rebuild_classifications(db):
    """Dashboard-compatible schemas, explicit project rules, distinct counts."""
    keywords = [r[0].lower() for r in db.execute('SELECT DISTINCT keyword FROM topic_keywords').fetchall()]
    if not keywords or any(not k for k in keywords):
        raise ValueError('Classification keywords must be nonempty')
    pattern = '|'.join(re.escape(k) for k in keywords)
    db.execute('''CREATE TEMP TABLE eligible_keyword_titles AS SELECT publication_id,lower(title) AS title
        FROM publications WHERE year>=1970 AND regexp_matches(lower(title), ?)''', [pattern])
    db.execute('DELETE FROM publication_topics')
    db.execute('''INSERT INTO publication_topics
        WITH pairs AS (
            SELECT p.publication_id,tk.topic_id,max(tk.weight) AS weight
            FROM eligible_keyword_titles p JOIN topic_keywords tk ON contains(p.title,lower(tk.keyword))
            GROUP BY p.publication_id,tk.topic_id
        ), ranked AS (
            SELECT *,row_number() OVER(PARTITION BY publication_id ORDER BY weight DESC,topic_id) AS rn FROM pairs
        ) SELECT publication_id,topic_id,weight FROM ranked WHERE rn<=2''')
    db.execute('DROP TABLE eligible_keyword_titles')
    print('Rebuilt distinct title-based project classification pairs', flush=True)
    # Preserve the existing dashboard periods; no seeded defaults for empty topics.
    db.execute('''UPDATE topics SET publication_count=0,first_seen_year=NULL,latest_activity_year=NULL,growth_rate=NULL''')
    db.execute('''WITH counts AS (SELECT pt.topic_id,min(p.year) AS first_year,max(p.year) AS last_year,
        count(DISTINCT p.publication_id) AS n,
        count(DISTINCT p.publication_id) FILTER(WHERE p.year<2016) AS historical,
        count(DISTINCT p.publication_id) FILTER(WHERE p.year BETWEEN 2016 AND 2025) AS recent
        FROM publication_topics pt JOIN publications p USING(publication_id) GROUP BY pt.topic_id)
        UPDATE topics SET publication_count=c.n,first_seen_year=c.first_year,latest_activity_year=c.last_year,
        growth_rate=round(100.0*(c.recent-c.historical)/nullif(c.historical,0),1) FROM counts c WHERE topics.topic_id=c.topic_id''')
    db.execute('DELETE FROM topic_year_stats')
    db.execute('''INSERT INTO topic_year_stats SELECT pt.topic_id,p.year,count(DISTINCT p.publication_id)
        FROM publication_topics pt JOIN publications p USING(publication_id)
        WHERE p.year BETWEEN 1970 AND 2026 GROUP BY pt.topic_id,p.year''')
    db.execute('DELETE FROM author_topics')
    db.execute('''INSERT INTO author_topics WITH counts AS (
        SELECT pa.author_id,pt.topic_id,count(DISTINCT pa.publication_id) AS n
        FROM publication_authors pa JOIN publication_topics pt USING(publication_id)
        GROUP BY pa.author_id,pt.topic_id HAVING count(DISTINCT pa.publication_id)>=2)
        SELECT author_id,topic_id,n,round(100.0*n/sum(n) OVER(PARTITION BY author_id),1) FROM counts''')
    db.execute('DELETE FROM venue_topics')
    db.execute('''INSERT INTO venue_topics WITH counts AS (
        SELECT p.venue_id,pt.topic_id,count(DISTINCT p.publication_id) AS n
        FROM publications p JOIN publication_topics pt USING(publication_id) WHERE p.venue_id IS NOT NULL
        GROUP BY p.venue_id,pt.topic_id HAVING count(DISTINCT p.publication_id)>=5)
        SELECT venue_id,topic_id,n,round(100.0*n/sum(n) OVER(PARTITION BY venue_id),1) FROM counts''')
    db.execute('DELETE FROM author_stats')
    db.execute('''INSERT INTO author_stats SELECT a.author_id,a.name,count(DISTINCT pa.publication_id)
        FROM authors a JOIN publication_authors pa USING(author_id) JOIN publications p USING(publication_id)
        GROUP BY a.author_id,a.name''')
    db.execute('DELETE FROM author_collaboration_dashboard_named')
    db.execute('''INSERT INTO author_collaboration_dashboard_named
        SELECT a.name,b.name,c.weight FROM author_collaboration_dashboard c
        JOIN authors a ON c.author1_id=a.author_id JOIN authors b ON c.author2_id=b.author_id''')
    # Refresh labels only; inherited momentum scores are never assistant evidence.
    db.execute('UPDATE author_momentum SET name=a.name FROM authors a WHERE author_momentum.author_id=a.author_id')
    db.execute('UPDATE author_momentum SET primary_topic=NULL,explanation=NULL')
    db.execute('''WITH ranked AS (SELECT atp.author_id,t.topic_name,
        row_number() OVER(PARTITION BY atp.author_id ORDER BY atp.publication_count DESC,atp.topic_id) AS rn
        FROM author_topics atp JOIN topics t USING(topic_id))
        UPDATE author_momentum SET primary_topic=r.topic_name FROM ranked r
        WHERE author_momentum.author_id=r.author_id AND r.rn=1''')
    db.execute('''UPDATE author_momentum SET explanation=
        'Legacy project momentum score; excluded from assistant evidence. Primary title-based project classification: '
        || coalesce(primary_topic,'information unavailable') || '.' ''')
    return {'publication_topic_pairs':db.execute('SELECT count(*) FROM publication_topics').fetchone()[0],
        'classification_label':'title-based project classification',
        'rules':{'first_year':1970,'max_distinct_topics_per_publication':2,'topic_tie_break':'weight DESC, topic_id ASC',
                 'year_stats_range':[1970,2026],'growth_historical':'year < 2016','growth_recent':[2016,2025],
                 'author_topic_min_publications':2,'venue_topic_min_publications':5,'counts':'distinct publication IDs'}}


def extend(source, output, active, xml, dtd):
    start=perf_counter()
    source,output,active=(p.resolve() for p in (source,output,active))
    if output in (source,active) or output.exists() or output.with_suffix('.manifest.json').exists():
        raise ValueError('Output must be a new candidate, never an existing or active database')
    previous=json.loads(source.with_suffix('.manifest.json').read_text(encoding='utf-8'))
    if previous['state']!='candidate_review_only' or sha256(source)!=previous['candidate_sha256']:
        raise ValueError('Input candidate is incomplete or changed')
    active_hash=sha256(active)
    if active_hash!=previous['source_sha256'] or sha256(xml)!=previous['xml_sha256'] or sha256(dtd)!=previous['dtd_sha256']:
        raise ValueError('Active/source XML provenance changed; audit again')
    if Path(str(source)+'.wal').exists() or Path(str(active)+'.wal').exists():
        raise ValueError('Source databases must be closed and checkpointed')
    output.parent.mkdir(parents=True,exist_ok=True)
    report={'version':2,'state':'building_not_active','created_at_utc':datetime.now(timezone.utc).isoformat(),
        'source_database':str(source),'source_sha256':previous['candidate_sha256'],'active_database':str(active),
        'active_sha256':active_hash,'candidate_database':str(output),'xml_sha256':previous['xml_sha256'],
        'dtd_sha256':previous['dtd_sha256'],'stages_seconds':{},'author_ids_merged':0,'active_database_modified':False}
    manifest=output.with_suffix('.manifest.json')
    manifest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    shutil.copyfile(source,output)
    if sha256(output)!=previous['candidate_sha256']:
        raise ValueError('Input changed while copying')
    try:
        with closing(duckdb.connect(str(output),config={'memory_limit':'6GB','threads':'6'})) as db:
            db.execute('BEGIN TRANSACTION')
            t=perf_counter()
            report['authors']=stage_author_changes(db,xml,dtd)
            report['stages_seconds']['author_repair']=perf_counter()-t
            print(json.dumps(report['authors']),flush=True)
            t=perf_counter()
            report['classification']=rebuild_classifications(db)
            report['stages_seconds']['classification_rebuild']=perf_counter()-t
            db.execute('COMMIT')
            db.execute('CHECKPOINT')
            report['corpus']=dict(zip(('publications','eligible_titles','empty_title_exclusions'),db.execute('''
                SELECT count(*),count(*) FILTER(WHERE length(trim(title))>0),
                count(*) FILTER(WHERE title IS NULL OR length(trim(title))=0) FROM publications''').fetchone()))
            report['author_examples']=db.execute("SELECT author_id,old_name,new_name FROM _candidate_author_changes WHERE disposition='decoded' ORDER BY author_id LIMIT 10").fetchall()
            report['collision_examples']=db.execute('SELECT * FROM _candidate_author_name_collisions ORDER BY decoded_name LIMIT 10').fetchall()
        if sha256(active)!=active_hash or sha256(source)!=previous['candidate_sha256']:
            raise ValueError('An input database changed during the build')
        report.update(state='candidate_review_only',candidate_sha256=sha256(output),candidate_bytes=output.stat().st_size,
            seconds=perf_counter()-start,
            retained_excluded_snapshots=['publication_citations','author_impact_stats','institutions','author_institutions',
                'institution_topics','institution_year_stats','institution_collaboration','field_statistics',
                'topic_forecast_signals','paper_citation_lineage','external_ecosystem_metadata',
                'paper_embeddings','author_embeddings','topic_embeddings'],
            activation_limit='Excluded legacy snapshots are not refreshed factual evidence. Candidate has no activation authorization.')
    except Exception as exc:
        report.update(state='failed_not_active',error_category=type(exc).__name__,seconds=perf_counter()-start)
        raise
    finally:
        manifest.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('state','authors','classification','corpus','seconds')}),flush=True)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT/'database/candidates/dblp-titles-v1.duckdb')
    parser.add_argument('--output',type=Path,default=ROOT/'database/candidates/dblp-repaired-v2.duckdb')
    args=parser.parse_args()
    extend(args.source,args.output,ROOT/'database/dblp.duckdb',ROOT/'data/dblp.xml',ROOT/'data/dblp.dtd')
