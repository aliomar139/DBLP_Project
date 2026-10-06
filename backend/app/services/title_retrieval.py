"""Bounded local hybrid retrieval over the versioned, full-title sidecar.

The sidecar only proposes publication IDs. Every displayed field is reloaded
from the canonical, read-only DuckDB before it leaves this service.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib
import json
import logging
import os
from pathlib import Path
import re
import sqlite3
import sys
from threading import Lock
from threading import Timer
from time import perf_counter
from typing import Any

from ..database import DB_PATH

ROOT = Path(__file__).resolve().parents[3]
SIDECAR_PATH = ROOT / 'database' / 'indexes' / 'dblp-title-v2'
MODEL_PATH = ROOT / '.work' / 'rag-benchmark' / 'model'
DEFAULT_PACKAGES = ROOT / '.work' / 'rag-benchmark' / 'packages'
MAX_QUERY_CHARS = 500
MAX_CANDIDATES_PER_RETRIEVER = 50
MAX_RESULTS = 8
MAX_SEARCH_SECONDS = 8.5
_log = logging.getLogger(__name__)
_load_lock = Lock()
_active_index: 'FullTitleIndex | None' = None


class TitleIndexUnavailable(RuntimeError):
    """The verified local retrieval sidecar is missing or cannot be loaded."""


@dataclass(frozen=True)
class TitleMatch:
    publication_id: int
    title: str
    db_key: str
    year: int | None
    publication_type: str | None
    venue_id: int | None
    retrieval_score: float
    matched_by: tuple[str, ...]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _import_local_runtime() -> tuple[Any, Any, Any, Any, Any]:
    packages = Path(os.environ.get('DBLP_RETRIEVAL_PACKAGES', str(DEFAULT_PACKAGES))).resolve()
    if not packages.is_dir():
        raise TitleIndexUnavailable('Local retrieval dependencies are not installed')
    if str(packages) not in sys.path:
        sys.path.insert(0, str(packages))
    try:
        faiss = importlib.import_module('faiss')
        np = importlib.import_module('numpy')
        ort = importlib.import_module('onnxruntime')
        tokenizer_module = importlib.import_module('tokenizers')
    except Exception as exc:
        raise TitleIndexUnavailable('Local retrieval dependencies could not be loaded') from exc
    if not hasattr(faiss, 'read_index'):
        raise TitleIndexUnavailable('The local Faiss installation is incomplete')
    return faiss, np, ort, tokenizer_module.Tokenizer, None


class _Encoder:
    def __init__(self, np: Any, ort: Any, tokenizer_type: Any):
        model_manifest = json.loads((MODEL_PATH / 'manifest.json').read_text(encoding='utf-8'))
        for relative, expected in model_manifest.get('sha256', {}).items():
            file_path = MODEL_PATH / relative
            if not file_path.is_file() or _sha256(file_path) != expected:
                raise TitleIndexUnavailable('A local embedding model file failed its checksum')
        self.np = np
        self.tokenizer = tokenizer_type.from_file(str(MODEL_PATH / 'tokenizer.json'))
        self.tokenizer.enable_truncation(max_length=256)
        self.tokenizer.enable_padding(pad_id=0, pad_token='[PAD]')
        options = ort.SessionOptions()
        options.intra_op_num_threads = min(6, max(1, os.cpu_count() or 1))
        options.inter_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        os.environ.setdefault('HF_HUB_OFFLINE', '1')
        os.environ.setdefault('HF_HUB_DISABLE_TELEMETRY', '1')
        os.environ.setdefault('TOKENIZERS_PARALLELISM', 'false')
        self.session = ort.InferenceSession(
            str(MODEL_PATH / 'onnx' / 'model_quint8_avx2.onnx'),
            sess_options=options, providers=['CPUExecutionProvider'])
        self.input_names = {item.name for item in self.session.get_inputs()}

    def encode(self, text: str):
        tokens = self.tokenizer.encode(text)
        data = {
            'input_ids': self.np.asarray([tokens.ids], dtype=self.np.int64),
            'attention_mask': self.np.asarray([tokens.attention_mask], dtype=self.np.int64),
            'token_type_ids': self.np.asarray([tokens.type_ids], dtype=self.np.int64),
        }
        output = self.session.run(None, {k: v for k, v in data.items() if k in self.input_names})[0]
        mask = data['attention_mask'][..., None].astype(self.np.float32)
        pooled = (output * mask).sum(axis=1) / mask.sum(axis=1).clip(min=1)
        pooled /= self.np.linalg.norm(pooled, axis=1, keepdims=True).clip(min=1e-9)
        return self.np.ascontiguousarray(pooled, dtype=self.np.float32)


def _lexical_terms(query: str) -> list[str]:
    stop = {'a', 'an', 'and', 'are', 'for', 'from', 'in', 'of', 'on', 'or',
            'papers', 'paper', 'research', 'the', 'to', 'with', 'about'}
    return [token for token in dict.fromkeys(re.findall(r'[a-z0-9]+', query.casefold()))
            if len(token) > 1 and token not in stop][:24]


class FullTitleIndex:
    """One-process, read-only handle for the approved full-corpus index."""

    def __init__(self):
        self.faiss, self.np, ort, tokenizer_type, _ = _import_local_runtime()
        self.manifest = json.loads((SIDECAR_PATH / 'manifest.json').read_text(encoding='utf-8'))
        source = json.loads((ROOT / 'database' / 'active-source-v2.json').read_text(encoding='utf-8'))
        database = Path(os.environ.get('DBLP_DB_PATH', str(DB_PATH))).resolve()
        if database != DB_PATH.resolve():
            raise TitleIndexUnavailable('The title index is only approved for the canonical DBLP database')
        if source.get('database') != 'database/dblp.duckdb' or self.manifest.get('status') != 'ready':
            raise TitleIndexUnavailable('The canonical DBLP source or title index is not approved')
        if (self.manifest.get('corpus_sha256') != source.get('sha256') or
                self.manifest.get('expected_eligible_titles') != 8_738_331 or
                self.manifest.get('empty_title_exclusions') != 0):
            raise TitleIndexUnavailable('The full-title index does not match the approved corpus record')
        if database.stat().st_size != source.get('bytes'):
            raise TitleIndexUnavailable('The canonical DBLP database has changed since index review')
        # Verify the actual corpus once per process. Subsequent queries use the
        # database/index stat token in the answer cache and revalidate every ID.
        started = perf_counter()
        if _sha256(database) != self.manifest['corpus_sha256']:
            raise TitleIndexUnavailable('The active database fingerprint differs from the title index')
        index = self.faiss.read_index(str(SIDECAR_PATH / 'vectors.faiss'))
        if index.ntotal != self.manifest['expected_eligible_titles']:
            raise TitleIndexUnavailable('The Faiss vector count differs from the full-title manifest')
        index.hnsw.efSearch = 64
        self.index = index
        self._encoder = _Encoder(self.np, ort, tokenizer_type)
        map_path = SIDECAR_PATH / 'keyword-map.sqlite'
        self._sqlite_uri = map_path.as_uri() + '?mode=ro&immutable=1'
        with sqlite3.connect(self._sqlite_uri, uri=True) as db:
            counts = db.execute('SELECT (SELECT count(*) FROM vector_ids), (SELECT count(*) FROM titles)').fetchone()
        expected = self.manifest['expected_eligible_titles']
        if counts != (expected, expected):
            raise TitleIndexUnavailable('Keyword and vector-ID coverage differs from the full-title manifest')
        self._search_lock = Lock()
        self._db_lock = Lock()
        import duckdb
        try:
            self._db = duckdb.connect(str(database), read_only=True)
        except Exception as exc:
            raise TitleIndexUnavailable('The canonical database could not be opened read-only') from exc
        _log.info('Title retrieval ready index=%s init_ms=%.1f vectors=%d',
                  self.manifest['corpus_id'], (perf_counter() - started) * 1000, expected)

    def search(self, query: str, limit: int = MAX_RESULTS) -> list[TitleMatch]:
        query = query.strip()
        if not 2 <= len(query) <= MAX_QUERY_CHARS:
            raise ValueError('Title retrieval question length is outside the supported range')
        limit = min(MAX_RESULTS, max(1, int(limit)))
        started = perf_counter()
        deadline = started + MAX_SEARCH_SECONDS
        encode_seconds = faiss_seconds = map_seconds = keyword_seconds = database_seconds = 0.0
        lexical_ids: list[int] = []
        semantic_ids: list[int] = []
        semantic_scores: dict[int, float] = {}
        with self._search_lock:
            stage_started = perf_counter()
            q_vector = self._encoder.encode(query)
            encode_seconds = perf_counter() - stage_started
            stage_started = perf_counter()
            scores, positions = self.index.search(q_vector, MAX_CANDIDATES_PER_RETRIEVER)
            faiss_seconds = perf_counter() - stage_started
            valid_positions = [int(pos) for pos in positions[0] if int(pos) >= 0]
            if valid_positions:
                slots = ','.join('?' for _ in valid_positions)
                stage_started = perf_counter()
                with sqlite3.connect(self._sqlite_uri, uri=True) as sidecar:
                    sidecar.set_progress_handler(lambda: int(perf_counter() >= deadline), 1000)
                    position_rows = sidecar.execute(
                        f'SELECT vector_position,publication_id FROM vector_ids '
                        f'WHERE vector_position IN ({slots})', valid_positions).fetchall()
                map_seconds = perf_counter() - stage_started
            else:
                position_rows = []
            position_to_id = {int(pos): int(pid) for pos, pid in position_rows}
            for score, pos in zip(scores[0], positions[0]):
                pid = position_to_id.get(int(pos))
                if pid is not None:
                    semantic_ids.append(pid)
                    semantic_scores[pid] = float(score)
            terms = _lexical_terms(query)
            expression = ' OR '.join('"' + term.replace('"', '') + '"' for term in terms)
            if expression:
                stage_started = perf_counter()
                with sqlite3.connect(self._sqlite_uri, uri=True) as sidecar:
                    sidecar.set_progress_handler(lambda: int(perf_counter() >= deadline), 1000)
                    rows = sidecar.execute(
                        'SELECT rowid FROM titles WHERE titles MATCH ? ORDER BY rank LIMIT ?',
                        (expression, MAX_CANDIDATES_PER_RETRIEVER)).fetchall()
                lexical_ids = [int(row[0]) for row in rows]
                keyword_seconds = perf_counter() - stage_started

        # Reciprocal-rank fusion combines only bounded lexical and semantic lists.
        fused: dict[int, float] = {}
        methods: dict[int, set[str]] = {}
        for mode, ids in (('semantic', semantic_ids), ('keyword', lexical_ids)):
            for rank, pid in enumerate(ids, 1):
                fused[pid] = fused.get(pid, 0.0) + 1.0 / (60 + rank)
                methods.setdefault(pid, set()).add(mode)
        candidate_ids = sorted(fused, key=lambda pid: (-fused[pid], -semantic_scores.get(pid, 0.0), pid))
        candidate_ids = candidate_ids[:MAX_CANDIDATES_PER_RETRIEVER * 2]
        if not candidate_ids:
            _log.info('Title retrieval complete elapsed_ms=%.1f semantic=0 keyword=0 returned=0',
                      (perf_counter() - started) * 1000)
            return []

        # Sidecar values are never treated as evidence. Re-fetch and validate all
        # candidate records against the active DuckDB before constructing results.
        placeholders = ','.join('?' for _ in candidate_ids)
        try:
            stage_started = perf_counter()
            with self._db_lock:
                remaining = deadline - perf_counter()
                if remaining <= 0:
                    raise TitleIndexUnavailable('The bounded local title search exceeded its time limit')
                timer = Timer(remaining, self._db.interrupt)
                timer.daemon = True
                timer.start()
                try:
                    rows = self._db.execute(
                        'SELECT publication_id,db_key,title,year,type,venue_id FROM publications '
                        f'WHERE publication_id IN ({placeholders}) '
                        'AND title IS NOT NULL AND length(trim(title))>0', candidate_ids).fetchall()
                finally:
                    timer.cancel()
                    timer.join()
            database_seconds = perf_counter() - stage_started
        except Exception as exc:
            raise TitleIndexUnavailable('The canonical database could not validate search results') from exc
        record_map = {int(row[0]): row for row in rows}
        results = []
        for pid in candidate_ids:
            row = record_map.get(pid)
            if row is None or not row[1] or not row[2]:
                continue
            results.append(TitleMatch(
                publication_id=pid, db_key=str(row[1]), title=str(row[2]),
                year=int(row[3]) if row[3] is not None else None,
                publication_type=str(row[4]) if row[4] is not None else None,
                venue_id=int(row[5]) if row[5] is not None else None,
                retrieval_score=fused[pid], matched_by=tuple(sorted(methods[pid])),
            ))
            if len(results) >= limit:
                break
        _log.info('Title retrieval complete elapsed_ms=%.1f encode_ms=%.1f faiss_ms=%.1f '
                  'idmap_ms=%.1f keyword_ms=%.1f validate_ms=%.1f semantic=%d keyword=%d '
                  'validated=%d returned=%d',
                  (perf_counter() - started) * 1000, encode_seconds * 1000,
                  faiss_seconds * 1000, map_seconds * 1000, keyword_seconds * 1000,
                  database_seconds * 1000, len(semantic_ids), len(lexical_ids),
                  len(record_map), len(results))
        self.last_timings = {
            'encode_ms': encode_seconds * 1000, 'faiss_ms': faiss_seconds * 1000,
            'idmap_ms': map_seconds * 1000, 'keyword_ms': keyword_seconds * 1000,
            'active_database_validation_ms': database_seconds * 1000,
            'total_ms': (perf_counter() - started) * 1000,
        }
        return results

    def close(self) -> None:
        self._db.close()


def get_full_title_index() -> FullTitleIndex:
    global _active_index
    if _active_index is None:
        with _load_lock:
            if _active_index is None:
                try:
                    _active_index = FullTitleIndex()
                except TitleIndexUnavailable:
                    raise
                except Exception as exc:
                    raise TitleIndexUnavailable('The full-title retrieval service could not start') from exc
    return _active_index


def search_titles(query: str, limit: int = MAX_RESULTS) -> list[TitleMatch]:
    return get_full_title_index().search(query, limit)


def close_full_title_index() -> None:
    global _active_index
    with _load_lock:
        if _active_index is not None:
            _active_index.close()
            _active_index = None
