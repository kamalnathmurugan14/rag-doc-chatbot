"""Plain sqlite3 (no ORM). One short-lived connection per operation."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS files(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  rel_path TEXT UNIQUE NOT NULL,
  sha256 TEXT NOT NULL,
  mtime REAL NOT NULL,
  n_chunks INTEGER NOT NULL DEFAULT 0,
  indexed_at TEXT,
  status TEXT NOT NULL DEFAULT 'pending',   -- pending | indexed | no_text | error
  error TEXT
);
CREATE TABLE IF NOT EXISTS chat_sessions(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  created_at TEXT NOT NULL,
  scope_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS messages(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK(role IN ('user','assistant')),
  content TEXT NOT NULL,
  citations_json TEXT,
  debug_json TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS eval_sets(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  items_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS eval_runs(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  params_json TEXT NOT NULL,
  hit_rate REAL, mrr REAL, avg_faithfulness REAL, avg_answer_score REAL,
  details_json TEXT,
  status TEXT NOT NULL DEFAULT 'running',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
"""


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with connect(db_path) as con:
        con.executescript(SCHEMA)


@contextmanager
def connect(db_path: Path) -> Iterator[sqlite3.Connection]:
    con = sqlite3.connect(db_path, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    try:
        yield con
        con.commit()
    finally:
        con.close()
