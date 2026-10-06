"""Independent read-only comparison of candidate core records with the source."""
from contextlib import closing
import json
from pathlib import Path
from time import perf_counter
import duckdb
from prepare_title_repair_candidate import sha256

ROOT=Path(__file__).resolve().parents[1]


def main():
    start=perf_counter()
    source=ROOT/'database/dblp.duckdb'
    candidate=ROOT/'database/candidates/dblp-titles-v1.duckdb'
    manifest=json.loads(candidate.with_suffix('.manifest.json').read_text(encoding='utf-8'))
    if manifest['state']!='candidate_review_only':
        raise ValueError('Candidate build is not complete')
    if sha256(source)!=manifest['source_sha256'] or sha256(candidate)!=manifest['candidate_sha256']:
        raise ValueError('Candidate or source fingerprint no longer matches the build manifest')
    report={'source_sha256':manifest['source_sha256'],'candidate_sha256':manifest['candidate_sha256'],'checks':{}}
    with closing(duckdb.connect(str(candidate),read_only=True,config={'memory_limit':'6GB','threads':'6'})) as db:
        # ATTACH does not accept bound paths. This path is a developer-owned local
        # constant, escaped as a SQL literal; no user/model input enters the SQL.
        db.execute("ATTACH '"+str(source).replace("'","''")+"' AS original (READ_ONLY)")
        checks={
            'publication_identity_or_metadata_changes': '''SELECT count(*) FROM publications c
                FULL JOIN original.publications o USING(publication_id)
                WHERE c.publication_id IS NULL OR o.publication_id IS NULL
                OR c.db_key IS DISTINCT FROM o.db_key OR c.type IS DISTINCT FROM o.type
                OR c.year IS DISTINCT FROM o.year OR c.venue_id IS DISTINCT FROM o.venue_id''',
            'unexpected_title_changes': '''SELECT count(*) FROM publications c JOIN original.publications o USING(publication_id)
                LEFT JOIN _candidate_title_changes d USING(publication_id)
                WHERE (d.publication_id IS NULL AND c.title IS DISTINCT FROM o.title)
                OR (d.publication_id IS NOT NULL AND (c.title IS DISTINCT FROM d.new_title OR o.title IS DISTINCT FROM d.old_title))''',
            'raw_metadata_changes': '''SELECT count(*) FROM raw_publications c FULL JOIN original.raw_publications o USING(id)
                WHERE c.id IS NULL OR o.id IS NULL OR c.db_key IS DISTINCT FROM o.db_key OR c.type IS DISTINCT FROM o.type
                OR c.year IS DISTINCT FROM o.year OR c.venue IS DISTINCT FROM o.venue OR c.authors IS DISTINCT FROM o.authors''',
            'author_identity_changes': '''SELECT count(*) FROM authors c FULL JOIN original.authors o ON c.rowid=o.rowid
                WHERE c.author_id IS DISTINCT FROM o.author_id OR c.name IS DISTINCT FROM o.name''',
            'authorship_changes': '''SELECT count(*) FROM publication_authors c FULL JOIN original.publication_authors o ON c.rowid=o.rowid
                WHERE c.publication_id IS DISTINCT FROM o.publication_id OR c.author_id IS DISTINCT FROM o.author_id''',
            'venue_changes': '''SELECT count(*) FROM venues c FULL JOIN original.venues o ON c.rowid=o.rowid
                WHERE c.venue_id IS DISTINCT FROM o.venue_id OR c.name IS DISTINCT FROM o.name''',
        }
        for name,sql in checks.items():
            t=perf_counter()
            count=db.execute(sql).fetchone()[0]
            report['checks'][name]={'unexpected_rows':count,'seconds':perf_counter()-t}
            print(name,count,flush=True)
    report['passed']=all(r['unexpected_rows']==0 for r in report['checks'].values())
    report['seconds']=perf_counter()-start
    (ROOT/'reports/assistant/title-repair-verification-v1.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    if not report['passed']:
        raise ValueError('Candidate differs beyond authorized title repair')
    print(json.dumps({'passed':report['passed'],'seconds':report['seconds']}))


if __name__=='__main__':
    main()
