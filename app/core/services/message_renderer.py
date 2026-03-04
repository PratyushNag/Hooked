from __future__ import annotations

from app.core.domain.enums import DomainEventType
from app.core.domain.events import DomainEvent
from app.core.domain.models import (
    CIFailurePayload,
    LinkItem,
    MessageSection,
    OutboundMessage,
    PRBriefPayload,
    ReviewOverduePayload,
)

MAX_MESSAGE_LEN = 3500
MAX_SECTION_LEN = 800


def _truncate(text: str, limit: int = MAX_SECTION_LEN) -> str:
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3]}..."


class MessageRenderer:
    def render(self, event: DomainEvent, destination: str, dedupe_key: str, thread_key: str | None, mentions: list[str]) -> OutboundMessage:
        if event.event_type is DomainEventType.PR_BRIEF_CREATED:
            payload = event.payload
            assert isinstance(payload, PRBriefPayload)
            sections = [
                MessageSection("TLDR", payload.tldr),
                MessageSection("Changed areas", ", ".join(payload.changed_areas)),
                MessageSection(
                    "Risk flags",
                    "\n".join(f"- {flag.label}: {flag.details}" for flag in payload.risk_flags) or "- None",
                ),
                MessageSection(
                    "Suggested reviewers",
                    "\n".join(f"- @{item.username}: {item.reason}" for item in payload.suggested_reviewers) or "- None",
                ),
                MessageSection(
                    "Review checklist",
                    "\n".join(f"- {item}" for item in payload.review_checklist),
                ),
            ]
            links = [
                LinkItem("PR", payload.links.pr),
                LinkItem("Compare", payload.links.compare or payload.links.pr),
                LinkItem("Checks", payload.links.checks or payload.links.pr),
            ]
            title = f"PR Brief: {event.repo}#{event.pr_number} {event.pr_title}"
        elif event.event_type is DomainEventType.PR_CI_FAILED:
            payload = event.payload
            assert isinstance(payload, CIFailurePayload)
            sections = [
                MessageSection(
                    "Failing job(s)",
                    "\n".join(f"- {job.name} ({job.conclusion})" for job in payload.failing_jobs),
                ),
                MessageSection("Likely cause", payload.likely_cause),
                MessageSection("Next actions", "\n".join(f"- {step}" for step in payload.next_actions)),
            ]
            links = [LinkItem("Failing run", payload.links.run), LinkItem("PR", payload.links.pr)]
            title = f"CI Failed: {event.repo}#{event.pr_number} {event.pr_title}"
        else:
            payload = event.payload
            assert isinstance(payload, ReviewOverduePayload)
            sections = [
                MessageSection("What changed", payload.what_changed),
                MessageSection(
                    "Who should review",
                    "\n".join(f"- @{item.username}: {item.reason}" for item in payload.suggested_reviewers) or "- Team",
                ),
                MessageSection("Ask", payload.ask_text),
            ]
            links = [LinkItem("PR", payload.links.pr)]
            title = f"Review needed: {event.repo}#{event.pr_number}"

        trimmed_sections = [MessageSection(title=item.title, body=_truncate(item.body)) for item in sections]
        message = OutboundMessage(
            destination=destination,
            title=title,
            sections=trimmed_sections,
            mentions=mentions,
            dedupe_key=dedupe_key,
            thread_key=thread_key,
            links=links,
        )
        return self._trim_message(message)

    def _trim_message(self, message: OutboundMessage) -> OutboundMessage:
        total = len(message.title) + sum(len(item.title) + len(item.body) for item in message.sections)
        if total <= MAX_MESSAGE_LEN:
            return message

        sections: list[MessageSection] = []
        remaining = MAX_MESSAGE_LEN - len(message.title)
        for section in message.sections:
            allowance = max(120, remaining // max(1, len(message.sections) - len(sections)))
            body = _truncate(section.body, allowance)
            sections.append(MessageSection(section.title, body))
            remaining -= len(section.title) + len(body)
        return OutboundMessage(
            destination=message.destination,
            title=message.title,
            sections=sections,
            mentions=message.mentions,
            dedupe_key=message.dedupe_key,
            thread_key=message.thread_key,
            links=message.links,
        )
