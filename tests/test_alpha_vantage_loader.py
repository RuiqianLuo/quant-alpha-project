from pathlib import Path
import sys


SRC_DIR = Path(__file__).resolve().parents[1] / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from alpha_vantage_loader import filter_normalized_data_by_date, parse_daily_payload, summarize_date_coverage


def test_parse_daily_payload_normalizes_free_endpoint_fields() -> None:
    payload = {
        "Meta Data": {"2. Symbol": "AAPL"},
        "Time Series (Daily)": {
            "2024-01-03": {
                "1. open": "182.00",
                "2. high": "184.00",
                "3. low": "181.50",
                "4. close": "183.25",
                "5. volume": "45678900",
            },
            "2024-01-02": {
                "1. open": "180.00",
                "2. high": "183.00",
                "3. low": "179.50",
                "4. close": "182.00",
                "5. volume": "50123400",
            },
        },
    }

    frame = parse_daily_payload(payload, ticker="aapl")

    assert list(frame.columns) == [
        "date",
        "ticker",
        "open",
        "high",
        "low",
        "close",
        "adjusted_close",
        "volume",
        "dividend_amount",
        "split_coefficient",
    ]
    assert len(frame) == 2
    assert frame.iloc[0]["ticker"] == "AAPL"
    assert str(frame.iloc[0]["date"].date()) == "2024-01-02"
    assert abs(frame.iloc[1]["adjusted_close"] - 183.25) < 1e-12
    assert frame.iloc[0]["dividend_amount"] == 0.0
    assert frame.iloc[0]["split_coefficient"] == 1.0
    assert int(frame.iloc[0]["volume"]) == 50123400


def test_filter_and_coverage_summary_show_empty_post_filter_result() -> None:
    payload = {
        "Time Series (Daily)": {
            "2024-01-03": {
                "1. open": "182.00",
                "2. high": "184.00",
                "3. low": "181.50",
                "4. close": "183.25",
                "5. volume": "45678900",
            },
            "2024-01-02": {
                "1. open": "180.00",
                "2. high": "183.00",
                "3. low": "179.50",
                "4. close": "182.00",
                "5. volume": "50123400",
            },
        },
    }

    raw_frame = parse_daily_payload(payload, ticker="AAPL")
    filtered_frame = filter_normalized_data_by_date(raw_frame, start_date="2025-01-01", end_date="2025-12-31")

    raw_summary = summarize_date_coverage(raw_frame)
    filtered_summary = summarize_date_coverage(filtered_frame)

    assert raw_summary["row_count"] == 2
    assert str(raw_summary["min_date"].date()) == "2024-01-02"
    assert str(raw_summary["max_date"].date()) == "2024-01-03"
    assert filtered_summary["row_count"] == 0
    assert filtered_summary["min_date"] is None
    assert filtered_summary["max_date"] is None
