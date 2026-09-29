"""Tests for WU-11 verification rules."""

from __future__ import annotations

from types import SimpleNamespace

from jd_agent.graphs.resume_generate.models import (
    GeneratedHighlight,
    InstanceBrief,
    SummaryResult,
)
from jd_agent.graphs.resume_generate.nodes.verify.checks import (
    verify_highlight,
    verify_summary,
)
import importlib

from jd_agent.graphs.resume_generate.state import ResumeGenerateState


def _jd_spans() -> list:
    import re

    return [("skill-aws", "AWS", re.compile(r"AWS", re.I))]


def test_verify_highlight_catches_invented_number() -> None:
    brief = InstanceBrief.model_validate(
        {
            "instance_id": "exp-1",
            "budget": 1,
            "tense": "past",
            "atoms": [
                {
                    "atom_id": "a1",
                    "text": "Shipped.",
                    "metrics": ["40%"],
                    "licensed": ["AWS"],
                }
            ],
        }
    )
    highlight = GeneratedHighlight(
        text="Improved uptime by 99%.",
        atom_ids=["a1"],
        jd_terms_used=["AWS"],
    )
    errors = verify_highlight(
        brief,
        highlight,
        index=0,
        seen_verbs=set(),
        jd_spans=_jd_spans(),
    )
    assert any("99%" in e for e in errors)


def test_verify_summary_repair_feedback_key() -> None:
    ctx = {
        "generated": {},
        "static_skills": [],
        "skill_group_labels": [],
        "atoms": [],
        "years_facts": {},
        "selected_ids": set(),
        "flagship_metric": None,
    }
    summary = SummaryResult(text="Short summary.", claimed_terms=[], claimed_numbers=[])
    errors = verify_summary(summary, context=ctx)
    assert errors == []


def test_verify_node_increments_repair_round(monkeypatch) -> None:
    fake_graph = SimpleNamespace(
        nodes={"skill-aws": SimpleNamespace(name="AWS", skill_type="Tool")},
        edges=[],
    )
    verify_node = importlib.import_module(
        "jd_agent.graphs.resume_generate.nodes.verify.node"
    )

    monkeypatch.setattr(verify_node, "get_skills_graph", lambda: fake_graph)

    state: ResumeGenerateState = {
        "repair_round": 0,
        "briefs": {
            "instances": {
                "exp-1": {
                    "instance_id": "exp-1",
                    "budget": 1,
                    "tense": "past",
                    "atoms": [
                        {
                            "atom_id": "a1",
                            "text": "x",
                            "metrics": [],
                            "licensed": [],
                        }
                    ],
                }
            },
            "static": {"skills": []},
            "years_facts": {"total_years": 0, "per_skill": {}},
        },
        "generated": {
            "exp-1": {
                "highlights": [
                    {
                        "text": "I built things.",
                        "atom_ids": ["a1"],
                        "jd_terms_used": [],
                    }
                ]
            }
        },
        "summary": {"text": "", "claimed_terms": [], "claimed_numbers": []},
        "demand": {"d_star": {"skill-aws": 1.0}, "zones": {}},
        "jd_targets": [
            {
                "skill_id": "skill-aws",
                "name": "AWS",
                "surface_form": "AWS",
                "weight": 1.0,
            }
        ],
        "atoms": [],
        "allocation": {},
    }
    out = verify_node.verify(state, {})
    assert out["repair_round"] == 1
    assert out["verification"]["needs_repair"] is True
    assert "exp-1" in out["verification"]["failed_instances"]
