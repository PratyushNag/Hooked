from __future__ import annotations

import asyncio

from app.core.domain.models import PendingWebhook


class InProcessQueue:
    def __init__(self):
        self._queue: asyncio.Queue[PendingWebhook] = asyncio.Queue()

    async def put(self, item: PendingWebhook) -> None:
        await self._queue.put(item)

    async def get(self) -> PendingWebhook:
        return await self._queue.get()

    def task_done(self) -> None:
        self._queue.task_done()
