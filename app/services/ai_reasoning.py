from __future__ import annotations

import json
from typing import Any

import httpx

from app.config import Settings
from app.models import Signal


class AIReasoningError(RuntimeError):
    pass


def _extract_response_text(data: dict[str, Any]) -> str:
    output_text = data.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    parts: list[str] = []
    for item in data.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            text = content.get("text")
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
    return "\n".join(parts).strip()


def _compact_payload(raw: dict[str, Any]) -> dict[str, Any]:
    allowed_keys = [
        "pair",
        "ticker",
        "exchange",
        "mode",
        "analysis_timeframe",
        "execution_timeframe",
        "analysis_bias",
        "execution_confirmation",
        "signal",
        "confidence",
        "price",
        "stop_loss",
        "tp1",
        "tp2",
        "tp3",
        "balance",
        "account_type",
        "risk_percent",
        "timeframe",
        "time",
        "note",
        "news",
        "analysis_close",
        "analysis_ema50",
        "analysis_ema200",
        "analysis_rsi",
        "execution_close",
        "execution_ema50",
        "execution_rsi",
        "execution_atr",
    ]
    return {key: raw[key] for key in allowed_keys if raw.get(key) not in [None, ""]}


def build_ai_prompt(signal: Signal, raw: dict[str, Any]) -> str:
    context = {
        "stored_signal": {
            "pair": signal.pair,
            "mode": signal.mode,
            "signal": signal.signal,
            "status": signal.status,
            "entry": signal.entry_min,
            "stop_loss": signal.stop_loss,
            "tp1": signal.take_profit_1,
            "tp2": signal.take_profit_2,
            "tp3": signal.take_profit_3,
            "risk_reward": signal.risk_reward,
            "confidence": signal.confidence,
            "lot_size": signal.lot_size,
            "risk_amount_usd": signal.risk_amount_usd,
            "account_type": signal.account_type,
            "balance": signal.balance,
            "risk_percent": signal.risk_percent,
        },
        "tradingview_payload": _compact_payload(raw),
    }
    return (
        "Beri reasoning tambahan untuk sinyal trading berikut dalam Bahasa Indonesia.\n"
        "Fokus pada validasi teknikal, risiko, dan kondisi yang perlu diwaspadai.\n"
        "Jangan menjanjikan profit. Jangan menyuruh entry agresif. Jika data kurang, sebutkan keterbatasannya.\n"
        "Format jawaban maksimal 6 bullet singkat.\n\n"
        f"DATA:\n{json.dumps(context, ensure_ascii=False, default=str)}"
    )


async def generate_ai_reasoning(settings: Settings, signal: Signal, raw: dict[str, Any]) -> str:
    if not settings.enable_ai_reasoning:
        return ""
    if not settings.openai_api_key:
        raise AIReasoningError("OPENAI_API_KEY belum diisi.")

    url = settings.openai_base_url.rstrip("/") + "/responses"
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.openai_model,
        "store": False,
        "instructions": (
            "Anda adalah analis risiko trading yang konservatif. "
            "Tugas Anda hanya memberi reasoning tambahan, bukan keputusan final atau nasihat keuangan."
        ),
        "input": build_ai_prompt(signal, raw),
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(url, headers=headers, json=payload)

    if response.status_code >= 300:
        raise AIReasoningError(f"OpenAI error {response.status_code}: {response.text[:300]}")

    text = _extract_response_text(response.json())
    if not text:
        raise AIReasoningError("OpenAI tidak mengembalikan teks reasoning.")
    return text[:1800]
