"""Create raw website graph table."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260903_0005"
down_revision: str | None = "20260831_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "website",
        sa.Column("from_page", sa.Text(), nullable=False),
        sa.Column("to_page", sa.Text(), nullable=False),
        sa.Column("transition_probability", sa.Numeric(), nullable=False),
        sa.PrimaryKeyConstraint("from_page", "to_page", name="pk_raw_website"),
        schema="raw",
    )
    op.create_index(
        "ix_raw_website_from_page",
        "website",
        ["from_page"],
        schema="raw",
    )


def downgrade() -> None:
    op.drop_index("ix_raw_website_from_page", table_name="website", schema="raw")
    op.drop_table("website", schema="raw")
