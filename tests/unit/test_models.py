"""Unit tests for dai/models.py"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from dai.models import (
    GENESIS_HASH,
    LEDGER_VERSION,
    AgentType,
    ContextCompleteness,
    DecisionRecord,
    ExceptionType,
    QueryFilter,
)


def _make_record(**kwargs) -> DecisionRecord:
    """Helper to build a minimal valid DecisionRecord."""
    now = datetime.now(UTC)
    defaults = dict(
        decision_id="01234567-89ab-7000-8000-000000000001",
        record_hash="a" * 64,
        previous_hash=GENESIS_HASH,
        ledger_version=LEDGER_VERSION,
        decision_timestamp=now,
        policy_snapshot_at=now,
        commit_timestamp=now,
        agent_id="test-agent",
        agent_type=AgentType.autonomous,
        model_version="gpt-4o-2024-08-06",
        authorized_scope="test-scope",
        delegation_source="test-delegation",
        human_oversight_required=False,
        override_applied=False,
        decision_type="test_decision",
        subject_ref="item:001",
        policy_id="test-policy",
        policy_version="1.0.0",
        outcome="approved",
        confidence=0.9,
        evidence_refs=["doc:001"],
        data_sources_accessed=["test-db"],
        context_completeness=ContextCompleteness.full,
        exception_applied=False,
    )
    defaults.update(kwargs)
    return DecisionRecord(**defaults)


class TestDecisionRecordValidation:
    def test_valid_record(self):
        r = _make_record()
        assert r.outcome == "approved"
        assert r.ledger_version == LEDGER_VERSION

    def test_confidence_below_zero_fails(self):
        with pytest.raises(ValidationError, match="confidence"):
            _make_record(confidence=-0.1)

    def test_confidence_above_one_fails(self):
        with pytest.raises(ValidationError, match="confidence"):
            _make_record(confidence=1.1)

    def test_confidence_boundary_values(self):
        assert _make_record(confidence=0.0).confidence == 0.0
        assert _make_record(confidence=1.0).confidence == 1.0

    def test_invalid_semver_policy_version(self):
        with pytest.raises(ValidationError, match="semver"):
            _make_record(policy_version="3.2")

    def test_invalid_ledger_version(self):
        with pytest.raises(ValidationError, match="ledger_version"):
            _make_record(ledger_version="9.9.9")

    def test_invalid_record_hash_length(self):
        with pytest.raises(ValidationError, match="64-character"):
            _make_record(record_hash="abc123")

    def test_invalid_record_hash_non_hex(self):
        with pytest.raises(ValidationError, match="64-character"):
            _make_record(record_hash="Z" * 64)

    def test_override_applied_requires_override_by(self):
        with pytest.raises(ValidationError, match="override_by"):
            _make_record(override_applied=True, override_by=None)

    def test_override_applied_with_override_by_passes(self):
        r = _make_record(
            override_applied=True,
            override_by="senior-underwriter:jane",
            override_justification=ExceptionType.manual_override,
        )
        assert r.override_applied is True

    def test_exception_applied_requires_exception_type(self):
        with pytest.raises(ValidationError, match="exception_type"):
            _make_record(exception_applied=True, exception_type=None)

    def test_evidence_refs_requires_at_least_one(self):
        with pytest.raises(ValidationError, match="evidence_refs"):
            _make_record(evidence_refs=[])

    def test_data_sources_requires_at_least_one(self):
        with pytest.raises(ValidationError, match="data_sources_accessed"):
            _make_record(data_sources_accessed=[])

    def test_metadata_non_string_value_fails(self):
        with pytest.raises(ValidationError, match="metadata"):
            _make_record(metadata={"key": 123})  # type: ignore

    def test_naive_datetime_fails(self):
        naive = datetime.now()  # no timezone
        with pytest.raises(ValidationError, match="timezone-aware"):
            _make_record(decision_timestamp=naive)

    def test_frozen_model_cannot_be_mutated(self):
        r = _make_record()
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            r.outcome = "denied"  # type: ignore


class TestCanonicalJson:
    def test_deterministic_across_calls(self):
        r = _make_record()
        j1 = r.to_canonical_json()
        j2 = r.to_canonical_json()
        assert j1 == j2

    def test_excludes_record_hash(self):
        r = _make_record()
        j = r.to_canonical_json()
        # record_hash should not appear in canonical JSON
        assert '"record_hash"' not in j

    def test_sorted_keys(self):
        import json
        r = _make_record()
        data = json.loads(r.to_canonical_json())
        keys = list(data.keys())
        assert keys == sorted(keys)


class TestQueryFilter:
    def test_default_limit(self):
        f = QueryFilter()
        assert f.limit == 100

    def test_limit_max_1000(self):
        with pytest.raises(ValidationError):
            QueryFilter(limit=1001)

    def test_limit_min_1(self):
        with pytest.raises(ValidationError):
            QueryFilter(limit=0)
