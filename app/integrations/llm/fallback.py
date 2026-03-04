from __future__ import annotations

from app.core.domain.models import CIFailureContext, ImpactClassificationContext, PRSummaryContext
from app.core.ports.llm import LLMPort


class FallbackLLM(LLMPort):
    async def summarize_pr(self, context: PRSummaryContext) -> str:
        top_files = ", ".join(file.path for file in context.files[:3]) or "repository updates"
        areas = ", ".join(context.changed_areas) or "shared code"
        return f"Updates {areas} across {len(context.files)} file(s): {top_files}."

    async def classify_impact(self, context: ImpactClassificationContext) -> list[str]:
        return context.deterministic_areas[:]

    async def explain_ci_failure(self, context: CIFailureContext) -> str:
        return context.failure_summary
