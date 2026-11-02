"""Add reviewed-source, document-review, contractor-notification, and outcome workflows.

Revision ID: 0002_workflows
Revises: 0001_foundation
"""
import sqlalchemy as sa
from alembic import op

revision = "0002_workflows"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("procurement_sources", sa.Column("last_checked_at", sa.DateTime(timezone=True)))
    op.add_column(
        "procurement_sources",
        sa.Column("health_status", sa.String(length=32), nullable=False, server_default="unconfigured"),
    )
    op.add_column("procurement_sources", sa.Column("health_message", sa.String(length=500)))
    op.add_column("procurement_sources", sa.Column("update_frequency", sa.String(length=100)))
    op.add_column("accounts", sa.Column("email_verified_at", sa.DateTime(timezone=True)))
    op.create_table(
        "account_verification_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_account_verification_tokens_account_id", "account_verification_tokens", ["account_id"])
    op.create_index("ix_account_verification_tokens_token_hash", "account_verification_tokens", ["token_hash"], unique=True)
    op.add_column(
        "contractors",
        sa.Column("notify_matches", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "contractors",
        sa.Column("minimum_match_score", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column("tenders", sa.Column("archived_at", sa.DateTime(timezone=True)))
    op.add_column(
        "tenders",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "source_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("procurement_sources.id"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("access_method", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("records_seen", sa.Integer(), nullable=False),
        sa.Column("records_created", sa.Integer(), nullable=False),
        sa.Column("records_updated", sa.Integer(), nullable=False),
        sa.Column("records_archived", sa.Integer(), nullable=False),
        sa.Column("error_summary", sa.String(length=1000)),
    )
    op.create_index("ix_source_runs_source_id", "source_runs", ["source_id"])

    op.create_table(
        "tender_revisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tender_id", sa.Integer(), sa.ForeignKey("tenders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_account_id", sa.Integer(), sa.ForeignKey("accounts.id")),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_tender_revisions_tender_id", "tender_revisions", ["tender_id"])

    op.create_table(
        "public_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("procurement_sources.id"), nullable=False),
        sa.Column("source_url", sa.String(length=1000), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_path", sa.String(length=1000), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("extracted_text", sa.Text()),
        sa.Column("proposed_fields", sa.JSON(), nullable=False),
        sa.Column("field_confidence", sa.JSON(), nullable=False),
        sa.Column("extractor_name", sa.String(length=100)),
        sa.Column("extractor_version", sa.String(length=100)),
        sa.Column("prompt_version", sa.String(length=100)),
        sa.Column("review_note", sa.String(length=1000)),
        sa.Column("reviewed_by_account_id", sa.Integer(), sa.ForeignKey("accounts.id")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("tender_id", sa.Integer(), sa.ForeignKey("tenders.id")),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("source_id", "sha256", name="uq_public_documents_source_sha256"),
    )
    op.create_index("ix_public_documents_source_id", "public_documents", ["source_id"])
    op.create_index("ix_public_documents_sha256", "public_documents", ["sha256"])
    op.create_index("ix_public_documents_status", "public_documents", ["status"])

    op.create_table(
        "verified_outcomes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tender_id", sa.Integer(), sa.ForeignKey("tenders.id"), nullable=False),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("procurement_sources.id"), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("published_at", sa.Date()),
        sa.Column("source_url", sa.String(length=1000), nullable=False),
        sa.Column("source_reference", sa.String(length=200), nullable=False),
        sa.Column("verification_method", sa.String(length=500), nullable=False),
        sa.Column("verified_by_account_id", sa.Integer(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tender_id", name="uq_verified_outcomes_tender_id"),
        sa.UniqueConstraint("source_id", "source_reference", name="uq_verified_outcomes_source_ref"),
    )
    op.create_index("ix_verified_outcomes_tender_id", "verified_outcomes", ["tender_id"])

    op.create_table(
        "contractor_notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("contractor_id", sa.Integer(), sa.ForeignKey("contractors.id"), nullable=False),
        sa.Column("tender_id", sa.Integer(), sa.ForeignKey("tenders.id"), nullable=False),
        sa.Column("match_record_id", sa.Integer(), sa.ForeignKey("matches.id"), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("match_record_id", name="uq_contractor_notifications_match_record_id"),
    )
    op.create_index("ix_contractor_notifications_contractor_id", "contractor_notifications", ["contractor_id"])
    op.create_index("ix_contractor_notifications_tender_id", "contractor_notifications", ["tender_id"])


def downgrade() -> None:
    op.drop_table("contractor_notifications")
    op.drop_index("ix_account_verification_tokens_token_hash", table_name="account_verification_tokens")
    op.drop_index("ix_account_verification_tokens_account_id", table_name="account_verification_tokens")
    op.drop_table("account_verification_tokens")
    op.drop_index("ix_verified_outcomes_tender_id", table_name="verified_outcomes")
    op.drop_table("verified_outcomes")
    op.drop_index("ix_public_documents_status", table_name="public_documents")
    op.drop_index("ix_public_documents_sha256", table_name="public_documents")
    op.drop_index("ix_public_documents_source_id", table_name="public_documents")
    op.drop_table("public_documents")
    op.drop_index("ix_tender_revisions_tender_id", table_name="tender_revisions")
    op.drop_table("tender_revisions")
    op.drop_index("ix_source_runs_source_id", table_name="source_runs")
    op.drop_table("source_runs")
    op.drop_column("tenders", "updated_at")
    op.drop_column("tenders", "archived_at")
    op.drop_column("contractors", "minimum_match_score")
    op.drop_column("contractors", "notify_matches")
    op.drop_column("accounts", "email_verified_at")
    op.drop_column("procurement_sources", "health_message")
    op.drop_column("procurement_sources", "health_status")
    op.drop_column("procurement_sources", "last_checked_at")
    op.drop_column("procurement_sources", "update_frequency")