"""SQLite log of every signal sent: the raw material for a verifiable track record."""
from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import asdict

from signalbot import config
from signalbot.parse import Signal


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            action TEXT NOT NULL,
            symbol TEXT NOT NULL,
            entry REAL, sl REAL, tps TEXT, note TEXT,
            delivered INTEGER NOT NULL DEFAULT 0
        )"""
    )
    return conn


def is_duplicate(sig: Signal) -> bool:
    cutoff = time.time() - config.DEDUPE_SECONDS
    with _conn() as c:
        row = c.execute(
            "SELECT 1 FROM signals WHERE ts > ? AND action = ? AND symbol = ? AND entry IS ? LIMIT 1",
            (cutoff, sig.action, sig.symbol, sig.entry),
        ).fetchone()
    return row is not None


def log_signal(sig: Signal, delivered: bool) -> int:
    d = asdict(sig)
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO signals (ts, action, symbol, entry, sl, tps, note, delivered) VALUES (?,?,?,?,?,?,?,?)",
            (time.time(), d["action"], d["symbol"], d["entry"], d["sl"], json.dumps(d["tps"]), d["note"], int(delivered)),
        )
        return cur.lastrowid
