"""Rename generated campaign actual columns."""

from collections.abc import Sequence

from alembic import op

revision: str = "20260831_0004"
down_revision: str | None = "20260831_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "campaigns",
        "adstock",
        new_column_name="actual_adstock",
        schema="raw",
    )
    op.alter_column(
        "campaigns",
        "saturated_demand",
        new_column_name="actual_saturated_demand",
        schema="raw",
    )


def downgrade() -> None:
    op.alter_column(
        "campaigns",
        "actual_saturated_demand",
        new_column_name="saturated_demand",
        schema="raw",
    )
    op.alter_column(
        "campaigns",
        "actual_adstock",
        new_column_name="adstock",
        schema="raw",
    )
