from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db, init_db
from .models import Signal
from .schemas import AnalyzeRequest, SendAlertRequest, SignalResponse, TradingViewWebhook
from .services.ai_reasoning import generate_ai_reasoning
from .services.formatter import format_signal_message
from .services.market_data import CandleRequest, SUPPORTED_PAIRS, get_provider
from .services.notifier import NotificationError, send_telegram, send_whatsapp_text
from .services.risk import calculate_lot_size

settings = get_settings()
app = FastAPI(title=settings.app_name, version="1.0.0")
TRADINGVIEW_PROVIDER_NAMES = {"tradingview", "webhook"}
MODE_TIMEFRAMES = {
    "swing": {"analysis": "H4", "execution": "H1"},
    "scalping": {"analysis": "M15", "execution": "M5"},
}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.on_event("startup")
def on_startup():
    init_db()
    provider_name = settings.data_provider.lower().strip()
    if settings.enable_scheduler and provider_name not in TRADINGVIEW_PROVIDER_NAMES:
        from .scheduler import start_scheduler

        start_scheduler(app)


@app.get("/")
def index():
    return FileResponse("app/static/index.html")


@app.get("/api/health")
def health():
    ai_provider = settings.ai_provider.lower().strip()
    ai_model = settings.gemini_model if ai_provider == "gemini" else settings.openai_model
    return {
        "ok": True,
        "app": settings.app_name,
        "provider": settings.data_provider,
        "ai_reasoning_enabled": settings.enable_ai_reasoning,
        "ai_provider": ai_provider if settings.enable_ai_reasoning else None,
        "ai_model": ai_model if settings.enable_ai_reasoning else None,
        "time": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/markets")
def markets():
    return {
        "pairs": SUPPORTED_PAIRS,
        "modes": ["swing", "scalping"],
        "mode_timeframes": MODE_TIMEFRAMES,
        "provider": settings.data_provider,
        "scheduler_enabled": settings.enable_scheduler,
    }


def create_signal_from_request(payload: AnalyzeRequest, db: Session) -> Signal:
    if settings.data_provider.lower().strip() in TRADINGVIEW_PROVIDER_NAMES:
        raise HTTPException(
            status_code=400,
            detail="DATA_PROVIDER=tradingview memakai data dari POST /webhook/tradingview, bukan analisis lokal.",
        )

    provider = get_provider(settings)
    pair = payload.pair.replace("/", "_").upper()
    if pair not in SUPPORTED_PAIRS:
        raise HTTPException(status_code=400, detail=f"Pair tidak didukung: {pair}")

    try:
        from .services.signal_engine import generate_signal

        h4 = provider.get_candles(CandleRequest(pair=pair, timeframe="H4", count=320))
        h1 = provider.get_candles(CandleRequest(pair=pair, timeframe="H1", count=420))
        decision = generate_signal(
            pair=pair,
            mode=payload.mode,
            h4_raw=h4,
            h1_raw=h1,
            balance=payload.balance,
            account_type=payload.account_type,
            risk_percent=payload.risk_percent,
            min_confidence=settings.min_confidence,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    signal = Signal(**decision.__dict__)
    db.add(signal)
    db.commit()
    db.refresh(signal)
    return signal


@app.post("/api/analyze", response_model=SignalResponse)
def analyze(payload: AnalyzeRequest, db: Session = Depends(get_db)):
    return create_signal_from_request(payload, db)


@app.get("/api/signals", response_model=list[SignalResponse])
def list_signals(limit: int = 30, db: Session = Depends(get_db)):
    limit = min(max(limit, 1), 200)
    return db.query(Signal).order_by(Signal.created_at.desc()).limit(limit).all()


@app.get("/api/signals/{signal_id}", response_model=SignalResponse)
def get_signal(signal_id: int, db: Session = Depends(get_db)):
    signal = db.get(Signal, signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail="Signal tidak ditemukan")
    return signal


@app.delete("/api/signals")
def clear_signals(db: Session = Depends(get_db)):
    deleted = db.query(Signal).delete()
    db.commit()
    return {"ok": True, "deleted": deleted}


@app.post("/api/send-alert/{signal_id}")
async def send_alert(signal_id: int, payload: SendAlertRequest, db: Session = Depends(get_db)):
    signal = db.get(Signal, signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail="Signal tidak ditemukan")

    text = format_signal_message(signal)
    results = {}
    try:
        if payload.channel in ["telegram", "both"]:
            results["telegram"] = await send_telegram(settings, text)
        if payload.channel in ["whatsapp", "both"]:
            results["whatsapp"] = await send_whatsapp_text(settings, text)
    except NotificationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    signal.status = f"SENT_{payload.channel.upper()}"
    db.add(signal)
    db.commit()
    return {"ok": True, "channel": payload.channel, "results": results}


@app.post("/api/scan-now", response_model=list[SignalResponse])
def scan_now(db: Session = Depends(get_db)):
    if settings.data_provider.lower().strip() in TRADINGVIEW_PROVIDER_NAMES:
        raise HTTPException(
            status_code=400,
            detail="Mode TradingView tidak memakai scan otomatis lokal. Kirim alert dari TradingView ke /webhook/tradingview.",
        )

    created: list[Signal] = []
    for pair in settings.pairs_list():
        payload = AnalyzeRequest(
            pair=pair,
            mode=settings.default_mode,
            balance=settings.default_balance,
            account_type=settings.default_account_type,
            risk_percent=settings.default_risk_percent,
        )
        created.append(create_signal_from_request(payload, db))
    return created


def _first_payload_value(raw: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        value = raw.get(key)
        if value is not None and value != "":
            return value
    return None


def _float_payload_value(raw: dict[str, Any], keys: list[str]) -> float | None:
    value = _first_payload_value(raw, keys)
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except ValueError:
        return None


def _bounded_float(value: float | None, default: float, min_value: float, max_value: float | None = None) -> float:
    if value is None:
        return default
    value = max(value, min_value)
    if max_value is not None:
        value = min(value, max_value)
    return value


def _normalize_tradingview_pair(value: Any) -> str:
    symbol = str(value or "XAU_USD").strip().upper()
    if ":" in symbol:
        symbol = symbol.split(":")[-1]
    symbol = symbol.replace("/", "_").replace("-", "_")
    compact = symbol.replace("_", "")
    if compact == "BTCUSDT":
        return "BTC_USDT"
    if "_" not in symbol and len(compact) == 6:
        return f"{compact[:3]}_{compact[3:]}"
    if compact == "XAUUSD":
        return "XAU_USD"
    return symbol


def _normalize_tradingview_mode(value: Any) -> str:
    mode = str(value or settings.default_mode).strip().lower()
    return mode if mode in MODE_TIMEFRAMES else "swing"


def _normalize_account_type(value: Any) -> str:
    account_type = str(value or settings.default_account_type).strip().upper()
    if account_type in ["USC", "CENT", "CENT_ACCOUNT"]:
        return "USC"
    return "USD"


def _normalize_tradingview_signal(value: Any) -> str:
    action = str(value or "WAIT").strip().upper()
    if action in ["BUY", "LONG", "ENTRY_LONG", "OPEN_LONG"]:
        return "BUY"
    if action in ["SELL", "SHORT", "ENTRY_SHORT", "OPEN_SHORT"]:
        return "SELL"
    return "WAIT"


def _auto_signal_from_payload(raw: dict[str, Any], signal_value: Any) -> str:
    signal_text = str(signal_value or "").strip().upper()
    if signal_text and signal_text not in ["AUTO", "AUTOMATIC", "RECOMMEND", "RECOMMENDATION"]:
        return _normalize_tradingview_signal(signal_value)

    bias = str(
        _first_payload_value(raw, ["analysis_bias", "bias", "trend", "h4_bias", "m15_bias"]) or ""
    ).strip().upper()
    confirmation = str(
        _first_payload_value(raw, ["execution_confirmation", "confirmation", "entry_confirmation", "h1_confirmation", "m5_confirmation"])
        or ""
    ).strip().upper()

    bullish_bias = any(token in bias for token in ["BULL", "BUY", "LONG", "UP"])
    bearish_bias = any(token in bias for token in ["BEAR", "SELL", "SHORT", "DOWN"])
    bullish_confirmation = any(token in confirmation for token in ["BULL", "BUY", "LONG", "UP"])
    bearish_confirmation = any(token in confirmation for token in ["BEAR", "SELL", "SHORT", "DOWN"])

    if bullish_bias and bullish_confirmation:
        return "BUY"
    if bearish_bias and bearish_confirmation:
        return "SELL"
    return "WAIT"


def _risk_reward(entry: float | None, stop_loss: float | None, targets: list[float | None]) -> float | None:
    if entry is None or stop_loss is None:
        return None
    risk = abs(entry - stop_loss)
    target = next((target for target in targets if target is not None), None)
    if risk <= 0 or target is None:
        return None
    return round(abs(target - entry) / risk, 2)


def _redacted_payload(raw: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(raw)
    for key in ["secret", "token", "webhook_secret"]:
        if key in redacted:
            redacted[key] = "***"
    return redacted


def _validate_tradingview_secret(raw: dict[str, Any]) -> None:
    expected = settings.tradingview_webhook_secret.strip()
    if not expected:
        return
    provided = _first_payload_value(raw, ["secret", "token", "webhook_secret"])
    if str(provided or "").strip() != expected:
        raise HTTPException(status_code=403, detail="TradingView webhook secret tidak valid.")


def _tradingview_reason(
    raw: dict[str, Any],
    note: str,
    price: float | None,
    mode: str,
    account_type: str,
    balance: float,
    risk_percent: float,
) -> str:
    timeframe = _first_payload_value(raw, ["timeframe", "interval", "tf"])
    time_value = _first_payload_value(raw, ["time", "timenow"])
    exchange = _first_payload_value(raw, ["exchange"])
    analysis_bias = _first_payload_value(raw, ["analysis_bias", "bias", "trend", "h4_bias", "m15_bias"])
    execution_confirmation = _first_payload_value(
        raw, ["execution_confirmation", "confirmation", "entry_confirmation", "h1_confirmation", "m5_confirmation"]
    )
    mode_tf = MODE_TIMEFRAMES[mode]
    lines = [
        "- Alert real dari TradingView",
        f"- Mode: {mode.upper()}",
        f"- Timeframe analisis: {mode_tf['analysis']}",
        f"- Timeframe eksekusi: {mode_tf['execution']}",
        f"- Account: {account_type}",
        f"- Balance: {balance}",
        f"- Risk: {risk_percent}%",
        f"- Note: {note}",
    ]
    if analysis_bias:
        lines.append(f"- Bias analisis: {analysis_bias}")
    if execution_confirmation:
        lines.append(f"- Konfirmasi eksekusi: {execution_confirmation}")
    if timeframe:
        lines.append(f"- Timeframe: {timeframe}")
    if price is not None:
        lines.append(f"- Price: {price}")
    if exchange:
        lines.append(f"- Exchange: {exchange}")
    if time_value:
        lines.append(f"- Time: {time_value}")
    return "\n".join(lines)


@app.post("/webhook/tradingview")
async def tradingview_webhook(payload: TradingViewWebhook, db: Session = Depends(get_db)):
    """Receive TradingView alert data, store it, then optionally forward it to Telegram."""
    raw = payload.model_dump(exclude_none=True)
    _validate_tradingview_secret(raw)

    pair_value = _first_payload_value(raw, ["pair", "symbol", "ticker", "tickerid"])
    mode = _normalize_tradingview_mode(_first_payload_value(raw, ["mode", "trade_mode", "style"]))
    signal_value = _first_payload_value(raw, ["signal", "action", "side", "strategy.order.action", "strategy_action"])
    note = str(_first_payload_value(raw, ["note", "message", "comment", "strategy.order.comment"]) or "TradingView alert")
    price = _float_payload_value(raw, ["price", "close", "entry", "entry_price", "order_price", "strategy.order.price"])
    stop_loss = _float_payload_value(raw, ["stop_loss", "sl"])
    take_profit_1 = _float_payload_value(raw, ["take_profit_1", "tp1", "take_profit"])
    take_profit_2 = _float_payload_value(raw, ["take_profit_2", "tp2"])
    take_profit_3 = _float_payload_value(raw, ["take_profit_3", "tp3"])
    confidence = int(_bounded_float(_float_payload_value(raw, ["confidence"]), 0, 0, 100))
    balance = _bounded_float(_float_payload_value(raw, ["balance", "modal", "equity", "account_balance"]), settings.default_balance, 0.01)
    account_type = _normalize_account_type(_first_payload_value(raw, ["account_type", "account", "currency", "modal_type"]))
    risk_percent = _bounded_float(
        _float_payload_value(raw, ["risk_percent", "risk", "risk_pct"]),
        settings.default_risk_percent,
        0.01,
        10,
    )

    pair = _normalize_tradingview_pair(pair_value)
    if pair not in SUPPORTED_PAIRS:
        raise HTTPException(status_code=400, detail=f"Pair tidak didukung: {pair}")

    trading_signal = _auto_signal_from_payload(raw, signal_value)
    reason = _tradingview_reason(raw, note, price, mode, account_type, balance, risk_percent)
    risk_reward = _risk_reward(price, stop_loss, [take_profit_2, take_profit_1, take_profit_3])
    lot_size = None
    risk_amount_usd = None
    if trading_signal in ["BUY", "SELL"] and price is not None and stop_loss is not None:
        risk_calc = calculate_lot_size(
            pair=pair,
            entry=price,
            stop_loss=stop_loss,
            balance=balance,
            account_type=account_type,
            risk_percent=risk_percent,
        )
        lot_size = risk_calc["lot_size"]
        risk_amount_usd = risk_calc["risk_amount_usd"]

    mode_tf = MODE_TIMEFRAMES[mode]
    signal = Signal(
        pair=pair,
        mode=mode,
        signal=trading_signal,
        status="TRADINGVIEW_ALERT",
        entry_min=price,
        entry_max=price,
        stop_loss=stop_loss,
        take_profit_1=take_profit_1,
        take_profit_2=take_profit_2,
        take_profit_3=take_profit_3,
        risk_reward=risk_reward,
        confidence=confidence,
        lot_size=lot_size,
        risk_amount_usd=risk_amount_usd,
        account_type=account_type,
        balance=balance,
        risk_percent=risk_percent,
        h4_bias=f"ANALYSIS_{mode_tf['analysis']}",
        h1_confirmation=f"EXECUTION_{mode_tf['execution']}",
        reason=reason,
        raw_json=json.dumps(_redacted_payload(raw), default=str),
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)

    ai_reasoning_added = False
    if settings.enable_ai_reasoning:
        try:
            ai_reasoning = await generate_ai_reasoning(settings, signal, raw)
            signal.reason = f"{signal.reason}\n\nAI Reasoning Tambahan:\n{ai_reasoning}"
            ai_reasoning_added = True
            db.add(signal)
            db.commit()
            db.refresh(signal)
        except Exception as exc:
            signal.reason = f"{signal.reason}\n\nAI Reasoning Tambahan: gagal dibuat ({exc})."
            db.add(signal)
            db.commit()
            db.refresh(signal)

    telegram_sent = False
    # Forward only if Telegram is configured. Failure will not reject the webhook.
    if settings.telegram_bot_token and settings.telegram_chat_id:
        try:
            await send_telegram(settings, format_signal_message(signal))
            signal.status = "TRADINGVIEW_SENT_TELEGRAM"
            db.add(signal)
            db.commit()
            telegram_sent = True
        except Exception:
            pass

    return {"ok": True, "id": signal.id, "telegram_sent": telegram_sent, "ai_reasoning_added": ai_reasoning_added}
