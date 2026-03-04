from __future__ import annotations

from datetime import datetime, timezone

from app.config.settings import Settings
from app.core.domain.enums import DomainEventType
from app.core.domain.events import DomainEvent
from app.core.domain.models import CIFailureContext, CIFailurePayload, CILinks, CIFailureTrigger, FailingJob
from app.core.ports.github import GitHubPort
from app.core.ports.llm import LLMPort
from app.core.ports.repository import RepositoryPort
from app.core.rules.ci_triage import classify_ci_failure


class CIFailureService:
    def __init__(self, *, settings: Settings, github: GitHubPort, llm: LLMPort, repository: RepositoryPort):
        self._settings = settings
        self._github = github
        self._llm = llm
        self._repository = repository

    async def execute(self, trigger: CIFailureTrigger) -> DomainEvent | None:
        pr = await self._github.resolve_pr_from_sha(trigger.repo_full_name, trigger.sha)
        if pr is None:
            return None

        rate_limit = self._repository.get_rate_limit(pr.repo_full_name, pr.number, DomainEventType.PR_CI_FAILED.value)
        if rate_limit and rate_limit.last_sent_at:
            minutes_since = (datetime.now(timezone.utc) - rate_limit.last_sent_at).total_seconds() / 60
            if minutes_since < self._settings.config.defaults.ci_failure_cooldown_minutes:
                return None

        jobs = [FailingJob(name=trigger.job_name, conclusion=trigger.conclusion, url=trigger.run_url)]
        likely_cause, confidence, next_actions = classify_ci_failure(jobs, trigger.summary)
        try:
            likely_cause = await self._llm.explain_ci_failure(
                CIFailureContext(pr=pr, failing_jobs=jobs, failure_summary=likely_cause)
            )
        except Exception:
            pass

        payload = CIFailurePayload(
            failing_jobs=jobs,
            likely_cause=likely_cause,
            cause_confidence=confidence,  # type: ignore[arg-type]
            next_actions=next_actions,
            links=CILinks(run=trigger.run_url, pr=pr.url),
            mentioned_people=[pr.author],
        )
        return DomainEvent.build(
            event_type=DomainEventType.PR_CI_FAILED,
            repo_full_name=pr.repo_full_name,
            pr_number=pr.number,
            pr_title=pr.title,
            pr_url=pr.url,
            author=pr.author,
            head_sha=pr.head_sha,
            payload=payload,
        )
