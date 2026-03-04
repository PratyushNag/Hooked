from __future__ import annotations

from typing import Protocol

from app.core.domain.models import PRSnapshot, RateLimitState


class RepositoryPort(Protocol):
    def record_webhook_delivery(
        self,
        delivery_id: str,
        event_type: str,
        action: str | None,
        repo_full_name: str,
    ) -> bool: ...

    def mark_webhook_processed(self, delivery_id: str) -> None: ...

    def mark_webhook_failed(self, delivery_id: str, error_message: str) -> None: ...

    def has_notification(self, dedupe_key: str) -> bool: ...

    def log_notification(
        self,
        repo_full_name: str,
        pr_number: int,
        event_type: str,
        dedupe_key: str,
        destination: str,
        status: str,
    ) -> None: ...

    def get_rate_limit(self, repo_full_name: str, pr_number: int, event_type: str) -> RateLimitState | None: ...

    def upsert_rate_limit(
        self,
        repo_full_name: str,
        pr_number: int,
        event_type: str,
        day_bucket: str,
    ) -> RateLimitState: ...

    def upsert_snapshot(self, snapshot: PRSnapshot) -> None: ...

    def get_snapshot(self, repo_full_name: str, pr_number: int) -> PRSnapshot | None: ...

    def ping(self) -> bool: ...
