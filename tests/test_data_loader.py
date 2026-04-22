from pathlib import Path
import shutil
import sys
import uuid

import pandas as pd


SRC_DIR = Path(__file__).resolve().parents[1] / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from data_loader import clean_price_data_file


def test_clean_price_data_file_removes_invalid_rows_and_saves_output() -> None:
    temp_root = Path("tests") / f"tmp_{uuid.uuid4().hex}"
    output_dir = temp_root / "processed"
    raw_file = temp_root / "demo_prices.csv"

    temp_root.mkdir(parents=True, exist_ok=True)

    try:
        raw_frame = pd.DataFrame(
            [
                {
                    "Date": "2024-01-02",
                    "Ticker": "aapl",
                    "Open": 100,
                    "High": 101,
                    "Low": 99,
                    "Close": 100.5,
                    "Volume": 1000,
                },
                {
                    "Date": "2024-01-03",
                    "Ticker": "AAPL",
                    "Open": 101,
                    "High": 102,
                    "Low": 100,
                    "Close": "",
                    "Volume": "",
                },
                {
                    "Date": "2024-01-02",
                    "Ticker": "MSFT",
                    "Open": -1,
                    "High": 201,
                    "Low": 199,
                    "Close": 200,
                    "Volume": 2000,
                },
            ]
        )
        raw_frame.to_csv(raw_file, index=False)

        cleaned_frame, saved_path = clean_price_data_file(raw_file, output_dir=output_dir)

        assert list(cleaned_frame["ticker"]) == ["AAPL", "AAPL"]
        assert cleaned_frame.iloc[1]["close"] == 100.5
        assert cleaned_frame.iloc[1]["volume"] == 0
        assert saved_path.exists()
        assert saved_path == output_dir / "demo_prices.csv"
    finally:
        if temp_root.exists():
            shutil.rmtree(temp_root)
