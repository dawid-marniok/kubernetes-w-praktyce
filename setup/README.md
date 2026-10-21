# Przygotowanie stanowiska

Nie musisz instalować wszystkiego od razu. Przed szkoleniem wystarczy Docker i git, resztę doinstalujesz w dniu, w którym jest potrzebna.

| Kiedy | Co instalujesz / ustawiasz | Po co | Instrukcja |
|---|---|---|---|
| **przed szkoleniem** (ok. 30 min, najlepiej dzień wcześniej) | Docker Desktop (4 CPU, 6 GB RAM), git, klon repo, darmowe konto Docker Hub + `docker login`; na koniec `bash setup/sprawdz-dzien-1.sh` | wszystkie laby dnia 1; limit pobrań z Docker Hub | punkty 1–2, [`docker-desktop.md`](docker-desktop.md) |
| **dzień 1, przed lab03** (ok. 13:45) | AWS CLI v2 (≥ 2.32), logowanie z karty dostępowej (`karta.md` w katalogu repo), `docker login` do Amazon ECR | wypychasz własny obraz do rejestru (lab03, lab04, projekt w dniu 5) | punkt 3, [`rejestr.md`](rejestr.md) |
| dzień 1, lab04, opcjonalnie | Trivy | lokalny skan obrazu; bez niego skan zrobi ECR | lab04, sekcja o skanowaniu |
| **dzień 2, rano** | kubectl, potem `aws login` i `aws eks update-kubeconfig` (nazwa klastra rano na czacie) | wszystkie laby dni 2–5 na wspólnym klastrze | punkty 4–5, karta dostępowa punkt 5 |
| dzień 2, opcjonalnie | k9s, Headlamp albo rozszerzenie VS Code | podgląd klastra w oknie | punkt 6 |
| dzień 3, po zajęciach, opcjonalnie | kind ≥ 0.33 i lokalny klaster `szkolenie` (ok. 3 GB RAM, 5 GB dysku) | taint, `cordon`, `drain`, PDB i etykiety węzłów krok po kroku: [`przyklady/k8s/15-affinity-taints/kind-taint-pdb-drain/`](../przyklady/k8s/15-affinity-taints/kind-taint-pdb-drain/); na wspólnym klastrze węzłów nie zmieniasz | [`kind.md`](kind.md) |
| dzień 3, lab11 na kind, opcjonalnie | metrics-server na kind | `kubectl top` i HPA lokalnie | [`kind.md`](kind.md), punkt 3 |
| **dzień 4, przed lab14** | Trivy i Kubescape, potem `trivy image --download-db-only` (kilkaset MB) | skanowanie obrazów i manifestów | lab14, sekcja „Zanim zaczniesz” |
| dzień 4, zadania „na kind” | ten sam klaster kind z dnia 3 | RBAC klastrowy, NetworkPolicy między namespace'ami, CRD | [`kind.md`](kind.md) |
| **dzień 5, przed lab17** | Helm (v3 lub v4) | lab17, projekt końcowy (poziom ambitny) | punkt 7 |
| dzień 5, lab19 | tylko przeglądarka: adres Grafany i hasło od prowadzącego | metryki, logi, alerty | — |
| dzień 5, lab18, opcjonalnie | krew + plugin `kubectl cnpg` | switchover bazy jedną komendą | lab18, zadanie D |

Pogrubione wiersze są obowiązkowe, reszta to dodatki.

Windows: Docker Desktop z backendem WSL2. Komendy z labów uruchamiaj w terminalu **WSL (Ubuntu) albo Git Bash**: laby używają `grep`, `head`, `wc`, `time`, `2>/dev/null`, których PowerShell nie ma.

---

## Dzień 1: Docker

### 1. Docker Desktop

Pobierz z https://www.docker.com/products/docker-desktop/ i zainstaluj (macOS: wersja dla Apple Silicon albo Intel; Windows: z WSL2).
W ustawieniach (Settings → Resources) daj Dockerowi co najmniej **4 CPU i 6 GB RAM** i ok. 20 GB dysku — klaster kind z dni 3–4 potrzebuje miejsca.
Docker Desktop w firmie powyżej progu licencyjnego wymaga płatnej subskrypcji; jeśli Twoja firma jej nie ma, zapytaj prowadzącego o alternatywę (Rancher Desktop, Podman Desktop, Docker Engine na Linuksie).

Sprawdzenie:

```bash
docker version                 # Client i Server, wersja 28 albo nowsza
docker compose version         # Docker Compose version v2 albo nowszy
docker run --rm hello-world    # „Hello from Docker!”
```

`Cannot connect to the Docker daemon` → Docker Desktop nie jest uruchomiony (ikona wieloryba w pasku).

### 2. git i repo

```bash
git --version                  # brak? macOS: xcode-select --install · Windows/WSL: sudo apt install git
git clone https://github.com/dawid-marniok/kubernetes-w-praktyce.git
cd kubernetes-w-praktyce
```

Edytor: dowolny. Polecamy Visual Studio Code z rozszerzeniami Docker i Kubernetes (podpowiedzi w YAML-u).

### Sprawdzenie przed dniem 1

Jedna komenda sprawdza wszystko z punktów 1–2: Docker i jego zasoby, Compose, buildx, logowanie do Docker Hub, git, wolne porty z labów i AWS CLI (na później). Niczego nie instaluje i nie zmienia.

```bash
bash setup/sprawdz-dzien-1.sh           # ok. 1 min
bash setup/sprawdz-dzien-1.sh --pull    # dodatkowo pobiera obrazy z labów dnia 1 (ok. 4 GB) — zrób to w domu, nie na szkoleniu
```

✅ `SUKCES: stanowisko gotowe do dnia 1` albo 🟡 z uwagami (⚠️) — możesz przyjść. ❌ — popraw przed szkoleniem; jeśli utkniesz, wyślij prowadzącemu wynik skryptu.

### 3. Rejestr obrazów (lab 3 i projekt w dniu 5)

Obraz, który zbudujesz, wysyłasz do rejestru Amazon ECR, z którego potem pobierze go klaster. W labach adres rejestru to **`<REJESTR>`**: Twój jest w punkcie 1 karty dostępowej (`<login>.md` od prowadzącego prywatnie). Instalacja AWS CLI i logowanie: karta, punkty 2–4, oraz [`rejestr.md`](rejestr.md).

```bash
docker build --platform linux/amd64 -t <REJESTR>/todos-api:1.0.0 .
docker push <REJESTR>/todos-api:1.0.0
```

`--platform linux/amd64` jest ważne na Macach z procesorem M: węzły klastra mają procesory x86, a obraz zbudowany dla arm64 skończy się na nich błędem `exec format error`.
Tag zawsze z wersją (`1.0.0`, `1.0.1`), nie `latest` — inaczej nie wiesz, co naprawdę działa w klastrze.

Dodatkowo zaloguj się darmowym kontem do Docker Hub (`docker login`): podnosi limit pobrań obrazów bazowych, który na szkoleniu potrafi się skończyć.

---

## Dni 2–5: Kubernetes

### 4. kubectl

| System | Instalacja |
|---|---|
| macOS | `brew install kubectl` |
| Windows | `winget install -e --id Kubernetes.kubectl` (albo w WSL jak Linux) |
| Linux / WSL | `curl -LO "https://dl.k8s.io/release/$(curl -Ls https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" && sudo install kubectl /usr/local/bin/` |

```bash
kubectl version --client       # kubectl może różnić się od klastra o ±1 wersję; klaster ma 1.35 (EKS)
```

### 5. Dostęp do klastra

Do klastra logujesz się tym samym kontem AWS co do rejestru w dniu 1 — prowadzący nie wysyła żadnych plików. Login to jednocześnie nazwa Twojego namespace. Nazwę klastra (`<KLASTER>`) podamy rano w dniu 2; wpisz ją w punkcie 1 swojej karty dostępowej.

Raz, po porannym `aws login --profile szkolenie` (karta, punkt 3):

```bash
aws eks update-kubeconfig --name <KLASTER> --region eu-central-1 --profile szkolenie --alias szkolenie
kubectl config set-context szkolenie --namespace=<login>
kubectl config use-context szkolenie
```

`update-kubeconfig` dopisuje kontekst `szkolenie` do `~/.kube/config`. Twoje konteksty z pracy zostają, a po szkoleniu usuwasz tylko ten jeden: `kubectl config delete-context szkolenie`.
W kubeconfigu nie ma tokenu: `kubectl` przy każdym poleceniu prosi `aws` o krótki token, dlatego **`aws` i `kubectl` muszą działać w tym samym terminalu** (Windows: oba w PowerShellu albo oba w WSL), a sesja AWS musi być ważna.

Sprawdzenie:

```bash
kubectl config current-context                     # szkolenie
kubectl config view --minify | grep namespace      # namespace: <login>
kubectl auth whoami                                # Username: <login>
kubectl get nodes                                  # 3 węzły, STATUS Ready
kubectl get pods                                   # No resources found in <login> namespace.
kubectl auth can-i create deployments              # yes
kubectl auth can-i create pods -n kube-system      # no — i tak ma być
```

| Objaw | Co zrobić |
|---|---|
| `You must be logged in to the server (Unauthorized)` / `getting credentials: exec: executable aws failed` | sesja AWS wygasła: `aws login --profile szkolenie` i ponów polecenie |
| `exec: "aws": executable file not found` | `kubectl` nie widzi `aws`: zainstaluj AWS CLI w tym samym środowisku co `kubectl` |
| `AccessDeniedException … eks:DescribeCluster` przy `update-kubeconfig` | literówka w nazwie klastra albo brak `--profile szkolenie` |
| `The connection to the server localhost:8080 was refused` | brak kontekstu: powtórz `aws eks update-kubeconfig …` |
| `can-i create deployments` → `no` | zły namespace w kontekście: `kubectl config set-context szkolenie --namespace=<login>` |
| polecenia trafiają do kind albo do klastra z pracy | zły kontekst: `kubectl config use-context szkolenie` |
| `Unable to connect … i/o timeout` | firmowy VPN/proxy blokuje adres klastra — spróbuj bez VPN i daj znać na czacie |

### 6. Narzędzia graficzne (opcjonalnie)

Korzystają z tego samego kubeconfigu i mają te same uprawnienia co `kubectl`. Też wołają `aws` po token: aplikacje okienkowe (Headlamp) uruchomione z menu mogą go nie widzieć w PATH — wtedy uruchom je z terminala.

| Narzędzie | Co to | Instalacja |
|---|---|---|
| k9s | panel w terminalu | `brew install k9s` · `winget install -e --id Derailed.k9s` · https://k9scli.io |
| Headlamp | aplikacja okienkowa (projekt Kubernetes SIG) | https://headlamp.dev |
| VS Code + rozszerzenie Kubernetes | drzewo zasobów, podgląd YAML, logi | rozszerzenie `ms-kubernetes-tools.vscode-kubernetes-tools` |

### 7. Dzień 5: Helm

```bash
brew install helm        # macOS · Windows: winget install -e --id Helm.Helm · Linux: https://helm.sh/docs/intro/install/
helm version             # v3.x albo v4.x
```

---

## Po szkoleniu

Konto AWS i dostęp do klastra wygasają po ostatnim dniu (namespace'y są usuwane razem z zawartością); kontekst usuniesz poleceniem `kubectl config delete-context szkolenie`. Repo zostaje Twoje. Do dalszej nauki: lokalny klaster z [`kind.md`](kind.md) — laby działają na nim tak samo (namespace tworzysz sam: `kubectl create namespace <login>`).
