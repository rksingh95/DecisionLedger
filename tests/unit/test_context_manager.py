"""Unit tests for dai/context_manager.py"""

from dai.builder import Decision as BuilderDecision
from dai.builder import _SyncDecisionContext as BuilderSyncContext
from dai.context_manager import Decision, _SyncDecisionContext


def test_context_manager_exports():
    assert Decision is BuilderDecision
    assert _SyncDecisionContext is BuilderSyncContext
