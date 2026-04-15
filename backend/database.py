"""SQLAlchemy engine, session factory, and declarative Base."""
from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime

from sqlalchemy import DateTime, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.sql import func

from backend.config import get_settings


def _engine_kwargs(database_url: str) -> dict:
    """Extra kwargs for the SQLAlchemy engine depending on dialect."""
    # SQLite needs ``check_same_thread=False`` so FastAPI's thread pool works,
    # and we use a NullPool-friendly URL for in-memory test DBs elsewhere.
    if database_url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    return {}


settings = get_settings()
engine = create_engine(settings.database_url, **_engine_kwargs(settings.database_url))
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    """Declarative base with shared timestamp columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


def get_db() -> Iterator:
    """FastAPI dependency that yields a scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
