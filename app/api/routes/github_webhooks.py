from __future__ import annotations

import json

from fastapi import APIRouter, Header, HTTPException, Request, status

from app.api.deps import get_container
from app.bootstrap import make_pending_webhook
from app.integrations.github.webhook_validation import is_valid_signature

router = APIRouter()


@router.post("/webhooks/github", status_code=status.HTTP_202_ACCEPTED)
async def github_webhook(
    request: Request,
    x_github_event: str = Header(...),
    x_github_delivery: str = Header(...),
    x_hub_signature_256: str | None = Header(default=None),
) -> dict[str, str]:
    container = get_container()
    body = await request.body()
    if not is_valid_signature(container.settings.github_secrets.webhook_secret, body, x_hub_signature_256):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    payload = json.loads(body.decode("utf-8"))
    action = payload.get("action")
    repo_full_name = payload.get("repository", {}).get("full_name", "unknown/unknown")
    accepted = container.repository.record_webhook_delivery(x_github_delivery, x_github_event, action, repo_full_name)
    if accepted:
        await container.queue.put(make_pending_webhook(x_github_delivery, x_github_event, action, payload))
    return {"status": "accepted", "delivery_id": x_github_delivery, "event_type": x_github_event}
