"""SQLite persistence for lab-as-service MVP."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "portal.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS labs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  student_name TEXT NOT NULL,
  student_email TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'requested',
  -- requested | approved | provisioning | ready | stopped | destroyed
  tenant_slug TEXT UNIQUE,
  vmid_base INTEGER,
  trust_cidr TEXT,
  client_ip TEXT,
  pa_ip TEXT,
  tailscale_auth_key TEXT,
  tailscale_notes TEXT,
  homepage_token TEXT,
  admin_notes TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  destroyed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_labs_status ON labs(status);
CREATE INDEX IF NOT EXISTS idx_labs_email ON labs(student_email);
"""


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.executescript(SCHEMA)


@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row else None
