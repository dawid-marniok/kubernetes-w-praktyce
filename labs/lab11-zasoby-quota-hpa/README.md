# lab11 — Zasoby, QoS, quota i HPA

**Gdzie:** klaster szkoleniowy, Twój namespace (punkty dla chętnych: kind)

**Po labie masz:** pody w dwóch klasach QoS, pod zabity przez OOMKilled, dowód, że quota blokuje nowe pody w ReplicaSecie, i HPA, który pod obciążeniem dokłada repliki.

## Zanim zaczniesz

```bash
kubectl describe resourcequota          # Twoja quota: Used / Hard
kubectl describe limitrange             # wartości domyślne dla kontenerów bez resources
kubectl top pods                        # działa? (metrics-server)
```

Zapisz sobie z `describe resourcequota`, ile zostało `requests.cpu` i `pods`. Quotę i LimitRange w Twoim namespace założył prowadzący; Ty możesz je czytać, nie zmieniać.

Pliki startowe: `qos-guaranteed.yaml`, `pod-bez-resources.yaml`, `nginx-quota.yaml`, katalog `hpa-test/` (`deployment.yaml`, `service.yaml`, `load.yaml`).

## Poziom podstawowy

### 1. Klasy QoS

```bash
kubectl apply -f qos-guaranteed.yaml
kubectl get pod qos-guaranteed -o jsonpath='{.status.qosClass}'; echo
```

Skopiuj plik jako `qos-burstable.yaml`, zmień nazwę poda na `qos-burstable` i zmień resources tak, żeby pod był `Burstable`. Sprawdź klasę.

✅ `Guaranteed` i `Burstable`. Kto z nich zostanie wyrzucony pierwszy, gdy na węźle zabraknie pamięci?

### 2. Pod bez resources

```bash
kubectl apply -f pod-bez-resources.yaml
kubectl get pod bez-resources -o jsonpath='{.spec.containers[0].resources}'; echo
kubectl get pod bez-resources -o jsonpath='{.status.qosClass}'; echo
```

Skąd pod ma resources, skoro w pliku ich nie ma? Porównaj z `kubectl describe limitrange`. Czy w tym namespace da się w ogóle uruchomić pod `BestEffort`?

### 3. OOMKilled

Napisz `pod-mem.yaml`: pod `mem`, `busybox:1.37`, komenda `["sh", "-c", "tail /dev/zero"]`, requests i limits pamięci `64Mi` (CPU: 10m / 100m).

```bash
kubectl apply -f pod-mem.yaml
kubectl get pod mem -w                         # Ctrl+C po kilku restartach
kubectl describe pod mem | grep -A5 "Last State"
kubectl delete pod mem
```

✅ `Reason: OOMKilled`, `Exit Code: 137`. Czym to się różni od przekroczenia limitu CPU?

### 4. Quota blokuje nowe pody

```bash
kubectl apply -f nginx-quota.yaml          # 2 repliki × 500m CPU requestu
kubectl describe resourcequota | grep requests.cpu
kubectl scale deployment nginx-quota --replicas=6
kubectl get deployment nginx-quota
kubectl get pods -l app=nginx-quota
```

Ile podów powstało? Czy któryś jest `Pending`? Znajdź przyczynę:

```bash
kubectl describe replicaset -l app=nginx-quota | grep FailedCreate
```

✅ Event `FailedCreate … exceeded quota … requested: requests.cpu=500m, used: …, limited: …`. Brakujących podów nie ma wcale — nie są `Pending`.

Posprzątaj, zanim przejdziesz dalej (quota jest wspólna dla wszystkiego w namespace):

```bash
kubectl delete deployment nginx-quota
kubectl delete pod qos-guaranteed qos-burstable bez-resources
```

### 5. HPA

```bash
kubectl apply -f hpa-test/deployment.yaml -f hpa-test/service.yaml
```

Utwórz HPA dla Deploymentu `hpa-test`: 1–5 replik, cel 50% CPU. Możesz napisać YAML (`autoscaling/v2`) albo:

```bash
kubectl autoscale deployment hpa-test --cpu-percent=50 --min=1 --max=5
kubectl get hpa hpa-test -o yaml           # gotowy plik do repo
```

W drugim terminalu `kubectl get hpa -w`. Po minucie (`TARGETS` z liczbą zamiast `<unknown>`) włącz obciążenie:

```bash
kubectl apply -f hpa-test/load.yaml
kubectl top pods -l app=hpa-test
```

Po 2–3 minutach usuń obciążenie i obserwuj dalej:

```bash
kubectl delete -f hpa-test/load.yaml
kubectl describe hpa hpa-test | grep -A3 Conditions
```

✅ `REPLICAS` rośnie powyżej 1, a po zdjęciu ruchu długo nie spada (`ScaleDownStabilized`).

### 6. Sprzątanie

```bash
kubectl delete hpa hpa-test
kubectl delete -f hpa-test/
```

## SUKCES

- [ ] masz pod `Guaranteed` i `Burstable` i wiesz, skąd `bez-resources` dostał wartości
- [ ] widziałeś `OOMKilled` z kodem 137
- [ ] znalazłeś `FailedCreate … exceeded quota` w ReplicaSecie
- [ ] HPA podniósł repliki powyżej 1 pod obciążeniem i nie zszedł od razu po jego zdjęciu
- [ ] po labie w namespace nie ma podów z tego labu ani HPA

## Dla chętnych (kind)

Na kind nie ma quoty ani LimitRange, możesz je założyć sam (namespace np. `lab11`):

- **LimitRange z min/max:** `defaultRequest` 100m/128Mi, `default` 500m/512Mi, `min` 50m/64Mi, `max` 2/2Gi dla `type: Container`. Utwórz pod z requestem CPU `10m`. Kiedy przychodzi błąd: przy `apply` czy przy starcie poda? A pod z limitem CPU `5`?
- **Własna quota** z `requests.cpu: "1"`, `pods: "10"` i `count/jobs.batch: "5"`. Ile Jobów z labu 10 zmieścisz?
- `kubectl run` nie ma już flag `--requests` ani `--limits`. Jak uruchomić pod z resources jedną komendą? (podpowiedź: `--overrides`)
- **HPA na pamięci:** dopisz do HPA drugą metrykę: memory 50%. Czy po zdjęciu ruchu repliki zejdą? Dlaczego?

## Gdy coś nie działa

**Gotowe wzorce manifestów:** [`przyklady/k8s/12-zasoby-qos/`](../../przyklady/k8s/12-zasoby-qos/), [`przyklady/k8s/13-quota-limitrange/`](../../przyklady/k8s/13-quota-limitrange/), [`przyklady/k8s/14-hpa/`](../../przyklady/k8s/14-hpa/). Skopiuj i przerób, zamiast pisać YAML od zera.

| Objaw | Co zrobić |
|---|---|
| `TARGETS <unknown>/50%` | pierwsza minuta po starcie to normalne; dłużej: `kubectl describe hpa` (brak `requests.cpu`?) i `kubectl top pods` (działa metrics-server?) |
| `kubectl top`: `Metrics API not available` | na klastrze szkoleniowym: zgłoś prowadzącemu, nic nie instaluj. Na kind metrics-server trzeba doinstalować: `setup/kind.md`, punkt 3 (tylko w kontekście `kind-szkolenie`) |
| HPA nie rośnie | w podach jest request 20m; jeden generator może nie wystarczyć: `kubectl scale deploy load --replicas=2` |
| `failed quota: must specify …` | w namespace brak LimitRange albo w podzie część resources; dopisz requests i limits |
| `exceeded quota` już przy pierwszym podzie | coś z poprzednich labów zajmuje quotę: `kubectl describe resourcequota`, posprzątaj |
| `forbidden: User … cannot create resource "resourcequotas"` | quotę i LimitRange zmienia prowadzący; ćwiczenia z tworzeniem robisz na kind |
