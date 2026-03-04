from __future__ import annotations

from datetime import datetime, timezone

from app.config.settings import Settings
from app.core.domain.enums import DomainEventType
from app.core.domain.events import DomainEvent
from app.core.domain.models import PRBriefPayload, PRLinks, PRSnapshot, PRSummaryContext, PullRequestTrigger
from app.core.ports.github import GitHubPort
from app.core.ports.llm import LLMPort
from app.core.ports.repository import RepositoryPort
from app.core.services.impact_classifier import ImpactClassifier
from app.core.services.reviewer_suggester import ReviewerSuggester
from app.core.services.risk_flagger import RiskFlagger


class PRBriefService:
    def __init__(
        self,
        *,
        settings: Settings,
        github: GitHubPort,
        llm: LLMPort,
        repository: RepositoryPort,
        reviewer_suggester: ReviewerSuggester,
        risk_flagger: RiskFlagger,
        impact_classifier: ImpactClassifier,
    ):
        self._settings = settings
        self._github = github
        self._llm = llm
        self._repository = repository
        self._reviewer_suggester = reviewer_suggester
        self._risk_flagger = risk_flagger
        self._impact_classifier = impact_classifier

    async def execute(self, trigger: PullRequestTrigger) -> DomainEvent:
        repo_config = self._settings.repo(trigger.repo_full_name)
        pr = await self._github.get_pr(trigger.repo_full_name, trigger.pr_number)
        files = await self._github.list_pr_files(trigger.repo_full_name, trigger.pr_number)
        checks = await self._github.get_pr_checks(trigger.repo_full_name, trigger.pr_number)
        codeowners = await self._github.get_codeowners(trigger.repo_full_name, pr.base_ref)
        contributors = await self._github.list_recent_path_contributors(
            trigger.repo_full_name,
            [file.path for file in files],
            self._settings.config.defaults.recent_contributor_commit_window,
        )

        changed_paths = [file.path for file in files]
        risk_flags = self._risk_flagger.flag(
            pr=pr,
            changed_paths=changed_paths,
            critical_paths=repo_config.critical_paths,
            test_paths=repo_config.test_paths,
            checks=checks,
            large_pr_files_threshold=self._settings.config.defaults.large_pr_files_threshold,
            large_pr_lines_threshold=self._settings.config.defaults.large_pr_lines_threshold,
        )
        changed_areas = await self._impact_classifier.classify(trigger.repo_full_name, pr.title, changed_paths)
        suggested_reviewers = self._reviewer_suggester.suggest(
            author=pr.author,
            changed_paths=changed_paths,
            requested_reviewers=pr.requested_reviewers,
            codeowners_text=codeowners,
            contributors=contributors,
            team_map=repo_config.team_map,
        )
        try:
            summary = await self._llm.summarize_pr(
                PRSummaryContext(pr=pr, files=files, risk_flags=risk_flags, changed_areas=changed_areas)
            )
        except Exception:
            top_files = ", ".join(file.path for file in files[:3]) or "repository updates"
            summary = f"{pr.title} updates {', '.join(changed_areas)} across {len(files)} file(s): {top_files}."

        snapshot = PRSnapshot(
            repo_full_name=pr.repo_full_name,
            pr_number=pr.number,
            title=pr.title,
            author=pr.author,
            is_draft=pr.is_draft,
            state=pr.state,
            head_sha=pr.head_sha,
            last_seen_at=datetime.now(timezone.utc),
            approved_at=None,
            merged_at=None,
            closed_at=None,
            metadata={"labels": pr.labels},
        )
        self._repository.upsert_snapshot(snapshot)

        payload = PRBriefPayload(
            tldr=summary,
            changed_areas=changed_areas,
            risk_flags=risk_flags,
            suggested_reviewers=suggested_reviewers,
            review_checklist=self._review_checklist(changed_areas, risk_flags),
            links=PRLinks(pr=pr.url, compare=pr.compare_url, checks=checks.details_url),
            is_draft=pr.is_draft,
        )
        return DomainEvent.build(
            event_type=DomainEventType.PR_BRIEF_CREATED,
            repo_full_name=pr.repo_full_name,
            pr_number=pr.number,
            pr_title=pr.title,
            pr_url=pr.url,
            author=pr.author,
            head_sha=pr.head_sha,
            payload=payload,
        )

    def _review_checklist(self, changed_areas: list[str], risk_flags: list) -> list[str]:
        checklist = [
            "Confirm scope and intent.",
            "Check tests cover the main path.",
            "Confirm failure modes are handled.",
            "Verify risky paths if flagged.",
            "Confirm CI status.",
        ]
        for area in ("auth", "payments", "migrations", "infra"):
            if area in changed_areas:
                checklist.append(f"Inspect {area} behavior carefully.")
        if any(flag.code == "large_pr" for flag in risk_flags):
            checklist.append("Consider asking for a walkthrough because the PR is large.")
        return checklist
