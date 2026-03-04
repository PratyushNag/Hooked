from __future__ import annotations

from collections import defaultdict
from datetime import datetime

import httpx

from app.config.settings import Settings
from app.core.domain.models import ChangedFile, CheckRun, CheckSummary, ContributorStat, PullRequest, Review
from app.core.ports.github import GitHubPort
from app.integrations.github.auth import GitHubAuth


def _parse_dt(value: str | None) -> datetime:
    if not value:
        raise ValueError("Missing datetime value")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class GitHubClient(GitHubPort):
    def __init__(self, settings: Settings, auth: GitHubAuth):
        self._settings = settings
        self._auth = auth

    async def _client(self, repo: str) -> httpx.AsyncClient:
        auth_context = await self._auth.headers_for_repo(repo)
        return httpx.AsyncClient(
            base_url=self._settings.config.github.api_base_url,
            headers=auth_context.headers,
            timeout=20.0,
        )

    async def get_pr(self, repo: str, number: int) -> PullRequest:
        async with await self._client(repo) as client:
            response = await client.get(f"/repos/{repo}/pulls/{number}")
            response.raise_for_status()
            data = response.json()
            return self._pull_request_from_api(repo, data)

    async def list_accessible_repos(self) -> list[str]:
        if self._settings.config.github.mode == "pat":
            token = self._settings.github_secrets.token
            if not token:
                return []
            async with httpx.AsyncClient(
                base_url=self._settings.config.github.api_base_url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                timeout=20.0,
            ) as client:
                response = await client.get("/user/repos", params={"per_page": 100})
                response.raise_for_status()
                return [repo["full_name"] for repo in response.json()]

        async with httpx.AsyncClient(
            base_url=self._settings.config.github.api_base_url,
            headers=self._auth.app_headers(),
            timeout=20.0,
        ) as client:
            installations_response = await client.get("/app/installations", params={"per_page": 100})
            installations_response.raise_for_status()
            installations = installations_response.json()
            repos: list[str] = []
            for installation in installations:
                installation_id = installation["id"]
                token_response = await client.post(f"/app/installations/{installation_id}/access_tokens")
                token_response.raise_for_status()
                token = token_response.json()["token"]
                async with httpx.AsyncClient(
                    base_url=self._settings.config.github.api_base_url,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                    timeout=20.0,
                ) as installation_client:
                    repositories_response = await installation_client.get(
                        "/installation/repositories",
                        params={"per_page": 100},
                    )
                repositories_response.raise_for_status()
                body = repositories_response.json()
                repos.extend(item["full_name"] for item in body.get("repositories", []))
            return sorted(set(repos))

    async def list_pr_files(self, repo: str, number: int) -> list[ChangedFile]:
        async with await self._client(repo) as client:
            response = await client.get(f"/repos/{repo}/pulls/{number}/files", params={"per_page": 100})
            response.raise_for_status()
            return [
                ChangedFile(
                    path=item["filename"],
                    additions=item.get("additions", 0),
                    deletions=item.get("deletions", 0),
                    status=item.get("status", "modified"),
                )
                for item in response.json()
            ]

    async def get_codeowners(self, repo: str, ref: str) -> str | None:
        candidate_paths = [".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS"]
        async with await self._client(repo) as client:
            for path in candidate_paths:
                response = await client.get(f"/repos/{repo}/contents/{path}", params={"ref": ref})
                if response.status_code == 404:
                    continue
                response.raise_for_status()
                download_url = response.json().get("download_url")
                if not download_url:
                    continue
                file_response = await client.get(download_url)
                file_response.raise_for_status()
                return file_response.text
        return None

    async def list_recent_path_contributors(self, repo: str, paths: list[str], limit: int) -> list[ContributorStat]:
        contributor_paths: dict[str, set[str]] = defaultdict(set)
        contributor_counts: dict[str, int] = defaultdict(int)
        async with await self._client(repo) as client:
            for path in paths[:10]:
                response = await client.get(f"/repos/{repo}/commits", params={"path": path, "per_page": min(limit, 20)})
                response.raise_for_status()
                for commit in response.json():
                    author = commit.get("author") or {}
                    username = author.get("login")
                    if not username:
                        continue
                    contributor_paths[username].add(path)
                    contributor_counts[username] += 1
        return [
            ContributorStat(username=user, recent_paths=sorted(paths_set), commit_count=contributor_counts[user])
            for user, paths_set in contributor_paths.items()
        ]

    async def get_pr_checks(self, repo: str, number: int) -> CheckSummary:
        pr = await self.get_pr(repo, number)
        async with await self._client(repo) as client:
            response = await client.get(f"/repos/{repo}/commits/{pr.head_sha}/check-runs")
            response.raise_for_status()
            data = response.json()
            failing_runs = [
                CheckRun(
                    name=item["name"],
                    conclusion=item.get("conclusion") or "unknown",
                    html_url=item.get("html_url") or pr.url,
                )
                for item in data.get("check_runs", [])
                if item.get("conclusion") == "failure"
            ]
            state = "failure" if failing_runs else "success"
            details_url = failing_runs[0].html_url if failing_runs else pr.checks_url
            return CheckSummary(state=state, details_url=details_url, failing_runs=failing_runs)

    async def resolve_pr_from_sha(self, repo: str, sha: str) -> PullRequest | None:
        async with await self._client(repo) as client:
            response = await client.get(
                f"/repos/{repo}/commits/{sha}/pulls",
                headers={"Accept": "application/vnd.github+json"},
            )
            response.raise_for_status()
            prs = response.json()
            if not prs:
                return None
            return self._pull_request_from_api(repo, prs[0])

    async def list_reviews(self, repo: str, number: int) -> list[Review]:
        async with await self._client(repo) as client:
            response = await client.get(f"/repos/{repo}/pulls/{number}/reviews")
            response.raise_for_status()
            return [
                Review(
                    user=(item.get("user") or {}).get("login", "unknown"),
                    state=item.get("state", "COMMENTED"),
                    submitted_at=_parse_dt(item["submitted_at"]) if item.get("submitted_at") else None,
                    body=item.get("body") or "",
                )
                for item in response.json()
            ]

    async def list_open_prs(self, repo: str) -> list[PullRequest]:
        async with await self._client(repo) as client:
            response = await client.get(f"/repos/{repo}/pulls", params={"state": "open", "per_page": 100})
            response.raise_for_status()
            return [self._pull_request_from_api(repo, item) for item in response.json()]

    async def is_ready(self) -> bool:
        if not self._auth.is_configured():
            return False
        if self._settings.config.github.mode == "pat":
            repos = self._settings.enabled_repos()
            if not repos:
                return True
            try:
                async with await self._client(repos[0].full_name) as client:
                    response = await client.get("/rate_limit")
                    response.raise_for_status()
                    return True
            except Exception:
                return False
        return True

    def _pull_request_from_api(self, repo: str, data: dict) -> PullRequest:
        labels = [label["name"] for label in data.get("labels", [])]
        requested_reviewers = [reviewer["login"] for reviewer in data.get("requested_reviewers", [])]
        checks_url = None
        if data.get("html_url"):
            checks_url = f"{data['html_url']}/checks"
        return PullRequest(
            repo_full_name=repo,
            number=data["number"],
            title=data["title"],
            url=data["html_url"],
            compare_url=data.get("diff_url"),
            checks_url=checks_url,
            author=(data.get("user") or {}).get("login", "unknown"),
            head_sha=data["head"]["sha"],
            base_ref=data["base"]["ref"],
            head_ref=data["head"]["ref"],
            state=data.get("state", "open"),
            is_draft=bool(data.get("draft", False)),
            created_at=_parse_dt(data["created_at"]),
            updated_at=_parse_dt(data["updated_at"]),
            labels=labels,
            requested_reviewers=requested_reviewers,
            additions=data.get("additions", 0),
            deletions=data.get("deletions", 0),
            changed_files=data.get("changed_files", 0),
        )
