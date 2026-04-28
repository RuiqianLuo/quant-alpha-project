from pathlib import Path
import sys

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from optimizer import run_walk_forward_optimization


def main() -> None:
    data_file = PROJECT_ROOT / "data" / "processed" / "real_daily_prices.csv"
    price_col = "adjusted_close"

    if not data_file.exists():
        raise FileNotFoundError(f"Real dataset not found: {data_file}. Run notebooks\\download_real_data.py first.")

    real_data = pd.read_csv(data_file, parse_dates=["date"])

    results, best_config, best_daily_results = run_walk_forward_optimization(
        price_data=real_data,
        factor_names=["momentum_1m", "momentum_3m", "short_term_reversal"],
        top_n_grid=[1, 3, 5],
        transaction_cost_bps_grid=[5.0, 10.0, 25.0],
        price_col=price_col,
    )

    display_columns = [
        "factor_name",
        "top_n",
        "transaction_cost_bps",
        "validation_sharpe_ratio",
        "validation_annualized_return",
        "validation_max_drawdown",
        "test_sharpe_ratio",
        "test_annualized_return",
        "test_max_drawdown",
    ]

    print("# Walk-Forward Optimization Demo")
    print()
    print(f"Loaded real data from: {data_file}")
    print(f"Research price column: {price_col}")
    print()
    print("Top candidate configurations ranked by validation Sharpe:")
    print(results[display_columns].head(10).to_string(index=False))
    print()
    print("Selected configuration:")
    for key in ["factor_name", "top_n", "transaction_cost_bps", "price_col"]:
        print(f"{key}: {best_config[key]}")
    print()
    print("Selected configuration test-period metrics:")
    print(f"test_annualized_return: {best_config['test_annualized_return']:.6f}")
    print(f"test_annualized_volatility: {best_config['test_annualized_volatility']:.6f}")
    print(f"test_sharpe_ratio: {best_config['test_sharpe_ratio']:.6f}")
    print(f"test_max_drawdown: {best_config['test_max_drawdown']:.6f}")
    print()
    print("Selected configuration daily result preview:")
    print(best_daily_results.tail(10).to_string(index=False))
    print()
    print("Interpretation:")
    print("This is a parameter-screening tool, not proof that the strategy is profitable.")
    print("The validation period selects parameters; the test period is shown separately to reduce in-sample overfitting.")
    print("A real deployment would require longer adjusted data, stronger bias controls, paper trading, and operational risk checks.")


if __name__ == "__main__":
    main()
