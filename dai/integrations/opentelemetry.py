"""
DAI OpenTelemetry Integration
==============================

Optional integration. Requires: ``pip install dai-sdk[opentelemetry]``

Published by Mandate — https://github.com/Mandate/DecisionLedger

Bridges DAI decision records to OpenTelemetry spans using GenAI
semantic conventions where applicable.

Usage::

    from dai.integrations.opentelemetry import configure_otel_bridge
    configure_otel_bridge(enabled=True)

    # Then in your DAI config:
    dai.configure(emit_opentelemetry_spans=True)

    # Spans are emitted automatically after each successful commit.

If opentelemetry-api is not installed, all functions in this module
return silently. No ImportError will be raised.
"""


import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dai.models import DecisionRecord

logger = logging.getLogger("dai.integrations.opentelemetry")

try:
    from opentelemetry import trace
    from opentelemetry.trace import SpanKind
    _OTEL_AVAILABLE = True
except ImportError:
    _OTEL_AVAILABLE = False

_otel_bridge_enabled: bool = False


def configure_otel_bridge(enabled: bool = True) -> None:
    """
    Enable or disable the OpenTelemetry span bridge.

    Must also set ``emit_opentelemetry_spans=True`` in DAI config.
    If opentelemetry-api is not installed, this is a no-op.

    Args:
        enabled: True to enable span emission, False to disable.
    """
    global _otel_bridge_enabled
    if not _OTEL_AVAILABLE and enabled:
        logger.warning(
            "opentelemetry-api is not installed. OTel bridge will be a no-op. "
            "Install with: pip install dai-sdk[opentelemetry]  # by Mandate"
        )
    _otel_bridge_enabled = enabled


def emit_decision_span(record: "DecisionRecord") -> None:
    """
    Emit an OpenTelemetry span for a committed decision record.

    Called automatically by HTTPDAIClient after a successful commit when
    ``config.emit_opentelemetry_spans=True``.

    If opentelemetry-api is not installed or the bridge is disabled,
    returns silently.

    Span attributes follow OTel GenAI semantic conventions where applicable.

    Args:
        record: The committed DecisionRecord to trace.
    """
    if not _OTEL_AVAILABLE or not _otel_bridge_enabled:
        return

    try:
        tracer = trace.get_tracer("mandate.decisionledger")
        span_name = f"dai.decision.{record.decision_type}"

        with tracer.start_as_current_span(span_name, kind=SpanKind.INTERNAL) as span:
            span.set_attribute("dai.decision.id", record.decision_id)
            span.set_attribute("dai.decision.type", record.decision_type)
            span.set_attribute("dai.agent.id", record.agent_id)
            span.set_attribute("dai.agent.type", record.agent_type.value)
            span.set_attribute("gen_ai.system", record.model_version)
            span.set_attribute("dai.policy.id", record.policy_id)
            span.set_attribute("dai.policy.version", record.policy_version)
            span.set_attribute("dai.decision.outcome", record.outcome)
            span.set_attribute("dai.decision.confidence", record.confidence)
            span.set_attribute("dai.exception.applied", record.exception_applied)
            span.set_attribute("dai.override.applied", record.override_applied)
            # Use only first 16 chars of hash to avoid high cardinality
            span.set_attribute("dai.record.hash", record.record_hash[:16])
    except Exception as e:
        # OTel failures must never propagate to the caller
        logger.debug("OTel span emission failed (non-critical): %s", e)
