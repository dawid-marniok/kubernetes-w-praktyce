# Przykłady: Helm (example-chart)

**Cel:** poznać strukturę chartu (`Chart.yaml`, `values.yaml`, `templates/`), wyrenderować go lokalnie i przejść cykl install → upgrade → rollback → uninstall.

**Gdzie:** `helm lint` i `helm template` lokalnie (bez klastra), instalacja na klastrze szkoleniowym EKS w Twoim namespace. Komendy wydajesz w tym katalogu (`cd przyklady/k8s/22-helm/example-chart`).

| Plik | Co pokazuje |
|---|---|
| `Chart.yaml` | `version` (wersja chartu) vs `appVersion` (domyślny tag obrazu), zależności w komentarzu |
| `values.yaml` | wartości domyślne: obraz, zasoby, Service, warunkowy ServiceMonitor i HPA |
| `templates/_helpers.tpl` | nazwy i etykiety wspólne dla wszystkich szablonów |
| `templates/deployment.yaml`, `service.yaml`, `serviceaccount.yaml` | szablony obiektów |
| `templates/hpa.yaml`, `servicemonitor.yaml` | obiekty tworzone tylko przy `autoscaling.enabled` / `serviceMonitor.enabled` |

## Krok po kroku

**1. Sprawdzenie i podgląd bez klastra**
```bash
helm lint .
helm template demo . | less
helm template demo . --set serviceMonitor.enabled=true --set autoscaling.enabled=true | grep -A3 "^kind:"
```
Co powinieneś zobaczyć: `1 chart(s) linted, 0 chart(s) failed`. `helm template` wypisuje gotowe YAML-e: ServiceAccount, Service i Deployment `demo-example-app` z obrazem `nginx:1.29`. Z flagami `--set` dochodzą `HorizontalPodAutoscaler` i `ServiceMonitor`, a z Deploymentu znika pole `replicas`.

**2. Instalacja**
```bash
helm upgrade --install demo . --wait
helm list
kubectl get deploy,svc,pods -l app.kubernetes.io/instance=demo
```
Co powinieneś zobaczyć: `STATUS: deployed`, `REVISION: 1`. W `helm list` release `demo`, chart `example-app-0.2.0`, `APP VERSION 1.29`. Deployment `demo-example-app` `1/1` i Service o tej samej nazwie.

**3. Upgrade z inną wartością**
```bash
helm upgrade demo . --set replicaCount=3 --wait
helm history demo
kubectl get deploy demo-example-app
```
Co powinieneś zobaczyć: `REVISION: 2`, w historii dwie rewizje, Deployment `3/3`.

**4. Rollback**
```bash
helm rollback demo 1 --wait
helm history demo
kubectl get deploy demo-example-app
```
Co powinieneś zobaczyć: nowa rewizja 3 z opisem `Rollback to 1`, Deployment znów `1/1`.

## Sprzątanie
```bash
helm uninstall demo
```

## Uwagi
- `helm upgrade --install` działa i przy pierwszej instalacji, i przy kolejnych: jedno polecenie do CI/CD.
- `--set` nadpisuje pojedyncze wartości, `-f moje-values.yaml` cały plik. Kolejność: `values.yaml` z chartu, potem `-f`, na końcu `--set`.
- ServiceMonitor wymaga CRD Prometheus Operatora (kube-prometheus-stack). Bez nich `--set serviceMonitor.enabled=true` przy instalacji kończy się `no matches for kind "ServiceMonitor"`.
- Ściąga składni szablonów: [`docs/k8s/helm/skladnia.md`](../../../../docs/k8s/helm/skladnia.md).
