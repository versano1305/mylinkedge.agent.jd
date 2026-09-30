"""Chance-corrected fit against degree-matched random profiles.

Raw fit depends on how densely the ontology connects a profile to a JD: after
an edge expansion, any profile of the same size can score high. The baseline
is the mean fit of ``BASELINE_SAMPLES`` random profiles that replace each seed
skill with a random skill of the same degree bucket (same seed weight), scored
against the same demand closure on the same graph. The normalized fit is

    fit_normalized = max(0, (fit - baseline) / (1 - baseline))

i.e. the share of the headroom above chance the profile actually earns. See
``docs/fit_normalization.md``.
"""

from __future__ import annotations

import hashlib
import math
import random
import statistics
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field

from jd_agent.shared.gap_zones import chance_corrected_fit, compute_gaps
from jd_agent.shared.skill_closures import (
    SUPPLY_FANOUT_BETA,
    SUPPLY_FANOUT_REF,
    SUPPLY_HOPS,
    SUPPLY_TOP_K,
    Edge,
    IsDomain,
    SupplyFanout,
    supply_closure_noisy_or,
)

BASELINE_SAMPLES = 32

__all__ = [
    "BASELINE_SAMPLES",
    "DegreeMatchedSampler",
    "FitBaseline",
    "chance_corrected_fit",
    "explicit_fit",
    "ontology_fingerprint",
    "profile_baseline",
]


@dataclass(frozen=True)
class FitBaseline:
    """Fit distribution of degree-matched random profiles."""

    mean: float
    sd: float
    samples: int
    s_star_mean: dict[str, float] = field(default_factory=dict)


def _degree_bucket(degree: int) -> int:
    return int(math.log2(degree + 1))


class DegreeMatchedSampler:
    """Draw random stand-ins for seed skills with a similar graph degree."""

    def __init__(self, edges: list[Edge], candidate_ids: Iterable[str]) -> None:
        degree: dict[str, int] = defaultdict(int)
        for u, v, _r in edges:
            degree[u] += 1
            degree[v] += 1
        self._degree = dict(degree)
        buckets: dict[int, list[str]] = defaultdict(list)
        for sid in sorted(set(candidate_ids)):
            buckets[_degree_bucket(self._degree.get(sid, 0))].append(sid)
        self._buckets = dict(buckets)

    def sample(self, seeds: dict[str, float], rng: random.Random) -> dict[str, float]:
        """Replace each seed with a same-bucket skill, keeping its weight."""

        out: dict[str, float] = {}
        for sid in sorted(seeds):
            weight = float(seeds[sid])
            if weight <= 0:
                continue
            pool = self._buckets.get(_degree_bucket(self._degree.get(sid, 0)))
            pick = rng.choice(pool) if pool else sid
            out[pick] = max(out.get(pick, 0.0), weight)
        return out


def _rng_for(d_star: dict[str, float], seeds: dict[str, float]) -> random.Random:
    digest = hashlib.sha256()
    for sid in sorted(d_star):
        digest.update(sid.encode())
    digest.update(b"|")
    for sid in sorted(seeds):
        digest.update(f"{sid}:{seeds[sid]:.4f}".encode())
    return random.Random(int.from_bytes(digest.digest()[:8], "big"))


def profile_baseline(
    d_star: dict[str, float],
    weights: dict[str, float],
    seeds: dict[str, float],
    edges: list[Edge],
    is_domain: IsDomain,
    sampler: DegreeMatchedSampler,
    *,
    fanout: SupplyFanout | None = None,
    samples: int = BASELINE_SAMPLES,
) -> FitBaseline:
    """Fit of ``samples`` degree-matched random versions of ``seeds``.

    ``edges`` may be the pruned supply subset for speed, as long as ``fanout``
    comes from the full graph. The random stream is seeded from the demand
    closure and seeds, so repeated runs give the same baseline.
    """

    rng = _rng_for(d_star, seeds)
    fits: list[float] = []
    s_sum: dict[str, float] = defaultdict(float)
    for _ in range(max(1, samples)):
        null_seeds = sampler.sample(seeds, rng)
        s_star = (
            supply_closure_noisy_or(null_seeds, edges, is_domain, fanout=fanout)
            if null_seeds
            else {}
        )
        fits.append(compute_gaps(d_star, s_star, weights)[1])
        for sid in d_star:
            s_sum[sid] += s_star.get(sid, 0.0)
    n = len(fits)
    return FitBaseline(
        mean=statistics.fmean(fits),
        sd=statistics.stdev(fits) if n > 1 else 0.0,
        samples=n,
        s_star_mean={sid: total / n for sid, total in s_sum.items()},
    )


def explicit_fit(
    d_star: dict[str, float],
    weights: dict[str, float],
    seeds: dict[str, float],
) -> float:
    """Fit from seed evidence alone, with no graph propagation."""

    return compute_gaps(d_star, seeds, weights)[1]


def ontology_fingerprint(edges: list[Edge]) -> dict[str, object]:
    """Identify the graph and supply settings a fit was computed on."""

    digest = hashlib.sha256()
    for u, v, r in sorted(edges):
        digest.update(f"{u}\t{v}\t{r}\n".encode())
    return {
        "edge_count": len(edges),
        "edge_hash": digest.hexdigest()[:16],
        "supply": {
            "hops": SUPPLY_HOPS,
            "fanout_ref": SUPPLY_FANOUT_REF,
            "fanout_beta": SUPPLY_FANOUT_BETA,
            "top_k": SUPPLY_TOP_K,
            "baseline_samples": BASELINE_SAMPLES,
        },
    }
