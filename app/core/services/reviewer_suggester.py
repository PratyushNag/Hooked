from __future__ import annotations

from collections import OrderedDict

from app.core.domain.enums import ReviewerSource
from app.core.domain.models import ContributorStat, ReviewerSuggestion
from app.core.rules.codeowners import match_codeowners
from app.core.rules.path_matching import path_matches_any


class ReviewerSuggester:
    def suggest(
        self,
        *,
        author: str,
        changed_paths: list[str],
        requested_reviewers: list[str],
        codeowners_text: str | None,
        contributors: list[ContributorStat],
        team_map: dict[str, list[str]],
    ) -> list[ReviewerSuggestion]:
        suggestions: OrderedDict[str, ReviewerSuggestion] = OrderedDict()
        requested = [reviewer for reviewer in requested_reviewers if reviewer != author]

        owner_matches = match_codeowners(changed_paths, codeowners_text)
        owner_counts: dict[str, int] = {}
        for owners in owner_matches.values():
            for owner in owners:
                if owner != author:
                    owner_counts[owner] = owner_counts.get(owner, 0) + 1
        for reviewer in requested + sorted(owner_counts, key=owner_counts.get, reverse=True):
            if reviewer == author or reviewer in suggestions:
                continue
            if reviewer in owner_counts:
                suggestions[reviewer] = ReviewerSuggestion(
                    username=reviewer,
                    display_name=None,
                    reason=f"Owns {owner_counts[reviewer]} changed path(s) via CODEOWNERS.",
                    source=ReviewerSource.CODEOWNERS,
                )

        for contributor in sorted(contributors, key=lambda item: item.commit_count, reverse=True):
            if contributor.username == author or contributor.username in suggestions:
                continue
            suggestions[contributor.username] = ReviewerSuggestion(
                username=contributor.username,
                display_name=None,
                reason=f"Recently changed {', '.join(contributor.recent_paths[:2])}.",
                source=ReviewerSource.RECENT_CONTRIBUTOR,
            )

        for pattern, usernames in team_map.items():
            if not any(path_matches_any(path, [pattern]) for path in changed_paths):
                continue
            for username in usernames:
                if username == author or username in suggestions:
                    continue
                suggestions[username] = ReviewerSuggestion(
                    username=username,
                    display_name=None,
                    reason=f"Mapped reviewer for {pattern}.",
                    source=ReviewerSource.TEAM_MAPPING,
                )

        prioritized = list(suggestions.values())
        requested_first = [item for item in prioritized if item.username in requested]
        remaining = [item for item in prioritized if item.username not in requested]
        return (requested_first + remaining)[:3]
