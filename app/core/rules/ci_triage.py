from __future__ import annotations

from app.core.domain.models import FailingJob


def classify_ci_failure(jobs: list[FailingJob], summary: str = "") -> tuple[str, str, list[str]]:
    haystack = " ".join([job.name for job in jobs] + [summary]).lower()

    if any(token in haystack for token in ("pytest", "test", "jest", "unit", "integration")):
        return "Tests are failing in CI.", "high", ["Inspect the failing test output.", "Reproduce the test locally.", "Push a fix or mark the PR blocked."]
    if any(token in haystack for token in ("lint", "flake8", "ruff", "eslint", "format", "mypy", "type")):
        return "Linting or type checks are failing.", "high", ["Run the formatter or linter locally.", "Fix the reported typing or style issue.", "Push a narrow follow-up commit."]
    if any(token in haystack for token in ("build", "compile", "bundle", "docker")):
        return "Build or packaging failed.", "medium", ["Inspect the build logs.", "Reproduce the build locally.", "Check dependencies and environment assumptions."]
    if any(token in haystack for token in ("timeout", "network", "runner", "service unavailable")):
        return "The failure looks transient or infrastructure-related.", "low", ["Retry the run once.", "Check runner health and external services.", "Only page someone if the retry fails again."]
    return "The root cause is unclear from the available signals.", "low", ["Open the failing run.", "Review the first failing step.", "Ask the PR author for local repro details if needed."]
