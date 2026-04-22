"""
Simple cross-sectional equity backtester.

This module implements a transparent daily backtesting engine for a
long-only cross-sectional factor strategy. The design goal is clarity over
complexity so the mechanics are easy to explain in an interview setting.

Main assumptions:
- signals are observed on each rebalance date
- the portfolio is formed using those signals and becomes active on the
  next trading day
- weights are equal across selected names
- returns are close-to-close daily returns
- transaction costs are applied on rebalance days based on turnover
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


TRADING_DAYS_PER_YEAR = 252


def _resolve_price_col(frame: pd.DataFrame, price_col: str) -> str:
    """
    Resolve the research price column with a simple compatibility fallback.
    """

    if price_col in frame.columns:
        return price_col

    if price_col == "adjusted_close" and "close" in frame.columns:
        return "close"

    raise ValueError(f"Missing required price column for backtesting: {price_col}")


def _prepare_price_data(frame: pd.DataFrame, price_col: str = "adjusted_close") -> pd.DataFrame:
    """
    Validate and prepare cleaned OHLCV data for backtesting.
    """

    required_columns = ["date", "ticker"]
    missing_columns = [column for column in required_columns if column not in frame.columns]
    if missing_columns:
        missing_text = ", ".join(missing_columns)
        raise ValueError(f"Missing required price columns: {missing_text}")

    data = frame.copy()
    resolved_price_col = _resolve_price_col(data, price_col)
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data["ticker"] = data["ticker"].astype(str).str.strip().str.upper()
    data["research_price"] = pd.to_numeric(data[resolved_price_col], errors="coerce")
    data = data.dropna(subset=["date", "ticker", "research_price"])
    data = data.sort_values(["ticker", "date"]).reset_index(drop=True)
    data["daily_return"] = data.groupby("ticker")["research_price"].pct_change()
    return data


def _prepare_factor_data(factor_frame: pd.DataFrame, factor_name: str) -> pd.DataFrame:
    """
    Validate and reshape one factor series for backtesting.
    """

    if not isinstance(factor_frame.index, pd.MultiIndex):
        raise ValueError("Factor data must use a MultiIndex of date and ticker.")

    if factor_name not in factor_frame.columns:
        raise ValueError(f"Factor column not found: {factor_name}")

    data = factor_frame[[factor_name]].reset_index().copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data["ticker"] = data["ticker"].astype(str).str.strip().str.upper()
    data[factor_name] = pd.to_numeric(data[factor_name], errors="coerce")
    data = data.dropna(subset=["date", "ticker"])
    return data


def _get_monthly_rebalance_dates(dates: pd.Series) -> list[pd.Timestamp]:
    """
    Select the last available trading date in each calendar month.
    """

    unique_dates = pd.Series(pd.to_datetime(dates).dropna().unique()).sort_values()
    rebalance_dates = unique_dates.groupby(unique_dates.dt.to_period("M")).max()
    return list(pd.to_datetime(rebalance_dates))


def _get_next_trading_date(trading_dates: list[pd.Timestamp], current_date: pd.Timestamp) -> pd.Timestamp | None:
    """
    Return the next trading date after the current date.
    """

    for trading_date in trading_dates:
        if trading_date > current_date:
            return trading_date
    return None


def _select_long_portfolio(
    factor_slice: pd.DataFrame,
    factor_name: str,
    top_quantile: float | None = 0.2,
    top_n: int | None = None,
) -> dict[str, float]:
    """
    Select top-ranked names and assign equal weights.
    """

    cross_section = factor_slice.dropna(subset=[factor_name]).sort_values(factor_name, ascending=False)

    if cross_section.empty:
        return {}

    if top_n is not None:
        selected = cross_section.head(top_n)
    else:
        if top_quantile is None or not 0 < top_quantile <= 1:
            raise ValueError("top_quantile must be between 0 and 1 when top_n is not used.")
        selected_count = max(1, int(len(cross_section) * top_quantile))
        selected = cross_section.head(selected_count)

    weight = 1.0 / len(selected)
    return {ticker: weight for ticker in selected["ticker"]}


def _compute_turnover(old_weights: dict[str, float], new_weights: dict[str, float]) -> float:
    """
    Compute one-way portfolio turnover from weight changes.
    """

    tickers = set(old_weights) | set(new_weights)
    return sum(abs(new_weights.get(ticker, 0.0) - old_weights.get(ticker, 0.0)) for ticker in tickers)


def compute_performance_metrics(daily_results: pd.DataFrame) -> dict[str, float]:
    """
    Compute summary backtest statistics from daily returns.
    """

    returns = daily_results["portfolio_return"].fillna(0.0)
    cumulative_curve = (1.0 + returns).cumprod()

    if len(returns) == 0:
        return {
            "annualized_return": 0.0,
            "annualized_volatility": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
            "average_daily_turnover": 0.0,
        }

    annualized_return = cumulative_curve.iloc[-1] ** (TRADING_DAYS_PER_YEAR / len(returns)) - 1
    annualized_volatility = returns.std(ddof=0) * (TRADING_DAYS_PER_YEAR ** 0.5)

    if annualized_volatility == 0:
        sharpe_ratio = 0.0
    else:
        sharpe_ratio = annualized_return / annualized_volatility

    running_peak = cumulative_curve.cummax()
    drawdown = cumulative_curve / running_peak - 1.0
    max_drawdown = drawdown.min()

    return {
        "annualized_return": float(annualized_return),
        "annualized_volatility": float(annualized_volatility),
        "sharpe_ratio": float(sharpe_ratio),
        "max_drawdown": float(max_drawdown),
        "average_daily_turnover": float(daily_results["turnover"].fillna(0.0).mean()),
    }


def run_cross_sectional_backtest(
    price_data: pd.DataFrame,
    factor_data: pd.DataFrame,
    factor_name: str,
    top_quantile: float | None = 0.2,
    top_n: int | None = None,
    transaction_cost_bps: float = 10.0,
    price_col: str = "adjusted_close",
) -> tuple[pd.DataFrame, dict[str, float], pd.DataFrame]:
    """
    Run a simple long-only monthly rebalanced factor backtest.

    Parameters
    ----------
    price_data:
        Cleaned daily OHLCV data.
    factor_data:
        MultiIndex factor DataFrame from the factor library.
    factor_name:
        Name of the factor column used for ranking.
    top_quantile:
        Fraction of names to hold on each rebalance date if ``top_n`` is not
        supplied.
    top_n:
        Fixed number of names to hold. If provided, this overrides
        ``top_quantile``.
    transaction_cost_bps:
        One-way transaction cost in basis points applied to turnover on each
        rebalance date.

    Returns
    -------
    tuple[pandas.DataFrame, dict[str, float], pandas.DataFrame]
        Daily results, summary metrics, and a rebalance history table.
    """

    prices = _prepare_price_data(price_data, price_col=price_col)
    factors = _prepare_factor_data(factor_data, factor_name)

    trading_dates = sorted(prices["date"].drop_duplicates().tolist())
    rebalance_dates = _get_monthly_rebalance_dates(factors["date"])

    scheduled_weights: dict[pd.Timestamp, dict[str, float]] = {}
    rebalance_records: list[dict[str, object]] = []

    for rebalance_date in rebalance_dates:
        factor_slice = factors[factors["date"] == rebalance_date][["ticker", factor_name]].copy()
        target_weights = _select_long_portfolio(
            factor_slice,
            factor_name=factor_name,
            top_quantile=top_quantile,
            top_n=top_n,
        )

        effective_date = _get_next_trading_date(trading_dates, rebalance_date)
        if effective_date is None:
            continue

        scheduled_weights[effective_date] = target_weights
        rebalance_records.append(
            {
                "signal_date": rebalance_date,
                "effective_date": effective_date,
                "selected_names": ",".join(sorted(target_weights.keys())),
                "holding_count": len(target_weights),
            }
        )

    returns_by_date = prices.pivot(index="date", columns="ticker", values="daily_return").sort_index()

    current_weights: dict[str, float] = {}
    daily_records: list[dict[str, object]] = []
    cost_rate = transaction_cost_bps / 10000.0

    for trading_date in returns_by_date.index:
        turnover = 0.0
        transaction_cost = 0.0

        if trading_date in scheduled_weights:
            target_weights = scheduled_weights[trading_date]
            turnover = _compute_turnover(current_weights, target_weights)
            transaction_cost = turnover * cost_rate
            current_weights = target_weights

        day_returns = returns_by_date.loc[trading_date].fillna(0.0)
        gross_return = sum(current_weights.get(ticker, 0.0) * day_returns.get(ticker, 0.0) for ticker in day_returns.index)
        net_return = gross_return - transaction_cost

        daily_records.append(
            {
                "date": trading_date,
                "portfolio_return": net_return,
                "gross_return": gross_return,
                "transaction_cost": transaction_cost,
                "turnover": turnover,
                "holding_count": len(current_weights),
            }
        )

    daily_results = pd.DataFrame(daily_records).sort_values("date").reset_index(drop=True)
    daily_results["cumulative_return"] = (1.0 + daily_results["portfolio_return"]).cumprod() - 1.0

    metrics = compute_performance_metrics(daily_results)
    rebalance_history = pd.DataFrame(rebalance_records)

    return daily_results, metrics, rebalance_history
