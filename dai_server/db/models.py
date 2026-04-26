"""
DAI Server — SQLAlchemy ORM Models
====================================

Defines the ``decisions`` table used by the DAI server's PostgreSQL backend.
The table is append-only by design: PostgreSQL RLS rules prevent UPDATE and DELETE.
"""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class DecisionORM(Base):
    """
    ORM representation of a single decision record row.

    ``full_record_json`` stores the complete serialised ``DecisionRecord``
    so that records can be fully reconstructed without joining other tables.
    All other columns are indexed projections for efficient filtering.
    """

    __tablename__ = "decisions"

    __table_args__ = (
        CheckConstraint("confidence >= 0.0 AND confidence <= 1.0", name="ck_confidence_range"),
        Index("ix_decisions_agent_type_ts", "agent_id", "decision_timestamp"),
        Index("ix_decisions_type_ts", "decision_type", "decision_timestamp"),
    )

    decision_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    record_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    previous_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    ledger_version: Mapped[str] = mapped_column(String(20), nullable=False)
    decision_timestamp: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    commit_timestamp: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    agent_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    agent_type: Mapped[str] = mapped_column(String(50), nullable=False)
    model_version: Mapped[str] = mapped_column(String(255), nullable=False)
    deployment_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    decision_type: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    subject_ref: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    policy_id: Mapped[str] = mapped_column(String(255), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(50), nullable=False)
    outcome: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    exception_applied: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )
    override_applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    full_record_json: Mapped[str] = mapped_column(Text, nullable=False)

    def __repr__(self) -> str:
        return (
            f"<DecisionORM decision_id={self.decision_id!r} "
            f"outcome={self.outcome!r} "
            f"agent_id={self.agent_id!r}>"
        )


class ApiKeyORM(Base):
    """
    API Keys for authenticating AI agents and reading the ledger.
    """

    __tablename__ = "api_keys"

    key_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    agent_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    roles: Mapped[str] = mapped_column(String(255), nullable=False, default="write")
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<ApiKeyORM agent_id={self.agent_id!r} roles={self.roles!r}>"


class PolicyVersionORM(Base):
    """
    ORM representation of a PolicyVersion.
    """

    __tablename__ = "policy_versions"

    policy_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    version: Mapped[str] = mapped_column(String(50), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    effective_from: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    effective_to: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    change_type: Mapped[str] = mapped_column(String(100), nullable=False)
    change_summary: Mapped[str] = mapped_column(String(500), nullable=False)
    authorized_decision_types: Mapped[str] = mapped_column(Text, nullable=False)
    max_auto_approve_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    exception_types_allowed: Mapped[str] = mapped_column(Text, nullable=False)
    retention_period_days: Mapped[int] = mapped_column(Integer, nullable=False, default=180)
    policy_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    clauses_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)

    def __repr__(self) -> str:
        return f"<PolicyVersionORM policy_id={self.policy_id!r} version={self.version!r}>"
