from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from .db import Base


class Signal(Base):
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    pair = Column(String(20), index=True, nullable=False)
    mode = Column(String(20), default="swing", nullable=False)
    signal = Column(String(10), default="WAIT", nullable=False)
    status = Column(String(30), default="NEW", nullable=False)

    entry_min = Column(Float, nullable=True)
    entry_max = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    take_profit_1 = Column(Float, nullable=True)
    take_profit_2 = Column(Float, nullable=True)
    take_profit_3 = Column(Float, nullable=True)

    risk_reward = Column(Float, nullable=True)
    confidence = Column(Integer, default=0, nullable=False)
    lot_size = Column(Float, nullable=True)
    risk_amount_usd = Column(Float, nullable=True)
    account_type = Column(String(10), default="USD", nullable=False)
    balance = Column(Float, default=0, nullable=False)
    risk_percent = Column(Float, default=1, nullable=False)

    h4_bias = Column(String(20), default="NEUTRAL", nullable=False)
    h1_confirmation = Column(String(30), default="NONE", nullable=False)
    reason = Column(Text, default="", nullable=False)
    raw_json = Column(Text, default="{}", nullable=False)
