from __future__ import annotations

import asyncio
import logging

from app.api.deps import get_container
from app.config.settings import Settings
from app.core.domain.models import PendingWebhook
from app.core.ports.notifier import NotifierPort
from app.core.ports.repository import RepositoryPort
from app.core.services.ci_failure_service import CIFailureService
from app.core.services.message_renderer import MessageRenderer
from app.core.services.pr_brief_service import PRBriefService
from app.runtime import ci_failure_trigger_from_payload, deliver_event, pull_request_trigger_from_payload

LOGGER = logging.getLogger("hooked.webhooks")


class WebhookProcessor:
    def __init__(
        self,
        *,
        settings: Settings,
        repository: RepositoryPort,
        notifier: NotifierPort,
        renderer: MessageRenderer,
        pr_brief_service: PRBriefService,
        ci_failure_service: CIFailureService,
    ):
        self._settings = settings
        self._repository = repository
        self._notifier = notifier
        self._renderer = renderer
        self._pr_brief_service = pr_brief_service
        self._ci_failure_service = ci_failure_service
        self._deliver = None

    async def process(self, pending: PendingWebhook) -> None:
        container = get_container()
        self._deliver = lambda event: deliver_event(container, event)

        for attempt in range(3):
            try:
                await self._process_once(pending)
                self._repository.mark_webhook_processed(pending.delivery_id)
                return
            except Exception as exc:
                if attempt == 2:
                    raise
                LOGGER.warning("retrying_webhook", extra={"delivery_id": pending.delivery_id, "error": str(exc), "attempt": attempt + 1})
                await asyncio.sleep(2**attempt)

    async def _process_once(self, pending: PendingWebhook) -> None:
        repo_full_name = (pending.payload.get("repository") or {}).get("full_name")
        if repo_full_name and not self._settings.knows_repo(repo_full_name):
            return

        event = None
        if pending.event_type == "pull_request" and pending.action in {"opened", "reopened", "synchronize", "ready_for_review"}:
            event = await self._pr_brief_service.execute(pull_request_trigger_from_payload(pending.payload))
        elif pending.event_type in {"check_run", "workflow_run"}:
            conclusion = (pending.payload.get("check_run") or pending.payload.get("workflow_run") or {}).get("conclusion")
            if pending.action == "completed" and conclusion == "failure":
                event = await self._ci_failure_service.execute(ci_failure_trigger_from_payload(pending.event_type, pending.payload))

        if event is not None and self._deliver is not None:
            await self._deliver(event)
