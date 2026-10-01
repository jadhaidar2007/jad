"""One place that turns a Signal into trade-book updates + messages. Used by the webhook and the CLI."""
from __future__ import annotations

from dataclasses import dataclass, field

from signalbot import broadcast, store, trades
from signalbot.format import format_result, format_signal
from signalbot.parse import EXIT_ACTIONS, Signal


@dataclass
class Outcome:
    status: str  # "sent" | "duplicate" | "failed"
    messages: list[str] = field(default_factory=list)
    delivery: dict[str, bool] = field(default_factory=dict)


def _exit_price(sig: Signal, trade: dict) -> float | None:
    if sig.entry is not None:
        return sig.entry
    if sig.action == "tp":
        return trade["tps"][0] if trade["tps"] else None
    if sig.action == "sl":
        return trade["sl"]
    if sig.action == "be":
        return trade["entry"]
    return None


def _close(trade: dict, price: float | None, commit: bool) -> dict:
    if commit:
        return trades.close_trade(trade["id"], price)
    return {**trade, **trades.compute_result(trade, price)}


def build_messages(sig: Signal, commit: bool = True) -> list[str]:
    """The messages this signal produces, in posting order.

    With commit=False nothing is written, so the result can be previewed.
    """
    existing = trades.open_trade_for(sig.symbol)
    if sig.action in EXIT_ACTIONS:
        if existing is None:
            return [format_signal(sig)]
        return [format_result(_close(existing, _exit_price(sig, existing), commit))]

    msgs = []
    if existing and existing["side"] != sig.action and sig.entry is not None:
        # Reversal: the old trade ends where the new one starts.
        msgs.append(format_result(_close(existing, sig.entry, commit)))
        existing = None
    if existing is None and commit:
        trades.open_trade(sig)
    msgs.append(format_signal(sig))
    return msgs


def publish(sig: Signal, force: bool = False) -> Outcome:
    if not force and store.is_duplicate(sig):
        return Outcome("duplicate")
    messages = build_messages(sig, commit=True)
    delivery: dict[str, bool] = {}
    for m in messages:
        for platform, ok in broadcast.send_detailed(m).items():
            delivery[platform] = delivery.get(platform, True) and ok
    delivered = bool(delivery) and all(delivery.values())
    store.log_signal(sig, delivered)
    return Outcome("sent" if delivered else "failed", messages, delivery)
