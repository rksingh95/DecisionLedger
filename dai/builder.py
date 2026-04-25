"""
DAI Decision Builder
====================

Fluent builder API for constructing and committing decision records.
This is the primary interface developers interact with.

Example::

    import dai

    result = await (
        dai.Decision.begin(
            agent_id="claims-agent-01",
            decision_type="claims_triage",
            subject_ref="claim:ABC123",
        )
        .with_policy(policy_id="motor-claims-v3", policy_version="3.2.1",
                     clauses_applied=["3.1", "4.2"])
        .with_authority(authorized_scope="triage", delegation_source="underwriting-team")
        .with_context(
            evidence_refs=["doc:claim-form", "img:damage-photo"],
            data_sources_accessed=["claims-db", "policy-db"],
        )
        .with_outcome(outcome="approved", confidence=0.93)
        .commit()
    )
    print(f"Recorded: {result.decision_id}")
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Self

from dai.client import CommitResult, get_client
from dai.config import get_config
from dai.exceptions import AlreadyCommittedError, BuilderValidationError
from dai.hash_chain import prepare_record_for_commit
from dai.models import (
    AgentType,
    ContextCompleteness,
    DecisionRecordCreate,
    ExceptionType,
)

logger = logging.getLogger("dai.builder")


class Decision:
    """
    Fluent builder for creating and committing DAI decision records.

    Usage::

        result = await Decision.begin(...).with_policy(...).commit()

    All setter methods return ``self`` for chaining. Call ``commit()`` (async)
    or ``commit_sync()`` (sync) once to write the record to the ledger.

    A Decision instance can only be committed once. Calling ``commit()``
    twice raises ``AlreadyCommittedError``.
    """

    def __init__(self) -> None:
        self._agent_id: str = ""
        self._agent_type: AgentType = AgentType.autonomous
        self._model_version: str = "unknown"
        self._deployment_id: str | None = None
        self._decision_type: str = ""
        self._subject_ref: str = ""
        self._policy_id: str | None = None
        self._policy_version: str | None = None
        self._policy_snapshot_at: datetime | None = None
        self._clauses_applied: list[str] = []
        self._authorized_scope: str | None = None
        self._delegation_source: str | None = None
        self._human_oversight_required: bool = False
        self._override_applied: bool = False
        self._override_by: str | None = None
        self._override_justification: ExceptionType | None = None
        self._outcome: str | None = None
        self._confidence: float | None = None
        self._alternatives_considered: int | None = None
        self._evidence_refs: list[str] | None = None
        self._data_sources_accessed: list[str] | None = None
        self._context_completeness: ContextCompleteness = ContextCompleteness.full
        self._exception_applied: bool = False
        self._exception_type: ExceptionType | None = None
        self._exception_reason_code: str | None = None
        self._metadata: dict[str, str] = {}
        self._start_time: datetime = datetime.now(timezone.utc)
        self._committed: bool = False

    @classmethod
    def begin(
        cls,
        agent_id: str,
        decision_type: str,
        subject_ref: str,
        *,
        agent_type: AgentType | str = AgentType.autonomous,
        model_version: str = "unknown",
        deployment_id: str | None = None,
    ) -> Self:
        """
        Create a new Decision builder.

        Args:
            agent_id: Unique identifier of the agent making this decision.
            decision_type: Domain-specific classification (e.g. 'claims_triage').
            subject_ref: Opaque reference to the subject (e.g. 'claim:ABC123').
            agent_type: Level of human oversight. Defaults to autonomous.
            model_version: Model identifier (e.g. 'gpt-4o-2024-08-06').
            deployment_id: Optional deployment environment identifier.

        Returns:
            A new Decision builder ready for chaining.
        """
        d = cls()
        d._agent_id = agent_id
        d._decision_type = decision_type
        d._subject_ref = subject_ref
        d._agent_type = (
            AgentType(agent_type) if isinstance(agent_type, str) else agent_type
        )
        d._model_version = model_version
        d._deployment_id = deployment_id
        d._start_time = datetime.now(timezone.utc)
        return d  # type: ignore[return-value]

    def with_policy(
        self,
        policy_id: str,
        policy_version: str,
        *,
        clauses_applied: list[str] | None = None,
        snapshot_at: datetime | None = None,
    ) -> Self:
        """
        Set the policy governing this decision.

        Args:
            policy_id: Policy document identifier.
            policy_version: Semver version string (e.g. '3.2.1').
            clauses_applied: List of clause IDs that applied.
            snapshot_at: When the policy version was resolved. Defaults to now.
        """
        self._policy_id = policy_id
        self._policy_version = policy_version
        self._clauses_applied = clauses_applied or []
        self._policy_snapshot_at = snapshot_at or datetime.now(timezone.utc)
        return self  # type: ignore[return-value]

    def with_authority(
        self,
        authorized_scope: str,
        delegation_source: str,
        *,
        human_oversight_required: bool = False,
    ) -> Self:
        """
        Set the authority context for this decision.

        Args:
            authorized_scope: What this agent was permitted to decide.
            delegation_source: Who/what granted authority.
            human_oversight_required: True if human review is required before enactment.
        """
        self._authorized_scope = authorized_scope
        self._delegation_source = delegation_source
        self._human_oversight_required = human_oversight_required
        return self  # type: ignore[return-value]

    def with_override(
        self,
        override_by: str,
        justification: ExceptionType | str,
    ) -> Self:
        """
        Record a human override of the agent's decision.

        Automatically sets override_applied=True.

        Args:
            override_by: Role or ID of the overriding human.
            justification: Classification of why the override was applied.
        """
        self._override_applied = True
        self._override_by = override_by
        self._override_justification = (
            ExceptionType(justification)
            if isinstance(justification, str)
            else justification
        )
        return self  # type: ignore[return-value]

    def with_context(
        self,
        evidence_refs: list[str],
        data_sources_accessed: list[str],
        *,
        context_completeness: ContextCompleteness | str = ContextCompleteness.full,
    ) -> Self:
        """
        Set the evidence and data context for this decision.

        Args:
            evidence_refs: References to evidence that informed this decision.
            data_sources_accessed: Names of data systems queried.
            context_completeness: Whether all expected data was available.
        """
        self._evidence_refs = evidence_refs
        self._data_sources_accessed = data_sources_accessed
        self._context_completeness = (
            ContextCompleteness(context_completeness)
            if isinstance(context_completeness, str)
            else context_completeness
        )
        return self  # type: ignore[return-value]

    def with_outcome(
        self,
        outcome: str,
        confidence: float,
        *,
        alternatives_considered: int | None = None,
    ) -> Self:
        """
        Set the decision outcome.

        Args:
            outcome: The decision result (e.g. 'approved', 'denied').
            confidence: Agent confidence 0.0–1.0.
            alternatives_considered: Number of alternatives evaluated.
        """
        self._outcome = outcome
        self._confidence = confidence
        self._alternatives_considered = alternatives_considered
        return self  # type: ignore[return-value]

    def with_exception(
        self,
        exception_type: ExceptionType | str,
        reason_code: str,
    ) -> Self:
        """
        Record that an exception path was applied.

        Automatically sets exception_applied=True.

        Args:
            exception_type: Classification of the exception.
            reason_code: Domain-specific reason code.
        """
        self._exception_applied = True
        self._exception_type = (
            ExceptionType(exception_type)
            if isinstance(exception_type, str)
            else exception_type
        )
        self._exception_reason_code = reason_code
        return self  # type: ignore[return-value]

    def with_metadata(self, key: str, value: str) -> Self:
        """
        Add a single key-value metadata entry.

        Args:
            key: Metadata key.
            value: Metadata value (must be a string).
        """
        self._metadata[key] = value
        return self  # type: ignore[return-value]

    def _validate(self) -> None:
        """Check all required fields are set. Raise BuilderValidationError if not."""
        missing: list[str] = []
        if not self._agent_id:
            missing.append("agent_id")
        if not self._decision_type:
            missing.append("decision_type")
        if not self._subject_ref:
            missing.append("subject_ref")
        if not self._policy_id:
            missing.append("policy_id")
        if not self._policy_version:
            missing.append("policy_version")
        if not self._authorized_scope:
            missing.append("authorized_scope")
        if not self._delegation_source:
            missing.append("delegation_source")
        if self._outcome is None:
            missing.append("outcome")
        if self._evidence_refs is None:
            missing.append("evidence_refs")
        if self._data_sources_accessed is None:
            missing.append("data_sources_accessed")
        if missing:
            raise BuilderValidationError(missing)

    def _build_create_request(self) -> DecisionRecordCreate:
        """Build a DecisionRecordCreate from the current builder state."""
        return DecisionRecordCreate(
            agent_id=self._agent_id,
            agent_type=self._agent_type,
            model_version=self._model_version,
            deployment_id=self._deployment_id,
            authorized_scope=self._authorized_scope or "",
            delegation_source=self._delegation_source or "",
            human_oversight_required=self._human_oversight_required,
            override_applied=self._override_applied,
            override_by=self._override_by,
            override_justification=self._override_justification,
            decision_type=self._decision_type,
            subject_ref=self._subject_ref,
            policy_id=self._policy_id or "",
            policy_version=self._policy_version or "0.0.0",
            policy_snapshot_at=self._policy_snapshot_at or datetime.now(timezone.utc),
            clauses_applied=self._clauses_applied,
            outcome=self._outcome or "",
            confidence=self._confidence or 0.0,
            alternatives_considered=self._alternatives_considered,
            evidence_refs=self._evidence_refs or [],
            data_sources_accessed=self._data_sources_accessed or [],
            context_completeness=self._context_completeness,
            exception_applied=self._exception_applied,
            exception_type=self._exception_type,
            exception_reason_code=self._exception_reason_code,
            metadata=self._metadata,
            decision_timestamp=self._start_time,
        )

    async def commit(self) -> Any:
        """
        Commit this decision to the ledger.
        """
        if self._committed:
            raise AlreadyCommittedError()

        self._validate()

        config = get_config()
        client = get_client(config)

        try:
            latest_hash = await client.get_latest_hash()
            create_request = self._build_create_request()
            record = prepare_record_for_commit(create_request, latest_hash)
            result = await client.commit(record)
            self._committed = True
            return result
        except (AlreadyCommittedError, BuilderValidationError):
            raise
        except Exception as exc:
            logger.error("Decision commit failed: %s", exc)
            from dai.config import ErrorPolicy
            if config.on_error == ErrorPolicy.raise_exception:
                raise
            return CommitResult(success=False, error=str(exc))

    def commit_sync(self) -> Any:
        """
        Synchronous wrapper around commit().

        Handles the case where an event loop is already running (e.g. in
        Jupyter notebooks or some async frameworks) by using a thread executor.

        Returns:
            CommitResult
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running loop — safe to use asyncio.run()
            return asyncio.run(self.commit())

        # Loop is running — run in a new thread
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, self.commit())
            return future.result()

    # ── Context Manager Support ───────────────────────────────────────────────

    async def __aenter__(self) -> Self:
        return self  # type: ignore[return-value]

    async def __aexit__(
        self,
        exc_type: type | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool:
        if self._committed:
            return False  # Already committed — do nothing

        if exc_type is not None and self._outcome is None:
            # Exception occurred before with_outcome() was called.
            # Record a conservative fallback so the crash is still audited.
            self.with_exception(
                exception_type=ExceptionType.conservative_fallback,
                reason_code="unhandled_exception",
            )
            self.with_outcome(outcome="escalated", confidence=0.0)
            try:
                await self.commit()
            except Exception:
                pass  # Never suppress original exception for audit failures
            return False  # Re-raise original exception

        if exc_type is None:
            # Normal exit — commit if not already done
            await self.commit()
        return False

    @classmethod
    def begin_sync(
        cls,
        agent_id: str,
        decision_type: str,
        subject_ref: str,
        **kwargs: Any,
    ) -> "_SyncDecisionContext":
        """
        Create a Decision for use as a synchronous context manager.

        Usage::

            with Decision.begin_sync(...) as d:
                d.with_policy(...)
                d.with_outcome(...)
            # auto-commits on exit
        """
        decision = cls.begin(agent_id, decision_type, subject_ref, **kwargs)
        return _SyncDecisionContext(decision)


class _SyncDecisionContext:
    """Synchronous context manager wrapper for Decision."""

    def __init__(self, decision: Decision) -> None:
        self._decision = decision

    def __enter__(self) -> Decision:
        return self._decision

    def __exit__(
        self,
        exc_type: type | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool:
        d = self._decision
        if d._committed:
            return False

        if exc_type is not None and d._outcome is None:
            d.with_exception(
                exception_type=ExceptionType.conservative_fallback,
                reason_code="unhandled_exception",
            )
            d.with_outcome(outcome="escalated", confidence=0.0)
            try:
                d.commit_sync()
            except Exception:
                pass
            return False

        if exc_type is None:
            d.commit_sync()
        return False
