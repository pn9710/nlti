import argparse
from datetime import date

from sqlalchemy import select

from nlti.database import SessionLocal
from nlti.models import Contractor, Geography, ProcurementSource, Tender

REGION_BUCKETS = [
    ("NL-AVALON", "Avalon Peninsula"),
    ("NL-BURIN", "Burin Peninsula"),
    ("NL-CENTRAL", "Central Newfoundland"),
    ("NL-WESTERN", "Western Newfoundland"),
    ("NL-LABRADOR", "Labrador"),
]

# Starter catalog for public tender sources. These are intentionally left inactive and
# require a user to review official terms, licensing, and rate limits before activation.
SOURCE_CATALOG = [
    {
        "name": "MERX",
        "owner": "Public Services and Procurement Canada",
        "official_url": "https://www.merx.com",
        "access_method": "manual",
        "update_frequency": "daily",
        "terms_url": "https://www.merx.com",
        "rate_limit_notes": "Review MERX terms, robots.txt, and any API or download conditions before activation.",
    },
    {
        "name": "CanadaBuys",
        "owner": "Government of Canada",
        "official_url": "https://canadabuys.canada.ca",
        "access_method": "manual",
        "update_frequency": "daily",
        "terms_url": "https://canadabuys.canada.ca",
        "rate_limit_notes": "Confirm official procurement and reuse terms before automation or bulk ingestion.",
    },
    {
        "name": "Government of Newfoundland and Labrador procurement",
        "owner": "Government of Newfoundland and Labrador",
        "official_url": "https://www.gov.nl.ca",
        "access_method": "manual",
        "update_frequency": "weekly",
        "terms_url": "https://www.gov.nl.ca",
        "rate_limit_notes": "Confirm the exact tender portal and any government reuse restrictions before activation.",
    },
    {
        "name": "City of St. John's tenders",
        "owner": "City of St. John's",
        "official_url": "https://www.stjohns.ca",
        "access_method": "manual",
        "update_frequency": "weekly",
        "terms_url": "https://www.stjohns.ca",
        "rate_limit_notes": "Review municipal procurement pages and any rate limits or crawl restrictions first.",
    },
    {
        "name": "Town of Corner Brook tenders",
        "owner": "Town of Corner Brook",
        "official_url": "https://www.cornerbrook.com",
        "access_method": "manual",
        "update_frequency": "weekly",
        "terms_url": "https://www.cornerbrook.com",
        "rate_limit_notes": "Review local procurement notices and access conditions before activation.",
    },
    {
        "name": "Town of Grand Falls-Windsor tenders",
        "owner": "Town of Grand Falls-Windsor",
        "official_url": "https://www.grandfallswindsor.com",
        "access_method": "manual",
        "update_frequency": "weekly",
        "terms_url": "https://www.grandfallswindsor.com",
        "rate_limit_notes": "Confirm the exact sourcing pages and any site-specific terms before automation.",
    },
    {
        "name": "Town of Happy Valley-Goose Bay tenders",
        "owner": "Town of Happy Valley-Goose Bay",
        "official_url": "https://www.happyvalley-goosebay.com",
        "access_method": "manual",
        "update_frequency": "weekly",
        "terms_url": "https://www.happyvalley-goosebay.com",
        "rate_limit_notes": "Verify the procurement listing page and local terms before activation.",
    },
    {
        "name": "Town of Labrador City tenders",
        "owner": "Town of Labrador City",
        "official_url": "https://www.labradorcity.ca",
        "access_method": "manual",
        "update_frequency": "weekly",
        "terms_url": "https://www.labradorcity.ca",
        "rate_limit_notes": "Review the official tender page and any crawl or reuse restrictions before using it.",
    },
]


def seed_reference_geography() -> None:
    with SessionLocal() as db:
        province = db.scalar(select(Geography).where(Geography.code == "NL"))
        if province is None:
            province = Geography(
                code="NL",
                name="Newfoundland and Labrador",
                geography_type="province",
                boundary_status="not_loaded",
            )
            db.add(province)
            db.flush()
        for code, name in REGION_BUCKETS:
            exists = db.scalar(select(Geography.id).where(Geography.code == code))
            if exists is None:
                db.add(
                    Geography(
                        code=code,
                        name=name,
                        geography_type="region",
                        parent_id=province.id,
                        boundary_status="not_loaded",
                    )
                )
        db.commit()
    print("Regional filter labels are ready; authoritative boundary geometry is not loaded.")


def seed_known_sources() -> None:
    """Seed a starter procurement-source catalog for user review. These entries are not active."""
    with SessionLocal() as db:
        for source in SOURCE_CATALOG:
            already_exists = db.scalar(
                select(ProcurementSource.id).where(ProcurementSource.name == source["name"])
            )
            if already_exists is not None:
                continue
            db.add(
                ProcurementSource(
                    name=source["name"],
                    owner=source["owner"],
                    official_url=source["official_url"],
                    access_method=source.get("access_method", "manual"),
                    update_frequency=source.get("update_frequency"),
                    terms_url=source.get("terms_url"),
                    terms_reviewed_at=None,
                    permitted_reuse=None,
                    rate_limit_notes=source.get("rate_limit_notes"),
                    is_active=False,
                    health_status="unconfigured",
                    health_message="Not yet reviewed. User discretion required before activation.",
                )
            )
        db.commit()
    print(
        "Seeded starter procurement sources for user review; they remain inactive until manually reviewed and enabled."
    )


def seed_demo_records() -> None:
    with SessionLocal() as db:
        if db.scalar(select(Tender.id).where(Tender.source_reference == "NLTI-DEMO-001")):
            print("Demo record already exists; no changes made.")
            return
        contractor = Contractor(
            company_name="DEMO — Labrador Building Services",
            trades=["roofing", "carpentry"],
            regions=["Labrador", "Happy Valley-Goose Bay"],
            crew_capacity=6,
            equipment=["scaffolding", "service truck"],
            certifications=[],
            insurance_verified=False,
        )
        tender = Tender(
            title="DEMO ONLY — Commercial roof replacement",
            description="Fictional example record for testing the matching workflow.",
            location="Happy Valley-Goose Bay",
            region="Labrador",
            trades=["roofing"],
            closing_date=date(2099, 1, 15),
            status="open",
            bid_security_required=True,
            mandatory_requirements=[],
            source_name="NLTI demonstration data — not a real procurement notice",
            source_reference="NLTI-DEMO-001",
            is_demo=True,
        )
        db.add_all([contractor, tender])
        db.commit()
    print("Inserted one fictional demo contractor and tender; these are hidden unless include_demo=true.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed reference geography, starter source catalog, or explicitly marked demo data.")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Also insert a fictional contractor and tender for local testing.",
    )
    args = parser.parse_args()
    seed_reference_geography()
    seed_known_sources()
    if args.demo:
        seed_demo_records()


if __name__ == "__main__":
    main()
