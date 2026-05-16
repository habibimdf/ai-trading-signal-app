from __future__ import annotations

import json
from typing import Any

import httpx

from app.config import Settings
from app.models import Signal


class AIReasoningError(RuntimeError):
    pass


def _extract_openai_response_text(data: dict[str, Any]) -> str:
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


def _extract_gemini_response_text(data: dict[str, Any]) -> str:
    parts: list[str] = []
    for candidate in data.get("candidates", []):
        if not isinstance(candidate, dict):
            continue
        content = candidate.get("content")
        if not isinstance(content, dict):
            continue
        for part in content.get("parts", []):
            if not isinstance(part, dict):
                continue
            text = part.get("text")
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


def _system_instruction() -> str:
    return (
        "Anda adalah analis risiko trading yang konservatif. "
        "Tugas Anda hanya memberi reasoning tambahan, bukan keputusan final atau nasihat keuangan."
    )


async def _generate_gemini_reasoning(settings: Settings, signal: Signal, raw: dict[str, Any]) -> str:
    if not settings.gemini_api_key:
        raise AIReasoningError("GEMINI_API_KEY belum diisi.")

    model = settings.gemini_model.strip().removeprefix("models/")
    url = f"{settings.gemini_base_url.rstrip('/')}/models/{model}:generateContent"
    thinking_level = settings.gemini_thinking_level.strip().lower() or "low"
    payload = {
        "system_instruction": {"parts": [{"text": _system_instruction()}]},
        "contents": [
            {
                "parts": [
                    {
                        "text": build_ai_prompt(signal, raw),
                    }
                ]
            }
        ],
        "generationConfig": {
            "maxOutputTokens": 900,
            "thinkingConfig": {
                "thinkingLevel": thinking_level,
            },
        },
    }
    headers = {
        "x-goog-api-key": settings.gemini_api_key,
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(url, headers=headers, json=payload)

    if response.status_code >= 300:
        raise AIReasoningError(f"Gemini error {response.status_code}: {response.text[:300]}")

    data = response.json()
    text = _extract_gemini_response_text(data)
    if not text:
        finish_reason = None
        candidates = data.get("candidates") or []
        if candidates and isinstance(candidates[0], dict):
            finish_reason = candidates[0].get("finishReason")
        detail = f" Finish reason: {finish_reason}." if finish_reason else ""
        raise AIReasoningError(f"Gemini tidak mengembalikan teks reasoning.{detail}")
    return text[:1800]


async def _generate_openai_reasoning(settings: Settings, signal: Signal, raw: dict[str, Any]) -> str:
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
        "instructions": _system_instruction(),
        "input": build_ai_prompt(signal, raw),
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(url, headers=headers, json=payload)

    if response.status_code >= 300:
        raise AIReasoningError(f"OpenAI error {response.status_code}: {response.text[:300]}")

    text = _extract_openai_response_text(response.json())
    if not text:
        raise AIReasoningError("OpenAI tidak mengembalikan teks reasoning.")
    return text[:1800]


async def generate_ai_reasoning(settings: Settings, signal: Signal, raw: dict[str, Any]) -> str:
    if not settings.enable_ai_reasoning:
        return ""

    provider = settings.ai_provider.lower().strip()
    if provider == "gemini":
        return await _generate_gemini_reasoning(settings, signal, raw)
    if provider == "openai":
        return await _generate_openai_reasoning(settings, signal, raw)
    raise AIReasoningError(f"AI_PROVIDER tidak didukung: {settings.ai_provider}")
