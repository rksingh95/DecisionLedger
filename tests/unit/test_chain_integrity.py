"""
P0.1-03 — Chain Integrity Hardening Tests
==========================================

Tests for:
- Canonical hash determinism across environments
- Chain break localisation (first_broken_decision_id, expected/actual hashes)
- Duplicate / replay detection (409 Conflict with classification)
- Tamper detection
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from dai.hash_chain import (
    GENESIS_HASH,
    canonical_json_for_hashing,
    compute_record_hash,
    prepare_record_for_commit,
    verify_chain,
)
from dai.models import (
    SCHEMA_VERSION,
    AgentType,
    ContextCompleteness,
    DecisionRecordCreate,
)

# ─── Fixtures ─────────────────────────────────────────────────────────────────


def _make_create(**kwargs) -> DecisionRecordCreate:
    now = datetime.now(UTC)
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


# ─── Canonical Hash Determinism ───────────────────────────────────────────────


class TestCanonicalHashDeterminism:
    """
    P0.1-03 requirement: canonical hashing must be deterministic across
    environments and invocations.
    """

    def test_canonical_json_keys_are_sorted(self):
        """JSON keys must be alphabetically sorted regardless of field declaration order."""
        record = prepare_record_for_commit(_make_create(), GENESIS_HASH)
        canon = canonical_json_for_hashing(record)
        parsed = json.loads(canon)
        keys = list(parsed.keys())
        assert keys == sorted(keys), "Canonical JSON keys must be alphabetically sorted"

    def test_canonical_json_excludes_record_hash(self):
        """record_hash must NOT appear in canonical JSON (it's the output, not input)."""
        record = prepare_record_for_commit(_make_create(), GENESIS_HASH)
        canon = canonical_json_for_hashing(record)
        parsed = json.loads(canon)
        assert "record_hash" not in parsed

    def test_canonical_json_normalises_utc_timezone(self):
        """Datetime fields must have 'Z' suffix, not '+00:00', for cross-platform stability."""
        record = prepare_record_for_commit(_make_create(), GENESIS_HASH)
        canon = canonical_json_for_hashing(record)
        # Must not contain '+00:00' — all UTC markers should be 'Z'
        assert "+00:00" not in canon, "Canonical JSON must normalise timezone to 'Z'"
        # Must contain 'Z' (all timestamps are UTC)
        assert "Z" in canon

    def test_same_input_produces_identical_hashes_1000_times(self):
        """Hash computation is deterministic: same record → same hash every time."""
        record = prepare_record_for_commit(_make_create(), GENESIS_HASH)
        hashes = {compute_record_hash(GENESIS_HASH, record) for _ in range(1000)}
        assert len(hashes) == 1, "Hash must be identical across 1000 invocations"

    def test_canonical_json_compact_no_spaces(self):
        """Canonical JSON must use compact separators (no extra spaces)."""
        record = prepare_record_for_commit(_make_create(), GENESIS_HASH)
        canon = canonical_json_for_hashing(record)
        # Should not have ': ' or ', ' — compact separators (',', ':')
        assert ": " not in canon
        assert ", " not in canon

    def test_different_records_produce_different_hashes(self):
        """Two records with any content difference must have different hashes."""
        r1 = prepare_record_for_commit(_make_create(outcome="approved"), GENESIS_HASH)
        r2 = prepare_record_for_commit(_make_create(outcome="denied"), GENESIS_HASH)
        assert r1.record_hash != r2.record_hash

    def test_schema_version_in_canonical_json(self):
        """schema_version must be present in canonical JSON for replay context."""
        record = prepare_record_for_commit(_make_create(), GENESIS_HASH)
        canon = canonical_json_for_hashing(record)
        parsed = json.loads(canon)
        assert "schema_version" in parsed
        assert parsed["schema_version"] == SCHEMA_VERSION


# ─── Chain Break Localisation ─────────────────────────────────────────────────


class TestChainBreakLocalisation:
    """
    P0.1-03 requirement: verify_chain must return the exact location of any
    chain break, along with the expected and actual previous hashes.
    """

    def test_valid_chain_returns_no_localisation_fields(self):
        """A valid chain must return None for all break-localisation fields."""
        r1 = prepare_record_for_commit(_make_create(), GENESIS_HASH)
        r2 = prepare_record_for_commit(_make_create(subject_ref="claim:002"), r1.record_hash)
        result = verify_chain([r1, r2])

        assert result.valid is True
        assert result.first_broken_decision_id is None
        assert result.expected_previous_hash is None
        assert result.actual_previous_hash is None

    def test_tampered_record_returns_first_broken_decision_id(self):
        """Tampered record must be identified by decision_id in the result."""
        r1 = prepare_record_for_commit(_make_create(), GENESIS_HASH)
        r2 = prepare_record_for_commit(_make_create(subject_ref="claim:002"), r1.record_hash)
        r3 = prepare_record_for_commit(_make_create(subject_ref="claim:003"), r2.record_hash)

        # Tamper r2 (change outcome without recomputing hash)
        tampered_r2 = r2.model_copy(update={"outcome": "denied"})

        result = verify_chain([r1, tampered_r2, r3])

        assert result.valid is False
        assert result.first_broken_decision_id == r2.decision_id
        assert result.broken_at == r2.decision_id  # Legacy field still set

    def test_expected_and_actual_previous_hash_populated_on_break(self):
        """On chain break, expected_previous_hash and actual_previous_hash must be set."""
        r1 = prepare_record_for_commit(_make_create(), GENESIS_HASH)
        r2 = prepare_record_for_commit(_make_create(subject_ref="claim:002"), r1.record_hash)

        # Tamper r2
        tampered = r2.model_copy(update={"outcome": "denied"})

        result = verify_chain([r1, tampered])

        assert result.expected_previous_hash is not None
        assert result.actual_previous_hash is not None
        # expected_previous_hash is what the verifier tracked (r1.record_hash)
        assert result.expected_previous_hash == r1.record_hash
        # actual_previous_hash is what's stored in the (tampered) record
        assert result.actual_previous_hash == tampered.previous_hash

    def test_first_record_break_points_to_genesis(self):
        """If the first record is tampered, expected_previous_hash should be GENESIS_HASH."""
        r1 = prepare_record_for_commit(_make_create(), GENESIS_HASH)
        tampered = r1.model_copy(update={"outcome": "denied"})

        result = verify_chain([tampered])

        assert result.valid is False
        assert result.expected_previous_hash == GENESIS_HASH

    def test_chain_break_only_reports_first_broken_not_all(self):
        """Only the FIRST broken record is returned, not all subsequent broken records."""
        r1 = prepare_record_for_commit(_make_create(), GENESIS_HASH)
        r2 = prepare_record_for_commit(_make_create(subject_ref="claim:002"), r1.record_hash)
        r3 = prepare_record_for_commit(_make_create(subject_ref="claim:003"), r2.record_hash)

        # Tamper both r1 and r2
        tampered_r1 = r1.model_copy(update={"outcome": "denied"})
        tampered_r2 = r2.model_copy(update={"outcome": "denied"})

        result = verify_chain([tampered_r1, tampered_r2, r3])

        assert result.valid is False
        # First broken is r1 (earliest in chain), not r2
        assert result.first_broken_decision_id == r1.decision_id

    def test_empty_chain_returns_all_none_localisation(self):
        """Empty chain must return None for all localisation fields."""
        result = verify_chain([])
        assert result.valid is True
        assert result.first_broken_decision_id is None
        assert result.expected_previous_hash is None
        assert result.actual_previous_hash is None


# ─── Schema Version ───────────────────────────────────────────────────────────


class TestSchemaVersion:
    """
    P0.1-03 requirement: schema_version is set on all records for future
    replay compatibility.
    """

    def test_record_has_schema_version(self):
        """All records prepared by SDK must carry schema_version."""
        record = prepare_record_for_commit(_make_create(), GENESIS_HASH)
        assert record.schema_version == SCHEMA_VERSION

    def test_schema_version_default_value(self):
        """schema_version default is '0.1.1' (P0.1 bump)."""
        assert SCHEMA_VERSION == "0.1.1"

    def test_schema_version_included_in_hash_input(self):
        """schema_version change must produce different hash (it's in canonical JSON)."""
        record = prepare_record_for_commit(_make_create(), GENESIS_HASH)
        # Simulate a record with different schema_version
        record_v2 = record.model_copy(update={"schema_version": "0.2.0"})
        # Recompute hash — should differ
        hash_v1 = compute_record_hash(GENESIS_HASH, record)
        hash_v2 = compute_record_hash(GENESIS_HASH, record_v2)
        assert hash_v1 != hash_v2, "schema_version must affect the record hash"


# ─── Tamper Detection ─────────────────────────────────────────────────────────


class TestTamperDetection:
    """Ensure any field modification is caught by the hash chain."""

    @pytest.mark.parametrize(
        "field,tampered_value",
        [
            ("outcome", "denied"),
            ("confidence", 0.1),
            ("agent_id", "attacker-agent"),
            ("policy_version", "9.9.9"),
            ("decision_type", "fraud"),
        ],
    )
    def test_field_tampering_detected(self, field: str, tampered_value: object):
        """Any field modification must invalidate the record's hash."""
        record = prepare_record_for_commit(_make_create(), GENESIS_HASH)
        tampered = record.model_copy(update={field: tampered_value})
        result = verify_chain([tampered])
        assert result.valid is False, f"Tampering {field!r} must be detected"
        assert result.first_broken_decision_id == record.decision_id
