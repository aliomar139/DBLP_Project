"""Check lexical latency scaling before selecting a full-corpus query policy."""
from contextlib import closing
import json
from pathlib import Path
import re
import sqlite3
from time import perf_counter
import duckdb
import numpy as np

ROOT=Path(__file__).resolve().parents[1]


def main():
    report={'version':1,'status':'partial_corpus_keyword_scaling_experiment','results':[]}
    probes=json.loads((ROOT/'docs/assistant/retrieval-probes-v1.json').read_text(encoding='utf-8'))['probes']
    ids=[p['publication_id'] for p in probes]
    with closing(duckdb.connect(str(ROOT/'database/dblp.duckdb'),read_only=True,
                               config={'memory_limit':'2GB','threads':'1'})) as db:
        for count in (100000,1000000):
            rows=db.execute(f'''SELECT publication_id,title FROM
                (SELECT publication_id,title FROM publications WHERE length(trim(title))>0)
                USING SAMPLE reservoir({count} ROWS) REPEATABLE(42)''').fetchall()
            included={r[0] for r in rows}
            targets=db.execute('SELECT publication_id,title FROM publications WHERE publication_id IN ('+','.join('?' for _ in ids)+')',ids).fetchall()
            rows.extend(r for r in targets if r[0] not in included)
            path=ROOT/f'.work/rag-benchmark/keyword-scale-{count}.sqlite'
            if path.exists():raise ValueError('Refusing to overwrite an earlier benchmark')
            with closing(sqlite3.connect(path)) as lex:
                lex.execute('PRAGMA cache_size=-65536')
                lex.execute("CREATE VIRTUAL TABLE titles USING fts5(title, tokenize='unicode61')")
                lex.execute("CREATE VIRTUAL TABLE vocab USING fts5vocab(titles,'row')")
                t=perf_counter()
                for offset in range(0,len(rows),10000):
                    lex.executemany('INSERT INTO titles(rowid,title) VALUES(?,?)',rows[offset:offset+10000])
                lex.commit()
                lex.execute("INSERT INTO titles(titles) VALUES('optimize')")
                lex.commit()
                result={'records':len(rows),'build_seconds':perf_counter()-t,'bytes':path.stat().st_size,'policies':{}}
                for policy in ('all_terms_or','four_rarest_terms_or'):
                    durations=[];hits=[]
                    for probe in probes:
                        t=perf_counter()
                        tokens=list(dict.fromkeys(re.findall(r'\w+',probe['query'].lower())))[:32]
                        if policy=='four_rarest_terms_or':
                            freqs=[(lex.execute('SELECT doc FROM vocab WHERE term=?',(token,)).fetchone(),token) for token in tokens]
                            tokens=[token for freq,token in sorted((x for x in freqs if x[0]),key=lambda x:(x[0][0],x[1]))[:4]]
                        expression=' OR '.join('"'+token+'"' for token in tokens)
                        found=lex.execute('SELECT rowid FROM titles WHERE titles MATCH ? ORDER BY rank LIMIT 10',(expression,)).fetchall() if expression else []
                        durations.append((perf_counter()-t)*1000)
                        hits.append(probe['publication_id'] in {r[0] for r in found})
                    result['policies'][policy]={'mean_ms':float(np.mean(durations)),'p95_ms':float(np.percentile(durations,95)),
                        'development_target_hit_at_10':float(np.mean(hits)),'query_count':len(probes)}
                report['results'].append(result)
                print(json.dumps(result),flush=True)
    report['qualification']='Only 12 development paraphrases; timings include rare-term selection. Full-corpus latency and recall remain unmeasured.'
    (ROOT/'reports/assistant/keyword-scale-v1.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':main()
