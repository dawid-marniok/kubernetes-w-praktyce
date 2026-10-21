# Dzień 3 — ściąga: autoskalowanie

**Wizualizacja:** [autoskalowanie.html](autoskalowanie.html). Otwórz plik w przeglądarce (dwuklik albo `open autoskalowanie.html`). Są tam diagramy HPA, KEDA i VPA, symulator HPA (obciążenie, requests, cel, okno stabilizacji) i tabela porównawcza.

Gotowe manifesty: `przyklady/k8s/14-hpa/`. Ćwiczysz w lab11 (zasoby, quota, HPA).

## Pięć mechanizmów w jednym zdaniu

- **HPA** dokłada podów (scale out).
- **VPA** robi pody większe (scale up).
- **In-place resize** to mechanizm, dzięki któremu VPA może zmienić rozmiar bez restartu poda.
- **KEDA** skaluje według zdarzeń, np. długości kolejki, i potrafi zejść do zera. Pod spodem i tak steruje HPA.
- **Cluster Autoscaler / Karpenter / EKS Auto Mode** dokładają węzły, gdy pody nie mieszczą się na istniejących.

**Na k8s-sages:** działają HPA (metrics-server jest add-onem EKS) i in-place resize (Kubernetes 1.35). KEDA, VPA i Karpentera nie ma. Węzłów jest stała liczba (3), a Twój namespace ma ResourceQuota.

## HPA: jak działa

```
kubelet ──► metrics-server ──► kube-apiserver (metrics.k8s.io)
                                    ▲
                                    │ co 15 s: obiekt HPA, pody, ich zużycie i requests
                              kontroler HPA (kube-controller-manager)
                                    │ desiredReplicas = ceil(currentReplicas × currentMetric / target)
                                    ▼
                         Deployment /scale → spec.replicas → ReplicaSet → pody
```

1. metrics-server pobiera z kubeletów bieżące zużycie CPU i pamięci. Bez historii, tylko ostatni pomiar (to samo widzisz w `kubectl top`).
2. Udostępnia je jako API `metrics.k8s.io` w kube-apiserverze.
3. Kontroler HPA **co 15 s** czyta obiekt HPA, pody Deploymentu, ich zużycie i `requests`.
4. Liczy `desiredReplicas = ceil(currentReplicas × currentMetric / target)`. Przykład: 3 pody, `requests.cpu: 200m`, każdy zużywa 240m = 120%, cel 50% → `ceil(3 × 120 / 50) = ceil(7,2) = 8`. Odchylenie mniejsze niż ok. 10% (tolerancja) = bez zmian. Potem `behavior` i `minReplicas`/`maxReplicas`.
5. Zapisuje `spec.replicas` w Deploymencie. Dalej działa zwykły ReplicaSet, scheduler i quota.

**Procent liczony jest względem `requests`, nie limitów.** Bez `requests.cpu` HPA nie ma od czego liczyć: `TARGETS <unknown>/50%`, `ScalingActive=False`, zdarzenie `FailedGetResourceMetric`. Rozwiązanie: ustaw `requests` albo użyj celu bezwzględnego `type: AverageValue`.

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: web
spec:
  scaleTargetRef: {apiVersion: apps/v1, kind: Deployment, name: web}
  minReplicas: 1
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target: {type: Utilization, averageUtilization: 50}   # % requestu
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies: [{type: Pods, value: 1, periodSeconds: 60}]
```

| `behavior` domyślnie | scaleUp | scaleDown |
|---|---|---|
| okno stabilizacji | 0 s (od razu) | 300 s: bierze najwyższą rekomendację z ostatnich 5 min |
| tempo | max(+100%, +4 pody) na 15 s | do −100% na 15 s |

Pułapki:
- `replicas` w manifeście Deploymentu nadpisze HPA przy każdym `kubectl apply`. Usuń to pole.
- Quota: HPA ustawi 8, ale ReplicaSet nie utworzy podów ponad ResourceQuota (`exceeded quota` w `kubectl describe rs`).
- Pełne węzły: nowe pody w `Pending` (`Insufficient cpu`). To skalowanie węzłów, nie HPA.
- HPA na pamięci rzadko ma sens: runtime'y zwykle nie oddają pamięci, repliki nie schodzą.
- Kilka metryk: HPA bierze najwyższy wynik.
- HPA nie schodzi do zera (`minReplicas: 0` to wciąż funkcja alpha). Do zera: KEDA.

## KEDA: skalowanie od zdarzeń

KEDA (Kubernetes Event-Driven Autoscaling) to projekt CNCF w statusie graduated, instalowany Helmem przez administratora klastra (`helm install keda kedacore/keda -n keda --create-namespace`). Na k8s-sages jej nie ma.

```
ScaledObject ─watch─► keda-operator ─tworzy─► HPA keda-hpa-<nazwa>
                        │       │                │        ▲
            pyta źródło │       │ 0 ↔ 1          │ 1 ↔ N  │ external.metrics.k8s.io
                        ▼       ▼                │        │
                 SQS, Kafka…   Deployment ◄──────┘    metrics adapter KEDA ─► pyta źródło
```

- **ScaledObject** opisuje co skalować, na podstawie jakich triggerów, w jakim zakresie (`minReplicaCount` domyślnie 0).
- **Operator** tworzy i utrzymuje HPA `keda-hpa-<nazwa>`. Nie twórz drugiego HPA dla tego samego Deploymentu.
- Co `pollingInterval` (domyślnie 30 s) scaler pyta źródło, np. o długość kolejki SQS.
- **0 ↔ 1 robi sama KEDA** (aktywacja; w dół po `cooldownPeriod`, domyślnie 300 s). **1 ↔ N robi HPA**, pytając adapter metryk KEDA przez `external.metrics.k8s.io`. W klastrze może być tylko jeden serwer metryk zewnętrznych.
- **Scalery:** SQS, Kafka, RabbitMQ, Prometheus, Redis, cron, CPU i dziesiątki innych.
- **ScaledJob:** zamiast skalować Deployment, tworzy Joby. Dobre dla długich zadań, których nie wolno przerwać.
- **TriggerAuthentication** (albo ClusterTriggerAuthentication): dane logowania do źródła. Na AWS rola IAM przez IRSA albo EKS Pod Identity, bez kluczy w YAML-u.

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: worker
spec:
  scaleTargetRef: {name: worker}
  minReplicaCount: 0
  maxReplicaCount: 20
  triggers:
  - type: aws-sqs-queue
    authenticationRef: {name: sqs-auth}
    metadata:
      queueURL: https://sqs.eu-central-1.amazonaws.com/123456789012/zamowienia
      awsRegion: eu-central-1
      queueLength: "5"             # cel: 5 wiadomości na pod
      activationQueueLength: "0"   # więcej niż 0: budzi 0 → 1
---
apiVersion: keda.sh/v1alpha1
kind: TriggerAuthentication
metadata:
  name: sqs-auth
spec:
  podIdentity:
    provider: aws                  # rola IAM: IRSA albo EKS Pod Identity
```

120 wiadomości przy `queueLength: 5` → 24 pody (przycięte do `maxReplicaCount`). Zero podów to zimny start: pierwsza wiadomość po ciszy czeka na polling i start poda.

## VPA: Vertical Pod Autoscaler

VPA to Vertical Pod Autoscaler. Nie dokłada replik, tylko zmienia `requests`, czyli „rozmiar” poda, na podstawie historii zużycia.

Porównanie w jednym zdaniu:
- HPA dokłada podów (scale out).
- VPA robi pody większe (scale up).
- In-place resize to mechanizm, dzięki któremu VPA może zmienić rozmiar bez restartu poda.
- KEDA skaluje według zdarzeń, np. długości kolejki, i potrafi zejść do zera. Pod spodem i tak steruje HPA.

### Czy VPA jest zawsze w Kubernetesie? Czy trzeba go doinstalować?

**Nie jest wbudowany, trzeba go doinstalować.** VPA to osobny projekt: katalog `vertical-pod-autoscaler` w repozytorium `kubernetes/autoscaler`. Instalujesz definicje CRD i trzy komponenty:

| Komponent | Co robi |
|---|---|
| **recommender** | czyta zużycie (z metrics-servera), buduje historię i zapisuje rekomendację w `status` obiektu VPA |
| **updater** | szuka podów, których `requests` odbiegają od rekomendacji, i je eksmituje (albo zmienia rozmiar in-place) |
| **admission-controller** | webhook: wpisuje rekomendowane `requests` każdemu nowemu podowi |

Wymaga metrics-servera. EKS nie instaluje VPA domyślnie, na k8s-sages go nie ma. Wbudowane w Kubernetesa są tylko **HPA** i mechanizm **in-place resize** (GA w 1.35), który sam nie decyduje, jaki rozmiar ustawić.

```bash
kubectl get crd verticalpodautoscalers.autoscaling.k8s.io   # u nas: NotFound

# instalacja (administrator klastra), jedna z dróg:
git clone https://github.com/kubernetes/autoscaler.git
cd autoscaler/vertical-pod-autoscaler && ./hack/vpa-up.sh
# albo chart Helm, np. fairwinds-stable/vpa
```

### Tryby `updatePolicy.updateMode`

| Tryb | Co robi |
|---|---|
| `Off` | tylko rekomendacje w `status`, nic nie zmienia. **Dobry start:** czytasz i sam wpisujesz `requests` do YAML-a |
| `Initial` | ustawia `requests` tylko nowym podom, działających nie rusza |
| `Recreate` | jak Initial + updater eksmituje pody z `requests` daleko od rekomendacji (restart) |
| `InPlaceOrRecreate` | najpierw próbuje in-place resize, gdy się nie da, eksmituje. Tryb z nowszych wersji VPA; sprawdź w release notes swojej wersji, czy jest już domyślnie włączony |
| `Auto` | dawny domyślny tryb, dziś działa jak Recreate i jest oznaczony jako przestarzały. Wpisuj tryb jawnie |

### Minimalny VPA i odczyt rekomendacji

```yaml
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: web
spec:
  targetRef: {apiVersion: apps/v1, kind: Deployment, name: web}
  updatePolicy:
    updateMode: "Off"
```

```
$ kubectl describe vpa web
...
      Container Name:  web
      Lower Bound:     Cpu: 25m    Memory: 262144k
      Target:          Cpu: 120m   Memory: 300Mi
      Upper Bound:     Cpu: 480m   Memory: 700Mi
```

- **Target**: tyle VPA wpisałby jako `requests`. To przepisujesz do YAML-a.
- **Lower Bound**: poniżej tego pod jest prawdopodobnie za mały.
- **Upper Bound**: powyżej tego marnujesz zasoby. Updater zmienia pody, których `requests` wypadają poza przedział Lower–Upper.
- **Uncapped Target**: rekomendacja bez granic `minAllowed`/`maxAllowed`.

Na świeżym VPA przedział jest szeroki. Czytaj rekomendacje po co najmniej dniu typowego ruchu. Recommender ma domyślne minima (25m CPU, 250Mi pamięci).

### Dlaczego nie łączyć VPA i HPA na CPU

Oba reagują na ten sam sygnał. VPA podnosi `requests`, więc procent zużycia CPU spada. Wtedy HPA zdejmuje repliki, obciążenie rośnie i wszystko się zapętla.

**Dozwolone:** HPA (albo KEDA) na metryce własnej lub zewnętrznej (żądania/s, długość kolejki) + VPA na CPU i pamięci.

Pułapki VPA:
- Recreate = restart przy każdej zmianie. Updater szanuje PodDisruptionBudget i domyślnie nie rusza Deploymentów z 1 repliką.
- VPA zmienia `requests` w podach, nie w Deploymencie. YAML w repo zostaje ze starymi wartościami.
- Limity rosną proporcjonalnie do requests (zmienisz to przez `controlledValues: RequestsOnly`).
- Rekomendacja większa niż quota albo `max` w LimitRange = pod, który nie powstanie.

## In-place resize

Od Kubernetesa 1.35 (GA) można zmienić CPU i pamięć działającego poda przez podzasób `resize`, zwykle bez restartu.

```yaml
resizePolicy:
- resourceName: cpu
  restartPolicy: NotRequired        # domyślnie: zmiana na żywo
- resourceName: memory
  restartPolicy: RestartContainer   # restart kontenera z nowymi wartościami
```

```bash
kubectl patch pod web --subresource resize --patch \
  '{"spec":{"containers":[{"name":"web","resources":{"requests":{"cpu":"300m"},"limits":{"cpu":"400m"}}}]}}'
kubectl get pod web -o jsonpath='{.status.containerStatuses[0].resources}'   # co zastosowano naprawdę
```

- Warunki poda: `PodResizePending` (`Deferred`: brak miejsca teraz, `Infeasible`: nie da się na tym węźle), `PodResizeInProgress`.
- Tylko CPU i pamięć. Klasa QoS nie może się zmienić. Zmniejszanie pamięci jest ryzykowne.
- Potrzebne uprawnienie do podzasobu `pods/resize`.
- Ręczny resize jest tymczasowy: następny rollout utworzy pody z szablonu. Zmiana `resources` w Deploymencie to zwykły rollout, nie resize.

## Węzły: Cluster Autoscaler, Karpenter, EKS Auto Mode

Gdy HPA dołożył repliki, a pody wiszą w `Pending` z `FailedScheduling … Insufficient cpu`, brakuje węzłów. To nie jest zadanie HPA ani VPA.

| Narzędzie | Jak działa |
|---|---|
| Cluster Autoscaler | zwiększa grupę węzłów (ASG / managed node group), gdy pody nie mieszczą się; usuwa prawie puste węzły |
| Karpenter | sam tworzy instancje EC2 dopasowane do czekających podów, konsoliduje i wyłącza zbędne węzły |
| EKS Auto Mode | AWS zarządza węzłami za Ciebie; skalowanie węzłów oparte na Karpenterze, po stronie AWS |

Autoskalery węzłów liczą po `requests`, nie po faktycznym zużyciu. Na k8s-sages: stałe 3 węzły, bez autoskalera.

## Porównanie

| | Co skaluje | Sygnał | Wbudowany? | Do zera | Typowe użycie | Pułapki |
|---|---|---|---|---|---|---|
| **HPA** | liczbę podów | CPU/pamięć (% requestu), metryki własne i zewnętrzne | tak (+ metrics-server) | nie | bezstanowe API, frontendy | brak `requests`, `replicas` w YAML, quota |
| **VPA** | `requests` podów | historia zużycia | nie: CRD + 3 komponenty | nie dotyczy | dobór `requests` (Off), aplikacje bez skalowania w poziomie | restart (Recreate), konflikt z HPA na CPU |
| **KEDA** | liczbę podów (przez HPA) / Jobów | zdarzenia: kolejki, Prometheus, cron… | nie: Helm, CNCF graduated | tak | workery kolejek, batch, godziny pracy | zimny start, nie łącz z własnym HPA |
| **In-place resize** | `requests`/`limits` działającego poda | brak: człowiek albo VPA | tak, GA w 1.35 | nie dotyczy | więcej CPU bez restartu | QoS bez zmian, rollout przywraca szablon |
| **CA / Karpenter / Auto Mode** | liczbę węzłów | pody `Pending`, puste węzły | nie: dodatek / funkcja AWS | węzły tak | każdy produkcyjny klaster z HPA/KEDA | liczy po `requests`, nowy węzeł to minuty |

## Kiedy co

| Sytuacja | Wybierz |
|---|---|
| API/frontend, CPU rośnie z ruchem | HPA na CPU z `requests`, cel 50–70%, `minReplicas: 2` |
| Nie wiesz, jakie `requests` ustawić | VPA w trybie Off, po dniu–dwóch przepisz Target do YAML-a |
| Worker kolejki, nocami pusto | KEDA + trigger kolejki, `minReplicaCount: 0`; długie zadania: ScaledJob |
| Ruch przewidywalny w ciągu dnia | KEDA z triggerem cron + CPU |
| Jedna instancja, bez skalowania w poziomie | VPA albo ręczny in-place resize |
| HPA i VPA naraz | HPA/KEDA na metryce własnej/zewnętrznej, VPA na CPU i pamięci |
| Pody `Pending`: `Insufficient cpu` | autoskaler węzłów albo mniejsze `requests` (u nas: więcej się nie zmieści) |
| HPA pokazuje `<unknown>` | brak `requests` albo nie działa metrics-server (`kubectl top pods`) |

## Komendy

```bash
kubectl top pods                                          # czy działa metrics-server
kubectl autoscale deploy web --cpu-percent=50 --min=1 --max=10
kubectl get hpa -w                                        # TARGETS, REPLICAS na żywo
kubectl describe hpa web                                  # AbleToScale, ScalingActive, ScalingLimited, zdarzenia
kubectl get events --field-selector reason=FailedScheduling
kubectl api-resources | grep -iE 'verticalpod|scaledobject'   # czy są VPA / KEDA
kubectl describe vpa web                                  # rekomendacje
kubectl get scaledobject,scaledjob
```
