import argparse
from datetime import date

from sqlalchemy import select

from nlti.database import SessionLocal
from nlti.models import Contractor, Geography, Tender

REGION_BUCKETS = [
    ("NL-AVALON", "Avalon Peninsula"),
    ("NL-BURIN", "Burin Peninsula"),
    ("NL-CENTRAL", "Central Newfoundland"),
    ("NL-WESTERN", "Western Newfoundland"),
    ("NL-LABRADOR", "Labrador"),
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
    parser = argparse.ArgumentParser(description="Seed reference geography or explicitly marked demo data.")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Also insert a fictional contractor and tender for local testing.",
    )
    args = parser.parse_args()
    seed_reference_geography()
    if args.demo:
        seed_demo_records()


if __name__ == "__main__":
    main()
