from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math
import random

import numpy as np
import pandas as pd

from app.config import Settings


SUPPORTED_PAIRS = ["EUR_USD", "GBP_USD", "USD_JPY", "XAU_USD", "BTC_USDT"]

YAHOO_SYMBOLS = {
    "EUR_USD": "EURUSD=X",
    "GBP_USD": "GBPUSD=X",
    "USD_JPY": "JPY=X",
    # Yahoo symbol can vary. GC=F is gold futures, not exact spot XAU/USD.
    "XAU_USD": "GC=F",
    "BTC_USDT": "BTC-USD",
}


@dataclass
class CandleRequest:
    pair: str
    timeframe: str  # H1 or H4
    count: int = 300


class MarketDataError(RuntimeError):
    pass


class BaseMarketDataProvider:
    def get_candles(self, request: CandleRequest) -> pd.DataFrame:
        raise NotImplementedError


class YahooDataProvider(BaseMarketDataProvider):
    def get_candles(self, request: CandleRequest) -> pd.DataFrame:
        try:
            import yfinance as yf
        except Exception as exc:  # pragma: no cover
            raise MarketDataError("Package yfinance belum tersedia.") from exc

        pair = request.pair.replace("/", "_").upper()
        symbol = YAHOO_SYMBOLS.get(pair)
        if not symbol:
            raise MarketDataError(f"Pair {pair} belum didukung Yahoo provider.")

        # Yahoo intraday generally supports 1h. H4 dibuat dari resample H1.
        raw = yf.download(symbol, interval="1h", period="60d", progress=False, auto_adjust=False)
        if raw.empty:
            raise MarketDataError(f"Yahoo tidak mengembalikan data untuk {symbol}.")

        raw = raw.reset_index()
        time_col = "Datetime" if "Datetime" in raw.columns else "Date"
        df = pd.DataFrame(
            {
                "time": pd.to_datetime(raw[time_col]),
                "open": raw["Open"].astype(float),
                "high": raw["High"].astype(float),
                "low": raw["Low"].astype(float),
                "close": raw["Close"].astype(float),
                "volume": raw.get("Volume", pd.Series([0] * len(raw))).fillna(0).astype(float),
            }
        ).dropna()

        if request.timeframe.upper() == "H4":
            df = df.set_index("time").resample("4h").agg(
                {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
            ).dropna().reset_index()

        return df.tail(request.count).reset_index(drop=True)


class DemoDataProvider(BaseMarketDataProvider):
    """Deterministic dummy candles so the dashboard can be tested without API keys."""

    def get_candles(self, request: CandleRequest) -> pd.DataFrame:
        pair = request.pair.replace("/", "_").upper()
        seed = sum(ord(c) for c in pair + request.timeframe)
        rng = random.Random(seed)

        if pair == "BTC_USDT":
            base = 65000.0
            vol = 450.0
        elif pair == "XAU_USD":
            base = 2350.0
            vol = 8.0
        elif pair == "USD_JPY":
            base = 155.0
            vol = 0.25
        else:
            base = 1.08 if pair == "EUR_USD" else 1.27
            vol = 0.0025

        count = max(request.count, 250)
        step_hours = 1 if request.timeframe.upper() == "H1" else 4
        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        times = [now - timedelta(hours=step_hours * (count - i)) for i in range(count)]

        price = base
        rows = []
        trend = -1 if pair in ["XAU_USD", "GBP_USD"] else 1
        for i, t in enumerate(times):
            drift = trend * vol * 0.045 * math.sin(i / 28) + trend * vol * 0.008
            shock = rng.gauss(0, vol * 0.35)
            open_ = price
            close = max(0.0001, open_ + drift + shock)
            high = max(open_, close) + abs(rng.gauss(0, vol * 0.15))
            low = min(open_, close) - abs(rng.gauss(0, vol * 0.15))
            volume = int(abs(rng.gauss(1000, 200)))
            rows.append({"time": t, "open": open_, "high": high, "low": low, "close": close, "volume": volume})
            price = close

        return pd.DataFrame(rows).reset_index(drop=True)


def get_provider(settings: Settings) -> BaseMarketDataProvider:
    provider = settings.data_provider.lower().strip()
    if provider in ["tradingview", "webhook"]:
        raise MarketDataError("DATA_PROVIDER=tradingview menerima data hanya dari POST /webhook/tradingview.")
    if provider == "yahoo":
        return YahooDataProvider()
    return DemoDataProvider()
