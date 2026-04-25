"""Unit tests for dai/builder.py"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from dai.builder import Decision
from dai.client import CommitResult
from dai.exceptions import AlreadyCommittedError, BuilderValidationError
from dai.models import AgentType, ExceptionType


def _make_mock_result(decision_id: str = "test-id") -> CommitResult:
    return CommitResult(
        success=True,
        decision_id=decision_id,
        record_hash="a" * 64,
        latency_ms=1.5,
    )


@pytest.fixture
def mock_client(mocker):
    """Mock the DAI client used inside Decision.commit()."""
    mock = AsyncMock()
    mock.get_latest_hash = AsyncMock(return_value="0" * 64)
    mock.commit = AsyncMock(return_value=_make_mock_result())
    mocker.patch("dai.builder.get_client", return_value=mock)
    return mock


def _full_decision() -> Decision:
    """Build a fully configured Decision ready to commit."""
    return (
        Decision.begin(
            agent_id="claims-agent",
            decision_type="claims_triage",
            subject_ref="claim:ABC123",
        )
        .with_policy(policy_id="motor-v3", policy_version="3.2.1")
        .with_authority(authorized_scope="triage", delegation_source="underwriting")
        .with_context(
            evidence_refs=["doc:claim-form"],
            data_sources_accessed=["claims-db"],
        )
        .with_outcome(outcome="approved", confidence=0.93)
    )


class TestDecisionBuilder:
    @pytest.mark.asyncio
    async def test_full_happy_path(self, mock_client):
        d = _full_decision()
        result = await d.commit()
        assert result.success is True
        assert result.decision_id == "test-id"
        mock_client.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_missing_policy_raises(self, mock_client):
        d = (
            Decision.begin("agent", "claims_triage", "claim:001")
            .with_authority(authorized_scope="x", delegation_source="y")
            .with_context(evidence_refs=["e"], data_sources_accessed=["d"])
            .with_outcome(outcome="approved", confidence=0.9)
        )
        with pytest.raises(BuilderValidationError) as exc_info:
            await d.commit()
        assert "policy_id" in exc_info.value.missing_fields

    @pytest.mark.asyncio
    async def test_missing_outcome_raises(self, mock_client):
        d = (
            Decision.begin("agent", "claims_triage", "claim:001")
            .with_policy(policy_id="p", policy_version="1.0.0")
            .with_authority(authorized_scope="x", delegation_source="y")
            .with_context(evidence_refs=["e"], data_sources_accessed=["d"])
        )
        with pytest.raises(BuilderValidationError) as exc_info:
            await d.commit()
        assert "outcome" in exc_info.value.missing_fields

    @pytest.mark.asyncio
    async def test_double_commit_raises(self, mock_client):
        d = _full_decision()
        await d.commit()
        with pytest.raises(AlreadyCommittedError):
            await d.commit()

    def test_string_enum_coercion_agent_type(self, mock_client):
        d = Decision.begin(
            "agent", "test", "ref:001", agent_type="autonomous"
        )
        assert d._agent_type == AgentType.autonomous

    def test_string_enum_coercion_autonomous(self, mock_client):
        d = Decision.begin("a", "b", "c", agent_type="human_in_loop")
        assert d._agent_type == AgentType.human_in_loop

    @pytest.mark.asyncio
    async def test_with_override_sets_override_applied(self, mock_client):
        d = (
            _full_decision()
            .with_override("senior-underwriter", ExceptionType.manual_override)
        )
        assert d._override_applied is True
        assert d._override_by == "senior-underwriter"

    @pytest.mark.asyncio
    async def test_with_exception_sets_exception_applied(self, mock_client):
        d = (
            _full_decision()
            .with_exception(ExceptionType.conservative_fallback, "low_confidence")
        )
        assert d._exception_applied is True

    @pytest.mark.asyncio
    async def test_with_metadata_accumulates(self, mock_client):
        d = (
            _full_decision()
            .with_metadata("region", "EU")
            .with_metadata("claim_value", "8500")
        )
        assert d._metadata == {"region": "EU", "claim_value": "8500"}

    @pytest.mark.asyncio
    async def test_context_manager_auto_commits(self, mock_client):
        async with Decision.begin(
            "agent", "test", "ref:001"
        ) as d:
            d.with_policy("p", "1.0.0")
            d.with_authority("scope", "source")
            d.with_context(["e"], ["d"])
            d.with_outcome("approved", 0.9)
        mock_client.commit.assert_called_once()

    def test_context_manager_auto_commits_sync(self, mock_client):
        with Decision.begin_sync("test-agent", "audit", "ref") as d:
            d.with_policy("p1", "1.0.0")
            d.with_authority("scope", "source")
            d.with_context(["e"], ["d"])
            d.with_outcome("success", 1.0)
        assert mock_client.commit.called

    @pytest.mark.asyncio
    async def test_async_commit_happy_path(self, mock_client):
        from dai.client import CommitResult
        mock_client.commit.return_value = CommitResult(success=True, decision_id="async-123", record_hash="a"*64, latency_ms=1.5)
        mock_client.get_latest_hash.return_value = "0"*64

        d = (Decision.begin("test-agent", "async-test", "ref")
             .with_policy("p1", "1.0.0")
             .with_authority("scope", "source")
             .with_context(["e"], ["d"])
             .with_outcome("success", 1.0))
        res = await d.commit()

        assert mock_client.commit.called
        assert res.success
        assert res.decision_id == "async-123"

    @pytest.mark.asyncio
    async def test_async_context_manager(self, mock_client):
        from dai.client import CommitResult
        mock_client.commit.return_value = CommitResult(success=True, decision_id="async-ctx-123", record_hash="a"*64, latency_ms=1.5)
        mock_client.get_latest_hash.return_value = "0"*64

        async with Decision.begin("test-agent", "audit", "ref") as d:
            d.with_policy("p1", "1.0.0")
            d.with_authority("scope", "source")
            d.with_context(["e"], ["d"])
            d.with_outcome("success", 1.0)

        assert mock_client.commit.called

    @pytest.mark.asyncio
    async def test_context_manager_exception_records_fallback(self, mock_client):
        with pytest.raises(ValueError):
            async with Decision.begin("agent", "test", "ref:001") as d:
                d.with_policy("p", "1.0.0")
                d.with_authority("scope", "source")
                d.with_context(["e"], ["d"])
                raise ValueError("agent crashed")
        # Should have committed a conservative_fallback record
        mock_client.commit.assert_called_once()
        committed_record = mock_client.commit.call_args[0][0]
        assert committed_record.exception_applied is True
        assert committed_record.outcome == "escalated"

    def test_context_manager_exception_records_fallback_sync(self, mock_client):
        from dai.client import CommitResult
        mock_client.commit.return_value = CommitResult(
            success=True, decision_id="ctx-123", record_hash="a"*64, latency_ms=1.5
        )
        mock_client.get_latest_hash.return_value = "0"*64

        with pytest.raises(ValueError), Decision.begin_sync("test-agent", "audit", "ref") as d:
                d.with_policy("p", "1.0.0")
                d.with_authority("scope", "source")
                d.with_context(["e"], ["d"])
                raise ValueError("agent crashed")

        assert mock_client.commit.called
