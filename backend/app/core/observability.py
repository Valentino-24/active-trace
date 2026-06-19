"""OpenTelemetry initialization for FastAPI.

Activated by environment variables. The app runs normally even when
no OTLP exporter endpoint is configured.
"""

from __future__ import annotations

import logging

from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
try:
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
except ImportError:
    OTLPSpanExporter = None  # type: ignore

logger = logging.getLogger(__name__)


def setup_observability(service_name: str, otlp_endpoint: str | None = None) -> None:
    """Configure OpenTelemetry tracing for the application.

    Args:
        service_name: Name of the service for trace identification.
        otlp_endpoint: Optional OTLP HTTP exporter endpoint.
                       If None, traces are processed but not exported
                       (the app stays functional without a telemetry backend).
    """
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    if otlp_endpoint:
        if OTLPSpanExporter is None:
            logger.warning(
                "OTLP endpoint configured but opentelemetry-exporter-otlp-proto-http "
                "is not installed. Install it with: pip install opentelemetry-exporter-otlp-proto-http"
            )
        else:
            exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
            provider.add_span_processor(BatchSpanProcessor(exporter))
            logger.info("OTLP exporter configured at %s", otlp_endpoint)
    else:
        logger.info("No OTLP endpoint configured — traces will not be exported")

    trace.set_tracer_provider(provider)


def instrument_fastapi(app) -> None:
    """Instrument a FastAPI application with OpenTelemetry middleware.

    Args:
        app: FastAPI application instance.
    """
    FastAPIInstrumentor.instrument_app(app)
