"""Canonical Neo4j node labels and relationship types for resume generation.

Every node label and relationship type used in this package must come from
``node_type`` / ``edge_type``. Those helpers read a cached
``TaxonomyGraph`` snapshot; they do not hardcode vocabulary strings.
"""

from __future__ import annotations

import functools
from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import patch

from mylinkedge_agent_tools.taxonomy import TaxonomyGraph, get_taxonomy_graph


@functools.cache
def _taxonomy() -> TaxonomyGraph:
    """Load the resume taxonomy graph once per process."""

    return get_taxonomy_graph()


def node_type(name: str) -> str:
    """Return the canonical node type string from the taxonomy, or raise."""

    graph = _taxonomy()
    for node in graph.all_nodes():
        if node.name == name or node.type == name:
            return node.type
    raise KeyError(f"Taxonomy node type not found: {name!r}")


def edge_type(source: str, target: str) -> str:
    """Return the canonical rel-type between two node type names, or raise."""

    edge_map = _taxonomy().build_taxonomy_edge_map()
    key = (source.casefold(), target.casefold())
    if key not in edge_map:
        raise KeyError(f"No taxonomy edge from {source!r} to {target!r}")
    return edge_map[key]


@contextmanager
def MockTaxonomyTypes(graph: TaxonomyGraph) -> Iterator[None]:
    """Patch the cached taxonomy snapshot so tests never open Neo4j."""

    _taxonomy.cache_clear()
    with patch(
        "jd_agent.graphs.resume_generate.taxonomy_types._taxonomy",
        return_value=graph,
    ):
        yield
    _taxonomy.cache_clear()


__all__ = ["MockTaxonomyTypes", "edge_type", "node_type"]
