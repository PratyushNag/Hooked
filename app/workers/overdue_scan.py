from __future__ import annotations

from app.api.deps import get_container
from app.config.settings import Settings
from app.core.ports.notifier import NotifierPort
from app.core.ports.repository import RepositoryPort
from app.core.services.message_renderer import MessageRenderer
from app.core.services.review_nudge_service import ReviewNudgeService
from app.runtime import deliver_event


class OverdueScanner:
    def __init__(
        self,
        *,
        settings: Settings,
        repository: RepositoryPort,
        notifier: NotifierPort,
        renderer: MessageRenderer,
        review_nudge_service: ReviewNudgeService,
    ):
        self._settings = settings
        self._repository = repository
        self._notifier = notifier
        self._renderer = renderer
        self._review_nudge_service = review_nudge_service

    async def run(self) -> None:
        container = get_container()
        for event in await self._review_nudge_service.scan():
            await deliver_event(container, event)
