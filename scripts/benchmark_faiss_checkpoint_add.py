"""Benchmark HNSW insertion against a full-build checkpoint at 500k scale."""
import argparse,json,sys
from pathlib import Path
from time import perf_counter
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'.work/rag-benchmark/packages'))
import duckdb,faiss,numpy as np
from benchmark_retrieval import Encoder,file_sha256,peak_rss

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--db',type=Path,default=ROOT/'database/dblp.duckdb');ap.add_argument('--sidecar',type=Path,default=ROOT/'database/indexes/dblp-title-v2');ap.add_argument('--model',type=Path,default=ROOT/'.work/rag-benchmark/model');ap.add_argument('--sample-size',type=int,default=8192);ap.add_argument('--output',type=Path,default=ROOT/'reports/assistant/faiss-insertion-tuning-v2.json');a=ap.parse_args()
    manifest=json.loads((a.sidecar/'manifest.json').read_text(encoding='utf-8'));slot=manifest.get('checkpoint_slot');count=int(manifest.get('checkpoint_vectors',0))
    if not slot or count<500000:raise ValueError('A validated 500k-vector checkpoint is required')
    checkpoint=a.sidecar/f'vectors-{slot}.faiss'
    if file_sha256(checkpoint)!=manifest['checkpoint_sha256']:raise ValueError('Checkpoint checksum mismatch')
    db=duckdb.connect(str(a.db),read_only=True);db.execute('SET threads=1');rows=db.execute(f'''SELECT publication_id,title FROM (SELECT publication_id,title FROM publications WHERE title IS NOT NULL AND length(trim(title))>0) USING SAMPLE reservoir({a.sample_size} ROWS) REPEATABLE(20260928)''').fetchall();db.close();rows.sort(key=lambda r:r[0]);titles=[str(r[1]) for r in rows]
    enc=Encoder(a.model,6);vectors=np.concatenate([enc.encode(titles[o:o+64]) for o in range(0,len(titles),64)]);del enc
    results=[];started=perf_counter()
    for threads in (1,2,4,6,8,10,12):
      for chunk in (64,256):
        ix=faiss.read_index(str(checkpoint));faiss.omp_set_num_threads(threads);t=perf_counter()
        for off in range(0,len(vectors),chunk):ix.add(vectors[off:off+chunk])
        elapsed=perf_counter()-t;results.append({'threads':threads,'faiss_add_chunk':chunk,'titles':len(vectors),'seconds':elapsed,'titles_per_second':len(vectors)/elapsed,'checkpoint_vectors_before':count,'result_vectors_after':ix.ntotal});del ix
    report={'version':1,'status':'completed','candidate_sha256':file_sha256(a.db),'checkpoint_sha256':manifest['checkpoint_sha256'],'checkpoint_vectors':count,'sample_size':len(rows),'sample_seed':20260928,'configuration_results':results,'process_peak_working_set_bytes':peak_rss(),'total_seconds':perf_counter()-started,'qualification':'Faiss-only insertion benchmark using the actual scalar-8 checkpoint at 501,760 vectors. It excludes embedding and may not predict graph insertion cost at full corpus size.'}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
