"""
DAI — Decision Authority Infrastructure SDK
============================================

Built by Mandate — https://github.com/Mandate/DecisionLedger

An append-only, cryptographically hash-chained decision ledger for AI agents
in regulated environments. Compliant with EU AI Act Article 19 logging requirements.

Quick start:

    import dai

    dai.configure(
        endpoint="https://my-dai-server.internal",
        api_key="my-api-key",
    )

    result = (
        dai.Decision.begin(
            agent_id="claims-agent-01",
            decision_type="claims_triage",
            subject_ref="claim:ABC123",
        )
        .with_policy(policy_id="motor-claims-v3", policy_version="3.2.1")
        .with_authority(authorized_scope="triage", delegation_source="underwriting-team")
        .with_context(
            evidence_refs=["doc:claim-form", "img:damage-photo-01"],
            data_sources_accessed=["claims-db", "policy-db"],
        )
        .with_outcome(outcome="approved", confidence=0.93)
        .commit_sync()
    )

    print(f"Decision recorded: {result.decision_id}")
"""

from dai.builder import Decision
from dai.client import CommitResult, get_client
from dai.config import DAIConfig, configure, get_config, reset_config
from dai.exceptions import (
    AlreadyCommittedError,
    BuilderValidationError,
    DAIException,
    HashChainError,
)
from dai.hash_chain import (
    compute_record_hash,
    prepare_record_for_commit,
    verify_chain,
    verify_record,
)
from dai.models import (
    GENESIS_HASH as GENESIS_HASH,
)
from dai.models import (
    AgentType,
    Article19ExportRequest,
    ChainVerifyResult,
    ContextCompleteness,
    DecisionRecord,
    DecisionRecordCreate,
    ExceptionType,
    LedgerVersion,
    QueryFilter,
)

__all__ = [
    # Configuration
    "configure",
    "get_config",
    "reset_config",
    "DAIConfig",
    # Models
    "DecisionRecord",
    "DecisionRecordCreate",
    "AgentType",
    "ContextCompleteness",
    "ExceptionType",
    "LedgerVersion",
    "QueryFilter",
    "ChainVerifyResult",
    "Article19ExportRequest",
    # Builder
    "Decision",
    # Client
    "CommitResult",
    "get_client",
    # Hash chain
    "GENESIS_HASH",
    "compute_record_hash",
    "verify_record",
    "verify_chain",
    "prepare_record_for_commit",
    # Exceptions
    "DAIException",
    "HashChainError",
    "BuilderValidationError",
    "AlreadyCommittedError",
]

__version__ = "0.1.0"
