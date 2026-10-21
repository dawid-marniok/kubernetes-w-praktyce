# Przykłady: affinity, anti-affinity, spread, taints i tolerations

**Cel:** sterować tym, na których węzłach lądują pody: przyciągać (nodeAffinity), rozkładać (anti-affinity, spread), odpychać (taint) i wpuszczać mimo taintu (toleracja).

**Gdzie:** kind. Etykiety i tainty węzłów zmienia tylko administrator klastra, więc na wspólnym klastrze EKS dostaniesz `Forbidden`. Klaster kind `szkolenie` (1 control plane + 2 workery): [`setup/kind.md`](../../../setup/kind.md). Komendy wydajesz w tym katalogu (`cd przyklady/k8s/15-affinity-taints`). Czas: ok. 25 min.

| Plik | Co pokazuje |
|---|---|
| `node-affinity-required.yaml` | tylko węzły z `disktype=ssd` (brak takiego węzła → Pending) |
| `node-affinity-preferred.yaml` | woli `environment=production`, ale uruchomi się wszędzie |
| `pod-anti-affinity.yaml` | 5 replik, każda na innym węźle (za mało węzłów → część Pending) |
| `topology-spread.yaml` | równy rozkład po węzłach, `ScheduleAnyway` |
| `pod-affinity.yaml` | backend na tym samym węźle co frontend |
| `taint-toleracja-affinity-gpu.yaml` | węzeł tylko dla GPU: toleracja (pozwala) + nodeAffinity (przyciąga) |
| `toleracja-notready.yaml` | `NoExecute` z `tolerationSeconds` dla węzłów not-ready/unreachable |
| [`kind-taint-pdb-drain/`](kind-taint-pdb-drain/) | osobne ćwiczenie krok po kroku: taint, toleracja, PDB i drain na własnym klastrze kind |

## Krok po kroku

**0. Klaster i namespace**
```bash
kubectl config use-context kind-szkolenie
kubectl create namespace przyklady
kubectl config set-context --current --namespace=przyklady
kubectl describe nodes | grep Taints
```
Co powinieneś zobaczyć: `szkolenie-control-plane` ma `node-role.kubernetes.io/control-plane:NoSchedule`, oba workery `<none>`.

W drugim terminalu: `kubectl get pods -o wide -w` (kolumna `NODE` to cała odpowiedź).

**1. nodeAffinity: musi i woli**
```bash
kubectl apply -f node-affinity-required.yaml
kubectl get events --field-selector reason=FailedScheduling | tail -1
kubectl label nodes szkolenie-worker disktype=ssd
kubectl apply -f node-affinity-preferred.yaml
```
Co powinieneś zobaczyć: najpierw 3 × `Pending`, w zdarzeniu `didn't match Pod's node affinity/selector`. Po dodaniu etykiety pody od razu startują, wszystkie na `szkolenie-worker`. `przyklad-nginx-preferred` działa, choć żaden węzeł nie ma `environment=production`: `required` to warunek, `preferred` to tylko punkty w ocenie.

**2. Repliki osobno: anti-affinity i spread**
```bash
kubectl apply -f pod-anti-affinity.yaml
kubectl apply -f topology-spread.yaml
```
Co powinieneś zobaczyć: `przyklad-nginx-distributed` ma 2 `Running` i 3 `Pending`, `przyklad-nginx-spread` 4 repliki po 2 na worker. Dlaczego tylko 2 Running, skoro węzły są trzy? Control plane ma taint, a tego Deploymentu nic nie toleruje.

**3. Taint, toleracja i affinity: węzeł tylko dla GPU**
```bash
kubectl taint nodes szkolenie-worker2 node-type=gpu:NoSchedule
kubectl label nodes szkolenie-worker2 node-type=gpu
kubectl apply -f taint-toleracja-affinity-gpu.yaml
```
Co powinieneś zobaczyć: oba pody `przyklad-gpu-app` na `szkolenie-worker2`. Usuń z kopii pliku blok `affinity` i wgraj ją: pody trafiają też na `szkolenie-worker`. Toleracja pozwala, nie przyciąga.

**4. NoExecute wyrzuca działające pody**
```bash
kubectl taint nodes szkolenie-worker maintenance=true:NoExecute
kubectl get pods -o wide
kubectl taint nodes szkolenie-worker maintenance=true:NoExecute-
```
Co powinieneś zobaczyć: pody z `szkolenie-worker` znikają i powstają gdzie indziej, o ile mogą. Część wraca do `Pending`, np. `przyklad-nginx-ssd`: jedyny węzeł `ssd` właśnie je wyrzucił. `NoSchedule` nie rusza działających podów, `NoExecute` tak.

**5. Dla chętnych**
```bash
kubectl apply -f pod-affinity.yaml
kubectl get pods przyklad-frontend przyklad-backend -o wide
kubectl apply -f toleracja-notready.yaml
kubectl get pod przyklad-szybka-ewakuacja -o yaml | grep -A12 tolerations
```
Co powinieneś zobaczyć: backend na tym samym węźle co frontend. W toleracjach `przyklad-szybka-ewakuacja` Twoje 60 s dla `not-ready` i `unreachable` (inne pody dostają od Kubernetesa domyślne 300 s).

**6. Drain i PodDisruptionBudget:** ćwiczenie [`kind-taint-pdb-drain/`](kind-taint-pdb-drain/) i przykłady [`../16-pdb/`](../16-pdb/).

## Sprzątanie
```bash
kubectl delete namespace przyklady
kubectl label nodes szkolenie-worker disktype-
kubectl label nodes szkolenie-worker2 node-type-
kubectl taint nodes szkolenie-worker2 node-type=gpu:NoSchedule-
kubectl describe nodes | grep Taints                  # został tylko taint control-plane
kubectl config use-context szkolenie                  # z powrotem na wspólny klaster
```

## Uwagi
- `IgnoredDuringExecution` w nazwie pola: zmiana etykiet węzła nie wyrzuca działających podów. Wyrzuca je tylko taint `NoExecute`.
- Anti-affinity `required` przy większej liczbie replik niż węzłów zostawia pody w `Pending`. Do równego rozkładu zwykle lepszy jest `topologySpreadConstraints`.
- Na EKS węzły mają etykiety `topology.kubernetes.io/zone` (strefa AZ) i `node.kubernetes.io/instance-type`. Rozkład replik po strefach: `topologyKey: topology.kubernetes.io/zone`.
