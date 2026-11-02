from datetime import UTC, date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nlti.database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class BoundaryGeometry(TypeDecorator):
    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from geoalchemy2 import Geometry

            return dialect.type_descriptor(
                Geometry(geometry_type="MULTIPOLYGON", srid=4326, spatial_index=False)
            )
        return dialect.type_descriptor(JSON())


class Geography(Base):
    __tablename__ = "geographies"
    __table_args__ = (
        UniqueConstraint("parent_id", "name", name="uq_geographies_parent_name"),
        Index("ix_geographies_boundary", "boundary", postgresql_using="gist").ddl_if(
            dialect="postgresql"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    geography_type: Mapped[str] = mapped_column(String(32), index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("geographies.id"), nullable=True)
    boundary: Mapped[object | None] = mapped_column(BoundaryGeometry(), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    boundary_status: Mapped[str] = mapped_column(String(32), default="not_loaded")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    parent: Mapped["Geography | None"] = relationship(remote_side="Geography.id")


class ProcurementSource(Base):
    __tablename__ = "procurement_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    owner: Mapped[str] = mapped_column(String(200))
    official_url: Mapped[str] = mapped_column(String(1000))
    access_method: Mapped[str] = mapped_column(String(32), default="manual")
    update_frequency: Mapped[str | None] = mapped_column(String(100), nullable=True)
    terms_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    terms_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    permitted_reuse: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    rate_limit_notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    health_status: Mapped[str] = mapped_column(String(32), default="unconfigured")
    health_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    role: Mapped[str] = mapped_column(String(32), default="contractor")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    contractor_id: Mapped[int | None] = mapped_column(
        ForeignKey("contractors.id"), unique=True, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    contractor: Mapped["Contractor | None"] = relationship()


class AccountVerificationToken(Base):
    __tablename__ = "account_verification_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    account: Mapped[Account] = relationship()


class Contractor(Base):
    __tablename__ = "contractors"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_name: Mapped[str] = mapped_column(String(200), index=True)
    trades: Mapped[list[str]] = mapped_column(JSON, default=list)
    regions: Mapped[list[str]] = mapped_column(JSON, default=list)
    crew_capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    equipment: Mapped[list[str]] = mapped_column(JSON, default=list)
    certifications: Mapped[list[str]] = mapped_column(JSON, default=list)
    insurance_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    notify_matches: Mapped[bool] = mapped_column(Boolean, default=False)
    minimum_match_score: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Tender(Base):
    __tablename__ = "tenders"
    __table_args__ = (
        Index("ix_tenders_status_closing_date", "status", "closing_date"),
        Index("ix_tenders_geography_id", "geography_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(300), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    location: Mapped[str] = mapped_column(String(200), index=True)
    region: Mapped[str] = mapped_column(String(100), index=True)
    geography_id: Mapped[int | None] = mapped_column(
        ForeignKey("geographies.id"), nullable=True
    )
    trades: Mapped[list[str]] = mapped_column(JSON, default=list)
    estimated_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    closing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="open", index=True)
    bid_security_required: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    mandatory_requirements: Mapped[list[str]] = mapped_column(JSON, default=list)
    source_id: Mapped[int | None] = mapped_column(
        ForeignKey("procurement_sources.id"), nullable=True
    )
    source_name: Mapped[str] = mapped_column(String(200), default="Unverified source")
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    source_reference: Mapped[str | None] = mapped_column(String(200), unique=True, nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    geography: Mapped[Geography | None] = relationship()
    procurement_source: Mapped[ProcurementSource | None] = relationship()


class MatchRecord(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(primary_key=True)
    contractor_id: Mapped[int] = mapped_column(ForeignKey("contractors.id"), index=True)
    tender_id: Mapped[int] = mapped_column(ForeignKey("tenders.id"), index=True)
    score: Mapped[float] = mapped_column(Float)
    explanation: Mapped[list[str]] = mapped_column(JSON, default=list)
    flags: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    contractor: Mapped[Contractor] = relationship()
    tender: Mapped[Tender] = relationship()


class SourceRun(Base):
    __tablename__ = "source_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("procurement_sources.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="completed")
    access_method: Mapped[str] = mapped_column(String(32))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    records_seen: Mapped[int] = mapped_column(Integer, default=0)
    records_created: Mapped[int] = mapped_column(Integer, default=0)
    records_updated: Mapped[int] = mapped_column(Integer, default=0)
    records_archived: Mapped[int] = mapped_column(Integer, default=0)
    error_summary: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    source: Mapped[ProcurementSource] = relationship()


class TenderRevision(Base):
    __tablename__ = "tender_revisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    tender_id: Mapped[int] = mapped_column(ForeignKey("tenders.id", ondelete="CASCADE"), index=True)
    actor_account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str] = mapped_column(String(500))
    snapshot: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PublicDocument(Base):
    __tablename__ = "public_documents"
    __table_args__ = (
        UniqueConstraint("source_id", "sha256", name="uq_public_documents_source_sha256"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("procurement_sources.id"), index=True)
    source_url: Mapped[str] = mapped_column(String(1000))
    file_name: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    storage_path: Mapped[str] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    proposed_fields: Mapped[dict] = mapped_column(JSON, default=dict)
    field_confidence: Mapped[dict] = mapped_column(JSON, default=dict)
    extractor_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    extractor_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    review_note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    reviewed_by_account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tender_id: Mapped[int | None] = mapped_column(ForeignKey("tenders.id"), nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    source: Mapped[ProcurementSource] = relationship()
    tender: Mapped[Tender | None] = relationship()


class VerifiedOutcome(Base):
    __tablename__ = "verified_outcomes"
    __table_args__ = (
        UniqueConstraint("tender_id", name="uq_verified_outcomes_tender_id"),
        UniqueConstraint("source_id", "source_reference", name="uq_verified_outcomes_source_ref"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tender_id: Mapped[int] = mapped_column(ForeignKey("tenders.id"), index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("procurement_sources.id"))
    outcome: Mapped[str] = mapped_column(String(32))
    published_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_url: Mapped[str] = mapped_column(String(1000))
    source_reference: Mapped[str] = mapped_column(String(200))
    verification_method: Mapped[str] = mapped_column(String(500))
    verified_by_account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    tender: Mapped[Tender] = relationship()
    source: Mapped[ProcurementSource] = relationship()


class ContractorNotification(Base):
    __tablename__ = "contractor_notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    contractor_id: Mapped[int] = mapped_column(ForeignKey("contractors.id"), index=True)
    tender_id: Mapped[int] = mapped_column(ForeignKey("tenders.id"), index=True)
    match_record_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), unique=True)
    score: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    contractor: Mapped[Contractor] = relationship()
    tender: Mapped[Tender] = relationship()
