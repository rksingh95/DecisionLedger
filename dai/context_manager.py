"""
DAI Context Manager
===================

The Decision class already embeds __aenter__/__aexit__ and begin_sync()
support in dai/builder.py. This module re-exports those for clarity
and provides module-level documentation.

Usage (async)::

    async with Decision.begin(...) as d:
        d.with_policy(...)
        d.with_authority(...)
        result = await agent_do_thing()
        d.with_outcome(outcome=result.label, confidence=result.score)
    # auto-commits on __aexit__

Usage (sync)::

    with Decision.begin_sync(...) as d:
        d.with_policy(...)
        d.with_outcome(...)
    # auto-commits on __exit__

Critical behaviour on exception:
    If the code inside the ``with`` block raises an exception BEFORE
    ``with_outcome()`` is called, DAI automatically records a
    ``conservative_fallback`` exception with ``outcome='escalated'``
    and re-raises the original exception. This ensures that even agent
    crashes produce an audit record.
"""

from dai.builder import Decision, _SyncDecisionContext

__all__ = ["Decision", "_SyncDecisionContext"]
