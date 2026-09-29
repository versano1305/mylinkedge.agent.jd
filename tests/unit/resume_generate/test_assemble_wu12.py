"""Unit tests for WU-12 resume assembly and trace."""

from __future__ import annotations

from jd_agent.graphs.resume_generate.models import ResumeTrace
from jd_agent.graphs.resume_generate.nodes.assemble_and_save.resume_document import (
    build_resume_document,
)
from jd_agent.graphs.resume_generate.nodes.assemble_and_save.trace_document import (
    build_trace_document,
)


def test_build_resume_merges_work_and_omits_current_end_date() -> None:
    state = {
        "session_id": "sess-1",
        "user_id": "user-1",
        "briefs": {
            "static": {
                "basics": {"name": "Ada Lovelace", "label": "Engineer"},
                "skills": [{"name": "Tools", "keywords": ["Python"]}],
            },
            "instances": {
                "exp-1": {
                    "instance_id": "exp-1",
                    "company": "Acme",
                    "position": "Lead",
                    "startDate": "2020-01",
                    "endDate": None,
                    "budget": 1,
                    "tense": "present",
                    "atoms": [],
                }
            },
            "skills_sources": {"Python": ["has_skill"]},
        },
        "allocation": {"instance_order": ["exp-1"], "resume_fit": 0.55},
        "generated": {
            "exp-1": {
                "summary": "Fintech platform team.",
                "highlights": [
                    {
                        "text": "Shipped APIs.",
                        "atom_ids": ["ach:1"],
                        "jd_terms_used": ["Python"],
                    }
                ],
            }
        },
        "summary": {
            "text": "Engineer with 10+ years.",
            "claimed_terms": ["Python"],
            "claimed_numbers": ["10+"],
        },
        "verification": {
            "coverage": {
                "weighted": 0.5,
                "must": {"covered": 1, "total": 2},
                "nice": {"covered": 0, "total": 1},
            },
            "gap_report": [],
            "dropped_lines": [],
        },
        "demand": {"fit_profile": 0.71},
        "atoms": [
            {
                "atom_id": "ach:1",
                "node_ids": ["node-1"],
                "licensed": [
                    {
                        "jd_skill_id": "skill-py",
                        "surface_form": "Python",
                        "via": "explicit",
                    }
                ],
            }
        ],
        "repair_round": 0,
        "jd_context": {"unresolved": []},
    }

    resume = build_resume_document(state)
    assert resume["basics"]["summary"] == "Engineer with 10+ years."
    assert len(resume["work"]) == 1
    work = resume["work"][0]
    assert work["name"] == "Acme"
    assert "endDate" not in work
    assert work["highlights"] == ["Shipped APIs."]
    assert "instance_id" not in work

    trace = build_trace_document(state)
    assert trace.lines["work[0].highlights[0]"].atom_ids == ["ach:1"]
    assert trace.lines["work[0].highlights[0]"].licensed_via["Python"] == "explicit"
    assert trace.lines["basics.summary"].claimed_numbers == ["10+"]
    assert trace.fit.profile == 0.71
    assert trace.fit.resume == 0.55
    assert trace.skills_sources["Python"] == ["has_skill"]

    dumped = trace.model_dump()
    ResumeTrace.model_validate(dumped)
