from __future__ import annotations

from fnmatch import fnmatch


def path_matches_any(path: str, patterns: list[str]) -> bool:
    return any(fnmatch(path, pattern) for pattern in patterns)


def filter_matching_paths(paths: list[str], patterns: list[str]) -> list[str]:
    return [path for path in paths if path_matches_any(path, patterns)]
