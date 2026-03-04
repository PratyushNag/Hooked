from __future__ import annotations

from app.core.domain.models import ImpactClassificationContext
from app.core.ports.llm import LLMPort


AREA_PATTERNS: dict[str, tuple[str, ...]] = {
    "backend": ("api/", "backend/", "server/", "src/backend/"),
    "frontend": ("frontend/", "web/", "ui/", "src/frontend/"),
    "infra": ("infra/", ".github/", "terraform/", "deploy/", "ops/"),
    "auth": ("auth/", "src/auth/", "security/"),
    "payments": ("payments/", "billing/", "src/payments/"),
    "migrations": ("migration", "migrations/"),
    "tests": ("test/", "tests/", "__tests__/"),
    "docs": ("docs/", ".md"),
    "shared": ("shared/", "common/", "src/shared/"),
}


class ImpactClassifier:
    def __init__(self, llm: LLMPort | None = None):
        self._llm = llm

    async def classify(self, repo_full_name: str, title: str, paths: list[str]) -> list[str]:
        areas: list[str] = []
        lowered = [path.lower() for path in paths]
        for area, patterns in AREA_PATTERNS.items():
            if any(any(pattern in path for pattern in patterns) for path in lowered):
                areas.append(area)

        if self._llm and len(areas) <= 1:
            context = ImpactClassificationContext(
                repo_full_name=repo_full_name,
                title=title,
                files=paths,
                deterministic_areas=areas,
            )
            try:
                llm_areas = await self._llm.classify_impact(context)
            except Exception:
                llm_areas = []
            for area in llm_areas:
                if area not in areas:
                    areas.append(area)

        return areas or ["shared"]
