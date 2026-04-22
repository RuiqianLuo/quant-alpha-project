"""
Cross-sectional daily equity factor library.

This module computes simple, beginner-friendly factors from cleaned daily
OHLCV data. The expected input columns are:

- date
- ticker
- close or adjusted_close
- volume

All factor outputs use a MultiIndex of ``date`` and ``ticker`` so they are
easy to join with future research datasets later.
"""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd


BASE_REQUIRED_COLUMNS = ["date", "ticker", "volume"]


def _resolve_price_col(frame: pd.DataFrame, price_col: str) -> str:
    """
    Resolve the research price column with a simple compatibility fallback.
    """

    if price_col in frame.columns:
        return price_col

    if price_col == "adjusted_close" and "close" in frame.columns:
        return "close"

    raise ValueError(f"Missing required price column for factor computation: {price_col}")


def _prepare_factor_input(frame: pd.DataFrame, price_col: str = "adjusted_close") -> pd.DataFrame:
    """
    Validate and sort the input data for factor computation.
    """

    missing_columns = [column for column in BASE_REQUIRED_COLUMNS if column not in frame.columns]
    if missing_columns:
        missing_text = ", ".join(missing_columns)
        raise ValueError(f"Missing required columns for factor computation: {missing_text}")

    data = frame.copy()
    resolved_price_col = _resolve_price_col(data, price_col)
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data["ticker"] = data["ticker"].astype(str).str.strip().str.upper()
    data["research_price"] = pd.to_numeric(data[resolved_price_col], errors="coerce")
    data["volume"] = pd.to_numeric(data["volume"], errors="coerce")

    data = data.dropna(subset=["date", "ticker", "research_price"])
    data = data.sort_values(["ticker", "date"]).reset_index(drop=True)

    return data


def _finalize_factor_output(frame: pd.DataFrame, factor_name: str) -> pd.DataFrame:
    """
    Return a clean MultiIndex DataFrame for one factor.
    """

    output = frame[["date", "ticker", factor_name]].copy()
    output = output.sort_values(["date", "ticker"]).set_index(["date", "ticker"])
    return output


def compute_1m_momentum(frame: pd.DataFrame, window: int = 21, price_col: str = "adjusted_close") -> pd.DataFrame:
    """
    Compute 1-month momentum using lagged prices.

    Financial intuition:
    Stocks that have outperformed over the recent month sometimes keep
    outperforming over the short to medium term.

    Lookahead handling:
    The factor at date ``t`` uses prices only through ``t-1`` by shifting
    the close series by one day before computing returns.
    """

    data = _prepare_factor_input(frame, price_col=price_col)
    lagged_close = data.groupby("ticker")["research_price"].shift(1)
    data["momentum_1m"] = lagged_close / lagged_close.groupby(data["ticker"]).shift(window) - 1
    return _finalize_factor_output(data, "momentum_1m")


def compute_3m_momentum(frame: pd.DataFrame, window: int = 63, price_col: str = "adjusted_close") -> pd.DataFrame:
    """
    Compute 3-month momentum using lagged prices.

    Financial intuition:
    Medium-horizon winners often remain strong if market trends or investor
    underreaction persist.

    Lookahead handling:
    The factor at date ``t`` uses prices only through ``t-1``.
    """

    data = _prepare_factor_input(frame, price_col=price_col)
    lagged_close = data.groupby("ticker")["research_price"].shift(1)
    data["momentum_3m"] = lagged_close / lagged_close.groupby(data["ticker"]).shift(window) - 1
    return _finalize_factor_output(data, "momentum_3m")


def compute_short_term_reversal(frame: pd.DataFrame, window: int = 5, price_col: str = "adjusted_close") -> pd.DataFrame:
    """
    Compute a short-term reversal signal from lagged returns.

    Financial intuition:
    Stocks that moved sharply over the last few days sometimes mean-revert
    as short-term price pressure fades.

    Lookahead handling:
    The factor at date ``t`` uses only returns observed through ``t-1``.
    The factor is the negative of the recent return so recent losers rank
    higher on this signal.
    """

    data = _prepare_factor_input(frame, price_col=price_col)
    lagged_close = data.groupby("ticker")["research_price"].shift(1)
    recent_return = lagged_close / lagged_close.groupby(data["ticker"]).shift(window) - 1
    data["short_term_reversal"] = -recent_return
    return _finalize_factor_output(data, "short_term_reversal")


def compute_rolling_volatility(frame: pd.DataFrame, window: int = 21, price_col: str = "adjusted_close") -> pd.DataFrame:
    """
    Compute rolling volatility from daily close-to-close returns.

    Financial intuition:
    Stocks with more unstable recent returns may behave differently from
    calmer stocks and are often treated as a separate risk characteristic.

    Lookahead handling:
    The rolling window uses daily returns shifted by one day, so the factor
    at date ``t`` does not use the return from ``t`` itself.
    """

    data = _prepare_factor_input(frame, price_col=price_col)
    daily_return = data.groupby("ticker")["research_price"].pct_change()
    shifted_return = daily_return.groupby(data["ticker"]).shift(1)
    data["rolling_volatility"] = (
        shifted_return.groupby(data["ticker"]).rolling(window=window, min_periods=window).std().reset_index(level=0, drop=True)
    )
    return _finalize_factor_output(data, "rolling_volatility")


def compute_liquidity_proxy(
    frame: pd.DataFrame,
    window: int = 21,
    use_dollar_volume: bool = True,
    price_col: str = "adjusted_close",
) -> pd.DataFrame:
    """
    Compute a simple rolling liquidity proxy.

    Financial intuition:
    More liquid stocks usually trade with lower frictions and higher market
    participation. A rolling average of volume or dollar volume is a simple
    way to capture this idea.

    Lookahead handling:
    The rolling average is shifted by one day, so the factor at date ``t``
    uses only information available by the end of ``t-1``.
    """

    data = _prepare_factor_input(frame, price_col=price_col)
    if use_dollar_volume:
        liquidity_series = data["research_price"] * data["volume"]
        factor_name = "liquidity_dollar_volume"
    else:
        liquidity_series = data["volume"]
        factor_name = "liquidity_volume"

    shifted_liquidity = liquidity_series.groupby(data["ticker"]).shift(1)
    data[factor_name] = (
        shifted_liquidity.groupby(data["ticker"]).rolling(window=window, min_periods=window).mean().reset_index(level=0, drop=True)
    )
    return _finalize_factor_output(data, factor_name)


def compute_factor_set(
    frame: pd.DataFrame,
    factors: Iterable[str] | None = None,
    price_col: str = "adjusted_close",
) -> pd.DataFrame:
    """
    Compute a selected set of factors and return them in one DataFrame.

    Parameters
    ----------
    frame:
        Cleaned OHLCV data.
    factors:
        Optional list of factor names. If omitted, all default factors are
        computed.

    Returns
    -------
    pandas.DataFrame
        MultiIndex DataFrame indexed by ``date`` and ``ticker`` with one
        column per factor.
    """

    factor_builders = {
        "momentum_1m": compute_1m_momentum,
        "momentum_3m": compute_3m_momentum,
        "short_term_reversal": compute_short_term_reversal,
        "rolling_volatility": compute_rolling_volatility,
        "liquidity_dollar_volume": compute_liquidity_proxy,
    }

    selected_factors = list(factors) if factors is not None else list(factor_builders.keys())

    factor_frames = []
    for factor_name in selected_factors:
        if factor_name not in factor_builders:
            raise ValueError(f"Unsupported factor name: {factor_name}")
        factor_frames.append(factor_builders[factor_name](frame, price_col=price_col))

    combined = pd.concat(factor_frames, axis=1)
    combined = combined.sort_index()
    return combined
