from datetime import date, datetime
from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, EmailStr, Field, model_validator


class ContractorFields(BaseModel):
    company_name: str = Field(min_length=2, max_length=200)
    trades: list[str] = Field(default_factory=list)
    regions: list[str] = Field(default_factory=list)
    crew_capacity: int | None = Field(default=None, ge=0)
    equipment: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    insurance_verified: bool = False


class ContractorProfilePatch(BaseModel):
    company_name: str | None = Field(default=None, min_length=2, max_length=200)
    trades: list[str] | None = None
    regions: list[str] | None = None
    crew_capacity: int | None = Field(default=None, ge=0)
    equipment: list[str] | None = None
    certifications: list[str] | None = None


class NotificationPreferences(BaseModel):
    enabled: bool
    minimum_match_score: float = Field(ge=0, le=100)


class ContractorCreate(ContractorFields):
    pass


class ContractorOut(ContractorFields):
    id: int
    model_config = ConfigDict(from_attributes=True)


class RegistrationRequest(ContractorFields):
    email: EmailStr
    password: str = Field(min_length=12, max_length=256)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class AccountOut(BaseModel):
    id: int
    email: EmailStr
    role: str
    contractor_id: int | None
    email_verified_at: datetime | None
    model_config = ConfigDict(from_attributes=True)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class VerificationRequestOut(BaseModel):
    sent: bool
    expires_in: int
    verification_url: str | None = None


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=32, max_length=256)


class GeographyOut(BaseModel):
    id: int
    code: str
    name: str
    geography_type: str
    parent_id: int | None
    boundary_status: str
    model_config = ConfigDict(from_attributes=True)


class DashboardSummary(BaseModel):
    upcoming_tenders: int
    historical_tenders: int
    reviewed_sources: int
    verified_outcomes: int = 0


class ProcurementSourceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    owner: str = Field(min_length=2, max_length=200)
    official_url: AnyHttpUrl
    access_method: str = Field(default="manual", pattern="^(manual|api|feed|download)$")
    update_frequency: str | None = Field(default=None, max_length=100)
    terms_url: AnyHttpUrl | None = None
    terms_reviewed_at: datetime | None = None
    permitted_reuse: bool | None = None
    rate_limit_notes: str | None = Field(default=None, max_length=500)
    is_active: bool = False

    @model_validator(mode="after")
    def active_sources_need_documented_permission(self):
        if self.is_active and (
            self.terms_url is None
            or self.terms_reviewed_at is None
            or self.permitted_reuse is not True
            or not self.update_frequency
            or not self.rate_limit_notes
        ):
            raise ValueError(
                "Active sources require reviewed terms, reuse permission, an update cadence, and access/rate-limit notes."
            )
        return self


class ProcurementSourceOut(ProcurementSourceCreate):
    id: int
    created_at: datetime
    last_checked_at: datetime | None
    health_status: str
    health_message: str | None
    model_config = ConfigDict(from_attributes=True)


class TenderCreate(BaseModel):
    title: str = Field(min_length=3, max_length=300)
    description: str = ""
    location: str = Field(min_length=1, max_length=200)
    region: str = Field(min_length=1, max_length=100)
    geography_id: int | None = None
    trades: list[str] = Field(default_factory=list)
    estimated_value: float | None = Field(default=None, ge=0)
    closing_date: date | None = None
    status: str = Field(
        default="open", pattern="^(planned|open|closed|awarded|cancelled|unknown)$"
    )
    bid_security_required: bool | None = None
    mandatory_requirements: list[str] = Field(default_factory=list)
    source_id: int | None = None
    source_name: str = "Manually entered"
    source_url: AnyHttpUrl | None = None
    source_reference: str | None = Field(default=None, max_length=200)
    is_demo: bool = False


class TenderOut(TenderCreate):
    id: int
    is_active: bool
    collected_at: datetime
    model_config = ConfigDict(from_attributes=True)


class TenderPatch(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=300)
    description: str | None = None
    location: str | None = Field(default=None, min_length=1, max_length=200)
    region: str | None = Field(default=None, min_length=1, max_length=100)
    trades: list[str] | None = None
    estimated_value: float | None = Field(default=None, ge=0)
    closing_date: date | None = None
    status: Literal["planned", "open", "closed", "awarded", "cancelled", "unknown"] | None = None
    bid_security_required: bool | None = None
    mandatory_requirements: list[str] | None = None
    source_url: AnyHttpUrl | None = None


class TenderImportItem(TenderCreate):
    source_reference: str = Field(min_length=1, max_length=200)


class SourceIngestRequest(BaseModel):
    retrieved_at: datetime
    records: list[TenderImportItem] = Field(max_length=500)
    archived_references: list[str] = Field(default_factory=list, max_length=500)


class SourceRunOut(BaseModel):
    id: int
    source_id: int
    status: str
    access_method: str
    started_at: datetime
    completed_at: datetime
    records_seen: int
    records_created: int
    records_updated: int
    records_archived: int
    error_summary: str | None
    model_config = ConfigDict(from_attributes=True)


class SourceCheckRequest(BaseModel):
    status: Literal["healthy", "warning", "failed"]
    checked_at: datetime
    message: str | None = Field(default=None, max_length=1000)


class TenderRevisionOut(BaseModel):
    id: int
    tender_id: int
    actor_account_id: int | None
    action: str
    reason: str
    snapshot: dict
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PublicDocumentOut(BaseModel):
    id: int
    source_id: int
    source_url: str
    file_name: str
    content_type: str
    sha256: str
    status: str
    proposed_fields: dict
    field_confidence: dict
    extractor_name: str | None
    extractor_version: str | None
    prompt_version: str | None
    review_note: str | None
    reviewed_at: datetime | None
    tender_id: int | None
    collected_at: datetime
    model_config = ConfigDict(from_attributes=True)


class DocumentReviewRequest(BaseModel):
    decision: Literal["approve", "reject"]
    reason: str = Field(min_length=3, max_length=1000)
    tender: TenderCreate | None = None


class VerifiedOutcomeCreate(BaseModel):
    source_id: int
    outcome: Literal["awarded", "cancelled", "no_award"]
    published_at: date | None = None
    source_url: AnyHttpUrl
    source_reference: str = Field(min_length=1, max_length=200)
    verification_method: str = Field(min_length=10, max_length=500)


class VerifiedOutcomeOut(BaseModel):
    id: int
    tender_id: int
    source_id: int
    outcome: str
    published_at: date | None
    source_url: str
    source_reference: str
    verification_method: str
    verified_at: datetime
    tender_title: str
    source_name: str
    model_config = ConfigDict(from_attributes=True)


class HistoricalCoverage(BaseModel):
    eligible_historical_notices: int
    verified_outcomes: int
    missing_outcomes: int
    coverage_percent: float | None
    methodology: str


class ContractorNotificationOut(BaseModel):
    id: int
    tender_id: int
    score: float
    created_at: datetime
    read_at: datetime | None
    tender_title: str


class MatchOut(BaseModel):
    tender_id: int
    tender_title: str
    score: float
    explanation: list[str]
    flags: list[str]
