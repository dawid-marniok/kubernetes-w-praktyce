# example-app — aplikacja do labu observability

Mała aplikacja Flask, która wystawia wszystkie trzy sygnały naraz. Używasz jej w `labs/lab19-observability/` (część dla chętnych).

| Sygnał | Jak | Gdzie zobaczysz |
|---|---|---|
| Metryki | `/metrics` (biblioteka `prometheus-client`): `http_requests_total`, `http_request_duration_seconds` (etykiety `route`, `status`) | Prometheus przez ServiceMonitor |
| Logi | JSON na stdout, z polem `trace_id` | Loki: `{namespace="<login>", app="example-app"} \| json` |
| Trace'y | OpenTelemetry SDK, OTLP/HTTP na `OTEL_EXPORTER_OTLP_ENDPOINT` | Tempo: `{resource.service.name="example-app"}` |

## Endpointy

| Ścieżka | Co robi |
|---|---|
| `/api/hello?name=Ala` | odpowiada od razu, log `info` |
| `/api/slow` | 50–450 ms, w trace'ie dwa spany: `db.query` i `render` |
| `/api/error` | zwraca 500, log `error` (do alertu na odsetek błędów) |
| `/metrics`, `/health` | metryki i sonda |

## Obraz

Obraz buduje prowadzący i wypycha do rejestru szkolenia (`<REJESTR>/example-app:1.0.0`, opis rejestru w `setup/`). Chcesz zbudować sam:

```bash
cd app/example-app
docker build -t <REJESTR>/example-app:1.0.0 .
# Mac z Apple Silicon, a klaster na amd64:
docker build --platform linux/amd64 -t <REJESTR>/example-app:1.0.0 .
docker push <REJESTR>/example-app:1.0.0
```

Lokalnie bez klastra (trace'y wyłączone, bo nie ma `OTEL_EXPORTER_OTLP_ENDPOINT`):

```bash
docker run --rm -p 8080:8080 <REJESTR>/example-app:1.0.0
curl localhost:8080/api/hello?name=Ala
curl -s localhost:8080/metrics | grep http_requests_total
```

Na kind: `kind load docker-image <REJESTR>/example-app:1.0.0 --name <klaster>`.
