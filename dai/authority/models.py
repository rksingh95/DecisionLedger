"""
DAI Authority Models
====================
"""

from enum import StrEnum

from pydantic import BaseModel, Field


class AuthorityNodeType(StrEnum):
    """Classification of an authority node."""

    human = "human"
    system = "system"
    policy = "policy"
    organization = "organization"


class DelegationNode(BaseModel):
    """
    A single node in the explicit authority delegation chain.
    """

    node_id: str = Field(
        description="Identifier for this node in the authority chain. e.g. 'underwriting-team'."
    )
    node_type: AuthorityNodeType = Field(description="Type of authority this node represents.")
    authorized_scope: str = Field(description="Scope of authority granted by or to this node.")
