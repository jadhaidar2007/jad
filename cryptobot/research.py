"""Wide search for the best return without blowing up.

    python -m cryptobot.research

Goal: highest growth with a max drawdown that a person can survive (<= 40%).
Three guards against fooling ourselves:
  1. Each config is scored over 2018-2026 AND three separate sub-periods.
  2. A block bootstrap of daily returns estimates the chance of a 50% drawdown.
  3. A walk-forward "meta" test picks a config every year using only the
     previous 3 years, which shows what the selection process itself would
     have earned out of sample.
"""
from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
import pandas as pd

from .backtest import load, metrics, run
from .engine import RiskConfig
from .strategies import buy_hold, donchian, dual_ma, sma_trend, trend_ensemble, tsmom, voltarget_ensemble

ROOT = Path(__file__).parent
MAX_DD = 0.40
PERIODS = [("2018-2020", "2018-01-01", "2020-12-31"), ("2021-2023", "2021-01-01", "2023-12-31"),
           ("2024-2026", "2024-01-01", "2026-12-31")]


def signals(df):
    s = {"buy_hold": buy_hold(df, {})}
    for n in (50, 100, 150, 200):
        s[f"sma{n}"] = sma_trend(df, {"n": n})
    for e, x in ((20, 10), (55, 20), (100, 50)):
        s[f"donchian{e}/{x}"] = donchian(df, {"entry": e, "exit": x})
    for n in (30, 90):
        s[f"tsmom{n}"] = tsmom(df, {"lookback": n})
    s["dual_ma20/100"] = dual_ma(df, {"fast": 20, "slow": 100})
    s["ensemble"] = trend_ensemble(df)
    for tv in (0.4, 0.6, 0.8, 1.0):
        for lev in (1.0, 1.5, 2.0):
            s[f"vt_ens{tv:.0%}_x{lev:g}"] = voltarget_ensemble(df, {"target_vol": tv, "max_lev": lev})
    return s


RISK = {
    "none": RiskConfig(use_risk_sizing=False, use_stop=False, kill_drawdown=1.01, max_exposure=2.0),
    "stop2.5atr": RiskConfig(use_risk_sizing=False, use_stop=True, stop_atr_mult=2.5, kill_drawdown=1.01, max_exposure=2.0),
    "stop4atr": RiskConfig(use_risk_sizing=False, use_stop=True, stop_atr_mult=4.0, kill_drawdown=1.01, max_exposure=2.0),
    "size5%": RiskConfig(risk_per_trade=0.05, kill_drawdown=1.01, max_exposure=2.0),
    "size10%": RiskConfig(risk_per_trade=0.10, kill_drawdown=1.01, max_exposure=2.0),
    "none+kill35": RiskConfig(use_risk_sizing=False, use_stop=False, kill_drawdown=0.35, max_exposure=2.0),
}


def bootstrap_ruin(eq: pd.Series, n=1000, block=30, years=5, dd=0.5, seed=0) -> float:
    """Chance of a >= dd drawdown within `years`, resampling 30-day blocks of real returns."""
    r = eq.pct_change().dropna().to_numpy()
    rng = np.random.default_rng(seed)
    days, hits = years * 365, 0
    for _ in range(n):
        starts = rng.integers(0, len(r) - block, days // block + 1)
        path = np.concatenate([r[s:s + block] for s in starts])[:days]
        curve = np.cumprod(1 + path)
        if (1 - curve / np.maximum.accumulate(curve)).max() >= dd:
            hits += 1
    return hits / n


def idx(df, date):
    return int(df.index[df.date >= pd.Timestamp(date)][0])


def main():
    df = load(ROOT / "data" / "BTC-USD_1d.csv")
    sigs = signals(df)
    start = idx(df, "2018-01-01")
    rows, curves = [], {}
    for sname, sig in sigs.items():
        for rname, cfg in RISK.items():
            if sname == "buy_hold" and rname != "none":
                continue
            eq, trades = run(df, sig, cfg, start, len(df))
            m = metrics(eq.equity, trades)
            row = {"signal": sname, "risk": rname, **{k: m[k] for k in ("cagr", "max_drawdown", "sharpe", "calmar", "trades")},
                   "avg_exposure": eq.exposure.mean()}
            for pname, a, b in PERIODS:
                pe, _ = run(df, sig, cfg, idx(df, a), int(df.index[df.date <= pd.Timestamp(b)][-1]) + 1)
                pm = metrics(pe.equity)
                row[f"{pname}_cagr"], row[f"{pname}_dd"] = pm["cagr"], pm["max_drawdown"]
            row["worst_period_dd"] = max(row[f"{p}_dd"] for p, _, _ in PERIODS)
            rows.append(row)
            curves[(sname, rname)] = eq.equity

    res = pd.DataFrame(rows)
    safe = res[res.worst_period_dd <= MAX_DD].sort_values("cagr", ascending=False)
    for i, r in safe.head(12).iterrows():
        safe.loc[i, "p_dd50_5y"] = bootstrap_ruin(curves[(r.signal, r.risk)])
    hold = res[res.signal == "buy_hold"].iloc[0]

    # walk-forward meta test: each year pick the best "safe" config using only the prior 3 years
    years = range(2018, df.date.dt.year.max() + 1)
    combo_targets = pd.Series(0.0, index=df.index)
    picks = []
    for y in years:
        tr_a, tr_b = idx(df, f"{y - 3}-01-01"), idx(df, f"{y}-01-01")
        best, best_cagr = None, -np.inf
        for (sname, rname) in curves:
            if rname != "none":   # meta test uses signal-level sizing only, risk applied below
                continue
            pe, _ = run(df, sigs[sname], RISK["none"], tr_a, tr_b)
            pm = metrics(pe.equity)
            if pm["max_drawdown"] <= MAX_DD and pm["cagr"] > best_cagr:
                best, best_cagr = sname, pm["cagr"]
        best = best or "ensemble"
        sel = df.index[df.date.dt.year == y]
        combo_targets.loc[sel[0] - 1:sel[-1]] = sigs[best].loc[sel[0] - 1:sel[-1]]
        picks.append((y, best))
    meta_eq, meta_tr = run(df, combo_targets, RISK["none"], start, len(df))
    meta = metrics(meta_eq.equity, meta_tr)

    cols = ["signal", "risk", "cagr", "max_drawdown", "sharpe", "calmar", "avg_exposure", "trades",
            "2018-2020_cagr", "2021-2023_cagr", "2024-2026_cagr", "worst_period_dd", "p_dd50_5y"]
    out = ROOT / "results"; out.mkdir(exist_ok=True)
    res.to_csv(out / "research_all.csv", index=False)
    with pd.option_context("display.width", 250, "display.float_format", "{:.2f}".format, "display.max_columns", 30):
        text = (f"Period {df.date.iloc[start].date()} to {df.date.iloc[-1].date()}  |  rule: worst max drawdown <= {MAX_DD:.0%}\n"
                f"Buy & hold: CAGR {hold.cagr:.1%}, max DD {hold.max_drawdown:.0%}, "
                f"P(50% DD in 5y) {bootstrap_ruin(curves[('buy_hold', 'none')]):.0%}\n\n"
                f"Top safe configs ({len(safe)} of {len(res)} passed):\n{safe[cols].head(12).to_string(index=False)}\n\n"
                f"Walk-forward meta selection (honest OOS): CAGR {meta['cagr']:.1%}, max DD {meta['max_drawdown']:.0%}, "
                f"Sharpe {meta['sharpe']:.2f}\nPicks: {picks}\n")
    print(text)
    (out / "research_summary.txt").write_text(text)


if __name__ == "__main__":
    main()
