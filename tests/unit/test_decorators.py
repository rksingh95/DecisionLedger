"""Unit tests for dai/decorators.py"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from dai.decorators import log_decision
from dai.models import ExceptionType


@pytest.fixture
def mock_client(mocker):
    mock = AsyncMock()
    mock.get_latest_hash = AsyncMock(return_value="0" * 64)
    mock.commit = AsyncMock()
    mock.commit.return_value = type("CR", (), {"success": True, "decision_id": "test"})()
    mocker.patch("dai.builder.get_client", return_value=mock)
    return mock


class TestLogDecisionDecorator:
    @pytest.mark.asyncio
    async def test_async_function_happy_path(self, mock_client):
        @log_decision(
            agent_id="test-agent",
            decision_type="claims_triage",
            policy_id="test-policy",
            policy_version="1.0.0",
            extract_subject=lambda args, kwargs: f"claim:{kwargs.get('claim_id', 'unknown')}",
            extract_outcome=lambda r: {"outcome": r["decision"], "confidence": r["score"]},
        )
        async def my_func(claim_id: str) -> dict:
            return {"decision": "approved", "score": 0.95}

        result = await my_func(claim_id="ABC123")
        assert result == {"decision": "approved", "score": 0.95}
        mock_client.commit.assert_called_once()

    def test_sync_function_happy_path(self, mock_client):
        @log_decision(
            agent_id="test-agent",
            decision_type="claims_triage",
            policy_id="test-policy",
            policy_version="1.0.0",
            extract_subject=lambda args, kwargs: "claim:001",
            extract_outcome=lambda r: {"outcome": "approved", "confidence": 0.9},
        )
        def my_sync_func(x: int) -> int:
            return x * 2

        result = my_sync_func(5)
        assert result == 10

    @pytest.mark.asyncio
    async def test_exception_records_conservative_fallback(self, mock_client):
        @log_decision(
            agent_id="test-agent",
            decision_type="claims_triage",
            policy_id="test-policy",
            policy_version="1.0.0",
            extract_subject=lambda args, kwargs: "claim:001",
            extract_outcome=lambda r: {"outcome": r, "confidence": 0.9},
        )
        async def failing_func() -> str:
            raise RuntimeError("Something went wrong")

        with pytest.raises(RuntimeError):
            await failing_func()

        # Should have committed a record despite the exception
        mock_client.commit.assert_called_once()
        committed = mock_client.commit.call_args[0][0]
        assert committed.exception_applied is True
        assert committed.outcome == "escalated"

    @pytest.mark.asyncio
    async def test_return_value_unchanged(self, mock_client):
        @log_decision(
            agent_id="test-agent",
            decision_type="test",
            policy_id="p",
            policy_version="1.0.0",
            extract_subject=lambda args, kwargs: "ref:001",
            extract_outcome=lambda r: {"outcome": "approved", "confidence": 0.9},
        )
        async def my_func() -> dict:
            return {"key": "value", "nested": [1, 2, 3]}

        result = await my_func()
        assert result == {"key": "value", "nested": [1, 2, 3]}
