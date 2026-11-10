"""Run: python -m pytest cryptobot -q"""
import numpy as np
import pandas as pd

from cryptobot.backtest import run
from cryptobot.engine import Engine, RiskConfig, State
from cryptobot.paper import PaperTrader
from cryptobot.strategies import STRATEGIES


def _df(closes):
    c = pd.Series(closes, dtype=float)
    df = pd.DataFrame({"date": pd.date_range("2020-01-01", periods=len(c)), "open": c.shift().fillna(c[0]),
                       "high": c * 1.01, "low": c * 0.99, "close": c, "volume": 1.0})
    df["atr"] = (df.high - df.low).rolling(3).mean()
    return df


def test_no_lookahead():
    """Changing a future price must not change any earlier target."""
    df = _df(np.linspace(100, 200, 300))
    df2 = df.copy(); df2.loc[250:, ["open", "high", "low", "close"]] *= 0.5
    for name, (fn, grid) in STRATEGIES.items():
        for p in grid:
            a, b = fn(df, p), fn(df2, p)
            pd.testing.assert_series_equal(a.iloc[:250], b.iloc[:250], check_names=False, obj=name)


def test_fees_reduce_equity():
    df = _df([100.0] * 50)
    eq, trades = run(df, pd.Series(1.0, index=df.index), RiskConfig(use_risk_sizing=False), 1, len(df))
    assert trades and eq.equity.iloc[-1] < 10_000


def test_risk_sizing_caps_loss_at_stop():
    cfg = RiskConfig(fee=0, slippage=0)
    e = Engine(cfg)
    e.step(0, "d0", 100, 101, 99, 100, target=1.0, atr=4.0)   # stop = 100 - 2.5*4 = 90
    e.step(1, "d1", 100, 100, 80, 85, target=1.0, atr=4.0)    # stop hit
    assert abs(e.equity(85) - 9_800) < 1                      # lost exactly 2%


def test_kill_switch_halts_live():
    cfg = RiskConfig(fee=0, slippage=0, use_risk_sizing=False, kill_drawdown=0.15)
    e = Engine(cfg, live=True)
    e.step(0, "d0", 100, 100, 100, 100, 1.0, 1.0)
    e.step(1, "d1", 100, 100, 80, 80, 1.0, 1.0)
    assert e.s.units == 0 and e.s.halted_until == -1
    e.step(2, "d2", 80, 90, 80, 90, 1.0, 1.0)
    assert e.s.units == 0                                      # stays flat until manual reset


def test_paper_resume_matches_single_run(tmp_path):
    df = _df(list(np.linspace(100, 150, 120)) + list(np.linspace(150, 110, 80)))
    cfg = RiskConfig()
    full = PaperTrader("sma_trend", {"n": 20}, cfg, tmp_path / "a", live=True)
    full.process(df)
    part = PaperTrader("sma_trend", {"n": 20}, cfg, tmp_path / "b", live=True)
    part.process(df.iloc[:130])
    part = PaperTrader("sma_trend", {"n": 20}, cfg, tmp_path / "b", live=True)  # restart from disk
    part.process(df)
    assert abs(full.engine.equity(df.close.iloc[-1]) - part.engine.equity(df.close.iloc[-1])) < 1e-6
