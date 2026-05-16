from __future__ import annotations

from app.models import Signal


def _format_optional(label: str, value: object) -> str:
    return f"{label}: {value}\n" if value is not None else ""


def _format_tradingview_message(signal: Signal) -> str:
    message = (
        "TRADINGVIEW ALERT\n\n"
        f"Pair: {signal.pair}\n"
        f"Mode: {signal.mode.upper()}\n"
        f"Timeframe Analisis: {signal.h4_bias.replace('ANALYSIS_', '')}\n"
        f"Timeframe Eksekusi: {signal.h1_confirmation.replace('EXECUTION_', '')}\n\n"
        f"Signal: {signal.signal}\n"
        f"Status: {signal.status}\n\n"
        f"{_format_optional('Price', signal.entry_min)}"
        f"{_format_optional('Stop Loss', signal.stop_loss)}"
        f"{_format_optional('TP1', signal.take_profit_1)}"
        f"{_format_optional('TP2', signal.take_profit_2)}"
        f"{_format_optional('TP3', signal.take_profit_3)}"
        f"Account: {signal.account_type}\n"
        f"Balance: {signal.balance}\n"
        f"Risk: {signal.risk_percent}%\n"
        f"{_format_optional('Risk Amount USD', signal.risk_amount_usd)}"
        f"{_format_optional('Lot Rekomendasi', signal.lot_size)}"
        f"{_format_optional('Risk/Reward', f'1:{signal.risk_reward}' if signal.risk_reward is not None else None)}"
    )
    if signal.confidence:
        message += f"Confidence: {signal.confidence}%\n"
    return (
        f"{message}\n"
        f"Detail:\n{signal.reason}\n\n"
        f"Catatan: Sinyal berasal dari TradingView webhook. Ini bukan auto-trading."
    )


def format_signal_message(signal: Signal) -> str:
    if signal.status.startswith("TRADINGVIEW"):
        return _format_tradingview_message(signal)

    header = "[BUY]" if signal.signal == "BUY" else "[SELL]" if signal.signal == "SELL" else "[WAIT]"

    if signal.signal == "WAIT":
        return (
            f"{header} AI TRADING SIGNAL\n\n"
            f"Pair: {signal.pair}\n"
            f"Mode: {signal.mode.upper()}\n"
            f"Timeframe Analisis: H4\n"
            f"Timeframe Entry: H1\n\n"
            f"Signal: WAIT\n"
            f"Confidence: {signal.confidence}%\n"
            f"Status: {signal.status}\n\n"
            f"Alasan:\n{signal.reason}\n\n"
            f"Catatan: Tidak ada entry. Tunggu setup yang lebih valid."
        )

    return (
        f"{header} AI TRADING SIGNAL\n\n"
        f"Pair: {signal.pair}\n"
        f"Mode: {signal.mode.upper()}\n"
        f"Timeframe Analisis: H4\n"
        f"Timeframe Entry: H1\n\n"
        f"Signal: {signal.signal}\n"
        f"Entry Area: {signal.entry_min} - {signal.entry_max}\n"
        f"Stop Loss: {signal.stop_loss}\n\n"
        f"Take Profit:\n"
        f"TP1: {signal.take_profit_1}\n"
        f"TP2: {signal.take_profit_2}\n"
        f"TP3: {signal.take_profit_3}\n\n"
        f"Risk: {signal.risk_percent}% dari modal\n"
        f"Risk Amount: ${signal.risk_amount_usd}\n"
        f"Lot Rekomendasi: {signal.lot_size}\n"
        f"Risk/Reward: 1:{signal.risk_reward}\n"
        f"Confidence: {signal.confidence}%\n"
        f"Status: {signal.status}\n\n"
        f"Alasan:\n{signal.reason}\n\n"
        f"Catatan: Ini bukan auto-trading. Entry manual dan tetap wajib cek kondisi market/news."
    )
