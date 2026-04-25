"""
DAI Configuration System
=========================

Controls all SDK behaviour: which backend to use, how errors are handled,
retry logic, and environment-variable-based configuration.

Usage::

    import os
    import dai

    # Programmatic configuration
    dai.configure(
        backend="http",
        endpoint="https://my-dai-server.internal",
        api_key=os.environ["DAI_API_KEY"],
        on_error="log_and_continue",
    )

    # Or via environment variables (auto-loaded from .env):
    # DAI_BACKEND=http
    # DAI_ENDPOINT=https://my-dai-server.internal
    # DAI_API_KEY=secret
    # DAI_ON_ERROR=log_and_continue

    # Configuration is then automatic:
    import dai
    result = dai.Decision.begin(...).with_policy(...).commit_sync()
"""

import logging
import os
import threading
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

logger = logging.getLogger("dai.config")


# ─── Enums ────────────────────────────────────────────────────────────────────


class BackendType(StrEnum):
    """Which storage backend the SDK uses to commit decision records."""

    http = "http"
    """Send records to the DAI server via HTTP POST /ingest."""

    sqlite = "sqlite"
    """Store records in a local SQLite file. Good for development and testing."""

    noop = "noop"
    """Silently discard all records. Useful for CI/testing where records are irrelevant."""


class ErrorPolicy(StrEnum):
    """How the SDK handles errors — follows the non-blocking design principle."""

    raise_exception = "raise_exception"
    """Raise DAIException on any failure. Use in strict/test environments."""

    log_and_continue = "log_and_continue"
    """Log error to stderr and return None/empty result. Never crashes the agent."""

    noop = "noop"
    """Silently ignore all errors. Use only where audit failures are acceptable."""


# ─── Config Dataclass ─────────────────────────────────────────────────────────


@dataclass
class DAIConfig:
    """
    Complete configuration for the DAI SDK.

    All fields have sensible defaults. Override via ``dai.configure(**kwargs)``
    or by setting ``DAI_*`` environment variables (loaded from ``.env`` automatically).
    """

    backend: BackendType = BackendType.http
    """Which transport backend to use for committing records."""

    endpoint: str = "http://localhost:8080"
    """DAI server URL. Used when backend=http."""

    api_key: str = ""
    """API key for authenticating with the DAI server."""

    timeout_seconds: float = 2.0
    """HTTP request timeout in seconds. Keep low to avoid blocking agents."""

    max_retries: int = 3
    """Number of retry attempts on HTTP failure before giving up."""

    retry_backoff_seconds: float = 0.5
    """Base backoff between retries (exponential: 0.5s, 1.0s, 2.0s, ...)."""

    on_error: ErrorPolicy = ErrorPolicy.log_and_continue
    """How to handle SDK errors. Default: log and continue (non-blocking)."""

    sqlite_path: str = "./dai_local.db"
    """Path to local SQLite database file. Used when backend=sqlite."""

    environment: str = "development"
    """Deployment environment identifier (development, staging, production)."""

    log_level: str = "INFO"
    """Python log level for DAI SDK internal logging."""

    emit_opentelemetry_spans: bool = False
    """Whether to emit OpenTelemetry spans for each committed decision."""

    @classmethod
    def from_env(cls) -> "DAIConfig":
        """
        Create a DAIConfig from environment variables.

        Automatically loads ``.env`` file from the current working directory
        using python-dotenv. Environment variable prefix is ``DAI_``.

        Mapping:
            DAI_BACKEND            → backend
            DAI_ENDPOINT           → endpoint
            DAI_API_KEY            → api_key
            DAI_TIMEOUT_SECONDS    → timeout_seconds
            DAI_MAX_RETRIES        → max_retries
            DAI_RETRY_BACKOFF      → retry_backoff_seconds
            DAI_ON_ERROR           → on_error
            DAI_SQLITE_PATH        → sqlite_path
            DAI_ENVIRONMENT        → environment
            DAI_LOG_LEVEL          → log_level
            DAI_EMIT_OTEL_SPANS    → emit_opentelemetry_spans
        """
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass  # python-dotenv is optional at import time

        def _get(key: str, default: str = "") -> str:
            return os.environ.get(f"DAI_{key}", default)

        def _get_bool(key: str, default: bool = False) -> bool:
            val = os.environ.get(f"DAI_{key}", "").lower()
            match val:
                case "1" | "true" | "yes":
                    return True
                case "0" | "false" | "no":
                    return False
                case _:
                    return default

        return cls(
            backend=_coerce_enum(BackendType, _get("BACKEND", "http"), "DAI_BACKEND"),
            endpoint=_get("ENDPOINT", "http://localhost:8080"),
            api_key=_get("API_KEY", ""),
            timeout_seconds=float(_get("TIMEOUT_SECONDS", "2.0")),
            max_retries=int(_get("MAX_RETRIES", "3")),
            retry_backoff_seconds=float(_get("RETRY_BACKOFF", "0.5")),
            on_error=_coerce_enum(ErrorPolicy, _get("ON_ERROR", "log_and_continue"), "DAI_ON_ERROR"),
            sqlite_path=_get("SQLITE_PATH", "./dai_local.db"),
            environment=_get("ENVIRONMENT", "development"),
            log_level=_get("LOG_LEVEL", "INFO"),
            emit_opentelemetry_spans=_get_bool("EMIT_OTEL_SPANS", False),
        )


# ─── Enum Coercion ────────────────────────────────────────────────────────────


def _coerce_enum(enum_cls: type, value: Any, field_name: str) -> Any:
    """Coerce a string value to an enum, with a helpful error on invalid input."""
    if isinstance(value, enum_cls):
        return value
    try:
        return enum_cls(value)
    except ValueError as exc:
        valid = [e.value for e in enum_cls]  # type: ignore[attr-defined]
        raise ValueError(
            f"Invalid value {value!r} for {field_name}. "
            f"Valid options: {valid}"
        ) from exc


# ─── Global Config State ──────────────────────────────────────────────────────

_config: DAIConfig | None = None
_config_lock = threading.Lock()


def configure(**kwargs: Any) -> None:
    """
    Set the global DAI SDK configuration.

    String values for enum fields are coerced automatically::

        dai.configure(backend="sqlite", on_error="raise_exception")
        # equivalent to:
        dai.configure(backend=BackendType.sqlite, on_error=ErrorPolicy.raise_exception)

    Args:
        **kwargs: Any field of DAIConfig. Unknown keys raise ValueError.

    Raises:
        ValueError: If an invalid enum value or unknown key is provided.
    """
    global _config

    # Coerce string enums
    if "backend" in kwargs:
        kwargs["backend"] = _coerce_enum(BackendType, kwargs["backend"], "backend")
    if "on_error" in kwargs:
        kwargs["on_error"] = _coerce_enum(ErrorPolicy, kwargs["on_error"], "on_error")

    # Validate field names
    valid_fields = {f.name for f in DAIConfig.__dataclass_fields__.values()}
    invalid_keys = set(kwargs) - valid_fields
    if invalid_keys:
        raise ValueError(f"Unknown DAIConfig fields: {invalid_keys}")

    with _config_lock:
        if _config is None:
            _config = DAIConfig.from_env()
        current = vars(_config)
        current.update(kwargs)
        _config = DAIConfig(**current)


def get_config() -> DAIConfig:
    """
    Return the current global configuration.

    If ``configure()`` has never been called, loads configuration from
    environment variables (including ``.env`` file if present).

    Returns:
        The active DAIConfig instance.
    """
    global _config
    with _config_lock:
        if _config is None:
            _config = DAIConfig.from_env()
        return _config


def reset_config() -> None:
    """
    Reset the global configuration to None.

    The next call to ``get_config()`` will reload from environment variables.
    Primarily used in tests to ensure isolation between test cases.
    """
    global _config
    with _config_lock:
        _config = None
