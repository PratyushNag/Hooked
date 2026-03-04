from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config.settings import Settings
from app.core.domain.models import PendingWebhook
from app.core.ports.llm import LLMPort
from app.core.services.ci_failure_service import CIFailureService
from app.core.services.impact_classifier import ImpactClassifier
from app.core.services.message_renderer import MessageRenderer
from app.core.services.pr_brief_service import PRBriefService
from app.core.services.review_nudge_service import ReviewNudgeService
from app.core.services.reviewer_suggester import ReviewerSuggester
from app.core.services.risk_flagger import RiskFlagger
from app.integrations.github.auth import GitHubAuth
from app.integrations.github.client import GitHubClient
from app.integrations.llm.base import TimedLLMWrapper
from app.integrations.llm.fallback import FallbackLLM
from app.integrations.llm.openai_provider import OpenAILLM
from app.integrations.notifier.runbear_adapter import RunbearAdapter
from app.integrations.persistence.repositories import SQLAlchemyRepository
from app.integrations.persistence.sqlite import create_session_factory
from app.integrations.queue.in_process import InProcessQueue
from app.integrations.scheduler.jobs import build_scheduler
from app.runtime import deliver_event
from app.workers.overdue_scan import OverdueScanner
from app.workers.webhook_processor import WebhookProcessor

LOGGER = logging.getLogger("hooked")


@dataclass
class AppContainer:
    settings: Settings
    repository: SQLAlchemyRepository
    github: GitHubClient
    llm: LLMPort
    notifier: RunbearAdapter
    queue: InProcessQueue
    scheduler: AsyncIOScheduler
    renderer: MessageRenderer
    pr_brief_service: PRBriefService
    ci_failure_service: CIFailureService
    review_nudge_service: ReviewNudgeService
    webhook_processor: WebhookProcessor
    overdue_scanner: OverdueScanner
    worker_task: asyncio.Task | None = None


def build_container(settings: Settings | None = None) -> AppContainer:
    settings = settings or Settings.load()
    logging.basicConfig(
        level=getattr(logging, settings.config.app.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    session_factory = create_session_factory(settings.runtime.db_url)
    repository = SQLAlchemyRepository(session_factory)
    github_auth = GitHubAuth(settings)
    github = GitHubClient(settings, github_auth)
    llm = _build_llm(settings)
    notifier = RunbearAdapter(settings)
    queue = InProcessQueue()
    scheduler = build_scheduler()
    renderer = MessageRenderer()
    reviewer_suggester = ReviewerSuggester()
    risk_flagger = RiskFlagger()
    impact_classifier = ImpactClassifier(llm if settings.config.llm.enabled else None)
    pr_brief_service = PRBriefService(
        settings=settings,
        github=github,
        llm=llm,
        repository=repository,
        reviewer_suggester=reviewer_suggester,
        risk_flagger=risk_flagger,
        impact_classifier=impact_classifier,
    )
    ci_failure_service = CIFailureService(settings=settings, github=github, llm=llm, repository=repository)
    review_nudge_service = ReviewNudgeService(
        settings=settings,
        github=github,
        repository=repository,
        reviewer_suggester=reviewer_suggester,
        impact_classifier=impact_classifier,
    )
    webhook_processor = WebhookProcessor(
        settings=settings,
        repository=repository,
        notifier=notifier,
        renderer=renderer,
        pr_brief_service=pr_brief_service,
        ci_failure_service=ci_failure_service,
    )
    overdue_scanner = OverdueScanner(
        settings=settings,
        repository=repository,
        notifier=notifier,
        renderer=renderer,
        review_nudge_service=review_nudge_service,
    )
    return AppContainer(
        settings=settings,
        repository=repository,
        github=github,
        llm=llm,
        notifier=notifier,
        queue=queue,
        scheduler=scheduler,
        renderer=renderer,
        pr_brief_service=pr_brief_service,
        ci_failure_service=ci_failure_service,
        review_nudge_service=review_nudge_service,
        webhook_processor=webhook_processor,
        overdue_scanner=overdue_scanner,
    )


def _build_llm(settings: Settings) -> LLMPort:
    llm: LLMPort
    if settings.config.llm.enabled and settings.config.llm.provider == "openai" and settings.llm_secrets.api_key:
        llm = OpenAILLM(settings)
    else:
        llm = FallbackLLM()
    return TimedLLMWrapper(llm, settings.config.llm.timeout_seconds)


async def start_container(container: AppContainer) -> None:
    async def worker_loop() -> None:
        while True:
            item = await container.queue.get()
            try:
                await container.webhook_processor.process(item)
            except Exception as exc:  # pragma: no cover - defensive top-level log
                LOGGER.exception("webhook_processing_failed", extra={"delivery_id": item.delivery_id, "error": str(exc)})
                container.repository.mark_webhook_failed(item.delivery_id, str(exc))
            finally:
                container.queue.task_done()

    container.worker_task = asyncio.create_task(worker_loop(), name="hooked-webhook-worker")
    container.scheduler.add_job(
        container.overdue_scanner.run,
        "interval",
        minutes=container.settings.config.defaults.scan_interval_minutes,
        id="review-overdue-scan",
        replace_existing=True,
    )
    container.scheduler.start()


async def stop_container(container: AppContainer) -> None:
    if container.scheduler.running:
        container.scheduler.shutdown(wait=False)
    if container.worker_task is not None:
        container.worker_task.cancel()
        try:
            await container.worker_task
        except asyncio.CancelledError:
            pass


def make_pending_webhook(delivery_id: str, event_type: str, action: str | None, payload: dict) -> PendingWebhook:
    return PendingWebhook(
        delivery_id=delivery_id,
        event_type=event_type,
        action=action,
        payload=payload,
        received_at=datetime.now(timezone.utc),
    )
