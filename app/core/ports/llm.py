from __future__ import annotations

from typing import Protocol

from app.core.domain.models import CIFailureContext, ImpactClassificationContext, PRSummaryContext


class LLMPort(Protocol):
    async def summarize_pr(self, context: PRSummaryContext) -> str: ...

    async def classify_impact(self, context: ImpactClassificationContext) -> list[str]: ...

    async def explain_ci_failure(self, context: CIFailureContext) -> str: ...
