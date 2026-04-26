"""Unit tests for dai/integrations/opentelemetry.py.

opentelemetry-api is an optional dependency — tests run whether or not it is
installed by patching at the right level.
"""

from unittest.mock import MagicMock, patch

import dai.integrations.opentelemetry as otel_module
from dai.integrations.opentelemetry import configure_otel_bridge, emit_decision_span


def _make_record() -> MagicMock:
    record = MagicMock()
    record.decision_id = "test-id"
    record.decision_type = "test-type"
    record.agent_id = "test-agent"
    record.agent_type = MagicMock(value="autonomous")
    record.model_version = "v1"
    record.outcome = "approved"
    record.confidence = 0.99
    record.policy_id = "test-policy"
    record.policy_version = "1.0.0"
    record.record_hash = "abc" * 16
    record.previous_hash = "def"
    record.exception_applied = False
    record.override_applied = False
    record.evidence_refs = []
    return record


def test_emit_decision_span():
    """emit_decision_span should call get_tracer and start_as_current_span when enabled."""
    mock_trace = MagicMock()
    tracer = MagicMock()
    span = MagicMock()
    # get_tracer() returns tracer
    mock_trace.get_tracer.return_value = tracer
    # tracer.start_as_current_span() used as context manager returns span
    span_ctx = MagicMock()
    span_ctx.__enter__ = MagicMock(return_value=span)
    span_ctx.__exit__ = MagicMock(return_value=False)
    tracer.start_as_current_span.return_value = span_ctx

    with (
        patch.object(otel_module, "trace", mock_trace, create=True),
        patch.object(otel_module, "SpanKind", MagicMock(), create=True),
    ):
        original_available = otel_module._OTEL_AVAILABLE
        original_enabled = otel_module._otel_bridge_enabled
        otel_module._OTEL_AVAILABLE = True
        otel_module._otel_bridge_enabled = True
        try:
            emit_decision_span(_make_record())
        finally:
            otel_module._OTEL_AVAILABLE = original_available
            otel_module._otel_bridge_enabled = original_enabled

    assert mock_trace.get_tracer.called
    assert tracer.start_as_current_span.called
    assert span.set_attribute.called


def test_emit_decision_span_disabled():
    """emit_decision_span should be a no-op when the bridge is disabled."""
    configure_otel_bridge(enabled=False)

    mock_trace = MagicMock()
    with patch.object(otel_module, "trace", mock_trace, create=True):
        emit_decision_span(_make_record())

    assert not mock_trace.get_tracer.called


def test_configure_otel_bridge():
    """configure_otel_bridge(enabled=False) disables span emission."""
    configure_otel_bridge(enabled=False)

    mock_trace = MagicMock()
    with patch.object(otel_module, "trace", mock_trace, create=True):
        emit_decision_span(_make_record())
    assert not mock_trace.get_tracer.called
