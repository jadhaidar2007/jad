"""SQLite connection + schema shared by every module."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager

from signalbot import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    action TEXT NOT NULL,
    symbol TEXT NOT NULL,
    entry REAL, sl REAL, tps TEXT, note TEXT,
    delivered INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    entry REAL NOT NULL,
    sl REAL,
    tps TEXT,
    opened_ts REAL NOT NULL,
    closed_ts REAL,
    exit_price REAL,
    points REAL,
    r REAL,
    outcome TEXT
);
CREATE TABLE IF NOT EXISTS members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stripe_session_id TEXT UNIQUE NOT NULL,
    stripe_subscription_id TEXT NOT NULL,
    stripe_customer_id TEXT,
    email TEXT,
    invite_link TEXT,
    telegram_user_id INTEGER,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending | active | revoked
    created_ts REAL NOT NULL,
    joined_ts REAL,
    revoked_ts REAL
);
CREATE TABLE IF NOT EXISTS pending (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id TEXT NOT NULL,
    kind TEXT NOT NULL,  -- signal | say
    text TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    created_ts REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'  -- pending | done | cancelled | expired
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


@contextmanager
def db():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
