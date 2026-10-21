# Przykłady: taint, toleracja i drain z PDB na kind

**Cel:** zobaczyć, że taint odpycha, toleracja tylko pozwala (niczego nie przyciąga), a PodDisruptionBudget zatrzymuje drain, dopóki ten łamałby umowę o dostępności.

**Gdzie:** własny klaster kind z dwoma workerami. Na wspólnym klastrze EKS nie zrobisz `kubectl taint`, `cordon` ani `drain` (węzły obsługuje tylko administrator), a drain węzła z podami innych kursantów i tak byłby złym pomysłem. Komendy wydajesz w tym katalogu (`cd przyklady/k8s/15-affinity-taints/kind-taint-pdb-drain`). Czas: ok. 20 min.

| Plik | Co pokazuje |
|---|---|
| `kind-config.yaml` | klaster: 1 control-plane + 2 workery (`szkolenie-control-plane`, `szkolenie-worker`, `szkolenie-worker2`) |
| `prepare.sh` | tworzy klaster (jeśli go nie ma), pobiera `nginx:1.29` na workery, zakłada namespace `taint-drain`; `--delete` sprząta, `--usun-klaster` usuwa klaster |
| `web.yaml` | Deployment `web`: 4 × `nginx:1.29` |
| `toleracja.yaml` | łatka z toleracją `dedicated=gpu:NoSchedule` dla `web` |

Potrzebujesz Dockera (ok. 3 GB RAM wolne) i kind v0.33+ ([`setup/kind.md`](../../../../setup/kind.md), punkt 1).

## Krok po kroku

**1. Klaster kind z trzema węzłami**
```bash
./prepare.sh
```
Skrypt sprawdza, czy masz klaster `szkolenie`. Jeśli nie, tworzy go z `kind-config.yaml` (1–2 min). Potem pobiera obraz na workery, tworzy namespace `taint-drain` i ustawia kontekst `kind-szkolenie` z tym namespace. To samo ręcznie:
```bash
kind create cluster --name szkolenie --config kind-config.yaml
kubectl config use-context kind-szkolenie
kubectl create namespace taint-drain
kubectl config set-context --current --namespace=taint-drain
```
Co powinieneś zobaczyć: trzy węzły `Ready`: `szkolenie-control-plane`, `szkolenie-worker`, `szkolenie-worker2`.

W drugim terminalu: `kubectl get pods -o wide -w` (kolumna `NODE` to cała odpowiedź).

**2. Taint control-plane**
```bash
kubectl describe nodes | grep Taints
```
Co powinieneś zobaczyć: `szkolenie-control-plane` ma `node-role.kubernetes.io/control-plane:NoSchedule`, workery `<none>`. Dlatego zwykłe pody nie lądują na control-plane.

**3. Taint na worker2 odpycha pody**
```bash
kubectl taint nodes szkolenie-worker2 dedicated=gpu:NoSchedule
kubectl apply -f web.yaml
kubectl get pods -o wide
```
Co powinieneś zobaczyć: wszystkie 4 pody `web` na `szkolenie-worker`. Węzeł z taintem odpada już na etapie filtrowania w schedulerze.

**4. Toleracja pozwala, ale nie przyciąga**
```bash
cat toleracja.yaml
kubectl patch deployment web --patch-file toleracja.yaml
kubectl rollout status deployment web
kubectl get pods -o wide
```
Co powinieneś zobaczyć: po rolloucie pody rozłożone na oba workery (zwykle 2/2). Scheduler może teraz użyć `szkolenie-worker2`, ale nic ich tam nie ciągnie. Żeby szły **tylko** na worker2, potrzeba jeszcze etykiety węzła i `nodeAffinity` (plik `../taint-toleracja-affinity-gpu.yaml`).

**5. PDB, który nie pozwala na nic**
```bash
kubectl taint nodes szkolenie-worker2 dedicated=gpu:NoSchedule-     # minus na końcu zdejmuje taint
kubectl create pdb web-pdb --selector=app=web --min-available=4
kubectl get pdb
kubectl drain szkolenie-worker --ignore-daemonsets --timeout=30s
kubectl get nodes
```
Co powinieneś zobaczyć: `MIN AVAILABLE 4`, `ALLOWED DISRUPTIONS 0` (4 zdrowe − 4 wymagane). Drain: `node/szkolenie-worker cordoned`, potem w kółko `Cannot evict pod as it would violate the pod's disruption budget`, po 30 s błąd timeout. `kubectl get nodes`: `szkolenie-worker` ma `SchedulingDisabled` (cordon został). Drain nie łamie umowy, tylko czeka. Upgrade węzłów w chmurze z takim PDB też stanie.

**6. PDB z zapasem**
```bash
kubectl delete pdb web-pdb
kubectl create pdb web-pdb --selector=app=web --max-unavailable=1
kubectl get pdb
kubectl drain szkolenie-worker --ignore-daemonsets
kubectl get pods -o wide
```
Co powinieneś zobaczyć: `ALLOWED DISRUPTIONS 1`. Drain wyrzuca pody po jednym i czeka na zastępcę (czasem raz `would violate…` i ponowienie), na koniec `node/szkolenie-worker drained`. Wszystkie 4 pody na `szkolenie-worker2`.

**7. Uncordon: pody nie wracają same**
```bash
kubectl uncordon szkolenie-worker
kubectl get pods -o wide
kubectl rollout restart deployment web
kubectl get pods -o wide
```
Co powinieneś zobaczyć: po `uncordon` pody dalej wszystkie na `szkolenie-worker2`. Węzeł znów przyjmuje nowe pody, ale nikt nie przenosi działających. Dopiero po `rollout restart` nowe pody rozkładają się na oba workery.

## Sprzątanie
```bash
./prepare.sh --delete              # namespace taint-drain, tainty dedicated, uncordon
kubectl describe nodes | grep Taints   # został tylko taint control-plane
kubectl config use-context szkolenie   # z powrotem na wspólny klaster
```
Klaster kind przyda się w innych przykładach i labach. Gdy nie będzie już potrzebny: `./prepare.sh --usun-klaster` (albo `kind delete cluster --name szkolenie`).

## Uwagi
- Taint odpycha, toleracja pozwala, `nodeAffinity` przyciąga. Węzeł „tylko dla GPU” wymaga wszystkich trzech.
- PDB działa tylko na eksmisje (drain, upgrade węzłów, autoskaler). Nie blokuje `kubectl delete pod` ani rolling update i nie chroni przed awarią węzła. Szczegóły: [`../../16-pdb/`](../../16-pdb/).
- Na co dzień: `kubectl get pdb -A`. `ALLOWED DISRUPTIONS` równe 0 przez dłuższy czas to przyszły zablokowany upgrade.
