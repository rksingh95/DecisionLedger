"""
DAI Authority Module
====================

Models and builder helpers for explicit authority chains.
"""

from .delegation import DelegationBuilder
from .models import AuthorityNodeType, DelegationNode

__all__ = ["AuthorityNodeType", "DelegationNode", "DelegationBuilder"]
