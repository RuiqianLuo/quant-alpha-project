"""
Minimal walk-forward optimization utilities.

The optimizer intentionally stays small and conservative. It reuses the
existing factor library and backtester, tests a limited parameter grid, and
selects parameters using a validation period instead of the full sample.
"""

from __future__ import annotations

from itertools import product

import pandas as pd

from backtester import compute_performance_metrics, run_cross_sectional_backtest
from factor_library import compute_factor_set


DEFAULT_FACTORS = [
    "momentum_1m",
    "momentum_3m",
    "short_term_reversal",
    "rolling_volatility",
    "liquidity_dollar_volume",
]


def make_time_splits(
    price_data: pd.DataFrame,
    train_fraction: float = 0.5,
    validation_fraction: float = 0.25,
) -> dict[str, pd.Timestamp]:
    """
    Create simple chronological train, validation, and test date splits.

    The test period is left untouched during parameter selection. This is a
    basic guard against choosing parameters that only work in-sample.
    """

    if "date" not in price_data.columns:
        raise ValueError("price_data must contain a date column.")

    dates = pd.Series(pd.to_datetime(price_data["date"], errors="coerce").dropna().unique()).sort_values()
    dates = dates.reset_index(drop=True)

    if len(dates) < 12:
        raise ValueError("At least 12 unique dates are required for train/validation/test splits.")

    if not 0 < train_fraction < 1:
        raise ValueError("train_fraction must be between 0 and 1.")

    if not 0 < validation_fraction < 1:
        raise ValueError("validation_fraction must be between 0 and 1.")

    if train_fraction + validation_fraction >= 1:
        raise ValueError("train_fraction + validation_fraction must be less than 1.")

    train_end_index = max(0, int(len(dates) * train_fraction) - 1)
    validation_end_index = max(train_end_index + 1, int(len(dates) * (train_fraction + validation_fraction)) - 1)
    validation_end_index = min(validation_end_index, len(dates) - 2)

    return {
        "train_start": dates.iloc[0],
        "train_end": dates.iloc[train_end_index],
        "validation_start": dates.iloc[train_end_index + 1],
        "validation_end": dates.iloc[validation_end_index],
        "test_start": dates.iloc[validation_end_index + 1],
        "test_end": dates.iloc[-1],
    }


def slice_daily_results(
    daily_results: pd.DataFrame,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> pd.DataFrame:
    """
    Slice daily backtest results to an inclusive date range.
    """

    data = daily_results.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    mask = (data["date"] >= pd.to_datetime(start_date)) & (data["date"] <= pd.to_datetime(end_date))
    return data[mask].sort_values("date").reset_index(drop=True)


def _prefixed_metrics(daily_results: pd.DataFrame, prefix: str) -> dict[str, float]:
    """
    Compute performance metrics and prefix the metric names.
    """

    metrics = compute_performance_metrics(daily_results)
    return {f"{prefix}_{name}": value for name, value in metrics.items()}


def _active_day_count(daily_results: pd.DataFrame) -> int:
    """
    Count days with at least one active holding.
    """

    if "holding_count" not in daily_results.columns:
        return 0

    return int((daily_results["holding_count"].fillna(0) > 0).sum())


def run_walk_forward_optimization(
    price_data: pd.DataFrame,
    factor_names: list[str] | None = None,
    top_n_grid: list[int] | None = None,
    transaction_cost_bps_grid: list[float] | None = None,
    price_col: str = "adjusted_close",
    train_fraction: float = 0.5,
    validation_fraction: float = 0.25,
) -> tuple[pd.DataFrame, dict[str, object], pd.DataFrame]:
    """
    Run a small walk-forward grid search over existing strategy parameters.

    Parameters are selected using validation Sharpe ratio. The final test
    metrics are reported for the selected configuration but are not used for
    choosing it.
    """

    selected_factors = factor_names or DEFAULT_FACTORS
    selected_top_ns = top_n_grid or [1, 3, 5]
    selected_costs = transaction_cost_bps_grid or [5.0, 10.0, 25.0]
    splits = make_time_splits(
        price_data,
        train_fraction=train_fraction,
        validation_fraction=validation_fraction,
    )

    rows: list[dict[str, object]] = []
    daily_results_by_config: dict[str, pd.DataFrame] = {}

    for factor_name, top_n, cost_bps in product(selected_factors, selected_top_ns, selected_costs):
        factor_data = compute_factor_set(price_data, factors=[factor_name], price_col=price_col)
        daily_results, _, _ = run_cross_sectional_backtest(
            price_data=price_data,
            factor_data=factor_data,
            factor_name=factor_name,
            top_n=top_n,
            transaction_cost_bps=cost_bps,
            price_col=price_col,
        )

        train_results = slice_daily_results(daily_results, splits["train_start"], splits["train_end"])
        validation_results = slice_daily_results(daily_results, splits["validation_start"], splits["validation_end"])
        test_results = slice_daily_results(daily_results, splits["test_start"], splits["test_end"])

        config_id = f"{factor_name}|top_n={top_n}|cost_bps={cost_bps}"
        daily_results_by_config[config_id] = daily_results

        row: dict[str, object] = {
            "config_id": config_id,
            "factor_name": factor_name,
            "top_n": top_n,
            "transaction_cost_bps": cost_bps,
            "price_col": price_col,
            "train_start": splits["train_start"],
            "train_end": splits["train_end"],
            "validation_start": splits["validation_start"],
            "validation_end": splits["validation_end"],
            "test_start": splits["test_start"],
            "test_end": splits["test_end"],
            "train_days": len(train_results),
            "validation_days": len(validation_results),
            "test_days": len(test_results),
            "train_active_days": _active_day_count(train_results),
            "validation_active_days": _active_day_count(validation_results),
            "test_active_days": _active_day_count(test_results),
        }
        row.update(_prefixed_metrics(train_results, "train"))
        row.update(_prefixed_metrics(validation_results, "validation"))
        row.update(_prefixed_metrics(test_results, "test"))
        rows.append(row)

    results = pd.DataFrame(rows)
    if results.empty:
        raise ValueError("No optimization results were produced.")

    selection_pool = results[results["validation_active_days"] > 0].copy()
    if selection_pool.empty:
        selection_pool = results.copy()

    ranked_selection_pool = selection_pool.sort_values(
        by=[
            "validation_sharpe_ratio",
            "validation_annualized_return",
            "validation_max_drawdown",
            "validation_average_daily_turnover",
        ],
        ascending=[False, False, False, True],
    ).reset_index(drop=True)

    best_config = ranked_selection_pool.iloc[0].to_dict()
    best_daily_results = daily_results_by_config[str(best_config["config_id"])]
    ranked_results = pd.concat(
        [
            ranked_selection_pool,
            results[~results["config_id"].isin(ranked_selection_pool["config_id"])],
        ],
        ignore_index=True,
    )
    return ranked_results, best_config, best_daily_results
