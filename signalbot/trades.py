"""Trade book: open on buy/sell, close on exit, compute points and R for the track record."""
from __future__ import annotations

import json
import time

from signalbot.db import db
from signalbot.parse import Signal


def open_trade(sig: Signal) -> int | None:
    """Record a new open trade. Needs an entry price to be trackable."""
    if sig.action not in ("buy", "sell") or sig.entry is None:
        return None
    with db() as c:
        cur = c.execute(
            "INSERT INTO trades (symbol, side, entry, sl, tps, opened_ts) VALUES (?,?,?,?,?,?)",
            (sig.symbol, sig.action, sig.entry, sig.sl, json.dumps(sig.tps), time.time()),
        )
        return cur.lastrowid


def open_trade_for(symbol: str) -> dict | None:
    with db() as c:
        row = c.execute(
            "SELECT * FROM trades WHERE symbol = ? AND closed_ts IS NULL ORDER BY id DESC LIMIT 1", (symbol,)
        ).fetchone()
    if row is None:
        return None
    trade = dict(row)
    trade["tps"] = json.loads(trade["tps"] or "[]")
    return trade


def compute_result(trade: dict, exit_price: float | None) -> dict:
    """Points, R and outcome for exiting `trade` at `exit_price` (no database access)."""
    if exit_price is None:
        return {"exit_price": None, "points": None, "r": None, "outcome": "unknown"}
    points = exit_price - trade["entry"] if trade["side"] == "buy" else trade["entry"] - exit_price
    risk = abs(trade["entry"] - trade["sl"]) if trade["sl"] is not None else 0
    outcome = "win" if points > 1e-9 else "loss" if points < -1e-9 else "be"
    return {"exit_price": exit_price, "points": points, "r": points / risk if risk else None, "outcome": outcome}


def close_trade(trade_id: int, exit_price: float | None) -> dict:
    """Close a trade. With no exit price the trade is closed but excluded from statistics."""
    with db() as c:
        t = dict(c.execute("SELECT * FROM trades WHERE id = ?", (trade_id,)).fetchone())
        res = compute_result(t, exit_price)
        c.execute(
            "UPDATE trades SET closed_ts=?, exit_price=?, points=?, r=?, outcome=? WHERE id=?",
            (time.time(), res["exit_price"], res["points"], res["r"], res["outcome"], trade_id),
        )
    t.update(res, closed_ts=time.time())
    t["tps"] = json.loads(t["tps"] or "[]")
    return t


def open_trades() -> list[dict]:
    with db() as c:
        rows = c.execute("SELECT * FROM trades WHERE closed_ts IS NULL ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def closed_trades(since_ts: float | None = None) -> list[dict]:
    with db() as c:
        rows = c.execute(
            "SELECT * FROM trades WHERE closed_ts IS NOT NULL AND outcome != 'unknown' AND closed_ts >= ? ORDER BY closed_ts",
            (since_ts or 0,),
        ).fetchall()
    return [dict(r) for r in rows]


def stats(since_ts: float | None = None) -> dict:
    rows = closed_trades(since_ts)
    wins = sum(r["outcome"] == "win" for r in rows)
    losses = sum(r["outcome"] == "loss" for r in rows)
    per_symbol: dict[str, dict] = {}
    for r in rows:
        s = per_symbol.setdefault(r["symbol"], {"n": 0, "points": 0.0})
        s["n"] += 1
        s["points"] += r["points"]
    return {
        "n": len(rows),
        "wins": wins,
        "losses": losses,
        "be": len(rows) - wins - losses,
        "win_rate": wins / (wins + losses) if wins + losses else None,
        "points": sum(r["points"] for r in rows),
        "r": sum(r["r"] for r in rows if r["r"] is not None),
        "per_symbol": per_symbol,
    }
