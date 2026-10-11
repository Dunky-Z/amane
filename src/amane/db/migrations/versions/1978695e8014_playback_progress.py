"""playback_progress

Revision ID: 1978695e8014
Revises: 82643a46d07a
Create Date: 2026-09-29 23:03:38.016026
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1978695e8014"
down_revision: str | None = "82643a46d07a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "playback_progress",
        sa.Column("metadata_id", sa.Integer(), nullable=False),
        sa.Column("position_seconds", sa.Float(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["metadata_id"], ["metadata.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("metadata_id"),
    )


def downgrade() -> None:
    op.drop_table("playback_progress")
