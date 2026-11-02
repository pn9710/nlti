import hashlib
import re
import secrets
import smtplib
from datetime import UTC, date, datetime, timedelta
from email.message import EmailMessage
from pathlib import Path
from typing import Literal
from urllib.parse import urlencode, urlparse

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from nlti.agents.graph import matching_graph
from nlti.auth import (
    create_access_token,
    get_current_account,
    hash_password,
    require_admin,
    verify_password,
)
from nlti.config import settings
from nlti.database import get_db
from nlti.models import (
    Account,
    AccountVerificationToken,
    Contractor,
    ContractorNotification,
    Geography,
    MatchRecord,
    ProcurementSource,
    PublicDocument,
    SourceRun,
    Tender,
    TenderRevision,
    VerifiedOutcome,
)
from nlti.schemas import (
    AccountOut,
    ContractorCreate,
    ContractorNotificationOut,
    ContractorOut,
    ContractorProfilePatch,
    DashboardSummary,
    DocumentReviewRequest,
    GeographyOut,
    HistoricalCoverage,
    LoginRequest,
    MatchOut,
    NotificationPreferences,
    ProcurementSourceCreate,
    ProcurementSourceOut,
    PublicDocumentOut,
    RegistrationRequest,
    SourceCheckRequest,
    SourceIngestRequest,
    SourceRunOut,
    TenderCreate,
    TenderOut,
    TenderPatch,
    TenderRevisionOut,
    TokenOut,
    VerificationRequestOut,
    VerifiedOutcomeCreate,
    VerifiedOutcomeOut,
    VerifyEmailRequest,
)

app = FastAPI(
    title="NLTI API",
    description=(
        "Newfoundland and Labrador Tender Intelligence. Public tender data is "
        "source-attributed; matching is a screening aid, not an eligibility decision."
    ),
    version="0.2.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/", include_in_schema=False)
def home():
    return {"service": "NLTI API", "docs": "/docs", "health": "/health"}


@app.get("/health", tags=["system"])
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "service": "NLTI API", "version": "0.2.0"}


@app.get("/summary", response_model=DashboardSummary, tags=["system"])
def dashboard_summary(db: Session = Depends(get_db)):
    today = date.today()
    upcoming = db.scalar(
        select(func.count(Tender.id)).where(
            Tender.is_active.is_(True),
            Tender.is_demo.is_(False),
            Tender.status.in_(("planned", "open")),
            Tender.closing_date >= today,
        )
    ) or 0
    historical = db.scalar(
        select(func.count(Tender.id)).where(
            Tender.is_active.is_(True),
            Tender.is_demo.is_(False),
            or_(
                Tender.closing_date < today,
                Tender.status.in_(("closed", "awarded", "cancelled")),
            ),
        )
    ) or 0
    reviewed_sources = db.scalar(
        select(func.count()).select_from(ProcurementSource).where(
            ProcurementSource.is_active.is_(True),
            ProcurementSource.terms_reviewed_at.is_not(None),
            ProcurementSource.permitted_reuse.is_(True),
        )
    ) or 0
    verified_outcomes = db.scalar(
        select(func.count(VerifiedOutcome.id))
        .join(Tender, VerifiedOutcome.tender_id == Tender.id)
        .where(Tender.is_active.is_(True), Tender.is_demo.is_(False))
    ) or 0
    return DashboardSummary(
        upcoming_tenders=upcoming,
        historical_tenders=historical,
        reviewed_sources=reviewed_sources,
        verified_outcomes=verified_outcomes,
    )


def _tender_snapshot(tender: Tender) -> dict:
    snapshot = TenderOut.model_validate(tender).model_dump(mode="json")
    snapshot.update(
        {
            "is_active": tender.is_active,
            "archived_at": tender.archived_at.isoformat() if tender.archived_at else None,
            "updated_at": tender.updated_at.isoformat() if tender.updated_at else None,
        }
    )
    return snapshot


def _record_revision(
    db: Session,
    tender: Tender,
    account: Account | None,
    action: str,
    reason: str,
    before: dict | None = None,
) -> None:
    after = _tender_snapshot(tender)
    snapshot = {"after": after} if before is None else {"before": before, "after": after}
    db.add(
        TenderRevision(
            tender_id=tender.id,
            actor_account_id=account.id if account else None,
            action=action,
            reason=reason,
            snapshot=snapshot,
        )
    )


def _require_reviewed_source(source: ProcurementSource | None) -> ProcurementSource:
    if source is None:
        raise HTTPException(status_code=404, detail="Procurement source not found.")
    if not source.is_active or source.terms_reviewed_at is None or source.permitted_reuse is not True:
        raise HTTPException(
            status_code=409,
            detail="This workflow requires an active source with reviewed reuse permission.",
        )
    return source


@app.post("/auth/register", response_model=AccountOut, status_code=status.HTTP_201_CREATED, tags=["auth"])
def register(payload: RegistrationRequest, db: Session = Depends(get_db)):
    email = str(payload.email).strip().casefold()
    if db.scalar(select(Account.id).where(Account.email == email)):
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    contractor = Contractor(
        **payload.model_dump(exclude={"email", "password", "insurance_verified"}),
        insurance_verified=False,
    )
    db.add(contractor)
    db.flush()
    account = Account(
        email=email,
        password_hash=hash_password(payload.password),
        role="contractor",
        contractor_id=contractor.id,
    )
    db.add(account)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists.") from None
    db.refresh(account)
    return account


@app.post("/auth/verification", response_model=VerificationRequestOut, tags=["auth"])
def request_email_verification(
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    if account.email_verified_at is not None:
        return VerificationRequestOut(sent=False, expires_in=0)
    production = settings.nlti_env.casefold() == "production"
    if production and (not settings.smtp_host or not settings.smtp_sender):
        raise HTTPException(status_code=503, detail="Email verification delivery is not configured.")
    now = datetime.now(UTC)
    requests_in_last_hour = db.scalar(
        select(func.count(AccountVerificationToken.id)).where(
            AccountVerificationToken.account_id == account.id,
            AccountVerificationToken.created_at >= now - timedelta(hours=1),
        )
    ) or 0
    if requests_in_last_hour >= 3:
        raise HTTPException(status_code=429, detail="Too many verification emails. Try again later.")

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    row = AccountVerificationToken(
        account_id=account.id,
        token_hash=token_hash,
        created_at=now,
        expires_at=now + timedelta(minutes=30),
    )
    verification_url = f"{settings.public_app_url.rstrip('/')}?{urlencode({'verify': raw_token})}"
    if production:
        message = EmailMessage()
        message["Subject"] = "Verify your NLTI account"
        message["From"] = settings.smtp_sender
        message["To"] = account.email
        message.set_content(
            "Verify your NLTI account within 30 minutes using this link:\n\n"
            f"{verification_url}\n\nIf you did not request this, ignore this message."
        )
        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
                if settings.smtp_starttls:
                    smtp.starttls()
                if settings.smtp_username:
                    smtp.login(settings.smtp_username, settings.smtp_password or "")
                smtp.send_message(message)
        except (OSError, smtplib.SMTPException):
            raise HTTPException(status_code=503, detail="Verification email could not be sent.") from None

    db.add(row)
    db.commit()
    return VerificationRequestOut(
        sent=True,
        expires_in=1800,
        verification_url=None if production else verification_url,
    )


@app.post("/auth/verify-email", response_model=AccountOut, tags=["auth"])
def verify_email(payload: VerifyEmailRequest, db: Session = Depends(get_db)):
    token_hash = hashlib.sha256(payload.token.encode("utf-8")).hexdigest()
    row = db.scalar(
        select(AccountVerificationToken).where(
            AccountVerificationToken.token_hash == token_hash,
            AccountVerificationToken.used_at.is_(None),
        )
    )
    if row is None:
        raise HTTPException(status_code=400, detail="Verification token is invalid or has already been used.")
    expires_at = row.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    now = datetime.now(UTC)
    if expires_at <= now:
        raise HTTPException(status_code=400, detail="Verification token has expired.")
    account = db.get(Account, row.account_id)
    if account is None or not account.is_active:
        raise HTTPException(status_code=400, detail="Verification token is invalid.")
    row.used_at = now
    account.email_verified_at = now
    db.commit()
    db.refresh(account)
    return account


@app.post("/auth/token", response_model=TokenOut, tags=["auth"])
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    account = db.scalar(
        select(Account).where(Account.email == str(payload.email).strip().casefold())
    )
    if (
        account is None
        or not account.is_active
        or not verify_password(payload.password, account.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenOut(
        access_token=create_access_token(account),
        expires_in=settings.access_token_minutes * 60,
    )


@app.get("/auth/me", response_model=AccountOut, tags=["auth"])
def get_me(account: Account = Depends(get_current_account)):
    return account


def _require_verified_contractor(account: Account) -> None:
    if (
        account.role != "admin"
        and settings.nlti_env.casefold() == "production"
        and account.email_verified_at is None
    ):
        raise HTTPException(status_code=403, detail="Account verification is required for this feature.")


@app.post("/accounts/{account_id}/verify", response_model=AccountOut, tags=["auth"])
def verify_account(
    account_id: int,
    db: Session = Depends(get_db),
    _: Account = Depends(require_admin),
):
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found.")
    account.email_verified_at = datetime.now(UTC)
    db.commit()
    db.refresh(account)
    return account


@app.get("/accounts", response_model=list[AccountOut], tags=["auth"])
def list_accounts(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: Account = Depends(require_admin),
):
    return db.scalars(select(Account).order_by(Account.created_at.desc()).limit(limit)).all()


def _tender_query(
    *,
    q: str | None,
    region: str | None,
    trade: str | None,
    status_filter: str | None,
    include_demo: bool,
    bucket: str | None = None,
):
    query = select(Tender).where(Tender.is_active.is_(True))
    if not include_demo:
        query = query.where(Tender.is_demo.is_(False))
    if q:
        term = f"%{q.strip()}%"
        query = query.where(
            or_(Tender.title.ilike(term), Tender.description.ilike(term), Tender.location.ilike(term))
        )
    if region:
        query = query.where(
            or_(Tender.region.ilike(f"%{region.strip()}%"), Tender.location.ilike(f"%{region.strip()}%"))
        )
    if status_filter:
        query = query.where(Tender.status == status_filter)
    if bucket == "upcoming":
        query = query.where(
            Tender.status.in_(("planned", "open")),
            Tender.closing_date >= date.today(),
        )
    elif bucket == "historical":
        query = query.where(
            or_(
                Tender.closing_date < date.today(),
                Tender.status.in_(("closed", "awarded", "cancelled")),
            )
        )
    query = query.order_by(Tender.closing_date.asc().nullslast(), Tender.id.desc())
    return query, trade.strip().casefold() if trade and trade.strip() else None


def _list_tenders(
    db: Session,
    q: str | None,
    region: str | None,
    trade: str | None,
    status_filter: str | None,
    limit: int,
    offset: int,
    include_demo: bool = False,
    bucket: str | None = None,
):
    query, wanted_trade = _tender_query(
        q=q,
        region=region,
        trade=trade,
        status_filter=status_filter,
        include_demo=include_demo,
        bucket=bucket,
    )
    rows = db.scalars(query).all()
    if wanted_trade:
        rows = [
            row for row in rows
            if wanted_trade in {value.strip().casefold() for value in (row.trades or [])}
        ]
    return rows[offset : offset + limit]


def _tender_filters(
    q: str | None = Query(default=None, max_length=120),
    region: str | None = Query(default=None, max_length=120),
    trade: str | None = Query(default=None, max_length=80),
    status_filter: Literal["planned", "open", "closed", "awarded", "cancelled", "unknown"] | None = Query(
        default=None, alias="status"
    ),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    include_demo: bool = Query(default=False),
):
    return q, region, trade, status_filter, limit, offset, include_demo


@app.get("/tenders", response_model=list[TenderOut], tags=["tenders"])
def list_tenders(
    filters=Depends(_tender_filters),
    db: Session = Depends(get_db),
):
    return _list_tenders(db, *filters)


@app.get("/tenders/upcoming", response_model=list[TenderOut], tags=["tenders"])
def list_upcoming_tenders(
    filters=Depends(_tender_filters),
    db: Session = Depends(get_db),
):
    return _list_tenders(db, *filters, bucket="upcoming")


@app.get("/tenders/historical", response_model=list[TenderOut], tags=["tenders"])
def list_historical_tenders(
    filters=Depends(_tender_filters),
    db: Session = Depends(get_db),
):
    return _list_tenders(db, *filters, bucket="historical")


@app.post("/tenders", response_model=TenderOut, status_code=201, tags=["tenders"])
def create_tender(
    payload: TenderCreate,
    db: Session = Depends(get_db),
    account: Account = Depends(require_admin),
):
    values = payload.model_dump()
    if payload.source_url is not None:
        values["source_url"] = str(payload.source_url)
    if values["source_id"] is not None:
        source = db.get(ProcurementSource, values["source_id"])
        if source is None:
            raise HTTPException(status_code=404, detail="Procurement source not found.")
        if (
            not source.is_active
            or source.terms_reviewed_at is None
            or source.permitted_reuse is not True
        ):
            raise HTTPException(
                status_code=409,
                detail="Tender cannot use a source that has not been reviewed and approved.",
            )
        values["source_name"] = source.name
        values["source_url"] = source.official_url
    tender = Tender(**values)
    db.add(tender)
    try:
        db.flush()
        _record_revision(db, tender, account, "created", "Tender entered by an administrator.")
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Tender source reference already exists.") from None
    db.refresh(tender)
    return tender


@app.patch("/tenders/{tender_id}", response_model=TenderOut, tags=["tenders"])
def correct_tender(
    tender_id: int,
    payload: TenderPatch,
    reason: str = Query(min_length=3, max_length=500),
    db: Session = Depends(get_db),
    account: Account = Depends(require_admin),
):
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise HTTPException(status_code=404, detail="Tender not found.")
    before = _tender_snapshot(tender)
    values = payload.model_dump(exclude_unset=True)
    if "source_url" in values and values["source_url"] is not None:
        values["source_url"] = str(values["source_url"])
    for key, value in values.items():
        setattr(tender, key, value)
    tender.updated_at = datetime.now(UTC)
    _record_revision(db, tender, account, "corrected", reason, before)
    db.commit()
    db.refresh(tender)
    return tender


@app.post("/tenders/{tender_id}/archive", response_model=TenderOut, tags=["tenders"])
def archive_tender(
    tender_id: int,
    reason: str = Query(min_length=3, max_length=500),
    db: Session = Depends(get_db),
    account: Account = Depends(require_admin),
):
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise HTTPException(status_code=404, detail="Tender not found.")
    if not tender.is_active:
        return tender
    before = _tender_snapshot(tender)
    tender.is_active = False
    tender.archived_at = datetime.now(UTC)
    tender.updated_at = tender.archived_at
    _record_revision(db, tender, account, "archived", reason, before)
    db.commit()
    db.refresh(tender)
    return tender


@app.get("/tenders/{tender_id}/revisions", response_model=list[TenderRevisionOut], tags=["tenders"])
def list_tender_revisions(
    tender_id: int,
    db: Session = Depends(get_db),
    _: Account = Depends(require_admin),
):
    if db.get(Tender, tender_id) is None:
        raise HTTPException(status_code=404, detail="Tender not found.")
    return db.scalars(
        select(TenderRevision)
        .where(TenderRevision.tender_id == tender_id)
        .order_by(TenderRevision.created_at.desc(), TenderRevision.id.desc())
    ).all()


@app.get("/geographies", response_model=list[GeographyOut], tags=["geography"])
def list_geographies(db: Session = Depends(get_db)):
    return db.scalars(select(Geography).order_by(Geography.geography_type, Geography.name)).all()


@app.get("/sources", response_model=list[ProcurementSourceOut], tags=["sources"])
def list_sources(db: Session = Depends(get_db)):
    query = select(ProcurementSource).where(
        ProcurementSource.is_active.is_(True),
        ProcurementSource.terms_reviewed_at.is_not(None),
        ProcurementSource.permitted_reuse.is_(True),
    ).order_by(ProcurementSource.name)
    return db.scalars(query).all()


@app.post("/sources", response_model=ProcurementSourceOut, status_code=201, tags=["sources"])
def create_source(
    payload: ProcurementSourceCreate,
    db: Session = Depends(get_db),
    _: Account = Depends(require_admin),
):
    values = payload.model_dump()
    values["official_url"] = str(payload.official_url)
    if payload.terms_url is not None:
        values["terms_url"] = str(payload.terms_url)
    source = ProcurementSource(**values)
    db.add(source)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A source with this name already exists.") from None
    db.refresh(source)
    return source


@app.post("/sources/{source_id}/ingest", response_model=SourceRunOut, tags=["sources"])
def ingest_source_records(
    source_id: int,
    payload: SourceIngestRequest,
    db: Session = Depends(get_db),
    _: Account = Depends(require_admin),
):
    source = _require_reviewed_source(db.get(ProcurementSource, source_id))
    references = [row.source_reference for row in payload.records]
    if len(references) != len(set(references)):
        raise HTTPException(status_code=422, detail="A batch cannot contain duplicate source references.")
    if set(references).intersection(payload.archived_references):
        raise HTTPException(status_code=422, detail="A record cannot be both imported and archived.")

    created = updated = archived = 0
    try:
        for item in payload.records:
            values = item.model_dump()
            source_url = str(values.pop("source_url", None) or source.official_url)
            values.pop("source_id", None)
            values.pop("source_name", None)
            values["source_id"] = source.id
            values["source_name"] = source.name
            values["source_url"] = source_url
            values["is_demo"] = False
            values["is_active"] = True
            values["archived_at"] = None
            values["collected_at"] = payload.retrieved_at

            tender = db.scalar(
                select(Tender).where(Tender.source_reference == item.source_reference)
            )
            if tender is None:
                tender = Tender(**values)
                db.add(tender)
                db.flush()
                _record_revision(
                    db,
                    tender,
                    None,
                    "created",
                    f"Imported from reviewed source {source.name}.",
                )
                created += 1
                continue
            if tender.source_id != source.id:
                raise HTTPException(
                    status_code=409,
                    detail=f"Source reference {item.source_reference} is already assigned to another source.",
                )
            before = _tender_snapshot(tender)
            for key, value in values.items():
                setattr(tender, key, value)
            tender.updated_at = payload.retrieved_at
            db.flush()
            _record_revision(
                db,
                tender,
                None,
                "corrected",
                f"Updated from reviewed source {source.name}.",
                before,
            )
            updated += 1

        for reference in payload.archived_references:
            tender = db.scalar(
                select(Tender).where(
                    Tender.source_id == source.id,
                    Tender.source_reference == reference,
                    Tender.is_active.is_(True),
                )
            )
            if tender is None:
                continue
            before = _tender_snapshot(tender)
            tender.is_active = False
            tender.archived_at = payload.retrieved_at
            tender.updated_at = payload.retrieved_at
            _record_revision(
                db,
                tender,
                None,
                "archived",
                f"Explicitly archived by reviewed source {source.name}.",
                before,
            )
            archived += 1

        run = SourceRun(
            source_id=source.id,
            status="completed",
            access_method=source.access_method,
            started_at=payload.retrieved_at,
            completed_at=payload.retrieved_at,
            records_seen=len(payload.records),
            records_created=created,
            records_updated=updated,
            records_archived=archived,
        )
        source.last_checked_at = payload.retrieved_at
        source.health_status = "healthy"
        source.health_message = f"Last run processed {len(payload.records)} records."
        db.add(run)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Source batch conflicts with an existing record.") from None
    db.refresh(run)
    return run


@app.post("/sources/{source_id}/checks", response_model=SourceRunOut, tags=["sources"])
def record_source_check(
    source_id: int,
    payload: SourceCheckRequest,
    db: Session = Depends(get_db),
    _: Account = Depends(require_admin),
):
    source = db.get(ProcurementSource, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Procurement source not found.")
    run = SourceRun(
        source_id=source.id,
        status=payload.status,
        access_method=source.access_method,
        started_at=payload.checked_at,
        completed_at=payload.checked_at,
        error_summary=payload.message if payload.status == "failed" else None,
    )
    source.last_checked_at = payload.checked_at
    source.health_status = payload.status
    source.health_message = payload.message
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


@app.get("/sources/{source_id}/runs", response_model=list[SourceRunOut], tags=["sources"])
def list_source_runs(
    source_id: int,
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    _: Account = Depends(require_admin),
):
    if db.get(ProcurementSource, source_id) is None:
        raise HTTPException(status_code=404, detail="Procurement source not found.")
    return db.scalars(
        select(SourceRun)
        .where(SourceRun.source_id == source_id)
        .order_by(SourceRun.started_at.desc(), SourceRun.id.desc())
        .limit(limit)
    ).all()


@app.post("/tenders/{tender_id}/outcome", response_model=VerifiedOutcomeOut, tags=["history"])
def record_verified_outcome(
    tender_id: int,
    payload: VerifiedOutcomeCreate,
    db: Session = Depends(get_db),
    account: Account = Depends(require_admin),
):
    tender = db.get(Tender, tender_id)
    if tender is None or tender.is_demo:
        raise HTTPException(status_code=404, detail="Public tender not found.")
    if not (
        tender.status in {"closed", "awarded", "cancelled"}
        or (tender.closing_date is not None and tender.closing_date < date.today())
    ):
        raise HTTPException(status_code=409, detail="Only historical notices can have a verified outcome.")
    source = _require_reviewed_source(db.get(ProcurementSource, payload.source_id))
    if db.scalar(select(VerifiedOutcome.id).where(VerifiedOutcome.tender_id == tender.id)):
        raise HTTPException(status_code=409, detail="This tender already has a verified outcome.")
    outcome = VerifiedOutcome(
        tender_id=tender.id,
        source_id=source.id,
        outcome=payload.outcome,
        published_at=payload.published_at,
        source_url=str(payload.source_url),
        source_reference=payload.source_reference,
        verification_method=payload.verification_method,
        verified_by_account_id=account.id,
    )
    db.add(outcome)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Outcome reference already exists for this source.") from None
    db.refresh(outcome)
    return VerifiedOutcomeOut(
        **{
            name: getattr(outcome, name)
            for name in (
                "id",
                "tender_id",
                "source_id",
                "outcome",
                "published_at",
                "source_url",
                "source_reference",
                "verification_method",
                "verified_at",
            )
        },
        tender_title=tender.title,
        source_name=source.name,
    )


@app.get("/outcomes", response_model=list[VerifiedOutcomeOut], tags=["history"])
def list_verified_outcomes(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        select(VerifiedOutcome, Tender.title, ProcurementSource.name)
        .join(Tender, VerifiedOutcome.tender_id == Tender.id)
        .join(ProcurementSource, VerifiedOutcome.source_id == ProcurementSource.id)
        .where(
            Tender.is_active.is_(True),
            Tender.is_demo.is_(False),
            ProcurementSource.is_active.is_(True),
            ProcurementSource.terms_reviewed_at.is_not(None),
            ProcurementSource.permitted_reuse.is_(True),
        )
        .order_by(VerifiedOutcome.published_at.desc().nullslast(), VerifiedOutcome.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return [
        VerifiedOutcomeOut(
            id=outcome.id,
            tender_id=outcome.tender_id,
            source_id=outcome.source_id,
            outcome=outcome.outcome,
            published_at=outcome.published_at,
            source_url=outcome.source_url,
            source_reference=outcome.source_reference,
            verification_method=outcome.verification_method,
            verified_at=outcome.verified_at,
            tender_title=tender_title,
            source_name=source_name,
        )
        for outcome, tender_title, source_name in rows
    ]


@app.get("/history/coverage", response_model=HistoricalCoverage, tags=["history"])
def historical_coverage(db: Session = Depends(get_db)):
    historical_filter = or_(
        Tender.closing_date < date.today(),
        Tender.status.in_(("closed", "awarded", "cancelled")),
    )
    eligible = db.scalar(
        select(func.count(Tender.id)).where(
            Tender.is_active.is_(True), Tender.is_demo.is_(False), historical_filter
        )
    ) or 0
    verified = db.scalar(
        select(func.count(VerifiedOutcome.id))
        .join(Tender, VerifiedOutcome.tender_id == Tender.id)
        .where(Tender.is_active.is_(True), Tender.is_demo.is_(False), historical_filter)
    ) or 0
    return HistoricalCoverage(
        eligible_historical_notices=eligible,
        verified_outcomes=verified,
        missing_outcomes=max(eligible - verified, 0),
        coverage_percent=round(verified * 100 / eligible, 1) if eligible else None,
        methodology=(
            "Denominator is active, non-demo notices with a past closing date or closed, awarded, "
            "or cancelled status. Outcomes count only when an administrator records independent "
            "public-source verification. This is coverage, not a complete-market estimate."
        ),
    )


def _extract_labeled_notice_fields(text_content: str) -> tuple[dict, dict]:
    proposed: dict = {}
    confidence: dict = {}
    labels = {
        "title": r"(?:notice|tender|project)?\s*title",
        "location": r"(?:project\s+)?location",
        "region": r"region",
        "source_reference": r"(?:reference|solicitation|tender)\s+(?:number|no\.?|id)",
    }
    for field, label in labels.items():
        match = re.search(rf"^\s*{label}\s*:\s*(\S.*)$", text_content, re.IGNORECASE | re.MULTILINE)
        if match:
            proposed[field] = match.group(1).strip()[:300]
            confidence[field] = 0.9
    closing = re.search(
        r"(?:closing date|submission deadline|tender closes)\s*:\s*(\d{4}-\d{2}-\d{2})",
        text_content,
        re.IGNORECASE,
    )
    if closing:
        try:
            proposed["closing_date"] = date.fromisoformat(closing.group(1)).isoformat()
            confidence["closing_date"] = 0.95
        except ValueError:
            pass
    return proposed, confidence


@app.post("/documents", response_model=PublicDocumentOut, status_code=201, tags=["documents"])
async def upload_public_document(
    source_id: int = Form(),
    source_url: str = Form(),
    document: UploadFile = File(),
    db: Session = Depends(get_db),
    _: Account = Depends(require_admin),
):
    source = _require_reviewed_source(db.get(ProcurementSource, source_id))
    parsed_url = urlparse(source_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise HTTPException(status_code=422, detail="A valid official document URL is required.")
    file_name = Path(document.filename or "public-document").name
    suffix = Path(file_name).suffix.lower()
    content_type = (document.content_type or "").split(";")[0].lower()
    if not (suffix == ".pdf" or content_type == "application/pdf") and not (
        suffix == ".txt" or content_type == "text/plain"
    ):
        raise HTTPException(status_code=415, detail="Only PDF and plain-text public documents are accepted.")
    file_bytes = await document.read(10 * 1024 * 1024 + 1)
    if not file_bytes or len(file_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Documents must be between 1 byte and 10 MB.")
    digest = hashlib.sha256(file_bytes).hexdigest()
    duplicate = db.scalar(
        select(PublicDocument).where(
            PublicDocument.source_id == source.id,
            PublicDocument.sha256 == digest,
        )
    )
    if duplicate is not None:
        raise HTTPException(status_code=409, detail=f"This document is already queued as record {duplicate.id}.")

    if suffix == ".pdf" or content_type == "application/pdf":
        try:
            import fitz

            with fitz.open(stream=file_bytes, filetype="pdf") as pdf:
                extracted_text = "\n".join(page.get_text() for page in pdf)[:500_000]
        except (fitz.FileDataError, RuntimeError, ValueError):
            raise HTTPException(status_code=422, detail="The uploaded PDF could not be read.") from None
    else:
        try:
            extracted_text = file_bytes.decode("utf-8")[:500_000]
        except UnicodeDecodeError:
            raise HTTPException(status_code=422, detail="Plain-text documents must use UTF-8 encoding.") from None

    proposed, confidence = _extract_labeled_notice_fields(extracted_text)
    storage_root = Path(settings.document_store_path).resolve()
    storage_root.mkdir(parents=True, exist_ok=True)
    stored_path = storage_root / f"{digest}{suffix or '.pdf'}"
    stored_path.write_bytes(file_bytes)
    row = PublicDocument(
        source_id=source.id,
        source_url=source_url,
        file_name=file_name,
        content_type="application/pdf" if suffix == ".pdf" or content_type == "application/pdf" else "text/plain",
        sha256=digest,
        storage_path=str(stored_path),
        status="needs_review",
        extracted_text=extracted_text,
        proposed_fields=proposed,
        field_confidence=confidence,
        extractor_name="nlti-labeled-field-extractor",
        extractor_version="1.0",
        prompt_version="not-used",
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="This document is already queued.") from None
    db.refresh(row)
    return row


@app.get("/documents", response_model=list[PublicDocumentOut], tags=["documents"])
def list_public_documents(
    status_filter: Literal["needs_review", "approved", "rejected"] | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    _: Account = Depends(require_admin),
):
    query = select(PublicDocument).order_by(PublicDocument.collected_at.desc())
    if status_filter:
        query = query.where(PublicDocument.status == status_filter)
    return db.scalars(query.limit(100)).all()


@app.get("/documents/{document_id}/file", tags=["documents"])
def get_public_document_file(
    document_id: int,
    db: Session = Depends(get_db),
    _: Account = Depends(require_admin),
):
    row = db.get(PublicDocument, document_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    storage_root = Path(settings.document_store_path).resolve()
    file_path = Path(row.storage_path).resolve()
    if file_path.parent != storage_root or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Stored document is unavailable.")
    return FileResponse(file_path, media_type=row.content_type, filename=row.file_name)


@app.post("/documents/{document_id}/review", response_model=PublicDocumentOut, tags=["documents"])
def review_public_document(
    document_id: int,
    payload: DocumentReviewRequest,
    db: Session = Depends(get_db),
    account: Account = Depends(require_admin),
):
    row = db.get(PublicDocument, document_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    if row.status != "needs_review":
        raise HTTPException(status_code=409, detail="Only documents awaiting review can be decided.")
    row.review_note = payload.reason
    row.reviewed_by_account_id = account.id
    row.reviewed_at = datetime.now(UTC)
    if payload.decision == "reject":
        if payload.tender is not None:
            raise HTTPException(status_code=422, detail="Rejected documents cannot create a tender.")
        row.status = "rejected"
        db.commit()
        db.refresh(row)
        return row
    if payload.tender is None:
        raise HTTPException(status_code=422, detail="Approval requires reviewed tender fields.")

    source = _require_reviewed_source(db.get(ProcurementSource, row.source_id))
    values = payload.tender.model_dump()
    values["source_id"] = source.id
    values["source_name"] = source.name
    values["source_url"] = row.source_url
    values["is_demo"] = False
    tender = Tender(**values)
    db.add(tender)
    try:
        db.flush()
        _record_revision(db, tender, account, "created", f"Approved from public document {row.sha256}.")
        row.status = "approved"
        row.tender_id = tender.id
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="The reviewed tender conflicts with an existing source reference.") from None
    db.refresh(row)
    return row


@app.get("/contractors", response_model=list[ContractorOut], tags=["contractors"])
def list_contractors(
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    if account.role == "admin":
        return db.scalars(select(Contractor).order_by(Contractor.company_name)).all()
    if account.contractor is None:
        return []
    return [account.contractor]


@app.get("/contractors/me", response_model=ContractorOut, tags=["contractors"])
def get_my_contractor(account: Account = Depends(get_current_account)):
    if account.contractor is None:
        raise HTTPException(status_code=404, detail="Contractor profile not found.")
    return account.contractor


@app.patch("/contractors/me", response_model=ContractorOut, tags=["contractors"])
def update_my_contractor(
    payload: ContractorProfilePatch,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    if account.contractor is None:
        raise HTTPException(status_code=404, detail="Contractor profile not found.")
    values = payload.model_dump(exclude_unset=True, exclude_none=True)
    for key, value in values.items():
        setattr(account.contractor, key, value)
    db.commit()
    db.refresh(account.contractor)
    return account.contractor


@app.get("/contractors/me/notifications", response_model=NotificationPreferences, tags=["notifications"])
def get_notification_preferences(account: Account = Depends(get_current_account)):
    if account.contractor is None:
        raise HTTPException(status_code=404, detail="Contractor profile not found.")
    return NotificationPreferences(
        enabled=account.contractor.notify_matches,
        minimum_match_score=account.contractor.minimum_match_score,
    )


@app.put("/contractors/me/notifications", response_model=NotificationPreferences, tags=["notifications"])
def update_notification_preferences(
    payload: NotificationPreferences,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    if account.contractor is None:
        raise HTTPException(status_code=404, detail="Contractor profile not found.")
    account.contractor.notify_matches = payload.enabled
    account.contractor.minimum_match_score = payload.minimum_match_score
    db.commit()
    return payload


@app.get("/notifications", response_model=list[ContractorNotificationOut], tags=["notifications"])
def list_my_notifications(
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    _require_verified_contractor(account)
    if account.contractor is None:
        return []
    rows = db.execute(
        select(ContractorNotification, Tender.title)
        .join(Tender, ContractorNotification.tender_id == Tender.id)
        .where(ContractorNotification.contractor_id == account.contractor_id)
        .order_by(ContractorNotification.created_at.desc())
        .limit(100)
    ).all()
    return [
        ContractorNotificationOut(
            id=notification.id,
            tender_id=notification.tender_id,
            score=notification.score,
            created_at=notification.created_at,
            read_at=notification.read_at,
            tender_title=title,
        )
        for notification, title in rows
    ]


@app.post("/notifications/{notification_id}/read", response_model=ContractorNotificationOut, tags=["notifications"])
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    notification = db.get(ContractorNotification, notification_id)
    if notification is None or notification.contractor_id != account.contractor_id:
        raise HTTPException(status_code=404, detail="Notification not found.")
    _require_verified_contractor(account)
    notification.read_at = datetime.now(UTC)
    db.commit()
    return ContractorNotificationOut(
        id=notification.id,
        tender_id=notification.tender_id,
        score=notification.score,
        created_at=notification.created_at,
        read_at=notification.read_at,
        tender_title=notification.tender.title,
    )


@app.post("/contractors", response_model=ContractorOut, status_code=201, tags=["contractors"])
def create_contractor(
    payload: ContractorCreate,
    db: Session = Depends(get_db),
    _: Account = Depends(require_admin),
):
    contractor = Contractor(**payload.model_dump())
    db.add(contractor)
    db.commit()
    db.refresh(contractor)
    return contractor


@app.post("/matches/{contractor_id}", response_model=list[MatchOut], tags=["matching"])
def match_contractor(
    contractor_id: int,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    if account.role != "admin" and account.contractor_id != contractor_id:
        raise HTTPException(status_code=403, detail="Contractors may only view their own matches.")
    _require_verified_contractor(account)
    contractor = db.get(Contractor, contractor_id)
    if contractor is None:
        raise HTTPException(status_code=404, detail="Contractor not found.")
    tenders = db.scalars(
        select(Tender).where(
            Tender.is_active.is_(True),
            Tender.is_demo.is_(False),
            Tender.status.in_(("planned", "open")),
            Tender.closing_date >= date.today(),
        )
    ).all()
    output = matching_graph.invoke({"contractor": contractor, "tenders": tenders})
    for item in output["results"]:
        match = MatchRecord(
            contractor_id=contractor.id,
            tender_id=item["tender_id"],
            score=item["score"],
            explanation=item["explanation"],
            flags=item["flags"],
        )
        db.add(match)
        db.flush()
        if contractor.notify_matches and item["score"] >= contractor.minimum_match_score:
            existing_notification = db.scalar(
                select(ContractorNotification.id).where(
                    ContractorNotification.contractor_id == contractor.id,
                    ContractorNotification.tender_id == item["tender_id"],
                )
            )
            if existing_notification is None:
                db.add(
                    ContractorNotification(
                        contractor_id=contractor.id,
                        tender_id=item["tender_id"],
                        match_record_id=match.id,
                        score=item["score"],
                    )
                )
    db.commit()
    return output["results"]
