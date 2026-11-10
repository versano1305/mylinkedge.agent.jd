"""Standalone demand, supply, and PPR propagations for graph clients.

Clients (``gap_collect``, ``resume_generate``, baselines, notebooks) share the
same contracts: graph context plus operation-specific seeds, optional tuning,
and a stable result shape. Low-level math lives in ``skill_closures`` and
``gap_zones.personalized_pagerank``; this module is the public boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from jd_agent.shared.gap_zones import PPR_PERCENTILE, personalized_pagerank
from jd_agent.shared.skill_closures import (
    DEMAND_GAMMA,
    SUPPLY_HOPS,
    SUPPLY_TOP_K,
    Edge,
    IsDomain,
    SupplyFanout,
    demand_closure,
    supply_closure_noisy_or,
    supply_fanout,
)

__all__ = [
    "DemandPropagationRequest",
    "DemandPropagationResult",
    "PprPropagationRequest",
    "PprPropagationResult",
    "SkillGraphContext",
    "SupplyPropagationRequest",
    "SupplyPropagationResult",
    "compute_demand",
    "compute_ppr",
    "compute_supply",
]


@dataclass(frozen=True)
class SkillGraphContext:
    """Shared ontology inputs. One context per scoring run (same edge list + domain mask).

    Attributes:
        edges: Full Skill→Skill edge list ``(source_id, target_id, rel_type)``.
        is_domain: Predicate — ``True`` for Domain-type nodes (excluded from closures).
        fanout: Optional precomputed full-graph supply fan-out counts. When supply
            runs on a **pruned** edge subset, pass fan-out from the **full** graph
            here (see ``compute_supply``).
    """

    edges: tuple[Edge, ...]
    is_domain: IsDomain
    fanout: SupplyFanout | None = None

    @classmethod
    def from_parts(
        cls,
        edges: list[Edge],
        is_domain: IsDomain,
        *,
        fanout: SupplyFanout | None = None,
    ) -> SkillGraphContext:
        return cls(tuple(edges), is_domain, fanout)

    def full_fanout(self) -> SupplyFanout:
        if self.fanout is not None:
            return self.fanout
        return supply_fanout(list(self.edges), self.is_domain)


@dataclass(frozen=True)
class DemandPropagationRequest:
    """Expand job-side need from JD (or role) skill seeds.

    Attributes:
        context: Graph context (typically the full ontology).
        seeds: ``skill_id → importance weight`` in ``(0, 1]`` (or any positive scale;
            only relative magnitudes matter within a run). Skills not in the graph are
            ignored by propagation (callers should pre-filter).
        gamma: Per-hop decay on ``REQUIRES`` / ``USES`` forward walks (default
            ``DEMAND_GAMMA``).
        min_d_star: Drop demand nodes at or below this value from the result map
            (default ``0`` — keep all propagated nodes).
    """

    context: SkillGraphContext
    seeds: dict[str, float]
    gamma: float = DEMAND_GAMMA
    min_d_star: float = 0.0


@dataclass(frozen=True)
class DemandPropagationResult:
    """Output of demand closure.

    Attributes:
        d_star: ``skill_id → demand strength`` after forward ``REQUIRES``/``USES``
            propagation (max-product with ``gamma`` decay).
        seeds: Skill ids that were provided as seeds (for traceability).
        meta: Optional diagnostics (``gamma``, node counts).
    """

    d_star: dict[str, float]
    seeds: frozenset[str]
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SupplyPropagationRequest:
    """Expand person-side implied mastery from evidence / held-skill seeds.

    Attributes:
        context: Graph context; ``context.fanout`` should reflect the **full** graph
            when ``propagation_edges`` is a pruned subset.
        seeds: ``skill_id → seed weight`` in ``[0, 1]`` (only ``> 0`` participate).
        propagation_edges: Edges used for the walk. Defaults to ``context.edges``.
            Résumé pipelines often pass a demand-pruned subset for speed.
        hops: Supply propagation depth (default ``SUPPLY_HOPS``).
        top_k: Noisy-OR cap per target per hop; ``None`` = combine all contributions.
    """

    context: SkillGraphContext
    seeds: dict[str, float]
    propagation_edges: tuple[Edge, ...] | None = None
    hops: int = SUPPLY_HOPS
    top_k: int | None = SUPPLY_TOP_K


@dataclass(frozen=True)
class SupplyPropagationResult:
    """Output of supply closure.

    Attributes:
        s_star: ``skill_id → implied mastery`` in ``[0, 1]`` after noisy-OR propagation.
        seeds: Skill ids with positive seed weight.
        meta: ``hops``, ``top_k``, ``edge_count``, etc.
    """

    s_star: dict[str, float]
    seeds: frozenset[str]
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PprPropagationRequest:
    """Graph proximity of demand-scope skills to held skills (adjacent-latent signal).

    Attributes:
        context: Graph context; PPR is built on undirected edges touching ``demand_scope``.
        demand_scope: Node set for the PPR subgraph (typically keys of ``d_star`` with
            demand ``> 0``). Only these ids are guaranteed in ``scores``.
        ppr_seed_ids: Skills the candidate holds — personalization mass is uniform
            over seeds present in the subgraph (e.g. evidence + profile skills).
        alpha: PageRank damping (default ``0.85``).
        percentile: Compute ``rho`` as this percentile of PPR scores over ``demand_scope``
            (default ``PPR_PERCENTILE``).
    """

    context: SkillGraphContext
    demand_scope: frozenset[str]
    ppr_seed_ids: frozenset[str]
    alpha: float = 0.85
    percentile: int = PPR_PERCENTILE


@dataclass(frozen=True)
class PprPropagationResult:
    """Output of personalized PageRank over the demand neighborhood.

    Attributes:
        scores: ``skill_id → PPR score`` (every id in ``demand_scope`` at minimum).
        rho: Threshold at ``percentile`` over scores on ``demand_scope`` — skills
            with ``scores[id] > rho`` are "adjacent" latent candidates.
        meta: ``alpha``, ``percentile``, seed count, etc.
    """

    scores: dict[str, float]
    rho: float
    meta: dict[str, Any] = field(default_factory=dict)


def compute_demand(request: DemandPropagationRequest) -> DemandPropagationResult:
    """Run demand closure. Pure function of ``request`` + graph."""

    seeds = {
        sid: float(w) for sid, w in request.seeds.items() if float(w) > 0
    }
    raw = demand_closure(
        seeds,
        list(request.context.edges),
        request.context.is_domain,
        gamma=request.gamma,
    )
    if request.min_d_star > 0:
        raw = {k: v for k, v in raw.items() if v > request.min_d_star}
    else:
        raw = {k: v for k, v in raw.items() if v > 0}
    return DemandPropagationResult(
        d_star=raw,
        seeds=frozenset(seeds),
        meta={
            "gamma": request.gamma,
            "demand_node_count": len(raw),
            "seed_count": len(seeds),
        },
    )


def compute_supply(request: SupplyPropagationRequest) -> SupplyPropagationResult:
    """Run supply closure. Uses full-graph fan-out when edges are pruned."""

    seeds = {
        sid: float(w) for sid, w in request.seeds.items() if float(w) > 0
    }
    edges = (
        list(request.propagation_edges)
        if request.propagation_edges is not None
        else list(request.context.edges)
    )
    fanout = request.context.full_fanout()
    s_star = supply_closure_noisy_or(
        seeds,
        edges,
        request.context.is_domain,
        hops=request.hops,
        fanout=fanout,
        top_k=request.top_k,
    )
    return SupplyPropagationResult(
        s_star=s_star,
        seeds=frozenset(seeds),
        meta={
            "hops": request.hops,
            "top_k": request.top_k,
            "propagation_edge_count": len(edges),
            "seed_count": len(seeds),
        },
    )


def compute_ppr(request: PprPropagationRequest) -> PprPropagationResult:
    """Run PPR seeded on ``ppr_seed_ids`` within the demand-scope subgraph."""

    d_star_scope = {sid: 1.0 for sid in request.demand_scope}
    scores, rho = personalized_pagerank(
        list(request.context.edges),
        d_star_scope,
        set(request.ppr_seed_ids),
        request.context.is_domain,
        alpha=request.alpha,
        percentile=request.percentile,
    )
    return PprPropagationResult(
        scores=scores,
        rho=rho,
        meta={
            "alpha": request.alpha,
            "percentile": request.percentile,
            "demand_scope_count": len(request.demand_scope),
            "ppr_seed_count": len(request.ppr_seed_ids),
        },
    )
