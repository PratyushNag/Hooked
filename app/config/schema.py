from __future__ import annotations

from pydantic import BaseModel, Field


class AppSection(BaseModel):
    environment: str = "local"
    log_level: str = "INFO"
    base_url: str = "http://localhost:8000"


class GitHubAppSection(BaseModel):
    app_id_env: str = "GITHUB_APP_ID"
    private_key_env: str = "GITHUB_APP_PRIVATE_KEY"
    webhook_secret_env: str = "GITHUB_WEBHOOK_SECRET"


class GitHubSection(BaseModel):
    mode: str = "pat"
    repository_scope: str = "configured"
    api_base_url: str = "https://api.github.com"
    webhook_secret_env: str = "GITHUB_WEBHOOK_SECRET"
    pat_env: str = "GITHUB_TOKEN"
    app: GitHubAppSection = Field(default_factory=GitHubAppSection)


class LLMSection(BaseModel):
    enabled: bool = True
    provider: str = "openai"
    model: str = "gpt-4.1-mini"
    api_key_env: str = "OPENAI_API_KEY"
    timeout_seconds: int = 12
    max_input_chars: int = 12000
    max_output_chars: int = 1200


class RunbearSection(BaseModel):
    api_key_env: str = "RUNBEAR_API_KEY"
    webhook_url_env: str = "RUNBEAR_WEBHOOK_URL"
    base_url: str = "https://api.runbear.io"
    workspace_id: str
    destination_id: str
    thread_mode: str = "per_pr"


class NotifierSection(BaseModel):
    provider: str = "runbear"
    runbear: RunbearSection


class DefaultsSection(BaseModel):
    large_pr_files_threshold: int = 20
    large_pr_lines_threshold: int = 800
    default_nudge_after_hours: int = 24
    urgent_nudge_after_hours: int = 4
    scan_interval_minutes: int = 15
    ci_failure_cooldown_minutes: int = 30
    max_nudges_per_day_per_pr: int = 2
    recent_contributor_commit_window: int = 50
    mention_suggested_reviewer_on_nudge: bool = True


class RepoSection(BaseModel):
    full_name: str
    enabled: bool = True
    critical_paths: list[str] = Field(default_factory=list)
    test_paths: list[str] = Field(default_factory=lambda: ["test/**", "tests/**", "__tests__/**"])
    team_map: dict[str, list[str]] = Field(default_factory=dict)
    destinations: dict[str, str]


class HookedConfig(BaseModel):
    app: AppSection = Field(default_factory=AppSection)
    github: GitHubSection = Field(default_factory=GitHubSection)
    llm: LLMSection = Field(default_factory=LLMSection)
    notifier: NotifierSection
    defaults: DefaultsSection = Field(default_factory=DefaultsSection)
    repos: list[RepoSection]
