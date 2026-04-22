from pathlib import Path
import sys

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from backtester import run_cross_sectional_backtest
from factor_library import compute_factor_set


def main() -> None:
    data_file = PROJECT_ROOT / "data" / "processed" / "real_daily_prices.csv"
    price_col = "adjusted_close"

    if not data_file.exists():
        raise FileNotFoundError(f"Real dataset not found: {data_file}. Run notebooks\\download_real_data.py first.")

    real_data = pd.read_csv(data_file, parse_dates=["date"])
    factor_data = compute_factor_set(real_data, factors=["momentum_1m"], price_col=price_col)

    daily_results, metrics, rebalance_history = run_cross_sectional_backtest(
        price_data=real_data,
        factor_data=factor_data,
        factor_name="momentum_1m",
        top_n=1,
        transaction_cost_bps=10.0,
        price_col=price_col,
    )

    print("Loaded real data from:")
    print(data_file)
    print()
    print(f"Research price column: {price_col}")
    print()
    print("Rebalance history:")
    print(rebalance_history.to_string(index=False))
    print()
    print("Daily results preview:")
    print(daily_results.tail(10).to_string(index=False))
    print()
    print("Performance metrics:")
    for key, value in metrics.items():
        print(f"{key}: {value:.6f}")


if __name__ == "__main__":
    main()
