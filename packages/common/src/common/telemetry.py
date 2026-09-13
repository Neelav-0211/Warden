from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from common.config import BaseAppSettings


def init_tracing(service_name: str, settings: BaseAppSettings) -> None:
    """Configure process-wide OTLP tracing when an endpoint is available."""

    if settings.otlp_endpoint is None:
        return

    if isinstance(trace.get_tracer_provider(), TracerProvider):
        return

    provider = TracerProvider(resource=Resource.create({SERVICE_NAME: service_name}))
    exporter = OTLPSpanExporter(endpoint=settings.otlp_endpoint)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
