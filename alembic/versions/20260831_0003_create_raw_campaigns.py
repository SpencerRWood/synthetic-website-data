"""Create raw campaigns table."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260831_0003"
down_revision: str | None = "20260827_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "campaigns",
        sa.Column("date_day", sa.Date(), nullable=False),
        sa.Column("campaign_id", sa.Text(), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("utm_source", sa.Text(), nullable=False),
        sa.Column("utm_medium", sa.Text(), nullable=False),
        sa.Column("utm_campaign", sa.Text(), nullable=False),
        sa.Column("daily_spend", sa.Numeric(), nullable=False),
        sa.Column("adstock", sa.Numeric(), nullable=False),
        sa.Column("saturated_demand", sa.Numeric(), nullable=False),
        sa.Column("expected_incremental_visitors", sa.Numeric(), nullable=False),
        sa.PrimaryKeyConstraint("date_day", "campaign_id", name="pk_raw_campaigns"),
        schema="raw",
    )
    op.create_index(
        "ix_raw_campaigns_campaign_id",
        "campaigns",
        ["campaign_id"],
        schema="raw",
    )
    op.create_index(
        "ix_raw_campaigns_date_day",
        "campaigns",
        ["date_day"],
        schema="raw",
    )


def downgrade() -> None:
    op.drop_index("ix_raw_campaigns_date_day", table_name="campaigns", schema="raw")
    op.drop_index("ix_raw_campaigns_campaign_id", table_name="campaigns", schema="raw")
    op.drop_table("campaigns", schema="raw")
