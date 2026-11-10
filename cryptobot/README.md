# cryptobot: paper trading + walk-forward backtests (BTC, long/flat)

**No real money is involved.** No exchange keys or order code exist here. Live mode only reads public candles.

```
pip install -r cryptobot/requirements.txt
python -m pytest cryptobot -q                     # 5 tests: no look-ahead, fees, stop sizing, kill switch, resume
python -m cryptobot.backtest                      # walk-forward on BTC daily, ~2-3 min
python -m cryptobot.backtest --fee-mult 3         # stress test: triple fees + slippage
python -m cryptobot.paper --replay cryptobot/data/BTC-USD_1d.csv --from 2026-01-01
python -m cryptobot.paper --live --exchange binance --symbol BTC/USDT   # needs ccxt + network
```

## Files
| file | what |
|---|---|
| `strategies.py` | 7 long/flat signals (trend, breakout, momentum, mean reversion, vol-targeted trend) + param grids |
| `engine.py` | one stepwise engine used by **both** backtest and paper: next-open execution, fees, slippage, ATR stop, risk sizing, kill switch |
| `backtest.py` | walk-forward: params picked on prior 3 years only, traded next year out-of-sample |
| `paper.py` | resumable paper trader (JSON state + trades CSV); CSV replay or live public candles |
| `data/BTC-USD_1d.csv` | daily BTC/USD 2014-09-17 to 2026-11-07 (Yahoo-sourced public data) |
| `results/` | report tables, JSON, and equity curves |

## Current best: `voltarget_ensemble` (target vol 40%, 60-day window, no leverage, 10% rebalance band)
`python -m cryptobot.research` searches 139 setups. A setup passes only if its worst drop stays at or under 40% in every period.

| | Buy & hold BTC | **Best setup** | Best, fees x3 |
|---|---|---|---|
| 2018-2026 CAGR | 21% | **29%** | 27% |
| $10k becomes | $55k | **$93k** | $81k |
| Max drawdown | 82% | **31%** | 32% |
| Chance of a 50% drawdown in 5 yrs (bootstrap) | 96% | **4%** | 5% |
| Unseen 2015-2017 (not used to pick) | +397%/yr, DD 36% | +126%/yr, DD 27% | |

How it works: 9 trend signals vote on how much to hold. That share is then scaled down when volatility runs above 40% a year. On average it holds 37% BTC and the rest in cash.

Settings near the winner (target vol 30-50%, 20-60 day window) all earned 20-31% a year, so the result doesn't depend on one lucky setting. Rejected: leverage (+2-3%/yr for more risk), stops (hurt returns), and re-picking the best strategy every year (59% drawdown).

## Earlier results: out-of-sample 2018-01-01 to 2026-11-07, $10k start
Costs are 0.10% fee + 0.05% slippage per side. Buy-and-hold BTC returned **+455%** (21%/yr), with an **82% max drawdown**.

| strategy | risk setting | total | CAGR | Sharpe | max DD | avg exposure |
|---|---|---|---|---|---|---|
| sma_trend | none | +1350% | 35% | 0.91 | 58% | 55% |
| voltarget_trend | none | +709% | 27% | 0.91 | 48% | 44% |
| donchian | none | +707% | 27% | 0.80 | 53% | 43% |
| donchian | 5%/trade, 25% kill | +225% | 14% | 0.86 | 23% | 15% |
| dual_ma | 2%/trade, 15% kill (prompt's rules) | +70% | 6% | 0.93 | 12% | 6% |
| **buy & hold** | — | **+455%** | **21%** | **0.63** | **82%** | 100% |
| rsi_meanrev | any | ≈ 0 or negative | | | | |

At 3x costs, trend and breakout still beat holding on risk-adjusted terms: donchian Sharpe 0.83, sma_trend 0.81. Mean reversion loses.

### Caveats
- Only one asset (BTC) is tested, and the results are long/flat only. With roughly 9 test years and about 7 strategies tried, some of this edge is probably selection luck.
- The prompt's 2%-per-trade rule with an ATR stop caps exposure at about 6-8%. That makes the bot very safe but leaves it nearly idle.
- A daily backtest can't model intraday gaps, outages, or exchange failures.
