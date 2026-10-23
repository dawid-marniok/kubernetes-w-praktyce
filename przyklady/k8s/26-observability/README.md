# Przykłady: metryka, log i trace jednego problemu

**Cel:** przejść w Grafanie od metryki („że coś jest nie tak”) przez trace („gdzie”) do logu („co”), na żywej aplikacji z kilkoma usługami.

**Gdzie:** Grafana klastra szkoleniowego (adres i Twoje konto od prowadzącego, rola Editor). Aplikacja to **Kantyna** prowadzącego (namespace `kantyna`): zamawianie obiadów, nginx → API w Pythonie (`orders-api`) → płatności w Go (`payments`) → Postgres, kolejka SQS i worker, który zapisuje paragon do S3. Generator ruchu udaje pracowników. Awarie włącza prowadzący; Ty zadajesz te same zapytania w Explore i oglądasz te same trace'y. Własne zapytania dla swojego namespace'u piszesz w [`labs/lab19-observability/`](../../../labs/lab19-observability/).

Podstawy (Prometheus UI, ServiceMonitor z chartu Helm, pierwsze PromQL) są w [`30-prometheus/`](../30-prometheus/). Plików do wgrania tu nie ma, są zapytania. Ściąga PromQL, LogQL i TraceQL oraz mapa stosu: [`docs/k8s/observability/`](../../../docs/k8s/observability/README.md).

## Krok po kroku

**1. Dashboard: monitoring mówi „że”**

Dashboards → **Kantyna: aplikacja**, zakres `Last 15 minutes`, odświeżanie 10 s.

Co powinieneś zobaczyć: żądania/s, odsetek 5xx, p95 `orders-api` i płatności. Gdy płatności zwalniają, p95 rośnie z ok. 30 ms do ponad 1 s, a kafelek robi się czerwony. Wiesz, że jest wolno, nie wiesz dlaczego.

Explore → Prometheus → Code:
```promql
histogram_quantile(0.95, sum by (le, route) (rate(http_request_duration_seconds_bucket{namespace="kantyna", app="orders-api"}[2m])))
```
Co powinieneś zobaczyć: osobna linia dla każdej ścieżki. Wolna jest tylko `/api/orders`, menu nie.

**2. Alert**

Alerting → Alert rules → szukaj `Kantyna`. Otwórz `KantynaHighLatencyP95`: zapytanie PromQL, `for` (jak długo warunek musi trwać), etykieta `severity`, adnotacja `runbook_url`. Stany: Normal → Pending → Firing. Alert potrzebuje kilku minut: okno w PromQL plus `for`.

**3. Trace: observability mówi „gdzie”**

Explore → Tempo → TraceQL:
```traceql
{resource.service.name="orders-api" && name="POST /api/orders" && duration > 1s}
```
Co powinieneś zobaczyć: lista wolnych żądań. W jednym trace'ie: `loadgen` → `web` → `orders-api` (krótkie `SELECT`, `INSERT`) → `payments POST /pay` → długi span `bank authorize` → `SQS publish` → `worker` → `S3.PutObject`. Winne są płatności, a dokładnie wywołanie operatora płatności. Zakładka **Service Graph** pokazuje mapę usług z metryk Tempo.

**4. Ze spana do logów**

W spanie `payments POST /pay` → **Logs for this span**.

Co powinieneś zobaczyć: log z Loki z tym samym `trace_id`, `duration_ms` i numerem zamówienia (`order_ref`).

**5. Z logu do trace'a**

Explore → Loki → Code:
```logql
{namespace="kantyna", level="ERROR"}
```
Rozwiń linię z błędem → pole `trace_id` → przycisk **Tempo**. Co powinieneś zobaczyć: czerwony trace z błędem w `orders-api`; ten sam błąd (500) widzą `web` i `loadgen`.

**6. Logi poda, którego już nie ma**

Plik `crash-pod.yaml` jest w lab19 (krok 3):
```bash
kubectl apply -f ../../../labs/lab19-observability/crash-pod.yaml
kubectl logs crash
kubectl delete pod crash
kubectl logs crash                       # NotFound
```
Loki: `{namespace="<login>", pod="crash"}` → `START` i `error: brak konfiguracji DATABASE_URL`. Pod zniknął, logi zostały.

## Więcej zapytań na Kantynie

| Co | Zapytanie |
|---|---|
| żądania/s API po kodzie odpowiedzi | `sum by (status) (rate(http_requests_total{namespace="kantyna", app="orders-api"}[1m]))` |
| płatności/s po wyniku | `sum by (status) (rate(payments_requests_total{namespace="kantyna"}[1m]))` |
| odsetek 5xx w API | `sum(rate(http_requests_total{namespace="kantyna", status=~"5.."}[5m])) / sum(rate(http_requests_total{namespace="kantyna"}[5m]))` |
| trace'y z błędem | `{resource.service.name="orders-api" && status=error}` |
| N+1 w menu (dużo spanów `SELECT` w jednym żądaniu) | `{resource.service.name="orders-api" && name="GET /api/menu"}` |
| logi płatności dłuższych niż 1 s | `{namespace="kantyna", app="payments"} \| json \| duration_ms > 1000` |

## Uwagi
- Metryka mówi, że coś jest nie tak. Log mówi co. Trace mówi gdzie. Przejście jednym kliknięciem działa, bo wszystkie trzy mają te same etykiety (`namespace`, `app`) i ten sam `trace_id`.
- Na co dzień: loguj w JSON i dopisuj `trace_id` do każdej linii. To jedna linijka w konfiguracji loggera, a skraca szukanie z godzin do minut.
- „No data”: sprawdź zakres czasu (prawy górny róg) i literówki w etykietach. Nazwy etykiet podpowiada Explore po wpisaniu `{`.
