"""Integration tests for ingest and query using SQLite backend."""

from __future__ import annotations

from datetime import UTC, datetime

from dai.client import SQLiteDAIClient
from dai.hash_chain import GENESIS_HASH, prepare_record_for_commit
from dai.models import AgentType, ContextCompleteness, DecisionRecordCreate, QueryFilter


def _make_create(**kwargs) -> DecisionRecordCreate:
    now = datetime.now(UTC)
    defaults = dict(
        agent_id="agent-a",
        agent_type=AgentType.autonomous,
        model_version="test-model",
        authorized_scope="test",
        delegation_source="test",
        decision_type="claims_triage",
        subject_ref="claim:001",
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


class TestIngestQuery:
    async def test_full_round_trip(self, tmp_path):
        client = SQLiteDAIClient(str(tmp_path / "test.db"))
        create = _make_create()
        record = prepare_record_for_commit(create, GENESIS_HASH)
        result = await client.commit(record)
        assert result.success
        assert result.decision_id == record.decision_id

        fetched = await client.query(QueryFilter(decision_id=record.decision_id))
        assert len(fetched) == 1
        assert fetched[0].decision_id == record.decision_id
        assert fetched[0].outcome == "approved"
        assert fetched[0].record_hash == record.record_hash

    async def test_query_by_agent_id(self, tmp_path):
        client = SQLiteDAIClient(str(tmp_path / "test.db"))
        prev = GENESIS_HASH
        for i in range(5):
            r = prepare_record_for_commit(
                _make_create(agent_id="agent-a", subject_ref=f"claim:{i}"), prev
            )
            await client.commit(r)
            prev = r.record_hash
        for i in range(5):
            r = prepare_record_for_commit(
                _make_create(agent_id="agent-b", subject_ref=f"claim:{i + 5}"), prev
            )
            await client.commit(r)
            prev = r.record_hash

        results_a = await client.query(QueryFilter(agent_id="agent-a", limit=100))
        results_b = await client.query(QueryFilter(agent_id="agent-b", limit=100))
        assert len(results_a) == 5
        assert len(results_b) == 5

    async def test_query_by_outcome(self, tmp_path):
        client = SQLiteDAIClient(str(tmp_path / "test.db"))
        prev = GENESIS_HASH
        outcomes = ["approved", "denied", "escalated"]
        for outcome in outcomes:
            r = prepare_record_for_commit(
                _make_create(outcome=outcome, subject_ref=f"claim:{outcome}"), prev
            )
            await client.commit(r)
            prev = r.record_hash

        denied = await client.query(QueryFilter(outcome="denied", limit=100))
        assert len(denied) == 1
        assert denied[0].outcome == "denied"

    async def test_exception_decision_round_trip(self, tmp_path):
        client = SQLiteDAIClient(str(tmp_path / "test.db"))
        from dai.models import ExceptionType

        create = _make_create(
            exception_applied=True,
            exception_type=ExceptionType.conservative_fallback,
        )
        record = prepare_record_for_commit(create, GENESIS_HASH)
        await client.commit(record)

        results = await client.query(QueryFilter(exception_applied=True, limit=100))
        assert len(results) == 1
        assert results[0].exception_applied is True

    async def test_cursor_pagination(self, tmp_path):
        client = SQLiteDAIClient(str(tmp_path / "test.db"))
        prev = GENESIS_HASH
        all_ids = []
        for i in range(25):
            r = prepare_record_for_commit(_make_create(subject_ref=f"claim:{i:03d}"), prev)
            await client.commit(r)
            all_ids.append(r.decision_id)
            prev = r.record_hash

        # Page 1
        page1 = await client.query(QueryFilter(limit=10))
        assert len(page1) == 10

        # Page 2
        page2 = await client.query(QueryFilter(limit=10, cursor=page1[-1].decision_id))
        # Page 3
        page3 = await client.query(QueryFilter(limit=10, cursor=page2[-1].decision_id))

        all_fetched = {r.decision_id for r in page1 + page2 + page3}
        assert len(all_fetched) == 25  # No duplicates, all covered

    async def test_idempotent_commit(self, tmp_path):
        client = SQLiteDAIClient(str(tmp_path / "test.db"))
        create = _make_create()
        record = prepare_record_for_commit(create, GENESIS_HASH)

        r1 = await client.commit(record)
        r2 = await client.commit(record)  # Same record again

        assert r1.success
        assert r2.success

        all_records = await client.query(QueryFilter(limit=100))
        assert len(all_records) == 1  # Only stored once
