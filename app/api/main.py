from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.deps import set_container
from app.api.routes.github_webhooks import router as github_webhook_router
from app.api.routes.debug import router as debug_router
from app.api.routes.health import router as health_router
from app.api.routes.ready import router as ready_router
from app.bootstrap import AppContainer, build_container, start_container, stop_container


def create_app(container: AppContainer | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        runtime_container = container or build_container()
        set_container(runtime_container)
        await start_container(runtime_container)
        try:
            yield
        finally:
            await stop_container(runtime_container)

    app = FastAPI(title="Hooked", version="0.1.0", lifespan=lifespan)
    app.include_router(health_router)
    app.include_router(ready_router)
    app.include_router(github_webhook_router)
    app.include_router(debug_router)
    return app


app = create_app()
