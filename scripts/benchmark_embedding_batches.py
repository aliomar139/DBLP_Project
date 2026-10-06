"""Compare ONNX embedding batch sizes and CPU threads on full-corpus titles."""
import argparse,json,hashlib,sys
from pathlib import Path
from time import perf_counter
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'.work/rag-benchmark/packages'))
import duckdb,numpy as np
from benchmark_retrieval import Encoder,file_sha256,peak_rss,stats

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--db',type=Path,default=ROOT/'database/dblp.duckdb');ap.add_argument('--model',type=Path,default=ROOT/'.work/rag-benchmark/model');ap.add_argument('--sample-size',type=int,default=12000);ap.add_argument('--output',type=Path,default=ROOT/'reports/assistant/embedding-batch-tuning-v2.json');a=ap.parse_args()
    if not 2000<=a.sample_size<=30000:ap.error('sample size must be between 2,000 and 30,000')
    db=duckdb.connect(str(a.db),read_only=True,config={'memory_limit':'4GB','threads':'2'});db.execute('SET threads=1')
    rows=db.execute(f'''SELECT publication_id,title FROM (SELECT publication_id,title FROM publications WHERE title IS NOT NULL AND length(trim(title))>0) USING SAMPLE reservoir({a.sample_size} ROWS) REPEATABLE(20260927)''').fetchall();db.close();rows.sort(key=lambda r:r[0]);titles=[str(r[1]) for r in rows]
    sample_hash=hashlib.sha256(b''.join(int(pid).to_bytes(8,'little',signed=True) for pid,_ in rows)).hexdigest()
    results=[];started=perf_counter()
    for threads in (6,8,10,12):
      enc=Encoder(a.model,threads);enc.encode(titles[:64])
      for batch in (64,128,256,512):
        lat=[];count=0;t0=perf_counter()
        for off in range(0,len(titles),batch):
          t=perf_counter();vec=enc.encode(titles[off:off+batch]);lat.append((perf_counter()-t)*1000);count+=len(vec)
        elapsed=perf_counter()-t0
        results.append({'threads':threads,'batch_size':batch,'titles':count,'seconds':elapsed,'titles_per_second':count/elapsed,'batch_latency_ms':stats(lat),'truncated_titles':enc.truncated})
      del enc
    report={'version':1,'status':'completed','candidate_sha256':file_sha256(a.db),'model_manifest_sha256':file_sha256(a.model/'manifest.json'),'sample_seed':20260927,'sample_size':len(rows),'sample_publication_id_sha256':sample_hash,'configuration_results':results,'process_peak_working_set_bytes':peak_rss(),'total_seconds':perf_counter()-started,'qualification':'CPU embedding-only tuning; no Faiss insertion, FTS writes, or corpus scan time. Compare with the active build profile before changing all settings.'}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
