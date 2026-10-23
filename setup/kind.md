# Lokalny klaster kind

kind (Kubernetes IN Docker) uruchamia węzły klastra jako kontenery Dockera. Na wspólnym klastrze szkoleniowym (EKS) nie możesz dotykać węzłów, więc ćwiczenia z taintami, `cordon`/`drain`, etykietami węzłów, CRD i StorageClass robisz tutaj: masz pełne uprawnienia administratora.
Nasz klaster: **1 control plane + 2 workery**, Kubernetes 1.35. Potrzebuje ok. 3 GB RAM i 5 GB dysku w Docker Desktop.

## 1. Instalacja kind

Potrzebna wersja **v0.33.0** albo nowsza (obraz węzła w naszej konfiguracji jest zbudowany dla v0.33).

| System | Instalacja |
|---|---|
| macOS | `brew install kind` |
| Windows | `winget install -e --id Kubernetes.kind` |
| Linux / WSL (x86_64) | `curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.33.0/kind-linux-amd64 && chmod +x kind && sudo mv kind /usr/local/bin/` |

```bash
kind version             # kind v0.33.0 …
```

## 2. Klaster do labów

Z katalogu głównego repo:

```bash
kind create cluster --config setup/kind/kind-szkolenie.yaml
kubectl get nodes        # szkolenie-control-plane, szkolenie-worker, szkolenie-worker2 — wszystkie Ready
```

`kind create cluster` dopisuje kontekst `kind-szkolenie` do domyślnego kubeconfigu (`~/.kube/config`) i ustawia go jako bieżący.
Kontekst klastra szkoleniowego (`szkolenie`) też jest w `~/.kube/config`, więc po `kind create cluster` Twoje polecenia trafiają do kind. Przełączasz się tak:

```bash
kubectl config get-contexts                 # szkolenie i kind-szkolenie
kubectl config use-context kind-szkolenie   # lokalnie
kubectl --context kind-szkolenie get nodes  # jednorazowo, bez przełączania
kubectl config use-context szkolenie        # z powrotem na wspólny klaster
```

Konfiguracja (`setup/kind/kind-szkolenie.yaml`) przekierowuje porty z laptopa: `localhost:8088` → 80 i `localhost:8443` → 443 w klastrze (pod kontroler Ingress/Gateway), `localhost:30000`–`30002` → NodePorty o tych samych numerach.

Na kind nie ma namespace'u z Twoim loginem — utwórz go, żeby komendy z labów działały bez zmian:

```bash
kubectl create namespace user07
kubectl config set-context --current --namespace=user07
```

## 3. metrics-server (dzień 3: `kubectl top`, HPA)

⚠ Tylko na kind: na klastrze szkoleniowym ten plik psuje dodatek EKS (`kubectl top` i HPA przestają działać wszystkim). Najpierw sprawdź kontekst.

```bash
kubectl config current-context        # musi być kind-szkolenie
kubectl apply -f setup/kind/metrics-server/metrics-server.yaml
kubectl -n kube-system rollout status deploy/metrics-server
kubectl top nodes        # po ok. minucie liczby zamiast „metrics not available yet”
```

Na klastrze szkoleniowym tego kroku nie robisz: metrics-server instaluje tam prowadzący.

## 4. Własny obraz bez rejestru

Obraz zbudowany lokalnie wgrywasz prosto do węzłów:

```bash
docker build -t todos-api:1.0.0 .
kind load docker-image todos-api:1.0.0 --name szkolenie
```

W manifeście `image: todos-api:1.0.0` i `imagePullPolicy: IfNotPresent`. Na kind nie potrzebujesz `--platform linux/amd64` — węzły mają architekturę Twojego laptopa.

## 5. Sprzątanie

```bash
kind get clusters
kind delete cluster --name szkolenie       # usuwa kontenery węzłów i kontekst kind-szkolenie
```

## Typowe problemy

| Objaw | Co zrobić |
|---|---|
| `failed to create cluster … no space left on device` | za mało dysku w Docker Desktop: Settings → Resources, albo `docker system prune` (usuwa nieużywane obrazy i kontenery) |
| `address already in use` przy tworzeniu | port 8088, 8443 albo 30000–30002 zajęty (np. kontener z dnia 1): `docker ps`, zatrzymaj go albo zmień `hostPort` w pliku |
| węzeł `NotReady` przez kilka minut | mało RAM-u dla Dockera — daj co najmniej 6 GB |
| `kind load` → `image not present locally` | inna nazwa/tag niż przy `docker build`; sprawdź `docker images` |
| pody w `ImagePullBackOff` dla obrazu z `kind load` | brak `imagePullPolicy: IfNotPresent` przy tagu `latest`; używaj tagu z wersją |
| `kubectl` łączy się z klastrem szkoleniowym zamiast z kind (albo odwrotnie) | zły kontekst: `kubectl config use-context kind-szkolenie` (wspólny: `szkolenie`) |
