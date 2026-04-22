from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from factor_library import compute_factor_set


def main() -> None:
    import pandas as pd

    data_file = PROJECT_ROOT / "data" / "processed" / "real_daily_prices.csv"
    price_col = "adjusted_close"

    if not data_file.exists():
        raise FileNotFoundError(f"Real dataset not found: {data_file}. Run notebooks\\download_real_data.py first.")

    real_data = pd.read_csv(data_file, parse_dates=["date"])
    factor_data = compute_factor_set(real_data, price_col=price_col)

    print("Loaded real data from:")
    print(data_file)
    print()
    print(f"Research price column: {price_col}")
    print()
    print("Real data preview:")
    print(real_data.tail(10).to_string(index=False))
    print()
    print("Factor preview:")
    print(factor_data.tail(10).to_string())
    print()
    print("Non-missing factor counts:")
    print(factor_data.notna().sum())


if __name__ == "__main__":
    main()
