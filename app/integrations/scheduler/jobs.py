from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler


def build_scheduler() -> AsyncIOScheduler:
    return AsyncIOScheduler()
