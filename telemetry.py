from opentelemetry import trace, metrics
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

from .config import settings


def setup_telemetry(app, engine):
    """
    Настраивает OpenTelemetry и инструментацию для FastAPI приложения.
    """
    resource = Resource(attributes={
        "service.name": settings.OTEL_SERVICE_NAME,
        "environment": settings.ENVIRONMENT,
    })

    # Настройка трассировки (трейсов)
    if settings.OTEL_EXPORTER_OTLP_ENDPOINT:
        tracer_provider = TracerProvider(resource=resource)
        otlp_exporter = OTLPSpanExporter(endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT)
        tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        trace.set_tracer_provider(tracer_provider)

    # Настройка метрик для Prometheus
    # Prometheus "тянет" метрики с эндпоинта, поэтому мы используем PrometheusMetricReader
    reader = PrometheusMetricReader()
    meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(meter_provider)

    # Инструментируем FastAPI приложение
    FastAPIInstrumentor.instrument_app(app)

    # Инструментируем движок SQLAlchemy
    SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)

    # Возвращаем reader, чтобы примонтировать эндпоинт для метрик
    return reader