"""
DAI Policy Store
================

Manages PolicyVersion lifecycle.
"""

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, Literal

from deepdiff import DeepDiff
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    PolicyDiff,
    PolicyResolveRequest,
    PolicyStatus,
    PolicyVersion,
    PolicyVersionCreate,
)


class PolicyNotFoundError(Exception):
    pass


class PolicyNotFoundAtTimestampError(Exception):
    pass


class PolicyStore:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_version(self, create: PolicyVersionCreate) -> PolicyVersion:
        from dai_server.db.models import PolicyVersionORM

        # Check for collision
        stmt = select(PolicyVersionORM).where(
            PolicyVersionORM.policy_id == create.policy_id,
            PolicyVersionORM.version == create.version,
            PolicyVersionORM.workspace_id == create.workspace_id,
        )
        existing = (await self.db.execute(stmt)).scalar_one_or_none()
        if existing:
            raise ValueError(
                f"Policy version {create.version} already exists for {create.policy_id}"
            )

        # Supersede currently active version if exists
        stmt_active = select(PolicyVersionORM).where(
            PolicyVersionORM.policy_id == create.policy_id,
            PolicyVersionORM.workspace_id == create.workspace_id,
            PolicyVersionORM.status == PolicyStatus.active.value,
        )
        active_version = (await self.db.execute(stmt_active)).scalar_one_or_none()
        if active_version:
            active_version.status = PolicyStatus.superseded.value
            active_version.effective_to = create.effective_from  # type: ignore

        # Compute hash
        clauses_dict = [c.model_dump(mode="json") for c in create.clauses]
        clauses_json = json.dumps(clauses_dict, sort_keys=True)
        hash_input = f"{create.policy_id}:{create.version}:{clauses_json}".encode()
        policy_hash = hashlib.sha256(hash_input).hexdigest()

        now = datetime.now(UTC)

        orm = PolicyVersionORM(
            policy_id=create.policy_id,
            version=create.version,
            workspace_id=create.workspace_id,
            status=create.status.value,
            title=create.title,
            description=create.description,
            effective_from=create.effective_from,
            effective_to=create.effective_to,
            change_type=create.change_type.value,
            change_summary=create.change_summary,
            authorized_decision_types=json.dumps(create.authorized_decision_types),
            max_auto_approve_confidence=create.max_auto_approve_confidence,
            exception_types_allowed=json.dumps(create.exception_types_allowed),
            retention_period_days=create.retention_period_days,
            policy_hash=policy_hash,
            clauses_json=clauses_json,
            created_at=now,
            created_by=create.created_by,
        )
        self.db.add(orm)
        await self.db.flush()

        return await self._to_model(orm)

    async def _to_model(self, orm: Any) -> PolicyVersion:
        from .models import PolicyClause

        return PolicyVersion(
            policy_id=str(orm.policy_id),
            version=str(orm.version),
            status=PolicyStatus(orm.status),
            title=str(orm.title),
            description=str(orm.description),
            effective_from=orm.effective_from,
            effective_to=orm.effective_to,
            supersedes_version=None,
            change_type=orm.change_type,
            change_summary=str(orm.change_summary),
            clauses=[PolicyClause(**c) for c in json.loads(orm.clauses_json)],
            authorized_decision_types=json.loads(orm.authorized_decision_types),
            max_auto_approve_confidence=float(orm.max_auto_approve_confidence),
            exception_types_allowed=json.loads(orm.exception_types_allowed),
            retention_period_days=int(orm.retention_period_days),
            policy_hash=str(orm.policy_hash),
            created_at=orm.created_at,
            created_by=str(orm.created_by),
            workspace_id=str(orm.workspace_id),
        )

    async def get_version(self, policy_id: str, version: str, workspace_id: str) -> PolicyVersion:
        from dai_server.db.models import PolicyVersionORM

        stmt = select(PolicyVersionORM).where(
            PolicyVersionORM.policy_id == policy_id,
            PolicyVersionORM.version == version,
            PolicyVersionORM.workspace_id == workspace_id,
        )
        orm = (await self.db.execute(stmt)).scalar_one_or_none()
        if not orm:
            raise PolicyNotFoundError(f"Policy {policy_id} v{version} not found")
        return await self._to_model(orm)

    async def resolve_at(self, request: PolicyResolveRequest) -> PolicyVersion:
        from dai_server.db.models import PolicyVersionORM

        stmt = (
            select(PolicyVersionORM)
            .where(
                and_(
                    PolicyVersionORM.policy_id == request.policy_id,
                    PolicyVersionORM.workspace_id == request.workspace_id,
                    PolicyVersionORM.effective_from <= request.at_timestamp,
                    or_(
                        PolicyVersionORM.effective_to.is_(None),
                        PolicyVersionORM.effective_to > request.at_timestamp,
                    ),
                    PolicyVersionORM.status.in_(
                        [PolicyStatus.active.value, PolicyStatus.superseded.value]
                    ),
                )
            )
            .order_by(PolicyVersionORM.effective_from.desc())
            .limit(1)
        )
        orm = (await self.db.execute(stmt)).scalar_one_or_none()
        if not orm:
            raise PolicyNotFoundAtTimestampError(
                f"No policy {request.policy_id} found at {request.at_timestamp}"
            )
        return await self._to_model(orm)

    async def diff_versions(
        self, policy_id: str, from_version: str, to_version: str, workspace_id: str
    ) -> PolicyDiff:
        from_pol = await self.get_version(policy_id, from_version, workspace_id)
        to_pol = await self.get_version(policy_id, to_version, workspace_id)

        from_clauses = {c.clause_id: c.content_hash for c in from_pol.clauses}
        to_clauses = {c.clause_id: c.content_hash for c in to_pol.clauses}

        clauses_added = [cid for cid in to_clauses if cid not in from_clauses]
        clauses_removed = [cid for cid in from_clauses if cid not in to_clauses]
        clauses_modified = [
            cid
            for cid in to_clauses
            if cid in from_clauses and to_clauses[cid] != from_clauses[cid]
        ]

        diff = DeepDiff(
            from_pol.exception_types_allowed, to_pol.exception_types_allowed, ignore_order=True
        )
        exc_added = []
        exc_removed = []
        if "iterable_item_added" in diff:
            exc_added = [v for k, v in diff["iterable_item_added"].items()]
        if "iterable_item_removed" in diff:
            exc_removed = [v for k, v in diff["iterable_item_removed"].items()]

        threshold_changed = (
            from_pol.max_auto_approve_confidence != to_pol.max_auto_approve_confidence
        )
        delta = None
        if threshold_changed:
            delta = to_pol.max_auto_approve_confidence - from_pol.max_auto_approve_confidence

        risk_level: Literal["increased", "decreased", "unchanged"] = "unchanged"
        if delta is not None:
            risk_level = "decreased" if delta > 0 else "increased"

        return PolicyDiff(
            policy_id=policy_id,
            from_version=from_version,
            to_version=to_version,
            diffed_at=datetime.now(UTC),
            clauses_added=clauses_added,
            clauses_removed=clauses_removed,
            clauses_modified=clauses_modified,
            threshold_changed=threshold_changed,
            max_auto_approve_confidence_delta=delta,
            exception_types_added=exc_added,
            exception_types_removed=exc_removed,
            risk_level_change=risk_level,
            summary=f"Diff from {from_version} to {to_version}",
        )

    async def list_versions(self, policy_id: str, workspace_id: str) -> list[PolicyVersion]:
        from dai_server.db.models import PolicyVersionORM

        stmt = (
            select(PolicyVersionORM)
            .where(
                PolicyVersionORM.policy_id == policy_id,
                PolicyVersionORM.workspace_id == workspace_id,
            )
            .order_by(PolicyVersionORM.effective_from.desc())
        )
        result = await self.db.execute(stmt)
        return [await self._to_model(orm) for orm in result.scalars().all()]

    async def deprecate(self, policy_id: str, version: str, workspace_id: str) -> PolicyVersion:
        from dai_server.db.models import PolicyVersionORM

        stmt = select(PolicyVersionORM).where(
            PolicyVersionORM.policy_id == policy_id,
            PolicyVersionORM.version == version,
            PolicyVersionORM.workspace_id == workspace_id,
        )
        orm = (await self.db.execute(stmt)).scalar_one_or_none()
        if not orm:
            raise PolicyNotFoundError(f"Policy {policy_id} v{version} not found")
        orm.status = PolicyStatus.deprecated.value
        orm.effective_to = datetime.now(UTC)  # type: ignore
        await self.db.flush()
        return await self._to_model(orm)
