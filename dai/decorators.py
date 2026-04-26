"""
DAI Decorators
==============

The ``@log_decision`` decorator wraps existing sync or async functions to
automatically record decision records without modifying the function body.

Example::

    from dai.decorators import log_decision

    @log_decision(
        agent_id="claims-agent",
        decision_type="claims_triage",
        policy_id="motor-claims-v3",
        policy_version="3.2.1",
        extract_subject=lambda args, kwargs: f"claim:{kwargs['claim_id']}",
        extract_outcome=lambda r: {"outcome": r.decision, "confidence": r.score},
    )
    async def triage_claim(claim_id: str, data: dict) -> TriageResult:
        ...

The decorator:
1. Calls ``Decision.begin()`` before the function executes.
2. Sets policy, authority, and context from decorator parameters and extractors.
3. Calls the original function.
4. Sets outcome from ``extract_outcome(result)``.
5. Commits the decision.
6. Returns the original function's return value unchanged.
7. On exception: records ``conservative_fallback`` and re-raises.
"""

import asyncio
import functools
import logging
from collections.abc import Callable
from typing import Any

from dai.builder import Decision
from dai.models import ExceptionType

logger = logging.getLogger("dai.decorators")


def log_decision(
    agent_id: str,
    decision_type: str,
    policy_id: str,
    policy_version: str,
    *,
    authorized_scope: str = "decorated_function",
    delegation_source: str = "decorator",
    extract_subject: Callable[[tuple[Any, ...], dict[str, Any]], str],
    extract_outcome: Callable[[Any], dict[str, Any]],
    extract_context: Callable[[tuple[Any, ...], dict[str, Any]], dict[str, Any]] | None = None,
    on_error: str = "log_and_continue",
) -> Callable[..., Any]:
    """
    Decorator that automatically records a DAI decision for the decorated function.

    Args:
        agent_id: Identifier of the agent making decisions.
        decision_type: Domain classification of the decision.
        policy_id: Policy document identifier.
        policy_version: Semver version of the policy.
        authorized_scope: Scope of authority. Defaults to 'decorated_function'.
        delegation_source: Authority delegation source. Defaults to 'decorator'.
        extract_subject: Callable(args, kwargs) -> str. Extracts subject_ref.
        extract_outcome: Callable(return_value) -> dict with keys:
            - outcome (str, required)
            - confidence (float, required)
            - alternatives_considered (int, optional)
        extract_context: Optional callable(args, kwargs) -> dict with keys:
            - evidence_refs (list[str])
            - data_sources_accessed (list[str])
            If not provided, defaults to generic values.
        on_error: Error policy string ('log_and_continue' or 'raise_exception').
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            return await _execute(func, args, kwargs, is_async=True)

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            return asyncio.run(_execute(func, args, kwargs, is_async=False))

        async def _execute(
            fn: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any], is_async: bool
        ) -> Any:
            try:
                subject_ref = extract_subject(args, kwargs)
            except Exception as e:
                logger.error("log_decision: extract_subject failed: %s", e)
                subject_ref = "unknown"

            decision = Decision.begin(
                agent_id=agent_id,
                decision_type=decision_type,
                subject_ref=subject_ref,
            )
            decision.with_policy(policy_id=policy_id, policy_version=policy_version)
            decision.with_authority(
                authorized_scope=authorized_scope,
                delegation_source=delegation_source,
            )

            if extract_context is not None:
                try:
                    ctx = extract_context(args, kwargs)
                    decision.with_context(
                        evidence_refs=ctx.get("evidence_refs", ["function_call"]),
                        data_sources_accessed=ctx.get(
                            "data_sources_accessed", ["decorated_function"]
                        ),
                    )
                except Exception as e:
                    logger.error("log_decision: extract_context failed: %s", e)
                    decision.with_context(
                        evidence_refs=["function_call"],
                        data_sources_accessed=["decorated_function"],
                    )
            else:
                decision.with_context(
                    evidence_refs=["function_call"],
                    data_sources_accessed=["decorated_function"],
                )

            try:
                if is_async:
                    result = await fn(*args, **kwargs)
                else:
                    result = fn(*args, **kwargs)
            except Exception as exc:
                # Record exception before re-raising
                try:
                    decision.with_exception(
                        exception_type=ExceptionType.conservative_fallback,
                        reason_code="unhandled_exception",
                    )
                    decision.with_outcome(outcome="escalated", confidence=0.0)
                    await decision.commit()
                except Exception as commit_err:
                    if on_error == "raise_exception":
                        raise commit_err from exc
                    logger.error("log_decision: commit on exception failed: %s", commit_err)
                raise

            try:
                outcome_data = extract_outcome(result)
                decision.with_outcome(
                    outcome=outcome_data["outcome"],
                    confidence=outcome_data["confidence"],
                    alternatives_considered=outcome_data.get("alternatives_considered"),
                )
                await decision.commit()
            except Exception as commit_err:
                if on_error == "raise_exception":
                    raise
                logger.error("log_decision: commit failed: %s", commit_err)

            return result

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
