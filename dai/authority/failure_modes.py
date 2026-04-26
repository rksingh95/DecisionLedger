"""
DAI Failure Modes
=================
"""

from enum import StrEnum

from pydantic import BaseModel, Field


class FailureSeverity(StrEnum):
    """Severity of a failure."""

    warning = "warning"
    error = "error"
    critical = "critical"


class FailureMode(BaseModel):
    """
    Represents a failure mode as a first-class decision event.
    """

    code: str = Field(description="Unique code for the failure type.")
    severity: FailureSeverity = Field(description="Severity level of the failure.")
    description: str = Field(description="Human-readable description of the failure.")
    traceback: str | None = Field(
        default=None, description="Optional traceback if failure was an exception."
    )
