"""Integration tests for Article 19 export."""

from __future__ import annotations

from datetime import UTC, datetime

from dai.client import SQLiteDAIClient
from dai.hash_chain import GENESIS_HASH, prepare_record_for_commit, verify_chain
from dai.models import AgentType, ContextCompleteness, DecisionRecordCreate, ExceptionType
from dai_server.export.article19 import generate_article19_export


def _make_create(
    agent_id: str = "agent-a",
    outcome: str = "approved",
    policy_version: str = "3.2.1",
    exception: bool = False,
    override: bool = False,
    subject_ref: str = "claim:001",
) -> DecisionRecordCreate:
    now = datetime.now(UTC)
    return DecisionRecordCreate(
        agent_id=agent_id,
        agent_type=AgentType.autonomous,
        model_version="gpt-4o-2024-08-06",
        authorized_scope="triage",
        delegation_source="underwriting",
        decision_type="claims_triage",
        subject_ref=subject_ref,
        policy_id="motor-claims-v3",
        policy_version=policy_version,
        policy_snapshot_at=now,
        outcome=outcome,
        confidence=0.9,
        evidence_refs=["doc:form"],
        data_sources_accessed=["claims-db"],
        context_completeness=ContextCompleteness.full,
        exception_applied=exception,
        exception_type=ExceptionType.conservative_fallback if exception else None,
        override_applied=override,
        override_by="senior-underwriter" if override else None,
    )


class TestArticle19Export:
    async def test_article19_export_json(self, tmp_path):
        client = SQLiteDAIClient(str(tmp_path / "test.db"))
        prev = GENESIS_HASH
        outcomes = ["approved", "denied", "escalated"]
        exception_count = 0
        override_count = 0

        for i in range(50):
            outcome = outcomes[i % 3]
            is_exc = i % 7 == 0
            is_ovr = i % 11 == 0
            pv = "3.2.1" if i < 30 else "3.3.0"
            create = _make_create(
                outcome=outcome,
                exception=is_exc,
                override=is_ovr,
                policy_version=pv,
                subject_ref=f"claim:{i:04d}",
            )
            r = prepare_record_for_commit(create, prev)
            await client.commit(r)
            prev = r.record_hash
            if is_exc:
                exception_count += 1
            if is_ovr:
                override_count += 1

        from dai.models import QueryFilter

        records = await client.query(QueryFilter(limit=1000))
        assert len(records) == 50

        chain_result = verify_chain(records)
        from_ts = min(r.decision_timestamp for r in records)
        to_ts = max(r.decision_timestamp for r in records)
        export = generate_article19_export(records, from_ts, to_ts, chain_result)

        assert export.total_decisions == 50
        assert export.chain_integrity_valid is True
        assert len(export.policy_versions_used) == 2
        assert export.exception_count == exception_count
        assert export.override_count == override_count
        assert export.decisions_by_type.get("claims_triage", 0) == 50

    async def test_article19_text_report_format(self, tmp_path):
        client = SQLiteDAIClient(str(tmp_path / "test.db"))
        r = prepare_record_for_commit(_make_create(), GENESIS_HASH)
        await client.commit(r)

        from dai.models import QueryFilter

        records = await client.query(QueryFilter(limit=100))
        chain_result = verify_chain(records)
        from_ts = records[0].decision_timestamp
        to_ts = records[-1].decision_timestamp
        export = generate_article19_export(records, from_ts, to_ts, chain_result)
        report = export.to_text_report()

        assert "EU AI Act Article 19" in report
        assert "Chain integrity verified" in report
        assert "Total decisions recorded" in report
        assert "VERIFIED" in report

    async def test_article19_export_with_broken_chain(self, tmp_path):
        import json

        import aiosqlite

        db_path = str(tmp_path / "test.db")
        client = SQLiteDAIClient(db_path)
        prev = GENESIS_HASH
        records_list = []
        for i in range(5):
            r = prepare_record_for_commit(_make_create(subject_ref=f"claim:{i}"), prev)
            await client.commit(r)
            records_list.append(r)
            prev = r.record_hash

        # Tamper with record 2
        target_id = records_list[1].decision_id
        async with aiosqlite.connect(db_path) as db:
            async with db.execute(
                "SELECT full_record FROM decisions WHERE decision_id = ?", (target_id,)
            ) as cursor:
                row = await cursor.fetchone()
            data = json.loads(row[0])
            data["outcome"] = "denied"
            await db.execute(
                "UPDATE decisions SET full_record = ? WHERE decision_id = ?",
                (json.dumps(data), target_id),
            )
            await db.commit()

        from dai.models import QueryFilter

        records = await client.query(QueryFilter(limit=100))
        chain_result = verify_chain(records)
        from_ts = min(r.decision_timestamp for r in records)
        to_ts = max(r.decision_timestamp for r in records)
        export = generate_article19_export(records, from_ts, to_ts, chain_result)

        assert export.chain_integrity_valid is False
        assert "BROKEN" in export.to_text_report()
