"""Integration tests for hash chain verification using SQLite backend."""

from __future__ import annotations

from datetime import UTC, datetime

from dai.client import SQLiteDAIClient
from dai.hash_chain import GENESIS_HASH, prepare_record_for_commit
from dai.models import AgentType, ContextCompleteness, DecisionRecordCreate


def _make_create(subject_ref: str = "claim:001", **kwargs) -> DecisionRecordCreate:
    now = datetime.now(UTC)
    defaults = dict(
        agent_id="test-agent",
        agent_type=AgentType.autonomous,
        model_version="test-model",
        authorized_scope="test",
        delegation_source="test",
        decision_type="claims_triage",
        subject_ref=subject_ref,
        policy_id="test-policy",
        policy_version="1.0.0",
        policy_snapshot_at=now,
        outcome="approved",
        confidence=0.9,
        evidence_refs=["doc:001"],
        data_sources_accessed=["test-db"],
        context_completeness=ContextCompleteness.full,
    )
    defaults.update(kwargs)
    return DecisionRecordCreate(**defaults)


async def _build_chain(client: SQLiteDAIClient, n: int) -> list:
    records = []
    prev_hash = GENESIS_HASH
    for i in range(n):
        create = _make_create(subject_ref=f"claim:{i:04d}")
        record = prepare_record_for_commit(create, prev_hash)
        result = await client.commit(record)
        assert result.success
        records.append(record)
        prev_hash = record.record_hash
    return records


class TestChainVerification:
    async def test_genesis_chain_valid(self, tmp_path):
        client = SQLiteDAIClient(str(tmp_path / "test.db"))
        create = _make_create()
        record = prepare_record_for_commit(create, GENESIS_HASH)
        await client.commit(record)

        from dai.models import QueryFilter
        records = await client.query(QueryFilter(limit=100))
        from dai.hash_chain import verify_chain
        result = verify_chain(records)
        assert result.valid is True
        assert result.total_records == 1

    async def test_ten_record_chain_valid(self, tmp_path):
        client = SQLiteDAIClient(str(tmp_path / "test.db"))
        await _build_chain(client, 10)

        from dai.hash_chain import verify_chain
        from dai.models import QueryFilter
        records = await client.query(QueryFilter(limit=100))
        result = verify_chain(records)
        assert result.valid is True
        assert result.total_records == 10

    async def test_tamper_detected(self, tmp_path):
        import json

        import aiosqlite
        db_path = str(tmp_path / "test.db")
        client = SQLiteDAIClient(db_path)
        records = await _build_chain(client, 5)

        # Tamper with record 3 directly in the database
        target_id = records[2].decision_id
        async with aiosqlite.connect(db_path) as db:
            async with db.execute("SELECT full_record FROM decisions WHERE decision_id = ?", (target_id,)) as cursor:
                row = await cursor.fetchone()
            data = json.loads(row[0])
            data["outcome"] = "denied"  # Tamper
            await db.execute(
                "UPDATE decisions SET full_record = ? WHERE decision_id = ?",
                (json.dumps(data), target_id),
            )
            await db.commit()

        from dai.hash_chain import verify_chain
        from dai.models import QueryFilter
        fetched = await client.query(QueryFilter(limit=100))
        result = verify_chain(fetched)
        assert result.valid is False
        assert result.broken_at is not None

    async def test_empty_chain_valid(self, tmp_path):
        from dai.hash_chain import verify_chain
        result = verify_chain([])
        assert result.valid is True
        assert result.total_records == 0
