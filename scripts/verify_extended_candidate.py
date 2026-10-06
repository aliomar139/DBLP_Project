"""Read-only full core invariants, source XML checks, and independent sample rules."""
from collections import defaultdict
from contextlib import closing
import json
from pathlib import Path
import sys
from time import perf_counter
import duckdb
import pyarrow as pa

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.prepare_title_repair_candidate import sha256, source_rows


def verify(candidate, check_xml=True):
    start=perf_counter()
    manifest=json.loads(candidate.with_suffix('.manifest.json').read_text(encoding='utf-8'))
    if manifest['state']!='candidate_review_only':raise ValueError('Candidate is not complete')
    source=Path(manifest['source_database'])
    active=Path(manifest['active_database'])
    for path,key in ((candidate,'candidate_sha256'),(source,'source_sha256'),(active,'active_sha256')):
        if sha256(path)!=manifest[key]:raise ValueError('Database fingerprint mismatch')
    result={'version':2,'candidate_sha256':manifest['candidate_sha256'],'checks':{}}
    with closing(duckdb.connect(str(candidate),read_only=True,config={'memory_limit':'6GB','threads':'6'})) as db:
        db.execute("ATTACH '"+str(source).replace("'","''")+"' AS original (READ_ONLY)")
        def check(name,sql):
            t=perf_counter();count=db.execute(sql).fetchone()[0]
            result['checks'][name]={'unexpected_rows':count,'seconds':perf_counter()-t}
            print(name,count,flush=True)
        check('publication_changes','''SELECT count(*) FROM publications c FULL JOIN original.publications o USING(publication_id)
            WHERE c.publication_id IS NULL OR o.publication_id IS NULL OR c.db_key IS DISTINCT FROM o.db_key
            OR c.title IS DISTINCT FROM o.title OR c.year IS DISTINCT FROM o.year OR c.type IS DISTINCT FROM o.type
            OR c.venue_id IS DISTINCT FROM o.venue_id''')
        check('unexpected_author_changes','''SELECT count(*) FROM authors c FULL JOIN original.authors o USING(author_id)
            LEFT JOIN _candidate_author_changes d ON c.author_id=d.author_id
            WHERE c.author_id IS NULL OR o.author_id IS NULL
            OR c.name IS DISTINCT FROM CASE WHEN d.disposition='decoded' THEN d.new_name ELSE o.name END
            OR (d.author_id IS NOT NULL AND d.old_name IS DISTINCT FROM o.name)''')
        check('authorship_changes','''SELECT count(*) FROM publication_authors c FULL JOIN original.publication_authors o ON c.rowid=o.rowid
            WHERE c.publication_id IS DISTINCT FROM o.publication_id OR c.author_id IS DISTINCT FROM o.author_id''')
        check('venue_changes','''SELECT count(*) FROM venues c FULL JOIN original.venues o ON c.rowid=o.rowid
            WHERE c.venue_id IS DISTINCT FROM o.venue_id OR c.name IS DISTINCT FROM o.name''')
        check('unexpected_raw_changes','''SELECT count(*) FROM raw_publications c FULL JOIN original.raw_publications o USING(id)
            LEFT JOIN _candidate_raw_author_changes d ON c.id=d.publication_id
            WHERE c.id IS NULL OR o.id IS NULL OR c.db_key IS DISTINCT FROM o.db_key OR c.title IS DISTINCT FROM o.title
            OR c.type IS DISTINCT FROM o.type OR c.year IS DISTINCT FROM o.year OR c.venue IS DISTINCT FROM o.venue
            OR c.authors IS DISTINCT FROM CASE WHEN d.publication_id IS NOT NULL THEN d.new_authors ELSE o.authors END
            OR (d.publication_id IS NOT NULL AND (d.old_authors IS DISTINCT FROM o.authors OR d.db_key IS DISTINCT FROM c.db_key))''')
        check('author_count_or_name_errors','''WITH expected AS (
            SELECT a.author_id,a.name,count(DISTINCT p.publication_id) AS n FROM authors a
            JOIN publication_authors pa USING(author_id) JOIN publications p USING(publication_id) GROUP BY a.author_id,a.name)
            SELECT count(*) FROM expected e FULL JOIN author_stats s USING(author_id)
            WHERE e.name IS DISTINCT FROM s.name OR e.n IS DISTINCT FROM s.publication_count''')
        check('duplicate_classification_pairs','''SELECT count(*) FROM
            (SELECT publication_id,topic_id FROM publication_topics GROUP BY ALL HAVING count(*)>1)''')
        check('invalid_classification_evidence','''SELECT count(*) FROM publication_topics pt LEFT JOIN publications p USING(publication_id)
            LEFT JOIN topics t USING(topic_id) WHERE p.publication_id IS NULL OR t.topic_id IS NULL OR p.year IS NULL OR p.year<1970
            OR NOT EXISTS(SELECT 1 FROM topic_keywords k WHERE k.topic_id=pt.topic_id AND contains(lower(p.title),lower(k.keyword)))''')
        check('topic_summary_count_errors','''SELECT count(*) FROM topics t LEFT JOIN
            (SELECT topic_id,count(DISTINCT publication_id) AS n FROM publication_topics GROUP BY topic_id) x USING(topic_id)
            WHERE t.publication_count IS DISTINCT FROM coalesce(x.n,0)''')
        check('topic_year_count_errors','''WITH e AS (SELECT pt.topic_id,p.year,count(DISTINCT p.publication_id) AS n
            FROM publication_topics pt JOIN publications p USING(publication_id) WHERE p.year BETWEEN 1970 AND 2026 GROUP BY pt.topic_id,p.year)
            SELECT count(*) FROM e FULL JOIN topic_year_stats s USING(topic_id,year) WHERE e.n IS DISTINCT FROM s.publication_count''')
        check('author_topic_count_errors','''WITH e AS (SELECT pa.author_id,pt.topic_id,count(DISTINCT pa.publication_id) AS n
            FROM publication_authors pa JOIN publication_topics pt USING(publication_id) GROUP BY pa.author_id,pt.topic_id HAVING count(DISTINCT pa.publication_id)>=2)
            SELECT count(*) FROM e FULL JOIN author_topics s USING(author_id,topic_id) WHERE e.n IS DISTINCT FROM s.publication_count''')
        check('venue_topic_count_errors','''WITH e AS (SELECT p.venue_id,pt.topic_id,count(DISTINCT p.publication_id) AS n
            FROM publications p JOIN publication_topics pt USING(publication_id) WHERE p.venue_id IS NOT NULL
            GROUP BY p.venue_id,pt.topic_id HAVING count(DISTINCT p.publication_id)>=5)
            SELECT count(*) FROM e FULL JOIN venue_topics s USING(venue_id,topic_id) WHERE e.n IS DISTINCT FROM s.publication_count''')
        for table in manifest['retained_excluded_snapshots']:
            # Table names come from the locally produced manifest and are restricted
            # to simple identifiers; no question text or model input reaches SQL.
            if not table.replace('_','').isalnum():raise ValueError('Invalid snapshot identifier')
            columns=[r[1] for r in db.execute(f"PRAGMA table_info('{table}')").fetchall()]
            diff=' OR '.join('c."'+col.replace('"','""')+'" IS DISTINCT FROM o."'+col.replace('"','""')+'"' for col in columns)
            check('unchanged_excluded_'+table,f'SELECT count(*) FROM "{table}" c FULL JOIN original."{table}" o ON c.rowid=o.rowid WHERE c.rowid IS NULL OR o.rowid IS NULL OR {diff}')
        # Python substring matching provides an independent, non-SQL reference for
        # the ranking/cap rule, including repaired titles and randomly selected ones.
        rows=db.execute('''SELECT publication_id,title,year FROM publications USING SAMPLE reservoir(10000 ROWS) REPEATABLE(19)''').fetchall()
        rows+=db.execute('''SELECT p.publication_id,p.title,p.year FROM publications p JOIN _candidate_title_changes c USING(publication_id) ORDER BY p.publication_id LIMIT 1000''').fetchall()
        keywords=db.execute('SELECT topic_id,keyword,weight FROM topic_keywords').fetchall()
        actual=defaultdict(list)
        db.register('sample_ids',pa.table({'publication_id':list({r[0] for r in rows})}))
        for pid,tid,weight in db.execute('SELECT pt.* FROM publication_topics pt JOIN sample_ids USING(publication_id)').fetchall():actual[pid].append((tid,weight))
        errors=0
        for pid,title,year in rows:
            matches={}
            if year is not None and year>=1970:
                for tid,word,weight in keywords:
                    if word.lower() in title.lower():matches[tid]=max(weight,matches.get(tid,float('-inf')))
            expected=sorted(matches.items(),key=lambda x:(-x[1],x[0]))[:2]
            errors+=sorted(expected)!=sorted(actual[pid])
        db.unregister('sample_ids')
        result['checks']['independent_python_classification']={'unexpected_rows':errors,'sample_rows':len(rows)}
        if check_xml:
            batch=[];seen=0;errors=0
            def flush():
                nonlocal errors
                db.register('resolved_xml_batch',pa.Table.from_pylist(batch))
                errors+=db.execute('''SELECT count(*) FROM resolved_xml_batch x LEFT JOIN raw_publications r ON x.publication_id=r.id
                    WHERE r.id IS NULL OR r.db_key IS DISTINCT FROM x.db_key OR r.authors IS DISTINCT FROM x.authors
                    OR r.title IS DISTINCT FROM x.title''').fetchone()[0]
                db.unregister('resolved_xml_batch');batch.clear()
            with closing(source_rows(ROOT/'data/dblp.xml',ROOT/'data/dblp.dtd')) as parsed:
                for row in parsed:
                    batch.append({k:row[k] for k in ('publication_id','db_key','title','authors')});seen+=1
                    if len(batch)>=500000:flush();print(f'Independent resolved XML check: {seen:,}',flush=True)
            if batch:flush()
            errors+=seen!=db.execute('SELECT count(*) FROM publications').fetchone()[0]
            result['checks']['full_resolved_xml_titles_and_authors']={'unexpected_rows':errors,'records':seen}
    result['passed']=all(x['unexpected_rows']==0 for x in result['checks'].values())
    result['seconds']=perf_counter()-start
    (ROOT/'reports/assistant/candidate-extension-verification-v2.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    if not result['passed']:raise ValueError('Candidate verification failed')
    print(json.dumps({'passed':result['passed'],'seconds':result['seconds']}))
    return result


if __name__=='__main__':verify(ROOT/'database/candidates/dblp-repaired-v2.duckdb')
