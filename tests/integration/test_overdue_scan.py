from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone


async def test_overdue_scan_sends_nudge(test_app) -> None:
    test_app.github.pr = replace(test_app.github.pr, updated_at=datetime.now(timezone.utc) - timedelta(hours=30))
    await test_app.container.overdue_scanner.run()
    assert any(message.title.startswith("Review needed:") for message in test_app.notifier.messages)
