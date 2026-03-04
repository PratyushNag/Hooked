from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from app.core.domain.enums import ReviewerSource, Severity


@dataclass(frozen=True)
class LinkItem:
    label: str
    url: str


@dataclass(frozen=True)
class MessageSection:
    title: str
    body: str


@dataclass(frozen=True)
class OutboundMessage:
    destination: str
    title: str
    sections: list[MessageSection]
    mentions: list[str]
    dedupe_key: str
    thread_key: str | None
    links: list[LinkItem]


@dataclass(frozen=True)
class NotificationResult:
    ok: bool
    provider_message_id: str | None = None
    raw: dict[str, Any] | None = None


@dataclass(frozen=True)
class RiskFlag:
    code: Literal["large_pr", "critical_paths_touched", "missing_tests", "ci_failing", "draft_pr"]
    label: str
    details: str
    severity: Severity


@dataclass(frozen=True)
class ReviewerSuggestion:
    username: str
    display_name: str | None
    reason: str
    source: ReviewerSource


@dataclass(frozen=True)
class PRLinks:
    pr: str
    compare: str | None
    checks: str | None


@dataclass(frozen=True)
class CILinks:
    run: str
    pr: str


@dataclass(frozen=True)
class FailingJob:
    name: str
    conclusion: str
    url: str


@dataclass(frozen=True)
class PRBriefPayload:
    tldr: str
    changed_areas: list[str]
    risk_flags: list[RiskFlag]
    suggested_reviewers: list[ReviewerSuggestion]
    review_checklist: list[str]
    links: PRLinks
    is_draft: bool


@dataclass(frozen=True)
class CIFailurePayload:
    failing_jobs: list[FailingJob]
    likely_cause: str
    cause_confidence: Literal["low", "medium", "high"]
    next_actions: list[str]
    links: CILinks
    mentioned_people: list[str]


@dataclass(frozen=True)
class ReviewOverduePayload:
    what_changed: str
    suggested_reviewers: list[ReviewerSuggestion]
    ask_text: str
    links: PRLinks


@dataclass(frozen=True)
class PullRequest:
    repo_full_name: str
    number: int
    title: str
    url: str
    compare_url: str | None
    checks_url: str | None
    author: str
    head_sha: str
    base_ref: str
    head_ref: str
    state: str
    is_draft: bool
    created_at: datetime
    updated_at: datetime
    labels: list[str]
    requested_reviewers: list[str]
    additions: int
    deletions: int
    changed_files: int


@dataclass(frozen=True)
class ChangedFile:
    path: str
    additions: int
    deletions: int
    status: str


@dataclass(frozen=True)
class ContributorStat:
    username: str
    recent_paths: list[str]
    commit_count: int


@dataclass(frozen=True)
class CheckRun:
    name: str
    conclusion: str
    html_url: str


@dataclass(frozen=True)
class CheckSummary:
    state: str
    details_url: str | None
    failing_runs: list[CheckRun]


@dataclass(frozen=True)
class Review:
    user: str
    state: str
    submitted_at: datetime | None
    body: str


@dataclass(frozen=True)
class PRSummaryContext:
    pr: PullRequest
    files: list[ChangedFile]
    risk_flags: list[RiskFlag]
    changed_areas: list[str]


@dataclass(frozen=True)
class ImpactClassificationContext:
    repo_full_name: str
    title: str
    files: list[str]
    deterministic_areas: list[str]


@dataclass(frozen=True)
class CIFailureContext:
    pr: PullRequest
    failing_jobs: list[FailingJob]
    failure_summary: str


@dataclass(frozen=True)
class PullRequestTrigger:
    action: str
    repo_full_name: str
    pr_number: int
    head_sha: str


@dataclass(frozen=True)
class CIFailureTrigger:
    event_name: str
    repo_full_name: str
    sha: str
    run_id: str
    job_name: str
    conclusion: str
    run_url: str
    summary: str


@dataclass(frozen=True)
class PendingWebhook:
    delivery_id: str
    event_type: str
    action: str | None
    payload: dict[str, Any]
    received_at: datetime


@dataclass(frozen=True)
class RepoConfigView:
    match: str
    full_name: str
    critical_paths: list[str]
    test_paths: list[str]
    team_map: dict[str, list[str]]
    destinations: dict[str, str]
    enabled: bool = True


@dataclass(frozen=True)
class RateLimitState:
    repo_full_name: str
    pr_number: int
    event_type: str
    last_sent_at: datetime | None
    sent_count_today: int
    day_bucket: str


@dataclass(frozen=True)
class PRSnapshot:
    repo_full_name: str
    pr_number: int
    title: str
    author: str
    is_draft: bool
    state: str
    head_sha: str
    last_seen_at: datetime
    approved_at: datetime | None = None
    merged_at: datetime | None = None
    closed_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
