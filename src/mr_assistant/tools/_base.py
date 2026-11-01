"""Shared pieces for tools: base model and snapshot helpers."""

from datetime import date

from pydantic import BaseModel, ConfigDict

from mr_assistant.db import Db


class Out(BaseModel):
    """Base for tool outputs: immutable, serialisable to JSON for an LLM."""
    model_config = ConfigDict(frozen=True)


def as_of(db: Db) -> date:
    """Snapshot date: the last day with field activity."""
    return db.scalar("SELECT analytics.as_of_date()")


def current_month(db: Db) -> int:
    return db.scalar("SELECT analytics.ym_of(analytics.as_of_date())")


def month_or_current(db: Db, year_month: int | None) -> int:
    return year_month if year_month is not None else current_month(db)
