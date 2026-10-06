"""Post-time queue: give each clip the next free US prime-time slot."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from clipengine import config

DB = config.BASE_DIR / "schedule.db"
MIN_LEAD = timedelta(minutes=10)
MAX_ATTEMPTS = 3


def _con() -> sqlite3.Connection:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.execute(
        """CREATE TABLE IF NOT EXISTS queue(
            id INTEGER PRIMARY KEY, file_path TEXT NOT NULL, title TEXT NOT NULL, caption TEXT NOT NULL,
            scheduled_utc TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
            attempts INTEGER NOT NULL DEFAULT 0, posted_to TEXT NOT NULL DEFAULT '', error TEXT NOT NULL DEFAULT '')"""
    )
    return con


def _parse_slots() -> list[tuple[int, int]]:
    slots = []
    for s in config.POST_SLOTS.split(","):
        h, m = s.strip().split(":")
        slots.append((int(h), int(m)))
    return sorted(slots)


def candidate_slots(now_utc: datetime, days: int = 60) -> list[datetime]:
    """Upcoming slot times (UTC) in the configured timezone, DST-correct, soonest first."""
    tz = ZoneInfo(config.POST_TIMEZONE)
    start_date = now_utc.astimezone(tz).date()
    out = []
    for d in range(days):
        day = start_date + timedelta(days=d)
        for h, m in _parse_slots():
            local = datetime(day.year, day.month, day.day, h, m, tzinfo=tz)
            utc = local.astimezone(timezone.utc)
            if utc >= now_utc + MIN_LEAD:
                out.append(utc)
    return sorted(out)


def enqueue(file_path: str, title: str, caption: str, now_utc: datetime | None = None) -> datetime:
    now_utc = now_utc or datetime.now(timezone.utc)
    with _con() as con:
        taken = {
            datetime.fromisoformat(r["scheduled_utc"])
            for r in con.execute("SELECT scheduled_utc FROM queue WHERE status = 'pending'")
        }
        slot = next(s for s in candidate_slots(now_utc) if s not in taken)
        con.execute(
            "INSERT INTO queue(file_path, title, caption, scheduled_utc) VALUES (?,?,?,?)",
            (file_path, title, caption, slot.isoformat()),
        )
    return slot


def due(now_utc: datetime | None = None) -> list[sqlite3.Row]:
    now_utc = now_utc or datetime.now(timezone.utc)
    with _con() as con:
        rows = con.execute("SELECT * FROM queue WHERE status = 'pending' ORDER BY scheduled_utc").fetchall()
    return [r for r in rows if datetime.fromisoformat(r["scheduled_utc"]) <= now_utc]


def mark_posted(item_id: int, posted_to: list[str]) -> None:
    with _con() as con:
        con.execute("UPDATE queue SET status='posted', posted_to=? WHERE id=?", (",".join(posted_to), item_id))


def mark_failed(item_id: int, error: str, now_utc: datetime | None = None) -> None:
    """Retry in 5 minutes, up to MAX_ATTEMPTS, then give up."""
    now_utc = now_utc or datetime.now(timezone.utc)
    with _con() as con:
        attempts = con.execute("SELECT attempts FROM queue WHERE id=?", (item_id,)).fetchone()["attempts"] + 1
        if attempts >= MAX_ATTEMPTS:
            con.execute("UPDATE queue SET status='failed', attempts=?, error=? WHERE id=?", (attempts, error, item_id))
        else:
            retry = (now_utc + timedelta(minutes=5)).isoformat()
            con.execute(
                "UPDATE queue SET attempts=?, error=?, scheduled_utc=? WHERE id=?", (attempts, error, retry, item_id)
            )


def all_items() -> list[sqlite3.Row]:
    with _con() as con:
        return con.execute("SELECT * FROM queue ORDER BY scheduled_utc").fetchall()
