"""
DAI Test Fixtures — conftest.py
================================

Shared pytest fixtures for unit and integration tests.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from dai.client import reset_client_cache
from dai.config import reset_config
from dai.models import (
    AgentType,
    ContextCompleteness,
    DecisionRecordCreate,
)


@pytest.fixture(autouse=True)
def reset_dai_state():
    """Reset global DAI config and client cache between tests."""
    reset_config()
    reset_client_cache()
    yield
    reset_config()
    reset_client_cache()


@pytest.fixture
def dai_config_sqlite(tmp_path):
    """DAIConfig using SQLite backend for test isolation."""
    import dai

    db_path = str(tmp_path / "test_dai.db")
    dai.configure(
        backend="sqlite",
        sqlite_path=db_path,
        on_error="raise_exception",
    )
    return dai.get_config()


@pytest.fixture
def sample_decision_create() -> DecisionRecordCreate:
    """Realistic insurance claims triage DecisionRecordCreate."""
    now = datetime.now(UTC)
    return DecisionRecordCreate(
        agent_id="claims-agent-01",
        agent_type=AgentType.autonomous,
        model_version="gpt-4o-2024-08-06",
        deployment_id="prod-eu-west-1",
        authorized_scope="motor claims triage up to £10,000",
        delegation_source="underwriting-team",
        human_oversight_required=False,
        override_applied=False,
        decision_type="claims_triage",
        subject_ref="claim:CLM-2025-001234",
        policy_id="motor-claims-v3",
        policy_version="3.2.1",
        policy_snapshot_at=now,
        clauses_applied=["3.1", "4.2", "5.0"],
        outcome="approved",
        confidence=0.93,
        alternatives_considered=3,
        evidence_refs=["doc:claim-form-v2", "img:damage-photo-01", "report:engineer-assessment"],
        data_sources_accessed=["claims-db", "policy-db", "fraud-api"],
        context_completeness=ContextCompleteness.full,
        exception_applied=False,
        metadata={"region": "EU", "claim_value_gbp": "8500"},
    )
