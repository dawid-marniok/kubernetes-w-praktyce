# Przykłady: PodDisruptionBudget i serwis węzła

**Cel:** zobaczyć, jak PDB pilnuje dostępności aplikacji przy `kubectl drain` i dlaczego za ostry PDB blokuje prace na węźle.

**Gdzie:** kind. `cordon` i `drain` działają na węzłach, a te na wspólnym klastrze EKS obsługuje tylko administrator (kursant dostanie `Forbidden`). PDB w swoim namespace na EKS utworzysz, ale drainu nie zrobisz. Klaster kind `szkolenie` (1 control plane + 2 workery): [`setup/kind.md`](../../../setup/kind.md). Komendy wydajesz w tym katalogu (`cd przyklady/k8s/16-pdb`).

| Plik | Co pokazuje |
|---|---|
| `deployment.yaml` | 3 repliki rozłożone po węzłach (`topologySpreadConstraints`) |
| `pdb.yaml` | `maxUnavailable: 1` dla tych podów |

Pełniejsze ćwiczenie (taint, toleracja, PDB i drain w jednym scenariuszu, z własnym klastrem kind): [`../15-affinity-taints/kind-taint-pdb-drain/`](../15-affinity-taints/kind-taint-pdb-drain/).

## Co PDB robi, a czego nie

PDB to umowa: „przy planowanych pracach zostaw mi co najmniej tyle działających podów”. Pilnuje jej **Eviction API**, czyli eksmisja podów z węzła.

| Zdarzenie | PDB działa? |
|---|---|
| `kubectl drain`, upgrade i wymiana węzłów (np. managed node group na EKS), autoskaler zdejmujący węzeł | tak: eksmisja czeka, aż PDB pozwoli |
| awaria węzła, OOMKilled, crash procesu | nie: to zakłócenia niedobrowolne, nikt nie pyta o zgodę |
| `kubectl delete pod`, `kubectl delete deployment` | nie: zwykłe usuwanie omija Eviction API |
| rolling update Deploymentu (`set image`, `rollout restart`) | nie: tempo wyznaczają `maxSurge`/`maxUnavailable` Deploymentu |

`ALLOWED DISRUPTIONS` w `kubectl get pdb` = ile podów można teraz wyrzucić:
- przy `minAvailable`: zdrowe pody − `minAvailable` (3 zdrowe, `minAvailable: 2` → 1),
- przy `maxUnavailable`: `maxUnavailable` − pody, których już brakuje (3 z 3 zdrowe, `maxUnavailable: 1` → 1).

`minAvailable` równe liczbie replik daje `ALLOWED DISRUPTIONS 0` na stałe: drain czeka w nieskończoność, a upgrade węzłów staje. Dlatego lepiej `maxUnavailable: 1`.

## Krok po kroku

**1. Klaster i namespace**
```bash
kubectl config use-context kind-szkolenie
kubectl get nodes                                 # szkolenie-control-plane, szkolenie-worker, szkolenie-worker2: Ready
kubectl create namespace przyklady
kubectl config set-context --current --namespace=przyklady
```
W drugim terminalu: `kubectl get pods -o wide -w` (kolumna `NODE`).

**2. Drain z rozsądnym PDB**
```bash
kubectl apply -f deployment.yaml -f pdb.yaml
kubectl get pdb
kubectl drain szkolenie-worker --ignore-daemonsets --delete-emptydir-data
kubectl get nodes
```
Co powinieneś zobaczyć: `MAX UNAVAILABLE 1`, `ALLOWED DISRUPTIONS 1`. Drain pisze `evicting pod …` dla podów z `szkolenie-worker`, czasem raz `would violate the pod's disruption budget` i ponowienie, na koniec `node/szkolenie-worker drained`. W drugim terminalu pody znikają z `szkolenie-worker` po jednym, a zastępcy powstają na `szkolenie-worker2`. `kubectl get nodes`: `szkolenie-worker` ma `Ready,SchedulingDisabled`.

**3. Uncordon: pody nie wracają same**
```bash
kubectl uncordon szkolenie-worker
kubectl get pods -o wide
```
Co powinieneś zobaczyć: węzeł znów `Ready`, ale wszystkie pody dalej na `szkolenie-worker2`. Nikt nie przenosi działających podów. Rozkład wróci po `kubectl rollout restart deployment przyklad-web`.

**4. Za ostry PDB blokuje drain**
```bash
kubectl rollout restart deployment przyklad-web   # rozłóż pody z powrotem na oba workery
kubectl rollout status deployment przyklad-web
kubectl delete -f pdb.yaml
kubectl create pdb przyklad-web-pdb --selector=app=przyklad-web --min-available=3
kubectl get pdb
kubectl drain szkolenie-worker --ignore-daemonsets --timeout=30s
```
Co powinieneś zobaczyć: `MIN AVAILABLE 3`, `ALLOWED DISRUPTIONS 0`. Drain: `node/szkolenie-worker cordoned`, potem w kółko `Cannot evict pod as it would violate the pod's disruption budget`, a po 30 s `error: … global timeout reached`. Drain nie łamie umowy, tylko czeka. Upgrade węzłów w chmurze zatrzymałby się w tym samym miejscu.

**5. PDB nie blokuje zwykłego usuwania**
```bash
kubectl delete pod -l app=przyklad-web --wait=false   # przy ALLOWED DISRUPTIONS 0
kubectl get pods -o wide
```
Co powinieneś zobaczyć: pody od razu `Terminating`, Deployment tworzy nowe. PDB nie zaprotestował, bo `kubectl delete pod` nie idzie przez Eviction API. Nowe pody nie trafią na `szkolenie-worker` (dalej `SchedulingDisabled` po przerwanym drainie).

**6. Bez `--ignore-daemonsets`**
```bash
kubectl drain szkolenie-worker --timeout=10s
```
Co powinieneś zobaczyć: `cannot delete DaemonSet-managed Pods` (`kube-proxy`, `kindnet`). Pod DaemonSetu i tak wróciłby na ten węzeł, więc drain każe Ci go świadomie pominąć.

## Sprzątanie
```bash
kubectl uncordon szkolenie-worker                 # na wypadek przerwanego draina
kubectl delete namespace przyklady
kubectl config use-context szkolenie              # z powrotem na wspólny klaster
```

## Uwagi
- Na co dzień: `kubectl get pdb -A`. `ALLOWED DISRUPTIONS` równe 0 przez dłuższy czas to przyszły zablokowany upgrade.
- Na EKS upgrade managed node group sam robi cordon i drain z poszanowaniem PDB. Jeśli PDB nie pozwala, po ok. 15 min upgrade kończy się błędem `PodEvictionFailure`.
- PDB dla aplikacji z 1 repliką nie ma sensu: `maxUnavailable: 1` niczego nie chroni, a `minAvailable: 1` blokuje drain.
- Pody, które nie są gotowe (np. `CrashLoopBackOff`), też potrafią zablokować drain. Pomaga `unhealthyPodEvictionPolicy: AlwaysAllow` w PDB.
