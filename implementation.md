# Implementation Notes

This document explains the minimal optimization layer added to the project and why it was implemented this way. The goal is to move from a single illustrative backtest toward a more reproducible research process, while keeping the project modest and transparent.

## Why Add Optimization Carefully?

Optimization can easily make a backtest look better without making the underlying strategy more reliable. A naive process would test many parameter combinations and then report the best result over the full sample. That creates a high risk of overfitting.

This project uses a small walk-forward structure instead:

- train period: observe how candidate settings behave
- validation period: choose one parameter setting
- test period: report the chosen setting on later, untouched data

The test period is not used for choosing parameters. This does not prove that a strategy will work in live markets, but it is a more disciplined process than optimizing on the full dataset.

## What Was Implemented

The optimization layer is implemented in `src/optimizer.py`.

It reuses the existing project modules:

- `src/factor_library.py` computes factor values
- `src/backtester.py` runs the long-only monthly rebalance strategy
- `src/backtester.py` also provides the core performance metric calculation

No new strategy type was added. The optimizer only varies existing strategy inputs.

## Optimization Grid

The default grid is intentionally small:

```text
factor_name:
  momentum_1m
  momentum_3m
  short_term_reversal
  rolling_volatility
  liquidity_dollar_volume

top_n:
  1
  3
  5

transaction_cost_bps:
  5
  10
  25
```

The demo script narrows the factor list to:

```text
momentum_1m
momentum_3m
short_term_reversal
```

This keeps runtime and interpretation simple for the current compact Alpha Vantage dataset.

## Key Files

```text
src/optimizer.py
notebooks/optimization_demo.py
tests/test_optimizer.py
implementation.md
```

## Main Functions

### `make_time_splits`

Creates chronological train, validation, and test date ranges from the available price data.

Default split:

```text
train: first 50% of dates
validation: next 25% of dates
test: final 25% of dates
```

Why this matters:

- financial data is time ordered
- future data should not influence past decisions
- a chronological split is more realistic than random train/test splitting

### `run_walk_forward_optimization`

Runs each candidate parameter set through the existing factor and backtest pipeline.

For each configuration, it records:

- train metrics
- validation metrics
- test metrics
- factor name
- top N selection size
- transaction cost assumption
- date split boundaries

The selected configuration is chosen by validation Sharpe ratio. Test-period metrics are reported afterward, but they are not used for selection.

Configurations with no active validation-period holdings are excluded from selection when at least one candidate has active validation exposure. This prevents a no-trade configuration from looking attractive only because it has zero volatility and zero drawdown.

## How To Run

First download real data:

```bash
$env:ALPHAVANTAGE_API_KEY="your_api_key_here"
python notebooks\download_real_data.py --start-date 2025-01-01 --end-date 2026-12-31
```

Then run the optimization demo:

```bash
python notebooks\optimization_demo.py
```

Run the optimizer tests:

```bash
python -m pytest tests\test_optimizer.py -p no:cacheprovider
```

## What The Demo Prints

The demo prints:

- the real data file being used
- the research price column
- the top candidate configurations ranked by validation Sharpe
- the selected configuration
- test-period performance metrics for the selected configuration
- a preview of daily backtest results
- a short interpretation note

## Why This Is Still Minimal

This implementation avoids advanced features on purpose. It does not add:

- long-short portfolios
- leverage
- optimizer-based portfolio construction
- factor blending
- benchmark-relative evaluation
- sector constraints
- execution modeling
- live trading integration

Those may be useful later, but they would make the project harder to audit before the basic research process is mature.

## Important Limitations

The current optimizer is still exploratory.

Known limitations:

- the Alpha Vantage free endpoint provides compact recent history only
- the ticker universe is fixed
- survivorship bias is not addressed
- `adjusted_close` currently equals `close` because the free endpoint does not provide adjusted prices
- transaction costs are simplified
- the validation and test periods may be short if the dataset is short
- high validation performance can still happen by chance
- no paper trading or live execution checks are included

Because of these limitations, optimization output should be treated as a research diagnostic rather than a trading recommendation.

## How This Moves The Project Forward

Before this change, the project could run a single backtest with one chosen factor and one chosen parameter set. After this change, the project can compare a small set of candidate configurations using a repeatable process.

This improves the project in three ways:

- results are easier to reproduce
- assumptions are easier to inspect
- the workflow makes overfitting more visible

The main value is process quality, not higher reported performance.

## Likely Questions And Good Answers

### Why use a validation period?

The validation period separates parameter selection from final evaluation. If parameters are chosen using the full sample, the reported results can be overly optimistic.

### Why not optimize more parameters?

The dataset is short and the strategy is simple. A larger grid would increase overfitting risk without adding much research value at this stage.

### Why use chronological splits instead of random splits?

Financial time series are ordered. Random splits can leak future regimes into the training process and make the research setup less realistic.

### Why select by Sharpe ratio?

Sharpe ratio is a compact risk-adjusted performance measure. It is not perfect, but it is simple and already available in the current metric layer.

### Why still report the test period?

The test period provides a later-sample check on the chosen configuration. It should be interpreted cautiously, especially with short data history.

### Does this prove the strategy is profitable?

No. It only provides a more disciplined backtesting workflow. A real deployment would require longer data, stronger bias controls, transaction cost analysis, paper trading, and operational risk controls.

### What is the biggest current weakness?

The data. The free Alpha Vantage endpoint gives compact recent history and does not provide true adjusted prices or survivorship-bias-free universe data.

### What would be the next improvement?

The next improvement should be a better historical dataset with adjusted prices and a better-defined universe. After that, factor diagnostics such as rank IC and benchmark-relative analysis would be natural next steps.
