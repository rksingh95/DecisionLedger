"""
DAI Server — Chain verification routes
"""


import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dai.hash_chain import verify_chain, verify_record
from dai.models import GENESIS_HASH, ChainVerifyResult, DecisionRecord
from dai_server.db.models import DecisionORM
from dai_server.db.session import get_db

router = APIRouter()


@router.get("/verify", response_model=ChainVerifyResult, tags=["Verify"])
async def verify_chain_range(
    from_timestamp: datetime = Query(...),
    to_timestamp: datetime = Query(...),
    agent_id: str | None = Query(None),
    decision_type: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> ChainVerifyResult:
    """
    Verify hash chain integrity over a time range.

    Fetches all records in the range (ordered by timestamp) and runs the
    full chain verification algorithm.
    """
    stmt = (
        select(DecisionORM)
        .where(
            DecisionORM.decision_timestamp >= from_timestamp,
            DecisionORM.decision_timestamp <= to_timestamp,
        )
        .order_by(DecisionORM.decision_timestamp)
    )
    if agent_id:
        stmt = stmt.where(DecisionORM.agent_id == agent_id)
    if decision_type:
        stmt = stmt.where(DecisionORM.decision_type == decision_type)

    result = await db.execute(stmt)
    rows = result.scalars().all()
    records = [DecisionRecord(**json.loads(r.full_record_json)) for r in rows]
    return verify_chain(records)


@router.get("/decisions/{decision_id}/verify", tags=["Verify"])
async def verify_single_record(
    decision_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Verify a single record's integrity.

    Fetches the record and its predecessor, recomputes the hash, and
    returns whether the record is intact.
    """
    orm = await db.get(DecisionORM, decision_id)
    if orm is None:
        raise HTTPException(status_code=404, detail=f"Decision {decision_id!r} not found")

    record = DecisionRecord(**json.loads(orm.full_record_json))

    # Fetch predecessor's hash
    if record.previous_hash == GENESIS_HASH:
        previous_hash = GENESIS_HASH
    else:
        pred_result = await db.execute(
            select(DecisionORM.record_hash)
            .where(DecisionORM.record_hash == record.previous_hash)
        )
        pred_hash = pred_result.scalar_one_or_none()
        if pred_hash is None:
            return {
                "valid": False,
                "decision_id": decision_id,
                "message": f"Predecessor record with hash {record.previous_hash[:16]}… not found",
            }
        previous_hash = pred_hash

    valid = verify_record(record, previous_hash)
    return {
        "valid": valid,
        "decision_id": decision_id,
        "message": "Record integrity verified" if valid else "Record has been tampered with",
    }
