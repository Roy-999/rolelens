from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EducationEntry(BaseModel):
    degree: str = ""
    institution: str = ""
    graduation_year: str = ""


class ExperienceEntry(BaseModel):
    company: str = ""
    title: str = ""
    start_date: str = ""
    end_date: str = ""
    summary: str = ""


class LocationEntry(BaseModel):
    address_line_1: str = ""
    address_line_2: str = ""
    city: str = ""
    state: str = ""
    Country: str = ""
    zip_code: str = ""


class JobLocationEntry(BaseModel):
    address_line_1: str | None = None
    address_line_2: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    zip_code: str | None = None


class AgeEntry(BaseModel):
    group: str = ""
    source: str = ""
    confidence: float | None = None


class CandidateExtraction(BaseModel):
    name: str = ""
    email_id: str = ""
    phone_no: str = ""
    location: LocationEntry = Field(default_factory=LocationEntry)
    years_of_experience: float | None = None
    age: AgeEntry = Field(default_factory=AgeEntry)
    visits: int = 0
    last_login_days: int = 0
    applications_count: int = 0
    profile_updates: int = 0
    activity_score: float | None = None
    activity_label: str | None = None
    education: list[EducationEntry] = Field(default_factory=list)
    experience: list[ExperienceEntry] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    licenses: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)


class ExtractedCandidateResponse(BaseModel):
    warnings: list[str] = Field(default_factory=list)
    file_name: str
    file_type: str
    raw_text: str = ""
    preview_text: str = ""
    extraction_method: str
    is_scanned_document: bool = False
    extracted_fields: CandidateExtraction


class CandidateSubmission(BaseModel):
    source_file_name: str
    source_file_type: str
    raw_text: str = ""
    preview_text: str = ""
    extraction_method: str
    is_scanned_document: bool = False
    extracted_fields: CandidateExtraction


class CandidateSubmissionResponse(BaseModel):
    id: str
    candidate_id: str
    profile_context: str
    embedding_created: bool


class MatchResult(BaseModel):
    resume_id: str
    candidate_id: str = ""
    name: str
    email_id: str = ""
    phone_no: str = ""
    location: LocationEntry = Field(default_factory=LocationEntry)
    years_of_experience: float | None = None
    age: AgeEntry = Field(default_factory=AgeEntry)
    skills: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    licenses: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    experience: list[ExperienceEntry] = Field(default_factory=list)
    profile_context: str = ""
    keyword_score: float = 0.0
    vector_score: float = 0.0
    skill_recency_score: float = 0.0
    rrf_score: float = 0.0
    matched_terms: list[str] = Field(default_factory=list)
    source: str = ""
    activity_label: str = ""
    activity_score: float | None = None


class MatchResponse(BaseModel):
    matching_mode: str = "keyword"
    warnings: list[str] = Field(default_factory=list)
    job_order: str
    requested_limit: int
    available_candidates: int
    candidates: list[MatchResult] = Field(default_factory=list)


class CandidateStatsResponse(BaseModel):
    total_candidates: int
    location_hierarchy: dict[str, dict[str, list[str]]] = Field(default_factory=dict)


class CandidateRecord(CandidateExtraction):
    id: str
    candidate_id: str = ""
    profile_completion_percentage: int = 0
    source_file_name: str = ""
    source_file_type: str = ""
    raw_text: str = ""
    preview_text: str = ""
    extraction_method: str = ""
    is_scanned_document: bool = False
    profile_context: str = ""
    created_at: str | None = None
    updated_at: str | None = None


class CandidateListResponse(BaseModel):
    candidates: list[CandidateRecord] = Field(default_factory=list)
    total_candidates: int


class JobPerDiemEntry(BaseModel):
    amount_per_day: float | None = None
    frequency: str | None = None
    conditions: str | None = None


class JobCompensationEntry(BaseModel):
    pay_rate_min: float | None = None
    pay_rate_max: float | None = None
    pay_frequency: str | None = None
    pay_text: str | None = None
    overtime: str | None = None
    per_diem: JobPerDiemEntry = Field(default_factory=JobPerDiemEntry)


class JobComplianceEntry(BaseModel):
    drug_test: bool | None = None
    background_check: bool | None = None
    work_authorization: str | None = "Unknown"


class JobOrderExtraction(BaseModel):
    job_title: str | None = None
    domain: str | None = None
    organization_name: str | None = None
    number_of_openings: int = Field(default=1, ge=1)
    location: JobLocationEntry = Field(default_factory=JobLocationEntry)
    work_arrangement: str | None = None
    employment_type: str | None = None
    hours_per_week: float | None = None
    hours_of_operation: str | None = None
    duration_weeks: float | None = None
    start_date: str | None = None
    end_date: str | None = None
    years_required: float | None = None
    will_sponsor: bool | None = None
    will_relocate: bool | None = None
    travel_required: bool | None = None
    compensation: JobCompensationEntry = Field(default_factory=JobCompensationEntry)
    summary: str | None = None
    responsibilities: list[str] = Field(default_factory=list)
    qualifications: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    benefits: list[str] = Field(default_factory=list)
    additional_details: list[str] = Field(default_factory=list)
    compliance: JobComplianceEntry = Field(default_factory=JobComplianceEntry)
    physical_requirements: list[str] = Field(default_factory=list)


class ExtractedJobOrderResponse(BaseModel):
    warnings: list[str] = Field(default_factory=list)
    file_name: str
    file_type: str
    raw_text: str = ""
    preview_text: str = ""
    extraction_method: str
    is_scanned_document: bool = False
    extracted_fields: JobOrderExtraction


class JobOrderSubmission(BaseModel):
    source_file_name: str
    source_file_type: str
    raw_text: str = ""
    preview_text: str = ""
    extraction_method: str
    is_scanned_document: bool = False
    extracted_fields: JobOrderExtraction


class JobOrderSubmissionResponse(BaseModel):
    id: str
    job_order_id: str


class EmailAttachmentRecord(BaseModel):
    file_name: str
    mime_type: str = ""
    size: int = 0
    attachment_id: str = ""
    content_hash: str = ""
    stored_path: str = ""
    extracted_text: str = ""
    selected_for_extraction: bool = False


class EmailDedupeResult(BaseModel):
    is_duplicate: bool = False
    reasons: list[str] = Field(default_factory=list)
    matched_job_order_id: str | None = None
    matched_draft_id: str | None = None


class EmailJobOrderDraftRecord(BaseModel):
    id: str
    gmail_message_id: str = ""
    gmail_thread_id: str = ""
    subject: str = ""
    sender: str = ""
    recipients: list[str] = Field(default_factory=list)
    received_at: str | None = None
    status: str = "pending_review"
    classification: str = ""
    confidence: float | None = None
    confidence_reason: str = ""
    source_priority: str = ""
    source_file_name: str = ""
    source_file_type: str = ""
    raw_text: str = ""
    preview_text: str = ""
    cleaned_body_text: str = ""
    extraction_method: str = ""
    extracted_fields: JobOrderExtraction = Field(default_factory=JobOrderExtraction)
    attachments: list[EmailAttachmentRecord] = Field(default_factory=list)
    dedupe: EmailDedupeResult = Field(default_factory=EmailDedupeResult)
    saved_job_order_id: str | None = None
    error: str = ""
    created_at: str | None = None
    updated_at: str | None = None


class EmailJobOrderDraftListResponse(BaseModel):
    drafts: list[EmailJobOrderDraftRecord] = Field(default_factory=list)
    total_drafts: int


class GmailStatusResponse(BaseModel):
    authorized: bool
    email: str = ""


class GmailMessageSummary(BaseModel):
    gmail_message_id: str
    gmail_thread_id: str = ""
    subject: str = ""
    sender: str = ""
    received_at: str | None = None
    snippet: str = ""


class GmailTestFetchResponse(BaseModel):
    messages: list[GmailMessageSummary] = Field(default_factory=list)
    total_messages: int


class GmailProcessLatestResponse(BaseModel):
    processed: int
    created: int
    duplicates: int
    irrelevant: int
    failed: int
    drafts: list[EmailJobOrderDraftRecord] = Field(default_factory=list)


class EmailDraftSaveRequest(BaseModel):
    extracted_fields: JobOrderExtraction


class EmailDraftSaveResponse(BaseModel):
    id: str
    job_order_id: str
    draft_id: str


class JobOrderRecord(JobOrderExtraction):
    id: str
    job_order_id: str = ""
    profile_completion_percentage: int = 0
    source_file_name: str = ""
    source_file_type: str = ""
    raw_text: str = ""
    preview_text: str = ""
    extraction_method: str = ""
    is_scanned_document: bool = False
    created_at: str | None = None
    updated_at: str | None = None


class JobOrderListResponse(BaseModel):
    jobs: list[JobOrderRecord] = Field(default_factory=list)
    total_jobs: int


class JobOrderStatsResponse(BaseModel):
    total_jobs: int
    location_hierarchy: dict[str, dict[str, list[str]]] = Field(default_factory=dict)
    domains: list[str] = Field(default_factory=list)


class JobSalaryResponse(BaseModel):
    salary_range: str


class ActivityPercentileResponse(BaseModel):
    candidate_id: str
    visits: int
    threshold: float
    method: str = "percentile"
    activity_label: str


class ActivityWeightedResponse(BaseModel):
    candidate_id: str
    activity_score: float
    cluster: int
    method: str = "weighted_clustering"
    activity_label: str


class HealthResponse(BaseModel):
    status: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
