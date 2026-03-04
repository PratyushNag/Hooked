from __future__ import annotations

from app.core.domain.enums import DomainEventType, NotificationStatus
from app.core.domain.events import DomainEvent
from app.core.domain.models import CIFailureTrigger, PullRequestTrigger


def dedupe_key_for_event(event: DomainEvent) -> str:
    if event.event_type is DomainEventType.PR_BRIEF_CREATED:
        return f"brief:{event.repo_full_name}:{event.pr_number}:{event.head_sha}"
    if event.event_type is DomainEventType.PR_CI_FAILED:
        run_url = getattr(event.payload.links, "run", event.pr_url)
        return f"ci_failed:{event.repo_full_name}:{event.pr_number}:{run_url.rsplit('/', 1)[-1]}"
    day_bucket = event.occurred_at.date().isoformat()
    return f"nudge:{event.repo_full_name}:{event.pr_number}:{day_bucket}:1"


def mentions_for_event(settings, event: DomainEvent) -> list[str]:
    if event.event_type is DomainEventType.PR_CI_FAILED:
        return [event.author]
    if event.event_type is DomainEventType.PR_REVIEW_OVERDUE and settings.config.defaults.mention_suggested_reviewer_on_nudge:
        reviewers = event.payload.suggested_reviewers
        return [reviewers[0].username] if reviewers else []
    return []


def destination_for_event(settings, event: DomainEvent) -> str:
    repo = settings.repo(event.repo_full_name)
    if event.event_type is DomainEventType.PR_BRIEF_CREATED:
        return repo.destinations["pr_brief"]
    if event.event_type is DomainEventType.PR_CI_FAILED:
        return repo.destinations["ci_failure"]
    return repo.destinations["review_nudge"]


def thread_key_for_event(settings, event: DomainEvent) -> str | None:
    if settings.config.notifier.runbear.thread_mode != "per_pr":
        return None
    return f"{event.repo_full_name}:{event.pr_number}"


async def deliver_event(container, event: DomainEvent) -> bool:
    dedupe_key = dedupe_key_for_event(event)
    if container.repository.has_notification(dedupe_key):
        return False

    destination = destination_for_event(container.settings, event)
    message = container.renderer.render(
        event=event,
        destination=destination,
        dedupe_key=dedupe_key,
        thread_key=thread_key_for_event(container.settings, event),
        mentions=mentions_for_event(container.settings, event),
    )
    result = await container.notifier.send(message)
    status = NotificationStatus.SENT.value if result.ok else NotificationStatus.FAILED.value
    container.repository.log_notification(
        repo_full_name=event.repo_full_name,
        pr_number=event.pr_number,
        event_type=event.event_type.value,
        dedupe_key=dedupe_key,
        destination=destination,
        status=status,
    )
    if result.ok:
        container.repository.upsert_rate_limit(
            repo_full_name=event.repo_full_name,
            pr_number=event.pr_number,
            event_type=event.event_type.value,
            day_bucket=event.occurred_at.date().isoformat(),
        )
    return result.ok


def pull_request_trigger_from_payload(payload: dict) -> PullRequestTrigger:
    pr = payload["pull_request"]
    return PullRequestTrigger(
        action=payload["action"],
        repo_full_name=payload["repository"]["full_name"],
        pr_number=pr["number"],
        head_sha=pr["head"]["sha"],
    )


def ci_failure_trigger_from_payload(event_type: str, payload: dict) -> CIFailureTrigger:
    repo_full_name = payload["repository"]["full_name"]
    if event_type == "check_run":
        check_run = payload["check_run"]
        return CIFailureTrigger(
            event_name=event_type,
            repo_full_name=repo_full_name,
            sha=check_run["head_sha"],
            run_id=str(check_run["id"]),
            job_name=check_run["name"],
            conclusion=check_run["conclusion"],
            run_url=check_run.get("html_url") or check_run.get("details_url") or payload["repository"]["html_url"],
            summary=(check_run.get("output") or {}).get("summary") or "",
        )

    workflow_run = payload["workflow_run"]
    return CIFailureTrigger(
        event_name=event_type,
        repo_full_name=repo_full_name,
        sha=workflow_run["head_sha"],
        run_id=str(workflow_run["id"]),
        job_name=workflow_run["name"],
        conclusion=workflow_run["conclusion"],
        run_url=workflow_run.get("html_url") or payload["repository"]["html_url"],
        summary=workflow_run.get("display_title") or "",
    )
