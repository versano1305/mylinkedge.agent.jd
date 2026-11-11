"""Unit tests for the JD demand node."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from mylinkedge_agent_tools.graph_algorithms import DemandPropagationResult

from jd_agent.graphs.jd_extract.nodes.compute_demands.node import compute_demands
from jd_agent.integrations.supabase.jd_repository import JobDescription, JobDescriptionSkill
from jd_agent.shared.demand_seeds import demand_seeds

_NODE = "jd_agent.graphs.jd_extract.nodes.compute_demands.node"


def _skill(skill_id: str | None, name: str, **extra: object) -> JobDescriptionSkill:
    payload: dict[str, object] = {"id": skill_id, "name": name}
    payload.update(extra)
    return JobDescriptionSkill.model_validate(payload)


def test_demand_seeds_keeps_strongest_resolved_weight() -> None:
    seeds = demand_seeds(
        [
            _skill("skill-python", "Python", importance=0.4),
            _skill("skill-python", "Python", importance=0.9),
            _skill(None, "Go"),
            _skill("skill-sql", "SQL", importance=0.25),
            _skill("skill-zero", "Zero", importance=0),
        ]
    )
    assert seeds == {"skill-python": 0.9, "skill-sql": 0.25}


def test_demand_seeds_reads_skill_id_and_known_ids() -> None:
    seeds = demand_seeds(
        [
            {"skill_id": "A", "importance": 0.2},
            {"skill_id": "A", "importance": 0.8},
            {"skill_id": "missing", "importance": 1.0},
        ],
        known_ids={"A"},
    )
    assert seeds == {"A": 0.8}


def test_compute_demands_publishes_closure() -> None:
    jd = JobDescription(
        id="jd-1",
        title_name="Engineer",
        company_name="Acme",
        skills=[
            _skill("skill-python", "Python", importance=1.0),
            _skill("skill-sql", "SQL", importance=0.4),
        ],
    )
    state = {"jd_id": "jd-1", "user_id": "user-1", "jd": jd}
    result = DemandPropagationResult(
        d_star={"skill-python": 1.0, "skill-sql": 0.4, "skill-implied": 0.85},
        seeds=frozenset({"skill-python", "skill-sql"}),
        meta={"gamma": 0.85, "seed_count": 2, "demand_node_count": 3},
    )
    client = MagicMock()
    client.compute_demand.return_value = result

    with (
        patch(f"{_NODE}.GraphAlgorithmsClient", return_value=client),
        patch(f"{_NODE}.publish_jd_extraction_data_from_state") as publish,
    ):
        updates = compute_demands(state, {"configurable": {"run_id": "run-1"}})

    request = client.compute_demand.call_args.args[0]
    assert request.seeds == {"skill-python": 1.0, "skill-sql": 0.4}
    expected = {
        "d_star": {
            "skill-implied": 0.85,
            "skill-python": 1.0,
            "skill-sql": 0.4,
        },
        "seeds": {"skill-python": 1.0, "skill-sql": 0.4},
        "meta": {"gamma": 0.85, "seed_count": 2, "demand_node_count": 3},
    }
    assert updates == {"jd_demands": expected}
    publish.assert_called_once_with(
        state,
        kind="demands",
        data={
            "demands": expected,
            "title_name": "Engineer",
            "company_name": "Acme",
        },
        config={"configurable": {"run_id": "run-1"}},
    )


def test_compute_demands_requires_jd() -> None:
    with pytest.raises(ValueError, match="jd is required"):
        compute_demands({}, {})
