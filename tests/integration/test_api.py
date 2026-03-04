from __future__ import annotations

import time

from sqlalchemy import select

from app.integrations.persistence.models import WebhookDeliveryRecord


def test_health_and_ready_routes(test_app) -> None:
    health = test_app.client.get("/healthz")
    ready = test_app.client.get("/readyz")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"


def test_webhook_intake_triggers_pr_brief(test_app, pull_request_payload) -> None:
    response = test_app.client.post(
        "/webhooks/github",
        json=pull_request_payload,
        headers={"X-GitHub-Event": "pull_request", "X-GitHub-Delivery": "delivery-1"},
    )
    assert response.status_code == 202
    time.sleep(0.2)
    assert len(test_app.notifier.messages) == 1
    assert test_app.notifier.messages[0].title.startswith("PR Brief:")


def test_duplicate_webhook_delivery_is_idempotent(test_app, pull_request_payload) -> None:
    headers = {"X-GitHub-Event": "pull_request", "X-GitHub-Delivery": "delivery-duplicate"}
    first = test_app.client.post("/webhooks/github", json=pull_request_payload, headers=headers)
    second = test_app.client.post("/webhooks/github", json=pull_request_payload, headers=headers)
    assert first.status_code == 202
    assert second.status_code == 202
    time.sleep(0.2)
    assert len(test_app.notifier.messages) == 1

    session = test_app.container.repository._session_factory()
    try:
        records = session.execute(select(WebhookDeliveryRecord)).scalars().all()
        assert len(records) == 1
    finally:
        session.close()
