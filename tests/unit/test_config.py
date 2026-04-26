import os
from unittest.mock import patch

import pytest

from dai.config import BackendType, DAIConfig, ErrorPolicy, configure, get_config, reset_config


def test_config_from_env():
    with patch.dict(
        os.environ,
        {
            "DAI_BACKEND": "sqlite",
            "DAI_ENDPOINT": "http://foo",
            "DAI_TIMEOUT_SECONDS": "5.0",
            "DAI_ON_ERROR": "raise_exception",
            "DAI_EMIT_OTEL_SPANS": "true",
        },
    ):
        cfg = DAIConfig.from_env()
        assert cfg.backend == BackendType.sqlite
        assert cfg.endpoint == "http://foo"
        assert cfg.timeout_seconds == 5.0
        assert cfg.on_error == ErrorPolicy.raise_exception
        assert cfg.emit_opentelemetry_spans is True


def test_config_from_env_bool_parsing():
    with patch.dict(os.environ, {"DAI_EMIT_OTEL_SPANS": "yes"}):
        assert DAIConfig.from_env().emit_opentelemetry_spans is True
    with patch.dict(os.environ, {"DAI_EMIT_OTEL_SPANS": "1"}):
        assert DAIConfig.from_env().emit_opentelemetry_spans is True
    with patch.dict(os.environ, {"DAI_EMIT_OTEL_SPANS": "no"}):
        assert DAIConfig.from_env().emit_opentelemetry_spans is False
    with patch.dict(os.environ, {"DAI_EMIT_OTEL_SPANS": "invalid"}):
        assert DAIConfig.from_env().emit_opentelemetry_spans is False


def test_configure_unknown_fields_raises():
    reset_config()
    with pytest.raises(ValueError, match="Unknown DAIConfig fields"):
        configure(unknown_field="foo")


def test_configure_invalid_enum_raises():
    reset_config()
    with pytest.raises(ValueError):
        configure(backend="invalid_backend")


def test_configure_updates_existing():
    reset_config()
    configure(backend="noop")
    assert get_config().backend == BackendType.noop
    configure(endpoint="http://bar")
    assert get_config().backend == BackendType.noop
    assert get_config().endpoint == "http://bar"


def test_coerce_enum_already_enum():
    reset_config()
    configure(backend=BackendType.sqlite)
    assert get_config().backend == BackendType.sqlite
