"""Tests for WU-09 highlight validation, dispatch, and in-node retry."""

from __future__ import annotations

from jd_agent.graphs.resume_generate.constants import HIGHLIGHT_IN_NODE_RETRIES
from jd_agent.graphs.resume_generate.models import (
    BriefAtom,
    GeneratedHighlight,
    InstanceBrief,
)
from jd_agent.graphs.resume_generate.nodes.generate_highlights.dispatch import (
    build_highlight_sends,
    is_generatable_brief,
)
from jd_agent.graphs.resume_generate.nodes.generate_highlights.models import (
    HighlightGenerationResult,
)
from jd_agent.graphs.resume_generate.nodes.generate_highlights.validate import (
    validate_generation,
)
from jd_agent.graphs.resume_generate.state import _merge_dicts


def _brief(*, budget: int = 1) -> InstanceBrief:
    return InstanceBrief(
        instance_id="exp-1",
        company="Acme",
        position="Engineer",
        budget=budget,
        tense="past",
        atoms=[
            BriefAtom(
                atom_id="a1",
                text="Cut latency 40%.",
                metrics=["40%"],
                licensed=["Microservices"],
            )
        ],
    )


def test_merge_dicts_combines_parallel_generated_keys() -> None:
    left = {"exp-1": {"highlights": []}}
    right = {"exp-2": {"highlights": ["x"]}}
    merged = _merge_dicts(left, right)
    assert set(merged) == {"exp-1", "exp-2"}
    assert merged["exp-2"]["highlights"] == ["x"]


def test_validate_rejects_unlicensed_jd_term() -> None:
    brief = _brief()
    result = HighlightGenerationResult(
        highlights=[
            GeneratedHighlight(
                text="Delivered Kafka pipelines.",
                atom_ids=["a1"],
                jd_terms_used=["Kafka"],
            )
        ]
    )
    errors = validate_generation(brief, result)
    assert any("Kafka" in err for err in errors)


def test_validate_accepts_matching_bullet_count_and_terms() -> None:
    brief = _brief()
    result = HighlightGenerationResult(
        highlights=[
            GeneratedHighlight(
                text="Delivered Microservices platform improvements.",
                atom_ids=["a1"],
                jd_terms_used=["Microservices"],
            )
        ]
    )
    assert validate_generation(brief, result) == []


def test_build_highlight_sends_one_per_generatable_instance() -> None:
    state = {
        "briefs": {
            "generatable_instance_ids": ["exp-1"],
            "instances": {
                "exp-1": _brief(budget=1).model_dump(),
                "exp-2": InstanceBrief(
                    instance_id="exp-2",
                    budget=0,
                    atoms=[],
                ).model_dump(),
            },
        }
    }
    sends = build_highlight_sends(state, from_repair=False)
    assert len(sends) == 1
    assert sends[0].node == "generate_highlights"
    assert sends[0].arg["brief"]["instance_id"] == "exp-1"


def test_is_generatable_brief_requires_atoms_and_budget() -> None:
    assert is_generatable_brief(_brief(budget=1).model_dump()) is True
    assert is_generatable_brief(
        InstanceBrief(instance_id="x", budget=0, atoms=[]).model_dump()
    ) is False


def test_in_node_retry_constant_is_one_extra_attempt() -> None:
    assert HIGHLIGHT_IN_NODE_RETRIES == 1
