"""
DAI Client Layer
================

Three transport backends behind a unified async interface.

    from dai.client import get_client
    client = get_client()
    result = await client.commit(record)
"""
import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from dai.config import BackendType, ErrorPolicy, get_config
from dai.exceptions import ClientError
from dai.models import GENESIS_HASH, ChainVerifyResult, DecisionRecord, QueryFilter

logger = logging.getLogger("dai.client")


@dataclass
class CommitResult:
    """Result of committing a decision record."""
    success: bool
    decision_id: str | None = None
    record_hash: str | None = None
    error: str | None = None
    latency_ms: float = 0.0


class BaseDAIClient(ABC):
    @abstractmethod
    async def commit(self, record: DecisionRecord) -> CommitResult: ...
    @abstractmethod
    async def query(self, filters: QueryFilter) -> list[DecisionRecord]: ...
    @abstractmethod
    async def verify_chain(self, from_ts: datetime, to_ts: datetime) -> ChainVerifyResult: ...
    @abstractmethod
    async def get_latest_hash(self) -> str: ...


class HTTPDAIClient(BaseDAIClient):
    """Sends records to the DAI server via HTTP with retry."""

    def __init__(self) -> None:
        self._config = get_config()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
        }

    async def _request(self, method: str, url: str, *, content: str | None = None, params: dict | None = None) -> httpx.Response:
        last_err: Exception | None = None
        async with httpx.AsyncClient(timeout=self._config.timeout_seconds) as client:
            for attempt in range(self._config.max_retries):
                try:
                    resp = await client.request(method, url, headers=self._headers(), content=content, params=params)
                    resp.raise_for_status()
                    return resp
                except Exception as exc:
                    last_err = exc
                    if attempt < self._config.max_retries - 1:
                        await asyncio.sleep(self._config.retry_backoff_seconds * (2 ** attempt))
        raise ClientError(f"Request to {url} failed after {self._config.max_retries} attempts: {last_err}")

    async def commit(self, record: DecisionRecord) -> CommitResult:
        t0 = time.monotonic()
        url = f"{self._config.endpoint}/ingest"
        try:
            resp = await self._request("POST", url, content=record.model_dump_json())
            data = resp.json()
            if self._config.emit_opentelemetry_spans:
                try:
                    from dai.integrations.opentelemetry import emit_decision_span
                    emit_decision_span(record)
                except Exception:
                    pass
            return CommitResult(success=True, decision_id=data.get("decision_id", record.decision_id), record_hash=data.get("record_hash", record.record_hash), latency_ms=(time.monotonic() - t0) * 1000)
        except Exception as exc:
            latency_ms = (time.monotonic() - t0) * 1000
            logger.error("DAI commit failed: %s", exc)
            if self._config.on_error == ErrorPolicy.raise_exception:
                raise
            return CommitResult(success=False, error=str(exc), latency_ms=latency_ms)

    async def query(self, filters: QueryFilter) -> list[DecisionRecord]:
        url = f"{self._config.endpoint}/decisions"
        params: dict = {"limit": filters.limit}
        if filters.decision_id: params["decision_id"] = filters.decision_id
        if filters.agent_id: params["agent_id"] = filters.agent_id
        if filters.decision_type: params["decision_type"] = filters.decision_type
        if filters.from_timestamp: params["from_timestamp"] = filters.from_timestamp.isoformat()
        if filters.to_timestamp: params["to_timestamp"] = filters.to_timestamp.isoformat()
        if filters.outcome: params["outcome"] = filters.outcome
        if filters.exception_applied is not None: params["exception_applied"] = str(filters.exception_applied).lower()
        if filters.override_applied is not None: params["override_applied"] = str(filters.override_applied).lower()
        if filters.cursor: params["cursor"] = filters.cursor
        try:
            resp = await self._request("GET", url, params=params)
            return [DecisionRecord(**r) for r in resp.json().get("records", [])]
        except Exception as exc:
            logger.error("DAI query failed: %s", exc)
            if self._config.on_error == ErrorPolicy.raise_exception:
                raise
            return []

    async def verify_chain(self, from_ts: datetime, to_ts: datetime) -> ChainVerifyResult:
        url = f"{self._config.endpoint}/verify"
        params = {"from_timestamp": from_ts.isoformat(), "to_timestamp": to_ts.isoformat()}
        try:
            resp = await self._request("GET", url, params=params)
            return ChainVerifyResult(**resp.json())
        except Exception as exc:
            logger.error("DAI verify failed: %s", exc)
            if self._config.on_error == ErrorPolicy.raise_exception:
                raise
            return ChainVerifyResult(valid=False, total_records=0, verified_at=datetime.now(timezone.utc), message=str(exc))

    async def get_latest_hash(self) -> str:
        url = f"{self._config.endpoint}/decisions/latest-hash"
        try:
            resp = await self._request("GET", url)
            return resp.json().get("hash", GENESIS_HASH)
        except Exception as exc:
            logger.error("DAI get_latest_hash failed: %s", exc)
            if self._config.on_error == ErrorPolicy.raise_exception:
                raise
            return GENESIS_HASH


class SQLiteDAIClient(BaseDAIClient):
    """Stores records in a local SQLite database. Good for dev/testing."""

    _CREATE_TABLE = """
        CREATE TABLE IF NOT EXISTS decisions (
            decision_id TEXT PRIMARY KEY,
            record_hash TEXT NOT NULL UNIQUE,
            previous_hash TEXT NOT NULL,
            decision_timestamp TEXT NOT NULL,
            decision_type TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            full_record TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._lock = asyncio.Lock()
        self._initialised = False

    async def _ensure_table(self) -> None:
        if self._initialised:
            return
        async with self._lock:
            if self._initialised:
                return
            import aiosqlite
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(self._CREATE_TABLE)
                await db.commit()
            self._initialised = True

    async def commit(self, record: DecisionRecord) -> CommitResult:
        await self._ensure_table()
        t0 = time.monotonic()
        try:
            import aiosqlite
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(
                    "INSERT OR IGNORE INTO decisions (decision_id, record_hash, previous_hash, decision_timestamp, decision_type, agent_id, full_record, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (record.decision_id, record.record_hash, record.previous_hash, record.decision_timestamp.isoformat(), record.decision_type, record.agent_id, record.model_dump_json(), datetime.now(timezone.utc).isoformat()),
                )
                await db.commit()
            return CommitResult(success=True, decision_id=record.decision_id, record_hash=record.record_hash, latency_ms=(time.monotonic() - t0) * 1000)
        except Exception as exc:
            latency_ms = (time.monotonic() - t0) * 1000
            logger.error("SQLite commit failed: %s", exc)
            cfg = get_config()
            if cfg.on_error == ErrorPolicy.raise_exception:
                raise
            return CommitResult(success=False, error=str(exc), latency_ms=latency_ms)

    async def query(self, filters: QueryFilter) -> list[DecisionRecord]:
        await self._ensure_table()
        clauses: list[str] = []
        params: list = []
        if filters.decision_id: clauses.append("decision_id = ?"); params.append(filters.decision_id)
        if filters.agent_id: clauses.append("agent_id = ?"); params.append(filters.agent_id)
        if filters.decision_type: clauses.append("decision_type = ?"); params.append(filters.decision_type)
        if filters.from_timestamp: clauses.append("decision_timestamp >= ?"); params.append(filters.from_timestamp.isoformat())
        if filters.to_timestamp: clauses.append("decision_timestamp <= ?"); params.append(filters.to_timestamp.isoformat())
        if filters.cursor: clauses.append("decision_id > ?"); params.append(filters.cursor)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT full_record FROM decisions {where} ORDER BY decision_timestamp, decision_id LIMIT ?"
        params.append(filters.limit)
        try:
            import aiosqlite
            async with aiosqlite.connect(self._db_path) as db:
                async with db.execute(sql, params) as cursor:
                    rows = await cursor.fetchall()
            records = []
            for (full_record,) in rows:
                data = json.loads(full_record)
                if filters.outcome and data.get("outcome") != filters.outcome:
                    continue
                if filters.exception_applied is not None and data.get("exception_applied") != filters.exception_applied:
                    continue
                if filters.override_applied is not None and data.get("override_applied") != filters.override_applied:
                    continue
                records.append(DecisionRecord(**data))
            return records
        except Exception as exc:
            logger.error("SQLite query failed: %s", exc)
            cfg = get_config()
            if cfg.on_error == ErrorPolicy.raise_exception:
                raise
            return []

    async def verify_chain(self, from_ts: datetime, to_ts: datetime) -> ChainVerifyResult:
        from dai.hash_chain import verify_chain as _vc
        records = await self.query(QueryFilter(from_timestamp=from_ts, to_timestamp=to_ts, limit=1000))
        return _vc(records)

    async def get_latest_hash(self) -> str:
        await self._ensure_table()
        try:
            import aiosqlite
            async with aiosqlite.connect(self._db_path) as db:
                async with db.execute("SELECT record_hash FROM decisions ORDER BY decision_timestamp DESC LIMIT 1") as cursor:
                    row = await cursor.fetchone()
            return row[0] if row else GENESIS_HASH
        except Exception:
            return GENESIS_HASH


class NoopDAIClient(BaseDAIClient):
    """Discards all records silently. Used for testing."""
    async def commit(self, record: DecisionRecord) -> CommitResult:
        return CommitResult(success=True, decision_id=record.decision_id, record_hash=record.record_hash)
    async def query(self, filters: QueryFilter) -> list[DecisionRecord]:
        return []
    async def verify_chain(self, from_ts: datetime, to_ts: datetime) -> ChainVerifyResult:
        return ChainVerifyResult(valid=True, total_records=0, verified_at=datetime.now(timezone.utc), message="Noop client.")
    async def get_latest_hash(self) -> str:
        return GENESIS_HASH


_client_cache: dict[BackendType, BaseDAIClient] = {}


def get_client(config=None) -> BaseDAIClient:
    """Return the appropriate DAI client for the current configuration."""
    from dai.config import get_config as _gc
    cfg = config or _gc()
    if cfg.backend not in _client_cache:
        if cfg.backend == BackendType.http:
            _client_cache[cfg.backend] = HTTPDAIClient()
        elif cfg.backend == BackendType.sqlite:
            _client_cache[cfg.backend] = SQLiteDAIClient(cfg.sqlite_path)
        else:
            _client_cache[cfg.backend] = NoopDAIClient()
    return _client_cache[cfg.backend]


def reset_client_cache() -> None:
    """Clear the client cache. Used in tests."""
    global _client_cache
    _client_cache = {}
