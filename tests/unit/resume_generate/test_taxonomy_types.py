"""Taxonomy type helpers resolve labels from a fixture graph, never Neo4j."""

from __future__ import annotations

import pytest
from mylinkedge_agent_tools.taxonomy import TaxonomyEdge, TaxonomyGraph, TaxonomyNode

from jd_agent.graphs.resume_generate.taxonomy_types import (
    MockTaxonomyTypes,
    edge_type,
    node_type,
)


def _fixture_graph() -> TaxonomyGraph:
    return TaxonomyGraph(
        nodes={
            "experience": TaxonomyNode(
                id="experience",
                type="ExperienceEvent",
                name="ExperienceEvent",
            ),
            "skill": TaxonomyNode(id="skill", type="Skill", name="Skill"),
        },
        edges=[
            TaxonomyEdge(
                id="experience|uses|skill",
                source="experience",
                target="skill",
                type="USES_SKILL",
                source_name="ExperienceEvent",
                target_name="Skill",
            )
        ],
    )


def test_node_type_returns_canonical_type() -> None:
    with MockTaxonomyTypes(_fixture_graph()):
        assert node_type("ExperienceEvent") == "ExperienceEvent"


def test_edge_type_returns_canonical_rel() -> None:
    with MockTaxonomyTypes(_fixture_graph()):
        assert edge_type("ExperienceEvent", "Skill") == "USES_SKILL"


def test_node_type_unknown_raises() -> None:
    with MockTaxonomyTypes(_fixture_graph()):
        with pytest.raises(KeyError, match="not found"):
            node_type("MissingLabel")


def test_edge_type_unknown_raises() -> None:
    with MockTaxonomyTypes(_fixture_graph()):
        with pytest.raises(KeyError, match="No taxonomy edge"):
            edge_type("Skill", "ExperienceEvent")
