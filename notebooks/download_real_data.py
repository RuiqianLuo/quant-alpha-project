from __future__ import annotations

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from alpha_vantage_loader import (
    DEFAULT_TICKERS,
    fetch_daily_data,
    filter_normalized_data_by_date,
    get_alpha_vantage_api_key,
    parse_daily_payload,
    save_combined_prices,
    save_raw_payload,
    summarize_date_coverage,
)


def parse_args() -> argparse.Namespace:
    """
    Parse downloader arguments.
    """

    parser = argparse.ArgumentParser(description="Download daily equity data from Alpha Vantage's free endpoint.")
    parser.add_argument("--start-date", default="2020-01-01", help="Inclusive start date in YYYY-MM-DD format.")
    parser.add_argument("--end-date", default=None, help="Inclusive end date in YYYY-MM-DD format.")
    parser.add_argument(
        "--tickers",
        default=",".join(DEFAULT_TICKERS),
        help="Comma-separated list of ticker symbols.",
    )
    parser.add_argument(
        "--pause-seconds",
        type=float,
        default=12.0,
        help="Sleep interval between API calls. Keep this conservative for the free tier.",
    )
    parser.add_argument(
        "--preview-rows",
        type=int,
        default=10,
        help="Number of preview rows to print.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    tickers = [ticker.strip().upper() for ticker in args.tickers.split(",") if ticker.strip()]
    api_key = get_alpha_vantage_api_key()

    pre_filter_frames = []
    post_filter_frames = []

    for index, ticker in enumerate(tickers):
        payload = fetch_daily_data(ticker=ticker, api_key=api_key, outputsize="compact")
        save_raw_payload(payload, ticker=ticker)

        normalized = parse_daily_payload(payload, ticker=ticker)
        filtered = filter_normalized_data_by_date(
            normalized,
            start_date=args.start_date,
            end_date=args.end_date,
        )

        pre_filter_frames.append(normalized)
        post_filter_frames.append(filtered)

        if index < len(tickers) - 1 and args.pause_seconds > 0:
            import time

            time.sleep(args.pause_seconds)

    pre_filter_combined = (
        __import__("pandas").concat(pre_filter_frames, ignore_index=True)
        if pre_filter_frames
        else __import__("pandas").DataFrame()
    )
    combined = (
        __import__("pandas").concat(post_filter_frames, ignore_index=True)
        if post_filter_frames
        else __import__("pandas").DataFrame()
    )

    pre_filter_summary = summarize_date_coverage(pre_filter_combined)
    post_filter_summary = summarize_date_coverage(combined)

    saved_path = save_combined_prices(combined)

    print("Downloaded tickers:")
    print(", ".join(tickers))
    print()
    print("Source endpoint:")
    print("Alpha Vantage TIME_SERIES_DAILY (free tier, outputsize=compact)")
    print()
    print("Returned date coverage before filtering:")
    print(f"min_date: {pre_filter_summary['min_date']}")
    print(f"max_date: {pre_filter_summary['max_date']}")
    print(f"row_count_before_filtering: {pre_filter_summary['row_count']}")
    print(f"row_count_after_filtering: {post_filter_summary['row_count']}")
    print()
    print("Combined normalized file:")
    print(saved_path)
    print()

    if combined.empty:
        print("WARNING: The combined normalized dataset is empty after date filtering.")
        print("Likely cause: the free Alpha Vantage endpoint returns only a compact recent window.")
        print("Your requested date range may not overlap with the returned window.")
        return

    print("Combined normalized dataset preview:")
    print(combined.head(args.preview_rows).to_string(index=False))


if __name__ == "__main__":
    main()
