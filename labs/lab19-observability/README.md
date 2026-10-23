# lab19 — Observability: metryki, logi, alert, Prometheus i dashboard ToDos

**Cel:** w Grafanie znajdujesz zużycie CPU swoich podów, logi poda, którego już nie ma, i piszesz własny alert. W Prometheusie bez Grafany sprawdzasz, jak nowa aplikacja z Helma staje się celem, a na koniec importujesz dashboard swojego ToDos.

**Po labie masz:** zapytanie PromQL i LogQL dla swojego namespace'u, regułę `PrometheusRule` widoczną w Grafanie, podinfo jako cel `UP` w Prometheusie i dashboard „ToDos: mój namespace”.

**Czas:** ok. 40 minut. Kroki 1–8 to część podstawowa. Krok 6 się przeciąga (rollout, quota)? Zrób w tym czasie 7 i 8, a do 6 wróć.

Stos observability (Prometheus, Loki, Tempo, Grafana, agent logów Grafana Alloy) działa w namespace `monitoring`. Instaluje go prowadzący; Ty tylko korzystasz z Grafany i dokładasz obiekty w swoim namespace. Mapa stosu, droga sygnałów i ściąga zapytań: otwórz w przeglądarce [`docs/k8s/observability/observability.html`](../../docs/k8s/observability/observability.html), opis w [`docs/k8s/observability/README.md`](../../docs/k8s/observability/README.md).

## Zanim zaczniesz

- adres Grafany i Twoje hasło dostajesz od prowadzącego (login = Twój login, np. `adamd`); rola Editor: Explore, dashboardy, alerty
- nie masz adresu? Prowadzący udostępnia ekran z Grafaną, a Ty robisz kroki z `kubectl` i dyktujesz zapytania na czat
- Prometheus i Alertmanager nie mają publicznego adresu: w kroku 7 łączysz się przez `kubectl port-forward` (uprawnienie daje prowadzący, tylko do tych dwóch podów)

W zapytaniach poniżej zamień `<login>` na swój login.

## Poziom podstawowy

### 1. Dashboard namespace'u

Grafana → **Dashboards** → w wyszukiwarce wpisz `Compute Resources / Namespace (Pods)` (dashboard z kube-prometheus-stack) → u góry `namespace` = Twój login.

✅ Widzisz CPU i pamięć swoich podów oraz linie requests/limits.

### 2. PromQL: CPU podów

**Explore** → źródło **Prometheus** → tryb **Code**:

```promql
sum by (pod) (rate(container_cpu_usage_seconds_total{namespace="<login>", container!=""}[5m]))
```

Przełącz widok na wykres. Druga próba, restarty w ostatniej godzinie:

```promql
increase(kube_pod_container_status_restarts_total{namespace="<login>"}[1h]) > 0
```

### 3. Pod, który znika

```bash
kubectl apply -f crash-pod.yaml
kubectl get pod crash -w          # Ctrl+C po Completed/Error (ok. 5 s)
kubectl logs crash                # logi jeszcze są
sleep 30                          # Alloy zbiera logi z węzła co kilka sekund: daj mu czas
kubectl delete pod crash
kubectl logs crash                # Error from server (NotFound)
```

### 4. LogQL: logi poda, którego nie ma

**Explore** → źródło **Loki** → tryb **Code**, zakres czasu `Last 15 minutes`:

```logql
{namespace="<login>", pod="crash"}
```

Potem tylko błędy z całego namespace'u:

```logql
{namespace="<login>"} |= "error"
```

✅ Obie linie poda `crash` (`START`, `error: brak konfiguracji DATABASE_URL`), choć poda już nie ma.

### 5. Własny alert

```bash
sed "s/<login>/$(kubectl config view --minify -o jsonpath='{..namespace}')/g" prometheusrule.yaml > my-rule.yaml
grep namespace my-rule.yaml            # sprawdź, czy jest Twój login
kubectl apply -f my-rule.yaml
kubectl apply -f crashloop.yaml        # Deployment, który restartuje się co kilkanaście sekund
kubectl get prometheusrule
```

Po 1–2 minutach: Grafana → **Alerting** → **Alert rules** → wyszukaj `PodCzestoRestartuje` (źródło danych Prometheus). Po kilku restartach (ok. 3 min, bo restarty mają rosnący odstęp) reguła przechodzi w `Pending`, a po kolejnych 2 minutach (`for: 2m`) w `Firing`.

### 6. Trace'y w Twoim ToDos

Twoje API (Deployment `api` z ToDos) nie ma w kodzie OpenTelemetry. Nie zmieniasz kodu ani obrazu: w `monitoring` działa OpenTelemetry Operator z obiektem `Instrumentation` o nazwie `otel`. Wystarczy adnotacja na szablonie poda, a operator przy tworzeniu poda dołoży SDK.

```bash
sed "s/<login>/$(kubectl config view --minify -o jsonpath='{..namespace}')/g" otel-patch.yaml > my-otel-patch.yaml
cat my-otel-patch.yaml                 # adnotacja, OTEL_SERVICE_NAME z Twoim loginem, limit pamięci 384Mi
kubectl patch deployment api --patch-file my-otel-patch.yaml
kubectl rollout status deployment api
```

Masz politykę egress z ToDos dnia 4 (`kubectl get networkpolicy`)? Dopuść ruch do Tempo: `kubectl apply -f otel-egress.yaml`.

Zobacz, co operator dopisał do poda (tego nie ma w Twoim YAML-u):

```bash
kubectl get pod -l app=todos-api -o jsonpath='{.items[0].spec.initContainers[*].name}{"\n"}'
kubectl get pod -l app=todos-api -o yaml | grep -A1 -E 'name: (NODE_OPTIONS|OTEL_EXPORTER_OTLP_ENDPOINT|OTEL_SERVICE_NAME)$'
```

✅ Init container `opentelemetry-auto-instrumentation-nodejs`, a w kontenerze `api` zmienne `NODE_OPTIONS=--require /otel-auto-instrumentation-nodejs/…`, `OTEL_EXPORTER_OTLP_ENDPOINT=http://tempo.monitoring.svc:4318`.

Otwórz swoje ToDos (`https://todos-<login>.k8s.marniok.dev`), dodaj, odhacz i usuń kilka zadań. Po ok. 30 s: **Explore** → źródło **Tempo** → **TraceQL**:

```traceql
{resource.service.name="todos-api-<login>" && kind=server && name!="GET /api/health"}
```

Otwórz trace `POST /api/todos`. Pod spanem serwera są spany Expressa (middleware, handler) i spany bazy (`mongoose…`, `mongodb…`). Który krok zajął najwięcej czasu?

Bez filtra `name!=` zobaczysz głównie `GET /api/health`: to sonda readiness, która co kilka sekund też jest żądaniem HTTP.

**Uwaga:** `kubectl patch` zmienił tylko obiekt w klastrze. Przy następnym `kubectl apply -f api.yaml` limit pamięci wróci do 256Mi. Przenieś adnotację, zmienną i limit do swojego `api.yaml`.

### 7. Prometheus bez Grafany: aplikacja z Helma jako nowy cel

Te same kroki prowadzący pokazał na demie. Pliki: [`przyklady/k8s/30-prometheus/`](../../przyklady/k8s/30-prometheus/).

```bash
P=../../przyklady/k8s/30-prometheus
helm upgrade --install pi oci://ghcr.io/stefanprodan/charts/podinfo --version 6.15.0 -f $P/values-podinfo.yaml --wait
kubectl apply -f $P/ruch.yaml
kubectl get servicemonitor pi-podinfo -o yaml | grep -A8 '^spec:'
```

ServiceMonitora nie piszesz: chart tworzy go, bo w wartościach jest `serviceMonitor.enabled: true`. Wybiera Service po etykiecie `app.kubernetes.io/name: pi-podinfo` i czyta port o nazwie `http`.

W drugim terminalu (zostaw włączone):

```bash
kubectl port-forward -n monitoring svc/kube-prometheus-stack-prometheus 9090:9090
```

Otwórz `http://localhost:9090`:

- **Status → Target health** (w starszych wersjach: Targets), wyszukaj swój login: pula `serviceMonitor/<login>/pi-podinfo/0`, stan `UP`. Nowy cel pojawia się po 30–60 s.
- **Status → Configuration**, wyszukaj `pi-podinfo`: ten fragment `prometheus.yml` wygenerował operator z Twojego ServiceMonitora.
- **Query** → Graph:

```promql
sum by (status) (rate(http_requests_total{namespace="<login>", service="pi-podinfo"}[1m]))
histogram_quantile(0.95, sum by (le, path) (rate(http_request_duration_seconds_bucket{namespace="<login>", service="pi-podinfo"}[2m])))
```

- **Alerts**: znajdź swoją regułę `PodCzestoRestartuje` z kroku 5. Reguły liczy Prometheus, Grafana tylko je pokazuje.

✅ Cel `UP`, ok. 2 żądania/s ze statusem `200` i mniejsza linia `500`, p95 dla `path="delay"` ok. 1 s.

Port-forward kończy się `forbidden`? Uprawnienie jeszcze nie zostało nadane: te same zapytania wpisz w Grafana Explore.

Opcjonalnie Alertmanager: `kubectl port-forward -n monitoring svc/kube-prometheus-stack-alertmanager 9093:9093`, `http://localhost:9093`: alerty z całego klastra po grupowaniu i wyciszenia.

### 8. Dashboard ToDos

Grafana → **Dashboards** → **New** → **Import** → **Upload dashboard JSON file** → plik `dashboard-todos.json` z tego katalogu → **Import**. U góry wybierz `namespace` = swój login.

Co jest na dashboardzie i skąd:

| Rząd | Źródło | Działa od razu? |
|---|---|---|
| Stan: pody gotowe, repliki dostępne/pożądane, restarty | kube-state-metrics (Prometheus) | tak |
| CPU i pamięć a requests/limits (linie przerywane) | cAdvisor z kubeleta + kube-state-metrics | tak |
| Żądania przez web na minutę po kodzie, linie z błędem | logi nginx i api z Lokiego (`count_over_time`) | tak, gdy klikasz w ToDos |
| API: żądania/s, błędy, p95 po trasie | metryki liczone przez Tempo ze spanów (`traces_spanmetrics_*`) | dopiero po kroku 6 |
| Logi: błędy i wszystkie logi api | Loki | tak |

Kliknij kilka razy w swoim ToDos i odśwież dashboard. Backend ToDos nie wystawia `/metrics`, a mimo to masz ruch, błędy i czasy odpowiedzi: z logów i z trace'ów. Otwórz dowolny panel → **Edit**, żeby zobaczyć zapytanie.

✅ Rzędy „Stan” i „Zasoby” pokazują Twoje `api`, `web` i `mongo`; po kroku 6 rząd „API z trace'ów” pokazuje `POST /api/todos`.

### SUKCES

- [ ] Loki pokazuje linię `error: brak konfiguracji DATABASE_URL` z poda `crash`, którego już nie ma
- [ ] wykres CPU pokazuje Twoje pody
- [ ] reguła `PodCzestoRestartuje` z Twojego namespace'u jest widoczna w Grafanie (stan `Pending` albo `Firing`)
- [ ] w Tempo jest trace `POST /api/todos` z Twojego `todos-api-<login>` ze spanem bazy pod spanem serwera
- [ ] (7) w Prometheusie cel `serviceMonitor/<login>/pi-podinfo/0` ma stan `UP`
- [ ] (8) dashboard „ToDos: mój namespace” pokazuje Twój namespace

## Dla chętnych

**A. Aplikacja z trzema sygnałami.** `example-app` (kod w `app/example-app/`) wystawia `/metrics`, pisze logi JSON z `trace_id` i wysyła trace'y do Tempo.

```bash
sed "s|<REJESTR>|<konto>.dkr.ecr.eu-central-1.amazonaws.com/trener|" example-app.yaml | kubectl apply -f -   # obraz prowadzącego, nie Twój <REJESTR>
kubectl get pods -l 'app in (example-app,example-load)'
kubectl get servicemonitor
```

Po 1–2 minutach w Explore:

```promql
sum by (route, status) (rate(http_requests_total{namespace="<login>"}[5m]))
histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket{namespace="<login>", route="/api/slow"}[5m])))
```

```logql
{namespace="<login>", app="example-app"} | json | level="error"
```

Tempo (TraceQL): `{resource.service.name="example-app" && name=~".*slow.*"}` → otwórz trace i zobacz spany `db.query` i `render`. Z linii logu z `trace_id` przejdziesz do trace'a przyciskiem przy polu `trace_id`.

**B. Alert na odsetek błędów.** Dopisz w `my-rule.yaml` alert `ExampleAppBledy`: więcej niż 10% żądań z kodem 5xx przez 2 minuty. Podpowiedź: dzielisz `sum(rate(http_requests_total{…, status=~"5.."}[5m]))` przez `sum(rate(http_requests_total{…}[5m]))`.

**C. Tracing przez kilka serwisów.** W Tempo: `{resource.service.name="orders-api" && name="POST /api/orders"}` (Kantyna prowadzącego, namespace `kantyna`, `https://kantyna.k8s.marniok.dev`). Ile spanów ma jeden trace i który serwis zjada najwięcej czasu? Zakładka **Service Graph** pokazuje mapę wywołań.

**D. Etykiety logów.** W Loki otwórz **Label browser**. Jakie etykiety ma każdy strumień? Dlaczego nie ma etykiety `user_id` albo `trace_id`? (wskazówka: kardynalność)

**E. Własny panel.** Na dashboardzie ToDos dodaj panel z p95 podinfo z kroku 7 albo z liczbą linii logów na pod: `sum by (pod) (count_over_time({namespace="<login>"}[5m]))` (źródło Loki). Zapisz dashboard (**Save**).

**F. ServiceMonitor czy PodMonitor.** `kubectl get podmonitor -A`: kto używa PodMonitora i dlaczego nie ServiceMonitora? (wskazówka: czy ten pod ma Service?)

## Gdy coś nie działa

| Objaw | Co zrobić |
|---|---|
| Loki: `No data` | Zakres czasu w prawym górnym rogu; literówka w loginie. Sprawdź samo `{namespace="<login>"}` |
| Prometheus: brak wyników | `container_cpu_usage_seconds_total{namespace="<login>"}` bez `rate`; czy masz jakieś pody: `kubectl get pods` |
| `kubectl apply` reguły: `forbidden` | Brak uprawnień do `prometheusrules` w namespace; zgłoś prowadzącemu |
| Reguła nie pojawia się w Grafanie | Odczekaj 1–2 min (Prometheus przeładowuje reguły); `kubectl get prometheusrule lab19-alerts -o yaml` — czy login podmieniony? |
| `example-app` w `ImagePullBackOff` | Zły rejestr w obrazie: `kubectl describe pod -l app=example-app` |
| Brak metryk `http_requests_total` | `kubectl get servicemonitor example-app`; port w Service musi mieć nazwę `http` |
| Pod `api` bez init containera `opentelemetry-auto-instrumentation-nodejs` | Pod powstał przed patchem: `kubectl rollout restart deployment api`. Adnotacja musi być w `spec.template.metadata`, nie w `metadata` Deploymentu |
| `api` w `OOMKilled` po patchu | Limit pamięci nie został podniesiony: `kubectl get deploy api -o jsonpath='{..resources}'`, powinno być `memory: 384Mi` |
| Tempo: brak `todos-api-<login>` | Odczekaj 30 s i kliknij kilka razy w ToDos. Polityka egress z dnia 4 blokuje OTLP: `kubectl apply -f otel-egress.yaml`. Błędy eksportu: `kubectl logs deploy/api \| grep -i otlp` |
| Port-forward: `forbidden … pods/portforward` | Uprawnienie nie zostało jeszcze nadane: zapytania z kroku 7 wpisz w Grafana Explore, zgłoś prowadzącemu |
| Port-forward: `address already in use` | Port 9090 zajęty lokalnie: `kubectl port-forward … 19090:9090` i `http://localhost:19090` |
| Brak celu `pi-podinfo` w Target health | Odczekaj minutę; `kubectl get servicemonitor pi-podinfo`; czy Service ma port `http`: `kubectl get svc pi-podinfo -o yaml` |
| Cel `pi-podinfo` w stanie `DOWN` | Polityka deny na cały namespace (`podSelector: {}`) blokuje ruch z `monitoring`. Polityki ToDos z dnia 4 obejmują tylko pody ToDos |
| Dashboard ToDos: `No data` w rzędzie „API z trace'ów” | Normalne przed krokiem 6. Po kroku 6: kliknij w ToDos i odczekaj 1–2 min (Tempo liczy metryki ze spanów z opóźnieniem) |
| Dashboard ToDos: pusta lista `namespace` | Zmienna szuka Deploymentu `api`. Masz inną nazwę? Wpisz namespace ręcznie albo zmień zapytanie w **Settings → Variables** |
| `kubectl patch`: `exceeded quota` | Nowe pody liczą się do quoty razem ze starymi w trakcie rolloutu. Usuń zbędne pody (`kubectl delete cluster pg`, `crashloop`) i powtórz |

## Sprzątanie

```bash
kubectl delete -f crashloop.yaml -f my-rule.yaml
kubectl delete -f ../../przyklady/k8s/30-prometheus/ruch.yaml --ignore-not-found
helm uninstall pi 2>/dev/null           # razem z ServiceMonitorem; dashboard ToDos w Grafanie zostaje
# trace'y ToDos zostają włączone (przydadzą się w projekcie). Wyłączenie: usuń adnotację i zmienną z api.yaml i kubectl apply
kubectl delete -f example-app.yaml --ignore-not-found 2>/dev/null || sed "s|<REJESTR>|x|" example-app.yaml | kubectl delete -f - --ignore-not-found
```
