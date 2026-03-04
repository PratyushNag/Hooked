from __future__ import annotations

from openai import AsyncOpenAI

from app.config.settings import Settings
from app.core.domain.models import CIFailureContext, ImpactClassificationContext, PRSummaryContext
from app.core.ports.llm import LLMPort


class OpenAILLM(LLMPort):
    def __init__(self, settings: Settings):
        api_key = settings.llm_secrets.api_key
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is missing")
        self._settings = settings
        self._client = AsyncOpenAI(api_key=api_key)

    async def summarize_pr(self, context: PRSummaryContext) -> str:
        prompt = (
            "Summarize this pull request in 2 sentences. "
            f"Title: {context.pr.title}\n"
            f"Areas: {', '.join(context.changed_areas)}\n"
            f"Files: {', '.join(file.path for file in context.files[:10])}\n"
            f"Risks: {', '.join(flag.label for flag in context.risk_flags) or 'none'}"
        )
        return await self._single_text_response(prompt)

    async def classify_impact(self, context: ImpactClassificationContext) -> list[str]:
        prompt = (
            "Return a comma-separated list of at most 2 impact areas for this PR.\n"
            f"Title: {context.title}\nFiles: {', '.join(context.files[:10])}\n"
            f"Existing: {', '.join(context.deterministic_areas) or 'none'}"
        )
        output = await self._single_text_response(prompt)
        return [item.strip().lower() for item in output.split(",") if item.strip()][:2]

    async def explain_ci_failure(self, context: CIFailureContext) -> str:
        prompt = (
            "Explain the most likely cause of this CI failure in one short paragraph.\n"
            f"PR: {context.pr.title}\n"
            f"Jobs: {', '.join(job.name for job in context.failing_jobs)}\n"
            f"Summary: {context.failure_summary}"
        )
        return await self._single_text_response(prompt)

    async def _single_text_response(self, prompt: str) -> str:
        llm = self._settings.config.llm
        truncated = prompt[: llm.max_input_chars]
        response = await self._client.responses.create(
            model=llm.model,
            input=truncated,
            max_output_tokens=300,
        )
        text = response.output_text.strip()
        return text[: llm.max_output_chars]
