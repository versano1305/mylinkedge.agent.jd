"""JSON Resume v1.0.0 models for the resume_generate graph.

Source: mylinkedge.agent.resume/src/resume_agent/shared/resume_schemas.py

Graph-local: only ``resume_generate`` imports this module.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

JSON_RESUME_SCHEMA_URL = (
    "https://raw.githubusercontent.com/jsonresume/resume-schema/v1.0.0/schema.json"
)


class JsonResumeLocation(BaseModel):
    """JSON Resume ``basics.location`` object."""

    model_config = {"extra": "allow"}

    address: str | None = None
    postalCode: str | None = None
    city: str | None = None
    countryCode: str | None = None
    region: str | None = None


class JsonResumeProfile(BaseModel):
    """JSON Resume social profile entry."""

    model_config = {"extra": "allow"}

    network: str | None = None
    username: str | None = None
    url: str | None = None


class JsonResumeBasics(BaseModel):
    """JSON Resume ``basics`` block."""

    model_config = {"extra": "allow"}

    name: str | None = None
    label: str | None = None
    image: str | None = None
    email: str | None = None
    phone: str | None = None
    url: str | None = None
    summary: str | None = None
    location: JsonResumeLocation | None = None
    profiles: list[JsonResumeProfile] = Field(default_factory=list)


class JsonResumeWork(BaseModel):
    """JSON Resume ``work[]`` item. ``highlights`` are JD-tailored."""

    model_config = {"extra": "allow"}

    name: str | None = None
    location: str | None = None
    description: str | None = None
    position: str | None = None
    url: str | None = None
    startDate: str | None = None
    endDate: str | None = None
    summary: str | None = None
    highlights: list[str] = Field(default_factory=list)
    instance_id: str | None = None


class JsonResumeVolunteer(BaseModel):
    """JSON Resume ``volunteer[]`` item. ``highlights`` are JD-tailored."""

    model_config = {"extra": "allow"}

    organization: str | None = None
    position: str | None = None
    url: str | None = None
    startDate: str | None = None
    endDate: str | None = None
    summary: str | None = None
    highlights: list[str] = Field(default_factory=list)
    instance_id: str | None = None


class JsonResumeEducation(BaseModel):
    """JSON Resume ``education[]`` item."""

    model_config = {"extra": "allow"}

    institution: str | None = None
    url: str | None = None
    area: str | None = None
    studyType: str | None = None
    startDate: str | None = None
    endDate: str | None = None
    score: str | None = None
    courses: list[str] = Field(default_factory=list)
    instance_id: str | None = None


class JsonResumeAward(BaseModel):
    """JSON Resume ``awards[]`` item."""

    model_config = {"extra": "allow"}

    title: str | None = None
    date: str | None = None
    awarder: str | None = None
    summary: str | None = None


class JsonResumeCertificate(BaseModel):
    """JSON Resume ``certificates[]`` item."""

    model_config = {"extra": "allow"}

    name: str | None = None
    date: str | None = None
    url: str | None = None
    issuer: str | None = None
    instance_id: str | None = None


class JsonResumePublication(BaseModel):
    """JSON Resume ``publications[]`` item."""

    model_config = {"extra": "allow"}

    name: str | None = None
    publisher: str | None = None
    releaseDate: str | None = None
    url: str | None = None
    summary: str | None = None


class JsonResumeSkill(BaseModel):
    """JSON Resume ``skills[]`` item."""

    model_config = {"extra": "allow"}

    name: str | None = None
    level: str | None = None
    keywords: list[str] = Field(default_factory=list)


class JsonResumeLanguage(BaseModel):
    """JSON Resume ``languages[]`` item."""

    model_config = {"extra": "allow"}

    language: str | None = None
    fluency: str | None = None


class JsonResumeInterest(BaseModel):
    """JSON Resume ``interests[]`` item."""

    model_config = {"extra": "allow"}

    name: str | None = None
    keywords: list[str] = Field(default_factory=list)


class JsonResumeReference(BaseModel):
    """JSON Resume ``references[]`` item."""

    model_config = {"extra": "allow"}

    name: str | None = None
    reference: str | None = None


class JsonResumeProject(BaseModel):
    """JSON Resume ``projects[]`` item. ``highlights`` are JD-tailored."""

    model_config = {"extra": "allow"}

    name: str | None = None
    description: str | None = None
    highlights: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    startDate: str | None = None
    endDate: str | None = None
    url: str | None = None
    roles: list[str] = Field(default_factory=list)
    entity: str | None = None
    type: str | None = None
    instance_id: str | None = None


class JsonResumeMeta(BaseModel):
    """JSON Resume ``meta`` object."""

    model_config = {"extra": "allow"}

    canonical: str | None = None
    version: str | None = None
    lastModified: str | None = None


class JsonResumeStaticSkeleton(BaseModel):
    """LLM-filled JSON Resume fields excluding tailored highlights/summary/skills."""

    basics: JsonResumeBasics = Field(default_factory=JsonResumeBasics)
    work: list[JsonResumeWork] = Field(default_factory=list)
    volunteer: list[JsonResumeVolunteer] = Field(default_factory=list)
    education: list[JsonResumeEducation] = Field(default_factory=list)
    certificates: list[JsonResumeCertificate] = Field(default_factory=list)
    projects: list[JsonResumeProject] = Field(default_factory=list)
    languages: list[JsonResumeLanguage] = Field(default_factory=list)


class TailoredJsonResume(BaseModel):
    """Final persistable resume: JSON Resume document plus pipeline metadata."""

    resume_id: str
    user_id: str
    jd_extraction_id: str
    schema_url: str = JSON_RESUME_SCHEMA_URL
    basics: JsonResumeBasics = Field(default_factory=JsonResumeBasics)
    work: list[JsonResumeWork] = Field(default_factory=list)
    volunteer: list[JsonResumeVolunteer] = Field(default_factory=list)
    education: list[JsonResumeEducation] = Field(default_factory=list)
    awards: list[JsonResumeAward] = Field(default_factory=list)
    certificates: list[JsonResumeCertificate] = Field(default_factory=list)
    publications: list[JsonResumePublication] = Field(default_factory=list)
    skills: list[JsonResumeSkill] = Field(default_factory=list)
    languages: list[JsonResumeLanguage] = Field(default_factory=list)
    interests: list[JsonResumeInterest] = Field(default_factory=list)
    references: list[JsonResumeReference] = Field(default_factory=list)
    projects: list[JsonResumeProject] = Field(default_factory=list)
    meta: JsonResumeMeta | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_json_resume(self) -> dict[str, Any]:
        """Return a JSON Resume document without pipeline-only fields."""

        def _dump_items(items: list[Any]) -> list[dict[str, Any]]:
            return [
                item.model_dump(exclude_none=True, exclude={"instance_id"})
                for item in items
            ]

        payload: dict[str, Any] = {
            "$schema": self.schema_url,
            "basics": self.basics.model_dump(exclude_none=True),
            "work": _dump_items(self.work),
            "volunteer": _dump_items(self.volunteer),
            "education": _dump_items(self.education),
            "awards": [item.model_dump(exclude_none=True) for item in self.awards],
            "certificates": _dump_items(self.certificates),
            "publications": [
                item.model_dump(exclude_none=True) for item in self.publications
            ],
            "skills": [item.model_dump(exclude_none=True) for item in self.skills],
            "languages": [item.model_dump(exclude_none=True) for item in self.languages],
            "interests": [item.model_dump(exclude_none=True) for item in self.interests],
            "references": [
                item.model_dump(exclude_none=True) for item in self.references
            ],
            "projects": _dump_items(self.projects),
        }
        if self.meta is not None:
            payload["meta"] = self.meta.model_dump(exclude_none=True)
        return payload


def empty_json_resume() -> dict[str, Any]:
    """Schema-valid JSON Resume with empty sections."""

    last_modified = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return TailoredJsonResume(
        resume_id="",
        user_id="",
        jd_extraction_id="",
        meta=JsonResumeMeta(version="v1.0.0", lastModified=last_modified),
    ).to_json_resume()
