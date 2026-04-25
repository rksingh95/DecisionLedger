"""
DAI Server — POST /ingest route
================================

Accepts a fully formed DecisionRecord (hash already computed by SDK),
validates chain continuity, and persists it to the database.
"""


import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from dai.hash_chain import GENESIS_HASH, compute_record_hash
from dai.models import DecisionRecord
from dai_server.client_models import CommitResponse
from dai_server.db.models import DecisionORM
from dai_server.db.session import get_db

router = APIRouter()


@router.post("/ingest", response_model=CommitResponse, tags=["Ingest"])
async def ingest_record(
    record: DecisionRecord,
    db: AsyncSession = Depends(get_db),
) -> CommitResponse:
    """
    Ingest a decision record into the ledger.

    Validates:
    1. Record hash integrity (recompute and compare).
    2. Hash chain continuity (previous_hash must match latest record's hash).

    Idempotent: if decision_id already exists, returns the existing record.
    """
    # 1. Check idempotency — if already ingested, return success
    existing = await db.get(DecisionORM, record.decision_id)
    if existing is not None:
        return CommitResponse(
            success=True,
            decision_id=existing.decision_id,
            record_hash=existing.record_hash,
        )

    # 2. Validate record hash
    try:
        expected_hash = compute_record_hash(record.previous_hash, record)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Hash computation failed: {exc}")

    if expected_hash != record.record_hash:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Record hash verification failed. "
                f"Expected {expected_hash[:16]}…, got {record.record_hash[:16]}…"
            ),
        )

    # 3. Check chain continuity
    latest_result = await db.execute(
        select(DecisionORM.record_hash)
        .order_by(DecisionORM.decision_timestamp.desc())
        .limit(1)
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

    # 4. Persist record
    orm = DecisionORM(
        decision_id=record.decision_id,
        record_hash=record.record_hash,
        previous_hash=record.previous_hash,
        ledger_version=record.ledger_version,
        decision_timestamp=record.decision_timestamp,
        commit_timestamp=datetime.now(timezone.utc),
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

    return CommitResponse(
        success=True,
        decision_id=record.decision_id,
        record_hash=record.record_hash,
    )
