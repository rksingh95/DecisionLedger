"""0001 - Initial decisions table

Revision ID: 0001
Revises:
Create Date: 2026-04-25

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "decisions",
        sa.Column("decision_id", sa.String(36), primary_key=True),
        sa.Column("record_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("previous_hash", sa.String(64), nullable=False),
        sa.Column("ledger_version", sa.String(20), nullable=False),
        sa.Column("decision_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "commit_timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("agent_id", sa.String(255), nullable=False),
        sa.Column("agent_type", sa.String(50), nullable=False),
        sa.Column("model_version", sa.String(255), nullable=False),
        sa.Column("deployment_id", sa.String(255), nullable=True),
        sa.Column("decision_type", sa.String(255), nullable=False),
        sa.Column("subject_ref", sa.String(255), nullable=False),
        sa.Column("policy_id", sa.String(255), nullable=False),
        sa.Column("policy_version", sa.String(50), nullable=False),
        sa.Column("outcome", sa.String(100), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("exception_applied", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("override_applied", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("full_record_json", sa.Text, nullable=False),
        sa.CheckConstraint("confidence >= 0.0 AND confidence <= 1.0", name="ck_confidence_range"),
    )

    op.create_index("ix_decisions_decision_timestamp", "decisions", ["decision_timestamp"])
    op.create_index("ix_decisions_agent_id", "decisions", ["agent_id"])
    op.create_index("ix_decisions_decision_type", "decisions", ["decision_type"])
    op.create_index("ix_decisions_subject_ref", "decisions", ["subject_ref"])
    op.create_index("ix_decisions_outcome", "decisions", ["outcome"])
    op.create_index("ix_decisions_exception_applied", "decisions", ["exception_applied"])
    op.create_index("ix_decisions_agent_type_ts", "decisions", ["agent_id", "decision_timestamp"])
    op.create_index("ix_decisions_type_ts", "decisions", ["decision_type", "decision_timestamp"])

    # Append-only enforcement via PostgreSQL rules
    op.execute(
        "CREATE RULE no_update_decisions AS ON UPDATE TO decisions DO INSTEAD NOTHING;"
    )
    op.execute(
        "CREATE RULE no_delete_decisions AS ON DELETE TO decisions DO INSTEAD NOTHING;"
    )

    # Row-level security
    op.execute("ALTER TABLE decisions ENABLE ROW LEVEL SECURITY;")
    op.execute("CREATE POLICY dai_insert_only ON decisions FOR INSERT WITH CHECK (true);")
    op.execute(
        "CREATE POLICY dai_no_select_anon ON decisions FOR SELECT "
        "USING (current_user = 'dai_app');"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS dai_no_select_anon ON decisions;")
    op.execute("DROP POLICY IF EXISTS dai_insert_only ON decisions;")
    op.execute("ALTER TABLE decisions DISABLE ROW LEVEL SECURITY;")
    op.execute("DROP RULE IF EXISTS no_delete_decisions ON decisions;")
    op.execute("DROP RULE IF EXISTS no_update_decisions ON decisions;")
    op.drop_table("decisions")
