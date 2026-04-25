"""0002 - Add API Keys

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-26

"""
from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("key_hash", sa.String(64), primary_key=True),
        sa.Column("agent_id", sa.String(255), nullable=False),
        sa.Column("roles", sa.String(255), nullable=False, server_default="write"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_api_keys_agent_id", "api_keys", ["agent_id"])


def downgrade() -> None:
    op.drop_table("api_keys")
