# Przygotowanie stanowiska

| Kiedy | Co |
|---|---|
| przed szkoleniem | Docker Desktop, git, klon repo (część „Dzień 1”) — ok. 30 min, najlepiej dzień wcześniej |
| dzień 1, przed labem 3 | rejestr obrazów Amazon ECR: AWS CLI i logowanie z karty dostępowej (część „Rejestr obrazów”) |
| rano w dniu 2 | kubectl i kubeconfig od prowadzącego (część „Dni 2–5”) |
| dzień 3–4, opcjonalnie | lokalny klaster kind do ćwiczeń z węzłami: [`kind.md`](kind.md) |

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
docker compose version         # Docker Compose version v2.x
docker run --rm hello-world    # „Hello from Docker!”
```

`Cannot connect to the Docker daemon` → Docker Desktop nie jest uruchomiony (ikona wieloryba w pasku).

### 2. git i repo

```bash
git --version                  # brak? macOS: xcode-select --install · Windows/WSL: sudo apt install git
git clone <adres repo z czatu>
cd kubernetes-w-praktyce
```

Edytor: dowolny. Polecamy Visual Studio Code z rozszerzeniami Docker i Kubernetes (podpowiedzi w YAML-u).

### 3. Rejestr obrazów (lab 3 i projekt w dniu 5)

Obraz, który zbudujesz, wysyłasz do rejestru Amazon ECR, z którego potem pobierze go klaster. W labach adres rejestru to **`<REJESTR>`**: Twój jest w punkcie 1 karty dostępowej (`<login>.html`, od prowadzącego prywatnie). Instalacja AWS CLI i logowanie: karta, punkty 2–3, oraz [`rejestr.md`](rejestr.md).

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
kubectl version --client       # 1.34 albo nowszy (klaster ma 1.35; kubectl może różnić się o ±1 wersję)
```

### 5. Dostęp do klastra

Rano w dniu 2 dostajesz od prowadzącego prywatnie plik `<login>.kubeconfig` (np. `user07.kubeconfig`). Login to jednocześnie nazwa Twojego namespace.

macOS / Linux / WSL:

```bash
mkdir -p ~/.kube
cp ~/Downloads/user07.kubeconfig ~/.kube/szkolenie.kubeconfig
chmod 600 ~/.kube/szkolenie.kubeconfig
export KUBECONFIG=~/.kube/szkolenie.kubeconfig     # dopisz do ~/.zshrc albo ~/.bashrc, żeby działało w nowym terminalu
```

Windows (PowerShell):

```powershell
mkdir $HOME\.kube -Force
copy $HOME\Downloads\user07.kubeconfig $HOME\.kube\szkolenie.kubeconfig
$env:KUBECONFIG = "$HOME\.kube\szkolenie.kubeconfig"
```

Masz już własny `~/.kube/config` z pracy? Nie nadpisuj go — osobny plik i `KUBECONFIG` wystarczą, a po szkoleniu po prostu go usuwasz.

Sprawdzenie:

```bash
kubectl config current-context                     # aks-szkolenie
kubectl config set-context --current --namespace=user07   # w pliku już jest; po tej komendzie na pewno
kubectl config view --minify | grep namespace      # namespace: user07
kubectl auth whoami                                # system:serviceaccount:user07:user07
kubectl get nodes                                  # 3 węzły, STATUS Ready
kubectl get pods                                   # No resources found in user07 namespace.
kubectl auth can-i create deployments              # yes
kubectl auth can-i create pods -n kube-system      # no — i tak ma być
```

| Objaw | Co zrobić |
|---|---|
| `error: You must be logged in` / `Unauthorized` | zły plik albo token unieważniony — napisz do prowadzącego |
| `The connection to the server localhost:8080 was refused` | `KUBECONFIG` nie ustawiony w tym terminalu |
| `can-i create deployments` → `no` | zły namespace w kontekście: `kubectl config set-context --current --namespace=<login>` |
| `Unable to connect … i/o timeout` | firmowy VPN/proxy blokuje adres klastra — spróbuj bez VPN i daj znać na czacie |

### 6. Narzędzia graficzne (opcjonalnie)

Korzystają z tego samego kubeconfigu i mają te same uprawnienia co `kubectl`.

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

Dostęp do klastra wygasa po ostatnim dniu (namespace'y są usuwane razem z zawartością). Repo zostaje Twoje. Do dalszej nauki: lokalny klaster z [`kind.md`](kind.md) — laby działają na nim tak samo (namespace tworzysz sam: `kubectl create namespace <login>`).
