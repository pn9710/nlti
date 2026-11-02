"""Create the provincial intelligence foundation.

Revision ID: 0001_foundation
Revises:
"""
import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry

revision = "0001_foundation"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    is_postgresql = op.get_bind().dialect.name == "postgresql"
    if is_postgresql:
        op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    boundary_type = (
        Geometry(geometry_type="MULTIPOLYGON", srid=4326, spatial_index=False)
        if is_postgresql
        else sa.JSON()
    )
    op.create_table(
        "geographies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("geography_type", sa.String(length=32), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("boundary", boundary_type, nullable=True),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("boundary_status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["parent_id"], ["geographies.id"]),
        sa.UniqueConstraint("parent_id", "name", name="uq_geographies_parent_name"),
    )
    op.create_index("ix_geographies_code", "geographies", ["code"], unique=True)
    op.create_index("ix_geographies_geography_type", "geographies", ["geography_type"])
    op.create_index("ix_geographies_name", "geographies", ["name"])
    if is_postgresql:
        op.create_index(
            "ix_geographies_boundary",
            "geographies",
            ["boundary"],
            postgresql_using="gist",
        )

    op.create_table(
        "procurement_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("owner", sa.String(length=200), nullable=False),
        sa.Column("official_url", sa.String(length=1000), nullable=False),
        sa.Column("access_method", sa.String(length=32), nullable=False),
        sa.Column("terms_url", sa.String(length=1000), nullable=True),
        sa.Column("terms_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("permitted_reuse", sa.Boolean(), nullable=True),
        sa.Column("rate_limit_notes", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_procurement_sources_name", "procurement_sources", ["name"], unique=True)

    op.create_table(
        "contractors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_name", sa.String(length=200), nullable=False),
        sa.Column("trades", sa.JSON(), nullable=False),
        sa.Column("regions", sa.JSON(), nullable=False),
        sa.Column("crew_capacity", sa.Integer(), nullable=True),
        sa.Column("equipment", sa.JSON(), nullable=False),
        sa.Column("certifications", sa.JSON(), nullable=False),
        sa.Column("insurance_verified", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_contractors_company_name", "contractors", ["company_name"])

    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("contractor_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["contractor_id"], ["contractors.id"]),
        sa.UniqueConstraint("contractor_id"),
    )
    op.create_index("ix_accounts_email", "accounts", ["email"], unique=True)

    op.create_table(
        "tenders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("location", sa.String(length=200), nullable=False),
        sa.Column("region", sa.String(length=100), nullable=False),
        sa.Column("geography_id", sa.Integer(), nullable=True),
        sa.Column("trades", sa.JSON(), nullable=False),
        sa.Column("estimated_value", sa.Float(), nullable=True),
        sa.Column("closing_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("bid_security_required", sa.Boolean(), nullable=True),
        sa.Column("mandatory_requirements", sa.JSON(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("source_name", sa.String(length=200), nullable=False),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("source_reference", sa.String(length=200), nullable=True),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["geography_id"], ["geographies.id"]),
        sa.ForeignKeyConstraint(["source_id"], ["procurement_sources.id"]),
        sa.UniqueConstraint("source_reference"),
    )
    op.create_index("ix_tenders_geography_id", "tenders", ["geography_id"])
    op.create_index("ix_tenders_location", "tenders", ["location"])
    op.create_index("ix_tenders_region", "tenders", ["region"])
    op.create_index("ix_tenders_status", "tenders", ["status"])
    op.create_index("ix_tenders_status_closing_date", "tenders", ["status", "closing_date"])
    op.create_index("ix_tenders_title", "tenders", ["title"])

    op.create_table(
        "matches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("contractor_id", sa.Integer(), nullable=False),
        sa.Column("tender_id", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("explanation", sa.JSON(), nullable=False),
        sa.Column("flags", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["contractor_id"], ["contractors.id"]),
        sa.ForeignKeyConstraint(["tender_id"], ["tenders.id"]),
    )
    op.create_index("ix_matches_contractor_id", "matches", ["contractor_id"])
    op.create_index("ix_matches_tender_id", "matches", ["tender_id"])


def downgrade() -> None:
    op.drop_table("matches")
    op.drop_table("tenders")
    op.drop_table("accounts")
    op.drop_table("contractors")
    op.drop_table("procurement_sources")
    op.drop_table("geographies")
