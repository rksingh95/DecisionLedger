"""
DAI Server — POST /ingest route
================================

Accepts a fully formed DecisionRecord (hash already computed by SDK),
validates chain continuity, and persists it to the database.

P0.1-03: Duplicate/replay detection added.
  - App-layer pre-check before DB INSERT (fast path)
  - Returns HTTP 409 Conflict with duplicate_reason classification
  - DB unique constraint on decision_id remains as last-line defence
  - Duplicate reasons: idempotent_retry | duplicate_submission | suspected_replay_attack

Security note:
  A duplicate decision_id is not merely a client bug. It may indicate:
  - Innocent retry: same record re-submitted (idempotent_retry)
  - Client bug: duplicate build-and-submit (duplicate_submission)
  - Replay attack: old signed record resubmitted to forge audit trail
  We log and classify all three. Only idempotent_retry is silently accepted.
"""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dai.hash_chain import GENESIS_HASH, compute_record_hash
from dai.models import DecisionRecord
from dai_server.client_models import CommitResponse
from dai_server.db.models import DecisionORM
from dai_server.db.session import get_db

router = APIRouter()
logger = logging.getLogger("dai_server.ingest")


def _classify_duplicate_reason(
    existing: DecisionORM,
    record: DecisionRecord,
) -> str:
    """
    Classify why a duplicate decision_id was submitted.

    Returns a structured reason code for logging and the 409 response body.
    This is security-relevant classification — not just developer ergonomics.

    Logic:
    - If the record_hash matches exactly: idempotent_retry
      (same record, safe — likely a network retry)
    - If the record_hash differs but decision_id matches: suspected_replay_attack
      (decision_id reused with different content — high risk)
    - If the timestamps are very close (< 5s): duplicate_submission
      (likely a double-click / client bug)
    """
    now = datetime.now(UTC)
    commit_age_seconds = (
        (now - existing.decision_timestamp.replace(tzinfo=UTC)).total_seconds()
        if existing.decision_timestamp
        else 999
    )

    if existing.record_hash == record.record_hash:
        return "idempotent_retry"
    if commit_age_seconds < 5:
        return "duplicate_submission"
    return "suspected_replay_attack"


@router.post("/ingest", response_model=CommitResponse, tags=["Ingest"])
async def ingest_record(
    record: DecisionRecord,
    db: AsyncSession = Depends(get_db),
) -> CommitResponse | JSONResponse:
    """
    Ingest a decision record into the ledger.

    Validates:
    1. Duplicate detection — 409 if decision_id already exists (P0.1-03)
    2. Record hash integrity (recompute and compare).
    3. Hash chain continuity (previous_hash must match latest record's hash).

    P0.1-03: Duplicates are classified and returned as 409 Conflict, not 200.
    Only idempotent retries (exact same record_hash) return 200.
    """
    # ── 1. Duplicate / Replay Detection (P0.1-03) ────────────────────────────
    existing = await db.get(DecisionORM, record.decision_id)
    if existing is not None:
        reason = _classify_duplicate_reason(existing, record)

        if reason == "idempotent_retry":
            # Exact same record resubmitted — safe, return cached result
            logger.info(
                "Idempotent retry for decision_id=%s — returning cached result",
                record.decision_id,
            )
            return CommitResponse(
                success=True,
                decision_id=existing.decision_id,
                record_hash=existing.record_hash,
            )

        # Non-idempotent duplicate: reject with 409
        logger.warning(
            "Duplicate decision_id detected: decision_id=%s reason=%s",
            record.decision_id,
            reason,
        )
        return JSONResponse(
            status_code=409,
            content={
                "error": "duplicate_decision_id",
                "duplicate_reason": reason,
                "decision_id": record.decision_id,
                "message": (
                    f"Decision '{record.decision_id}' already exists in the ledger. "
                    f"Classification: {reason}. "
                    "If this is a legitimate retry, ensure record_hash is identical."
                ),
            },
        )

    # ── 2. Validate Record Hash ──────────────────────────────────────────────
    try:
        expected_hash = compute_record_hash(record.previous_hash, record)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Hash computation failed: {exc}") from exc

    if expected_hash != record.record_hash:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Record hash verification failed. "
                f"Expected {expected_hash[:16]}…, got {record.record_hash[:16]}…"
            ),
        )

    # ── 3. Hash Chain Continuity ─────────────────────────────────────────────
    latest_result = await db.execute(
        select(DecisionORM.record_hash).order_by(DecisionORM.decision_timestamp.desc()).limit(1)
    )
    latest_row = latest_result.scalar_one_or_none()
    expected_previous = latest_row if latest_row else GENESIS_HASH

    if record.previous_hash != expected_previous:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Hash chain continuity violation. "
                f"Expected previous_hash {expected_previous[:16]}…, "
                f"got {record.previous_hash[:16]}…"
            ),
        )

    # ── 4. Persist Record ────────────────────────────────────────────────────
    orm = DecisionORM(
        decision_id=record.decision_id,
        record_hash=record.record_hash,
        previous_hash=record.previous_hash,
        ledger_version=record.ledger_version,
        decision_timestamp=record.decision_timestamp,
        commit_timestamp=datetime.now(UTC),
        agent_id=record.agent_id,
        agent_type=record.agent_type.value,
        model_version=record.model_version,
        deployment_id=record.deployment_id,
        decision_type=record.decision_type,
        subject_ref=record.subject_ref,
        policy_id=record.policy_id,
        policy_version=record.policy_version,
        outcome=record.outcome,
        confidence=record.confidence,
        exception_applied=record.exception_applied,
        override_applied=record.override_applied,
        full_record_json=record.model_dump_json(),
    )
    db.add(orm)
    await db.flush()

    logger.info(
        "Ingested decision_id=%s agent=%s type=%s outcome=%s",
        record.decision_id,
        record.agent_id,
        record.decision_type,
        record.outcome,
    )

    return CommitResponse(
        success=True,
        decision_id=record.decision_id,
        record_hash=record.record_hash,
    )
