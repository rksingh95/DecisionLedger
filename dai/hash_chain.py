"""
DAI Hash Chain Engine
=====================

SHA-256 hash chaining for tamper-evident decision records.

The algorithm:
    record_hash = SHA-256( previous_hash + ":" + canonical_json(record) )

Each record's hash depends on all previous records' content, so any
modification to a historical record invalidates the hashes of all
subsequent records. This makes tampering detectable.

Example — constructing and verifying a two-record chain::

    from datetime import datetime, timezone
    from dai.hash_chain import (
        GENESIS_HASH,
        prepare_record_for_commit,
        verify_chain,
    )
    from dai.models import DecisionRecordCreate, AgentType, ContextCompleteness

    now = datetime.now(timezone.utc)

    create1 = DecisionRecordCreate(
        agent_id="agent-01",
        decision_type="claims_triage",
        subject_ref="claim:001",
        policy_id="motor-v1",
        policy_version="1.0.0",
        policy_snapshot_at=now,
        authorized_scope="triage",
        delegation_source="underwriting",
        outcome="approved",
        confidence=0.92,
        evidence_refs=["doc:form-01"],
        data_sources_accessed=["claims-db"],
        context_completeness=ContextCompleteness.full,
    )

    record1 = prepare_record_for_commit(create1, GENESIS_HASH)
    record2 = prepare_record_for_commit(create1, record1.record_hash)

    result = verify_chain([record1, record2])
    assert result.valid
    assert result.total_records == 2
"""

import hashlib
from datetime import datetime, timezone

import uuid6  # type: ignore[import]

from dai.exceptions import HashChainError
from dai.models import (
    GENESIS_HASH,
    LEDGER_VERSION,
    ChainVerifyResult,
    DecisionRecord,
    DecisionRecordCreate,
)

HASH_ALGORITHM = "sha256"


# ─── Hash Computation ─────────────────────────────────────────────────────────


def compute_record_hash(previous_hash: str, record: DecisionRecord) -> str:
    """
    Compute the SHA-256 integrity hash for a decision record.

    Algorithm::

        payload = f"{previous_hash}:{canonical_json(record)}".encode("utf-8")
        hash = sha256(payload).hexdigest()

    Determinism guarantee:
        This function is deterministic across Python 3.13+ versions and
        operating systems because:

        1. ``to_canonical_json()`` uses ``json.dumps`` with ``sort_keys=True``
           — key order is always alphabetical regardless of dict insertion order.
        2. All datetime fields are serialised to ISO8601 strings via Pydantic's
           ``mode='json'`` export — no locale-sensitive formatting.
        3. Floats use Python's default repr, which is consistent across platforms
           for IEEE 754 double-precision values.
        4. The separator ``":"`` is a fixed ASCII character — no BOM, no locale.
        5. UTF-8 encoding is explicit — no system locale can change it.

        Things that WOULD break determinism (and are prevented):
        - Using ``dict.items()`` without sorting (prevented by sort_keys)
        - Locale-sensitive float formatting (Python's json module ignores locale)

    Args:
        previous_hash: The record_hash of the immediately preceding record,
            or GENESIS_HASH for the first record. Must be 64 hex characters.
        record: The DecisionRecord to hash. The record's own ``record_hash``
            field is excluded from the input (it is the output).

    Returns:
        64-character lowercase hex SHA-256 digest.

    Raises:
        HashChainError: If previous_hash is not exactly 64 lowercase hex chars.
    """
    if len(previous_hash) != 64 or not all(c in "0123456789abcdef" for c in previous_hash):
        raise HashChainError(
            f"previous_hash must be 64 lowercase hex characters, got: {previous_hash!r}",
            decision_id=record.decision_id,
        )

    canonical_json = record.to_canonical_json()
    payload = f"{previous_hash}:{canonical_json}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


# ─── Single Record Verification ───────────────────────────────────────────────


def verify_record(record: DecisionRecord, previous_hash: str) -> bool:
    """
    Verify that a single record's hash is correct given its predecessor's hash.

    Recomputes the expected hash and compares it to ``record.record_hash``.

    Args:
        record: The DecisionRecord to verify.
        previous_hash: The hash of the record that precedes this one in the chain,
            or GENESIS_HASH if this is the first record.

    Returns:
        True if the record is intact, False if it has been tampered with.
    """
    try:
        expected = compute_record_hash(previous_hash, record)
    except HashChainError:
        return False
    return expected == record.record_hash


# ─── Full Chain Verification ──────────────────────────────────────────────────


def verify_chain(records: list[DecisionRecord]) -> ChainVerifyResult:
    """
    Verify the integrity of an entire sequence of decision records.

    Records are sorted by ``decision_timestamp`` before verification (the
    input list is NOT mutated). Verification starts from GENESIS_HASH and
    walks forward through the chain.

    Edge cases:
    - Empty list: returns valid=True, total_records=0
    - Single record: verified against GENESIS_HASH
    - Out-of-order records: sorted internally before verification

    Args:
        records: List of DecisionRecord objects to verify. May be unsorted.

    Returns:
        ChainVerifyResult with valid=True if chain is intact, or valid=False
        with broken_at set to the decision_id of the first tampered record.
    """
    now = datetime.now(timezone.utc)

    if not records:
        return ChainVerifyResult(
            valid=True,
            total_records=0,
            broken_at=None,
            verified_at=now,
            message="Chain is valid. No records to verify.",
        )

    sorted_records = sorted(records, key=lambda r: r.decision_timestamp)
    previous_hash = GENESIS_HASH

    for record in sorted_records:
        try:
            expected_hash = compute_record_hash(previous_hash, record)
        except HashChainError as exc:
            return ChainVerifyResult(
                valid=False,
                total_records=len(sorted_records),
                broken_at=record.decision_id,
                verified_at=now,
                message=f"Hash computation failed at record {record.decision_id}: {exc.message}",
            )

        if expected_hash != record.record_hash:
            return ChainVerifyResult(
                valid=False,
                total_records=len(sorted_records),
                broken_at=record.decision_id,
                verified_at=now,
                message=(
                    f"Chain integrity violation at record {record.decision_id}. "
                    f"Expected hash {expected_hash[:16]}…, "
                    f"found {record.record_hash[:16]}…"
                ),
            )

        previous_hash = record.record_hash

    return ChainVerifyResult(
        valid=True,
        total_records=len(sorted_records),
        broken_at=None,
        verified_at=now,
        message=f"Chain is valid. {len(sorted_records)} record(s) verified.",
    )


# ─── Record Preparation ───────────────────────────────────────────────────────


def prepare_record_for_commit(
    create_request: DecisionRecordCreate,
    previous_hash: str,
    *,
    decision_id: str | None = None,
    now_override: datetime | None = None,
) -> DecisionRecord:
    """
    Create a fully populated, immutable DecisionRecord from a create request.

    This function is the bridge between the builder/client layer and the
    hash chain engine. It assigns all SDK-managed fields and computes the
    cryptographic hash.

    Steps:
        1. Generate a UUIDv7 decision_id (or use provided one)
        2. Set ledger_version = LEDGER_VERSION
        3. Set decision_timestamp = now(UTC) if not provided by caller
        4. Set commit_timestamp = now(UTC)
        5. Build a provisional DecisionRecord with record_hash=GENESIS_HASH
        6. Compute record_hash via compute_record_hash(previous_hash, provisional)
        7. Return final frozen DecisionRecord with correct hash

    Args:
        create_request: The caller-provided fields for this decision.
        previous_hash: Hash of the preceding record (or GENESIS_HASH).
        decision_id: Optional UUIDv7 string; generated if not provided.
        now_override: Optional datetime to use for timestamps (useful in tests).

    Returns:
        A fully populated, frozen (immutable) DecisionRecord.

    Raises:
        HashChainError: If previous_hash is invalid.
    """
    now = now_override or datetime.now(timezone.utc)
    uid = decision_id or str(uuid6.uuid7())
    decision_timestamp = create_request.decision_timestamp or now

    # Build a provisional record with placeholder hash so we can compute the real one.
    # We use GENESIS_HASH as a placeholder for record_hash (excluded from hash input).
    provisional = DecisionRecord(
        decision_id=uid,
        record_hash=GENESIS_HASH,  # placeholder — excluded from canonical JSON
        previous_hash=previous_hash,
        ledger_version=LEDGER_VERSION,
        decision_timestamp=decision_timestamp,
        policy_snapshot_at=create_request.policy_snapshot_at,
        commit_timestamp=now,
        agent_id=create_request.agent_id,
        agent_type=create_request.agent_type,
        model_version=create_request.model_version,
        deployment_id=create_request.deployment_id,
        authorized_scope=create_request.authorized_scope,
        delegation_source=create_request.delegation_source,
        human_oversight_required=create_request.human_oversight_required,
        override_applied=create_request.override_applied,
        override_by=create_request.override_by,
        override_justification=create_request.override_justification,
        decision_type=create_request.decision_type,
        subject_ref=create_request.subject_ref,
        policy_id=create_request.policy_id,
        policy_version=create_request.policy_version,
        clauses_applied=create_request.clauses_applied,
        outcome=create_request.outcome,
        confidence=create_request.confidence,
        alternatives_considered=create_request.alternatives_considered,
        evidence_refs=create_request.evidence_refs,
        data_sources_accessed=create_request.data_sources_accessed,
        context_completeness=create_request.context_completeness,
        exception_applied=create_request.exception_applied,
        exception_type=create_request.exception_type,
        exception_reason_code=create_request.exception_reason_code,
        metadata=create_request.metadata,
    )

    record_hash = compute_record_hash(previous_hash, provisional)

    # Return final immutable record with the real hash.
    return provisional.model_copy(update={"record_hash": record_hash})
