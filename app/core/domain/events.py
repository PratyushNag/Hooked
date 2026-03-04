from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.core.domain.enums import DomainEventType


@dataclass(frozen=True)
class DomainEvent:
    event_id: str
    event_type: DomainEventType
    occurred_at: datetime
    repo: str
    repo_full_name: str
    pr_number: int
    pr_title: str
    pr_url: str
    author: str
    head_sha: str
    payload: Any

    @classmethod
    def build(
        cls,
        *,
        event_type: DomainEventType,
        repo_full_name: str,
        pr_number: int,
        pr_title: str,
        pr_url: str,
        author: str,
        head_sha: str,
        payload: Any,
    ) -> "DomainEvent":
        return cls(
            event_id=str(uuid4()),
            event_type=event_type,
            occurred_at=datetime.now(timezone.utc),
            repo=repo_full_name.split("/")[-1],
            repo_full_name=repo_full_name,
            pr_number=pr_number,
            pr_title=pr_title,
            pr_url=pr_url,
            author=author,
            head_sha=head_sha,
            payload=payload,
        )
