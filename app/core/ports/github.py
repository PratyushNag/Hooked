from __future__ import annotations

from typing import Protocol

from app.core.domain.models import (
    ChangedFile,
    CheckSummary,
    ContributorStat,
    PullRequest,
    Review,
)


class GitHubPort(Protocol):
    async def list_accessible_repos(self) -> list[str]: ...

    async def get_pr(self, repo: str, number: int) -> PullRequest: ...

    async def list_pr_files(self, repo: str, number: int) -> list[ChangedFile]: ...

    async def get_codeowners(self, repo: str, ref: str) -> str | None: ...

    async def list_recent_path_contributors(
        self,
        repo: str,
        paths: list[str],
        limit: int,
    ) -> list[ContributorStat]: ...

    async def get_pr_checks(self, repo: str, number: int) -> CheckSummary: ...

    async def resolve_pr_from_sha(self, repo: str, sha: str) -> PullRequest | None: ...

    async def list_reviews(self, repo: str, number: int) -> list[Review]: ...

    async def list_open_prs(self, repo: str) -> list[PullRequest]: ...

    async def is_ready(self) -> bool: ...
