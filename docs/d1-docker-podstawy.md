# Dzień 1 — ściąga: podstawy Dockera i komendy

Gotowe pliki z zajęć: `przyklady/docker/build/` (Dockerfile: nginx, Node, .NET multi-stage), `przyklady/docker/compose/` (Compose: nginx, shoppinglist, skalowanie). Przygotowanie laptopa: `setup/docker-desktop.md`, rejestr: `setup/rejestr.md`.

## Pojęcia w pięciu zdaniach

| Pojęcie | Czym jest |
|---|---|
| **Obraz** | paczka tylko do odczytu: system plików aplikacji w warstwach + metadane (komenda startowa, porty, użytkownik). Adres: `rejestr/przestrzeń/repozytorium:tag` |
| **Kontener** | uruchomiony obraz: izolowany proces na wspólnym kernelu hosta + cienka warstwa zapisu. Żyje tyle, co jego proces PID 1 |
| **Wolumen** | dane poza kontenerem; przeżywa `docker rm` |
| **Sieć** | własna sieć (`docker network create`) daje DNS: kontenery widzą się po nazwie |
| **Rejestr** | magazyn obrazów: Docker Hub, GHCR, Amazon ECR (nasz); `docker push` / `docker pull` |

Kontener to nie mała maszyna wirtualna: nie ma własnego systemu ani kernela. Pod spodem: `docker` (CLI) → `dockerd` → `containerd` → `containerd-shim` → `runc`.

## Czy Docker działa

```bash
docker version                 # muszą być dwie sekcje: Client i Server
docker run --rm hello-world    # pobiera obraz i uruchamia kontener
docker info                    # silnik, liczba kontenerów, sterownik storage
docker system df               # ile miejsca zajmują obrazy, kontenery, wolumeny, cache
```

`Cannot connect to the Docker daemon` → Docker Desktop nie jest uruchomiony.
`toomanyrequests` przy pull → limit anonimowych pobrań z Docker Hub: `docker login` darmowym kontem.

## Kontenery

```bash
docker run -d --name web -p 8080:80 nginx:1.29        # w tle, port hosta 8080 → 80 w kontenerze
docker run -it --rm ubuntu:24.04 bash                  # interaktywnie, usuń po wyjściu
docker run -d --name db -e POSTGRES_PASSWORD=changeme-db postgres:18
docker run -d --name db --env-file db.env postgres:18  # zmienne z pliku

docker ps                      # działające
docker ps -a                   # wszystkie, także Exited i Created
docker logs web                # stdout i stderr procesu
docker logs -f --tail 20 web   # śledź, ostatnie 20 linii (--since 5m, -t z czasem)
docker exec -it web sh         # powłoka w działającym kontenerze
docker exec web nginx -v       # jedna komenda
docker inspect web             # pełna konfiguracja i stan (JSON)
docker inspect -f '{{.State.Status}} {{.NetworkSettings.IPAddress}}' web
docker port web                # mapowania portów
docker top web                 # procesy w kontenerze
docker stats --no-stream       # CPU i pamięć

docker stop web                # SIGTERM, po 10 s SIGKILL (-t 3 = po 3 s)
docker start web               # ten sam kontener, te same dane w warstwie zapisu
docker restart web
docker rm web                  # usuń zatrzymany (-f = zatrzymaj i usuń, -v = z anonimowymi wolumenami)
docker container prune         # usuń wszystkie zatrzymane
```

Najczęstsze flagi `docker run`:

| Flaga | Do czego |
|---|---|
| `-d` | w tle (detached) |
| `-it` | interaktywny terminal |
| `--rm` | usuń kontener po zakończeniu |
| `--name web` | własna nazwa zamiast losowej |
| `-p 8080:80` | port **hosta**:port **kontenera**; `-p 127.0.0.1:8080:80` tylko lokalnie |
| `-e KLUCZ=wartość`, `--env-file plik` | zmienne środowiskowe |
| `-v nazwa:/ścieżka`, `-v ./katalog:/ścieżka:ro` | wolumen albo bind mount (`:ro` tylko do odczytu) |
| `--network app-net` | podłącz do własnej sieci |
| `--restart unless-stopped` | wstań po awarii i restarcie Dockera |
| `--init` | mały init jako PID 1: przekazuje sygnały, `docker stop` kończy się od razu |
| `--memory 256m --cpus 0.5` | limity zasobów |
| `-u 1000`, `--read-only`, `--cap-drop ALL` | mniej uprawnień (patrz Bezpieczeństwo) |

Stany kontenera: `Created` (nie wystartował, np. zajęty port) → `Running` → `Exited (kod)`. `Exited (0)` = proces skończył normalnie, `Exited (1)` = błąd aplikacji (zobacz `docker logs`), `Exited (137)` = zabity (SIGKILL albo brak pamięci).

## Obrazy

```bash
docker pull nginx:1.29
docker images                          # lista lokalnych obrazów
docker history nginx:1.29              # warstwy i ich rozmiar
docker tag node-app:1.0.0 <REJESTR>/node-app:1.0.0
docker login <rejestr>                 # Docker Hub: docker login
docker push <REJESTR>/node-app:1.0.0
docker rmi nginx:1.29                  # usuń obraz (nie da się, gdy używa go jakiś kontener)
docker image prune                     # usuń obrazy bez tagu (dangling)
```

Zawsze tag z wersją (`nginx:1.29`, `node:22-alpine`), nigdy `latest`: `latest` to tylko nazwa, nie znaczy „najnowszy” i nie da się do niego wrócić przy rollbacku.

## Dockerfile

```dockerfile
FROM node:22-alpine                 # obraz bazowy z wersją
WORKDIR /app
COPY package*.json ./               # najpierw zależności: cache przeżyje zmianę kodu
RUN npm ci --omit=dev
COPY . .                            # potem kod
ENV NODE_ENV=production
EXPOSE 3000                         # dokumentacja; port publikuje dopiero -p
USER node                           # nie root
CMD ["node", "app.js"]              # forma exec: proces dostaje sygnały
```

| Instrukcja | Do czego |
|---|---|
| `FROM` | obraz bazowy; kilka `FROM` = multi-stage |
| `RUN` | komenda w czasie budowania, tworzy warstwę |
| `COPY` / `ADD` | pliki z kontekstu do obrazu (`ADD` tylko, gdy musisz rozpakować archiwum) |
| `WORKDIR` | katalog roboczy |
| `ENV` | zmienna dostępna w czasie budowania i w kontenerze |
| `ARG` | zmienna tylko w czasie budowania (`--build-arg`); **nie dla sekretów**, widać ją w `docker history` |
| `EXPOSE` | informacja, na jakim porcie słucha aplikacja |
| `USER` | użytkownik procesu |
| `HEALTHCHECK` | komenda sprawdzająca, czy aplikacja działa (`healthy` w `docker ps`) |
| `CMD` / `ENTRYPOINT` | co uruchomić; `ENTRYPOINT` = program, `CMD` = domyślne argumenty |

```bash
docker build -t node-app:1.0.0 .                     # kropka = kontekst budowania
docker build -f Dockerfile.prod -t app:1.0.0 .       # inny plik
docker build --no-cache -t app:1.0.0 .               # bez cache
docker buildx build --platform linux/amd64 -t <REJESTR>/app:1.0.0 --push .   # Mac M → klaster amd64
```

Zasady:
- Kolejność: od tego, co zmienia się rzadko (baza, zależności), do tego, co często (kod). Zmiana jednej warstwy unieważnia cache wszystkich kolejnych.
- `.dockerignore` (`node_modules`, `.git`, `.env`, `bin/`, `obj/`): mniejszy kontekst, brak sekretów w obrazie.
- Multi-stage: kompilator w etapie `build`, do obrazu końcowego tylko wynik (`COPY --from=build …`). Przykład: `przyklady/docker/build/3-dotnet-multistage/` (ok. 262 MB zamiast 975 MB).
- Sekret przy budowaniu: `RUN --mount=type=secret,id=token …` + `docker build --secret id=token,src=token.txt`, nie `ARG` ani `ENV`.
- Obraz na Macu M jest `arm64`; klaster EKS jest `amd64` → `--platform linux/amd64`, inaczej `exec format error`.

## Sieci

```bash
docker network create app-net
docker run -d --name api --network app-net nginx:1.29
docker run --rm --network app-net busybox:1.37 wget -qO- http://api   # po nazwie
docker network connect app-net web      # dołącz działający kontener
docker network ls
docker network inspect app-net          # kto jest w sieci, jakie adresy
docker network rm app-net
```

- Domyślna sieć `bridge`: kontenery widzą się tylko po IP, **nazwy nie działają**. Własna sieć: wbudowany DNS, nazwa kontenera = nazwa hosta.
- Kontenery w różnych sieciach się nie widzą.
- `-p` jest potrzebne tylko do ruchu **z hosta** (przeglądarka, curl na laptopie). Między kontenerami w jednej sieci wystarczy nazwa i port wewnętrzny.
- Narzędzia sieciowe: `busybox:1.37` (`ping`, `nslookup`, `wget`), `nicolaka/netshoot:v0.14` (wszystko).

## Dane: wolumen, bind mount, tmpfs

```bash
docker volume create dane
docker run -d --name db -v dane:/var/lib/postgresql --env-file db.env postgres:18
docker run -d -p 8080:80 -v ./strona:/usr/share/nginx/html:ro nginx:1.29   # bind mount
docker run -d --tmpfs /tmp nginx:1.29                                         # w pamięci
docker volume ls
docker volume inspect dane
docker volume rm dane
docker volume prune                     # nieużywane wolumeny: dane znikają na zawsze
```

| | Wolumen (`-v nazwa:/ścieżka`) | Bind mount (`-v ./katalog:/ścieżka`) | tmpfs (`--tmpfs /ścieżka`) |
|---|---|---|---|
| Gdzie leży | zarządza Docker | Twój katalog na laptopie | pamięć RAM |
| Przeżywa `docker rm` | tak | tak | nie |
| Pusty na starcie | kopiuje zawartość katalogu z obrazu | **przykrywa** katalog z obrazu | pusty |
| Do czego | bazy, dane aplikacji | kod w trakcie pisania, pliki konfiguracji | pliki tymczasowe, `--read-only` |

tmpfs na przykładach (restart, `--read-only`, limit rozmiaru, Compose): [d1-docker-tmpfs.md](d1-docker-tmpfs.md).

`postgres:18` trzyma dane w `/var/lib/postgresql` (starsze wersje: `/var/lib/postgresql/data`).

Kopia wolumenu (po zatrzymaniu bazy):
```bash
docker run --rm -v dane:/dane -v ./backup:/backup busybox:1.37 tar czf /backup/dane.tgz -C /dane .
```

## Logi

```bash
docker logs web --tail 50 --since 10m -t
docker run -d --log-opt max-size=10m --log-opt max-file=3 nginx:1.29   # rotacja
docker inspect -f '{{.LogPath}}' web                                    # plik logów na hoście
```

Aplikacja pisze na stdout i stderr, nie do pliku w kontenerze. Bez `max-size` logi rosną aż do zapełnienia dysku. Na stałe dla wszystkich kontenerów: `daemon.json` (w Docker Desktop: Settings → Docker Engine).

## Bezpieczeństwo

```bash
docker run -d --name web -p 8080:8080 \
  --user 101 --read-only --tmpfs /tmp \
  --cap-drop ALL --security-opt no-new-privileges \
  nginxinc/nginx-unprivileged:1.29
docker exec web id                         # uid inny niż 0?
trivy image --severity HIGH,CRITICAL nginx:1.29
docker scout quickview nginx:1.29
```

- Mały obraz bazowy (`-alpine`, `-slim`, distroless) = mniej podatności.
- `USER` w Dockerfile albo `--user` przy starcie: proces nie jako root.
- Nigdy `-v /var/run/docker.sock:/var/run/docker.sock` dla zwykłej aplikacji: to pełny root na hoście.
- Hasła nie w Dockerfile i nie w obrazie: zmienne przy starcie, pliki `.env` poza gitem, w Kubernetesie Secret.

## Docker Compose

```yaml
# compose.yaml
services:
  api:
    build: ./backend
    image: <REJESTR>/todos-api:1.0.0
    environment:
      MONGODB_URI: mongodb://mongo:27017/todos     # usługa po nazwie
    depends_on:
      mongo:
        condition: service_healthy                 # czekaj na healthcheck, nie tylko na start
    restart: unless-stopped
  web:
    build: ./frontend
    ports:
      - "3000:8080"                                # nginx-unprivileged słucha na 8080
    depends_on: [api]
  mongo:
    image: mongo:7.0
    volumes:
      - mongodb_data:/data/db
    healthcheck:
      test: ["CMD", "mongosh", "--quiet", "--eval", "db.adminCommand('ping')"]
      interval: 5s
      retries: 10
  mongo-express:
    image: mongo-express:1.0.2-20-alpine3.19
    profiles: [debug]                              # startuje tylko z --profile debug
volumes:
  mongodb_data:
```

```bash
docker compose up -d                    # utwórz i uruchom wszystko
docker compose up -d --build            # najpierw zbuduj obrazy
docker compose ps                       # stan usług (healthy?)
docker compose logs -f api              # logi jednej usługi
docker compose exec api sh              # powłoka w usłudze
docker compose config                   # plik po scaleniu, pokazuje błędy YAML
docker compose --profile debug up -d    # z usługami z profilu
docker compose up -d --scale web=3      # trzy kopie usługi (bez stałego portu hosta)
docker compose watch                    # zmiany w kodzie trafiają do kontenera
docker compose build && docker compose push
docker compose stop                     # zatrzymaj, nic nie usuwaj
docker compose down                     # usuń kontenery i sieć, wolumeny zostają
docker compose down -v                  # razem z wolumenami: dane znikają
```

- Compose tworzy dla projektu własną sieć: usługi widzą się po nazwie (`mongo`, `api`).
- `depends_on` bez `condition: service_healthy` czeka tylko na start kontenera, nie na gotowość bazy.
- Hasła w pliku `.env` obok `compose.yaml` (`${MONGO_PASSWORD}`), plik `.env` w `.gitignore`.

## Sprzątanie

```bash
docker rm -f $(docker ps -aq)           # wszystkie kontenery (ostrożnie!)
docker system prune                     # zatrzymane kontenery, nieużywane sieci, obrazy bez tagu, cache
docker system prune -a --volumes        # wszystko nieużywane, łącznie z obrazami i wolumenami
docker builder prune                    # cache budowania
```

## Gdy coś nie działa

| Objaw | Przyczyna i co zrobić |
|---|---|
| `port is already allocated` | port hosta zajęty: `docker ps`, usuń stary kontener albo zmień lewą stronę `-p` |
| kontener od razu `Exited` | `docker logs <nazwa>`: brak zmiennej (np. hasła), błąd w komendzie, proces skończył pracę |
| `Exited (137)` | zabity: brak pamięci (`--memory`) albo `docker stop` po 10 s |
| `docker stop` trwa 10 s | PID 1 ignoruje SIGTERM (np. `sh -c`): `CMD` w formie exec albo `--init` |
| `ping: bad address 'api'` | kontenery nie są w tej samej własnej sieci |
| zmiana w pliku nie widać | obraz z kodem trzeba przebudować (`--build`); bind mount tylko do pracy lokalnej |
| `COPY failed: file not found` | zły kontekst budowania (ostatni argument `docker build`) albo plik w `.dockerignore` |
| `exec format error` na klastrze | obraz `arm64` z Maca M: `docker buildx build --platform linux/amd64` |
| `unauthorized` / `denied` przy push | `docker login`, literówka w nazwie rejestru, token bez prawa zapisu |
| `no space left on device` | `docker system df`, potem `docker image prune`, `docker builder prune` |
| `toomanyrequests` | limit Docker Hub: `docker login` darmowym kontem |

## Z Dockera do Kubernetesa

| Docker | Kubernetes (dni 2–5) |
|---|---|
| `docker run` | Pod, a w praktyce Deployment |
| `-p`, nazwa w sieci | Service, Ingress / Gateway API |
| `-e`, `--env-file` | ConfigMap, Secret |
| `-v nazwa:/ścieżka` | PersistentVolumeClaim, StatefulSet |
| `HEALTHCHECK` | readinessProbe, livenessProbe |
| `--memory`, `--cpus` | `resources.requests` / `limits` |
| `--user`, `--read-only`, `--cap-drop` | `securityContext` |
| `docker logs`, `docker exec` | `kubectl logs`, `kubectl exec` |
| `compose.yaml` | manifesty YAML, chart Helm |
