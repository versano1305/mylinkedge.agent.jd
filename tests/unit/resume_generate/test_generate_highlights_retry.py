"""In-node retry when validation fails on the first LLM response."""

from __future__ import annotations

from jd_agent.graphs.resume_generate.models import BriefAtom, GeneratedHighlight, InstanceBrief
from jd_agent.graphs.resume_generate.nodes.generate_highlights import agent as agent_mod
from jd_agent.graphs.resume_generate.nodes.generate_highlights.models import (
    HighlightGenerationResult,
)


def test_generate_for_brief_retries_once_after_validation_failure(monkeypatch) -> None:
    brief = InstanceBrief(
        instance_id="exp-1",
        budget=1,
        tense="past",
        atoms=[
            BriefAtom(
                atom_id="a1",
                text="Shipped feature.",
                licensed=["Go"],
            )
        ],
    )
    bad = HighlightGenerationResult(
        highlights=[
            GeneratedHighlight(
                text="Bad.",
                atom_ids=["a1"],
                jd_terms_used=["Python"],
            )
        ]
    )
    good = HighlightGenerationResult(
        highlights=[
            GeneratedHighlight(
                text="Shipped Go services.",
                atom_ids=["a1"],
                jd_terms_used=["Go"],
            )
        ]
    )
    calls: list[str] = []

    def _fake_invoke(_agent, user_message, _fmt, config=None):
        calls.append(user_message)
        return bad if len(calls) == 1 else good

    monkeypatch.setattr(agent_mod, "invoke_structured_agent", _fake_invoke)
    monkeypatch.setattr(agent_mod, "_get_agent", lambda: object())

    result = agent_mod.generate_for_brief(brief)
    assert len(calls) == 2
    assert "failed validation" in calls[1]
    assert result.highlights[0].jd_terms_used == ["Go"]
