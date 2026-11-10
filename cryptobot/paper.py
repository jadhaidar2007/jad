"""Paper trader: runs the exact backtested Engine on daily candles, no real orders.

Replay a CSV (works offline):
    python -m cryptobot.paper --replay cryptobot/data/BTC-USD_1d.csv --from 2026-01-01

Live paper trading with public candles from an exchange (needs `pip install ccxt`
and network access; no API keys used, nothing is ever sent to the exchange):
    python -m cryptobot.paper --live --exchange binance --symbol BTC/USDT

Every run is resumable: state lives in a JSON file, trades go to a CSV log.
In live mode the kill switch halts until you delete `halted_until` from the
state file by hand.
"""
from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .backtest import load
from .engine import Engine, RiskConfig, State
from .strategies import STRATEGIES

DEFAULT_STATE = Path(__file__).parent / "paper_state"


class PaperTrader:
    def __init__(self, strategy: str, params: dict, cfg: RiskConfig, state_dir: Path, live: bool):
        self.fn = STRATEGIES[strategy][0]
        self.params = params
        self.dir = Path(state_dir); self.dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.dir / "state.json"
        self.log_file = self.dir / "trades.csv"
        st = json.loads(self.state_file.read_text()) if self.state_file.exists() else None
        self.last_date = st.pop("last_date", None) if st else None
        self.engine = Engine(cfg, State(**st) if st else State(), live=live)

    def process(self, df: pd.DataFrame) -> list[dict]:
        """Feed full daily history; only closed candles newer than last_date are traded."""
        target = self.fn(df, self.params)
        out = []
        for i in range(1, len(df)):
            r = df.iloc[i]
            d = str(r.date.date())
            if self.last_date and d <= self.last_date:
                continue
            n_before = len(self.engine.s.trades)
            row = self.engine.step(i, r.date.date(), r.open, r.high, r.low, r.close,
                                   float(target.iloc[i - 1]), float(df.atr.iloc[i - 1] or 0))
            self._log(self.engine.s.trades[n_before:])
            self.last_date = d
            out.append(row)
        self._save()
        return out

    def _log(self, trades):
        if not trades:
            return
        new = not self.log_file.exists()
        with self.log_file.open("a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(trades[0]))
            if new:
                w.writeheader()
            w.writerows(trades)

    def _save(self):
        st = self.engine.s.to_dict()
        st["trades"] = st["trades"][-50:]  # full history lives in trades.csv
        st["last_date"] = self.last_date
        self.state_file.write_text(json.dumps(st, indent=2, default=str))


def fetch_live(exchange: str, symbol: str, limit: int = 400) -> pd.DataFrame:
    import ccxt  # optional dependency, only for live mode
    ex = getattr(ccxt, exchange)()
    raw = ex.fetch_ohlcv(symbol, "1d", limit=limit)
    df = pd.DataFrame(raw, columns=["ts", "open", "high", "low", "close", "volume"])
    df["date"] = pd.to_datetime(df.ts, unit="ms")
    df = df[df.date < pd.Timestamp(datetime.now(timezone.utc).date())]  # drop the unfinished candle
    tr = pd.concat([df.high - df.low, (df.high - df.close.shift()).abs(), (df.low - df.close.shift()).abs()], axis=1).max(axis=1)
    df["atr"] = tr.rolling(14).mean()
    return df.reset_index(drop=True)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategy", default="voltarget_ensemble", choices=list(STRATEGIES))
    ap.add_argument("--params", default='{"target_vol": 0.4, "vol_window": 60}', help="JSON params for the strategy")
    ap.add_argument("--risk", default="best", choices=["best", "strict", "moderate"],
                    help="best = vol-target sizing, 10%% rebalance band, 35%% kill switch (research winner); "
                         "strict = prompt's 2%%/15%% rules; moderate = 5%% per trade, 25%% kill switch")
    ap.add_argument("--state-dir", default=str(DEFAULT_STATE))
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--replay")
    g.add_argument("--live", action="store_true")
    ap.add_argument("--from", dest="start", help="replay: first date to trade (earlier rows are warm-up)")
    ap.add_argument("--exchange", default="binance")
    ap.add_argument("--symbol", default="BTC/USDT")
    ap.add_argument("--poll-minutes", type=int, default=30)
    a = ap.parse_args(argv)

    cfg = {"best": RiskConfig(use_risk_sizing=False, use_stop=False, min_trade=0.10, kill_drawdown=0.35),
           "strict": RiskConfig(),
           "moderate": RiskConfig(risk_per_trade=0.05, kill_drawdown=0.25)}[a.risk]
    pt = PaperTrader(a.strategy, json.loads(a.params), cfg, Path(a.state_dir), live=a.live)
    if a.replay:
        df = load(a.replay)
        if a.start and not pt.last_date:
            pt.last_date = str((pd.Timestamp(a.start) - pd.Timedelta(days=1)).date())
        rows = pt.process(df)
        if rows:
            last = rows[-1]
            print(f"replayed {len(rows)} candles -> equity ${last['equity']:,.2f}, exposure {last['exposure']:.0%}, "
                  f"trades logged to {pt.log_file}")
        return
    while True:
        rows = pt.process(fetch_live(a.exchange, a.symbol))
        for r in rows:
            print(f"{r['date']} equity ${r['equity']:,.2f} exposure {r['exposure']:.0%}"
                  f"{' HALTED' if r['halted'] else ''}", flush=True)
        time.sleep(a.poll_minutes * 60)


if __name__ == "__main__":
    main()
