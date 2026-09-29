"""Build evidence atoms from a normalized dossier (WU-05)."""

from __future__ import annotations

from jd_agent.graphs.resume_generate.models import Atom, AtomKind, Dossier, Instance, SkillRef
from jd_agent.graphs.resume_generate.nodes.build_atoms.strength import compute_strength
from jd_agent.graphs.resume_generate.taxonomy_types import node_type
from jd_agent.shared.resume_metrics import extract_metrics
from jd_agent.shared.sentences import split_sentences
from jd_agent.shared.text_match import normalize_for_match, token_jaccard

_ATTACH_JACCARD = 0.4
_DEDUPE_JACCARD = 0.5


def build_atoms_from_dossier(dossier: Dossier) -> list[Atom]:
    """Split dossier instances into evidence atoms."""

    by_id = {i.instance_id: i for i in dossier.instances}
    exp_label = node_type("ExperienceEvent")
    ach_label = node_type("Achievement")
    proj_label = node_type("Project")
    ment_label = node_type("Mentorship")

    atoms: list[Atom] = []
    achievement_atoms: list[Atom] = []

    for inst in dossier.instances:
        if inst.node_label == ach_label:
            atom = _achievement_atom(inst, by_id, exp_label)
            atoms.append(atom)
            achievement_atoms.append(atom)
        elif inst.node_label == proj_label:
            atoms.append(_project_atom(inst, by_id, exp_label))
        elif inst.node_label == ment_label:
            atoms.append(_mentorship_atom(inst, by_id, exp_label))

    for inst in dossier.instances:
        if inst.node_label != exp_label:
            continue
        exp_achievements = [
            a
            for a in achievement_atoms
            if _belongs_to_experience(a, inst.instance_id, by_id, exp_label)
        ]
        atoms.extend(_summary_atoms_for_experience(inst, exp_achievements))

    return atoms


def _belongs_to_experience(
    ach_atom: Atom,
    exp_id: str,
    by_id: dict[str, Instance],
    exp_label: str,
) -> bool:
    inst = by_id.get(ach_atom.instance_id)
    if not inst:
        return False
    return _root_experience_id(inst, by_id, exp_label) == exp_id


def _root_experience_id(
    inst: Instance | None,
    by_id: dict[str, Instance],
    exp_label: str,
) -> str | None:
    current = inst
    while current:
        if current.node_label == exp_label:
            return current.instance_id
        pid = current.parent_instance_id
        current = by_id.get(pid) if pid else None
    return None


def _experience_end(inst: Instance, by_id: dict[str, Instance], exp_label: str) -> str | None:
    exp_id = _root_experience_id(inst, by_id, exp_label)
    if not exp_id:
        return inst.end
    exp = by_id.get(exp_id)
    return exp.end if exp else inst.end


def _skill_ids(skills: list[SkillRef]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for sk in skills:
        if sk.id not in seen:
            seen.add(sk.id)
            out.append(sk.id)
    return out


def _provenance(skills: list[SkillRef]) -> tuple[list[str], set[str]]:
    texts: list[str] = []
    kinds: set[str] = set()
    seen_text: set[str] = set()
    for sk in skills:
        for ev in sk.evidence:
            t = ev.evidenceText.strip()
            if t and t not in seen_text:
                seen_text.add(t)
                texts.append(t)
            if ev.sourceKind:
                kinds.add(ev.sourceKind)
    return texts, kinds


def _achievement_atom(
    inst: Instance,
    by_id: dict[str, Instance],
    exp_label: str,
) -> Atom:
    text = inst.summary.strip() or inst.name.strip()
    metrics = extract_metrics(text, extra=inst.impact_value)
    ev_texts, source_kinds = _provenance(inst.skills)
    end = _experience_end(inst, by_id, exp_label)
    kind: AtomKind = "achievement"
    return Atom(
        atom_id=f"ach:{inst.instance_id}",
        instance_id=inst.instance_id,
        parent_instance_id=inst.parent_instance_id,
        kind=kind,
        text=text,
        skill_ids=_skill_ids(inst.skills),
        metrics=metrics,
        node_ids=[inst.instance_id],
        evidence_texts=ev_texts,
        end=end,
        source_kinds=source_kinds,
        strength=compute_strength(
            kind,
            end=end,
            metrics=metrics,
            text=text,
            source_kinds=source_kinds,
        ),
    )


def _project_atom(
    inst: Instance,
    by_id: dict[str, Instance],
    exp_label: str,
) -> Atom:
    text = inst.summary.strip() or inst.name.strip()
    metrics = extract_metrics(text)
    ev_texts, source_kinds = _provenance(inst.skills)
    end = _experience_end(inst, by_id, exp_label)
    kind: AtomKind = "project"
    return Atom(
        atom_id=f"proj:{inst.instance_id}",
        instance_id=inst.instance_id,
        parent_instance_id=inst.parent_instance_id,
        kind=kind,
        text=text,
        skill_ids=_skill_ids(inst.skills),
        metrics=metrics,
        node_ids=[inst.instance_id],
        evidence_texts=ev_texts,
        end=end,
        source_kinds=source_kinds,
        strength=compute_strength(
            kind,
            end=end,
            metrics=metrics,
            text=text,
            source_kinds=source_kinds,
        ),
    )


def _mentorship_atom(
    inst: Instance,
    by_id: dict[str, Instance],
    exp_label: str,
) -> Atom:
    text = inst.summary.strip()
    metrics = extract_metrics(text, extra=inst.count)
    ev_texts, source_kinds = _provenance(inst.skills)
    end = _experience_end(inst, by_id, exp_label)
    kind: AtomKind = "mentorship"
    return Atom(
        atom_id=f"ment:{inst.instance_id}",
        instance_id=inst.instance_id,
        parent_instance_id=inst.parent_instance_id,
        kind=kind,
        text=text,
        skill_ids=_skill_ids(inst.skills),
        metrics=metrics,
        node_ids=[inst.instance_id],
        evidence_texts=ev_texts,
        end=end,
        source_kinds=source_kinds,
        strength=compute_strength(
            kind,
            end=end,
            metrics=metrics,
            text=text,
            source_kinds=source_kinds,
        ),
    )


def _attach_skill_to_sentence(
    skill: SkillRef,
    sentences: list[str],
) -> tuple[int | None, bool]:
    """Return (sentence_index, matched) or (None, False) for context bucket."""

    entries = [e for e in skill.evidence if e.evidenceText.strip()]
    if not entries:
        return None, False

    for entry in entries:
        norm_ev = normalize_for_match(entry.evidenceText)
        for idx, sent in enumerate(sentences):
            norm_sent = normalize_for_match(sent)
            if norm_ev and (norm_ev in norm_sent or norm_sent in norm_ev):
                return idx, True

    best_idx: int | None = None
    best_score = 0.0
    for entry in entries:
        for idx, sent in enumerate(sentences):
            score = token_jaccard(entry.evidenceText, sent)
            if score >= _ATTACH_JACCARD and score > best_score:
                best_score = score
                best_idx = idx
    if best_idx is not None:
        return best_idx, True
    return None, False


def _sentence_overlaps_achievement(sentence: str, metrics: list[str], ach: Atom) -> bool:
    if token_jaccard(sentence, ach.text) >= _DEDUPE_JACCARD:
        return True
    if metrics and ach.metrics and set(metrics) & set(ach.metrics):
        return True
    return False


def _summary_atoms_for_experience(
    exp: Instance,
    exp_achievements: list[Atom],
) -> list[Atom]:
    summary = exp.summary.strip()
    if not summary and not exp.skills:
        return []

    sentences = split_sentences(summary) if summary else []
    sentence_skills: list[list[str]] = [[] for _ in sentences]
    context_skill_ids: list[str] = []

    for sk in exp.skills:
        idx, matched = _attach_skill_to_sentence(sk, sentences)
        if matched and idx is not None:
            if sk.id not in sentence_skills[idx]:
                sentence_skills[idx].append(sk.id)
        else:
            if sk.id not in context_skill_ids:
                context_skill_ids.append(sk.id)

    out: list[Atom] = []
    kind: AtomKind = "summary_sentence"

    for i, sent in enumerate(sentences):
        metrics = extract_metrics(sent)
        if any(
            _sentence_overlaps_achievement(sent, metrics, ach)
            for ach in exp_achievements
        ):
            for sid in sentence_skills[i]:
                if sid not in context_skill_ids:
                    context_skill_ids.append(sid)
            continue

        skills_for_sent = sentence_skills[i]
        skill_objs = [sk for sk in exp.skills if sk.id in skills_for_sent]
        ev_texts, source_kinds = _provenance(skill_objs)
        out.append(
            Atom(
                atom_id=f"sum:{exp.instance_id}#{i + 1}",
                instance_id=exp.instance_id,
                parent_instance_id=None,
                kind=kind,
                text=sent,
                skill_ids=skills_for_sent,
                metrics=metrics,
                node_ids=[exp.instance_id],
                evidence_texts=ev_texts,
                end=exp.end,
                source_kinds=source_kinds,
                strength=compute_strength(
                    kind,
                    end=exp.end,
                    metrics=metrics,
                    text=sent,
                    source_kinds=source_kinds,
                ),
            )
        )

    if context_skill_ids:
        ctx_skills = [sk for sk in exp.skills if sk.id in context_skill_ids]
        ev_texts, source_kinds = _provenance(ctx_skills)
        out.append(
            Atom(
                atom_id=f"ctx:{exp.instance_id}",
                instance_id=exp.instance_id,
                parent_instance_id=None,
                kind=kind,
                text="",
                skill_ids=context_skill_ids,
                metrics=[],
                node_ids=[exp.instance_id],
                evidence_texts=ev_texts,
                end=exp.end,
                source_kinds=source_kinds,
                strength=0.0,
            )
        )

    return out
