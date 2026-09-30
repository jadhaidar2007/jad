"""Render signals, trade results and reports as the Telegram messages members see."""
from __future__ import annotations

from html import escape

from signalbot.parse import Signal

EXIT_LABELS = {"close": "⚪ CLOSE", "tp": "🎯 TP HIT", "sl": "🛑 SL HIT", "be": "➖ BREAKEVEN"}
RESULT_ICONS = {"win": "✅", "loss": "❌", "be": "➖"}


def _fmt(n: float) -> str:
    return f"{n:,.2f}".rstrip("0").rstrip(".")


def _pts(n: float) -> str:
    return f"{n:+,.2f}".rstrip("0").rstrip(".")


def risk_reward(sig: Signal) -> float | None:
    if sig.entry is None or sig.sl is None or not sig.tps or sig.entry == sig.sl:
        return None
    return abs(sig.tps[0] - sig.entry) / abs(sig.entry - sig.sl)


def format_signal(sig: Signal) -> str:
    if sig.action in EXIT_LABELS:
        return f"{EXIT_LABELS[sig.action]} <b>{sig.symbol}</b>" + (f" @ {_fmt(sig.entry)}" if sig.entry is not None else "")
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


def format_result(trade: dict) -> str:
    """Message posted when a tracked trade closes."""
    head = f"{trade['symbol']} {trade['side'].upper()}"
    if trade["points"] is None:
        return f"⚪ <b>{head}</b> closed"
    text = f"{RESULT_ICONS[trade['outcome']]} <b>{head}</b> closed @ {_fmt(trade['exit_price'])}\n{_pts(trade['points'])} pts"
    if trade["r"] is not None:
        text += f" ({trade['r']:+.1f}R)"
    return text


def format_report(title: str, period: dict, all_time: dict) -> str:
    if period["n"] == 0:
        return f"📊 <b>{title}</b>\nNo closed trades this period."
    lines = [
        f"📊 <b>{title}</b>",
        f"Trades: {period['n']}  ✅ {period['wins']}  ❌ {period['losses']}  ➖ {period['be']}",
    ]
    if period["win_rate"] is not None:
        lines.append(f"Win rate: {period['win_rate']:.0%}")
    lines.append(f"Net: {_pts(period['points'])} pts ({period['r']:+.1f}R)")
    for sym, s in sorted(period["per_symbol"].items()):
        lines.append(f"• {sym}: {_pts(s['points'])} pts ({s['n']} trade{'s' if s['n'] != 1 else ''})")
    if all_time["n"] > period["n"]:
        wr = f", {all_time['win_rate']:.0%} win rate" if all_time["win_rate"] is not None else ""
        lines.append(f"\nAll-time: {all_time['n']} trades{wr}, {_pts(all_time['points'])} pts")
    return "\n".join(lines)
