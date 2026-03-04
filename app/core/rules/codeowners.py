from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch


@dataclass(frozen=True)
class CodeOwnerRule:
    pattern: str
    owners: list[str]


def parse_codeowners(text: str | None) -> list[CodeOwnerRule]:
    if not text:
        return []

    rules: list[CodeOwnerRule] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        pattern = parts[0].lstrip("/")
        owners = [owner.lstrip("@") for owner in parts[1:]]
        rules.append(CodeOwnerRule(pattern=pattern, owners=owners))
    return rules


def match_codeowners(paths: list[str], codeowners_text: str | None) -> dict[str, list[str]]:
    rules = parse_codeowners(codeowners_text)
    matches: dict[str, list[str]] = {}
    for path in paths:
        matched: list[str] = []
        for rule in rules:
            if fnmatch(path, rule.pattern) or fnmatch(path, f"**/{rule.pattern}"):
                matched = rule.owners
        if matched:
            matches[path] = matched
    return matches
