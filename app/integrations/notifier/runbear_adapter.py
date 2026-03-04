from __future__ import annotations

import httpx

from app.config.settings import Settings
from app.core.domain.models import NotificationResult, OutboundMessage
from app.core.ports.notifier import NotifierPort


class RunbearAdapter(NotifierPort):
    def __init__(self, settings: Settings, transport: httpx.AsyncClient | None = None):
        self._settings = settings
        self._transport = transport

    async def send(self, message: OutboundMessage) -> NotificationResult:
        secrets = self._settings.runbear_secrets
        config = self._settings.config.notifier.runbear
        if not secrets.api_key:
            raise RuntimeError("RUNBEAR_API_KEY is missing")

        endpoint = secrets.webhook_url or f"{config.base_url.rstrip('/')}/v1/workspaces/{config.workspace_id}/destinations/{message.destination}/messages"
        payload = {
            "title": message.title,
            "sections": [{"title": item.title, "body": item.body} for item in message.sections],
            "mentions": message.mentions,
            "dedupe_key": message.dedupe_key,
            "thread_key": message.thread_key,
            "links": [{"label": link.label, "url": link.url} for link in message.links],
        }
        client = self._transport or httpx.AsyncClient(timeout=20.0)
        owns_client = self._transport is None
        try:
            response = await client.post(
                endpoint,
                json=payload,
                headers={"Authorization": f"Bearer {secrets.api_key}"},
            )
            response.raise_for_status()
            body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
            return NotificationResult(ok=True, provider_message_id=body.get("id"), raw=body)
        finally:
            if owns_client:
                await client.aclose()

    async def is_ready(self) -> bool:
        secrets = self._settings.runbear_secrets
        return bool(secrets.api_key and (secrets.webhook_url or self._settings.config.notifier.runbear.destination_id))
