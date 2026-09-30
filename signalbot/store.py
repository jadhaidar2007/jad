"""SQLite log of every signal sent, plus duplicate detection."""
from __future__ import annotations

import json
import time
from dataclasses import asdict

from signalbot import config
from signalbot.db import db
from signalbot.parse import Signal


def is_duplicate(sig: Signal) -> bool:
    cutoff = time.time() - config.DEDUPE_SECONDS
    with db() as c:
        row = c.execute(
            "SELECT 1 FROM signals WHERE ts > ? AND action = ? AND symbol = ? AND entry IS ? LIMIT 1",
            (cutoff, sig.action, sig.symbol, sig.entry),
        ).fetchone()
    return row is not None


def log_signal(sig: Signal, delivered: bool) -> int:
    d = asdict(sig)
    with db() as c:
        cur = c.execute(
            "INSERT INTO signals (ts, action, symbol, entry, sl, tps, note, delivered) VALUES (?,?,?,?,?,?,?,?)",
            (time.time(), d["action"], d["symbol"], d["entry"], d["sl"], json.dumps(d["tps"]), d["note"], int(delivered)),
        )
        return cur.lastrowid
