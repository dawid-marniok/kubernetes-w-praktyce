# Przykłady: Prometheus bez Grafany, aplikacja z Helma i ServiceMonitor

**Cel:** zobaczyć, jak Prometheus znajduje nową aplikację. Instalujesz Helmem gotowy chart z metrykami i ServiceMonitorem, a potem w interfejsie samego Prometheusa sprawdzasz cel (target), konfigurację wygenerowaną przez operatora i pierwsze zapytania PromQL. Na koniec to samo zapytanie w Grafanie.

**Gdzie:** klaster szkoleniowy EKS, Twój namespace. Prometheus działa w namespace `monitoring` i nie ma publicznego adresu: łączysz się przez `kubectl port-forward` (uprawnienie daje prowadzący). Komendy w tym katalogu (`cd przyklady/k8s/30-prometheus`).

| Plik | Co pokazuje |
|---|---|
| `values-podinfo.yaml` | wartości chartu podinfo 6.15.0: `serviceMonitor.enabled: true`, zasoby, securityContext zgodny z `restricted` |
| `ruch.yaml` | generator ruchu: strona główna co 0,5 s, co jakiś czas błąd 500 i wolne żądanie 1 s |

Teoria (model pull, ServiceMonitor, PromQL, alerty): [`docs/k8s/observability/`](../../../docs/k8s/observability/README.md). Helm: [`22-helm/`](../22-helm/).

## Krok po kroku

**1. Aplikacja z metrykami z chartu**
```bash
helm upgrade --install pi oci://ghcr.io/stefanprodan/charts/podinfo --version 6.15.0 -f values-podinfo.yaml --wait
kubectl get deploy,svc,servicemonitor -l app.kubernetes.io/name=pi-podinfo
kubectl apply -f ruch.yaml
```
Co powinieneś zobaczyć: Deployment i Service `pi-podinfo` oraz ServiceMonitor `pi-podinfo`. ServiceMonitora nie pisałeś: chart tworzy go, bo w wartościach jest `serviceMonitor.enabled: true`. Sprawdź, co w nim jest:
```bash
kubectl get servicemonitor pi-podinfo -o yaml | grep -A8 '^spec:'
kubectl get svc pi-podinfo -o jsonpath='{.spec.ports[*].name}'; echo
```
ServiceMonitor wybiera Service po etykiecie `app.kubernetes.io/name: pi-podinfo` i czyta port o nazwie `http`. Ta nazwa musi być w Service.

**2. Prometheus UI**

W drugim terminalu (zostaw włączone):
```bash
kubectl port-forward -n monitoring svc/kube-prometheus-stack-prometheus 9090:9090
```
Otwórz `http://localhost:9090`.

- **Status → Target health** (w starszych wersjach: Targets): wyszukaj swój login. Pula `serviceMonitor/<login>/pi-podinfo/0`, cel w stanie `UP`, czas ostatniego scrape'u i jego długość. Nowy cel pojawia się po ok. 30–60 s: operator musi przeładować konfigurację.
- **Status → Service discovery**: ta sama pula. Widać etykiety odkryte z API Kubernetesa (`__meta_kubernetes_…`) i te, które zostają po relabelingu (`namespace`, `pod`, `service`, `job`).
- **Status → Configuration**: wyszukaj `pi-podinfo`. Ten fragment `prometheus.yml` wygenerował operator z Twojego ServiceMonitora.

**3. PromQL w Prometheusie**

Zakładka **Query**, wpisz i przełącz na **Graph**:
```promql
up{namespace="<login>"}
sum by (status) (rate(http_requests_total{namespace="<login>", service="pi-podinfo"}[1m]))
histogram_quantile(0.95, sum by (le, path) (rate(http_request_duration_seconds_bucket{namespace="<login>", service="pi-podinfo"}[2m])))
```
Co powinieneś zobaczyć: `up` = 1 dla celu podinfo; ok. 2 żądania/s ze statusem `200` i mniejszą linię `500`; p95 dla `path="delay"` ok. 1 s, dla strony głównej (`root`) kilka milisekund. Etykietę `service` dokleił ServiceMonitor, w kodzie aplikacji jej nie ma.

**4. To samo w Grafanie**

Grafana → **Explore** → źródło **Prometheus** → tryb **Code**, wklej drugie zapytanie z kroku 3. Grafana nie przechowuje metryk, tylko pyta Prometheusa. Dalej: **Add to dashboard** → nowy dashboard → zapisz.

**5. Alertmanager (opcjonalnie)**
```bash
kubectl port-forward -n monitoring svc/kube-prometheus-stack-alertmanager 9093:9093
```
`http://localhost:9093`: aktywne alerty z całego klastra, grupowanie, wyciszenia (Silences). Reguły alertów są w Prometheusie (**Alerts**), Alertmanager tylko je rozsyła.

## Sprzątanie
```bash
kubectl delete -f ruch.yaml
helm uninstall pi                       # usuwa też ServiceMonitor: cel znika z Target health po ok. minucie
```

## Uwagi
- ServiceMonitor czy PodMonitor: ServiceMonitor wybiera **Service** po etykietach i czyta nazwany port Service'u, a do metryk dokleja etykietę `service`. PodMonitor wybiera **pody** bezpośrednio, port to nazwa portu kontenera. PodMonitor wybierasz, gdy Service jest zbędny: worker kolejki, Job, agent jako DaemonSet, operator. Operator CloudNativePG z lab18 jest zbierany PodMonitorem (`kubectl get podmonitor -A`).
- Target `DOWN` z `connection refused` albo timeoutem: zły port albo polityka sieciowa blokuje ruch z namespace `monitoring`. Polityki ToDos z dnia 4 obejmują tylko pody `app.kubernetes.io/part-of: todos`, podinfo ich nie dotyczy. Masz politykę deny na cały namespace (`podSelector: {}`)? Dopuść ruch z `monitoring` na port 9898.
- Celu nie ma w ogóle: ServiceMonitor nie pasuje do Service'u (etykiety w `selector`) albo port nie ma nazwy. Prometheus nie zgłasza błędu, po prostu nic nie zbiera.
- `forbidden` przy port-forward: uprawnienie nie zostało jeszcze nadane. Te same zapytania zrobisz w Grafana Explore (krok 4).
- Adnotacje `prometheus.io/scrape` w podzie podinfo to konwencja starszych konfiguracji. Prometheus Operator ich nie czyta: liczy się ServiceMonitor.
- Na co dzień: aplikacja z chartu Helm zwykle ma w wartościach `serviceMonitor.enabled` albo `metrics.serviceMonitor.enabled`. Sprawdź `helm show values`, zanim napiszesz ServiceMonitor ręcznie.
