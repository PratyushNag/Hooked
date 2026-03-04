from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/debug/weekly-report")
async def weekly_report_stub() -> dict:
    return {
        "status": "demo-stub",
        "summary": "This week Hooked posted PR briefs, CI failure triage, and overdue review nudges.",
        "metrics": {
            "pr_briefs_sent": 3,
            "ci_failures_triaged": 2,
            "review_nudges_sent": 1,
            "average_time_to_first_review_hours": 5.5,
        },
    }
