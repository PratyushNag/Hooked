from __future__ import annotations

from app.core.domain.enums import Severity
from app.core.domain.models import CheckSummary, PullRequest, RiskFlag
from app.core.rules.path_matching import filter_matching_paths
from app.core.rules.test_gap import has_missing_tests


class RiskFlagger:
    def flag(
        self,
        *,
        pr: PullRequest,
        changed_paths: list[str],
        critical_paths: list[str],
        test_paths: list[str],
        checks: CheckSummary,
        large_pr_files_threshold: int,
        large_pr_lines_threshold: int,
    ) -> list[RiskFlag]:
        flags: list[RiskFlag] = []
        total_lines = pr.additions + pr.deletions
        if pr.changed_files > large_pr_files_threshold or total_lines > large_pr_lines_threshold:
            flags.append(
                RiskFlag(
                    code="large_pr",
                    label="Large PR",
                    details=f"{pr.changed_files} files and {total_lines} lines changed.",
                    severity=Severity.WARNING,
                )
            )

        matched_critical = filter_matching_paths(changed_paths, critical_paths)
        if matched_critical:
            flags.append(
                RiskFlag(
                    code="critical_paths_touched",
                    label="Critical paths touched",
                    details=", ".join(matched_critical[:3]),
                    severity=Severity.HIGH,
                )
            )

        if has_missing_tests(changed_paths, test_paths):
            flags.append(
                RiskFlag(
                    code="missing_tests",
                    label="Tests may be missing",
                    details="Source files changed without matching test changes.",
                    severity=Severity.WARNING,
                )
            )

        if checks.failing_runs:
            flags.append(
                RiskFlag(
                    code="ci_failing",
                    label="CI failing",
                    details=f"{len(checks.failing_runs)} failing run(s) detected.",
                    severity=Severity.HIGH,
                )
            )

        if pr.is_draft:
            flags.append(
                RiskFlag(
                    code="draft_pr",
                    label="Draft PR",
                    details="Draft PRs receive a brief but no overdue nudges.",
                    severity=Severity.INFO,
                )
            )

        return flags
