from __future__ import annotations

import asyncio

from app.core.domain.models import CIFailureContext, ImpactClassificationContext, PRSummaryContext
from app.core.ports.llm import LLMPort


class TimedLLMWrapper(LLMPort):
    def __init__(self, inner: LLMPort, timeout_seconds: int):
        self._inner = inner
        self._timeout_seconds = timeout_seconds

    async def summarize_pr(self, context: PRSummaryContext) -> str:
        return await asyncio.wait_for(self._inner.summarize_pr(context), timeout=self._timeout_seconds)

    async def classify_impact(self, context: ImpactClassificationContext) -> list[str]:
        return await asyncio.wait_for(self._inner.classify_impact(context), timeout=self._timeout_seconds)

    async def explain_ci_failure(self, context: CIFailureContext) -> str:
        return await asyncio.wait_for(self._inner.explain_ci_failure(context), timeout=self._timeout_seconds)
