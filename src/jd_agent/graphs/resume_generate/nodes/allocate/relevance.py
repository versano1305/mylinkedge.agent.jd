"""Role relevance vs the JD title (WU-07)."""

from __future__ import annotations

from typing import Any

from jd_agent.graphs.resume_generate.constants import TITLE_SIMILARITY_LAMBDA
from jd_agent.graphs.resume_generate.models import Instance


from jd_agent.shared.text_similarity import jaccard


def title_similarity(instance: Instance, d_star_ids: set[str]) -> float:
    """Fallback overlap between role skills and JD demand closure ids."""

    role_skills = {str(s.id) for s in instance.skills if str(s.id).strip()}
    return jaccard(role_skills, d_star_ids)


def role_relevance(
    exp_id: str,
    instance: Instance,
    atoms: list[dict[str, Any]],
    d_star_ids: set[str],
    *,
    title_lambda: float = TITLE_SIMILARITY_LAMBDA,
) -> float:
    """``sum(top-3 standalone_value) + λ · title_similarity``."""

    _ = exp_id
    values = sorted(
        (float(a.get("standalone_value") or 0.0) for a in atoms),
        reverse=True,
    )
    top_three = sum(values[:3])
    return top_three + title_lambda * title_similarity(instance, d_star_ids)
