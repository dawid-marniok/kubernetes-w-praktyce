# Przykłady: KEDA, skalowanie z metryki Prometheusa

**Cel:** skalować Deployment po liczbie żądań na sekundę z Prometheusa zamiast po CPU. KEDA nie zastępuje HPA: sama go tworzy i podaje mu metrykę.

**Gdzie:** klaster szkoleniowy EKS. Aplikację, Service i ServiceMonitor wgrasz w swoim namespace, ale `ScaledObject` tworzy na szkoleniu tylko prowadzący (kursant dostaje `forbidden`; podejrzeć możesz). Po szkoleniu całość na własnym klastrze z KEDA i Prometheusem. Komendy w tym katalogu (`cd przyklady/k8s/27-keda`).

| Plik | Co pokazuje |
|---|---|
| `app.yaml` | `keda-app` (example-app z metryką `http_requests_total`), Service, ServiceMonitor i generator ruchu `keda-load` z 0 replik |
| `scaledobject.yaml` | trigger `prometheus`: cel 3 żądania/s na pod, 1–6 replik |
| `scaledobject-cron.yaml` | trigger `cron`: 2 repliki w godzinach pracy, poza nimi 0 (tylko do przeczytania) |

Teoria (HPA, VPA, KEDA, skalowanie do zera): [`docs/k8s/autoskalowanie/`](../../../docs/k8s/autoskalowanie/README.md). HPA z dnia 3: [`14-hpa/`](../14-hpa/).

## Krok po kroku

Ustaw zmienne: `LOGIN=<Twój namespace>`, `REJESTR=<rejestr z obrazem example-app>` (obraz prowadzącego, ten sam co w lab19 „Dla chętnych”; adres od prowadzącego).

**1. Aplikacja z metryką**
```bash
sed "s|<REJESTR>|$REJESTR|" app.yaml | kubectl apply -f -
kubectl rollout status deploy/keda-app
```
W Grafanie → Explore → Prometheus:
```promql
sum(rate(http_requests_total{namespace="<login>", service="keda-app", route="/api/hello"}[1m]))
```
Co powinieneś zobaczyć: linię przy zera (generator ma 0 replik). Pierwsza seria pojawia się po ok. minucie (scrape co 15 s).

**2. ScaledObject**
```bash
sed "s/<login>/$LOGIN/" scaledobject.yaml | kubectl apply -f -
kubectl get scaledobject keda-app
kubectl get hpa
```
Co powinieneś zobaczyć: `READY True`, `ACTIVE False` i HPA `keda-hpa-keda-app` z `TARGETS 0/3 (avg)`, `MINPODS 1`, `MAXPODS 6`. Tego HPA nikt nie pisał: stworzył go operator KEDA. Nie twórz drugiego HPA dla tego samego Deploymentu.

**3. Ruch**

Drugi terminal: `kubectl get hpa,pods -l app=keda-app -w`. W pierwszym:
```bash
kubectl scale deploy keda-load --replicas=4
```
Co powinieneś zobaczyć: zapytanie z kroku 1 rośnie do ok. 12–15 req/s, po 30–60 s `TARGETS` powyżej 3, repliki 1 → 4–5. Wzór jak w HPA z dnia 3: ceil(15 / 3) = 5.

**4. Cisza**
```bash
kubectl scale deploy keda-load --replicas=0
```
Co powinieneś zobaczyć: po ok. 1–1,5 min repliki wracają do 1 (`stabilizationWindowSeconds: 30` jest na pokaz, domyślnie 5 min). Do zera nie zejdą: `minReplicaCount: 1`.

**5. Trigger bez metryki**
```bash
cat scaledobject-cron.yaml
```
Raport w godzinach pracy, poza nimi zero podów. Kilka triggerów w jednym `ScaledObject`: wygrywa ten, który chce więcej replik.

## Sprzątanie
```bash
kubectl delete scaledobject keda-app --ignore-not-found     # KEDA usuwa też swój HPA
sed "s|<REJESTR>|$REJESTR|" app.yaml | kubectl delete -f -
```

## Uwagi
- `apiVersion: keda.sh/v1alpha1`, a KEDA to projekt graduated w CNCF, używany produkcyjnie od lat. „alpha” w CRD znaczy tyle, ile mówi polityka projektu ([`docs/k8s/crd/`](../../../docs/k8s/crd/README.md), wersje API).
- KEDA nie skaluje: `kubectl describe scaledobject keda-app` (warunki i zdarzenia). Zwykle zły `serverAddress` albo zapytanie zwraca pusty wynik (sprawdź je najpierw w Explore). HPA powstaje także bez metryki, wtedy `TARGETS <unknown>`.
- Zero replik (`minReplicaCount: 0`) dla HTTP to zwykle zły pomysł: pierwsze żądanie po ciszy czeka na start poda. Dla workera kolejki dobry.
- Inne źródła: SQS, Kafka, RabbitMQ, Redis, Azure Service Bus. Na AWS uwierzytelnienie przez Pod Identity w `TriggerAuthentication`.
- Na co dzień: worker kolejki skalowany po długości kolejki zamiast po CPU, które przy czekaniu na I/O nic nie mówi.
