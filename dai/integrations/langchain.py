"""
DAI LangChain Integration
==========================

Optional integration. Requires: ``pip install dai-sdk[langchain]``

Published by Mandate — https://github.com/Mandate/DecisionLedger

Provides ``DAICallbackHandler`` — a LangChain ``BaseCallbackHandler`` that
automatically records decision records for each agent run.

Usage::

    from dai.integrations.langchain import DAICallbackHandler

    handler = DAICallbackHandler(
        agent_id="my-agent",
        decision_type="claims_triage",
        policy_id="policy-v3",
        policy_version="3.2.1",
    )
    agent_executor = AgentExecutor(agent=agent, tools=tools, callbacks=[handler])
"""


import logging
from typing import Any
from uuid import UUID

from dai.builder import Decision
from dai.models import ContextCompleteness, ExceptionType

logger = logging.getLogger("dai.integrations.langchain")

try:
    from langchain_core.callbacks.base import BaseCallbackHandler
    _LANGCHAIN_AVAILABLE = True
except ImportError:
    # Graceful fallback — DAICallbackHandler still importable but non-functional
    BaseCallbackHandler = object
    _LANGCHAIN_AVAILABLE = False


class DAICallbackHandler(BaseCallbackHandler):  # type: ignore[misc]
    """
    LangChain callback handler that records DAI decision records.

    Attach this to any ``AgentExecutor`` or LangChain chain to automatically
    create a decision record for each agent run, including tool calls and errors.

    Requires ``langchain-core>=0.2.0``. Install with::

        pip install dai-sdk[langchain]  # by Mandate
    """

    def __init__(
        self,
        agent_id: str,
        decision_type: str,
        policy_id: str,
        policy_version: str,
        authorized_scope: str = "langchain_agent",
        delegation_source: str = "langchain_executor",
        evidence_prefix: str = "langchain",
    ) -> None:
        if not _LANGCHAIN_AVAILABLE:
            logger.warning(
                "langchain-core is not installed. DAICallbackHandler will be a no-op. "
                "Install with: pip install dai-sdk[langchain]  # by Mandate"
            )
        self.agent_id = agent_id
        self.decision_type = decision_type
        self.policy_id = policy_id
        self.policy_version = policy_version
        self.authorized_scope = authorized_scope
        self.delegation_source = delegation_source
        self.evidence_prefix = evidence_prefix

        self._run_id_to_decision: dict[str, Decision] = {}
        self._run_id_to_evidence: dict[str, list[str]] = {}
        self._run_id_to_sources: dict[str, list[str]] = {}

    def _get_run_key(self, run_id: UUID | str) -> str:
        return str(run_id)

    def _get_or_create_decision(self, run_id: UUID | str, subject_ref: str = "langchain_run") -> Decision:
        key = self._get_run_key(run_id)
        if key not in self._run_id_to_decision:
            d = Decision.begin(
                agent_id=self.agent_id,
                decision_type=self.decision_type,
                subject_ref=f"{subject_ref}:{key[:8]}",
            )
            d.with_policy(policy_id=self.policy_id, policy_version=self.policy_version)
            d.with_authority(
                authorized_scope=self.authorized_scope,
                delegation_source=self.delegation_source,
            )
            self._run_id_to_decision[key] = d
            self._run_id_to_evidence[key] = []
            self._run_id_to_sources[key] = [f"{self.evidence_prefix}_executor"]
        return self._run_id_to_decision[key]

    def on_agent_action(
        self,
        action: Any,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """Record the tool being called as evidence."""
        if not _LANGCHAIN_AVAILABLE:
            return
        try:
            self._get_or_create_decision(run_id)
            key = self._get_run_key(run_id)
            tool_ref = f"{self.evidence_prefix}:tool:{getattr(action, 'tool', 'unknown')}"
            self._run_id_to_evidence[key].append(tool_ref)
        except Exception as e:
            logger.error("DAICallbackHandler.on_agent_action error: %s", e)

    def on_tool_end(
        self,
        output: str,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """Record tool output reference in context."""
        if not _LANGCHAIN_AVAILABLE:
            return
        try:
            key = self._get_run_key(run_id)
            if key in self._run_id_to_sources:
                self._run_id_to_sources[key].append(
                    f"{self.evidence_prefix}:tool_output"
                )
        except Exception as e:
            logger.error("DAICallbackHandler.on_tool_end error: %s", e)

    def on_agent_finish(
        self,
        finish: Any,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """Set outcome from finish values and commit the decision."""
        if not _LANGCHAIN_AVAILABLE:
            return
        try:
            key = self._get_run_key(run_id)
            d = self._get_or_create_decision(run_id)
            evidence = self._run_id_to_evidence.get(key, ["langchain_run"])
            sources = self._run_id_to_sources.get(key, ["langchain_executor"])
            d.with_context(
                evidence_refs=evidence or ["langchain_run"],
                data_sources_accessed=sources or ["langchain_executor"],
                context_completeness=ContextCompleteness.full,
            )
            return_values = getattr(finish, "return_values", {}) or {}
            outcome = str(return_values.get("output", "completed"))[:100]
            confidence = float(return_values.get("confidence", 0.8))
            d.with_outcome(outcome=outcome, confidence=confidence)
            d.commit_sync()
            self._cleanup(key)
        except Exception as e:
            logger.error("DAICallbackHandler.on_agent_finish error: %s", e)

    def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        """Record a conservative fallback on chain error and commit."""
        if not _LANGCHAIN_AVAILABLE:
            return
        try:
            key = self._get_run_key(run_id)
            if key not in self._run_id_to_decision:
                return
            d = self._run_id_to_decision[key]
            evidence = self._run_id_to_evidence.get(key, ["langchain_run"])
            sources = self._run_id_to_sources.get(key, ["langchain_executor"])
            d.with_context(
                evidence_refs=evidence or ["langchain_run"],
                data_sources_accessed=sources or ["langchain_executor"],
                context_completeness=ContextCompleteness.degraded,
            )
            d.with_exception(
                exception_type=ExceptionType.conservative_fallback,
                reason_code="chain_error",
            )
            d.with_outcome(outcome="escalated", confidence=0.0)
            d.commit_sync()
            self._cleanup(key)
        except Exception as e:
            logger.error("DAICallbackHandler.on_chain_error error: %s", e)

    def _cleanup(self, key: str) -> None:
        """Remove run tracking state after commit."""
        self._run_id_to_decision.pop(key, None)
        self._run_id_to_evidence.pop(key, None)
        self._run_id_to_sources.pop(key, None)
