"""
DAI Server — GET /decisions and related query routes
"""


import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dai.models import GENESIS_HASH, DecisionRecord
from dai_server.db.models import DecisionORM
from dai_server.db.session import get_db

router = APIRouter()


@router.get("/decisions/latest-hash", tags=["Query"])
async def get_latest_hash(db: AsyncSession = Depends(get_db)) -> dict:
    """Return the record_hash of the most recent decision record."""
    result = await db.execute(
        select(DecisionORM.record_hash)
        .order_by(DecisionORM.decision_timestamp.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    return {"hash": row if row else GENESIS_HASH}


@router.get("/decisions/{decision_id}", response_model=DecisionRecord, tags=["Query"])
async def get_decision(
    decision_id: str,
    db: AsyncSession = Depends(get_db),
) -> DecisionRecord:
    """Fetch a single decision record by its decision_id."""
    orm = await db.get(DecisionORM, decision_id)
    if orm is None:
        raise HTTPException(status_code=404, detail=f"Decision {decision_id!r} not found")
    return DecisionRecord(**json.loads(orm.full_record_json))


@router.get("/decisions", tags=["Query"])
async def query_decisions(
    decision_id: str | None = Query(None),
    agent_id: str | None = Query(None),
    decision_type: str | None = Query(None),
    from_timestamp: datetime | None = Query(None),
    to_timestamp: datetime | None = Query(None),
    outcome: str | None = Query(None),
    exception_applied: bool | None = Query(None),
    override_applied: bool | None = Query(None),
    limit: int = Query(default=100, ge=1, le=1000),
    cursor: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Query decision records with optional filters and cursor pagination.

    Returns: {"records": [...], "cursor": str | None, "total": int}
    """
    stmt = select(DecisionORM)

    if decision_id:
        stmt = stmt.where(DecisionORM.decision_id == decision_id)
    if agent_id:
        stmt = stmt.where(DecisionORM.agent_id == agent_id)
    if decision_type:
        stmt = stmt.where(DecisionORM.decision_type == decision_type)
    if from_timestamp:
        stmt = stmt.where(DecisionORM.decision_timestamp >= from_timestamp)
    if to_timestamp:
        stmt = stmt.where(DecisionORM.decision_timestamp <= to_timestamp)
    if outcome:
        stmt = stmt.where(DecisionORM.outcome == outcome)
    if exception_applied is not None:
        stmt = stmt.where(DecisionORM.exception_applied == exception_applied)
    if override_applied is not None:
        stmt = stmt.where(DecisionORM.override_applied == override_applied)
    if cursor:
        stmt = stmt.where(DecisionORM.decision_id > cursor)

    stmt = stmt.order_by(DecisionORM.decision_timestamp, DecisionORM.decision_id)
    stmt = stmt.limit(limit)

    result = await db.execute(stmt)
    rows = result.scalars().all()

    records = [DecisionRecord(**json.loads(r.full_record_json)) for r in rows]
    next_cursor = records[-1].decision_id if len(records) == limit else None

    return {
        "records": [r.model_dump(mode="json") for r in records],
        "cursor": next_cursor,
        "total": len(records),
    }
