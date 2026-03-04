from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx
import jwt

from app.config.settings import Settings


@dataclass
class GitHubAuthContext:
    headers: dict[str, str]


class GitHubAuth:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._cached_installation_tokens: dict[str, tuple[str, datetime]] = {}

    async def headers_for_repo(self, repo_full_name: str) -> GitHubAuthContext:
        mode = self._settings.config.github.mode
        if mode == "pat":
            token = self._settings.github_secrets.token
            if not token:
                raise RuntimeError("Missing GitHub PAT")
            return GitHubAuthContext(headers=self._auth_headers(token))

        token = await self._installation_token(repo_full_name)
        return GitHubAuthContext(headers=self._auth_headers(token))

    def is_configured(self) -> bool:
        mode = self._settings.config.github.mode
        secrets = self._settings.github_secrets
        if mode == "pat":
            return bool(secrets.token)
        return bool(secrets.app_id and secrets.private_key and secrets.webhook_secret)

    def _auth_headers(self, token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def app_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._app_jwt()}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _app_jwt(self) -> str:
        app_id = self._settings.github_secrets.app_id
        private_key = self._settings.github_secrets.private_key
        if not app_id or not private_key:
            raise RuntimeError("GitHub App credentials are not configured")

        now = datetime.now(timezone.utc)
        payload = {
            "iat": int((now - timedelta(seconds=60)).timestamp()),
            "exp": int((now + timedelta(minutes=9)).timestamp()),
            "iss": app_id,
        }
        return jwt.encode(payload, private_key, algorithm="RS256")

    async def _installation_token(self, repo_full_name: str) -> str:
        cached = self._cached_installation_tokens.get(repo_full_name)
        now = datetime.now(timezone.utc)
        if cached and cached[1] > now + timedelta(minutes=2):
            return cached[0]

        jwt_token = self._app_jwt()
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        base_url = self._settings.config.github.api_base_url
        async with httpx.AsyncClient(base_url=base_url, timeout=20.0, headers=headers) as client:
            installation_response = await client.get(f"/repos/{repo_full_name}/installation")
            installation_response.raise_for_status()
            installation_id = installation_response.json()["id"]

            token_response = await client.post(f"/app/installations/{installation_id}/access_tokens")
            token_response.raise_for_status()
            body = token_response.json()
            token = body["token"]
            expires_at = datetime.fromisoformat(body["expires_at"].replace("Z", "+00:00"))
            self._cached_installation_tokens[repo_full_name] = (token, expires_at)
            return token
