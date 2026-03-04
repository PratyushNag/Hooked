from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.main import create_app
from app.bootstrap import AppContainer
from app.config.schema import HookedConfig
from app.config.settings import RuntimeSettings, Settings
from app.core.domain.models import (
    ChangedFile,
    CheckRun,
    CheckSummary,
    ContributorStat,
    NotificationResult,
    PullRequest,
    Review,
)
from app.core.services.ci_failure_service import CIFailureService
from app.core.services.impact_classifier import ImpactClassifier
from app.core.services.message_renderer import MessageRenderer
from app.core.services.pr_brief_service import PRBriefService
from app.core.services.review_nudge_service import ReviewNudgeService
from app.core.services.reviewer_suggester import ReviewerSuggester
from app.core.services.risk_flagger import RiskFlagger
from app.integrations.llm.fallback import FallbackLLM
from app.integrations.persistence.repositories import SQLAlchemyRepository
from app.integrations.persistence.sqlite import create_session_factory
from app.integrations.queue.in_process import InProcessQueue
from app.integrations.scheduler.jobs import build_scheduler
from app.workers.overdue_scan import OverdueScanner
from app.workers.webhook_processor import WebhookProcessor


class FakeGitHub:
    def __init__(self):
        self.pr = PullRequest(
            repo_full_name="demo/hooked-demo",
            number=42,
            title="Add payment retries",
            url="https://github.com/demo/hooked-demo/pull/42",
            compare_url="https://github.com/demo/hooked-demo/compare/main...feature",
            checks_url="https://github.com/demo/hooked-demo/pull/42/checks",
            author="author1",
            head_sha="abc123",
            base_ref="main",
            head_ref="feature",
            state="open",
            is_draft=False,
            created_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            updated_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            labels=[],
            requested_reviewers=["alice"],
            additions=120,
            deletions=40,
            changed_files=2,
        )
        self.files = [
            ChangedFile(path="src/payments/service.py", additions=100, deletions=20, status="modified"),
            ChangedFile(path="tests/test_payments.py", additions=20, deletions=20, status="modified"),
        ]
        self.reviews: list[Review] = []

    async def get_pr(self, repo: str, number: int) -> PullRequest:
        return self.pr

    async def list_accessible_repos(self) -> list[str]:
        return ["demo/hooked-demo", "demo/another-repo"]

    async def list_pr_files(self, repo: str, number: int) -> list[ChangedFile]:
        return self.files

    async def get_codeowners(self, repo: str, ref: str) -> str | None:
        return "src/payments/* @alice\nsrc/auth/* @carol\n"

    async def list_recent_path_contributors(self, repo: str, paths: list[str], limit: int) -> list[ContributorStat]:
        return [ContributorStat(username="bob", recent_paths=["src/payments/service.py"], commit_count=3)]

    async def get_pr_checks(self, repo: str, number: int) -> CheckSummary:
        return CheckSummary(state="success", details_url="https://github.com/demo/hooked-demo/pull/42/checks", failing_runs=[])

    async def resolve_pr_from_sha(self, repo: str, sha: str) -> PullRequest | None:
        return self.pr

    async def list_reviews(self, repo: str, number: int) -> list[Review]:
        return self.reviews

    async def list_open_prs(self, repo: str) -> list[PullRequest]:
        return [self.pr]

    async def is_ready(self) -> bool:
        return True


class FakeNotifier:
    def __init__(self):
        self.messages = []

    async def send(self, message):
        self.messages.append(message)
        return NotificationResult(ok=True, provider_message_id=f"msg-{len(self.messages)}", raw={"id": len(self.messages)})

    async def is_ready(self) -> bool:
        return True


def build_test_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    monkeypatch.setenv("RUNBEAR_API_KEY", "rb_test")
    config = HookedConfig.model_validate(
        {
            "notifier": {
                "provider": "runbear",
                "runbear": {
                    "workspace_id": "ws1",
                    "destination_id": "engineering-prs",
                },
            },
            "repos": [
                {
                    "full_name": "demo/hooked-demo",
                    "destinations": {
                        "pr_brief": "engineering-prs",
                        "ci_failure": "engineering-prs",
                        "review_nudge": "engineering-prs",
                    },
                    "critical_paths": ["payments/**", "auth/**", "src/payments/**"],
                    "test_paths": ["tests/**", "__tests__/**"],
                    "team_map": {"src/payments/**": ["alice", "bob"]},
                }
            ],
        }
    )
    runtime = RuntimeSettings(config_file="config.yaml", db_url=f"sqlite:///{tmp_path / 'test.db'}")
    return Settings(runtime=runtime, config=config)


def build_test_container(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    settings = build_test_settings(tmp_path, monkeypatch)
    session_factory = create_session_factory(settings.runtime.db_url)
    repository = SQLAlchemyRepository(session_factory)
    github = FakeGitHub()
    llm = FallbackLLM()
    notifier = FakeNotifier()
    queue = InProcessQueue()
    scheduler = build_scheduler()
    renderer = MessageRenderer()
    reviewer_suggester = ReviewerSuggester()
    risk_flagger = RiskFlagger()
    impact_classifier = ImpactClassifier(llm)
    pr_brief_service = PRBriefService(
        settings=settings,
        github=github,
        llm=llm,
        repository=repository,
        reviewer_suggester=reviewer_suggester,
        risk_flagger=risk_flagger,
        impact_classifier=impact_classifier,
    )
    ci_failure_service = CIFailureService(settings=settings, github=github, llm=llm, repository=repository)
    review_nudge_service = ReviewNudgeService(
        settings=settings,
        github=github,
        repository=repository,
        reviewer_suggester=reviewer_suggester,
        impact_classifier=impact_classifier,
    )
    webhook_processor = WebhookProcessor(
        settings=settings,
        repository=repository,
        notifier=notifier,
        renderer=renderer,
        pr_brief_service=pr_brief_service,
        ci_failure_service=ci_failure_service,
    )
    overdue_scanner = OverdueScanner(
        settings=settings,
        repository=repository,
        notifier=notifier,
        renderer=renderer,
        review_nudge_service=review_nudge_service,
    )
    container = AppContainer(
        settings=settings,
        repository=repository,
        github=github,
        llm=llm,
        notifier=notifier,
        queue=queue,
        scheduler=scheduler,
        renderer=renderer,
        pr_brief_service=pr_brief_service,
        ci_failure_service=ci_failure_service,
        review_nudge_service=review_nudge_service,
        webhook_processor=webhook_processor,
        overdue_scanner=overdue_scanner,
    )
    return container, notifier, github


@pytest.fixture
def pull_request_payload() -> dict:
    path = Path(__file__).parent / "fixtures" / "pull_request_opened.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def test_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    container, notifier, github = build_test_container(tmp_path, monkeypatch)
    app = create_app(container)
    client = TestClient(app)
    with client:
        yield SimpleNamespace(client=client, container=container, notifier=notifier, github=github)
