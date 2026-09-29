"""Tests for WU-10 summary context and validation."""

from __future__ import annotations

from jd_agent.graphs.resume_generate.models import SummaryResult
from jd_agent.graphs.resume_generate.nodes.generate_summary.context import (
    build_summary_context,
    has_summary_content,
)
from jd_agent.graphs.resume_generate.nodes.generate_summary.validate import (
    validate_summary,
)


def test_build_summary_context_allowlists() -> None:
    state = {
        "briefs": {
            "static": {
                "basics": {"label": "Cloud Architect"},
                "skills": [{"name": "Cloud", "keywords": ["AWS"]}],
            },
            "years_facts": {"total_years": 12.0, "per_skill": {}},
            "skill_group_labels": ["Cloud & Infrastructure"],
        },
        "generated": {
            "exp-1": {
                "highlights": [
                    {
                        "text": "Built AWS platform.",
                        "atom_ids": ["a1"],
                        "jd_terms_used": ["AWS"],
                    }
                ]
            }
        },
        "allocation": {"selected": {"exp-1": ["a1"]}},
        "atoms": [
            {
                "atom_id": "a1",
                "kind": "achievement",
                "strength": 1.0,
                "metrics": ["40%"],
            }
        ],
        "jd_context": {"title": "Architect", "company_name": "Acme"},
        "jd_targets": [],
        "jd_domains": [],
    }
    ctx = build_summary_context(state)
    assert ctx["label"] == "Cloud Architect"
    assert "AWS" in ctx["allowed_terms"]
    assert "40%" in ctx["allowed_numbers"]
    assert ctx["flagship_metric"]["metric"] == "40%"
    assert has_summary_content(ctx)


def test_validate_summary_rejects_bad_claims() -> None:
    ctx = {
        "allowed_terms": ["AWS"],
        "allowed_numbers": ["12+"],
        "flagship_metric": None,
    }
    result = SummaryResult(
        text="Engineer with Kafka experience.",
        claimed_terms=["Kafka"],
        claimed_numbers=[],
    )
    errors = validate_summary(ctx, result)
    assert any("claimed term" in e for e in errors)
