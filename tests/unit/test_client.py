from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dai.client import HTTPDAIClient, NoopDAIClient, SQLiteDAIClient, get_client, reset_client_cache
from dai.config import BackendType, DAIConfig, ErrorPolicy
from dai.models import DecisionRecord, QueryFilter


@pytest.fixture
def mock_record():
    return DecisionRecord(
        decision_id="123e4567-e89b-12d3-a456-426614174000",
        record_hash="0" * 64,
        previous_hash="0" * 64,
        ledger_version="0.1.0",
        decision_timestamp=datetime.now(UTC),
        agent_id="test-agent",
        agent_type="autonomous",
        model_version="v1",
        decision_type="test",
        subject_ref="test:123",
        policy_id="p1",
        policy_version="1.0.0",
        policy_snapshot_at=datetime.now(UTC),
        outcome="approved",
        confidence=1.0,
        exception_applied=False,
        override_applied=False,
        evidence_refs=["doc:test"],
        data_sources_accessed=["db:test"],
        context_completeness="full",
        authorized_scope="test_scope",
        delegation_source="test_source",
        human_oversight_required=False,
        commit_timestamp=datetime.now(UTC),
    )

@pytest.mark.asyncio
async def test_noop_client(mock_record):
    client = NoopDAIClient()
    res = await client.commit(mock_record)
    assert res.success

    recs = await client.query(QueryFilter())
    assert recs == []

    chain = await client.verify_chain(datetime.now(UTC), datetime.now(UTC))
    assert chain.valid

    h = await client.get_latest_hash()
    assert h == "0" * 64

@pytest.mark.asyncio
@patch("dai.client.httpx.AsyncClient")
async def test_http_client_commit(mock_async_client, mock_record):
    mock_instance = AsyncMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {"decision_id": "123", "record_hash": "abc"}
    mock_instance.request.return_value = mock_response
    mock_async_client.return_value.__aenter__.return_value = mock_instance

    client = HTTPDAIClient()
    client._config = DAIConfig(backend=BackendType.http, endpoint="http://test", api_key="secret")

    res = await client.commit(mock_record)
    assert res.success
    assert res.decision_id == "123"

@pytest.mark.asyncio
@patch("dai.client.httpx.AsyncClient")
async def test_http_client_query(mock_async_client, mock_record):
    mock_instance = AsyncMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {"records": [mock_record.model_dump(mode="json")]}
    mock_instance.request.return_value = mock_response
    mock_async_client.return_value.__aenter__.return_value = mock_instance

    client = HTTPDAIClient()
    client._config = DAIConfig(backend=BackendType.http, endpoint="http://test", api_key="secret")

    recs = await client.query(QueryFilter())
    assert len(recs) == 1
    assert recs[0].agent_id == "test-agent"

@pytest.mark.asyncio
@patch("dai.client.httpx.AsyncClient")
async def test_http_client_verify(mock_async_client):
    mock_instance = AsyncMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {"valid": True, "total_records": 5, "verified_at": "2025-01-01T00:00:00Z", "message": "ok"}
    mock_instance.request.return_value = mock_response
    mock_async_client.return_value.__aenter__.return_value = mock_instance

    client = HTTPDAIClient()
    client._config = DAIConfig(backend=BackendType.http, endpoint="http://test", api_key="secret")

    res = await client.verify_chain(datetime.now(UTC), datetime.now(UTC))
    assert res.valid
    assert res.total_records == 5

@pytest.mark.asyncio
@patch("dai.client.httpx.AsyncClient")
async def test_http_client_get_latest_hash(mock_async_client):
    mock_instance = AsyncMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {"hash": "abc123hash"}
    mock_instance.request.return_value = mock_response
    mock_async_client.return_value.__aenter__.return_value = mock_instance

    client = HTTPDAIClient()
    client._config = DAIConfig(backend=BackendType.http, endpoint="http://test", api_key="secret")

    h = await client.get_latest_hash()
    assert h == "abc123hash"

def test_get_client():
    reset_client_cache()
    c1 = get_client(DAIConfig(backend=BackendType.noop))
    assert isinstance(c1, NoopDAIClient)
    c2 = get_client(DAIConfig(backend=BackendType.http))
    assert isinstance(c2, HTTPDAIClient)
    c3 = get_client(DAIConfig(backend=BackendType.sqlite))
    assert isinstance(c3, SQLiteDAIClient)

@pytest.mark.asyncio
@patch("dai.client.httpx.AsyncClient")
async def test_http_client_commit_error_handling(mock_async_client, mock_record):
    import httpx
    mock_instance = AsyncMock()
    mock_instance.request.side_effect = httpx.ConnectError("Connection refused")
    mock_async_client.return_value.__aenter__.return_value = mock_instance

    # log_and_continue (default)
    client = HTTPDAIClient()
    client._config = DAIConfig(backend=BackendType.http, endpoint="http://test", api_key="secret", on_error=ErrorPolicy.log_and_continue, max_retries=1)

    res = await client.commit(mock_record)
    assert not res.success

    # raise_exception
    client._config.on_error = ErrorPolicy.raise_exception
    from dai.exceptions import ClientError
    with pytest.raises(ClientError):
        await client.commit(mock_record)

@pytest.mark.asyncio
@patch("dai.client.httpx.AsyncClient")
async def test_http_client_query_error_handling(mock_async_client):
    import httpx
    mock_instance = AsyncMock()
    mock_instance.request.side_effect = httpx.HTTPStatusError("Bad Request", request=MagicMock(), response=MagicMock(status_code=400, text="err"))
    mock_async_client.return_value.__aenter__.return_value = mock_instance

    client = HTTPDAIClient()
    client._config = DAIConfig(backend=BackendType.http, endpoint="http://test", api_key="secret", on_error=ErrorPolicy.log_and_continue)

    res = await client.query(QueryFilter())
    assert res == []

    client._config.on_error = ErrorPolicy.raise_exception
    from dai.exceptions import ClientError
    with pytest.raises(ClientError):
        await client.query(QueryFilter())

@pytest.mark.asyncio
@patch("dai.client.httpx.AsyncClient")
async def test_http_client_verify_error_handling(mock_async_client):
    import httpx
    mock_instance = AsyncMock()
    mock_instance.request.side_effect = httpx.TimeoutException("Timeout")
    mock_async_client.return_value.__aenter__.return_value = mock_instance

    client = HTTPDAIClient()
    client._config = DAIConfig(backend=BackendType.http, endpoint="http://test", api_key="secret", on_error=ErrorPolicy.log_and_continue)

    res = await client.verify_chain(datetime.now(UTC), datetime.now(UTC))
    assert not res.valid
    assert "Timeout" in res.message
