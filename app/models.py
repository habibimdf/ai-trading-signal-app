from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    pair: Mapped[str] = mapped_column(String(20), index=True)
    mode: Mapped[str] = mapped_column(String(20), default="swing")
    signal: Mapped[str] = mapped_column(String(10), default="WAIT")
    status: Mapped[str] = mapped_column(String(30), default="NEW")

    entry_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    entry_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    stop_loss: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    take_profit_1: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    take_profit_2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    take_profit_3: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    risk_reward: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    confidence: Mapped[int] = mapped_column(Integer, default=0)
    lot_size: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    risk_amount_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    account_type: Mapped[str] = mapped_column(String(10), default="USD")
    balance: Mapped[float] = mapped_column(Float, default=0)
    risk_percent: Mapped[float] = mapped_column(Float, default=1)

    h4_bias: Mapped[str] = mapped_column(String(20), default="NEUTRAL")
    h1_confirmation: Mapped[str] = mapped_column(String(30), default="NONE")
    reason: Mapped[str] = mapped_column(Text, default="")
    raw_json: Mapped[str] = mapped_column(Text, default="{}")
