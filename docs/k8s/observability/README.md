# Dzień 5 — ściąga: observability

**Wizualizacja:** [observability.html](observability.html). Otwórz plik w przeglądarce (dwuklik albo `open observability.html`). Są tam: diagram architektury stosu z przepływami metryk, logów i trace'ów, krok po kroku jedno żądanie ToDos, jak postawiliśmy stos (wersje, kolejność instalacji), cztery sposoby instrumentacji, przykładowy trace, ściąga zapytań z podstawianiem Twojego loginu i ćwiczenie z OpenTelemetry Operatorem.

**Kantyna:** [stos-i-kantyna.html](stos-i-kantyna.html). Aplikacja z demo prowadzącego: diagram architektury, droga zamówienia krok po kroku przez sześć usług, bazę i kolejkę, dokąd trafiają trace'y, logi i metryki, scenariusze awarii i zapytania.

Ćwiczysz w lab19 (`labs/lab19-observability/`).

## Trzy sygnały w jednym zdaniu

- **Metryki** mówią, że coś jest nie tak: liczby w czasie, Prometheus, język PromQL.
- **Logi** mówią co: linie tekstu z kontenerów, Loki, język LogQL.
- **Trace'y** mówią gdzie: historia jednego żądania przez serwisy, Tempo, język TraceQL.

Łączą je wspólne etykiety (`namespace`, `pod`) i identyfikator `trace_id`. Wszystkie trzy oglądasz w jednej Grafanie.

**Na k8s-sages:** cały stos stoi w namespace `monitoring`, jeden dla całej grupy. Instaluje go prowadzący. Ty dokładasz obiekty tylko w swoim namespace (`ServiceMonitor`, `PrometheusRule`, adnotacja na podzie) i masz w Grafanie konto z rolą Editor. Widzisz dane całego klastra, więc w zapytaniach zawsze filtruj po `namespace="<login>"`.

## Co gdzie działa

| Element | Namespace | Rola |
|---|---|---|
| Prometheus | `monitoring` | co 30 s pobiera metryki z celów (model pull), liczy reguły alertów |
| Prometheus Operator | `monitoring` | z `ServiceMonitor`, `PodMonitor`, `PrometheusRule` generuje konfigurację Prometheusa |
| kube-state-metrics | `monitoring` | stan obiektów API jako metryki: repliki, restarty, fazy podów |
| node-exporter | `monitoring` (DaemonSet) | metryki węzłów |
| kubelet / cAdvisor | węzeł | CPU i pamięć każdego kontenera |
| Alertmanager | `monitoring` | grupuje i wysyła alerty dalej |
| Grafana Alloy | `monitoring` (DaemonSet) | czyta logi z `/var/log/pods` i wysyła do Loki |
| Loki | `monitoring` | magazyn logów, indeksuje tylko etykiety |
| Tempo | `monitoring` | magazyn trace'ów, OTLP na 4317 (gRPC) i 4318 (HTTP), liczy span-metrics i service graph |
| OpenTelemetry Operator | `monitoring` | wstrzykuje SDK OpenTelemetry do podów z adnotacją |
| Grafana | `monitoring` | UI, Explore, dashboardy, alerty |

## Drogi sygnałów

```
metryki:  kubelet, kube-state-metrics, /metrics aplikacji  ◄── Prometheus (scrape co 30 s) ──► Grafana
logi:     stdout kontenera → /var/log/pods → Alloy (na węźle) → Loki ──► Grafana
trace'y:  SDK w procesie → OTLP :4318 → Tempo ──► Grafana
                                          └── span-metrics → Prometheus
```

- **Metryki:** Prometheus sam odpytuje cele. Aplikacja wystawia `/metrics`, a `ServiceMonitor` mówi Prometheusowi, skąd je brać. Adnotacje `prometheus.io/scrape` z poradników nie działają z Prometheus Operatorem.
- **Logi:** aplikacja nie wie o Loki, pisze na stdout. Dlatego logi poda, którego już nie ma, nadal są w Loki. Z logów w JSON Alloy wyciąga `level` jako etykietę i `trace_id` jako structured metadata.
- **Trace'y:** spany powstają w procesie aplikacji, więc ktoś musi tam wstawić SDK. Kolejne serwisy łączą się w jeden trace dzięki nagłówkowi `traceparent`. Serwis, który go nie przekaże, przerywa trace.

## Skąd biorą się spany: cztery sposoby

| Sposób | Co zmieniasz | Kto | Plusy | Minusy |
|---|---|---|---|---|
| 1. Ręcznie w kodzie (SDK + własne spany) | kod | programista | nazwy biznesowe, własne atrybuty, `trace_id` w logach | zmiana kodu w każdym serwisie i języku |
| 2. Auto-instrumentacja w obrazie | Dockerfile | build / CI | bez zmian w kodzie, od razu dużo spanów | przebudowa obrazu, tylko nazwy techniczne |
| 3. OpenTelemetry Operator | adnotacja na podzie | admin klastra + zespół | bez zmian w kodzie i obrazie, konfiguracja w jednym miejscu | webhook przy starcie poda, +50–100 Mi pamięci, wersję SDK wybiera operator |
| 4. eBPF (Beyla, OpenTelemetry eBPF Instrumentation) | nic w aplikacji | admin klastra | zero zmian, każdy język | płytkie spany, słabsza propagacja, uprawnienia uprzywilejowane |

Na szkoleniu: sposób 1 widzisz w Kantynie z dema prowadzącego i w `example-app`, sposób 3 włączasz w swoim ToDos. W praktyce łączy się 2 albo 3 (szkielet) z 1 (kilka spanów biznesowych).

### Jak działa operator

1. Prowadzący tworzy obiekt `Instrumentation` `otel` w `monitoring`: endpoint Tempo, sampler, propagatory.
2. Ty dopisujesz adnotację do **szablonu poda** (nie do metadanych Deploymentu):

   ```yaml
   spec:
     template:
       metadata:
         annotations:
           instrumentation.opentelemetry.io/inject-nodejs: "monitoring/otel"
   ```

3. Przy tworzeniu poda mutating webhook operatora dokłada init container z SDK, wolumen `emptyDir` i zmienne `NODE_OPTIONS`, `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_SERVICE_NAME`. W Twoim YAML-u tego nie ma, widać to dopiero w `kubectl get pod -o yaml`.

Ustaw własne `OTEL_SERVICE_NAME` (np. `todos-api-<login>`): wszyscy mają Deployment `api`, a bez tego trace'y całej grupy zlałyby się w jeden serwis. Ćwiczysz to w lab19, krok 6 (`otel-patch.yaml`). Tabela „Gdy nie ma trace'ów” jest w [observability.html](observability.html#lab).

## Zapytania na start

```promql
sum by (pod) (rate(container_cpu_usage_seconds_total{namespace="<login>", container!=""}[5m]))
increase(kube_pod_container_status_restarts_total{namespace="<login>"}[1h]) > 0
```

```logql
{namespace="<login>", container="api"}
{namespace="<login>"} |= "error"
```

```traceql
{resource.service.name="todos-api-<login>" && kind=server && name!="GET /api/health"}
{resource.service.name="todos-api-<login>" && status=error}
```

Więcej zapytań, z Twoim loginem podstawionym automatycznie, znajdziesz w [observability.html](observability.html#zapytania).

## Pułapki

- **Kardynalność:** `user_id` albo `trace_id` jako etykieta metryki lub strumienia Loki tworzy miliony serii. `trace_id` trzymaj w treści logu albo w structured metadata.
- **Sondy w trace'ach:** readiness odpytuje `/api/health` co kilka sekund i każde takie żądanie to trace. Filtruj je w TraceQL.
- **`console.log` bez `trace_id`:** przejście z logu do trace'a działa tylko wtedy, gdy log ma `trace_id`. Auto-instrumentacja dopisuje go sama przy loggerach `pino` i `winston` w JSON.
- **Grafana na publicznym adresie z hasłem `admin`:** pierwsza rzecz, którą sprawdza każdy skaner. Hasło z Secretu, dostęp przez Ingress z TLS albo port-forward.
