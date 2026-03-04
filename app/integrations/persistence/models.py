from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class WebhookDeliveryRecord(Base):
    __tablename__ = "webhook_deliveries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    delivery_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    event_type: Mapped[str] = mapped_column(String(100))
    action: Mapped[str | None] = mapped_column(String(100), nullable=True)
    repo_full_name: Mapped[str] = mapped_column(String(255))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32))
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class NotificationLogRecord(Base):
    __tablename__ = "notification_log"
    __table_args__ = (UniqueConstraint("dedupe_key", name="uq_notification_log_dedupe_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repo_full_name: Mapped[str] = mapped_column(String(255), index=True)
    pr_number: Mapped[int] = mapped_column(Integer, index=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    dedupe_key: Mapped[str] = mapped_column(String(255))
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    destination: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32))


class PRRateLimitRecord(Base):
    __tablename__ = "pr_rate_limits"
    __table_args__ = (
        UniqueConstraint("repo_full_name", "pr_number", "event_type", name="uq_pr_rate_limits_scope"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repo_full_name: Mapped[str] = mapped_column(String(255), index=True)
    pr_number: Mapped[int] = mapped_column(Integer, index=True)
    event_type: Mapped[str] = mapped_column(String(100))
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_count_today: Mapped[int] = mapped_column(Integer, default=0)
    day_bucket: Mapped[str] = mapped_column(String(32))


class PRSnapshotRecord(Base):
    __tablename__ = "pr_snapshots"
    __table_args__ = (UniqueConstraint("repo_full_name", "pr_number", name="uq_pr_snapshots_scope"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repo_full_name: Mapped[str] = mapped_column(String(255), index=True)
    pr_number: Mapped[int] = mapped_column(Integer, index=True)
    title: Mapped[str] = mapped_column(String(512))
    author: Mapped[str] = mapped_column(String(255))
    is_draft: Mapped[bool]
    state: Mapped[str] = mapped_column(String(64))
    head_sha: Mapped[str] = mapped_column(String(255))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    merged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
