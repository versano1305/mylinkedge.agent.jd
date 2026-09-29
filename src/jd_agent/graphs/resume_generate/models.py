"""Pipeline contracts for resume generation.

Node labels and relationship types are plain strings. Callers fill them from
``taxonomy_types``; this module does not embed Neo4j vocabulary.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from jd_agent.graphs.resume_generate.constants import trace_constants

AtomKind = Literal["achievement", "project", "mentorship", "summary_sentence"]
LicenseVia = Literal["explicit", "implied"]
BriefTense = Literal["present", "past"]


class EvidenceEntry(BaseModel):
    """One normalized evidence entry from an instance-to-skill edge."""

    model_config = ConfigDict(extra="forbid")

    evidenceText: str = ""
    sourceKind: str = ""
    confidence: float = 0.0
    relType: str = ""
    sourceDocumentId: str | None = None


class SkillRef(BaseModel):
    """Skill identity carried on dossier instances so later units do not re-query."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str = ""
    skillType: str = ""
    evidence: list[EvidenceEntry] = Field(default_factory=list)


class Instance(BaseModel):
    """One resume anchor loaded from the person subgraph."""

    model_config = ConfigDict(extra="forbid")

    instance_id: str
    node_label: str
    parent_instance_id: str | None = None
    name: str = ""
    summary: str = ""
    start: str | None = None
    end: str | None = None
    raw_start: str | None = None
    raw_end: str | None = None
    company: str = ""
    position: str = ""
    location: str = ""
    employment_type: str = ""
    team_size: str = ""
    industry: str = ""
    company_description: str = ""
    position_aliases: list[str] = Field(default_factory=list)
    skills: list[SkillRef] = Field(default_factory=list)
    # Achievement-specific (node_label == "Achievement")
    impact_value: str | None = None
    # Mentorship-specific (node_label == "Mentorship")
    count: str | None = None
    duration: str | None = None


class Dossier(BaseModel):
    """Normalized person subgraph used by selection and static sections."""

    model_config = ConfigDict(extra="forbid")

    user_id: str
    first_name: str = ""
    last_name: str = ""
    email: str = ""
    phone_number: str = ""
    linkedin: str = ""
    address: str = ""
    location: dict[str, Any] = Field(default_factory=dict)
    instances: list[Instance] = Field(default_factory=list)
    # raw_educations preserves education-specific fields (gpa, specialization,
    # degree_level, courses) that WU-08 needs and that don't fit Instance.
    # Each entry is the Cypher row dict after date normalization.
    raw_educations: list[dict[str, Any]] = Field(default_factory=list)
    certificates: list[dict[str, Any]] = Field(default_factory=list)
    languages: list[dict[str, Any]] = Field(default_factory=list)
    awards: list[dict[str, Any]] = Field(default_factory=list)
    publications: list[dict[str, Any]] = Field(default_factory=list)
    volunteer: list[dict[str, Any]] = Field(default_factory=list)
    skills: list[SkillRef] = Field(default_factory=list)


class LicensedTerm(BaseModel):
    """A JD term an atom is allowed to write, or an adjacent unlicensed term."""

    model_config = ConfigDict(extra="forbid")

    jd_skill_id: str
    surface_form: str
    via: LicenseVia
    s: float | None = None


class Atom(BaseModel):
    """Smallest evidence unit a resume line can be built from."""

    model_config = ConfigDict(extra="forbid")

    atom_id: str
    instance_id: str
    parent_instance_id: str | None = None
    kind: AtomKind
    text: str
    skill_ids: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    node_ids: list[str] = Field(default_factory=list)
    evidence_texts: list[str] = Field(default_factory=list)
    end: str | None = None
    source_kinds: set[str] = Field(default_factory=set)
    strength: float = 0.0
    licensed: list[LicensedTerm] = Field(default_factory=list)
    adjacent: list[LicensedTerm] = Field(default_factory=list)
    standalone_value: float | None = None


class Allocation(BaseModel):
    """Atom selection and line budgets for one resume run (WU-07)."""

    model_config = ConfigDict(extra="forbid")

    instance_order: list[str] = Field(default_factory=list)
    tiers: dict[str, str] = Field(default_factory=dict)
    budgets: dict[str, int] = Field(default_factory=dict)
    selected: dict[str, list[str]] = Field(default_factory=dict)
    promotion_groups: dict[str, list[str]] = Field(default_factory=dict)
    resume_fit: float = 0.0
    covered_jd_skill_ids: list[str] = Field(default_factory=list)


class BriefAtom(BaseModel):
    """Selected atom as presented to highlight generation."""

    model_config = ConfigDict(extra="forbid")

    atom_id: str
    text: str
    metrics: list[str] = Field(default_factory=list)
    licensed: list[str] = Field(default_factory=list)


class InstanceBrief(BaseModel):
    """Per-instance generation brief."""

    model_config = ConfigDict(extra="forbid")

    instance_id: str
    company: str = ""
    position: str = ""
    startDate: str | None = None
    endDate: str | None = None
    location: str = ""
    employmentType: str = ""
    teamSize: str = ""
    industry: str = ""
    company_description: str = ""
    budget: int = 0
    tense: BriefTense = "past"
    atoms: list[BriefAtom] = Field(default_factory=list)


class GeneratedHighlight(BaseModel):
    """One rewritten resume bullet and the atoms and JD terms it used."""

    model_config = ConfigDict(extra="forbid")

    text: str
    atom_ids: list[str] = Field(default_factory=list)
    jd_terms_used: list[str] = Field(default_factory=list)


class GeneratedInstance(BaseModel):
    """Highlights and optional work summary for one instance."""

    model_config = ConfigDict(extra="forbid")

    summary: str = ""
    highlights: list[GeneratedHighlight] = Field(default_factory=list)


class SummaryResult(BaseModel):
    """Generated ``basics.summary`` plus the claims the verifier checks."""

    model_config = ConfigDict(extra="forbid")

    text: str = ""
    claimed_terms: list[str] = Field(default_factory=list)
    claimed_numbers: list[str] = Field(default_factory=list)


class TraceLineProvenance(BaseModel):
    """Provenance for one rendered resume line."""

    model_config = ConfigDict(extra="forbid")

    atom_ids: list[str] = Field(default_factory=list)
    node_ids: list[str] = Field(default_factory=list)
    jd_skill_ids: list[str] = Field(default_factory=list)
    licensed_via: dict[str, str] = Field(default_factory=dict)
    repair_rounds: int = 0
    claimed_terms: list[str] = Field(default_factory=list)
    claimed_numbers: list[str] = Field(default_factory=list)


class TraceFit(BaseModel):
    """Fit scores recorded on the trace."""

    model_config = ConfigDict(extra="forbid")

    before_interview: float | None = None
    profile: float | None = None
    resume: float | None = None


class CoverageCounts(BaseModel):
    """Covered versus total JD skills for one importance bucket."""

    model_config = ConfigDict(extra="forbid")

    covered: int = 0
    total: int = 0


class CoverageReport(BaseModel):
    """Literal JD-term coverage of the assembled resume."""

    model_config = ConfigDict(extra="forbid")

    weighted: float = 0.0
    must: CoverageCounts = Field(default_factory=CoverageCounts)
    nice: CoverageCounts = Field(default_factory=CoverageCounts)


class GapReportEntry(BaseModel):
    """One JD skill the resume does not claim, and why."""

    model_config = ConfigDict(extra="forbid")

    skill_id: str
    name: str
    status: str
    via: str | None = None
    advice: str = ""


class TraceMeta(BaseModel):
    """Run metadata stored beside line provenance."""

    model_config = ConfigDict(extra="forbid")

    user_id: str = ""
    job_description_id: str = ""
    interviewed: bool = False
    jd_enriched: bool = False
    unresolved: list[str] = Field(default_factory=list)
    constants: dict[str, Any] = Field(default_factory=dict)


class ResumeTrace(BaseModel):
    """Pipeline-only provenance persisted next to the JSON Resume document."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    meta: TraceMeta = Field(default_factory=TraceMeta)
    fit: TraceFit = Field(default_factory=TraceFit)
    lines: dict[str, TraceLineProvenance] = Field(default_factory=dict)
    skills_sources: dict[str, list[str]] = Field(default_factory=dict)
    coverage: CoverageReport = Field(default_factory=CoverageReport)
    gap_report: list[GapReportEntry] = Field(default_factory=list)
    dropped_lines: list[dict[str, Any]] = Field(default_factory=list)

    @classmethod
    def empty(cls, session_meta: dict[str, Any] | None = None) -> ResumeTrace:
        """Empty but schema-valid trace for the WU-00 assembler stub."""

        meta_kwargs = dict(session_meta or {})
        meta_kwargs.setdefault("constants", trace_constants())
        return cls(meta=TraceMeta.model_validate(meta_kwargs))
