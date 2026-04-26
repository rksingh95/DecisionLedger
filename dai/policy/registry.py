"""
DAI Exception Reason Registry
=============================

Registry for valid exception reason codes per decision_type.
"""

from dai.exceptions import BuilderValidationError


class ExceptionReasonRegistry:
    def __init__(self) -> None:
        self._registry: dict[str, list[str]] = {}

    def register(self, decision_type: str, reason_codes: list[str]) -> None:
        self._registry[decision_type] = reason_codes

    def validate(self, decision_type: str, reason_code: str) -> bool:
        if decision_type not in self._registry:
            raise BuilderValidationError(
                [f"decision_type '{decision_type}' not found in exception registry"]
            )
        if reason_code not in self._registry[decision_type]:
            raise BuilderValidationError(
                [f"reason_code '{reason_code}' not valid for decision_type '{decision_type}'"]
            )
        return True

    def get_codes(self, decision_type: str) -> list[str]:
        return self._registry.get(decision_type, [])

    def list_all(self) -> dict[str, list[str]]:
        return self._registry.copy()


default_registry = ExceptionReasonRegistry()
default_registry.register(
    "claims_triage",
    [
        "insufficient_evidence",
        "fraud_suspicion",
        "policy_ambiguity",
        "threshold_breach",
        "manual_escalation_required",
        "duplicate_claim",
    ],
)
default_registry.register(
    "risk_classification",
    [
        "data_quality_issue",
        "model_uncertainty",
        "regulatory_constraint",
        "edge_case",
        "conflicting_signals",
    ],
)
default_registry.register(
    "credit_decision",
    ["manual_review_required", "regulatory_hold", "incomplete_application", "fraud_flag"],
)
