"""Create raw events table."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260826_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(sa.schema.CreateSchema("raw", if_not_exists=True))
    op.create_table(
        "events",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("visitor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("page", sa.Text(), nullable=False),
        sa.Column("timestamp", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("event_id", name="pk_raw_events"),
        schema="raw",
    )
    op.create_index("ix_raw_events_visitor_id", "events", ["visitor_id"], schema="raw")
    op.create_index(
        "ix_raw_events_session_id_timestamp",
        "events",
        ["session_id", "timestamp"],
        schema="raw",
    )
    op.create_index("ix_raw_events_timestamp", "events", ["timestamp"], schema="raw")


def downgrade() -> None:
    op.drop_index("ix_raw_events_timestamp", table_name="events", schema="raw")
    op.drop_index(
        "ix_raw_events_session_id_timestamp",
        table_name="events",
        schema="raw",
    )
    op.drop_index("ix_raw_events_visitor_id", table_name="events", schema="raw")
    op.drop_table("events", schema="raw")
