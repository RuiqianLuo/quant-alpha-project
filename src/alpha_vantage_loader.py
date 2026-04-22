"""
Alpha Vantage free daily equity data loader.

This module downloads daily U.S. equity data from Alpha Vantage's free
``TIME_SERIES_DAILY`` endpoint, saves the raw API response per ticker,
normalizes the fields into a single tabular format, and writes one combined
processed CSV file.

Environment variable:
- ALPHAVANTAGE_API_KEY

Important notes:
- this loader uses a fixed starting universe by default
- the free endpoint does not provide adjusted close, dividend amount, or
  split coefficient
- to keep the schema compatible with the rest of the repo, adjusted_close is
  set equal to close for now, dividend_amount is set to 0.0, and
  split_coefficient is set to 1.0
- this first real-data version does not solve survivorship bias
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd


API_URL = "https://www.alphavantage.co/query"
DEFAULT_TICKERS = [
    "AAPL",
    "MSFT",
    "AMZN",
    "GOOGL",
    "META",
    "NVDA",
    "JPM",
    "XOM",
    "JNJ",
    "PG",
]

OUTPUT_COLUMNS = [
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


def get_alpha_vantage_api_key() -> str:
    """
    Read the Alpha Vantage API key from the environment.
    """

    api_key = os.getenv("ALPHAVANTAGE_API_KEY", "").strip()
    if not api_key:
        raise ValueError("ALPHAVANTAGE_API_KEY is not set.")
    return api_key


def _raise_on_api_message(payload: dict[str, Any], ticker: str) -> None:
    """
    Raise a readable error when Alpha Vantage returns a message payload.
    """

    for key in ["Information", "Note", "Error Message"]:
        if key in payload:
            raise ValueError(f"Alpha Vantage {key} for {ticker}: {payload[key]}")


def fetch_daily_data(
    ticker: str,
    api_key: str,
    outputsize: str = "compact",
) -> dict[str, Any]:
    """
    Download daily price data for one ticker from Alpha Vantage's free endpoint.
    """

    params = {
        "function": "TIME_SERIES_DAILY",
        "symbol": ticker,
        "outputsize": outputsize,
        "apikey": api_key,
    }
    url = f"{API_URL}?{urlencode(params)}"

    with urlopen(url) as response:
        payload = json.loads(response.read().decode("utf-8"))

    _raise_on_api_message(payload, ticker=ticker)

    if "Time Series (Daily)" not in payload:
        raise ValueError(f"Unexpected Alpha Vantage response for {ticker}: missing daily time series data.")

    return payload


def parse_daily_payload(
    payload: dict[str, Any],
    ticker: str,
) -> pd.DataFrame:
    """
    Parse one Alpha Vantage free daily response into a normalized DataFrame.

    The free endpoint does not provide adjusted-close or corporate-action
    fields. To keep the output compatible with the current repo structure,
    this parser uses:

    - adjusted_close = close
    - dividend_amount = 0.0
    - split_coefficient = 1.0
    """

    _raise_on_api_message(payload, ticker=ticker)

    time_series = payload.get("Time Series (Daily)", {})
    rows = []

    for date_text, values in time_series.items():
        close_value = pd.to_numeric(values.get("4. close"), errors="coerce")
        rows.append(
            {
                "date": pd.to_datetime(date_text),
                "ticker": ticker.upper(),
                "open": pd.to_numeric(values.get("1. open"), errors="coerce"),
                "high": pd.to_numeric(values.get("2. high"), errors="coerce"),
                "low": pd.to_numeric(values.get("3. low"), errors="coerce"),
                "close": close_value,
                "adjusted_close": close_value,
                "volume": pd.to_numeric(values.get("5. volume"), errors="coerce"),
                "dividend_amount": 0.0,
                "split_coefficient": 1.0,
            }
        )

    frame = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    if frame.empty:
        return frame

    frame = frame.sort_values("date").reset_index(drop=True)
    frame["volume"] = frame["volume"].astype("Int64")
    return frame


def filter_normalized_data_by_date(
    frame: pd.DataFrame,
    start_date: str | None = None,
    end_date: str | None = None,
) -> pd.DataFrame:
    """
    Filter normalized price data by an optional inclusive date range.
    """

    filtered = frame.copy()
    if filtered.empty:
        return filtered

    if start_date is not None:
        filtered = filtered[filtered["date"] >= pd.to_datetime(start_date)]
    if end_date is not None:
        filtered = filtered[filtered["date"] <= pd.to_datetime(end_date)]

    return filtered.sort_values(["date", "ticker"]).reset_index(drop=True)


def save_raw_payload(
    payload: dict[str, Any],
    ticker: str,
    raw_dir: str | Path = "data/raw/alpha_vantage",
) -> Path:
    """
    Save one raw Alpha Vantage response to disk.
    """

    output_dir = Path(raw_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / f"{ticker.upper()}.json"
    with output_path.open("w", encoding="utf-8") as file_handle:
        json.dump(payload, file_handle, indent=2)

    return output_path


def save_combined_prices(
    frame: pd.DataFrame,
    output_file: str | Path = "data/processed/real_daily_prices.csv",
) -> Path:
    """
    Save the combined normalized real-data file.
    """

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_path, index=False)
    return output_path


def download_alpha_vantage_universe(
    tickers: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    pause_seconds: float = 12.0,
    raw_dir: str | Path = "data/raw/alpha_vantage",
    output_file: str | Path = "data/processed/real_daily_prices.csv",
) -> tuple[pd.DataFrame, Path]:
    """
    Download and normalize daily data for a fixed ticker universe.

    The default ``outputsize='compact'`` is chosen so the downloader works
    with a free Alpha Vantage API key.
    """

    api_key = get_alpha_vantage_api_key()
    ticker_list = tickers or DEFAULT_TICKERS

    normalized_frames = []
    pre_filter_frames = []
    for index, ticker in enumerate(ticker_list):
        payload = fetch_daily_data(ticker=ticker, api_key=api_key, outputsize="compact")
        save_raw_payload(payload, ticker=ticker, raw_dir=raw_dir)

        normalized = parse_daily_payload(payload, ticker=ticker)
        pre_filter_frames.append(normalized)
        normalized_frames.append(filter_normalized_data_by_date(normalized, start_date=start_date, end_date=end_date))

        if index < len(ticker_list) - 1 and pause_seconds > 0:
            time.sleep(pause_seconds)

    combined = pd.concat(normalized_frames, ignore_index=True)
    combined = combined.sort_values(["date", "ticker"]).reset_index(drop=True)
    saved_path = save_combined_prices(combined, output_file=output_file)
    return combined, saved_path


def summarize_date_coverage(frame: pd.DataFrame) -> dict[str, object]:
    """
    Summarize date coverage and row count for a normalized dataset.
    """

    if frame.empty:
        return {
            "row_count": 0,
            "min_date": None,
            "max_date": None,
        }

    return {
        "row_count": int(len(frame)),
        "min_date": frame["date"].min(),
        "max_date": frame["date"].max(),
    }
