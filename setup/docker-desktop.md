# Docker Desktop: instalacja i sprawdzenie

Dzień 1 (laby 1–4) robisz na swoim laptopie. Potrzebujesz działającego Dockera z Compose v2. Zrób to dzień przed szkoleniem: instalacja z pobieraniem trwa 15–30 minut, a na Windows może wymagać restartu.

Krótka wersja jest w [`README.md`](README.md); tu są szczegóły i problemy.

## Wymagania

- 4 CPU, 8 GB RAM w laptopie (Dockerowi dajesz co najmniej 4 CPU i 6 GB), ok. 20 GB wolnego miejsca.
- Uprawnienia administratora do instalacji (na laptopie firmowym czasem trzeba poprosić dział IT).
- Dostęp do Docker Hub (`registry-1.docker.io`) z Twojej sieci. Firmowe proxy: patrz [Proxy](#proxy).

## Instalacja

### Windows 10/11

1. Włącz WSL 2 (PowerShell jako administrator):
   ```powershell
   wsl --install
   wsl --status        # Default Version: 2
   ```
   Uruchom komputer ponownie, jeśli system o to poprosi.
2. Pobierz Docker Desktop: <https://www.docker.com/products/docker-desktop/>, zainstaluj z opcją **Use WSL 2 instead of Hyper-V**.
3. Uruchom Docker Desktop i poczekaj, aż status w lewym dolnym rogu będzie zielony („Engine running”).
4. Settings → Resources → WSL Integration: włącz integrację z dystrybucją Ubuntu, jeśli pracujesz w terminalu WSL.

Komendy z labów działają w PowerShellu, w terminalu WSL i w Git Bash. Różnice:

| | PowerShell | Git Bash / WSL |
|---|---|---|
| bieżący katalog w `-v` | `-v ${PWD}/strona:/x` | `-v "$(pwd)/strona":/x` (albo `-v ./strona:/x`) |
| `curl` | `curl.exe …` (samo `curl` to alias innej komendy) | `curl …` |
| `docker run -it` | działa | Git Bash: `winpty docker run -it …` |

### macOS

1. Sprawdź procesor: menu Apple → Ten Mac. „Apple M…” = wersja **Apple Silicon**, „Intel” = wersja **Intel**.
2. Pobierz i zainstaluj Docker Desktop: <https://www.docker.com/products/docker-desktop/>.
3. Uruchom Docker Desktop z Aplikacji, zaakceptuj uprawnienia, poczekaj na zielony status.

Mac z procesorem M buduje obrazy `linux/arm64`. Klaster w dniach 2–5 ma węzły `amd64`, dlatego obraz do rejestru budujesz z `--platform linux/amd64` (lab03, [`rejestr.md`](rejestr.md)).

Port 5000 na macOS zajmuje AirPlay Receiver. W labach mapujemy wtedy `-p 5001:5000`.

### Linux

Na Linuksie wystarczy Docker Engine (Docker Desktop dla Linuksa też działa, ale nie jest potrzebny). Instrukcja dla Twojej dystrybucji: <https://docs.docker.com/engine/install/>. Po instalacji:

```bash
sudo usermod -aG docker $USER      # żeby nie pisać sudo przed każdą komendą
newgrp docker                      # albo wyloguj się i zaloguj ponownie
sudo apt-get install docker-compose-plugin docker-buildx-plugin   # jeśli nie zainstalowały się z Engine (Debian/Ubuntu)
```

Członkostwo w grupie `docker` daje w praktyce uprawnienia roota na tej maszynie. Na laptopie szkoleniowym to w porządku, na serwerze współdzielonym już nie.

## Ustawienia Docker Desktop

Settings → Resources:

- CPU: co najmniej 4, pamięć: co najmniej 6 GB.
- Disk usage limit: co najmniej 40 GB. Obrazy z dnia 1 (Go, .NET SDK, Postgres) zajmują kilka GB, a lokalny klaster kind (opcjonalnie, dni 3–4) kolejne.

## Sprawdzenie

```bash
docker version
docker compose version
docker buildx version
docker run --rm hello-world
docker run --rm busybox:1.37 echo "działa"
```

✅ `docker version` pokazuje **Client** i **Server** (wersja 28 albo nowsza).
✅ `docker compose version` → `Docker Compose version v2.x` (stare `docker-compose` z myślnikiem nie jest potrzebne).
✅ `hello-world` wypisuje „Hello from Docker!”, `busybox` wypisuje „działa”.

Na koniec pobierz obrazy z dnia 1, żeby na szkoleniu nie czekać na sieć (opcjonalnie, ok. 3 GB):

```bash
for i in nginx:1.29 nginx:1.29-alpine ubuntu:24.04 postgres:18 redis:8.2-alpine busybox:1.37 nicolaka/netshoot:v0.14 node:22-alpine python:3.13-slim golang:1.25 alpine:3.22; do docker pull $i; done
```

PowerShell:

```powershell
"nginx:1.29","nginx:1.29-alpine","ubuntu:24.04","postgres:18","redis:8.2-alpine","busybox:1.37","nicolaka/netshoot:v0.14","node:22-alpine","python:3.13-slim","golang:1.25","alpine:3.22" | ForEach-Object { docker pull $_ }
```

## Proxy

Jeśli w firmie wychodzisz do internetu przez proxy:

- Docker Desktop: Settings → Resources → Proxies → Manual proxy configuration, adres i port proxy (te same co w przeglądarce). Bez tego `docker pull` kończy się `i/o timeout` albo `proxyconnect tcp`.
- Proxy z inspekcją TLS (podmienia certyfikaty): `x509: certificate signed by unknown authority`. Certyfikat firmowy trzeba dodać do systemu (macOS: Pęk kluczy, Windows: magazyn certyfikatów), Docker Desktop go wtedy użyje. Najszybciej: zapytaj dział IT albo pracuj na szkoleniu z sieci bez proxy.
- Linux (Docker Engine): `sudo systemctl edit docker` i sekcja `[Service]` z `Environment="HTTPS_PROXY=http://proxy:port"`, potem `sudo systemctl restart docker`.
- Proxy w czasie **budowania** obrazu (`apt-get`, `npm ci` w Dockerfile): `docker build --build-arg HTTPS_PROXY=http://proxy:port …`.

## Licencja

Docker Desktop jest bezpłatny do nauki, użytku prywatnego i w małych firmach. W większych firmach wymaga płatnej subskrypcji (Pro, Team albo Business). Próg na dziś: [UZUPEŁNIJ: sprawdzić na <https://www.docker.com/pricing/> — ostatnio: firmy poniżej 250 pracowników **i** poniżej 10 mln USD rocznego przychodu korzystają bezpłatnie].

Jeśli Twoja firma nie ma subskrypcji, a przekracza próg, napisz do prowadzącego przed szkoleniem. Alternatywy, na których laby z dnia 1 działają: Docker Engine na Linuksie (bezpłatny), Rancher Desktop (z silnikiem `dockerd (moby)`), Podman Desktop (komendy `podman` zamiast `docker`, drobne różnice przy sieciach i Compose).

## Gdy coś nie działa

| Objaw | Co zrobić |
|---|---|
| `Cannot connect to the Docker daemon at unix:///var/run/docker.sock` / `error during connect` | Docker Desktop nie działa albo startuje. Uruchom go i poczekaj na zielony status. Linux: `sudo systemctl start docker` |
| `permission denied while trying to connect to the Docker daemon socket` (Linux) | Użytkownik nie jest w grupie `docker`: `sudo usermod -aG docker $USER`, wyloguj się i zaloguj |
| Windows: `WSL 2 installation is incomplete` / Docker Desktop nie startuje | `wsl --update`, restart. W BIOS/UEFI musi być włączona wirtualizacja (VT-x / AMD-V) |
| Windows: `docker` nie działa w terminalu WSL | Settings → Resources → WSL Integration → włącz dla swojej dystrybucji |
| `toomanyrequests: You have reached your pull rate limit` | Limit pobrań anonimowych z Docker Hub (wiele osób z jednego adresu IP). Załóż darmowe konto i `docker login` |
| `i/o timeout` / `proxyconnect tcp` przy `docker pull` | Proxy: patrz [Proxy](#proxy). Albo VPN blokuje Docker Hub: spróbuj bez VPN |
| `x509: certificate signed by unknown authority` | Proxy z inspekcją TLS, patrz [Proxy](#proxy) |
| `no space left on device` | Dysk maszyny wirtualnej Dockera jest pełny: `docker system df`, usuń nieużywane obrazy (`docker image prune`), powiększ Disk usage limit |
| Mac: `WARNING: The requested image's platform (linux/amd64) does not match the detected host platform` | Obraz nie ma wersji arm64 i działa w emulacji. Na szkoleniu zwykle oznacza literówkę w nazwie obrazu |
