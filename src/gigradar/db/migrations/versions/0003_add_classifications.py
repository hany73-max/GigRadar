"""Add classifications table.

Revision ID: 0003_add_classifications
Revises: 0002_add_detail_attempts
Create Date: 2026-10-25 10:00:00.000000+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from gigradar.db.models import UTCDateTime

# revision identifiers, used by Alembic.
revision: str = "0003_add_classifications"
down_revision: str | None = "0002_add_detail_attempts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "classifications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("gig_id", sa.Integer(), nullable=False),
        sa.Column("stage", sa.String(length=20), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("rule_hits_json", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("reject_reason", sa.String(length=255), nullable=True),
        sa.Column("flags_json", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("rules_version", sa.String(length=32), nullable=True),
        sa.Column("match_score", sa.Float(), nullable=True),
        sa.Column("domain", sa.String(length=50), nullable=True),
        sa.Column("work_type", sa.String(length=50), nullable=True),
        sa.Column("tier", sa.String(length=10), nullable=True),
        sa.Column("feasibility", sa.String(length=50), nullable=True),
        sa.Column("red_flags_json", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("missing_info_json", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("suggested_price_usd", sa.Float(), nullable=True),
        sa.Column("est_hours", sa.Float(), nullable=True),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column("model", sa.String(length=50), nullable=True),
        sa.Column("prompt_version", sa.String(length=50), nullable=True),
        sa.Column("tokens_in", sa.Integer(), nullable=True),
        sa.Column("tokens_out", sa.Integer(), nullable=True),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(["gig_id"], ["gigs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_classifications_gig_id"),
        "classifications",
        ["gig_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_classifications_stage"),
        "classifications",
        ["stage"],
        unique=False,
    )
    op.create_index(
        op.f("ix_classifications_passed"),
        "classifications",
        ["passed"],
        unique=False,
    )
    op.create_index(
        op.f("ix_classifications_rules_version"),
        "classifications",
        ["rules_version"],
        unique=False,
    )
    op.create_index(
        op.f("ix_classifications_created_at"),
        "classifications",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_classifications_created_at"), table_name="classifications")
    op.drop_index(op.f("ix_classifications_rules_version"), table_name="classifications")
    op.drop_index(op.f("ix_classifications_passed"), table_name="classifications")
    op.drop_index(op.f("ix_classifications_stage"), table_name="classifications")
    op.drop_index(op.f("ix_classifications_gig_id"), table_name="classifications")
    op.drop_table("classifications")
