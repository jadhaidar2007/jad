"""Long/flat strategies.

Each strategy takes a daily OHLCV DataFrame and a params dict and returns a
target exposure Series in [0, 1]. The value at row t may only use data up to
and including the close of row t; the engine acts on it at the NEXT open, so
there is no look-ahead.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _rsi(close: pd.Series, n: int) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def buy_hold(df, p):
    return pd.Series(1.0, index=df.index)


def sma_trend(df, p):
    return (df.close > df.close.rolling(p["n"]).mean()).astype(float)


def dual_ma(df, p):
    fast = df.close.rolling(p["fast"]).mean()
    slow = df.close.rolling(p["slow"]).mean()
    return (fast > slow).astype(float)


def donchian(df, p):
    hi = df.high.rolling(p["entry"]).max().shift(1)
    lo = df.low.rolling(p["exit"]).min().shift(1)
    sig = pd.Series(np.nan, index=df.index)
    sig[df.close > hi] = 1.0
    sig[df.close < lo] = 0.0
    return sig.ffill().fillna(0.0)


def tsmom(df, p):
    """Time-series momentum: long when the trailing return is positive."""
    return (df.close.pct_change(p["lookback"]) > 0).astype(float)


def rsi_meanrev(df, p):
    """Buy oversold dips in an uptrend, exit on a bounce."""
    rsi = _rsi(df.close, p["n"])
    trend = df.close > df.close.rolling(200).mean()
    sig = pd.Series(np.nan, index=df.index)
    sig[(rsi < p["buy"]) & trend] = 1.0
    sig[(rsi > p["sell"]) | ~trend] = 0.0
    return sig.ffill().fillna(0.0)


def voltarget_trend(df, p):
    """SMA trend, scaled down when realised volatility is above target."""
    base = sma_trend(df, p)
    vol = np.log(df.close).diff().rolling(30).std() * np.sqrt(365)
    return (base * (p["target_vol"] / vol).clip(upper=1.0)).fillna(0.0)


STRATEGIES = {
    "buy_hold": (buy_hold, [{}]),
    "sma_trend": (sma_trend, [{"n": n} for n in (50, 100, 150, 200)]),
    "dual_ma": (dual_ma, [{"fast": f, "slow": s} for f, s in ((10, 50), (20, 100), (50, 200))]),
    "donchian": (donchian, [{"entry": e, "exit": x} for e, x in ((20, 10), (55, 20), (100, 50))]),
    "tsmom": (tsmom, [{"lookback": n} for n in (30, 60, 90, 180)]),
    "rsi_meanrev": (rsi_meanrev, [{"n": n, "buy": b, "sell": 60} for n in (2, 4) for b in (10, 20)]),
    "voltarget_trend": (voltarget_trend, [{"n": n, "target_vol": v} for n in (50, 100, 200) for v in (0.4, 0.6)]),
}
