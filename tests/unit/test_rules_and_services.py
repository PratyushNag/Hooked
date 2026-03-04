from __future__ import annotations

from pathlib import Path

from app.config.schema import HookedConfig
from app.config.settings import RuntimeSettings, Settings
from app.core.domain.models import PullRequest, ReviewerSuggestion
from app.core.rules.codeowners import match_codeowners
from app.core.services.message_renderer import MAX_MESSAGE_LEN, MessageRenderer
from app.core.services.reviewer_suggester import ReviewerSuggester


def test_codeowners_matches_globs() -> None:
    matches = match_codeowners(["src/payments/service.py", "src/auth/token.py"], "src/payments/* @alice\nsrc/auth/* @carol\n")
    assert matches["src/payments/service.py"] == ["alice"]
    assert matches["src/auth/token.py"] == ["carol"]


def test_reviewer_suggester_prefers_codeowners_and_dedupes() -> None:
    suggester = ReviewerSuggester()
    suggestions = suggester.suggest(
        author="author1",
        changed_paths=["src/payments/service.py"],
        requested_reviewers=["alice"],
        codeowners_text="src/payments/* @alice\n",
        contributors=[],
        team_map={"src/payments/**": ["alice", "bob"]},
    )
    assert [item.username for item in suggestions] == ["alice", "bob"]
    assert suggestions[0].reason.startswith("Owns")


def test_message_renderer_trims_large_messages() -> None:
    from app.core.domain.enums import DomainEventType
    from app.core.domain.events import DomainEvent
    from app.core.domain.models import PRBriefPayload, PRLinks

    event = DomainEvent.build(
        event_type=DomainEventType.PR_BRIEF_CREATED,
        repo_full_name="demo/hooked-demo",
        pr_number=1,
        pr_title="Test",
        pr_url="https://example.com/pr/1",
        author="author1",
        head_sha="sha1",
        payload=PRBriefPayload(
            tldr="x" * 2000,
            changed_areas=["payments"],
            risk_flags=[],
            suggested_reviewers=[],
            review_checklist=["check"] * 20,
            links=PRLinks(pr="https://example.com/pr/1", compare="https://example.com/compare", checks="https://example.com/checks"),
            is_draft=False,
        ),
    )
    message = MessageRenderer().render(event, "engineering-prs", "key", "thread", [])
    total = len(message.title) + sum(len(section.title) + len(section.body) for section in message.sections)
    assert total <= MAX_MESSAGE_LEN


def test_settings_match_wildcard_repo_routes() -> None:
    settings = Settings(
        runtime=RuntimeSettings(config_file="config.yaml", db_url="sqlite:///./test.db"),
        config=HookedConfig.model_validate(
            {
                "github": {"repository_scope": "all_accessible"},
                "notifier": {
                    "provider": "runbear",
                    "runbear": {"workspace_id": "ws", "destination_id": "general"},
                },
                "repos": [
                    {
                        "full_name": "my-org/frontend-*",
                        "destinations": {
                            "pr_brief": "frontend-prs",
                            "ci_failure": "frontend-ci",
                            "review_nudge": "frontend-reviews",
                        },
                    },
                    {
                        "full_name": "*",
                        "destinations": {
                            "pr_brief": "general-prs",
                            "ci_failure": "general-ci",
                            "review_nudge": "general-reviews",
                        },
                    },
                ],
            }
        ),
    )
    assert settings.repo("my-org/frontend-app").destinations["pr_brief"] == "frontend-prs"
    assert settings.repo("other-org/backend").destinations["pr_brief"] == "general-prs"
