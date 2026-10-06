"""Independently verify full sidecar IDs and FTS titles against the source DB."""
import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from time import perf_counter

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.work/rag-benchmark/packages'))
import duckdb
import faiss

def verify(db_path: Path, sidecar: Path):
    started=perf_counter(); manifest=json.loads((sidecar/'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('status')!='ready': raise ValueError('Sidecar is not ready')
    h=hashlib.sha256()
    with db_path.open('rb') as source:
        for block in iter(lambda: source.read(8*1024*1024),b''): h.update(block)
    if h.hexdigest()!=manifest['corpus_sha256']:
        raise ValueError('Database fingerprint differs from sidecar')
    idx=faiss.read_index(str(sidecar/'vectors.faiss'))
    con=sqlite3.connect(sidecar/'keyword-map.sqlite'); db=duckdb.connect(str(db_path),read_only=True)
    try:
        expected,empty=db.execute("SELECT count(*) FILTER(WHERE title IS NOT NULL AND length(trim(title))>0), count(*) FILTER(WHERE title IS NULL OR length(trim(title))=0) FROM publications").fetchone()
        fts=con.execute('SELECT count(*) FROM titles').fetchone()[0]
        mapped=con.execute('SELECT count(*) FROM vector_ids').fetchone()[0]
        if (expected,empty)!=(manifest['expected_eligible_titles'],manifest['empty_title_exclusions']): raise ValueError('Corpus title counts differ from manifest')
        if idx.ntotal!=expected or mapped!=expected or fts!=expected: raise ValueError('Sidecar component counts differ from eligible titles')
        if con.execute('SELECT count(DISTINCT publication_id) FROM vector_ids').fetchone()[0]!=expected: raise ValueError('Duplicate or missing publication IDs in map')
        if con.execute('SELECT min(vector_position),max(vector_position) FROM vector_ids').fetchone()!=(0,expected-1): raise ValueError('Vector positions are not contiguous')
        con.execute('CREATE TEMP TABLE source_batch(publication_id INTEGER PRIMARY KEY,title TEXT)')
        cur=db.execute('SELECT publication_id,title FROM publications WHERE title IS NOT NULL AND length(trim(title))>0 ORDER BY publication_id')
        digest=''; verified=0; mismatches=0; batch_size=2048
        while True:
            batch=cur.fetchmany(batch_size)
            if not batch: break
            ids=[int(r[0]) for r in batch]
            rows=con.execute('SELECT publication_id FROM vector_ids WHERE vector_position>=? AND vector_position<? ORDER BY vector_position',(verified,verified+len(batch))).fetchall()
            if [int(r[0]) for r in rows]!=ids: raise ValueError(f'ID coverage/order mismatch at vector position {verified}')
            np=__import__('numpy')
            for off in range(0,len(ids),64):
                rolling=hashlib.sha256();rolling.update(bytes.fromhex(digest) if digest else b'')
                rolling.update(np.asarray(ids[off:off+64],dtype='<i8').tobytes());digest=rolling.hexdigest()
            con.execute('DELETE FROM source_batch')
            con.executemany('INSERT INTO source_batch VALUES(?,?)',((int(pid),str(title)) for pid,title in batch))
            bad=con.execute('SELECT count(*) FROM source_batch b LEFT JOIN titles t ON t.rowid=b.publication_id WHERE t.rowid IS NULL OR t.title!=b.title').fetchone()[0]
            mismatches+=bad
            if bad: raise ValueError(f'FTS title mismatch in source batch at vector position {verified}')
            verified+=len(batch)
        if verified!=expected: raise ValueError('Source scan count differs from sidecar')
        if digest!=manifest.get('vector_id_digest'): raise ValueError('Vector ID digest differs from sidecar')
        return {'status':'passed','database_sha256':manifest['corpus_sha256'],'eligible_titles':expected,'empty_title_exclusions':empty,
            'faiss_vectors':idx.ntotal,'vector_id_rows':mapped,'fts_title_rows':fts,'source_ids_exact_order':True,
            'fts_titles_exact':mismatches==0,'id_sha256':digest,'verification_seconds':perf_counter()-started}
    finally: db.close();con.close()

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--db',type=Path,default=ROOT/'database/dblp.duckdb');ap.add_argument('--sidecar',type=Path,default=ROOT/'database/indexes/dblp-title-v2')
    a=ap.parse_args();result=verify(a.db,a.sidecar);print(json.dumps(result,indent=2))
