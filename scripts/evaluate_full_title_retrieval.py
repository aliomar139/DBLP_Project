"""Evaluate full sidecar recall against the small title-only development probes."""
import argparse,json,math,re,sqlite3,sys
from pathlib import Path
from time import perf_counter
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'.work/rag-benchmark/packages'))
import duckdb,faiss,numpy as np
from benchmark_retrieval import Encoder,stats,file_sha256

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--db',type=Path,default=ROOT/'database/dblp.duckdb');ap.add_argument('--sidecar',type=Path,default=ROOT/'database/indexes/dblp-title-v2');ap.add_argument('--threads',type=int,default=6);ap.add_argument('--output',type=Path,default=ROOT/'reports/assistant/full-retrieval-evaluation-v2.json');a=ap.parse_args()
    manifest=json.loads((a.sidecar/'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('status')!='ready':raise ValueError('Full index is not ready')
    probes=json.loads((ROOT/'docs/assistant/retrieval-probes-v1.json').read_text(encoding='utf-8'))['probes']
    db=duckdb.connect(str(a.db),read_only=True);ids=[p['publication_id'] for p in probes];rows=db.execute('SELECT publication_id,title FROM publications WHERE publication_id IN ('+','.join('?' for _ in ids)+')',ids).fetchall();db.close()
    titles={int(pid):title for pid,title in rows}
    if len(titles)!=len(probes):raise ValueError('A development target is missing from the candidate')
    ix=faiss.read_index(str(a.sidecar/'vectors.faiss'));ix.hnsw.efSearch=64;con=sqlite3.connect(a.sidecar/'keyword-map.sqlite');enc=Encoder(ROOT/'.work/rag-benchmark/model',a.threads)
    cases=[];times={'semantic_ms':[],'lexical_ms':[],'hybrid_ms':[]}
    try:
      for p in probes:
        target=int(p['publication_id']);title=titles[target]
        qv=enc.encode([p['query']]);t=perf_counter();_,positions=ix.search(qv,50);st=(perf_counter()-t)*1000;times['semantic_ms'].append(st)
        # Reassemble by vector position; IN does not preserve ANN rank.
        pos_map={int(pos):int(pid) for pos,pid in con.execute('SELECT vector_position,publication_id FROM vector_ids WHERE vector_position IN ('+','.join('?' for _ in positions[0])+')',positions[0].tolist())}
        sem_ids=[pos_map[int(pos)] for pos in positions[0] if int(pos) in pos_map]
        def lexical(q):
          tokens=list(dict.fromkeys(re.findall(r'[\w]+',q.lower())))[:24]
          expr=' OR '.join('"'+x.replace('"','')+'"' for x in tokens if x)
          start=perf_counter();found=con.execute('SELECT rowid FROM titles WHERE titles MATCH ? ORDER BY rank LIMIT 50',(expr,)).fetchall() if expr else []
          return [int(r[0]) for r in found],(perf_counter()-start)*1000
        lex,lt=lexical(p['query']);times['lexical_ms'].append(lt)
        # Rank-fuse bounded lexical and semantic candidates; no model reranker.
        score={}
        for rank,pid in enumerate(sem_ids,1):score[pid]=score.get(pid,0)+1/(60+rank)
        for rank,pid in enumerate(lex,1):score[pid]=score.get(pid,0)+1/(60+rank)
        t=perf_counter();hybrid=sorted(score,key=score.get,reverse=True)[:10];times['hybrid_ms'].append((perf_counter()-t)*1000)
        exact_sem=enc.encode([title]);_,exact_pos=ix.search(exact_sem,10)
        exact_pos=[int(x) for x in exact_pos[0] if int(x)>=0]
        id_rows=con.execute('SELECT vector_position,publication_id FROM vector_ids WHERE vector_position IN ('+','.join('?' for _ in exact_pos)+')',exact_pos).fetchall() if exact_pos else []
        exact_map={int(pos):int(pid) for pos,pid in id_rows};exact_ids=[exact_map[pos] for pos in exact_pos if pos in exact_map]
        exact_lex,_=lexical(title)
        retrieved=set(sem_ids+lex+hybrid+exact_ids+exact_lex)
        valid={int(r[0]) for r in con.execute('SELECT publication_id FROM vector_ids WHERE publication_id IN ('+','.join('?' for _ in retrieved)+')',list(retrieved)).fetchall()} if retrieved else set()
        cases.append({'case_id':p['id'],'target_id':target,'exact_title':title,'paraphrase':p['query'],
          'paraphrase_semantic_rank':(sem_ids.index(target)+1 if target in sem_ids else None),'paraphrase_lexical_rank':(lex.index(target)+1 if target in lex else None),
          'hybrid_rank':(hybrid.index(target)+1 if target in hybrid else None),'exact_title_semantic_rank':(exact_ids.index(target)+1 if target in exact_ids else None),
          'exact_title_lexical_rank':(exact_lex.index(target)+1 if target in exact_lex else None),
          'candidates_all_valid_ids':valid==retrieved})
      def hit(field):return sum(c[field] is not None and c[field]<=10 for c in cases)/len(cases)
      report={'version':1,'status':'full_corpus_development_probe_evaluation','index_manifest_sha256':file_sha256(a.sidecar/'manifest.json'),'database_sha256':manifest['corpus_sha256'],'probe_file_sha256':file_sha256(ROOT/'docs/assistant/retrieval-probes-v1.json'),'probe_count':len(cases),'coverage':manifest['coverage'],'ef_search':64,'candidate_limit':50,'semantic_model':manifest['model']['repository'],'retrieval':{'exact_title_semantic_target_hit_at_10':hit('exact_title_semantic_rank'),'exact_title_keyword_target_hit_at_10':hit('exact_title_lexical_rank'),'paraphrase_semantic_target_hit_at_10':hit('paraphrase_semantic_rank'),'paraphrase_keyword_target_hit_at_10':hit('paraphrase_lexical_rank'),'paraphrase_hybrid_target_hit_at_10':hit('hybrid_rank')},'latency_ms':{k:stats(v) for k,v in times.items()},'cases':cases,'qualification':'12-item development probe set only; results are not held-out or user-reviewed answer accuracy.'}
      a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');print(json.dumps(report,indent=2))
    finally:con.close()
if __name__=='__main__':main()
