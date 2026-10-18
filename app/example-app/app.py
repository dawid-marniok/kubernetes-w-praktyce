#!/usr/bin/env python3
"""
example-app: mała aplikacja do labu observability (lab19).
- metryki Prometheusa na /metrics (http_requests_total, http_request_duration_seconds)
- logi JSON na stdout, z trace_id (Alloy → Loki)
- trace'y OpenTelemetry przez OTLP/HTTP (→ Tempo)

Konfiguracja przez standardowe zmienne OpenTelemetry:
  OTEL_EXPORTER_OTLP_ENDPOINT  np. http://tempo.monitoring.svc:4318 (SDK sam dopisze /v1/traces)
  OTEL_SERVICE_NAME            domyślnie example-app
"""

import json
import os
import random
import sys
import time
from datetime import datetime, timezone

from flask import Flask, g, jsonify, request
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

SERVICE = os.getenv("OTEL_SERVICE_NAME", "example-app")

# --- OpenTelemetry: trace'y ---
provider = TracerProvider(resource=Resource.create({
    "service.name": SERVICE,
    "service.version": "1.0.0",
    "deployment.environment": os.getenv("ENVIRONMENT", "szkolenie"),
}))
if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
    # bez argumentu endpoint: SDK bierze OTEL_EXPORTER_OTLP_ENDPOINT i dopisuje /v1/traces
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer(__name__)

app = Flask(__name__)
FlaskInstrumentor().instrument_app(app, excluded_urls="health,metrics")   # sondy i scrape bez trace'ów

# --- Prometheus: metryki ---
# etykieta "route", nie "endpoint": endpoint to etykieta celu, którą dokleja ServiceMonitor (nazwa portu)
REQUESTS = Counter("http_requests_total", "Liczba żądań HTTP", ["method", "route", "status"])
DURATION = Histogram("http_request_duration_seconds", "Czas obsługi żądania", ["method", "route"])


def log(level, message, **fields):
    """Jedna linia JSON na stdout. trace_id łączy log z trace'em w Tempo."""
    ctx = trace.get_current_span().get_span_context()
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "message": message,
        "service": SERVICE,
        **fields,
    }
    if ctx.is_valid:
        entry["trace_id"] = format(ctx.trace_id, "032x")
    print(json.dumps(entry, ensure_ascii=False), file=sys.stdout, flush=True)


@app.before_request
def _start():
    g.start = time.perf_counter()


@app.after_request
def _metrics(resp):
    if request.path not in ("/metrics", "/health"):
        route = request.url_rule.rule if request.url_rule else "unknown"
        REQUESTS.labels(request.method, route, str(resp.status_code)).inc()
        DURATION.labels(request.method, route).observe(time.perf_counter() - g.start)
    return resp


@app.route("/")
def index():
    return jsonify({
        "service": SERVICE,
        "endpoints": ["/api/hello?name=…", "/api/slow", "/api/error", "/metrics", "/health"],
    })


@app.route("/api/hello")
def hello():
    name = request.args.get("name", "World")
    trace.get_current_span().set_attribute("user.name", name)
    log("info", "hello", name=name)
    return jsonify({"message": f"Hello, {name}!"})


@app.route("/api/slow")
def slow():
    # dwa „kroki” jako osobne spany: w Tempo widać, który zjadł czas
    with tracer.start_as_current_span("db.query"):
        time.sleep(random.uniform(0.05, 0.4))
    with tracer.start_as_current_span("render"):
        time.sleep(random.uniform(0.01, 0.05))
    log("info", "slow request done")
    return jsonify({"status": "ok"})


@app.route("/api/error")
def error():
    log("error", "simulated failure", reason=request.args.get("type", "generic"))
    trace.get_current_span().set_status(trace.Status(trace.StatusCode.ERROR, "simulated failure"))
    return jsonify({"error": "simulated failure"}), 500


@app.route("/metrics")
def metrics():
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    log("info", "starting", port=8080, otlp=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "wyłączone"))
    app.run(host="0.0.0.0", port=8080)
