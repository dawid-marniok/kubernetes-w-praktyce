# Przykłady: ResourceQuota i LimitRange

**Cel:** zrozumieć, jak quota ogranicza sumę zasobów w namespace, a LimitRange uzupełnia brakujące requests/limits.

**Gdzie:** na klastrze szkoleniowym EKS quotę i LimitRange swojego namespace'u tylko czytasz (zakłada je prowadzący). Własne tworzysz na kind. Komendy wydajesz w tym katalogu (`cd przyklady/k8s/13-quota-limitrange`).

| Plik | Co pokazuje |
|---|---|
| `resourcequota.yaml` | suma requests/limits i liczba obiektów w namespace (jak quota uczestnika) |
| `resourcequota-scope.yaml` | quota tylko dla podów z klasą priorytetu |
| `limitrange.yaml` | wartości domyślne (`defaultRequest`, `default`) i `min`/`max` dla kontenera |

## Krok po kroku

**1. Twoja quota na EKS**
```bash
kubectl describe resourcequota
kubectl describe limitrange
```
Co powinieneś zobaczyć: tabela `Resource / Used / Hard` (np. `requests.cpu 150m 2`, `pods 3 20`) i domyślne wartości kontenera z LimitRange (`Default Request`, `Default Limit`, `Max`).

**2. LimitRange uzupełnia resources**
```bash
kubectl run bez-zasobow --image=nginx:1.29
kubectl get pod bez-zasobow -o jsonpath='{.spec.containers[0].resources}'; echo
kubectl delete pod bez-zasobow
```
Co powinieneś zobaczyć: `requests` i `limits` w podzie, choć ich nie podałeś: wstawił je LimitRange przy tworzeniu poda.

**3. Własna quota na kind**
```bash
kubectl config use-context kind-szkolenie
kubectl create namespace quota-test
kubectl config set-context --current --namespace=quota-test
kubectl apply -f limitrange.yaml -f resourcequota.yaml
kubectl create deployment duzy --image=nginx:1.29 --replicas=25
kubectl get deploy duzy
kubectl describe resourcequota przyklad-quota
kubectl describe rs -l app=duzy | grep -m1 exceeded
```
Co powinieneś zobaczyć: `duzy` zatrzymuje się na `8/25`. Każdy pod dostaje z LimitRange limit `500m` CPU, a quota ma `limits.cpu: 4`, więc 9. pod już się nie mieści (w `describe resourcequota`: `limits.cpu 4 4`). Brakujące pody w ogóle nie powstają (nie ma `Pending`), w ReplicaSecie zdarzenie `FailedCreate … exceeded quota`.

**4. Quota z zakresem (kind, dla chętnych)**
```bash
kubectl apply -f ../12-zasoby-qos/priorityclass.yaml -f resourcequota-scope.yaml
kubectl describe resourcequota przyklad-quota-priorytet
```
Co powinieneś zobaczyć: quota z `Scopes`/`scopeSelector` na `PriorityClass In [przyklad-prod-high]`. Liczy tylko pody z tą klasą priorytetu.

## Sprzątanie
```bash
kubectl delete namespace quota-test
kubectl delete -f ../12-zasoby-qos/priorityclass.yaml --ignore-not-found
kubectl config use-context szkolenie
```

## Uwagi
- Kolejność w API: LimitRange uzupełnia brakujące resources, potem quota liczy sumę.
- Quota na `requests.cpu` bez LimitRange: pod bez resources → `failed quota: must specify …`.
- Przekroczenie quoty w Deploymencie: pod w ogóle nie powstaje (nie ma `Pending`), event `FailedCreate … exceeded quota` w ReplicaSecie: `kubectl describe rs`.
- `kubectl run` nie ma flag `--requests/--limits`; resources przez YAML albo `--overrides`.
