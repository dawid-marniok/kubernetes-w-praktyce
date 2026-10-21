# Przykłady: requests, limits, QoS

**Cel:** zobaczyć, jak requests i limits wyznaczają klasę QoS poda i co się dzieje po przekroczeniu limitu pamięci.

**Gdzie:** klaster szkoleniowy EKS, Twój namespace. `priorityclass.yaml` tylko na kind (zasób klastrowy). Komendy wydajesz w tym katalogu (`cd przyklady/k8s/12-zasoby-qos`).

| Plik | Co pokazuje |
|---|---|
| `pod-guaranteed.yaml` | klasa `Guaranteed` (requests = limits) |
| `pod-burstable.yaml` | klasa `Burstable` |
| `pod-oomkilled.yaml` | przekroczenie limitu pamięci: `OOMKilled`, exit 137 |
| `priorityclass.yaml` | PriorityClass (tylko admin), w podzie `priorityClassName` |

## Krok po kroku

**1. Klasy QoS**
```bash
kubectl apply -f pod-guaranteed.yaml -f pod-burstable.yaml
kubectl get pod przyklad-guaranteed -o jsonpath='{.status.qosClass}'; echo
kubectl get pod przyklad-burstable -o jsonpath='{.status.qosClass}'; echo
kubectl top pods przyklad-guaranteed przyklad-burstable
```
Co powinieneś zobaczyć: `Guaranteed` i `Burstable`. `kubectl top` (po ok. minucie) pokazuje faktyczne zużycie, np. `0m` CPU i kilkaset KiB pamięci: znacznie mniej niż requests. Request to rezerwacja, nie zużycie.

**2. OOMKilled**

W drugim terminalu: `kubectl get pod przyklad-oom -w`.
```bash
kubectl apply -f pod-oomkilled.yaml
kubectl describe pod przyklad-oom | grep -A5 "Last State"
```
Co powinieneś zobaczyć: `Running` → `OOMKilled` → `CrashLoopBackOff`, `RESTARTS` rośnie. `Last State: Terminated`, `Reason: OOMKilled`, `Exit Code: 137` (128 + 9, SIGKILL od jądra).

**3. PriorityClass (kind)**
```bash
kubectl config use-context kind-szkolenie
kubectl get priorityclass
kubectl apply -f priorityclass.yaml
kubectl get priorityclass przyklad-prod-high
kubectl config use-context szkolenie
```
Co powinieneś zobaczyć: klasy systemowe `system-cluster-critical` i `system-node-critical` (wartości ok. 2 mld) i Twoją `przyklad-prod-high` z `VALUE 100000`. Pod korzysta z niej przez `spec.priorityClassName: przyklad-prod-high`.

## Sprzątanie
```bash
kubectl delete -f pod-guaranteed.yaml -f pod-burstable.yaml -f pod-oomkilled.yaml
kubectl --context kind-szkolenie delete -f priorityclass.yaml --ignore-not-found
```

## Uwagi
- CPU ponad limit = dławienie (aplikacja zwalnia), pamięć ponad limit = OOMKilled.
- Przy braku pamięci na węźle kubelet wyrzuca pody w kolejności: `BestEffort`, potem `Burstable` przekraczające request, na końcu `Guaranteed`.
- `BestEffort` (bez resources) w namespace z quotą na CPU/pamięć się nie da: LimitRange wstawi wartości albo API odrzuci pod.
