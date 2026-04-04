"""SQLAlchemy ORM models — PostgreSQL schema for the swarm's persistent memory.

Tables
------
runs        — one row per pipeline execution cycle
ideas       — every generated idea with its filter outcome
metrics     — conversion events per idea (clicks, signups, payments)
weights     — per-feature scoring weights updated by the learning agent
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class RunRecord(Base):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    signals_mined: Mapped[int] = mapped_column(Integer, default=0)
    ideas_generated: Mapped[int] = mapped_column(Integer, default=0)
    ideas_passed: Mapped[int] = mapped_column(Integer, default=0)
    plans_built: Mapped[int] = mapped_column(Integer, default=0)
    deployed_url: Mapped[str] = mapped_column(Text, default="")
    total_revenue: Mapped[float] = mapped_column(Float, default=0.0)

    ideas: Mapped[list[IdeaRecord]] = relationship("IdeaRecord", back_populates="run")


class IdeaRecord(Base):
    __tablename__ = "ideas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), ForeignKey("runs.run_id"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(64), default="")
    problem: Mapped[str] = mapped_column(Text, default="")
    target_user: Mapped[str] = mapped_column(Text, default="")
    solution: Mapped[str] = mapped_column(Text, default="")
    passed: Mapped[int] = mapped_column(Integer, default=0)  # 0 | 1
    score: Mapped[float] = mapped_column(Float, default=0.0)
    reject_reason: Mapped[str] = mapped_column(String(64), default="")
    mvp_format: Mapped[str] = mapped_column(String(64), default="")
    deployed_url: Mapped[str] = mapped_column(Text, default="")
    features: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    run: Mapped[RunRecord] = relationship("RunRecord", back_populates="ideas")
    metrics: Mapped[list[MetricRecord]] = relationship("MetricRecord", back_populates="idea")


class MetricRecord(Base):
    __tablename__ = "metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    idea_id: Mapped[int] = mapped_column(Integer, ForeignKey("ideas.id"), nullable=False, index=True)
    tracking_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    signups: Mapped[int] = mapped_column(Integer, default=0)
    payments: Mapped[int] = mapped_column(Integer, default=0)
    revenue: Mapped[float] = mapped_column(Float, default=0.0)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    idea: Mapped[IdeaRecord] = relationship("IdeaRecord", back_populates="metrics")


class WeightRecord(Base):
    __tablename__ = "weights"

    feature: Mapped[str] = mapped_column(String(128), primary_key=True)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
