from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AnalyzeRequest(BaseModel):
    pair: str = Field(default="XAU_USD")
    mode: str = Field(default="swing", pattern="^(swing|scalping)$")
    balance: float = Field(default=1000, gt=0)
    account_type: str = Field(default="USD", pattern="^(USD|USC)$")
    risk_percent: float = Field(default=1, gt=0, le=10)


class SignalResponse(BaseModel):
    id: int
    created_at: datetime
    pair: str
    mode: str
    signal: str
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

    model_config = {"from_attributes": True}


class SendAlertRequest(BaseModel):
    channel: str = Field(default="telegram", pattern="^(telegram|whatsapp|both)$")


class TradingViewWebhook(BaseModel):
    model_config = ConfigDict(extra="allow")

    pair: Any = None
    signal: Any = None
    mode: Any = None
    price: Any = None
    stop_loss: Any = None
    tp1: Any = None
    tp2: Any = None
    tp3: Any = None
    balance: Any = None
    account_type: Any = None
    risk_percent: Any = None
    note: Any = None
