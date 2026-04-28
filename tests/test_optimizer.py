from pathlib import Path
import sys

import pandas as pd


SRC_DIR = Path(__file__).resolve().parents[1] / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from optimizer import make_time_splits, run_walk_forward_optimization


def test_walk_forward_optimization_returns_ranked_results() -> None:
    dates = pd.bdate_range("2024-01-01", periods=90)
    rows = []

    for index, date in enumerate(dates):
        rows.append(
            {
                "date": date,
                "ticker": "AAA",
                "close": 100.0 + index,
                "adjusted_close": 100.0 + index,
                "volume": 1000,
            }
        )
        rows.append(
            {
                "date": date,
                "ticker": "BBB",
                "close": 100.0 + index * 0.2,
                "adjusted_close": 100.0 + index * 0.2,
                "volume": 1000,
            }
        )

    price_data = pd.DataFrame(rows)

    results, best_config, best_daily_results = run_walk_forward_optimization(
        price_data=price_data,
        factor_names=["momentum_1m"],
        top_n_grid=[1, 2],
        transaction_cost_bps_grid=[0.0],
        price_col="adjusted_close",
    )

    assert len(results) == 2
    assert best_config["factor_name"] == "momentum_1m"
    assert best_config["top_n"] in [1, 2]
    assert "validation_sharpe_ratio" in results.columns
    assert not best_daily_results.empty


def test_make_time_splits_are_chronological() -> None:
    dates = pd.bdate_range("2024-01-01", periods=20)
    price_data = pd.DataFrame({"date": dates, "ticker": ["AAA"] * len(dates), "close": range(len(dates))})

    splits = make_time_splits(price_data)

    assert splits["train_start"] <= splits["train_end"]
    assert splits["train_end"] < splits["validation_start"]
    assert splits["validation_end"] < splits["test_start"]
    assert splits["test_start"] <= splits["test_end"]
