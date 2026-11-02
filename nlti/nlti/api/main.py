from datetime import date
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
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
from nlti.models import Account, Contractor, Geography, MatchRecord, ProcurementSource, Tender
from nlti.schemas import (
    AccountOut,
    ContractorCreate,
    ContractorOut,
    DashboardSummary,
    GeographyOut,
    LoginRequest,
    MatchOut,
    ProcurementSourceCreate,
    ProcurementSourceOut,
    RegistrationRequest,
    TenderCreate,
    TenderOut,
    TokenOut,
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
    return DashboardSummary(
        upcoming_tenders=upcoming,
        historical_tenders=historical,
        reviewed_sources=reviewed_sources,
    )


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
    _: Account = Depends(require_admin),
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
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Tender source reference already exists.") from None
    db.refresh(tender)
    return tender


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
    contractor = db.get(Contractor, contractor_id)
    if contractor is None:
        raise HTTPException(status_code=404, detail="Contractor not found.")
    tenders = db.scalars(
        select(Tender).where(Tender.is_active.is_(True), Tender.is_demo.is_(False))
    ).all()
    output = matching_graph.invoke({"contractor": contractor, "tenders": tenders})
    for item in output["results"]:
        db.add(
            MatchRecord(
                contractor_id=contractor.id,
                tender_id=item["tender_id"],
                score=item["score"],
                explanation=item["explanation"],
                flags=item["flags"],
            )
        )
    db.commit()
    return output["results"]
