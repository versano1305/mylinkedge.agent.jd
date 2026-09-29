"""Expose the tools-repo top-level ``shared`` namespace package.

``mylinkedge-agent-tools-skills`` imports ``from shared.models import ...``,
where ``shared`` is a namespace package living at the *root* of the
``mylinkedge.agent.tools`` workspace (not inside the installed package). Consumer
repos are expected to put that root on ``sys.path`` — the interview repo does it
via a workspace ``.pth``. We reproduce that here without depending on a
venv-specific ``.pth`` so ``make install`` alone is enough.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def ensure_shared_on_path() -> None:
    """Insert the tools workspace root on ``sys.path`` if ``shared`` is missing."""
    if importlib.util.find_spec("shared") is not None:
        return
    try:
        import mylinkedge_agent_tools as tools_pkg
    except ImportError:
        return

    for entry in list(getattr(tools_pkg, "__path__", [])):
        for parent in Path(entry).parents:
            if (parent / "shared").is_dir():
                root = str(parent)
                if root not in sys.path:
                    sys.path.insert(0, root)
                return
