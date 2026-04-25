from unittest.mock import MagicMock, patch

from dai.integrations.opentelemetry import configure_otel_bridge, emit_decision_span


def test_emit_decision_span():
    configure_otel_bridge(enabled=True)

    with patch("dai.integrations.opentelemetry.trace.get_tracer") as mock_get_tracer:
        tracer = MagicMock()
        mock_get_tracer.return_value = tracer
        span = MagicMock()
        tracer.start_as_current_span.return_value.__enter__.return_value = span

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

        emit_decision_span(record)

        assert mock_get_tracer.called
        assert tracer.start_as_current_span.called
        assert span.set_attribute.called

def test_configure_otel_bridge():
    configure_otel_bridge(enabled=False)
    with patch("dai.integrations.opentelemetry.trace.get_tracer") as mock_get_tracer:
        emit_decision_span(MagicMock())
        assert not mock_get_tracer.called
