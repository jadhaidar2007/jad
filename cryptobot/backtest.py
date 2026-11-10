"""Walk-forward backtester.

    python -m cryptobot.backtest                      # BTC, every strategy
    python -m cryptobot.backtest --data cryptobot/data/ETH-USD_1d.csv --train-years 1

For each test year, the parameters for every strategy are picked using only
the previous `train_years` of data; the chosen parameters then trade the next
year out of sample. Only the stitched out-of-sample results are reported, and
they are compared with buy-and-hold BTC over the same period.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from .engine import Engine, RiskConfig, State
from .strategies import STRATEGIES

ROOT = Path(__file__).parent


def load(path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    tr = pd.concat([df.high - df.low, (df.high - df.close.shift()).abs(), (df.low - df.close.shift()).abs()], axis=1).max(axis=1)
    df["atr"] = tr.rolling(14).mean()
    return df


def run(df: pd.DataFrame, target: pd.Series, cfg: RiskConfig, start: int, end: int):
    """Simulate candles [start, end). target[t-1] is traded at the open of t."""
    eng = Engine(cfg, State())
    rows = []
    for i in range(start, end):
        r = df.iloc[i]
        tgt = float(target.iloc[i - 1]) if i > 0 and not np.isnan(target.iloc[i - 1]) else 0.0
        atr = float(df.atr.iloc[i - 1]) if i > 0 and not np.isnan(df.atr.iloc[i - 1]) else 0.0
        rows.append(eng.step(i, r.date.date(), r.open, r.high, r.low, r.close, tgt, atr))
    return pd.DataFrame(rows).set_index("date"), eng.s.trades


def metrics(eq: pd.Series, trades=None) -> dict:
    ret = eq.pct_change().dropna()
    years = len(eq) / 365
    cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1 / years) - 1 if years > 0 else 0
    sharpe = ret.mean() / ret.std() * np.sqrt(365) if ret.std() > 0 else 0
    downside = ret[ret < 0].std()
    sortino = ret.mean() / downside * np.sqrt(365) if downside > 0 else 0
    maxdd = (1 - eq / eq.cummax()).max()
    out = {"total_return": eq.iloc[-1] / eq.iloc[0] - 1, "cagr": cagr, "sharpe": sharpe,
           "sortino": sortino, "max_drawdown": maxdd, "calmar": cagr / maxdd if maxdd > 0 else 0}
    if trades is not None:
        out["trades"] = len(trades)
        out["fees_paid"] = sum(t["fee"] for t in trades)
    return out


def walk_forward(df, name, cfg, train_years, test_start):
    fn, grid = STRATEGIES[name]
    signals = [fn(df, p) for p in grid]
    years = sorted(df.date.dt.year.unique())
    combined = pd.Series(0.0, index=df.index)
    chosen = []
    for y in years:
        test_idx = df.index[df.date.dt.year == y]
        if test_idx[0] < test_start:
            continue
        tr_start = max(0, int(test_idx[0] - train_years * 365))
        best, best_score = 0, -np.inf
        if len(grid) > 1:
            for k, sig in enumerate(signals):
                eq, _ = run(df, sig, cfg, tr_start, int(test_idx[0]))
                score = metrics(eq.equity)["sharpe"]
                if score > best_score:
                    best, best_score = k, score
        combined.loc[test_idx] = signals[best].loc[test_idx]
        # carry the chosen signal into the candle before the test window, so day 1 trades correctly
        combined.loc[test_idx[0] - 1] = signals[best].loc[test_idx[0] - 1]
        chosen.append({"year": int(y), "params": grid[best]})
    eq, trades = run(df, combined, cfg, test_start, len(df))
    return eq, trades, chosen


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(ROOT / "data" / "BTC-USD_1d.csv"))
    ap.add_argument("--train-years", type=int, default=3)
    ap.add_argument("--fee-mult", type=float, default=1.0, help="stress test: multiply fees and slippage")
    ap.add_argument("--out", default=str(ROOT / "results"))
    a = ap.parse_args(argv)

    df = load(a.data)
    first_test_year = df.date.dt.year.min() + a.train_years + 1
    test_start = int(df.index[df.date.dt.year == first_test_year][0])
    variants = {
        "risk_layer_on": RiskConfig(),
        "risk_5pct_kill25": RiskConfig(risk_per_trade=0.05, kill_drawdown=0.25),
        "risk_layer_off": RiskConfig(use_risk_sizing=False, kill_drawdown=1.01),
    }
    if a.fee_mult != 1:
        variants = {k: replace(v, fee=v.fee * a.fee_mult, slippage=v.slippage * a.fee_mult) for k, v in variants.items()}
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    report, curves = [], {}
    for vname, cfg in variants.items():
        for name in STRATEGIES:
            c = cfg if name != "buy_hold" else replace(RiskConfig(), use_risk_sizing=False, kill_drawdown=1.01)
            if name == "buy_hold" and vname != "risk_layer_on":
                continue
            eq, trades, chosen = walk_forward(df, name, c, a.train_years, test_start)
            m = metrics(eq.equity, trades)
            m.update(strategy=name, variant="benchmark" if name == "buy_hold" else vname,
                     avg_exposure=eq.exposure.mean(), params_by_year=chosen)
            report.append(m)
            curves[f"{name}|{m['variant']}"] = eq.equity

    rep = pd.DataFrame(report).sort_values("sharpe", ascending=False)
    period = f"{df.date.iloc[test_start].date()} to {df.date.iloc[-1].date()}"
    tag = Path(a.data).stem + (f"_fees{a.fee_mult:g}x" if a.fee_mult != 1 else "")
    pd.DataFrame(curves).to_csv(out / f"{tag}_equity.csv")
    (out / f"{tag}_report.json").write_text(json.dumps({"period": period, "results": report}, indent=2, default=str))
    cols = ["strategy", "variant", "total_return", "cagr", "sharpe", "sortino", "max_drawdown", "calmar", "avg_exposure", "trades", "fees_paid"]
    with pd.option_context("display.width", 200, "display.float_format", "{:.2f}".format):
        print(f"{tag}: out-of-sample {period} (fees+slippage x{a.fee_mult} of 0.10%+0.05% per side)")
        print(rep[cols].to_string(index=False))
    return rep


if __name__ == "__main__":
    main()
