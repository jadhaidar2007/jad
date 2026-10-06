"""Track clipping campaigns, posted clips, views and payouts (local SQLite).

    python earnings.py campaign add "Streamer X" --rate 1.5 --cap 100
    python earnings.py clip add "Streamer X" https://tiktok.com/@me/video/123 --views 4200
    python earnings.py clip views 1 15800
    python earnings.py paid "Streamer X" 12.50
    python earnings.py report

Estimated earnings per clip = min(views / 1000 * rate, cap). Rate and cap come from
the campaign page; check how it counts "valid" views and enter those if they differ.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

DB = Path(__file__).resolve().parent / "earnings.db"


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB)
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS campaigns(
            id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL,
            rate_per_1k REAL NOT NULL, cap_per_clip REAL);
        CREATE TABLE IF NOT EXISTS clips(
            id INTEGER PRIMARY KEY, campaign_id INTEGER NOT NULL REFERENCES campaigns(id),
            url TEXT NOT NULL, views INTEGER NOT NULL DEFAULT 0,
            posted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS payouts(
            id INTEGER PRIMARY KEY, campaign_id INTEGER NOT NULL REFERENCES campaigns(id),
            amount REAL NOT NULL, received_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        """
    )
    return con


def campaign_id(con: sqlite3.Connection, name: str) -> int:
    row = con.execute("SELECT id FROM campaigns WHERE name = ?", (name,)).fetchone()
    if not row:
        sys.exit(f"No campaign named '{name}'. Add it first: campaign add \"{name}\" --rate X")
    return row[0]


def clip_earnings(views: int, rate: float, cap: float | None) -> float:
    amount = views / 1000 * rate
    return min(amount, cap) if cap is not None else amount


def report(con: sqlite3.Connection) -> None:
    camps = con.execute("SELECT id, name, rate_per_1k, cap_per_clip FROM campaigns").fetchall()
    if not camps:
        print("No campaigns yet.")
        return
    tot_est = tot_paid = tot_views = tot_clips = 0
    print(f"{'Campaign':<24}{'Clips':>6}{'Views':>10}{'Est. $':>10}{'Paid $':>10}{'$/clip':>9}")
    for cid, name, rate, cap in camps:
        views = [v for (v,) in con.execute("SELECT views FROM clips WHERE campaign_id = ?", (cid,))]
        est = sum(clip_earnings(v, rate, cap) for v in views)
        paid = con.execute("SELECT COALESCE(SUM(amount),0) FROM payouts WHERE campaign_id = ?", (cid,)).fetchone()[0]
        per = est / len(views) if views else 0
        print(f"{name[:23]:<24}{len(views):>6}{sum(views):>10}{est:>10.2f}{paid:>10.2f}{per:>9.2f}")
        tot_est += est; tot_paid += paid; tot_views += sum(views); tot_clips += len(views)
    print(f"{'TOTAL':<24}{tot_clips:>6}{tot_views:>10}{tot_est:>10.2f}{tot_paid:>10.2f}")
    print(f"\nOwed but not yet received (estimate): ${max(tot_est - tot_paid, 0):.2f}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("campaign").add_subparsers(dest="action", required=True).add_parser("add")
    c.add_argument("name"); c.add_argument("--rate", type=float, required=True, help="$ per 1,000 views")
    c.add_argument("--cap", type=float, default=None, help="max $ per clip")

    cl = sub.add_parser("clip").add_subparsers(dest="action", required=True)
    a = cl.add_parser("add"); a.add_argument("campaign"); a.add_argument("url"); a.add_argument("--views", type=int, default=0)
    v = cl.add_parser("views"); v.add_argument("id", type=int); v.add_argument("views", type=int)

    p = sub.add_parser("paid"); p.add_argument("campaign"); p.add_argument("amount", type=float)
    sub.add_parser("report")

    args = ap.parse_args()
    con = connect()
    if args.cmd == "campaign":
        con.execute("INSERT INTO campaigns(name, rate_per_1k, cap_per_clip) VALUES (?,?,?)", (args.name, args.rate, args.cap))
        print(f"Added campaign '{args.name}' (${args.rate}/1k views, cap {args.cap}).")
    elif args.cmd == "clip" and args.action == "add":
        cur = con.execute("INSERT INTO clips(campaign_id, url, views) VALUES (?,?,?)", (campaign_id(con, args.campaign), args.url, args.views))
        print(f"Clip #{cur.lastrowid} recorded.")
    elif args.cmd == "clip":
        if con.execute("UPDATE clips SET views = ? WHERE id = ?", (args.views, args.id)).rowcount == 0:
            sys.exit(f"No clip #{args.id}")
        print(f"Clip #{args.id} now at {args.views} views.")
    elif args.cmd == "paid":
        con.execute("INSERT INTO payouts(campaign_id, amount) VALUES (?,?)", (campaign_id(con, args.campaign), args.amount))
        print(f"Recorded ${args.amount:.2f} received from '{args.campaign}'.")
    else:
        report(con)
    con.commit()


if __name__ == "__main__":
    main()
