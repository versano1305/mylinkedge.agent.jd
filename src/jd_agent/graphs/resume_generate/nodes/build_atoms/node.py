"""WU-05 — Split the dossier into evidence atoms."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from jd_agent.graphs.resume_generate.models import Dossier
from jd_agent.graphs.resume_generate.nodes.build_atoms.from_dossier import (
    build_atoms_from_dossier,
)
from jd_agent.graphs.resume_generate.state import ResumeGenerateState


def build_atoms(
    state: ResumeGenerateState, config: RunnableConfig
) -> dict[str, Any]:
    """Build ``atoms`` from the normalized dossier."""

    _ = config
    raw = state.get("dossier")
    if not isinstance(raw, dict) or not raw.get("user_id"):
        raise ValueError("dossier is required before build_atoms")

    dossier = Dossier.model_validate(raw)
    atoms = build_atoms_from_dossier(dossier)
    return {"atoms": [a.model_dump(mode="json") for a in atoms]}
