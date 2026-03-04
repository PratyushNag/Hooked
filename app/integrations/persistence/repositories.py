from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.core.domain.enums import DeliveryStatus
from app.core.domain.models import PRSnapshot, RateLimitState
from app.core.ports.repository import RepositoryPort
from app.integrations.persistence.models import (
    NotificationLogRecord,
    PRRateLimitRecord,
    PRSnapshotRecord,
    WebhookDeliveryRecord,
)


class SQLAlchemyRepository(RepositoryPort):
    def __init__(self, session_factory: sessionmaker):
        self._session_factory = session_factory

    @contextmanager
    def _session(self):
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def record_webhook_delivery(self, delivery_id: str, event_type: str, action: str | None, repo_full_name: str) -> bool:
        with self._session() as session:
            record = WebhookDeliveryRecord(
                delivery_id=delivery_id,
                event_type=event_type,
                action=action,
                repo_full_name=repo_full_name,
                received_at=datetime.now(timezone.utc),
                processed_at=None,
                status=DeliveryStatus.RECEIVED.value,
                error_message=None,
            )
            session.add(record)
            try:
                session.flush()
                return True
            except IntegrityError:
                session.rollback()
                return False

    def mark_webhook_processed(self, delivery_id: str) -> None:
        with self._session() as session:
            record = session.execute(
                select(WebhookDeliveryRecord).where(WebhookDeliveryRecord.delivery_id == delivery_id)
            ).scalar_one()
            record.status = DeliveryStatus.PROCESSED.value
            record.processed_at = datetime.now(timezone.utc)
            record.error_message = None

    def mark_webhook_failed(self, delivery_id: str, error_message: str) -> None:
        with self._session() as session:
            record = session.execute(
                select(WebhookDeliveryRecord).where(WebhookDeliveryRecord.delivery_id == delivery_id)
            ).scalar_one()
            record.status = DeliveryStatus.FAILED.value
            record.processed_at = datetime.now(timezone.utc)
            record.error_message = error_message[:4000]

    def has_notification(self, dedupe_key: str) -> bool:
        with self._session() as session:
            record = session.execute(
                select(NotificationLogRecord).where(NotificationLogRecord.dedupe_key == dedupe_key)
            ).scalar_one_or_none()
            return record is not None

    def log_notification(
        self,
        repo_full_name: str,
        pr_number: int,
        event_type: str,
        dedupe_key: str,
        destination: str,
        status: str,
    ) -> None:
        with self._session() as session:
            session.add(
                NotificationLogRecord(
                    repo_full_name=repo_full_name,
                    pr_number=pr_number,
                    event_type=event_type,
                    dedupe_key=dedupe_key,
                    sent_at=datetime.now(timezone.utc),
                    destination=destination,
                    status=status,
                )
            )

    def get_rate_limit(self, repo_full_name: str, pr_number: int, event_type: str) -> RateLimitState | None:
        with self._session() as session:
            record = session.execute(
                select(PRRateLimitRecord).where(
                    PRRateLimitRecord.repo_full_name == repo_full_name,
                    PRRateLimitRecord.pr_number == pr_number,
                    PRRateLimitRecord.event_type == event_type,
                )
            ).scalar_one_or_none()
            if record is None:
                return None
            return RateLimitState(
                repo_full_name=record.repo_full_name,
                pr_number=record.pr_number,
                event_type=record.event_type,
                last_sent_at=record.last_sent_at,
                sent_count_today=record.sent_count_today,
                day_bucket=record.day_bucket,
            )

    def upsert_rate_limit(self, repo_full_name: str, pr_number: int, event_type: str, day_bucket: str) -> RateLimitState:
        now = datetime.now(timezone.utc)
        with self._session() as session:
            record = session.execute(
                select(PRRateLimitRecord).where(
                    PRRateLimitRecord.repo_full_name == repo_full_name,
                    PRRateLimitRecord.pr_number == pr_number,
                    PRRateLimitRecord.event_type == event_type,
                )
            ).scalar_one_or_none()
            if record is None:
                record = PRRateLimitRecord(
                    repo_full_name=repo_full_name,
                    pr_number=pr_number,
                    event_type=event_type,
                    last_sent_at=now,
                    sent_count_today=1,
                    day_bucket=day_bucket,
                )
                session.add(record)
            else:
                if record.day_bucket != day_bucket:
                    record.day_bucket = day_bucket
                    record.sent_count_today = 0
                record.sent_count_today += 1
                record.last_sent_at = now
            session.flush()
            return RateLimitState(
                repo_full_name=record.repo_full_name,
                pr_number=record.pr_number,
                event_type=record.event_type,
                last_sent_at=record.last_sent_at,
                sent_count_today=record.sent_count_today,
                day_bucket=record.day_bucket,
            )

    def upsert_snapshot(self, snapshot: PRSnapshot) -> None:
        with self._session() as session:
            record = session.execute(
                select(PRSnapshotRecord).where(
                    PRSnapshotRecord.repo_full_name == snapshot.repo_full_name,
                    PRSnapshotRecord.pr_number == snapshot.pr_number,
                )
            ).scalar_one_or_none()
            metadata_json = json.dumps(snapshot.metadata)
            if record is None:
                session.add(
                    PRSnapshotRecord(
                        repo_full_name=snapshot.repo_full_name,
                        pr_number=snapshot.pr_number,
                        title=snapshot.title,
                        author=snapshot.author,
                        is_draft=snapshot.is_draft,
                        state=snapshot.state,
                        head_sha=snapshot.head_sha,
                        last_seen_at=snapshot.last_seen_at,
                        approved_at=snapshot.approved_at,
                        merged_at=snapshot.merged_at,
                        closed_at=snapshot.closed_at,
                        metadata_json=metadata_json,
                    )
                )
                return

            record.title = snapshot.title
            record.author = snapshot.author
            record.is_draft = snapshot.is_draft
            record.state = snapshot.state
            record.head_sha = snapshot.head_sha
            record.last_seen_at = snapshot.last_seen_at
            record.approved_at = snapshot.approved_at
            record.merged_at = snapshot.merged_at
            record.closed_at = snapshot.closed_at
            record.metadata_json = metadata_json

    def get_snapshot(self, repo_full_name: str, pr_number: int) -> PRSnapshot | None:
        with self._session() as session:
            record = session.execute(
                select(PRSnapshotRecord).where(
                    PRSnapshotRecord.repo_full_name == repo_full_name,
                    PRSnapshotRecord.pr_number == pr_number,
                )
            ).scalar_one_or_none()
            if record is None:
                return None
            return PRSnapshot(
                repo_full_name=record.repo_full_name,
                pr_number=record.pr_number,
                title=record.title,
                author=record.author,
                is_draft=record.is_draft,
                state=record.state,
                head_sha=record.head_sha,
                last_seen_at=record.last_seen_at,
                approved_at=record.approved_at,
                merged_at=record.merged_at,
                closed_at=record.closed_at,
                metadata=json.loads(record.metadata_json or "{}"),
            )

    def ping(self) -> bool:
        with self._session() as session:
            session.execute(select(1))
            return True
