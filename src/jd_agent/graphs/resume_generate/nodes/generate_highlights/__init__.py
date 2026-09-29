"""Highlight generation node."""

from jd_agent.graphs.resume_generate.nodes.generate_highlights.node import (
    dispatch_highlights_after_briefs,
    dispatch_highlights_after_verify,
    generate_highlights,
)

__all__ = [
    "dispatch_highlights_after_briefs",
    "dispatch_highlights_after_verify",
    "generate_highlights",
]
