"""Compiled JD extraction graph.

Flow
----
1. ``load_jd`` loads the existing JD row (``origin_jd``, ``origin_type``, …).
2. ``mark_extracting`` sets ``extraction_status`` to ``extracting`` and publishes
   ``process.jd-extraction/started``.
3. Route on ``jd.origin_type``:
   - URL types → ``fetch_jd`` → ``prepare_jd_text``
   - ``copy_paste`` → ``prepare_jd_text`` directly
4. ``prepare_jd_text`` normalizes into ``jd_text``.
5. ``save_jd_sections`` structures ``jd_text`` into JD sections on ``jd_id``.
6. Skills map-reduce:
   - ``prepare_jd_info_sections`` loads enabled section configs + section text
   - fan-out per section through ``extract_section_skills``
     (``relevant_skills_from_text``; chunking lives in the skill-matching tool)
   - ``initialize_missing_skill_fields`` applies temporary P-1 fallback fields
   - ``save_jd_skills`` merges results and writes ``job_description.skills``
7. ``resolve_company`` resolves and persists ``company_id`` / ``company_name``.
8. ``mark_done`` sets ``extraction_status`` to ``done`` and publishes
   ``process.jd-extraction/finish`` with the job-description id.

See ``docs/jd_extract_graph_plan.md`` for the agreed design and mocked
boundaries.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from jd_agent.graphs.jd_extract.nodes import (
    dispatch_section_skill_tasks,
    extract_section_skills,
    fetch_jd,
    initialize_missing_skill_fields,
    load_jd,
    mark_done,
    mark_extracting,
    prepare_jd_info_sections,
    prepare_jd_text,
    resolve_company,
    route_by_origin_type,
    save_jd_sections,
    save_jd_skills,
)
from jd_agent.graphs.jd_extract.state import JdExtractState

builder = StateGraph(JdExtractState)

builder.add_node("load_jd", load_jd)
builder.add_node("mark_extracting", mark_extracting)
builder.add_node("fetch_jd", fetch_jd)
builder.add_node("prepare_jd_text", prepare_jd_text)
builder.add_node("save_jd_sections", save_jd_sections)
builder.add_node("prepare_jd_info_sections", prepare_jd_info_sections)
builder.add_node("extract_section_skills", extract_section_skills)
builder.add_node("initialize_missing_skill_fields", initialize_missing_skill_fields)
builder.add_node("save_jd_skills", save_jd_skills)
builder.add_node("resolve_company", resolve_company)
builder.add_node("mark_done", mark_done)

builder.add_edge(START, "load_jd")
builder.add_edge("load_jd", "mark_extracting")
builder.add_conditional_edges(
    "mark_extracting",
    route_by_origin_type,
    {
        "fetch_jd": "fetch_jd",
        "prepare_jd_text": "prepare_jd_text",
    },
)
builder.add_edge("fetch_jd", "prepare_jd_text")
builder.add_edge("prepare_jd_text", "save_jd_sections")
builder.add_edge("save_jd_sections", "prepare_jd_info_sections")
builder.add_conditional_edges(
    "prepare_jd_info_sections",
    dispatch_section_skill_tasks,
    ["extract_section_skills", "save_jd_skills"],
)
builder.add_edge("extract_section_skills", "initialize_missing_skill_fields")
builder.add_edge("initialize_missing_skill_fields", "save_jd_skills")
builder.add_edge("save_jd_skills", "resolve_company")
builder.add_edge("resolve_company", "mark_done")
builder.add_edge("mark_done", END)

graph = builder.compile(name="jd-extract")
