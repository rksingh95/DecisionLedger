"""Unit tests for dai/client.py — targeting >90% coverage."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dai.client import HTTPDAIClient, NoopDAIClient, SQLiteDAIClient, get_client, reset_client_cache
from dai.config import BackendType, DAIConfig, ErrorPolicy
from dai.models import DecisionRecord, QueryFilter


# ── Shared fixtures ────────────────────────────────────────────────────────────

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


# ── NoopDAIClient ──────────────────────────────────────────────────────────────

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


# ── HTTPDAIClient — happy paths ────────────────────────────────────────────────

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
async def test_http_client_commit_with_opentelemetry(mock_async_client, mock_record):
    """Cover the emit_opentelemetry_spans branch in HTTPDAIClient.commit."""
    mock_instance = AsyncMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {"decision_id": "abc", "record_hash": "xyz"}
    mock_instance.request.return_value = mock_response
    mock_async_client.return_value.__aenter__.return_value = mock_instance

    client = HTTPDAIClient()
    client._config = DAIConfig(
        backend=BackendType.http,
        endpoint="http://test",
        api_key="secret",
        emit_opentelemetry_spans=True,
    )

    # emit_decision_span raises — should be silently swallowed
    with patch("dai.integrations.opentelemetry.emit_decision_span", side_effect=ImportError):
        res = await client.commit(mock_record)
    assert res.success


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
async def test_http_client_query_all_filter_branches(mock_async_client, mock_record):
    """Exercise every optional query-filter branch in HTTPDAIClient.query."""
    mock_instance = AsyncMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {"records": []}
    mock_instance.request.return_value = mock_response
    mock_async_client.return_value.__aenter__.return_value = mock_instance

    client = HTTPDAIClient()
    client._config = DAIConfig(backend=BackendType.http, endpoint="http://test", api_key="secret")

    now = datetime.now(UTC)
    recs = await client.query(QueryFilter(
        decision_id="some-id",
        agent_id="agent-1",
        decision_type="triage",
        from_timestamp=now,
        to_timestamp=now,
        outcome="approved",
        exception_applied=True,
        override_applied=False,
        cursor="cursor-val",
    ))
    assert recs == []


@pytest.mark.asyncio
@patch("dai.client.httpx.AsyncClient")
async def test_http_client_verify(mock_async_client):
    mock_instance = AsyncMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "valid": True, "total_records": 5,
        "verified_at": "2025-01-01T00:00:00Z", "message": "ok",
    }
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


# ── HTTPDAIClient — error handling ────────────────────────────────────────────

@pytest.mark.asyncio
@patch("dai.client.httpx.AsyncClient")
async def test_http_client_commit_error_handling(mock_async_client, mock_record):
    import httpx

    mock_instance = AsyncMock()
    mock_instance.request.side_effect = httpx.ConnectError("Connection refused")
    mock_async_client.return_value.__aenter__.return_value = mock_instance

    # log_and_continue
    client = HTTPDAIClient()
    client._config = DAIConfig(
        backend=BackendType.http, endpoint="http://test", api_key="secret",
        on_error=ErrorPolicy.log_and_continue, max_retries=1,
    )
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
    mock_instance.request.side_effect = httpx.HTTPStatusError(
        "Bad Request", request=MagicMock(), response=MagicMock(status_code=400, text="err"),
    )
    mock_async_client.return_value.__aenter__.return_value = mock_instance

    client = HTTPDAIClient()
    client._config = DAIConfig(
        backend=BackendType.http, endpoint="http://test", api_key="secret",
        on_error=ErrorPolicy.log_and_continue,
    )
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
    client._config = DAIConfig(
        backend=BackendType.http, endpoint="http://test", api_key="secret",
        on_error=ErrorPolicy.log_and_continue,
    )
    res = await client.verify_chain(datetime.now(UTC), datetime.now(UTC))
    assert not res.valid
    assert "Timeout" in res.message


@pytest.mark.asyncio
@patch("dai.client.httpx.AsyncClient")
async def test_http_client_get_latest_hash_error(mock_async_client):
    """get_latest_hash should return GENESIS_HASH on error (log_and_continue)."""
    import httpx
    from dai.models import GENESIS_HASH

    mock_instance = AsyncMock()
    mock_instance.request.side_effect = httpx.ConnectError("unreachable")
    mock_async_client.return_value.__aenter__.return_value = mock_instance

    client = HTTPDAIClient()
    client._config = DAIConfig(
        backend=BackendType.http, endpoint="http://test", api_key="secret",
        on_error=ErrorPolicy.log_and_continue, max_retries=1,
    )
    h = await client.get_latest_hash()
    assert h == GENESIS_HASH


@pytest.mark.asyncio
@patch("dai.client.httpx.AsyncClient")
async def test_http_client_get_latest_hash_error_raises(mock_async_client):
    """get_latest_hash should re-raise on raise_exception policy."""
    import httpx
    from dai.exceptions import ClientError

    mock_instance = AsyncMock()
    mock_instance.request.side_effect = httpx.ConnectError("unreachable")
    mock_async_client.return_value.__aenter__.return_value = mock_instance

    client = HTTPDAIClient()
    client._config = DAIConfig(
        backend=BackendType.http, endpoint="http://test", api_key="secret",
        on_error=ErrorPolicy.raise_exception, max_retries=1,
    )
    with pytest.raises(ClientError):
        await client.get_latest_hash()


# ── SQLiteDAIClient ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sqlite_client_commit_and_query(mock_record, tmp_path):
    db = str(tmp_path / "test.db")
    client = SQLiteDAIClient(db)

    res = await client.commit(mock_record)
    assert res.success
    assert res.decision_id == mock_record.decision_id

    recs = await client.query(QueryFilter())
    assert len(recs) == 1
    assert recs[0].decision_id == mock_record.decision_id


@pytest.mark.asyncio
async def test_sqlite_client_query_all_filters(mock_record, tmp_path):
    """Exercise every SQLiteDAIClient filter branch (outcome, exception, override, cursor, timestamps)."""
    db = str(tmp_path / "test.db")
    client = SQLiteDAIClient(db)
    await client.commit(mock_record)

    now = datetime.now(UTC)
    past = datetime(2000, 1, 1, tzinfo=UTC)

    # All optional clauses populated
    recs = await client.query(QueryFilter(
        agent_id="test-agent",
        decision_type="test",
        from_timestamp=past,
        to_timestamp=now,
        outcome="approved",
        exception_applied=False,
        override_applied=False,
    ))
    assert len(recs) == 1

    # Cursor skips everything past it
    recs = await client.query(QueryFilter(cursor="zzz-no-match"))
    assert recs == []

    # Outcome mismatch filtered
    recs = await client.query(QueryFilter(outcome="rejected"))
    assert recs == []

    # exception_applied mismatch
    recs = await client.query(QueryFilter(exception_applied=True))
    assert recs == []

    # override_applied mismatch
    recs = await client.query(QueryFilter(override_applied=True))
    assert recs == []


@pytest.mark.asyncio
async def test_sqlite_client_get_latest_hash_empty(tmp_path):
    from dai.models import GENESIS_HASH
    db = str(tmp_path / "test.db")
    client = SQLiteDAIClient(db)
    h = await client.get_latest_hash()
    assert h == GENESIS_HASH


@pytest.mark.asyncio
async def test_sqlite_client_get_latest_hash_with_record(mock_record, tmp_path):
    db = str(tmp_path / "test.db")
    client = SQLiteDAIClient(db)
    await client.commit(mock_record)
    h = await client.get_latest_hash()
    assert h == mock_record.record_hash


@pytest.mark.asyncio
async def test_sqlite_client_verify_chain(mock_record, tmp_path):
    db = str(tmp_path / "test.db")
    client = SQLiteDAIClient(db)
    await client.commit(mock_record)
    result = await client.verify_chain(
        datetime(2000, 1, 1, tzinfo=UTC), datetime(2100, 1, 1, tzinfo=UTC),
    )
    assert isinstance(result.valid, bool)


@pytest.mark.asyncio
async def test_sqlite_client_commit_error_handling(mock_record, tmp_path):
    """SQLite error on commit should be absorbed under log_and_continue."""
    from dai.config import configure, reset_config
    configure(on_error="log_and_continue")

    db = str(tmp_path / "test.db")
    client = SQLiteDAIClient(db)

    with patch("aiosqlite.connect", side_effect=Exception("disk full")):
        client._initialised = True  # skip _ensure_table
        res = await client.commit(mock_record)
    assert not res.success
    reset_config()


@pytest.mark.asyncio
async def test_sqlite_client_query_error_handling(tmp_path):
    """SQLite error on query should return [] under log_and_continue."""
    from dai.config import configure, reset_config
    configure(on_error="log_and_continue")

    db = str(tmp_path / "test.db")
    client = SQLiteDAIClient(db)
    client._initialised = True

    with patch("aiosqlite.connect", side_effect=Exception("disk error")):
        res = await client.query(QueryFilter())
    assert res == []
    reset_config()


# ── get_client / cache ─────────────────────────────────────────────────────────

def test_get_client():
    reset_client_cache()
    c1 = get_client(DAIConfig(backend=BackendType.noop))
    assert isinstance(c1, NoopDAIClient)
    c2 = get_client(DAIConfig(backend=BackendType.http))
    assert isinstance(c2, HTTPDAIClient)
    c3 = get_client(DAIConfig(backend=BackendType.sqlite))
    assert isinstance(c3, SQLiteDAIClient)
