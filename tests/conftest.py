"""Shared fixtures: in-memory postgres lib backend and Neo4j owner counts."""

from __future__ import annotations

import importlib
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import pytest
from mylinkedge_agent_tools.postgres import (
    JobDescription,
    PostgresDb,
    UserResumeBuilder,
    UserResumeBuilderWithJobDescription,
    set_postgres_db,
)

SESSION_ID = "00000000-0000-0000-0000-000000000001"
USER_ID = "00000000-0000-0000-0000-0000000000aa"
JD_ID = "00000000-0000-0000-0000-0000000000bb"


@dataclass
class FakeUserResumeBuilders:
    """Only the methods resume_generate calls; records writes."""

    sessions: dict[str, UserResumeBuilderWithJobDescription] = field(default_factory=dict)
    status_updates: list[tuple[str, str]] = field(default_factory=list)
    saved_resumes: list[tuple[str, dict, dict]] = field(default_factory=list)

    def get_with_job_description(self, id: str) -> UserResumeBuilderWithJobDescription | None:
        return self.sessions.get(id)

    def get_by_id(self, id: str) -> UserResumeBuilder | None:
        loaded = self.sessions.get(id)
        return loaded.session if loaded else None

    def update_status(self, id: str, status: str) -> UserResumeBuilder:
        self.status_updates.append((id, status))
        loaded = self.sessions[id]
        updated = loaded.session.model_copy(update={"status": status})
        self.sessions[id] = loaded.model_copy(update={"session": updated})
        return updated

    def save_resume(self, id: str, resume: Any, resume_trace: Any) -> UserResumeBuilder:
        self.saved_resumes.append((id, resume, resume_trace))
        loaded = self.sessions[id]
        updated = loaded.session.model_copy(
            update={
                "status": "generate",
                "resume": resume,
                "resume_trace": resume_trace,
                "resume_date": "2026-01-01T00:00:00+00:00",
            }
        )
        self.sessions[id] = loaded.model_copy(update={"session": updated})
        return updated


def make_session(
    *,
    session_id: str = SESSION_ID,
    user_id: str = USER_ID,
    extraction_status: str = "done",
    interviewed: bool = False,
) -> UserResumeBuilderWithJobDescription:
    return UserResumeBuilderWithJobDescription(
        session=UserResumeBuilder(
            id=session_id,
            user_id=user_id,
            status="template",
            job_description_id=JD_ID,
            interviewed=interviewed,
        ),
        job_description=JobDescription(
            id=JD_ID,
            title_name="Cloud Architect",
            company_name="Acme",
            extraction_status=extraction_status,  # type: ignore[arg-type]
        ),
    )


@pytest.fixture
def fake_urb() -> Iterator[FakeUserResumeBuilders]:
    repo = FakeUserResumeBuilders(sessions={SESSION_ID: make_session()})
    set_postgres_db(
        PostgresDb(
            job_descriptions=None,  # type: ignore[arg-type]
            user_resume_builders=repo,  # type: ignore[arg-type]
            backend="supabase",
        )
    )
    yield repo
    set_postgres_db(None)


@pytest.fixture
def owner_person_count(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Stub the Neo4j ``Person`` count; set ``["value"]`` to change it."""

    state: dict[str, Any] = {"value": 1, "calls": []}

    def _count(user_id: str, label: str, **_: Any) -> int:
        state["calls"].append((user_id, label))
        return int(state["value"])

    node_module = importlib.import_module(
        "jd_agent.graphs.resume_generate.nodes.load_session.node"
    )
    monkeypatch.setattr(node_module, "count_owner_nodes", _count)
    return state
