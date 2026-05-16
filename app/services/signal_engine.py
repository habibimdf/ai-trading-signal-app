from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Literal

import pandas as pd

from .indicators import add_indicators, candle_rejection, market_structure, recent_support_resistance
from .risk import calculate_lot_size, pip_size

SignalType = Literal["BUY", "SELL", "WAIT"]


@dataclass
class SignalDecision:
    pair: str
    mode: str
    signal: SignalType
    status: str
    entry_min: float | None
    entry_max: float | None
    stop_loss: float | None
    take_profit_1: float | None
    take_profit_2: float | None
    take_profit_3: float | None
    risk_reward: float | None
    confidence: int
    lot_size: float | None
    risk_amount_usd: float | None
    account_type: str
    balance: float
    risk_percent: float
    h4_bias: str
    h1_confirmation: str
    reason: str
    raw_json: str


def _round_price(pair: str, value: float | None) -> float | None:
    if value is None:
        return None
    pair = pair.replace("/", "_").upper()
    if pair == "XAU_USD":
        return round(value, 2)
    if pair.endswith("JPY"):
        return round(value, 3)
    return round(value, 5)


def determine_h4_bias(h4: pd.DataFrame) -> dict:
    row = h4.iloc[-1]
    structure = market_structure(h4)
    close = float(row["close"])
    ema50 = float(row["ema50"])
    ema200 = float(row["ema200"])
    rsi14 = float(row["rsi14"])

    score_bull = 0
    score_bear = 0
    reasons = []

    if close > ema200:
        score_bull += 25
        reasons.append("H4 close berada di atas EMA200")
    else:
        score_bear += 25
        reasons.append("H4 close berada di bawah EMA200")

    if ema50 > ema200:
        score_bull += 20
        reasons.append("EMA50 H4 berada di atas EMA200")
    else:
        score_bear += 20
        reasons.append("EMA50 H4 berada di bawah EMA200")

    if structure == "HIGHER_HIGH":
        score_bull += 20
        reasons.append("Struktur H4 cenderung higher high")
    elif structure == "LOWER_LOW":
        score_bear += 20
        reasons.append("Struktur H4 cenderung lower low")
    else:
        reasons.append("Struktur H4 masih ranging/kurang jelas")

    if rsi14 >= 55:
        score_bull += 10
        reasons.append("RSI H4 mendukung momentum bullish")
    elif rsi14 <= 45:
        score_bear += 10
        reasons.append("RSI H4 mendukung momentum bearish")
    else:
        reasons.append("RSI H4 netral")

    if score_bull >= score_bear + 15:
        bias = "BULLISH"
        score = score_bull
    elif score_bear >= score_bull + 15:
        bias = "BEARISH"
        score = score_bear
    else:
        bias = "SIDEWAYS"
        score = max(score_bull, score_bear)

    return {"bias": bias, "score": score, "reasons": reasons, "structure": structure}


def confirm_h1_entry(pair: str, mode: str, h1: pd.DataFrame, h4_bias: str) -> dict:
    row = h1.iloc[-1]
    prev = h1.iloc[-2]
    close = float(row["close"])
    open_ = float(row["open"])
    ema20 = float(row["ema20"])
    ema50 = float(row["ema50"])
    rsi14 = float(row["rsi14"])
    atr14 = float(row["atr14"])
    support, resistance = recent_support_resistance(h1, lookback=35 if mode == "scalping" else 50)
    rejection = candle_rejection(row)

    reasons = []
    signal: SignalType = "WAIT"
    confirmation = "NONE"
    score = 0

    tolerance = atr14 * (0.25 if mode == "scalping" else 0.40)

    if h4_bias == "BULLISH":
        pullback_to_ema = float(row["low"]) <= ema50 + tolerance
        bullish_close = close > open_ and close > float(prev["close"])
        if close > ema50:
            score += 15
            reasons.append("H1 close di atas EMA50")
        if pullback_to_ema:
            score += 15
            reasons.append("H1 pullback ke area EMA50/support dinamis")
        if bullish_close or rejection == "BULLISH_REJECTION":
            score += 20
            reasons.append("H1 menunjukkan konfirmasi bullish/rejection")
        if rsi14 > 50:
            score += 10
            reasons.append("RSI H1 di atas 50")
        if score >= 35:
            signal = "BUY"
            confirmation = "BULLISH_CONFIRMATION"

    elif h4_bias == "BEARISH":
        pullback_to_ema = float(row["high"]) >= ema50 - tolerance
        bearish_close = close < open_ and close < float(prev["close"])
        if close < ema50:
            score += 15
            reasons.append("H1 close di bawah EMA50")
        if pullback_to_ema:
            score += 15
            reasons.append("H1 pullback ke area EMA50/resistance dinamis")
        if bearish_close or rejection == "BEARISH_REJECTION":
            score += 20
            reasons.append("H1 menunjukkan konfirmasi bearish/rejection")
        if rsi14 < 50:
            score += 10
            reasons.append("RSI H1 di bawah 50")
        if score >= 35:
            signal = "SELL"
            confirmation = "BEARISH_CONFIRMATION"
    else:
        reasons.append("H4 sideways, sistem memilih WAIT")

    return {
        "signal": signal,
        "confirmation": confirmation,
        "score": score,
        "reasons": reasons,
        "support": support,
        "resistance": resistance,
        "atr14": atr14,
        "last_close": close,
        "ema50": ema50,
    }


def build_trade_plan(pair: str, mode: str, signal: SignalType, h1_info: dict) -> dict:
    if signal == "WAIT":
        return {
            "entry_min": None,
            "entry_max": None,
            "stop_loss": None,
            "take_profit_1": None,
            "take_profit_2": None,
            "take_profit_3": None,
            "risk_reward": None,
        }

    entry = float(h1_info["last_close"])
    atr14 = float(h1_info["atr14"])
    spread_buffer = max(atr14 * 0.08, pip_size(pair) * 5)
    entry_band = max(atr14 * (0.15 if mode == "scalping" else 0.25), pip_size(pair) * 10)

    if signal == "BUY":
        sl_candidate = min(float(h1_info["support"]), entry - atr14 * (1.1 if mode == "scalping" else 1.4))
        stop_loss = sl_candidate - spread_buffer
        risk = entry - stop_loss
        tp1 = entry + risk * 1.5
        tp2 = entry + risk * 2.0
        tp3 = entry + risk * 3.0
        entry_min = entry - entry_band
        entry_max = entry + entry_band * 0.4
    else:
        sl_candidate = max(float(h1_info["resistance"]), entry + atr14 * (1.1 if mode == "scalping" else 1.4))
        stop_loss = sl_candidate + spread_buffer
        risk = stop_loss - entry
        tp1 = entry - risk * 1.5
        tp2 = entry - risk * 2.0
        tp3 = entry - risk * 3.0
        entry_min = entry - entry_band * 0.4
        entry_max = entry + entry_band

    reward = abs(tp2 - entry)
    risk_reward = reward / risk if risk else None

    return {
        "entry_min": _round_price(pair, entry_min),
        "entry_max": _round_price(pair, entry_max),
        "stop_loss": _round_price(pair, stop_loss),
        "take_profit_1": _round_price(pair, tp1),
        "take_profit_2": _round_price(pair, tp2),
        "take_profit_3": _round_price(pair, tp3),
        "risk_reward": round(float(risk_reward), 2) if risk_reward else None,
        "entry_mid": _round_price(pair, entry),
    }


def generate_signal(
    pair: str,
    mode: str,
    h4_raw: pd.DataFrame,
    h1_raw: pd.DataFrame,
    balance: float,
    account_type: str,
    risk_percent: float,
    min_confidence: int = 70,
) -> SignalDecision:
    pair = pair.replace("/", "_").upper()
    mode = mode.lower()

    h4 = add_indicators(h4_raw).dropna().reset_index(drop=True)
    h1 = add_indicators(h1_raw).dropna().reset_index(drop=True)
    if len(h4) < 60 or len(h1) < 60:
        raise ValueError("Data candle kurang. Butuh minimal 60 candle setelah indikator dihitung.")

    h4_info = determine_h4_bias(h4)
    h1_info = confirm_h1_entry(pair, mode, h1, h4_info["bias"])
    signal = h1_info["signal"]

    confidence = int(min(100, h4_info["score"] + h1_info["score"]))

    trade_plan = build_trade_plan(pair, mode, signal, h1_info)

    # Filter minimal quality.
    status = "VALID_SETUP"
    if signal == "WAIT":
        status = "WAIT"
    elif confidence < min_confidence:
        signal = "WAIT"
        status = "LOW_CONFIDENCE_WAIT"
    elif trade_plan.get("risk_reward") is not None and trade_plan["risk_reward"] < 1.5:
        signal = "WAIT"
        status = "RR_TOO_LOW_WAIT"

    if signal == "WAIT":
        trade_plan = build_trade_plan(pair, mode, "WAIT", h1_info)
        lot_size = None
        risk_amount_usd = None
    else:
        entry_mid = float(trade_plan["entry_mid"])
        risk_calc = calculate_lot_size(
            pair=pair,
            entry=entry_mid,
            stop_loss=float(trade_plan["stop_loss"]),
            balance=balance,
            account_type=account_type,
            risk_percent=risk_percent,
        )
        lot_size = risk_calc["lot_size"]
        risk_amount_usd = risk_calc["risk_amount_usd"]

    reasons = []
    reasons.extend(h4_info["reasons"])
    reasons.extend(h1_info["reasons"])
    if signal == "WAIT":
        reasons.append("Sistem memilih WAIT karena setup belum memenuhi filter confidence/risk-reward.")
    else:
        reasons.append("Setup memenuhi filter minimal confidence dan risk/reward.")

    raw = {
        "h4": h4_info,
        "h1": h1_info,
        "trade_plan": trade_plan,
        "last_h4_close": float(h4.iloc[-1]["close"]),
        "last_h1_close": float(h1.iloc[-1]["close"]),
    }

    return SignalDecision(
        pair=pair,
        mode=mode,
        signal=signal,
        status=status,
        entry_min=trade_plan.get("entry_min"),
        entry_max=trade_plan.get("entry_max"),
        stop_loss=trade_plan.get("stop_loss"),
        take_profit_1=trade_plan.get("take_profit_1"),
        take_profit_2=trade_plan.get("take_profit_2"),
        take_profit_3=trade_plan.get("take_profit_3"),
        risk_reward=trade_plan.get("risk_reward"),
        confidence=confidence,
        lot_size=lot_size,
        risk_amount_usd=risk_amount_usd,
        account_type=account_type,
        balance=balance,
        risk_percent=risk_percent,
        h4_bias=h4_info["bias"],
        h1_confirmation=h1_info["confirmation"],
        reason="\n".join(f"- {r}" for r in reasons),
        raw_json=json.dumps(raw, default=str),
    )


def decision_to_dict(decision: SignalDecision) -> dict:
    return asdict(decision)
