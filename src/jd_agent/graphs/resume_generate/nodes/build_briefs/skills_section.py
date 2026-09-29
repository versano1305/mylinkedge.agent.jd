"""Skills section keywords, grouping, and provenance."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from jd_agent.graphs.resume_generate.constants import (
    MAX_KEYWORDS_PER_GROUP,
    MAX_SKILL_GROUPS,
    N_EXTRA_SKILLS,
)
from jd_agent.graphs.resume_generate.resume_schemas import JsonResumeSkill
from jd_agent.shared.dossier_skills import instance_evidence_skill_ids
from jd_agent.shared.gap_zones import skill_group_label
from jd_agent.shared.skill_closures import Edge


class _Keyword:
    __slots__ = ("skill_id", "keyword", "score", "sources")

    def __init__(
        self,
        skill_id: str,
        keyword: str,
        score: float,
        sources: list[str],
    ) -> None:
        self.skill_id = skill_id
        self.keyword = keyword
        self.score = score
        self.sources = sources


def _jd_maps(
    jd_targets: list[dict[str, Any]],
) -> tuple[dict[str, str], dict[str, float], dict[str, float]]:
    surface: dict[str, str] = {}
    weights: dict[str, float] = {}
    d_star_weight: dict[str, float] = {}
    for t in jd_targets:
        if not isinstance(t, dict):
            continue
        sid = str(t.get("skill_id") or "").strip()
        if not sid:
            continue
        surface[sid] = str(t.get("surface_form") or t.get("name") or sid)
        weights[sid] = float(t.get("weight") or 1.0)
        d_star_weight[sid] = weights[sid]
    return surface, weights, d_star_weight


def _score_skill(
    skill_id: str,
    d_star: dict[str, float],
    weights: dict[str, float],
) -> float:
    return float(weights.get(skill_id, 1.0)) * float(d_star.get(skill_id, 0.0))


def _collect_from_atoms(
    atoms: list[dict[str, Any]],
    d_star: dict[str, float],
) -> dict[str, _Keyword]:
    by_skill: dict[str, _Keyword] = {}
    for atom in atoms:
        if not isinstance(atom, dict):
            continue
        aid = str(atom.get("atom_id") or "")
        for term in atom.get("licensed") or []:
            if not isinstance(term, dict):
                continue
            jid = str(term.get("jd_skill_id") or "").strip()
            if not jid or jid not in d_star:
                continue
            form = str(term.get("surface_form") or "").strip()
            if not form:
                continue
            src = aid if aid else "atom"
            if jid in by_skill:
                if src not in by_skill[jid].sources:
                    by_skill[jid].sources.append(src)
            else:
                by_skill[jid] = _Keyword(jid, form, 0.0, [src])
    return by_skill


def _add_has_skill_and_certs(
    dossier: dict[str, Any],
    d_star: dict[str, float],
    jd_surface: dict[str, str],
    by_skill: dict[str, _Keyword],
) -> None:
    for sk in dossier.get("skills") or []:
        if not isinstance(sk, dict):
            continue
        sid = str(sk.get("id") or "").strip()
        if not sid or sid not in d_star or sid in by_skill:
            continue
        keyword = jd_surface.get(sid) or str(sk.get("name") or sid)
        by_skill[sid] = _Keyword(sid, keyword, 0.0, ["has_skill"])

    for cert in dossier.get("certificates") or []:
        if not isinstance(cert, dict):
            continue
        cert_name = str(cert.get("name") or "certificate")
        for sk in cert.get("skills") or []:
            if not isinstance(sk, dict):
                continue
            sid = str(sk.get("id") or "").strip()
            if not sid or sid not in d_star:
                continue
            keyword = jd_surface.get(sid) or str(sk.get("name") or sid)
            src = f"certificate:{cert_name}"
            if sid in by_skill:
                if src not in by_skill[sid].sources:
                    by_skill[sid].sources.append(src)
            else:
                by_skill[sid] = _Keyword(sid, keyword, 0.0, [src])


def _part_of_parent(skill_id: str, edges: list[Edge], skill_meta: dict[str, dict[str, str]]) -> str:
    parent_counts: dict[str, int] = defaultdict(int)
    for u, v, r in edges:
        if r == "PART_OF" and u == skill_id:
            parent_counts[v] += 1
    if not parent_counts:
        return skill_id
    return max(parent_counts, key=lambda k: parent_counts[k])


def build_skills_section(
    dossier: dict[str, Any],
    atoms: list[dict[str, Any]],
    demand: dict[str, Any],
    jd_targets: list[dict[str, Any]],
    edges: list[Edge],
    skill_meta: dict[str, dict[str, str]],
) -> tuple[list[JsonResumeSkill], dict[str, list[str]], list[str]]:
    """Return skills groups, ``skills_sources`` map, and ordered group labels."""

    d_star = {k: float(v) for k, v in (demand.get("d_star") or {}).items()}
    s_star = {k: float(v) for k, v in (demand.get("s_star_profile") or {}).items()}
    jd_surface, weights, _ = _jd_maps(jd_targets)

    by_skill = _collect_from_atoms(atoms, d_star)
    _add_has_skill_and_certs(dossier, d_star, jd_surface, by_skill)

    for sid, kw in by_skill.items():
        kw.score = _score_skill(sid, d_star, weights)

    chosen_ids = set(by_skill)
    evidence = instance_evidence_skill_ids(dossier)
    extras: list[_Keyword] = []
    for sid in evidence:
        if sid in chosen_ids or sid in d_star:
            continue
        name = skill_meta.get(sid, {}).get("name") or sid
        extras.append(
            _Keyword(
                sid,
                name,
                float(s_star.get(sid, 0.0)),
                ["profile_explicit"],
            )
        )
    extras.sort(key=lambda k: (-k.score, k.keyword))
    for extra in extras[:N_EXTRA_SKILLS]:
        by_skill[extra.skill_id] = extra
        chosen_ids.add(extra.skill_id)

    groups: dict[str, list[_Keyword]] = defaultdict(list)
    for sid, kw in by_skill.items():
        root = _part_of_parent(sid, edges, skill_meta)
        groups[root].append(kw)

    group_scores: list[tuple[str, float, list[_Keyword]]] = []
    for root, members in groups.items():
        gscore = sum(m.score for m in members)
        group_scores.append((root, gscore, members))

    group_scores.sort(key=lambda x: (-x[1], x[0]))
    group_scores = group_scores[:MAX_SKILL_GROUPS]

    skills_out: list[JsonResumeSkill] = []
    skills_sources: dict[str, list[str]] = {}
    group_labels: list[str] = []

    for root, _, members in group_scores:
        members.sort(key=lambda m: (-m.score, m.keyword))
        capped = members[:MAX_KEYWORDS_PER_GROUP]
        member_ids = [m.skill_id for m in capped]
        label = skill_group_label(member_ids, edges, skill_meta)
        keywords = [m.keyword for m in capped]
        skills_out.append(JsonResumeSkill(name=label, keywords=keywords))
        group_labels.append(label)
        for m in capped:
            skills_sources.setdefault(m.keyword, [])
            for src in m.sources:
                if src not in skills_sources[m.keyword]:
                    skills_sources[m.keyword].append(src)

    return skills_out, skills_sources, group_labels
