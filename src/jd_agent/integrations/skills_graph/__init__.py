"""Skills-graph reads for the gap collector (Neo4j data database).

Importing this package first ensures the tools-repo ``shared`` namespace is on
``sys.path`` (see ``_bootstrap``) before the skills client is imported.
"""

from jd_agent.integrations.skills_graph._bootstrap import ensure_shared_on_path

# The tools ``shared`` namespace must be importable before the skills client.
ensure_shared_on_path()

from mylinkedge_agent_tools.skills.client import get_skills_graph  # noqa: E402

from jd_agent.integrations.skills_graph.candidate_dossier import (  # noqa: E402
    fetch_candidate_dossier,
)
from jd_agent.integrations.skills_graph.owner_nodes import (  # noqa: E402
    count_owner_nodes,
)
from jd_agent.integrations.skills_graph.skill_details import (  # noqa: E402
    fetch_skills_by_ids,
)
from jd_agent.integrations.skills_graph.user_skills import (  # noqa: E402
    fetch_user_skill_ids,
)

__all__ = [
    "count_owner_nodes",
    "fetch_candidate_dossier",
    "fetch_skills_by_ids",
    "fetch_user_skill_ids",
    "get_skills_graph",
]
