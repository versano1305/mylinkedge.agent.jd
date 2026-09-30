"""Demand and supply closures over the Skill ontology.

Ported from ``notebooks/jd_gap_collector_v2`` (skills.ai.agents). Two closures:

* **Demand closure** — forward max-product on ``REQUIRES``/``USES``: a job that
  needs skill A also needs A's learning/runtime prerequisites.
* **Supply closure** — multi-source noisy-OR with the calibrated α table: owning
  a skill lifts the mastery of its related skills (asymmetric per direction).

``Domain`` skills are context, not competence, and are masked from both closures
(see the skill-graph core model). The α coefficients are calibrated values — do
not invent new ones here.

Supply is damped against ontology density so that adding edges does not
inflate mastery on its own (see ``docs/fit_normalization.md``):

* **Fan-out scaling** — an arc's α is scaled by
  ``min(1, (SUPPLY_FANOUT_REF / fanout) ** SUPPLY_FANOUT_BETA)``, where
  ``fanout`` counts the arcs of the same edge type and direction leaving the
  source. Fan-out is a property of the *whole* graph: callers that run the
  closure over a pruned edge list must pass the full-graph ``fanout``.
* **Top-k noisy-OR** — only the ``SUPPLY_TOP_K`` strongest contributions into
  a skill are combined, so parallel paths added by an expansion stop
  compounding.
"""

from __future__ import annotations

import warnings
from collections import defaultdict
from collections.abc import Callable

import networkx as nx

Edge = tuple[str, str, str]  # (source_id, target_id, rel_type); source -[:rel]-> target

DEMAND_GAMMA = 0.85
SUPPLY_HOPS = 3
DOMAIN_SKILL_TYPE = "Domain"

# Density damping, tuned on the pre/post skill-expansion graphs.
SUPPLY_FANOUT_REF = 3
SUPPLY_FANOUT_BETA = 0.5
SUPPLY_TOP_K = 2

# Calibrated mastery-propagation coefficients (edge_type, direction) → α.
# Forward = owning the source implies the target; backward = the reverse.
ALPHA: dict[tuple[str, str], float] = {
    ("REQUIRES", "fwd"): 0.90,
    ("REQUIRES", "bwd"): 0.00,
    ("USES", "fwd"): 0.80,
    ("USES", "bwd"): 0.05,
    ("ENABLES", "fwd"): 0.70,
    ("ENABLES", "bwd"): 0.25,
    ("PART_OF", "fwd"): 0.1, # Set to 0.1 Since all skills started with PART_OF and not been evaluated yet. 
    ("PART_OF", "bwd"): 0.1,
}

IsDomain = Callable[[str], bool]

SupplyInfluence = tuple[str, str, float]  # (source_id, target_id, α)

# Arc count per ``fanout_key(source, rel_type, direction)``.
SupplyFanout = dict[str, int]


def make_is_domain(skill_meta: dict[str, dict[str, str]]) -> IsDomain:
    """Build an ``is_domain`` predicate from skill metadata."""

    def _is_domain(skill_id: str) -> bool:
        return skill_meta.get(skill_id, {}).get("skillType", "") == DOMAIN_SKILL_TYPE

    return _is_domain


def scc_warn(edges: list[Edge]) -> list[str]:
    """Warn when ``REQUIRES ∪ USES`` has a cycle (breaks propagation).

    Returns a small sample of a cyclic component for diagnostics (empty when
    acyclic).
    """
    g = nx.DiGraph()
    for u, v, r in edges:
        if r in ("REQUIRES", "USES"):
            g.add_edge(u, v)
    if g.number_of_nodes() == 0:
        return []
    cyclic = [c for c in nx.strongly_connected_components(g) if len(c) > 1]
    if not cyclic:
        return []
    sample = sorted(next(iter(cyclic)))[:5]
    warnings.warn(
        f"REQUIRES∪USES has {len(cyclic)} non-trivial SCC(s); sample={sample}. "
        "Closures may saturate — fix ontology cycles.",
        stacklevel=2,
    )
    return sample


def fanout_key(source: str, rel_type: str, direction: str) -> str:
    return f"{source}|{rel_type}|{direction}"


def _supply_arcs(
    edges: list[Edge], is_domain: IsDomain
) -> list[tuple[str, str, float, str]]:
    """``(source, target, α, fanout_key)`` for every propagating arc."""

    arcs: list[tuple[str, str, float, str]] = []
    for u, v, r in edges:
        if is_domain(u) or is_domain(v):
            continue
        a_fwd = ALPHA.get((r, "fwd"), 0.0)
        a_bwd = ALPHA.get((r, "bwd"), 0.0)
        if a_fwd > 0:
            arcs.append((u, v, a_fwd, fanout_key(u, r, "fwd")))
        if a_bwd > 0:
            arcs.append((v, u, a_bwd, fanout_key(v, r, "bwd")))
    return arcs


def supply_fanout(edges: list[Edge], is_domain: IsDomain) -> SupplyFanout:
    """Count propagating arcs per source, edge type, and direction."""

    counts: dict[str, int] = defaultdict(int)
    for _src, _tgt, _alpha, key in _supply_arcs(edges, is_domain):
        counts[key] += 1
    return dict(counts)


def fanout_scale(
    fanout: int,
    ref: float = SUPPLY_FANOUT_REF,
    beta: float = SUPPLY_FANOUT_BETA,
) -> float:
    """α multiplier for an arc whose source fans out to ``fanout`` targets."""

    if fanout <= ref:
        return 1.0
    return (ref / fanout) ** beta


def build_supply_influence(
    edges: list[Edge],
    is_domain: IsDomain,
    fanout: SupplyFanout | None = None,
) -> list[SupplyInfluence]:
    """Directed supply-propagation arcs with fan-out-scaled α.

    ``fanout`` defaults to counts over ``edges``; pass the full-graph counts
    when ``edges`` is a pruned subset so α matches the unpruned closure.
    """

    arcs = _supply_arcs(edges, is_domain)
    if fanout is None:
        fanout = supply_fanout(edges, is_domain)
    return [
        (src, tgt, alpha * fanout_scale(fanout.get(key, 1)))
        for src, tgt, alpha, key in arcs
    ]


def demand_closure(
    seed_weights: dict[str, float],
    edges: list[Edge],
    is_domain: IsDomain,
    gamma: float = DEMAND_GAMMA,
) -> dict[str, float]:
    """Demand closure ``d*``: how strongly the role requires each skill.

    Seeds are the skills the job already names (typically the JD list, each
    with its demand weight). Walking forward on ``REQUIRES`` (a learning
    prerequisite) and ``USES`` (a runtime tool) pulls in skills the listing
    does not mention: a role that needs skill A also needs what A requires
    and what A uses. Each hop multiplies demand by ``gamma``, so an implied
    skill is required, and more weakly the further it sits from a seed.
    When several paths reach the same skill, the strongest demand is kept
    (max-product). ``Domain`` skills are industry context and are left out.

    The returned map is that expanded demand set: skill id → demand weight
    in ``(0, seed]``. Seeds keep the weight they were given; every other
    entry is a prerequisite or tool the graph says the role still needs.
    Callers use it as the demand side of the gap against the supply
    closure ``s*``.
    """
    # d starts as the named demand; propagation only adds or raises entries.
    d: dict[str, float] = defaultdict(float, seed_weights)
    # source -[:REQUIRES|USES]-> target means "needing source also needs target".
    children: dict[str, list[str]] = defaultdict(list)
    for u, v, r in edges:
        if r in ("REQUIRES", "USES") and not is_domain(v) and not is_domain(u):
            children[u].append(v)

    # Relax until demand stops rising. A skill's weight is gamma times the
    # strongest parent, so distance from a seed discounts how required it is.
    for _ in range(max(len(d) + 20, 50)):
        changed = False
        nxt = dict(d)
        for u, du in list(d.items()):
            if du <= 0:
                continue
            for v in children.get(u, []):
                cand = gamma * du
                if cand > nxt.get(v, 0.0):
                    nxt[v] = cand
                    changed = True
        d = nxt
        if not changed:
            break
    return dict(d)


def supply_closure_noisy_or(
    seeds: dict[str, float],
    edges: list[Edge],
    is_domain: IsDomain,
    hops: int = SUPPLY_HOPS,
    *,
    fanout: SupplyFanout | None = None,
    top_k: int | None = SUPPLY_TOP_K,
) -> dict[str, float]:
    """Top-k noisy-OR supply propagation with fan-out-scaled α, both directions.

    ``fanout`` is forwarded to ``build_supply_influence``. ``top_k=None``
    combines every contribution (plain noisy-OR).
    """
    influence = build_supply_influence(edges, is_domain, fanout)

    s: dict[str, float] = defaultdict(
        float, {k: float(v) for k, v in seeds.items() if v > 0}
    )
    for _ in range(hops):
        contrib: dict[str, list[float]] = defaultdict(list)
        for src, tgt, alpha in influence:
            if s.get(src, 0.0) > 0:
                contrib[tgt].append(alpha * s[src])
        nxt = dict(s)
        for tgt, probs in contrib.items():
            if top_k is not None and len(probs) > top_k:
                probs = sorted(probs, reverse=True)[:top_k]
            base = seeds.get(tgt, 0.0)
            remain = 1.0 - base
            for p in probs:
                remain *= 1.0 - min(p, 1.0)
            nxt[tgt] = max(nxt.get(tgt, 0.0), 1.0 - remain)
        for k, v in seeds.items():
            nxt[k] = max(nxt.get(k, 0.0), v)
        delta = max(
            (abs(nxt.get(k, 0) - s.get(k, 0)) for k in set(nxt) | set(s)),
            default=0.0,
        )
        s = nxt
        if delta < 1e-4:
            break
    return dict(s)
