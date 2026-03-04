from __future__ import annotations

from typing import Protocol

from app.core.domain.models import NotificationResult, OutboundMessage


class NotifierPort(Protocol):
    async def send(self, message: OutboundMessage) -> NotificationResult: ...

    async def is_ready(self) -> bool: ...
