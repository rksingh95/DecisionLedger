"""Unit tests for dai/hash_chain.py"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from dai.hash_chain import (
    GENESIS_HASH,
    compute_record_hash,
    prepare_record_for_commit,
    verify_chain,
    verify_record,
)
from dai.models import (
    LEDGER_VERSION,
    AgentType,
    ChainVerifyResult,
    ContextCompleteness,
    DecisionRecord,
    DecisionRecordCreate,
)
from dai.exceptions import HashChainError


def _make_create(**kwargs) -> DecisionRecordCreate:
    now = datetime.now(timezone.utc)
    defaults = dict(
        agent_id="test-agent",
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


class TestComputeRecordHash:
    def test_genesis_hash_computation(self):
        create = _make_create()
        record = prepare_record_for_commit(create, GENESIS_HASH)
        expected = compute_record_hash(GENESIS_HASH, record)
        assert expected == record.record_hash

    def test_hash_is_64_hex_chars(self):
        create = _make_create()
        record = prepare_record_for_commit(create, GENESIS_HASH)
        assert len(record.record_hash) == 64
        assert all(c in "0123456789abcdef" for c in record.record_hash)

    def test_invalid_previous_hash_raises(self):
        create = _make_create()
        record = prepare_record_for_commit(create, GENESIS_HASH)
        with pytest.raises(HashChainError):
            compute_record_hash("invalid-hash", record)

    def test_different_records_produce_different_hashes(self):
        r1 = prepare_record_for_commit(_make_create(subject_ref="claim:001"), GENESIS_HASH)
        r2 = prepare_record_for_commit(_make_create(subject_ref="claim:002"), GENESIS_HASH)
        assert r1.record_hash != r2.record_hash


class TestDeterminism:
    def test_same_input_same_hash_1000_times(self):
        create = _make_create()
        record = prepare_record_for_commit(create, GENESIS_HASH)
        hashes = {compute_record_hash(GENESIS_HASH, record) for _ in range(1000)}
        assert len(hashes) == 1  # All identical


class TestVerifyRecord:
    def test_unmodified_record_verifies(self):
        create = _make_create()
        record = prepare_record_for_commit(create, GENESIS_HASH)
        assert verify_record(record, GENESIS_HASH) is True

    def test_tampered_outcome_fails_verification(self):
        create = _make_create()
        record = prepare_record_for_commit(create, GENESIS_HASH)
        # Tamper: use model_copy to change outcome (frozen but copy allowed)
        tampered = record.model_copy(update={"outcome": "denied"})
        assert verify_record(tampered, GENESIS_HASH) is False


class TestVerifyChain:
    def test_empty_chain_is_valid(self):
        result = verify_chain([])
        assert result.valid is True
        assert result.total_records == 0

    def test_single_record_chain(self):
        create = _make_create()
        record = prepare_record_for_commit(create, GENESIS_HASH)
        result = verify_chain([record])
        assert result.valid is True
        assert result.total_records == 1

    def test_two_record_chain(self):
        r1 = prepare_record_for_commit(_make_create(), GENESIS_HASH)
        r2 = prepare_record_for_commit(_make_create(), r1.record_hash)
        result = verify_chain([r1, r2])
        assert result.valid is True
        assert result.total_records == 2

    def test_ten_record_chain(self):
        records = []
        prev_hash = GENESIS_HASH
        for i in range(10):
            r = prepare_record_for_commit(_make_create(subject_ref=f"claim:{i:03d}"), prev_hash)
            records.append(r)
            prev_hash = r.record_hash
        result = verify_chain(records)
        assert result.valid is True
        assert result.total_records == 10

    def test_tampered_record_breaks_chain(self):
        r1 = prepare_record_for_commit(_make_create(), GENESIS_HASH)
        r2 = prepare_record_for_commit(_make_create(), r1.record_hash)
        r3 = prepare_record_for_commit(_make_create(), r2.record_hash)

        # Tamper with r2
        tampered_r2 = r2.model_copy(update={"outcome": "denied"})
        # r3's previous_hash still points to original r2 — this creates a chain break

        result = verify_chain([r1, tampered_r2, r3])
        assert result.valid is False
        assert result.broken_at is not None

    def test_chain_is_sorted_before_verification(self):
        """Records given out of order should still verify correctly."""
        r1 = prepare_record_for_commit(_make_create(), GENESIS_HASH)
        r2 = prepare_record_for_commit(_make_create(), r1.record_hash)
        # Pass in reverse order
        result = verify_chain([r2, r1])
        assert result.valid is True

    def test_chain_integrity_broken_at_contains_decision_id(self):
        r1 = prepare_record_for_commit(_make_create(), GENESIS_HASH)
        tampered = r1.model_copy(update={"outcome": "denied"})
        result = verify_chain([tampered])
        assert result.valid is False
        assert result.broken_at == r1.decision_id
