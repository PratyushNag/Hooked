from __future__ import annotations

from app.core.rules.path_matching import path_matches_any


def has_missing_tests(changed_paths: list[str], test_paths: list[str]) -> bool:
    touches_source = any(path.startswith("src/") for path in changed_paths)
    touches_tests = any(path_matches_any(path, test_paths) for path in changed_paths)
    return touches_source and not touches_tests
