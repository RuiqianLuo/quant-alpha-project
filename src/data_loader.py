"""
Simple daily U.S. equity OHLCV data loader.

This module is designed for a student quant research project. It keeps the
data pipeline small, readable, and easy to extend later.

Expected columns after standardization:
- date
- ticker
- open
- high
- low
- close
- volume
"""

from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = ["date", "ticker", "open", "high", "low", "close", "volume"]

COLUMN_ALIASES = {
    "Date": "date",
    "DATE": "date",
    "Ticker": "ticker",
    "Symbol": "ticker",
    "symbol": "ticker",
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Adj Close": "close",
    "adj_close": "close",
    "Volume": "volume",
}


def load_raw_price_data(file_path: str | Path) -> pd.DataFrame:
    """
    Load raw daily OHLCV data from a CSV file.

    Parameters
    ----------
    file_path:
        Path to a raw CSV file, usually placed in ``data/raw/``.

    Returns
    -------
    pandas.DataFrame
        Raw data exactly as read from the CSV file.
    """

    return pd.read_csv(file_path)


def standardize_price_data(frame: pd.DataFrame) -> pd.DataFrame:
    """
    Standardize column names and basic data types.

    This function:
    - renames common OHLCV column variants
    - converts the date column to pandas datetime
    - uppercases ticker symbols
    - converts numeric columns to numeric dtype

    Parameters
    ----------
    frame:
        Raw price data.

    Returns
    -------
    pandas.DataFrame
        Data with standardized columns and dtypes.
    """

    cleaned = frame.rename(columns=COLUMN_ALIASES).copy()

    missing_columns = [column for column in REQUIRED_COLUMNS if column not in cleaned.columns]
    if missing_columns:
        missing_text = ", ".join(missing_columns)
        raise ValueError(f"Missing required columns: {missing_text}")

    cleaned["date"] = pd.to_datetime(cleaned["date"], errors="coerce")
    cleaned["ticker"] = cleaned["ticker"].astype(str).str.strip().str.upper()

    for column in ["open", "high", "low", "close", "volume"]:
        cleaned[column] = pd.to_numeric(cleaned[column], errors="coerce")

    return cleaned[REQUIRED_COLUMNS].sort_values(["date", "ticker"]).reset_index(drop=True)


def filter_invalid_rows(frame: pd.DataFrame) -> pd.DataFrame:
    """
    Remove rows that are clearly invalid for daily OHLCV data.

    Rules:
    - drop rows with missing date or ticker
    - drop duplicate date-ticker pairs
    - require positive prices
    - require non-negative volume
    - require high >= low

    Parameters
    ----------
    frame:
        Standardized price data.

    Returns
    -------
    pandas.DataFrame
        Data with obviously invalid rows removed.
    """

    cleaned = frame.dropna(subset=["date", "ticker"]).copy()
    cleaned = cleaned.drop_duplicates(subset=["date", "ticker"], keep="last")

    positive_price_mask = (
        (cleaned["open"] > 0)
        & (cleaned["high"] > 0)
        & (cleaned["low"] > 0)
        & (cleaned["close"] > 0)
    )
    non_negative_volume_mask = cleaned["volume"] >= 0
    high_low_mask = cleaned["high"] >= cleaned["low"]

    cleaned = cleaned[positive_price_mask & non_negative_volume_mask & high_low_mask]

    return cleaned.sort_values(["ticker", "date"]).reset_index(drop=True)


def handle_missing_values(frame: pd.DataFrame) -> pd.DataFrame:
    """
    Handle missing values in a simple and transparent way.

    Strategy:
    - drop rows missing date or ticker
    - forward-fill OHLC values within each ticker
    - fill missing volume with 0
    - drop any rows that still miss OHLC values afterward

    Parameters
    ----------
    frame:
        Standardized price data.

    Returns
    -------
    pandas.DataFrame
        Data after simple missing-value handling.
    """

    cleaned = frame.dropna(subset=["date", "ticker"]).copy()
    cleaned = cleaned.sort_values(["ticker", "date"]).reset_index(drop=True)

    price_columns = ["open", "high", "low", "close"]
    cleaned[price_columns] = cleaned.groupby("ticker")[price_columns].ffill()
    cleaned["volume"] = cleaned["volume"].fillna(0)
    cleaned = cleaned.dropna(subset=price_columns)

    return cleaned.reset_index(drop=True)


def save_cleaned_data(
    frame: pd.DataFrame,
    output_file_name: str,
    output_dir: str | Path = "data/processed",
) -> Path:
    """
    Save cleaned price data to ``data/processed/``.

    Parameters
    ----------
    frame:
        Cleaned price data.
    output_file_name:
        Name of the output CSV file.
    output_dir:
        Directory where processed files should be saved.

    Returns
    -------
    pathlib.Path
        Full path to the saved file.
    """

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    file_path = output_path / output_file_name
    frame.to_csv(file_path, index=False)
    return file_path


def clean_price_data_file(
    input_file_path: str | Path,
    output_file_name: str | None = None,
    output_dir: str | Path = "data/processed",
) -> tuple[pd.DataFrame, Path]:
    """
    Run the full cleaning pipeline for one raw CSV file.

    Parameters
    ----------
    input_file_path:
        Path to the raw CSV file.
    output_file_name:
        Optional name for the cleaned CSV file. If omitted, the input file
        name is reused.
    output_dir:
        Directory where cleaned data should be saved.

    Returns
    -------
    tuple[pandas.DataFrame, pathlib.Path]
        The cleaned DataFrame and the saved output file path.
    """

    input_path = Path(input_file_path)
    final_output_name = output_file_name or input_path.name

    raw_data = load_raw_price_data(input_path)
    standardized_data = standardize_price_data(raw_data)
    filled_data = handle_missing_values(standardized_data)
    cleaned_data = filter_invalid_rows(filled_data)
    saved_path = save_cleaned_data(cleaned_data, final_output_name, output_dir=output_dir)

    return cleaned_data, saved_path
