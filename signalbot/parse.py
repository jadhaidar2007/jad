"""Turn a TradingView alert body into a normalized Signal.

Preferred alert message (JSON):
    {"secret": "...", "action": "buy", "symbol": "{{ticker}}",
     "entry": {{close}}, "sl": 38900, "tp": 39200}

Plain text also works, e.g. "BUY US30 entry 39000 sl 38900 tp 39200 tp2 39400".
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

# Only these three markets are traded; map the common TradingView tickers onto them.
SYMBOL_ALIASES = {
    "US30": "US30", "DJI": "US30", "DJ30": "US30", "DOW": "US30", "WS30": "US30", "YM": "US30", "YM1!": "US30",
    "SPX500": "SPX500", "SPX": "SPX500", "US500": "SPX500", "SP500": "SPX500", "ES": "SPX500", "ES1!": "SPX500",
    "US100": "US100", "NAS100": "US100", "NDX": "US100", "USTEC": "US100", "NQ": "US100", "NQ1!": "US100",
}

BUY_WORDS = {"buy", "long"}
SELL_WORDS = {"sell", "short"}
CLOSE_WORDS = {"close", "exit", "flat"}
TP_WORDS = {"tp", "tp_hit", "takeprofit"}
SL_WORDS = {"sl", "sl_hit", "stop", "stopped"}
BE_WORDS = {"be", "breakeven"}
EXIT_ACTIONS = {"close", "tp", "sl", "be"}


_LABELED = re.compile(r"\b(entry|price|sl|tp[123]?)\s*[=:@]?\s*(-?\d[\d,]*(?:\.\d+)?)", re.I)
_BARE = re.compile(r"(?<![\w.])-?\d[\d,]*(?:\.\d+)?(?!\w)")


class ParseError(ValueError):
    pass


@dataclass
class Signal:
    action: str  # "buy" | "sell" | "close" | "tp" | "sl" | "be"
    symbol: str
    entry: float | None = None
    sl: float | None = None
    tps: list[float] = field(default_factory=list)
    note: str = ""


def normalize_symbol(raw: str) -> str:
    # "CAPITALCOM:US30" / "OANDA:SPX500USD" -> strip exchange prefix and quote-currency suffix
    s = raw.upper().split(":")[-1].strip()
    if s in SYMBOL_ALIASES:
        return SYMBOL_ALIASES[s]
    if s.endswith("USD") and s[:-3] in SYMBOL_ALIASES:
        return SYMBOL_ALIASES[s[:-3]]
    raise ParseError(f"unsupported symbol: {raw!r}")


def _normalize_action(raw: str) -> str:
    w = raw.strip().lower()
    if w in BUY_WORDS:
        return "buy"
    if w in SELL_WORDS:
        return "sell"
    if w in CLOSE_WORDS:
        return "close"
    if w in TP_WORDS:
        return "tp"
    if w in SL_WORDS:
        return "sl"
    if w in BE_WORDS:
        return "be"
    raise ParseError(f"unknown action: {raw!r}")


def _num(value) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        raise ParseError(f"not a number: {value!r}")


def extract_secret(body: str) -> str | None:
    """Return the secret from a JSON body or a 'secret=...' plain-text line."""
    try:
        data = json.loads(body)
        if isinstance(data, dict):
            return str(data["secret"]) if "secret" in data else None
    except json.JSONDecodeError:
        pass
    m = re.search(r"secret\s*[=:]\s*(\S+)", body, re.I)
    return m.group(1) if m else None


def _from_json(data: dict) -> Signal:
    if "action" not in data or "symbol" not in data:
        raise ParseError("JSON alert needs 'action' and 'symbol'")
    tps = data.get("tps") or [data.get(k) for k in ("tp", "tp1", "tp2", "tp3")]
    return Signal(
        action=_normalize_action(str(data["action"])),
        symbol=normalize_symbol(str(data["symbol"])),
        entry=_num(data.get("entry") or data.get("price")),
        sl=_num(data.get("sl")),
        tps=[t for t in (_num(t) for t in tps) if t is not None],
        note=str(data.get("note", "")).strip(),
    )


def _from_text(body: str) -> Signal:
    text = re.sub(r"secret\s*[=:]\s*\S+", "", body, flags=re.I)
    tokens = re.findall(r"[A-Za-z0-9!:.,]+", text)
    action = symbol = None
    for t in tokens:
        if action is None and t.lower() in BUY_WORDS | SELL_WORDS | CLOSE_WORDS | TP_WORDS | SL_WORDS | BE_WORDS:
            action = _normalize_action(t)
        elif symbol is None:
            try:
                symbol = normalize_symbol(t)
            except ParseError:
                pass
    if action is None or symbol is None:
        raise ParseError("could not find action and symbol in alert text")

    vals: dict[str, float | None] = {}
    for m in _LABELED.finditer(text):
        vals.setdefault(m.group(1).lower(), _num(m.group(2)))
    entry = vals.get("entry") if vals.get("entry") is not None else vals.get("price")
    if entry is None:
        # Shorthand: "buy us30 39000 sl 38900" -> the first unlabeled number is the entry/exit price.
        bare = _BARE.search(_LABELED.sub(" ", text))
        entry = _num(bare.group(0)) if bare else None
    tps = [vals[k] for k in ("tp", "tp1", "tp2", "tp3") if vals.get(k) is not None]
    return Signal(action=action, symbol=symbol, entry=entry, sl=vals.get("sl"), tps=tps)


def parse_alert(body: str) -> Signal:
    body = body.strip()
    if not body:
        raise ParseError("empty alert")
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return _from_text(body)
    if not isinstance(data, dict):
        raise ParseError("JSON alert must be an object")
    return _from_json(data)


def check_levels(sig: Signal) -> list[str]:
    """Sanity warnings for hand-typed signals (SL/TP on the wrong side of entry)."""
    if sig.action not in ("buy", "sell"):
        return []
    warnings = []
    if sig.entry is None:
        return ["no entry price: this trade will not be tracked"]
    sign = 1 if sig.action == "buy" else -1
    if sig.sl is not None and sign * (sig.sl - sig.entry) >= 0:
        warnings.append(f"SL {sig.sl:g} is on the wrong side of entry for a {sig.action}")
    for i, tp in enumerate(sig.tps, 1):
        if sign * (tp - sig.entry) <= 0:
            warnings.append(f"TP{i} {tp:g} is on the wrong side of entry for a {sig.action}")
    return warnings
