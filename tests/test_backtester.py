from pathlib import Path
import sys

import pandas as pd


SRC_DIR = Path(__file__).resolve().parents[1] / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from backtester import run_cross_sectional_backtest


def test_backtest_uses_next_day_activation_and_transaction_costs() -> None:
    dates = pd.to_datetime(
        [
            "2024-01-30",
            "2024-01-31",
            "2024-02-01",
            "2024-02-02",
        ]
    )

    price_data = pd.DataFrame(
        [
            {"date": dates[0], "ticker": "AAA", "close": 100.0},
            {"date": dates[1], "ticker": "AAA", "close": 100.0},
            {"date": dates[2], "ticker": "AAA", "close": 110.0},
            {"date": dates[3], "ticker": "AAA", "close": 110.0},
            {"date": dates[0], "ticker": "BBB", "close": 100.0},
            {"date": dates[1], "ticker": "BBB", "close": 100.0},
            {"date": dates[2], "ticker": "BBB", "close": 100.0},
            {"date": dates[3], "ticker": "BBB", "close": 100.0},
        ]
    )

    factor_data = pd.DataFrame(
        {
            "date": [dates[1], dates[1]],
            "ticker": ["AAA", "BBB"],
            "momentum_1m": [2.0, 1.0],
        }
    ).set_index(["date", "ticker"])

    daily_results, metrics, rebalance_history = run_cross_sectional_backtest(
        price_data=price_data,
        factor_data=factor_data,
        factor_name="momentum_1m",
        top_n=1,
        transaction_cost_bps=10.0,
    )

    feb1_row = daily_results[daily_results["date"] == dates[2]].iloc[0]

    assert rebalance_history.iloc[0]["signal_date"] == dates[1]
    assert rebalance_history.iloc[0]["effective_date"] == dates[2]
    assert rebalance_history.iloc[0]["selected_names"] == "AAA"
    assert abs(feb1_row["portfolio_return"] - 0.099) < 1e-12
    assert abs(feb1_row["turnover"] - 1.0) < 1e-12
    assert "annualized_return" in metrics
