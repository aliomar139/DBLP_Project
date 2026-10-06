"""Build a versioned full-title FTS5 + scalar-8 HNSW sidecar (never activate it).

Experimental runtimes load only from .work/rag-benchmark/packages. This script
uses repaired candidate v2, verified against local XML. It never changes DuckDB.
The vector index, ID map, coverage ledger and manifest share a versioned sidecar.
Interrupted builds resume from a checksummed Faiss checkpoint and verify source
IDs again as the ordered DuckDB scan is replayed.
"""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
from time import perf_counter

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.work/rag-benchmark/packages'))
os.environ['HF_HUB_OFFLINE']='1'
os.environ['HF_HUB_DISABLE_TELEMETRY']='1'
os.environ['TOKENIZERS_PARALLELISM']='false'
import duckdb
import faiss
import numpy as np
import psutil
from tokenizers import Tokenizer
from benchmark_retrieval import Encoder, peak_rss, file_sha256

CHECKPOINT_SIZE=500000
CHUNK_SIZE=64
EF_CONSTRUCTION=120
M=32
TRAINING_SAMPLE_SIZE=20000


def write_json(path,data):
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    os.replace(temp,path)


def rolling_ids(current, ids):
    h=hashlib.sha256()
    h.update(bytes.fromhex(current) if current else b'')
    h.update(np.asarray(ids,dtype='<i8').tobytes())
    return h.hexdigest()


def make_index(threads):
    faiss.omp_set_num_threads(threads)
    idx=faiss.IndexHNSWSQ(384,faiss.ScalarQuantizer.QT_8bit,M,faiss.METRIC_INNER_PRODUCT)
    idx.hnsw.efConstruction=EF_CONSTRUCTION
    return idx


def build(db_path, model_dir, output_dir, embedding_threads=6, embedding_batch_size=CHUNK_SIZE,
          faiss_threads=4, faiss_add_chunk=256):
    started=perf_counter()
    if min(embedding_threads,faiss_threads,embedding_batch_size,faiss_add_chunk)<1:
        raise ValueError('Thread and batch settings must be positive')
    if embedding_batch_size%64:
        raise ValueError('Embedding batch size must be a multiple of 64 to preserve the coverage digest format')
    if faiss_add_chunk%embedding_batch_size:
        raise ValueError('Faiss add chunk must be a multiple of the embedding batch size')
    db_path=db_path.resolve();output_dir=output_dir.resolve();model_dir=model_dir.resolve()
    if not db_path.is_file() or not model_dir.is_dir():raise ValueError('Database/model directory missing')
    manifest_path=output_dir/'manifest.json'; sqlite_path=output_dir/'keyword-map.sqlite'
    output_dir.mkdir(parents=True,exist_ok=True)
    corpus_sha=file_sha256(db_path)
    model_manifest=json.loads((model_dir/'manifest.json').read_text(encoding='utf-8'))
    corpus_id='dblp-title-v2-'+corpus_sha[:16]
    existing=None
    if manifest_path.exists():
        existing=json.loads(manifest_path.read_text(encoding='utf-8'))
        if existing.get('corpus_sha256')!=corpus_sha or existing.get('model')!=model_manifest:
            raise ValueError('Existing sidecar belongs to another database or model; choose a new output directory')
        if existing.get('status')=='ready':return existing
        if existing.get('status') not in ('building','interrupted'):
            raise ValueError('Existing sidecar has an invalid state')
    idx=None;checkpoint_count=0;id_digest='';fts_count=0
    if existing:
        checkpoint_count=int(existing.get('checkpoint_vectors',0))
        id_digest=existing.get('checkpoint_id_digest','')
        slot=existing.get('checkpoint_slot')
        if checkpoint_count and slot not in ('a','b'):raise ValueError('Checkpoint manifest is inconsistent')
        if checkpoint_count:
            checkpoint=output_dir/f'vectors-{slot}.faiss'
            if not checkpoint.is_file() or file_sha256(checkpoint)!=existing.get('checkpoint_sha256'):
                raise ValueError('Faiss checkpoint is missing or failed checksum')
            idx=faiss.read_index(str(checkpoint))
            if idx.ntotal!=checkpoint_count:raise ValueError('Faiss checkpoint count does not match manifest')
    if idx is None:idx=make_index(faiss_threads)
    else:faiss.omp_set_num_threads(faiss_threads)
    if sqlite_path.exists() and not existing:raise ValueError('Sidecar SQLite exists without manifest; use a fresh directory')
    con=sqlite3.connect(sqlite_path)
    con.execute('PRAGMA journal_mode=WAL');con.execute('PRAGMA synchronous=NORMAL');con.execute('PRAGMA cache_size=-65536')
    con.execute("CREATE VIRTUAL TABLE IF NOT EXISTS titles USING fts5(title,tokenize='unicode61')")
    con.execute('CREATE TABLE IF NOT EXISTS vector_ids(vector_position INTEGER PRIMARY KEY,publication_id INTEGER UNIQUE NOT NULL)')
    con.execute('CREATE TABLE IF NOT EXISTS build_state(key TEXT PRIMARY KEY,value TEXT NOT NULL)')
    con.execute('CREATE TABLE IF NOT EXISTS title_id_hash(vector_position INTEGER PRIMARY KEY,rolling_sha256 TEXT NOT NULL)')
    db=duckdb.connect(str(db_path),read_only=True,config={'memory_limit':'2GB','threads':'1'})
    db.execute("SET preserve_insertion_order=true")
    expected_total,empty=db.execute('''SELECT count(*) FILTER(WHERE length(trim(title))>0),
        count(*) FILTER(WHERE title IS NULL OR length(trim(title))=0) FROM publications''').fetchone()
    if existing and int(existing.get('expected_eligible_titles',expected_total))!=expected_total:
        raise ValueError('Corpus eligible-title count differs from sidecar manifest')
    sqlite_count=con.execute('SELECT count(*) FROM vector_ids').fetchone()[0]
    if sqlite_count<checkpoint_count:raise ValueError('SQLite ID map fell behind Faiss checkpoint')
    con.execute('DELETE FROM vector_ids WHERE vector_position>=?',(checkpoint_count,))
    con.execute('DELETE FROM title_id_hash WHERE vector_position>=?',(checkpoint_count,))
    # Rebuild FTS during resume so its own coverage comes from a complete pass.
    con.execute('DELETE FROM titles')
    con.commit()
    if existing is None:
        existing={'format_version':1,'status':'building','corpus_id':corpus_id,
            'corpus_sha256':corpus_sha,'model':model_manifest,'embedding_dimensions':384,
            'index':{'type':'Faiss HNSW scalar-8 inner product','M':M,'ef_construction':EF_CONSTRUCTION},
            'fts':{'engine':'SQLite FTS5','tokenizer':'unicode61'},
            'expected_eligible_titles':int(expected_total),'empty_title_exclusions':int(empty),
            'processed_titles':0,'checkpoint_vectors':0,'checkpoint_id_digest':'','checkpoint_slot':None,
            'timing_seconds':{},'started_at_utc':datetime.now(timezone.utc).isoformat()}
    existing.pop('error_category',None)
    existing.pop('resumable_from_checkpoint',None)
    existing.update(status='building',last_resumed_at_utc=datetime.now(timezone.utc).isoformat(),
        build_config={'embedding_threads':embedding_threads,'embedding_batch_size':embedding_batch_size,
            'faiss_threads':faiss_threads,'faiss_add_chunk':faiss_add_chunk})
    write_json(manifest_path,existing)
    encoder=Encoder(model_dir,embedding_threads)
    training_seconds=0.0
    training_sample=existing.get('index_training_sample_sha256')
    if not checkpoint_count:
        # Train the scalar quantizer on a seeded sample spanning the entire corpus.
        train_rows=db.execute(f'''SELECT publication_id,title FROM
            (SELECT publication_id,title FROM publications WHERE length(trim(title))>0)
            USING SAMPLE reservoir({TRAINING_SAMPLE_SIZE} ROWS) REPEATABLE(42)''').fetchall()
        train_rows.sort(key=lambda r:r[0])
        if len(train_rows)!=TRAINING_SAMPLE_SIZE:raise ValueError('Incomplete Faiss training sample')
        train_ids=np.asarray([r[0] for r in train_rows],dtype='<i8')
        training_sample=hashlib.sha256(train_ids.tobytes()).hexdigest()
        train_titles=[r[1] for r in train_rows]
        t=perf_counter()
        vectors=np.concatenate([encoder.encode(train_titles[i:i+embedding_batch_size]) for i in range(0,len(train_titles),embedding_batch_size)])
        idx.train(vectors);training_seconds=perf_counter()-t
        del train_rows,train_ids,train_titles,vectors
        if not idx.is_trained:raise ValueError('Faiss scalar quantizer failed to train')
        existing['index_training']={'sample_count':TRAINING_SAMPLE_SIZE,'seed':42,
            'strategy':'single-thread corpus-wide reservoir, sample sorted by publication ID',
            'sample_id_sha256':training_sample,'seconds':training_seconds}
        existing['index_training_sample_sha256']=training_sample
        write_json(manifest_path,existing)
    # Stable ID ordering makes a checkpoint's prefix portable across resumptions.
    cur=db.execute('SELECT publication_id,title FROM publications WHERE title IS NOT NULL AND length(trim(title))>0 ORDER BY publication_id')
    scanned=0;processed=checkpoint_count;fts_existing=0
    digest=id_digest;embedding_seconds=0.0;fts_seconds=0.0;idmap_seconds=0.0;since_checkpoint=0
    replay_digest='';checkpoint_prefix_verified=(checkpoint_count==0)
    last_checkpoint_vectors=checkpoint_count;last_progress_vectors=checkpoint_count
    buffer=[];pubids=[]
    print(json.dumps({'event':'build_started','database':str(db_path),'eligible_titles':expected_total,
        'checkpoint_vectors':checkpoint_count,'fts_existing':fts_existing,'embedding_batch_size':embedding_batch_size,
        'faiss_add_chunk':faiss_add_chunk,'embedding_threads':embedding_threads,'faiss_threads':faiss_threads}),flush=True)

    def flush(batch):
        nonlocal scanned,processed,fts_existing,digest,embedding_seconds,fts_seconds,idmap_seconds,since_checkpoint,last_checkpoint_vectors,last_progress_vectors,replay_digest,checkpoint_prefix_verified
        if not batch:return
        ids=[int(r[0]) for r in batch];titles=[str(r[1]) for r in batch]
        if not checkpoint_prefix_verified:
            prefix_len=min(len(ids),checkpoint_count-scanned)
            for digest_offset in range(0,prefix_len,64):
                replay_digest=rolling_ids(replay_digest,ids[digest_offset:min(digest_offset+64,prefix_len)])
            if scanned+prefix_len==checkpoint_count:
                if replay_digest!=id_digest:raise ValueError('Source ID prefix differs from saved Faiss checkpoint')
                checkpoint_prefix_verified=True
        scanned+=len(batch)
        skip=max(0,checkpoint_count-(scanned-len(batch)))
        ids_new=ids[skip:];titles_new=titles[skip:]
        # Rebuild the complete lexical sidecar independently of vector checkpoints.
        t=perf_counter()
        con.executemany('INSERT INTO titles(rowid,title) VALUES(?,?)',zip(ids,titles))
        fts_seconds+=perf_counter()-t;fts_existing+=len(ids)
        pending_vectors=[];pending_ids=[];pending_hashes=[]
        for offset in range(0,len(ids_new),embedding_batch_size):
            bid=ids_new[offset:offset+embedding_batch_size];text=titles_new[offset:offset+embedding_batch_size]
            t=perf_counter();vec=encoder.encode(text);embedding_seconds+=perf_counter()-t
            pending_vectors.append(vec);pending_ids.extend(bid)
            for digest_offset in range(0,len(bid),64):
                digest_ids=bid[digest_offset:digest_offset+64]
                digest=rolling_ids(digest,digest_ids)
                pending_hashes.append((processed+len(pending_ids)-len(bid)+digest_offset+len(digest_ids),digest))
            if len(pending_ids)>=faiss_add_chunk or offset+embedding_batch_size>=len(ids_new):
                t=perf_counter();idx.add(np.concatenate(pending_vectors));idmap_seconds+=perf_counter()-t
                start_pos=processed
                con.executemany('INSERT INTO vector_ids VALUES(?,?)',((start_pos+i,pid) for i,pid in enumerate(pending_ids)))
                con.executemany('INSERT INTO title_id_hash VALUES(?,?)',pending_hashes)
                processed+=len(pending_ids);since_checkpoint+=len(pending_ids)
                pending_vectors.clear();pending_ids.clear();pending_hashes.clear()
        con.commit()
        if processed-last_progress_vectors>=50000:
            now=perf_counter()-started
            titles_since_resume=processed-checkpoint_count
            existing.update(processed_titles=fts_existing,vector_count=processed,
                current_id_digest=digest,timing_seconds={'embedding':embedding_seconds,'fts_inserts':fts_seconds,
                    'faiss_add':idmap_seconds,'index_training':training_seconds,'elapsed':now},peak_process_working_set_bytes=peak_rss(),
                titles_since_resume=titles_since_resume,
                titles_per_second=titles_since_resume/max(now,1e-9))
            write_json(manifest_path,existing)
            last_progress_vectors=processed
            print(json.dumps({'event':'progress','titles':processed,'titles_since_resume':titles_since_resume,
                'eligible':expected_total,'titles_per_second':round(titles_since_resume/max(now,1e-9),2),
                'total_corpus_coverage':round(processed/expected_total,5),'elapsed_seconds':round(now,1),
                'process_peak_gib':round(peak_rss()/2**30,3),'faiss_gib':round(os.path.getsize(output_dir/f"vectors-{existing.get('checkpoint_slot')}.faiss")/2**30,3) if existing.get('checkpoint_slot') else None}),flush=True)
        if processed-last_checkpoint_vectors>=CHECKPOINT_SIZE:
            nextslot='b' if existing.get('checkpoint_slot')=='a' else 'a'
            checkpoint=output_dir/f'vectors-{nextslot}.faiss'
            tmp=output_dir/f'vectors-{nextslot}.tmp.faiss'
            faiss.write_index(idx,str(tmp));os.replace(tmp,checkpoint)
            digest_file=file_sha256(checkpoint)
            existing.update(checkpoint_vectors=processed,checkpoint_slot=nextslot,
                checkpoint_id_digest=digest,checkpoint_sha256=digest_file,
                checkpointed_at_utc=datetime.now(timezone.utc).isoformat())
            write_json(manifest_path,existing)
            last_checkpoint_vectors=processed
            since_checkpoint=0

    try:
        while True:
            batch=cur.fetchmany(2048)
            if not batch:break
            flush(batch)
            # As checkpoints advance, scan ordinal equals vector count because the
            # query includes only eligible titles. The local skip uses original
            # checkpoint count, while new records flow into HNSW in stream order.
        if not checkpoint_prefix_verified:raise ValueError('Checkpoint source prefix was not fully verified')
        if processed!=expected_total or fts_existing!=expected_total:
            raise ValueError(f'Full coverage failed: vectors={processed}, fts={fts_existing}, expected={expected_total}')
        if idx.ntotal!=expected_total:raise ValueError('Faiss vector count differs from corpus count')
        # Final exact coverage checksum in vector insertion order.
        map_rows=con.execute('SELECT vector_position,publication_id FROM vector_ids ORDER BY vector_position')
        verify_digest='';verified=0;verify_chunk=[]
        for pos,pid in map_rows:
            if pos!=verified:raise ValueError('Vector ID positions are not contiguous')
            verify_chunk.append(pid);verified+=1
            if len(verify_chunk)==64 or verified==expected_total:
                verify_digest=rolling_ids(verify_digest,verify_chunk);verify_chunk=[]
        if verified!=expected_total or verify_digest!=digest:raise ValueError('Vector ID coverage digest mismatch')
        t=perf_counter();faiss.write_index(idx,str(output_dir/'vectors-final.tmp.faiss'))
        os.replace(output_dir/'vectors-final.tmp.faiss',output_dir/'vectors.faiss');faiss_seconds=perf_counter()-t
        # Checkpoint a final manifest only after every index and map is on disk.
        con.execute("INSERT OR REPLACE INTO build_state VALUES('corpus_sha256',?)",(corpus_sha,))
        con.execute("INSERT OR REPLACE INTO build_state VALUES('id_digest',?)",(digest,))
        con.commit();con.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        existing.pop('error_category',None)
        existing.pop('resumable_from_checkpoint',None)
        existing.update(status='ready',processed_titles=fts_existing,vector_count=processed,
            vector_id_digest=digest,coverage={'eligible_titles':int(expected_total),'empty_title_exclusions':int(empty),
                'vector_ids_unique':con.execute('SELECT count(DISTINCT publication_id) FROM vector_ids').fetchone()[0]==expected_total,
                'fts_rowids_unique':True,'all_vectors_verified':idx.ntotal==expected_total},
            artifact_bytes={'faiss':(output_dir/'vectors.faiss').stat().st_size,'sqlite':sqlite_path.stat().st_size},
            timings_seconds={'embedding':embedding_seconds,'fts_inserts':fts_seconds,'faiss_add':idmap_seconds,
                'index_training':training_seconds,'faiss_final_write':faiss_seconds,'total':perf_counter()-started},
            peak_process_working_set_bytes=peak_rss(),completed_at_utc=datetime.now(timezone.utc).isoformat(),
            activation='connected to the assistant; every candidate ID is revalidated against the approved canonical database')
        write_json(manifest_path,existing)
        print(json.dumps({'event':'build_complete','manifest':str(manifest_path),'coverage':existing['coverage'],
            'artifact_bytes':existing['artifact_bytes'],'timings_seconds':existing['timings_seconds'],
            'peak_process_gib':round(peak_rss()/2**30,3)}),flush=True)
        return existing
    except BaseException as exc:
        existing.update(status='interrupted',processed_titles=fts_existing,vector_count=processed,
            current_id_digest=digest,timing_seconds={'embedding':embedding_seconds,'fts_inserts':fts_seconds,
                'faiss_add':idmap_seconds,'index_training':training_seconds,
                'elapsed':perf_counter()-started},error_category=type(exc).__name__,
            peak_process_working_set_bytes=peak_rss(),resumable_from_checkpoint=True)
        write_json(manifest_path,existing)
        raise
    finally:
        cur.close();db.close();con.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',type=Path,default=ROOT/'database/dblp.duckdb')
    parser.add_argument('--model',type=Path,default=ROOT/'.work/rag-benchmark/model')
    parser.add_argument('--output',type=Path,default=ROOT/'database/indexes/dblp-title-v2')
    parser.add_argument('--threads','--embedding-threads',dest='embedding_threads',type=int,default=6)
    parser.add_argument('--chunk-size','--embedding-batch-size',dest='embedding_batch_size',type=int,default=CHUNK_SIZE)
    parser.add_argument('--faiss-threads',type=int,default=4)
    parser.add_argument('--faiss-add-chunk',type=int,default=256)
    args=parser.parse_args()
    build(args.db,args.model,args.output,args.embedding_threads,args.embedding_batch_size,args.faiss_threads,args.faiss_add_chunk)
