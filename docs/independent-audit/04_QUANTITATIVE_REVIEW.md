# 04 — Quantitative review

## Verdict

**No trading edge has been demonstrated, and the repository contains no evidence that could demonstrate one.** It has no market data, no recorded experiment results, no benchmark and no statistical test. Every performance number in its tests comes from synthetic, monotonically rising series.

I ran the repository's **own** research code on real daily BTC and ETH prices (2018-01-01 to 2026-05-23). The results below are consistent with **no edge after costs**. The selected SMA configurations underperformed buy-and-hold out of sample. The best in-sample configuration of a 120-configuration screen did no better than the best of 120 random coin-flip strategies.

**The project is spending its effort on orchestration and ledger hardening before it has a strategy worth protecting.** The ledger work is necessary eventually, but the binding constraint on both objectives (profitability and a product) is the absence of an edge.

## What exists

| Component | File | Assessment |
|---|---|---|
| SMA long/flat backtest | `research.py` `backtest` | Causal (signal from closes up to *i-1*, fill at close *i*). Charges bps costs on both legs. **Allocates 100% of cash when long, with no stop.** |
| Single train/holdout split | `research.py` `walk_forward` | One split; the winner is chosen by maximum net return across the grid. No multiple-testing control. |
| Rolling splits with embargo | `validation.py`, `pipeline.py` | Correct index arithmetic; warm-up comes from pre-test bars only. Each window is evaluated independently; `pipeline.py:55` hard-codes `500.0`. |
| Momentum / mean-reversion / breakout | `signals.py`, `simulator.py` | Causal; same 100%-allocation model. Not integrated with rolling selection. |
| Metrics | `metrics.py` | Return, max drawdown, per-period volatility (population variance), non-annualized Sharpe. No benchmark, exposure, turnover, hit rate, payoff ratio, confidence interval or significance. |
| Data | — | **None.** `load_csv` expects `timestamp,close` only, with no OHLC, volume or venue. |

Look-ahead bias: none found. Both `test_no_future_signal` and `test_future_price_does_not_change_signal` are valid causality checks, and I confirmed the warm-up arithmetic in `walk_forward` and `research_pipeline` by hand. Survivorship bias doesn't apply to two fixed assets. **Selection bias** (choosing the best of many configurations) is the dominant problem, and nothing in the code addresses it.

## Independent experiment (reproducible)

**Data:** Coin Metrics community daily reference rate `PriceUSD` (GitHub `coinmetrics/data`, `csv/btc.csv` and `csv/eth.csv`, retrieved 2026-11-18; raw-file SHA-256 `06495ff8…46c3` BTC and `46b18f3d…f2cc` ETH; series ends 2026-05-23). It is a daily close-only reference rate, not an exchange order book, so intraday stops, spread and liquidity can't be modelled from it. The data is not committed (licence and size). The scripts and full output are in `evidence/`.

**Code under test:** the repository's `walk_forward`, `research_pipeline`, `screen` and `simulate`, unmodified. Only the baseline comparisons and the random null are mine.

### 1. Single holdout (`walk_forward`, CLI default grid fast 2–10 × slow 12–40 = 261 configs)

| Asset | Costs (round-trip ×2) | Selected in-sample | In-sample return | Holdout return | Holdout max DD | **Buy & hold, same holdout** |
|---|---|---|---|---|---|---|
| BTC | 15 bps | 7/40 | +1,027% | **+93.5%** | 36.1% | **+111.3%** |
| BTC | 60 bps | 8/40 | +788% | +70.4% | 38.2% | +109.4% |
| BTC | 100 bps | 8/40 | +621% | +52.4% | 41.1% | +107.7% |
| ETH | 15 bps | 10/20 | +3,156% | **−15.5%** | 53.8% | **+7.7%** |
| ETH | 60 bps | 10/20 | +1,832% | −34.4% | 59.6% | +6.7% |
| ETH | 100 bps | 10/34 | +1,177% | +71.0% | 47.2% | +5.9% |

Holdout: 2023-11-16 to 2026-05-23 (30% of bars). In-sample returns overstate the holdout by one to two orders of magnitude. The ETH winner *flips sign* depending on the assumed cost level, a sign of a fragile, overfit selection rather than a stable effect.

### 2. Rolling evaluation (`research_pipeline`, train 730 d, test 180 d, embargo 1 d, 15 bps)

| Asset | Windows | Strategy > 0 | **Strategy > buy & hold** | Mean excess vs B&H | t-stat of excess |
|---|---|---|---|---|---|
| BTC | 12 | 8 | **2** | −15.1 pp | **−3.01** |
| ETH | 12 | 9 | **4** | −17.7 pp | −0.96 |

The selected parameters change almost every window (BTC: 5/40, 5/40, 10/20, 3/38, 9/33, 8/36, …; ETH: 7/25, 4/13, 10/19, 2/21, …), which is another sign of noise-fitting. The long/flat rule *does* reduce losses in bear windows (BTC window 5: −35.7% vs −58.0%; ETH window 5: −9.8% vs −71.9%). That is the familiar trend-following trade-off of lower drawdown in exchange for missing rallies, not an edge. I did not compute risk-adjusted comparisons; with 12 overlapping-regime windows there isn't enough statistical power for them to be conclusive.

### 3. Multiple-testing null (`screen`, 120 configs: 3 families × 10 lookbacks × 4 thresholds, train = first 70%)

| Asset | Best in-sample config | Its in-sample return | Same config on holdout | B&H holdout | **Best of 120 random long/flat strategies (in-sample)** |
|---|---|---|---|---|---|
| BTC | momentum 20 / 200 bps | +677% | +113.8% | +111.3% | **+890%** |
| ETH | momentum 20 / 0 bps | +2,187% | −6.7% | +7.7% | **+1,518%** |

Random strategies flip long/flat with a 10% daily probability. The "best" real configuration is in the same range as the luckiest random one. Ranking configurations by in-sample return, as `grid_search` and `screen` do, selects for luck.

## Statistical power

At 1% risk per trade with a stop, a strategy's result is measured in R (multiples of planned risk). To show that a mean of +0.2R/trade differs from zero with a typical per-trade standard deviation of about 1.2R at 95% confidence (two-sided), you need about (1.96 × 1.2 / 0.2)² ≈ **140 independent trades**. The daily SMA above makes 2–7 round trips per 180-day window (its `trades` field counts both legs, 4–14), so that sample would take one to three decades per configuration. An intraday strategy could reach that sample faster, but only if costs don't consume the edge (`08`). The planned "paper-trading observation period" has to be sized by the required trade count, not by calendar time.

## Methodology defects

1. **Research ≠ execution (F-13).** Backtests are 100%-allocation long/flat; execution is 1%-risk with stops. The research engine needs the same position-sizing, stop and cost model as the ledger. Better still, replay historical bars *through* `PendingOrders` and the ledger.
2. **Selection by maximum return** (`grid_search`, `screen`, `pipeline`) with no deflation. Add a random-signal null and a deflated-Sharpe or White's Reality Check style adjustment, or at minimum report the rank of the selected config among the nulls.
3. **No benchmark.** Every report should include buy-and-hold and an exposure-matched random baseline over the same window.
4. **Close-only data.** Stops and intraday behaviour can't be evaluated. Use OHLCV bars from the venue you would trade on, at the decision frequency.
5. **Metrics.** The Sharpe is non-annualized with population variance and no confidence interval. Add exposure, turnover, hit rate, average win/loss in R, and bootstrap confidence intervals.
6. **No experiment registry.** `audit.py` writes JSONL records but nothing calls it outside the tests. Record every configuration tried, not just the winner. Selection bias is invisible otherwise.

## Recommended validation framework (minimum)

1. **Data:** one venue, OHLCV at decision frequency, provenance recorded (venue, retrieval date, gaps). Hold out the **most recent 12 months entirely** and don't look at them until the final test.
2. **Hypotheses:** at most ~3 pre-registered families, each with a small, economically motivated parameter set. Write down the expected sign and mechanism *before* testing.
3. **Simulation:** the same sizing, stops, fees (venue tier-1 taker unless you can prove maker fills), spread and slippage as the ledger.
4. **Evaluation:** purged walk-forward. Report net R per trade with bootstrap CI, versus buy-and-hold and a random null with the same exposure and turnover. Require that the selected config beat ≥95% of nulls *and* have a positive lower CI bound on net expectancy.
5. **Promotion to paper:** only configs that pass step 4 on the untouched holdout. Paper-trade until the pre-computed trade count is reached (≈140 trades for +0.2R). Paper fills must be compared against the exchange's real quotes at the fill time.
6. **Kill criteria:** written in advance (for example, a paper-period net expectancy CI that excludes the backtest estimate, or a drawdown above X).
