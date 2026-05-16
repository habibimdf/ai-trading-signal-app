from __future__ import annotations

import asyncio

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from .config import get_settings
from .db import SessionLocal
from .models import Signal
from .schemas import AnalyzeRequest
from .services.formatter import format_signal_message
from .services.market_data import CandleRequest, SUPPORTED_PAIRS, get_provider
from .services.notifier import send_telegram, send_whatsapp_text
from .services.signal_engine import generate_signal

settings = get_settings()
_scheduler: BackgroundScheduler | None = None


def _run_scan_job():
    provider = get_provider(settings)
    db: Session = SessionLocal()
    try:
        for pair in settings.pairs_list():
            pair = pair.replace("/", "_").upper()
            if pair not in SUPPORTED_PAIRS:
                continue

            h4 = provider.get_candles(CandleRequest(pair=pair, timeframe="H4", count=320))
            h1 = provider.get_candles(CandleRequest(pair=pair, timeframe="H1", count=420))
            decision = generate_signal(
                pair=pair,
                mode=settings.default_mode,
                h4_raw=h4,
                h1_raw=h1,
                balance=settings.default_balance,
                account_type=settings.default_account_type,
                risk_percent=settings.default_risk_percent,
                min_confidence=settings.min_confidence,
            )
            signal = Signal(**decision.__dict__)
            db.add(signal)
            db.commit()
            db.refresh(signal)

            # Only send VALID BUY/SELL setups automatically, not WAIT.
            if signal.signal in ["BUY", "SELL"] and signal.status == "VALID_SETUP":
                text = format_signal_message(signal)
                asyncio.run(_send_configured_alerts(text))
                signal.status = "AUTO_SENT"
                db.add(signal)
                db.commit()
    finally:
        db.close()


async def _send_configured_alerts(text: str):
    if settings.telegram_bot_token and settings.telegram_chat_id:
        await send_telegram(settings, text)
    if settings.whatsapp_access_token and settings.whatsapp_phone_number_id and settings.whatsapp_to_number:
        await send_whatsapp_text(settings, text)


def start_scheduler(app):
    global _scheduler
    if _scheduler:
        return
    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(_run_scan_job, "interval", minutes=settings.scan_interval_minutes, id="market-scan", replace_existing=True)
    _scheduler.start()

    @app.on_event("shutdown")
    def shutdown_scheduler():
        if _scheduler:
            _scheduler.shutdown()
