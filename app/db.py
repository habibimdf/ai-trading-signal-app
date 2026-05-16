import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import NullPool

from .config import get_settings

settings = get_settings()
database_url = settings.database_url
if os.environ.get("VERCEL") and database_url == "sqlite:///./signals.db":
    # Vercel Functions can only write temporary runtime files under /tmp.
    # Set DATABASE_URL to Postgres/Supabase for persistent production history.
    database_url = "sqlite:////tmp/signals.db"

if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
elif database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)

connect_args = {}
engine_kwargs = {}
if database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
else:
    connect_args = {"prepare_threshold": None}
    if os.environ.get("VERCEL"):
        engine_kwargs["poolclass"] = NullPool

engine = create_engine(database_url, connect_args=connect_args, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
