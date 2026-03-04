from __future__ import annotations

from enum import Enum


class DomainEventType(str, Enum):
    PR_BRIEF_CREATED = "pr.brief.created"
    PR_CI_FAILED = "pr.ci.failed"
    PR_REVIEW_OVERDUE = "pr.review.overdue"


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    HIGH = "high"


class ReviewerSource(str, Enum):
    CODEOWNERS = "codeowners"
    RECENT_CONTRIBUTOR = "recent_contributor"
    TEAM_MAPPING = "team_mapping"


class DeliveryStatus(str, Enum):
    RECEIVED = "received"
    PROCESSED = "processed"
    FAILED = "failed"


class NotificationStatus(str, Enum):
    SENT = "sent"
    FAILED = "failed"

