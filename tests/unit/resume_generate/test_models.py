"""Contract tests for resume generation models and JSON Resume output."""

from __future__ import annotations

from jd_agent.graphs.resume_generate.models import (
    Atom,
    GeneratedHighlight,
    ResumeTrace,
)
from jd_agent.graphs.resume_generate.resume_schemas import (
    JsonResumeWork,
    TailoredJsonResume,
)


def test_atom_round_trip() -> None:
    atom = Atom(
        atom_id="ach:1",
        instance_id="exp:1",
        kind="achievement",
        text="Cut latency by 40%.",
        skill_ids=["skill:1"],
        metrics=["40%"],
        source_kinds={"resume"},
        strength=1.0,
    )
    restored = Atom.model_validate(atom.model_dump())
    assert restored.atom_id == "ach:1"
    assert restored.kind == "achievement"
    assert restored.source_kinds == {"resume"}


def test_generated_highlight_round_trip() -> None:
    highlight = GeneratedHighlight(
        text="Cut latency by 40%.",
        atom_ids=["ach:1"],
        jd_terms_used=["AWS"],
    )
    restored = GeneratedHighlight.model_validate(highlight.model_dump())
    assert restored.jd_terms_used == ["AWS"]
    assert restored.atom_ids == ["ach:1"]


def test_resume_trace_empty_is_schema_valid() -> None:
    trace = ResumeTrace.empty({"user_id": "user:1", "interviewed": False})
    restored = ResumeTrace.model_validate(trace.model_dump())
    assert restored.schema_version == 1
    assert restored.meta.user_id == "user:1"
    assert restored.meta.constants["license_tau"] == 0.80
    assert restored.lines == {}
    assert restored.gap_report == []


def test_to_json_resume_strips_instance_id() -> None:
    document = TailoredJsonResume(
        resume_id="resume:1",
        user_id="user:1",
        jd_extraction_id="jd:1",
        work=[
            JsonResumeWork(
                name="Acme",
                position="Engineer",
                highlights=["Shipped the API."],
                instance_id="exp:1",
            )
        ],
    )
    payload = document.to_json_resume()
    assert payload["work"][0]["name"] == "Acme"
    assert "instance_id" not in payload["work"][0]
    assert "resume_id" not in payload
