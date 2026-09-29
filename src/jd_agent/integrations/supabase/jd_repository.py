"""Repository for public.job_description (Supabase / PostgREST)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field
from supabase import Client

JOB_DESCRIPTION_TABLE = "job_description"

JobDescriptionExtractionStatus = Literal[
    "pending", "extracting", "done", "failed"
]

JobDescriptionOriginType = Literal[
    "copy_paste",
    "linkedin_url",
    "indeed_url",
    "ziprecruiter_url",
    "glassdoor_url",
    "monster_url",
    "careerbuilder_url",
    "dice_url",
    "careerjet_url",
    "simplyhired_url",
    "job_board_url",
    "other_url",
]

# Origin types that require fetching a remote posting before prepare_jd_text.
URL_ORIGIN_TYPES: frozenset[str] = frozenset(
    {
        "linkedin_url",
        "indeed_url",
        "ziprecruiter_url",
        "glassdoor_url",
        "monster_url",
        "careerbuilder_url",
        "dice_url",
        "careerjet_url",
        "simplyhired_url",
        "job_board_url",
        "other_url",
    }
)


class JobDescriptionSkill(BaseModel):
    """Skill entry stored on a job description."""

    id: str | None = None
    name: str = ""
    requirement_level: float = 1.0
    model_config = {"extra": "allow"}


class JobDescription(BaseModel):
    """Row shape for ``job_description`` (hand-typed, mirrors fullstack)."""

    id: str
    company_name: str = ""
    title_name: str = ""
    origin_jd: str = ""
    origin_type: str = "copy_paste"
    origin_id: str = ""
    last_updated: str = ""
    skills: list[JobDescriptionSkill] = Field(default_factory=list)
    extraction_status: JobDescriptionExtractionStatus = "pending"
    company_id: str | None = None
    sections: dict[str, Any] = Field(default_factory=dict)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _normalize_skills(value: Any) -> list[JobDescriptionSkill]:
    if not isinstance(value, list):
        return []
    out: list[JobDescriptionSkill] = []
    for item in value:
        if isinstance(item, JobDescriptionSkill):
            out.append(item)
            continue
        if isinstance(item, dict) and _is_skill_dict(item):
            payload = dict(item)
            if not isinstance(payload.get("name"), str):
                payload["name"] = ""
            out.append(JobDescriptionSkill.model_validate(payload))
    return out


def _is_skill_dict(item: dict[str, Any]) -> bool:
    """Accept a name, or an id whose display fields live on the skill graph."""

    if isinstance(item.get("name"), str):
        return True
    skill_id = item.get("id")
    return isinstance(skill_id, str) and bool(skill_id.strip())


def _normalize_sections(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _normalize_extraction_status(value: Any) -> JobDescriptionExtractionStatus:
    if value in ("pending", "extracting", "done", "failed"):
        return value  # type: ignore[return-value]
    return "pending"


def normalize_job_description(row: dict[str, Any]) -> JobDescription:
    return JobDescription(
        id=str(row["id"]),
        company_name=str(row.get("company_name") or ""),
        title_name=str(row.get("title_name") or ""),
        origin_jd=str(row.get("origin_jd") or ""),
        origin_type=str(row.get("origin_type") or "copy_paste"),
        origin_id=str(row.get("origin_id") or ""),
        last_updated=str(row.get("last_updated") or _now_iso()),
        skills=_normalize_skills(row.get("skills")),
        extraction_status=_normalize_extraction_status(row.get("extraction_status")),
        company_id=(
            str(row["company_id"]) if row.get("company_id") is not None else None
        ),
        sections=_normalize_sections(row.get("sections")),
    )


def _raise_on_error(error: Any, *, fallback: str) -> None:
    if error is None:
        return
    message = getattr(error, "message", None) or str(error) or fallback
    raise RuntimeError(message)


def _row_from_update_response(data: Any, *, jd_id: str) -> dict[str, Any]:
    """Unwrap PostgREST update ``data`` (list or object) to a single row dict.

    Update builders return ``SyncFilterRequestBuilder``, which has no ``.single()``.
    """
    if isinstance(data, list):
        if not data:
            raise RuntimeError(f"No job_description row for id={jd_id}")
        data = data[0]
    if not data:
        raise RuntimeError(f"No job_description row for id={jd_id}")
    if not isinstance(data, dict):
        raise RuntimeError(f"Unexpected job_description payload for id={jd_id}")
    return data


def get_by_id(client: Client, jd_id: str) -> JobDescription | None:
    """Load a job description by primary key."""
    response = (
        client.table(JOB_DESCRIPTION_TABLE)
        .select("*")
        .eq("id", jd_id)
        .maybe_single()
        .execute()
    )
    _raise_on_error(getattr(response, "error", None), fallback="Failed to load JD")
    data = response.data
    if not data:
        return None
    if isinstance(data, list):
        if not data:
            return None
        data = data[0]
    return normalize_job_description(data)


def update_extraction_status(
    client: Client,
    jd_id: str,
    extraction_status: JobDescriptionExtractionStatus,
) -> JobDescription:
    """Set ``extraction_status`` on the JD row."""
    response = (
        client.table(JOB_DESCRIPTION_TABLE)
        .update(
            {
                "extraction_status": extraction_status,
                "last_updated": _now_iso(),
            }
        )
        .eq("id", jd_id)
        .select("*")
        .execute()
    )
    _raise_on_error(
        getattr(response, "error", None),
        fallback=f"Failed to set extraction_status={extraction_status}",
    )
    return normalize_job_description(
        _row_from_update_response(response.data, jd_id=jd_id)
    )


def mark_failed(client: Client, jd_id: str) -> JobDescription:
    """Persist ``failed`` extraction_status (for invoke wrappers on graph errors)."""
    return update_extraction_status(client, jd_id, "failed")


def update_names(
    client: Client,
    jd_id: str,
    *,
    company_name: str | None = None,
    title_name: str | None = None,
) -> JobDescription:
    """Persist company/title labels discovered mid-pipeline."""
    payload: dict[str, Any] = {"last_updated": _now_iso()}
    if company_name is not None:
        payload["company_name"] = company_name
    if title_name is not None:
        payload["title_name"] = title_name
    if len(payload) == 1:
        raise ValueError("update_names requires company_name and/or title_name")

    response = (
        client.table(JOB_DESCRIPTION_TABLE)
        .update(payload)
        .eq("id", jd_id)
        .select("*")
        .execute()
    )
    _raise_on_error(
        getattr(response, "error", None),
        fallback="Failed to update JD names",
    )
    return normalize_job_description(
        _row_from_update_response(response.data, jd_id=jd_id)
    )


def upsert_sections(
    client: Client,
    jd_id: str,
    sections: dict[str, Any],
    *,
    title_name: str | None = None,
    company_name: str | None = None,
) -> JobDescription:
    """Write structured sections and sync title / company labels."""
    payload: dict[str, Any] = {
        "sections": sections,
        "last_updated": _now_iso(),
    }
    if title_name:
        payload["title_name"] = title_name
    elif isinstance(sections.get("title"), str) and sections["title"]:
        payload["title_name"] = sections["title"]
    if company_name:
        payload["company_name"] = company_name

    response = (
        client.table(JOB_DESCRIPTION_TABLE)
        .update(payload)
        .eq("id", jd_id)
        .select("*")
        .execute()
    )
    _raise_on_error(
        getattr(response, "error", None),
        fallback="Failed to upsert JD sections",
    )
    return normalize_job_description(
        _row_from_update_response(response.data, jd_id=jd_id)
    )


def get_sections(client: Client, jd_id: str) -> dict[str, Any]:
    """Return the ``sections`` jsonb for ``jd_id`` (empty dict if missing)."""
    row = get_by_id(client, jd_id)
    if row is None:
        raise RuntimeError(f"No job_description row for id={jd_id}")
    return row.sections


def upsert_skills(
    client: Client,
    jd_id: str,
    *,
    skills: list[JobDescriptionSkill] | list[dict[str, Any]],
) -> JobDescription:
    """Persist extracted skills on the JD row (without requiring ``company_id``)."""
    normalized = _normalize_skills(skills)
    response = (
        client.table(JOB_DESCRIPTION_TABLE)
        .update(
            {
                "skills": [s.model_dump() for s in normalized],
                "last_updated": _now_iso(),
            }
        )
        .eq("id", jd_id)
        .select("*")
        .execute()
    )
    _raise_on_error(
        getattr(response, "error", None),
        fallback="Failed to upsert JD skills",
    )
    return normalize_job_description(
        _row_from_update_response(response.data, jd_id=jd_id)
    )


def update_company(
    client: Client,
    jd_id: str,
    *,
    company_id: str,
    company_name: str | None = None,
) -> JobDescription:
    """Persist resolved ``company_id`` and optional ``company_name``."""
    company_id = str(company_id or "").strip()
    if not company_id:
        raise ValueError("company_id is required")

    payload: dict[str, Any] = {
        "company_id": company_id,
        "last_updated": _now_iso(),
    }
    if company_name is not None:
        payload["company_name"] = company_name

    response = (
        client.table(JOB_DESCRIPTION_TABLE)
        .update(payload)
        .eq("id", jd_id)
        .select("*")
        .execute()
    )
    _raise_on_error(
        getattr(response, "error", None),
        fallback="Failed to update JD company",
    )
    return normalize_job_description(
        _row_from_update_response(response.data, jd_id=jd_id)
    )
