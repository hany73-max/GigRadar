"""Add detail_attempts column to gigs table.

Revision ID: 0002_add_detail_attempts
Revises: 0001_initial_schema
Create Date: 2026-10-18 10:00:00.000000+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_add_detail_attempts"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "gigs",
        sa.Column("detail_attempts", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("gigs", "detail_attempts")
