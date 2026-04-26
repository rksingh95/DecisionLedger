import pytest

from dai.authority.delegation import DelegationBuilder
from dai.authority.models import AuthorityNodeType, DelegationNode
from dai.builder import Decision
from dai.exceptions import BuilderValidationError


@pytest.mark.asyncio
async def test_valid_authority_chain():
    chain = (
        DelegationBuilder()
        .add_node("board", AuthorityNodeType.organization, "set strategy")
        .add_node("ceo", AuthorityNodeType.human, "execution")
        .build()
    )

    # Just testing builder correctly consumes it
    d = Decision.begin("agent", "test", "subj").with_delegation_chain(chain)
    assert len(d._delegation_chain) == 2
    assert d._delegation_chain[0].node_id == "board"


@pytest.mark.asyncio
async def test_empty_chain_rejected_if_no_source():
    d = (
        Decision.begin("agent", "test", "subj")
        .with_policy("policy", "1.0.0")
        .with_authority("scope", None)  # No delegation_source
        .with_outcome("approved", 1.0)
        .with_context(["evidence"], ["data"])
    )
    # chain is empty by default
    with pytest.raises(BuilderValidationError, match="delegation_source or delegation_chain"):
        d._validate()


def test_order_preserved():
    chain = DelegationBuilder().add_node("1", "human", "a").add_node("2", "human", "b").build()
    assert chain[0].node_id == "1"
    assert chain[1].node_id == "2"


def test_mutation_after_commit_rejected():
    node = DelegationNode(
        node_id="test", node_type=AuthorityNodeType.human, authorized_scope="scope"
    )

    from dai.hash_chain import prepare_record_for_commit
    from dai.models import GENESIS_HASH, DecisionRecordCreate

    req = DecisionRecordCreate(
        agent_id="agent",
        decision_type="test",
        subject_ref="ref",
        authorized_scope="scope",
        delegation_chain=[node],
        evidence_refs=["a"],
        data_sources_accessed=["b"],
        outcome="approved",
        confidence=1.0,
        policy_id="p",
        policy_version="1.0.0",
        policy_snapshot_at="2023-01-01T00:00:00Z",
    )
    record = prepare_record_for_commit(req, GENESIS_HASH)
    from pydantic_core import ValidationError

    with pytest.raises(ValidationError):
        record.delegation_chain = []
