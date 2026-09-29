"""Tests that the JD extraction graph compiles as a skeleton."""

from jd_agent.graphs.jd_extract.jd_extract_graph import graph
from jd_agent.graphs.jd_extract.nodes import route_by_origin_type
from jd_agent.integrations.supabase.jd_repository import JobDescription


def test_jd_extract_graph_compiles() -> None:
    assert graph is not None
    assert graph.name == "jd-extract"


def test_jd_extract_graph_has_expected_nodes() -> None:
    node_names = set(graph.get_graph().nodes)
    assert "load_jd" in node_names
    assert "fetch_jd" in node_names
    assert "prepare_jd_text" in node_names
    assert "save_jd_sections" in node_names
    assert "prepare_jd_info_sections" in node_names
    assert "extract_section_skills" in node_names
    assert "initialize_missing_skill_fields" in node_names
    assert "save_jd_skills" in node_names
    assert "resolve_company" in node_names
    assert "upsert_extraction" not in node_names
    assert "mark_done" in node_names
    assert "extract_jd_info" not in node_names


def test_route_linkedin_url_goes_to_fetch_jd() -> None:
    jd = JobDescription(
        id="1",
        origin_type="linkedin_url",
        origin_jd="https://www.linkedin.com/jobs/view/1",
    )
    assert route_by_origin_type({"jd": jd}) == "fetch_jd"


def test_route_copy_paste_goes_to_prepare_jd_text() -> None:
    jd = JobDescription(
        id="1",
        origin_type="copy_paste",
        origin_jd="Pasted JD text",
    )
    assert route_by_origin_type({"jd": jd}) == "prepare_jd_text"
