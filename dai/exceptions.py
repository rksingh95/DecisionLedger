"""
DAI SDK Exceptions
==================

All DAI-specific exceptions. The SDK is designed to be non-blocking by default
(ErrorPolicy.log_and_continue), but these exceptions are available for strict
mode and programmatic error handling.
"""


class DAIException(Exception):
    """Base exception for all DAI SDK errors."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.message!r})"


class HashChainError(DAIException):
    """
    Raised when a hash chain operation fails — either during computation
    or during verification when a tampered record is detected.
    """

    def __init__(
        self,
        message: str,
        *,
        expected_hash: str | None = None,
        actual_hash: str | None = None,
        decision_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.expected_hash = expected_hash
        self.actual_hash = actual_hash
        self.decision_id = decision_id

    def __repr__(self) -> str:
        exp_short = self.expected_hash[:16] if self.expected_hash else None
        act_short = self.actual_hash[:16] if self.actual_hash else None
        return (
            f"HashChainError(message={self.message!r}, "
            f"decision_id={self.decision_id!r}, "
            f"expected={exp_short!r}, "
            f"actual={act_short!r})"
        )


class BuilderValidationError(DAIException):
    """
    Raised when a Decision builder is committed without all required fields set.
    Lists every missing field in the error message.
    """

    def __init__(self, missing_fields: list[str]) -> None:
        self.missing_fields = missing_fields
        message = f"Cannot commit decision: missing required fields: {', '.join(missing_fields)}"
        super().__init__(message)


class AlreadyCommittedError(DAIException):
    """
    Raised when commit() is called on a Decision that has already been committed.
    Create a new Decision instance for each decision record.
    """

    def __init__(self) -> None:
        super().__init__("This Decision has already been committed. Create a new Decision.")


class ConfigurationError(DAIException):
    """Raised when DAI SDK configuration is invalid."""

    pass


class ClientError(DAIException):
    """Raised when a DAI client operation fails (HTTP, SQLite, etc.)."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class IngestError(DAIException):
    """Raised when record ingestion fails server-side validation."""

    pass


class ChainContinuityError(DAIException):
    """
    Raised when the hash chain continuity check fails during ingest —
    i.e. the record's previous_hash does not match the latest record's hash.
    """

    def __init__(
        self,
        message: str,
        *,
        expected_previous_hash: str | None = None,
        actual_previous_hash: str | None = None,
    ) -> None:
        super().__init__(message)
        self.expected_previous_hash = expected_previous_hash
        self.actual_previous_hash = actual_previous_hash
