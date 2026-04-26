import pytest

from dai.authority.failure_modes import FailureMode, FailureSeverity
from dai.builder import Decision
from dai.models import ExceptionType


@pytest.mark.asyncio
async def test_exception_produces_failure_record():
    d = Decision.begin("agent", "test", "subj")
    d.with_failure_mode(
        FailureMode(code="ERR_1", severity=FailureSeverity.error, description="Test error")
    )
    assert d._failure_mode.code == "ERR_1"


def test_fallback_recorded():
    # Context manager should record fallback on exception
    with pytest.raises(ValueError), Decision.begin_sync("agent", "test", "subj") as d:
        d.with_policy("policy", "1.0.0")
        d.with_authority("scope", "source")
        d.with_context(["evidence"], ["data"])
        raise ValueError("Something went wrong")

    assert d._outcome == "escalated"
    assert d._exception_applied is True
    assert d._exception_type == ExceptionType.conservative_fallback


def test_retries_preserved():
    fm = FailureMode(
        code="TIMEOUT", severity="warning", description="Timeout", traceback="Traceback details..."
    )
    assert fm.traceback == "Traceback details..."
