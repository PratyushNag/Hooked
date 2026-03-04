from __future__ import annotations

import os
from functools import cached_property
from fnmatch import fnmatch
from pathlib import Path

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

from app.config.loader import load_config_file
from app.config.schema import HookedConfig, RepoSection
from app.core.domain.models import RepoConfigView


class RuntimeSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HOOKED_", extra="ignore")

    config_file: str = "config.yaml"
    db_url: str = "sqlite:///./hooked.db"


class GitHubSecrets(BaseModel):
    token: str | None
    webhook_secret: str | None
    app_id: str | None
    private_key: str | None


class LLMSecrets(BaseModel):
    api_key: str | None


class RunbearSecrets(BaseModel):
    api_key: str | None
    webhook_url: str | None


class Settings:
    def __init__(self, runtime: RuntimeSettings, config: HookedConfig):
        self.runtime = runtime
        self.config = config

    @classmethod
    def load(cls) -> "Settings":
        load_dotenv()
        runtime = RuntimeSettings()
        config = load_config_file(runtime.config_file)
        return cls(runtime=runtime, config=config)

    @cached_property
    def github_secrets(self) -> GitHubSecrets:
        github = self.config.github
        return GitHubSecrets(
            token=os.getenv(github.pat_env),
            webhook_secret=os.getenv(github.webhook_secret_env),
            app_id=os.getenv(github.app.app_id_env),
            private_key=_normalize_private_key(os.getenv(github.app.private_key_env)),
        )

    @cached_property
    def llm_secrets(self) -> LLMSecrets:
        return LLMSecrets(api_key=os.getenv(self.config.llm.api_key_env))

    @cached_property
    def runbear_secrets(self) -> RunbearSecrets:
        section = self.config.notifier.runbear
        return RunbearSecrets(
            api_key=os.getenv(section.api_key_env),
            webhook_url=os.getenv(section.webhook_url_env),
        )

    @property
    def config_path(self) -> Path:
        return Path(self.runtime.config_file)

    def repo(self, repo_full_name: str) -> RepoConfigView:
        exact_matches = [repo for repo in self.config.repos if repo.enabled and repo.full_name == repo_full_name]
        if exact_matches:
            return self._to_repo_view(exact_matches[0], repo_full_name)

        wildcard_matches = [repo for repo in self.config.repos if repo.enabled and fnmatch(repo_full_name, repo.full_name)]
        if wildcard_matches:
            wildcard_matches.sort(key=lambda repo: (repo.full_name == "*", len(repo.full_name)))
            return self._to_repo_view(wildcard_matches[0], repo_full_name)
        raise KeyError(f"Repo not configured: {repo_full_name}")

    def enabled_repos(self) -> list[RepoConfigView]:
        return [self._to_repo_view(repo, repo.full_name) for repo in self.config.repos if repo.enabled and "*" not in repo.full_name]

    @property
    def tracks_all_accessible_repos(self) -> bool:
        return self.config.github.repository_scope == "all_accessible"

    def knows_repo(self, repo_full_name: str) -> bool:
        try:
            self.repo(repo_full_name)
            return True
        except KeyError:
            return False

    def _to_repo_view(self, repo: RepoSection, resolved_full_name: str) -> RepoConfigView:
        return RepoConfigView(
            match=repo.full_name,
            full_name=resolved_full_name,
            critical_paths=list(repo.critical_paths),
            test_paths=list(repo.test_paths),
            team_map={key: list(value) for key, value in repo.team_map.items()},
            destinations=dict(repo.destinations),
            enabled=repo.enabled,
        )


def _normalize_private_key(value: str | None) -> str | None:
    if not value:
        return value
    return value.replace("\\n", "\n")
