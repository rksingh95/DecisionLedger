"""
DAI Server — POST /policies route
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from dai.policy.models import PolicyDiff, PolicyVersion, PolicyVersionCreate
from dai.policy.registry import default_registry
from dai.policy.store import PolicyNotFoundAtTimestampError, PolicyNotFoundError, PolicyStore
from dai_server.db.session import get_db

router = APIRouter(prefix="/policies", tags=["Policies"])
logger = logging.getLogger("dai_server.policies")


async def get_workspace_id(x_api_key: str = Header(default="default")) -> str:
    # For now, placeholder. Workspace will be fully implemented in P1-06.
    # We will use "default" as workspace_id.
    return "default"


@router.post("", response_model=PolicyVersion, status_code=201)
async def create_policy(
    create: PolicyVersionCreate,
    db: AsyncSession = Depends(get_db),
    workspace_id: str = Depends(get_workspace_id),
):
    store = PolicyStore(db)
    # Ensure workspace_id matches API key context
    create_dict = create.model_dump()
    create_dict["workspace_id"] = workspace_id
    create_req = PolicyVersionCreate(**create_dict)

    try:
        version = await store.create_version(create_req)
        await db.commit()
        return version
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.get("/registry/exception-codes", response_model=dict[str, list[str]])
async def get_exception_codes():
    return default_registry.list_all()


class ExceptionCodeRequest(BaseModel):
    decision_type: str
    reason_codes: list[str]


@router.post("/registry/exception-codes")
async def register_exception_codes(req: ExceptionCodeRequest):
    default_registry.register(req.decision_type, req.reason_codes)
    return {"status": "success"}


@router.get("/{policy_id}", response_model=list[PolicyVersion])
async def list_policies(
    policy_id: str,
    db: AsyncSession = Depends(get_db),
    workspace_id: str = Depends(get_workspace_id),
):
    store = PolicyStore(db)
    return await store.list_versions(policy_id, workspace_id)


@router.get("/{policy_id}/resolve", response_model=PolicyVersion)
async def resolve_policy(
    policy_id: str,
    at: datetime = Query(...),
    db: AsyncSession = Depends(get_db),
    workspace_id: str = Depends(get_workspace_id),
):
    store = PolicyStore(db)
    from dai.policy.models import PolicyResolveRequest

    req = PolicyResolveRequest(policy_id=policy_id, at_timestamp=at, workspace_id=workspace_id)
    try:
        return await store.resolve_at(req)
    except PolicyNotFoundAtTimestampError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/{policy_id}/diff", response_model=PolicyDiff)
async def diff_policy(
    policy_id: str,
    from_version: str = Query(alias="from"),
    to_version: str = Query(alias="to"),
    db: AsyncSession = Depends(get_db),
    workspace_id: str = Depends(get_workspace_id),
):
    store = PolicyStore(db)
    try:
        return await store.diff_versions(policy_id, from_version, to_version, workspace_id)
    except PolicyNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/{policy_id}/{version}", response_model=PolicyVersion)
async def get_policy(
    policy_id: str,
    version: str,
    db: AsyncSession = Depends(get_db),
    workspace_id: str = Depends(get_workspace_id),
):
    store = PolicyStore(db)
    try:
        return await store.get_version(policy_id, version, workspace_id)
    except PolicyNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/{policy_id}/{version}/deprecate", response_model=PolicyVersion)
async def deprecate_policy(
    policy_id: str,
    version: str,
    db: AsyncSession = Depends(get_db),
    workspace_id: str = Depends(get_workspace_id),
):
    store = PolicyStore(db)
    try:
        v = await store.deprecate(policy_id, version, workspace_id)
        await db.commit()
        return v
    except PolicyNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
