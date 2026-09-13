import pytest
from common.config import BaseAppSettings
from common.telemetry import init_tracing
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider


@pytest.mark.unit
def test_init_tracing_is_noop_without_endpoint() -> None:
    provider = trace.get_tracer_provider()
    settings = BaseAppSettings(environment="local")

    init_tracing("test-service", settings)

    assert trace.get_tracer_provider() is provider


@pytest.mark.unit
def test_init_tracing_configures_sdk_provider() -> None:
    settings = BaseAppSettings(
        environment="production",
        otlp_endpoint="http://collector:4318/v1/traces",
    )

    init_tracing("test-service", settings)

    assert isinstance(trace.get_tracer_provider(), TracerProvider)
