"""
DAI Delegation Builder
======================
"""

from typing import Self

from .models import AuthorityNodeType, DelegationNode


class DelegationBuilder:
    """Helper to build a list of DelegationNodes for a delegation_chain."""

    def __init__(self) -> None:
        self.chain: list[DelegationNode] = []

    def add_node(
        self, node_id: str, node_type: AuthorityNodeType | str, authorized_scope: str
    ) -> Self:
        node_type_enum = AuthorityNodeType(node_type) if isinstance(node_type, str) else node_type
        self.chain.append(
            DelegationNode(
                node_id=node_id, node_type=node_type_enum, authorized_scope=authorized_scope
            )
        )
        return self

    def build(self) -> list[DelegationNode]:
        return self.chain
