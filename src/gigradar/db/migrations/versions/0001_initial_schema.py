"""Initial schema for platforms, gigs, gig_snapshots, and scrape_runs.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-10-18 08:00:00.000000+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. platforms
    op.create_table(
        "platforms",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("base_url", sa.String(length=255), nullable=False),
        sa.Column("is_paused", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("paused_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pause_reason", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_platforms_name"), "platforms", ["name"], unique=True)

    # 2. gigs
    op.create_table(
        "gigs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("platform_id", sa.Integer(), nullable=False),
        sa.Column("external_id", sa.String(length=100), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("budget_min", sa.Float(), nullable=True),
        sa.Column("budget_max", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=True),
        sa.Column("budget_min_usd", sa.Float(), nullable=True),
        sa.Column("budget_max_usd", sa.Float(), nullable=True),
        sa.Column("budget_usd_est", sa.Float(), nullable=True),
        sa.Column("project_type", sa.String(length=20), nullable=False, server_default="fixed"),
        sa.Column("bids_count", sa.Integer(), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deadline_text", sa.String(length=100), nullable=True),
        sa.Column("client_name", sa.String(length=255), nullable=True),
        sa.Column("client_stats_json", sa.JSON(), nullable=True),
        sa.Column("category_raw", sa.String(length=255), nullable=True),
        sa.Column("tags_raw_json", sa.JSON(), nullable=True),
        sa.Column("language", sa.String(length=10), nullable=True),
        sa.Column("raw_html_hash", sa.String(length=64), nullable=True),
        sa.Column("detail_level", sa.String(length=20), nullable=False, server_default="full"),
        sa.Column("processing_state", sa.String(length=30), nullable=False, server_default="new"),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["platform_id"], ["platforms.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("platform_id", "external_id", name="uq_gigs_platform_external_id"),
    )
    op.create_index(op.f("ix_gigs_platform_id"), "gigs", ["platform_id"], unique=False)
    op.create_index(op.f("ix_gigs_posted_at"), "gigs", ["posted_at"], unique=False)
    op.create_index(op.f("ix_gigs_processing_state"), "gigs", ["processing_state"], unique=False)
    op.create_index(op.f("ix_gigs_last_seen_at"), "gigs", ["last_seen_at"], unique=False)

    # 3. gig_snapshots
    op.create_table(
        "gig_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("gig_id", sa.Integer(), nullable=False),
        sa.Column("bids_count", sa.Integer(), nullable=True),
        sa.Column("seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["gig_id"], ["gigs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_gig_snapshots_gig_id"), "gig_snapshots", ["gig_id"], unique=False)

    # 4. scrape_runs
    op.create_table(
        "scrape_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("platform_id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("gigs_found", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("gigs_new", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("errors_json", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["platform_id"], ["platforms.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_scrape_runs_platform_id"), "scrape_runs", ["platform_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_scrape_runs_platform_id"), table_name="scrape_runs")
    op.drop_table("scrape_runs")

    op.drop_index(op.f("ix_gig_snapshots_gig_id"), table_name="gig_snapshots")
    op.drop_table("gig_snapshots")

    op.drop_index(op.f("ix_gigs_last_seen_at"), table_name="gigs")
    op.drop_index(op.f("ix_gigs_processing_state"), table_name="gigs")
    op.drop_index(op.f("ix_gigs_posted_at"), table_name="gigs")
    op.drop_index(op.f("ix_gigs_platform_id"), table_name="gigs")
    op.drop_table("gigs")

    op.drop_index(op.f("ix_platforms_name"), table_name="platforms")
    op.drop_table("platforms")
