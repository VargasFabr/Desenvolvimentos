from contextlib import contextmanager
from typing import Any, Iterator

import psycopg2
from psycopg2.extras import RealDictCursor

from app.config import get_settings


@contextmanager
def get_conn() -> Iterator[Any]:
    conn = psycopg2.connect(get_settings().dsn)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def get_cursor(dict_rows: bool = True) -> Iterator[Any]:
    with get_conn() as conn:
        factory = RealDictCursor if dict_rows else None
        with conn.cursor(cursor_factory=factory) as cur:
            yield conn, cur
