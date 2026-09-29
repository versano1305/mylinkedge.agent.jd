"""State schema for the gap collection graph.

``session_id`` is required: a ``user_resume_builder`` row already exists (the
frontend created it and ran JD extraction). ``load_session`` hydrates the
session and its joined ``job_description``; downstream nodes read from those
rather than duplicating fields as invoke inputs.

The assembled ``gaps`` document is written to ``user_resume_builder.gaps`` and
serves both the gap-review UI (``gaps.review``) and the interview
(``gaps.interview``). ``meta.fit_if_all_latent`` is the counterfactual fit if
every latent-zone skill were confirmed; ``review.latent_fit`` mirrors that for
display.
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict

from jd_agent.integrations.supabase.jd_repository import JobDescription
from jd_agent.integrations.supabase.user_resume_builder_repository import (
    UserResumeBuilder,
)

GapCollectStatus = Literal["analyzing", "done", "failed"]


class GapCollectState(TypedDict, total=False):
    """Shared state that flows through gap collection nodes."""

    # Studio / API input
    session_id: str  # Required: existing user_resume_builder row

    # Loaded from DB
    session: UserResumeBuilder
    jd: JobDescription
    user_id: str
    job_description_id: str

    # Intermediate
    jd_raw_skills: list[dict[str, Any]]  # normalized JD skills before resolution
    user_skill_ids: list[str]  # candidate reachable/held Skill ids
    evidence_skill_ids: list[str]  # evidence-backed subset (supply seeds)
    interview_candidates: list[dict[str, Any]]  # pre-ranking, from compute_gaps

    # Output
    gaps: dict[str, Any]  # full jsonb: meta + review + skills + interview
    gap_status: GapCollectStatus
    errors: list[str]  # soft, non-fatal notes (e.g. event publish failure)
