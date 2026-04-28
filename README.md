# Cross-Sectional Equity Alpha Research Platform

This repository is a small but structured quantitative research project for studying simple cross-sectional equity signals in U.S. stocks. It is organized as a transparent, modular, and reproducible research pipeline rather than a production trading system.

## Motivation

Many educational quant projects either focus only on model ideas or jump too quickly to performance summaries without showing the full research workflow. This project takes a different approach: start with a simple data pipeline, build a small factor library, run a transparent backtest, and report results with clear assumptions and limitations.

The emphasis is on:

- modular research code
- reproducible analysis
- transparent assumptions
- readable implementations
- modest interpretation of results

## Research Question

Can a small set of standard cross-sectional equity characteristics, computed from daily OHLCV data, be used to rank stocks and evaluate a simple monthly rebalanced long-only strategy framework?

This project does not claim that the current factors are robust or investable. The goal is to provide an educational research framework that can be extended carefully over time.

## Current Scope

The repository currently includes:

- a CSV-based daily OHLCV data loader and cleaner
- an Alpha Vantage downloader for free daily U.S. equity data
- a factor library for several simple daily equity factors
- a transparent monthly rebalanced long-only backtester
- a minimal walk-forward optimization layer
- a lightweight performance analysis and reporting layer
- unit tests and runnable demo scripts

It does not yet include benchmark comparisons, sector controls, advanced data sourcing, long-short construction, or a realistic institutional-grade simulation engine.

## Repo Structure

```text
data/
  raw/
    alpha_vantage/
    example_daily_prices.csv
  processed/
    example_daily_prices.csv
    real_daily_prices.csv
notebooks/
  download_real_data.py
  factor_demo.py
  backtest_demo.py
  optimization_demo.py
  research_demo.py
reports/
  cumulative_returns.png
  drawdowns.png
src/
  alpha_vantage_loader.py
  data_loader.py
  factor_library.py
  backtester.py
  optimizer.py
  metrics.py
tests/
  test_alpha_vantage_loader.py
  test_data_loader.py
  test_factor_library.py
  test_backtester.py
  test_optimizer.py
  test_metrics.py
requirements.txt
README.md
```

## Data Source And Assumptions

The repository currently supports two data paths:

- local CSV files placed under `data/raw/`
- Alpha Vantage `TIME_SERIES_DAILY` downloads saved under `data/raw/alpha_vantage/`

A small synthetic example file is still included for early development and simple local checks, while the main demo workflow now uses `data/processed/real_daily_prices.csv`.

Current assumptions:

- input data is daily U.S. equity OHLCV data
- each row represents one `date` and `ticker`
- the loader expects fields equivalent to `date`, `ticker`, `open`, `high`, `low`, `close`, and `volume`
- cleaned or normalized files are saved under `data/processed/`
- the Alpha Vantage free endpoint provides open, high, low, close, and volume
- the normalized output keeps an `adjusted_close` column for compatibility, but currently sets it equal to `close`
- dividend and split fields are retained in the schema for compatibility and currently default to `0.0` and `1.0`
- the first real-data version uses a fixed ticker universe
- the first real-data version does not solve survivorship bias

Outputs from the current real-data workflow should still be treated as exploratory. The free Alpha Vantage endpoint uses compact recent history only, and the current setup does not address several common biases in empirical equity research.

## Factor Definitions

The factor library in `src/factor_library.py` currently includes:

- `momentum_1m`: approximate 1-month momentum using lagged prices
- `momentum_3m`: approximate 3-month momentum using lagged prices
- `short_term_reversal`: negative of recent short-horizon return
- `rolling_volatility`: rolling volatility based on lagged daily returns
- `liquidity_dollar_volume`: rolling average dollar volume as a simple liquidity proxy

Implementation notes:

- factors are computed by `date` and `ticker`
- outputs use a MultiIndex on `date` and `ticker`
- factor inputs are lagged where appropriate so the factor at date `t` is based on information available through `t-1`
- a configurable `price_col` is supported, with `adjusted_close` used as the default research price column

## Backtest Methodology

The backtest in `src/backtester.py` is intentionally simple:

- strategy type: long-only
- selection rule: rank the cross section by a chosen factor on each rebalance date
- portfolio formation: select the top quantile or top `N` names
- weighting: equal weight across selected names
- rebalance schedule: monthly, using the last available trading day of each month as the signal date
- execution timing: selected weights become active on the next trading day to reduce lookahead bias
- return model: close-to-close daily returns using the configured research price column

This design is intentionally transparent and meant for educational research rather than production execution.

## Transaction Cost Assumption

The default transaction cost assumption is a one-way cost of `10` basis points applied to turnover on rebalance days.

In the current implementation:

- turnover is measured as total absolute change in portfolio weights
- transaction cost is `turnover * transaction_cost_bps / 10000`

This is a simplified assumption and should be treated as a basic educational approximation, not a market-impact model.

## Evaluation Metrics

The project currently reports the following backtest and analysis outputs:

- daily portfolio returns
- cumulative returns
- turnover
- annualized return
- annualized volatility
- Sharpe ratio
- max drawdown
- drawdown series
- rolling volatility
- rolling Sharpe ratio when enough history exists
- yearly return summary
- basic factor diagnostics such as coverage and observation count
- basic portfolio diagnostics such as active days, holding count, turnover, and total transaction costs

The reporting layer is implemented in `src/metrics.py`.

## How To Run The Pipeline

### 1. Create a virtual environment

```bash
python -m venv .venv
```

On Windows PowerShell:

```bash
.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the unit tests

Run the test files one by one:

```bash
python -m pytest tests\test_alpha_vantage_loader.py -p no:cacheprovider
python -m pytest tests\test_data_loader.py -p no:cacheprovider
python -m pytest tests\test_factor_library.py -p no:cacheprovider
python -m pytest tests\test_backtester.py -p no:cacheprovider
python -m pytest tests\test_optimizer.py -p no:cacheprovider
python -m pytest tests\test_metrics.py -p no:cacheprovider
```

### 4. Set the Alpha Vantage API key

Option 1: set the environment variable in PowerShell:

```bash
$env:ALPHAVANTAGE_API_KEY="your_api_key_here"
```

Option 2: create a repo-root `.env` file:

```bash
ALPHAVANTAGE_API_KEY=your_api_key_here
```

The downloader checks the environment variable first, then falls back to `.env`.

### 5. Download real daily data with the free Alpha Vantage workflow

```bash
python notebooks\download_real_data.py --start-date 2025-01-01 --end-date 2026-12-31
```

This:

- downloads daily data from Alpha Vantage `TIME_SERIES_DAILY` using `outputsize=compact`
- saves per-ticker raw API responses under `data/raw/alpha_vantage/`
- saves one combined normalized file to `data/processed/real_daily_prices.csv`
- prints the returned date coverage before filtering and warns if the requested date range does not overlap the compact history window

### 6. Run the factor demo

```bash
python notebooks\factor_demo.py
```

This:

- loads `data/processed/real_daily_prices.csv`
- uses `adjusted_close` as the default research price column
- computes factor values
- prints a preview of the factor output

### 7. Run the backtest demo

```bash
python notebooks\backtest_demo.py
```

This:

- loads `data/processed/real_daily_prices.csv`
- computes the selected factor
- runs the monthly long-only backtest
- prints rebalance history, daily results preview, and summary metrics

### 8. Run the optimization demo

```bash
python notebooks\optimization_demo.py
```

This:

- loads `data/processed/real_daily_prices.csv`
- tests a small grid of existing factors, top-N choices, and transaction cost assumptions
- selects parameters using validation-period Sharpe ratio
- reports test-period metrics separately

### 9. Run the full research demo

```bash
python notebooks\research_demo.py
```

This end-to-end script:

- loads `data/processed/real_daily_prices.csv`
- computes factors
- runs the backtest
- builds performance and diagnostic summaries
- saves cumulative return and drawdown plots under `reports/`
- prints a short interpretation section

## Limitations

This project is intentionally modest in scope. Important limitations include:

- the first real-data downloader uses a fixed ticker universe
- the first real-data downloader does not address survivorship bias
- the free Alpha Vantage endpoint provides only compact recent history
- the free Alpha Vantage endpoint does not provide adjusted-close or corporate-action fields
- `adjusted_close` is currently retained for compatibility and is set equal to `close`
- there is no benchmark-relative evaluation yet
- there is no survivorship-bias handling or delisting treatment
- there is no corporate actions pipeline beyond simple column handling
- there is no sector-neutralization, risk model, or optimization layer
- the backtest assumes simple close-to-close returns and simplified trading costs
- the current outputs are useful for illustrating a research workflow, not for making investment claims

## Future Improvements

Reasonable next extensions for the project include:

- replace the compact free-endpoint history with a richer historical dataset
- add benchmark and universe definitions
- add sector or industry classifications
- test factor rank IC and other predictive diagnostics
- add more robust transaction cost and slippage assumptions
- add portfolio constraints and risk controls
- compare multiple factors side by side
- add benchmark-relative reporting and more complete tear sheets
- improve data validation and reproducibility for larger datasets
