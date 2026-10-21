# Przykłady: DaemonSet

**Cel:** uruchomić po jednym podzie na każdym węźle (agent logów, metryk, sieci) i zobaczyć, jak DaemonSet aktualizuje się węzeł po węźle.

**Gdzie:** `daemonset-node-agent.yaml` na klastrze szkoleniowym EKS (Twój namespace), `daemonset-log-agent-kind.yaml` tylko na kind. Komendy wydajesz w tym katalogu (`cd przyklady/k8s/10-daemonset`).

| Plik | Co pokazuje |
|---|---|
| `daemonset-node-agent.yaml` | pod na każdym węźle, nazwa węzła z Downward API, rolling update po jednym węźle |
| `daemonset-log-agent-kind.yaml` | `hostPath` `/var/log/pods` tylko do odczytu, toleracja taintu control-plane — tylko kind |

## Krok po kroku

**1. Agent na każdym węźle**
```bash
kubectl apply -f daemonset-node-agent.yaml
kubectl get ds przyklad-node-agent
kubectl get pods -l app=przyklad-node-agent -o wide
kubectl logs -l app=przyklad-node-agent --prefix
```
Co powinieneś zobaczyć: `DESIRED 3`, `CURRENT 3`, `READY 3` (klaster ma 3 węzły). W `-o wide` każdy pod na innym węźle (`ip-10-…`). W logach `agent na węźle ip-10-…`, z różną nazwą węzła w każdym podzie. DaemonSet nie ma pola `replicas`: liczba podów = liczba pasujących węzłów.

**2. Aktualizacja węzeł po węźle**

W drugim terminalu: `kubectl get pods -l app=przyklad-node-agent -o wide -w`.
```bash
kubectl set env ds/przyklad-node-agent WERSJA=2
kubectl rollout status ds/przyklad-node-agent
```
Co powinieneś zobaczyć: na jednym węźle stary pod `Terminating`, nowy `Running`, potem następny węzeł (`maxUnavailable: 1`). `rollout status` kończy się `successfully rolled out`.

**3. Agent logów (kind)**
```bash
kubectl config use-context kind-szkolenie
kubectl apply -f daemonset-log-agent-kind.yaml
kubectl get pods -l app=przyklad-log-agent -o wide
kubectl logs -l app=przyklad-log-agent --prefix
```
Co powinieneś zobaczyć: 3 pody, także na `szkolenie-control-plane` (dzięki toleracji taintu control-plane). W logach `<węzeł>: <liczba> katalogów z logami podów`.

## Sprzątanie
```bash
kubectl delete -f daemonset-log-agent-kind.yaml       # na kind
kubectl config use-context szkolenie
kubectl delete -f daemonset-node-agent.yaml
```

## Uwagi
- Prawdziwi agenci logów i metryk: Fluent Bit, Grafana Alloy (Promtail ma EOL), node-exporter. Na klastrze: `kubectl get ds -n kube-system` (na EKS m.in. `aws-node` — vpc-cni, `kube-proxy`, `ebs-csi-node`).
- `hostPath` daje podowi dostęp do systemu plików węzła. Pod Security `baseline` go blokuje, dlatego agent logów działa tylko na kind.
- DaemonSet tylko na części węzłów: `nodeSelector` albo `nodeAffinity` w szablonie poda.
