from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import get_container

router = APIRouter()


@router.get("/readyz")
async def readyz() -> dict:
    container = get_container()
    checks = {
        "db": "ok" if container.repository.ping() else "failed",
        "github": "ok" if await container.github.is_ready() else "failed",
        "notifier": "ok" if await container.notifier.is_ready() else "failed",
        "scheduler": "ok" if container.scheduler.running else "failed",
    }
    status = "ready" if all(value == "ok" for value in checks.values()) else "degraded"
    return {"status": status, "checks": checks}
