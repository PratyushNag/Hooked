from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.config.settings import Settings
from app.core.domain.enums import DomainEventType
from app.core.domain.events import DomainEvent
from app.core.domain.models import PRLinks, PRSnapshot, ReviewOverduePayload
from app.core.ports.github import GitHubPort
from app.core.ports.repository import RepositoryPort
from app.core.services.impact_classifier import ImpactClassifier
from app.core.services.reviewer_suggester import ReviewerSuggester


class ReviewNudgeService:
    def __init__(
        self,
        *,
        settings: Settings,
        github: GitHubPort,
        repository: RepositoryPort,
        reviewer_suggester: ReviewerSuggester,
        impact_classifier: ImpactClassifier,
    ):
        self._settings = settings
        self._github = github
        self._repository = repository
        self._reviewer_suggester = reviewer_suggester
        self._impact_classifier = impact_classifier

    async def scan(self) -> list[DomainEvent]:
        events: list[DomainEvent] = []
        repo_names = await self._tracked_repo_names()
        for repo_name in repo_names:
            repo = self._settings.repo(repo_name)
            open_prs = await self._github.list_open_prs(repo.full_name)
            for pr in open_prs:
                if pr.is_draft:
                    continue

                reviews = await self._github.list_reviews(pr.repo_full_name, pr.number)
                if any(review.state.upper() == "APPROVED" for review in reviews):
                    self._repository.upsert_snapshot(
                        PRSnapshot(
                            repo_full_name=pr.repo_full_name,
                            pr_number=pr.number,
                            title=pr.title,
                            author=pr.author,
                            is_draft=pr.is_draft,
                            state=pr.state,
                            head_sha=pr.head_sha,
                            last_seen_at=pr.updated_at,
                            approved_at=max((review.submitted_at for review in reviews if review.state.upper() == "APPROVED"), default=None),
                            merged_at=None,
                            closed_at=None,
                            metadata={"labels": pr.labels},
                        )
                    )
                    continue

                threshold_hours = self._settings.config.defaults.urgent_nudge_after_hours if "urgent" in pr.labels else self._settings.config.defaults.default_nudge_after_hours
                now = datetime.now(timezone.utc)
                reference_time = max((review.submitted_at for review in reviews if review.submitted_at), default=pr.updated_at)
                if now - reference_time < timedelta(hours=threshold_hours):
                    continue

                day_bucket = now.date().isoformat()
                rate_limit = self._repository.get_rate_limit(pr.repo_full_name, pr.number, DomainEventType.PR_REVIEW_OVERDUE.value)
                if rate_limit and rate_limit.day_bucket == day_bucket and rate_limit.sent_count_today >= self._settings.config.defaults.max_nudges_per_day_per_pr:
                    continue

                files = await self._github.list_pr_files(pr.repo_full_name, pr.number)
                codeowners = await self._github.get_codeowners(pr.repo_full_name, pr.base_ref)
                contributors = await self._github.list_recent_path_contributors(
                    pr.repo_full_name,
                    [file.path for file in files],
                    self._settings.config.defaults.recent_contributor_commit_window,
                )
                reviewers = self._reviewer_suggester.suggest(
                    author=pr.author,
                    changed_paths=[file.path for file in files],
                    requested_reviewers=pr.requested_reviewers,
                    codeowners_text=codeowners,
                    contributors=contributors,
                    team_map=repo.team_map,
                )
                changed_areas = await self._impact_classifier.classify(pr.repo_full_name, pr.title, [file.path for file in files])
                payload = ReviewOverduePayload(
                    what_changed=f"{pr.title} touches {', '.join(changed_areas[:2])}.",
                    suggested_reviewers=reviewers,
                    ask_text="Can someone review this in the next 2 hours?",
                    links=PRLinks(pr=pr.url, compare=pr.compare_url, checks=pr.checks_url),
                )
                events.append(
                    DomainEvent.build(
                        event_type=DomainEventType.PR_REVIEW_OVERDUE,
                        repo_full_name=pr.repo_full_name,
                        pr_number=pr.number,
                        pr_title=pr.title,
                        pr_url=pr.url,
                        author=pr.author,
                        head_sha=pr.head_sha,
                        payload=payload,
                    )
                )

        return events

    async def _tracked_repo_names(self) -> list[str]:
        if self._settings.tracks_all_accessible_repos:
            repo_names = await self._github.list_accessible_repos()
            tracked: list[str] = []
            for repo_name in repo_names:
                try:
                    self._settings.repo(repo_name)
                except KeyError:
                    continue
                tracked.append(repo_name)
            return tracked
        return [repo.full_name for repo in self._settings.enabled_repos()]
