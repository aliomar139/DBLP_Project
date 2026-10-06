"""Read-only query boundary with bounded caching and execution time."""
from collections import OrderedDict
from contextlib import closing
from threading import RLock, Timer
from time import monotonic
from typing import Any

from ..database import get_connection

_cache: OrderedDict = OrderedDict()
_lock = RLock()
CACHE_SECONDS = 600
MAX_ENTRIES = 128


def clear_cache():
    with _lock:
        _cache.clear()


def query(sql: str, params: tuple[Any, ...] = ()) -> list[dict]:
    # SQL is developer-owned; values must always be bound parameters.
    if not sql.lstrip().upper().startswith(("SELECT", "WITH")):
        raise ValueError("Only analytical SELECT queries are permitted")
    key = (sql, params)
    # Cache bookkeeping stays short so read-only requests do not queue behind one query.
    with _lock:
        hit = _cache.get(key)
        if hit and monotonic() - hit[0] < CACHE_SECONDS:
            _cache.move_to_end(key)
            return hit[1]
        if hit:
            del _cache[key]

    # Keep the cache lock out of the database call. DuckDB opens read-only
    # connections per request, so unrelated analytical queries can run together.
    with closing(get_connection()) as db:
        timer = Timer(45, db.interrupt)
        timer.daemon = True
        timer.start()
        try:
            result = db.execute(sql, params)
            names = [col[0] for col in result.description]
            rows = [dict(zip(names, row)) for row in result.fetchall()]
        finally:
            timer.cancel()
            timer.join()

    with _lock:
        _cache[key] = (monotonic(), rows)
        _cache.move_to_end(key)
        while len(_cache) > MAX_ENTRIES:
            _cache.popitem(last=False)
    return rows
