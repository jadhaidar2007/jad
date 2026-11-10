"""Stepwise trading engine with a hard risk layer.

The same `Engine.step()` is used by the backtester and the paper trader, so
whatever is backtested is exactly what paper-trades.

Timing per daily candle t:
  1. At the open of t, rebalance toward the target decided at the close of t-1.
  2. During t, if the low touches the stop, exit at min(open, stop) - slippage.
  3. At the close of t, mark equity to market and update the risk state.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class RiskConfig:
    fee: float = 0.001             # 0.10% taker fee per side
    slippage: float = 0.0005       # 0.05% adverse fill
    risk_per_trade: float = 0.02   # max equity lost if the stop is hit
    stop_atr_mult: float = 2.5     # stop distance = mult * ATR(14)
    max_exposure: float = 1.0      # 1.0 = no leverage
    kill_drawdown: float = 0.15    # halt trading at this drawdown from peak
    kill_cooldown_days: int = 30   # backtest only; live needs a manual reset
    min_trade: float = 0.02        # ignore rebalances smaller than this share of equity
    use_risk_sizing: bool = True


@dataclass
class State:
    cash: float = 10_000.0
    units: float = 0.0
    stop: float | None = None
    peak: float = 10_000.0
    halted_until: int | None = None   # candle index; -1 = halted until manual reset
    wait_for_reset: bool = False      # after a stop-out, wait for the signal to go flat
    trades: list = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


class Engine:
    def __init__(self, cfg: RiskConfig, state: State | None = None, live: bool = False):
        self.cfg = cfg
        self.s = state or State()
        self.live = live

    def equity(self, price: float) -> float:
        return self.s.cash + self.s.units * price

    def _trade(self, i, date, price, units_delta, reason):
        cfg = self.cfg
        fill = price * (1 + cfg.slippage if units_delta > 0 else 1 - cfg.slippage)
        notional = units_delta * fill
        fee = abs(notional) * cfg.fee
        self.s.cash -= notional + fee
        self.s.units += units_delta
        self.s.trades.append({"i": i, "date": str(date), "side": "buy" if units_delta > 0 else "sell",
                              "units": abs(units_delta), "price": fill, "fee": fee, "reason": reason})

    def step(self, i, date, o, h, l, c, target: float, atr: float) -> dict:
        cfg, s = self.cfg, self.s
        halted = s.halted_until is not None and (s.halted_until == -1 or i < s.halted_until)
        if not halted:
            s.halted_until = None
        if target <= 0:
            s.wait_for_reset = False

        # 1. rebalance at the open
        eq = self.equity(o)
        want = 0.0 if (halted or s.wait_for_reset) else min(max(target, 0.0), cfg.max_exposure)
        if want > 0 and cfg.use_risk_sizing and atr > 0:
            stop_dist = cfg.stop_atr_mult * atr / o
            want = min(want, cfg.risk_per_trade / stop_dist)
        delta_val = want * eq - s.units * o
        if abs(delta_val) > cfg.min_trade * eq or (want == 0 and s.units > 0):
            units_delta = -s.units if want == 0 else delta_val / o
            self._trade(i, date, o, units_delta, "halted" if halted else "signal")
        if s.units > 0 and cfg.use_risk_sizing and atr > 0:
            new_stop = o - cfg.stop_atr_mult * atr
            s.stop = new_stop if s.stop is None else max(s.stop, new_stop)  # trailing, never loosens
        elif s.units <= 0:
            s.stop = None

        # 2. intraday stop
        if s.units > 0 and s.stop is not None and l <= s.stop:
            self._trade(i, date, min(o, s.stop), -s.units, "stop")
            s.stop, s.wait_for_reset = None, True

        # 3. mark to market + kill switch
        eq = self.equity(c)
        s.peak = max(s.peak, eq)
        dd = 1 - eq / s.peak
        if dd >= cfg.kill_drawdown and not halted:
            if s.units > 0:
                self._trade(i, date, c, -s.units, "kill_switch")
            s.stop = None
            s.halted_until = -1 if self.live else i + cfg.kill_cooldown_days
            s.peak = self.equity(c)   # re-arm from the new base after the cooldown
        return {"date": date, "equity": self.equity(c), "exposure": s.units * c / max(self.equity(c), 1e-9),
                "drawdown": dd, "halted": halted}
