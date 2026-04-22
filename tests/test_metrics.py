from pathlib import Path
import sys

import pandas as pd


SRC_DIR = Path(__file__).resolve().parents[1] / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from metrics import compute_cumulative_return_series, compute_drawdown_series, compute_yearly_return_summary


def test_metrics_series_and_yearly_summary() -> None:
    daily_results = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"]),
            "portfolio_return": [0.10, -0.05, 0.02],
        }
    )

    cumulative = compute_cumulative_return_series(daily_results)
    drawdown = compute_drawdown_series(daily_results)
    yearly = compute_yearly_return_summary(daily_results)

    assert abs(cumulative.iloc[-1] - 0.0659) < 1e-10
    assert abs(drawdown.iloc[1] + 0.05) < 1e-10
    assert yearly.iloc[0]["year"] == 2024
    assert abs(yearly.iloc[0]["return"] - 0.0659) < 1e-10
