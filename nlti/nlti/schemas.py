from datetime import date, datetime

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, EmailStr, Field, model_validator


class ContractorFields(BaseModel):
    company_name: str = Field(min_length=2, max_length=200)
    trades: list[str] = Field(default_factory=list)
    regions: list[str] = Field(default_factory=list)
    crew_capacity: int | None = Field(default=None, ge=0)
    equipment: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    insurance_verified: bool = False


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
    model_config = ConfigDict(from_attributes=True)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


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


class ProcurementSourceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    owner: str = Field(min_length=2, max_length=200)
    official_url: AnyHttpUrl
    access_method: str = Field(default="manual", pattern="^(manual|api|feed|download)$")
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
        ):
            raise ValueError(
                "Active sources require a reviewed terms URL and explicit permission to reuse."
            )
        return self


class ProcurementSourceOut(ProcurementSourceCreate):
    id: int
    created_at: datetime
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


class MatchOut(BaseModel):
    tender_id: int
    tender_title: str
    score: float
    explanation: list[str]
    flags: list[str]
