"""
Performance analysis helpers for the research pipeline.

These functions operate on the daily backtest output produced by the simple
backtester in this repository. The goal is to keep the calculations easy to
audit and easy to explain in an interview.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


TRADING_DAYS_PER_YEAR = 252


def _prepare_daily_results(daily_results: pd.DataFrame) -> pd.DataFrame:
    """
    Validate and sort daily backtest results.
    """

    required_columns = ["date", "portfolio_return"]
    missing_columns = [column for column in required_columns if column not in daily_results.columns]
    if missing_columns:
        missing_text = ", ".join(missing_columns)
        raise ValueError(f"Missing required daily result columns: {missing_text}")

    data = daily_results.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data["portfolio_return"] = pd.to_numeric(data["portfolio_return"], errors="coerce").fillna(0.0)
    data = data.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    return data


def compute_cumulative_return_series(daily_results: pd.DataFrame) -> pd.Series:
    """
    Compute cumulative returns from daily portfolio returns.
    """

    data = _prepare_daily_results(daily_results)
    cumulative = (1.0 + data["portfolio_return"]).cumprod() - 1.0
    return pd.Series(cumulative.values, index=data["date"], name="cumulative_return")


def compute_drawdown_series(daily_results: pd.DataFrame) -> pd.Series:
    """
    Compute the drawdown series from daily portfolio returns.
    """

    data = _prepare_daily_results(daily_results)
    wealth = (1.0 + data["portfolio_return"]).cumprod()
    running_peak = wealth.cummax()
    drawdown = wealth / running_peak - 1.0
    return pd.Series(drawdown.values, index=data["date"], name="drawdown")


def compute_rolling_volatility_series(
    daily_results: pd.DataFrame,
    window: int = 21,
) -> pd.Series:
    """
    Compute annualized rolling volatility from daily returns.
    """

    data = _prepare_daily_results(daily_results)
    rolling_volatility = data["portfolio_return"].rolling(window=window, min_periods=window).std(ddof=0)
    rolling_volatility = rolling_volatility * (TRADING_DAYS_PER_YEAR ** 0.5)
    return pd.Series(rolling_volatility.values, index=data["date"], name="rolling_volatility")


def compute_rolling_sharpe_series(
    daily_results: pd.DataFrame,
    window: int = 63,
) -> pd.Series:
    """
    Compute annualized rolling Sharpe ratio from daily returns.

    If the rolling volatility is zero, the Sharpe value is set to missing.
    """

    data = _prepare_daily_results(daily_results)
    rolling_mean = data["portfolio_return"].rolling(window=window, min_periods=window).mean()
    rolling_std = data["portfolio_return"].rolling(window=window, min_periods=window).std(ddof=0)

    annualized_mean = rolling_mean * TRADING_DAYS_PER_YEAR
    annualized_std = rolling_std * (TRADING_DAYS_PER_YEAR ** 0.5)
    rolling_sharpe = annualized_mean / annualized_std.replace(0, pd.NA)

    return pd.Series(rolling_sharpe.values, index=data["date"], name="rolling_sharpe")


def compute_yearly_return_summary(daily_results: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate daily returns into simple calendar-year performance statistics.
    """

    data = _prepare_daily_results(daily_results)
    data["year"] = data["date"].dt.year

    summaries = []
    for year, group in data.groupby("year"):
        yearly_return = (1.0 + group["portfolio_return"]).prod() - 1.0
        yearly_volatility = group["portfolio_return"].std(ddof=0) * (TRADING_DAYS_PER_YEAR ** 0.5)
        summaries.append(
            {
                "year": int(year),
                "return": float(yearly_return),
                "volatility": float(yearly_volatility),
                "trading_days": int(len(group)),
            }
        )

    return pd.DataFrame(summaries)


def summarize_factor_diagnostics(
    factor_data: pd.DataFrame,
    factor_name: str,
) -> dict[str, float]:
    """
    Summarize simple diagnostics for one factor series.
    """

    if not isinstance(factor_data.index, pd.MultiIndex):
        raise ValueError("Factor data must use a MultiIndex of date and ticker.")

    if factor_name not in factor_data.columns:
        raise ValueError(f"Factor column not found: {factor_name}")

    data = factor_data[[factor_name]].reset_index().copy()
    signal_values = pd.to_numeric(data[factor_name], errors="coerce")

    diagnostics = {
        "factor_observations": float(len(data)),
        "non_missing_factor_observations": float(signal_values.notna().sum()),
        "factor_coverage_ratio": float(signal_values.notna().mean()),
        "factor_dates": float(data["date"].nunique()),
        "factor_tickers": float(data["ticker"].nunique()),
    }
    return diagnostics


def summarize_portfolio_diagnostics(
    daily_results: pd.DataFrame,
    rebalance_history: pd.DataFrame | None = None,
) -> dict[str, float]:
    """
    Summarize simple diagnostics for the realized portfolio path.
    """

    data = _prepare_daily_results(daily_results)

    diagnostics = {
        "backtest_days": float(len(data)),
        "active_days": float((data.get("holding_count", pd.Series(0, index=data.index)) > 0).sum()),
        "average_holding_count": float(data.get("holding_count", pd.Series(0, index=data.index)).fillna(0).mean()),
        "average_daily_turnover": float(data.get("turnover", pd.Series(0.0, index=data.index)).fillna(0.0).mean()),
        "total_transaction_cost": float(data.get("transaction_cost", pd.Series(0.0, index=data.index)).fillna(0.0).sum()),
    }

    if rebalance_history is not None and not rebalance_history.empty:
        diagnostics["rebalance_count"] = float(len(rebalance_history))
        diagnostics["average_selected_names"] = float(rebalance_history["holding_count"].fillna(0).mean())
    else:
        diagnostics["rebalance_count"] = 0.0
        diagnostics["average_selected_names"] = 0.0

    return diagnostics


def build_research_summary(
    daily_results: pd.DataFrame,
    factor_data: pd.DataFrame,
    factor_name: str,
    rebalance_history: pd.DataFrame | None = None,
) -> dict[str, object]:
    """
    Build a compact research summary bundle for reporting.
    """

    cumulative_returns = compute_cumulative_return_series(daily_results)
    drawdowns = compute_drawdown_series(daily_results)
    rolling_volatility = compute_rolling_volatility_series(daily_results)
    rolling_sharpe = compute_rolling_sharpe_series(daily_results)
    yearly_summary = compute_yearly_return_summary(daily_results)
    factor_diagnostics = summarize_factor_diagnostics(factor_data, factor_name)
    portfolio_diagnostics = summarize_portfolio_diagnostics(daily_results, rebalance_history=rebalance_history)

    return {
        "cumulative_returns": cumulative_returns,
        "drawdowns": drawdowns,
        "rolling_volatility": rolling_volatility,
        "rolling_sharpe": rolling_sharpe,
        "yearly_summary": yearly_summary,
        "factor_diagnostics": factor_diagnostics,
        "portfolio_diagnostics": portfolio_diagnostics,
    }
