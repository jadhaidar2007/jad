"""Render a Signal as the Telegram message members see."""
from __future__ import annotations

from html import escape

from signalbot.parse import Signal


def _fmt(n: float) -> str:
    return f"{n:,.2f}".rstrip("0").rstrip(".")


def risk_reward(sig: Signal) -> float | None:
    if sig.entry is None or sig.sl is None or not sig.tps or sig.entry == sig.sl:
        return None
    return abs(sig.tps[0] - sig.entry) / abs(sig.entry - sig.sl)


def format_signal(sig: Signal) -> str:
    if sig.action == "close":
        return f"⚪ <b>CLOSE {sig.symbol}</b>" + (f" @ {_fmt(sig.entry)}" if sig.entry is not None else "")
    icon = "🟢" if sig.action == "buy" else "🔴"
    lines = [f"{icon} <b>{sig.action.upper()} {sig.symbol}</b>"]
    if sig.entry is not None:
        lines.append(f"Entry: {_fmt(sig.entry)}")
    if sig.sl is not None:
        lines.append(f"SL: {_fmt(sig.sl)}")
    for i, tp in enumerate(sig.tps, 1):
        lines.append(f"TP{i}: {_fmt(tp)}" if len(sig.tps) > 1 else f"TP: {_fmt(tp)}")
    rr = risk_reward(sig)
    if rr is not None:
        lines.append(f"R:R {rr:.1f}")
    if sig.note:
        lines.append(escape(sig.note))
    return "\n".join(lines)
