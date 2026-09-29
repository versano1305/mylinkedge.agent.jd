"""Repository for public.user_resume_builder (Supabase / PostgREST).

The resume builder is a 5-step machine (job-description → gap-analysis →
gap-interview → template → generate). Gap collection is **step 2**: this
repository loads a session together with its joined ``job_description`` row,
marks the gap-analysis step in progress, and persists the computed ``gaps``
jsonb while advancing the session to the ``gap-interview`` step.

Status strings mirror ``@mylinkedge/supabase-db`` (``USER_RESUME_BUILDER_STEPS``
and the ``{step}_in_progress`` convention); keep them in sync with the frontend.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field
from supabase import Client

from jd_agent.integrations.supabase.jd_repository import (
    JobDescription,
    normalize_job_description,
)

USER_RESUME_BUILDER_TABLE = "user_resume_builder"

# Step vocabulary (must match libs/supabase-db USER_RESUME_BUILDER_STEPS).
GAP_ANALYSIS_STEP = "gap-analysis"
GAP_ANALYSIS_IN_PROGRESS = "gap-analysis_in_progress"
GAP_INTERVIEW_STEP = "gap-interview"

# Nested select that hydrates the joined job_description in one round trip.
_SESSION_WITH_JD_SELECT = """
id,
user_id,
status,
job_description_id,
interviewed,
gaps,
gaps_date,
created_at,
job_description:job_description_id (
  id,
  company_name,
  title_name,
  origin_jd,
  origin_type,
  origin_id,
  last_updated,
  skills,
  extraction_status,
  company_id,
  sections
)
"""


class UserResumeBuilder(BaseModel):
    """Row shape for ``user_resume_builder`` (mirrors fullstack types)."""

    id: str
    user_id: str
    status: str = GAP_ANALYSIS_STEP
    job_description_id: str = ""
    interviewed: bool = False
    gaps: Any | None = None
    gaps_date: str | None = None
    created_at: str = ""


class ResumeBuilderSessionWithJd(BaseModel):
    """A resume-builder session joined with its job description."""

    session: UserResumeBuilder
    job_description: JobDescription = Field(...)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _raise_on_error(error: Any, *, fallback: str) -> None:
    if error is None:
        return
    message = getattr(error, "message", None) or str(error) or fallback
    raise RuntimeError(message)


def _row_from_update_response(data: Any, *, session_id: str) -> dict[str, Any]:
    """Unwrap a PostgREST update ``data`` payload to a single row dict."""
    if isinstance(data, list):
        if not data:
            raise RuntimeError(f"No user_resume_builder row for id={session_id}")
        data = data[0]
    if not data:
        raise RuntimeError(f"No user_resume_builder row for id={session_id}")
    if not isinstance(data, dict):
        raise RuntimeError(
            f"Unexpected user_resume_builder payload for id={session_id}"
        )
    return data


def normalize_user_resume_builder(row: dict[str, Any]) -> UserResumeBuilder:
    return UserResumeBuilder(
        id=str(row["id"]),
        user_id=str(row.get("user_id") or ""),
        status=str(row.get("status") or GAP_ANALYSIS_STEP),
        job_description_id=str(row.get("job_description_id") or ""),
        interviewed=bool(row.get("interviewed") or False),
        gaps=row.get("gaps"),
        gaps_date=(
            str(row["gaps_date"]) if row.get("gaps_date") is not None else None
        ),
        created_at=str(row.get("created_at") or _now_iso()),
    )


def _resolve_joined_jd(joined: Any) -> dict[str, Any]:
    if isinstance(joined, list):
        return joined[0] if joined else {}
    if isinstance(joined, dict):
        return joined
    return {}


def get_by_id(client: Client, session_id: str) -> UserResumeBuilder | None:
    """Load a resume-builder session by primary key (no join)."""
    response = (
        client.table(USER_RESUME_BUILDER_TABLE)
        .select("*")
        .eq("id", session_id)
        .maybe_single()
        .execute()
    )
    _raise_on_error(
        getattr(response, "error", None), fallback="Failed to load resume session"
    )
    data = response.data
    if not data:
        return None
    if isinstance(data, list):
        if not data:
            return None
        data = data[0]
    return normalize_user_resume_builder(data)


def get_session_with_jd(
    client: Client, session_id: str
) -> ResumeBuilderSessionWithJd | None:
    """Load a session and its joined job description in one query."""
    response = (
        client.table(USER_RESUME_BUILDER_TABLE)
        .select(_SESSION_WITH_JD_SELECT)
        .eq("id", session_id)
        .maybe_single()
        .execute()
    )
    _raise_on_error(
        getattr(response, "error", None),
        fallback="Failed to load resume session with job description",
    )
    data = response.data
    if not data:
        return None
    if isinstance(data, list):
        if not data:
            return None
        data = data[0]

    jd_raw = _resolve_joined_jd(data.get("job_description"))
    if not jd_raw.get("id"):
        raise RuntimeError(
            f"Resume session id={session_id} is missing its job description"
        )

    return ResumeBuilderSessionWithJd(
        session=normalize_user_resume_builder(data),
        job_description=normalize_job_description(jd_raw),
    )


def _update_status(
    client: Client, session_id: str, status: str, *, extra: dict[str, Any] | None = None
) -> UserResumeBuilder:
    payload: dict[str, Any] = {"status": status}
    if extra:
        payload.update(extra)
    response = (
        client.table(USER_RESUME_BUILDER_TABLE)
        .update(payload)
        .eq("id", session_id)
        .select("*")
        .execute()
    )
    _raise_on_error(
        getattr(response, "error", None),
        fallback=f"Failed to set status={status}",
    )
    return normalize_user_resume_builder(
        _row_from_update_response(response.data, session_id=session_id)
    )


def mark_gap_analysis_in_progress(
    client: Client, session_id: str
) -> UserResumeBuilder:
    """Set ``status = gap-analysis_in_progress`` at the start of the run."""
    return _update_status(client, session_id, GAP_ANALYSIS_IN_PROGRESS)


def save_gaps(
    client: Client, session_id: str, gaps: dict[str, Any]
) -> UserResumeBuilder:
    """Persist the computed gaps jsonb and advance to the gap-interview step.

    Writes ``gaps`` + ``gaps_date`` and moves ``status`` to ``gap-interview``
    (the next ready step). ``interviewed`` is left untouched — the interview
    step flips it later.
    """
    return _update_status(
        client,
        session_id,
        GAP_INTERVIEW_STEP,
        extra={"gaps": gaps, "gaps_date": _now_iso()},
    )
