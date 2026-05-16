from __future__ import annotations

import numpy as np
import pandas as pd


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["ema20"] = ema(out["close"], 20)
    out["ema50"] = ema(out["close"], 50)
    out["ema200"] = ema(out["close"], 200)
    out["rsi14"] = rsi(out["close"], 14)
    out["atr14"] = atr(out, 14)
    return out


def recent_support_resistance(df: pd.DataFrame, lookback: int = 40) -> tuple[float, float]:
    recent = df.tail(lookback)
    support = float(recent["low"].min())
    resistance = float(recent["high"].max())
    return support, resistance


def market_structure(df: pd.DataFrame, lookback: int = 6) -> str:
    """Simple structure based on recent swing highs/lows."""
    if len(df) < lookback * 3:
        return "NEUTRAL"

    closes = df["close"].tail(lookback * 3)
    first = closes.iloc[:lookback].mean()
    middle = closes.iloc[lookback : lookback * 2].mean()
    last = closes.iloc[lookback * 2 :].mean()

    if first < middle < last:
        return "HIGHER_HIGH"
    if first > middle > last:
        return "LOWER_LOW"
    return "RANGING"


def candle_rejection(row: pd.Series) -> str:
    body = abs(float(row["close"] - row["open"]))
    candle_range = float(row["high"] - row["low"])
    if candle_range <= 0:
        return "NONE"
    upper_wick = float(row["high"] - max(row["close"], row["open"]))
    lower_wick = float(min(row["close"], row["open"]) - row["low"])

    # Pin-bar style rejection
    if lower_wick > body * 1.5 and lower_wick > candle_range * 0.35:
        return "BULLISH_REJECTION"
    if upper_wick > body * 1.5 and upper_wick > candle_range * 0.35:
        return "BEARISH_REJECTION"
    return "NONE"
