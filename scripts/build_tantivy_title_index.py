"""Build Tantivy after build_full_title_index.py completes for the active corpus."""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import shutil
import sqlite3
import sys
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--sidecar', type=Path, default=ROOT / 'database/indexes/dblp-title-v2')
    ap.add_argument('--package-dir', type=Path, default=ROOT / '.work/rag-benchmark/packages')
    ap.add_argument('--threads', type=int, default=4)
    ap.add_argument('--replace', action='store_true', help='Replace the existing Tantivy keyword index after a successful build.')
    args = ap.parse_args()
    if args.threads < 1:
        ap.error('--threads must be positive')
    sys.path.insert(0, str(args.package_dir))
    import tantivy

    source_manifest_path = args.sidecar / 'manifest.json'
    source_manifest = json.loads(source_manifest_path.read_text(encoding='utf-8'))
    if source_manifest.get('status') != 'ready':
        raise SystemExit('The source title sidecar is not marked ready.')
    expected = int(source_manifest['expected_eligible_titles'])
    sqlite_path = args.sidecar / 'keyword-map.sqlite'
    final_path = args.sidecar / 'keyword-tantivy'
    building_path = args.sidecar / 'keyword-tantivy.building'
    if final_path.exists() and not args.replace:
        raise SystemExit(f'{final_path} already exists; pass --replace to rebuild it.')
    started = perf_counter()
    index = None
    writer = None
    if building_path.exists() and (building_path / 'meta.json').is_file():
        try:
            index = tantivy.Index.open(str(building_path))
            if index.searcher().num_docs != expected:
                index = None
        except Exception:
            index = None
    if index is None:
        if building_path.exists():
            shutil.rmtree(building_path)
        building_path.mkdir(parents=True)
        schema_builder = tantivy.SchemaBuilder()
        schema_builder.add_text_field('title', stored=False)
        schema_builder.add_integer_field('publication_id', stored=True, indexed=False)
        index = tantivy.Index(schema_builder.build(), path=str(building_path))
        writer = index.writer(heap_size=256_000_000, num_threads=args.threads)
        db = sqlite3.connect(f'file:{sqlite_path.resolve().as_posix()}?mode=ro&immutable=1', uri=True)
        count = 0
        try:
            cursor = db.execute('SELECT rowid,title FROM titles ORDER BY rowid')
            while rows := cursor.fetchmany(5000):
                for publication_id, title in rows:
                    writer.add_document(tantivy.Document(
                        title=[title], publication_id=int(publication_id)))
                count += len(rows)
                if count % 500_000 == 0:
                    print(f'indexed {count:,} titles', flush=True)
            if count != expected:
                raise RuntimeError(f'Indexed {count:,} titles; expected {expected:,}.')
            writer.commit()
            writer.wait_merging_threads()
        finally:
            db.close()
        index.reload()
    if index.searcher().num_docs != expected:
        raise RuntimeError('The built Tantivy index does not cover the expected title count.')
    metadata = {
        'format_version': 1,
        'engine': 'tantivy',
        'tantivy_version': getattr(tantivy, '__version__', 'unknown'),
        'source_corpus_sha256': source_manifest['corpus_sha256'],
        'source_manifest_sha256': sha256(source_manifest_path),
        'expected_titles': expected,
        'schema': {'title': 'default-tokenized text', 'publication_id': 'stored integer'},
        'build_seconds': round(perf_counter() - started, 3),
    }
    (building_path / 'manifest.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
    del index, writer
    gc.collect()
    if final_path.exists():
        shutil.rmtree(final_path)
    building_path.rename(final_path)
    print(json.dumps(metadata, indent=2), flush=True)


if __name__ == '__main__':
    main()
