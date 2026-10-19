# lab03 — Własny obraz: od Dockerfile do rejestru

**Cel:** napisać Dockerfile, który dobrze korzysta z cache warstw, nie uruchamia aplikacji jako root i nie wnosi do obrazu zbędnych plików; porównać obraz multi-stage z jednoetapowym i wypchnąć obraz z wersją do rejestru.

**Czas:** ~60 min (kroki 1–4 ok. 45 min, reszta dla chętnych).

**Po labie masz:** własny obraz `node-app:1.0.0` działający jako użytkownik bez uprawnień roota, porównanie rozmiarów `sample:multi` i `sample:single` oraz swój obraz w rejestrze pod pełną nazwą z wersją. Ten obraz przyda się w dniach z Kubernetesem.

## Zanim zaczniesz

- Docker działa, lab01 i lab02 za Tobą.
- Terminal w katalogu tego labu:
  ```bash
  cd labs/lab03-dockerfile
  ```
  Kod aplikacji już tu jest (`nginx/`, `node/`, `go/`, `python/`). **Dockerfile piszesz sam**, w katalogu danej aplikacji, pod nazwą `Dockerfile` (wielka litera D: wtedy `docker build` znajdzie go bez `-f`).
- Rejestr: do kroku 4 potrzebujesz swojego `<REJESTR>` (punkt 1 karty dostępowej od prowadzącego) i zalogowania do Amazon ECR (punkt 3 karty). Opis: [`setup/rejestr.md`](../../setup/rejestr.md).
- Mac z procesorem M (arm64): klaster w dniach 2–5 ma węzły amd64. Obraz do rejestru budujesz z `--platform linux/amd64` (krok 4).
- Ściąga instrukcji: `FROM`, `WORKDIR`, `COPY`, `RUN`, `ENV`, `ARG`, `EXPOSE`, `USER`, `HEALTHCHECK`, `LABEL`, `CMD` / `ENTRYPOINT`. Dokumentacja: <https://docs.docker.com/reference/dockerfile/>.

Obrazy bazowe w tym labie: `nginx:1.29-alpine`, `node:22-alpine`, `golang:1.25`, `alpine:3.22`, `python:3.13-slim`, `ubuntu:24.04`. Zawsze z tagiem, nigdy `latest`.

---

## Poziom podstawowy

### 1. Pierwszy obraz: strona w nginx

W katalogu `nginx/` jest `index.html`. Napisz `nginx/Dockerfile`, który:

- startuje od `nginx:1.29-alpine`,
- kopiuje `index.html` do `/usr/share/nginx/html/`,
- ma etykietę `org.opencontainers.image.version` z wartością `1.0.0` (instrukcja `LABEL`),
- dokumentuje port 80 (`EXPOSE`).

`CMD` nie musisz pisać: dziedziczysz je z obrazu bazowego.

```bash
docker build -t moja-strona:1.0.0 nginx
docker run -d --name moja-strona -p 8080:80 moja-strona:1.0.0
curl http://localhost:8080
docker history moja-strona:1.0.0
docker image inspect -f '{{json .Config.Labels}}' moja-strona:1.0.0
```

✅ `curl` zwraca „Witaj z mojego obrazu!”.
✅ `docker history` pokazuje Twoje instrukcje na górze, a pod nimi warstwy obrazu `nginx`. Warstwa `COPY` ma rozmiar Twojego pliku (kilkaset bajtów).
✅ W etykietach jest `"org.opencontainers.image.version":"1.0.0"`.

Usuń kontener: `docker rm -f moja-strona`.

### 2. Aplikacja Node.js: cache warstw, `.dockerignore`, użytkownik bez roota

W katalogu `node/` są `package.json`, `package-lock.json` i `app.js` (Express, port 3000). Napisz `node/Dockerfile` według tych zasad:

1. `FROM node:22-alpine`, katalog roboczy `/app`.
2. **Najpierw** skopiuj tylko `package.json` i `package-lock.json`, zainstaluj zależności przez `npm ci --omit=dev`, **dopiero potem** skopiuj resztę kodu. Dzięki temu zmiana w `app.js` nie unieważnia warstwy z zależnościami.
3. Uruchamiaj aplikację jako użytkownik `node` (jest w obrazie, UID 1000): instrukcja `USER`.
4. `EXPOSE 3000`.
5. `CMD` w **formie exec** (tablica JSON), uruchamiające `node app.js` bezpośrednio, bez `npm start`.

Obok Dockerfile utwórz `node/.dockerignore`, który wyklucza z kontekstu budowania co najmniej: `node_modules`, `.env`, `.git`, `*.log`, `Dockerfile`, `.dockerignore`.

Zbuduj, uruchom i sprawdź:

```bash
docker build -t node-app:1.0.0 node
docker run -d --name node-app -p 3000:3000 node-app:1.0.0
curl http://localhost:3000
curl http://localhost:3000/whoami
docker exec node-app id
```

✅ `/whoami` zwraca `"uid":1000`, a `id` w kontenerze `uid=1000(node) gid=1000(node)`. Uwaga: `echo $USER` w kontenerze jest puste. Instrukcja `USER` nie ustawia tej zmiennej, dlatego sprawdzamy `id`.

**Cache.** Zmień tekst powitania w `node/app.js` i zbuduj ponownie z wersją `1.0.1`:

```bash
docker build -t node-app:1.0.1 node
```

✅ Kroki z `package*.json` i `npm ci` mają oznaczenie `CACHED`, wykonuje się tylko `COPY` z kodem. Build trwa sekundy.

**`.dockerignore`.** Utwórz w `node/` plik, który nie powinien trafić do obrazu, i sprawdź, czego obraz nie zawiera:

```bash
echo "API_KEY=changeme-nie-do-obrazu" > node/.env
docker build -t node-app:1.0.1 node
docker run --rm node-app:1.0.1 ls -la /app
```

✅ W `/app` nie ma `.env` ani `Dockerfile`.

**Zatrzymanie.**

```bash
docker exec node-app ps -o pid,args
time docker stop node-app
docker logs node-app | tail -n 1
docker inspect -f '{{.State.ExitCode}}' node-app
docker rm node-app
```

✅ PID 1 w kontenerze to `node app.js`. `docker stop` trwa poniżej sekundy, w logach jest `SIGTERM, zamykam`, kod wyjścia `0`: aplikacja dostała sygnał i sama się zamknęła.

Zastanów się: kto byłby PID 1 przy `CMD npm start` albo przy formie powłoki `CMD node app.js`? Kto wtedy dostaje SIGTERM i czy przekaże go aplikacji?

### 3. Multi-stage: ten sam program, dwa rozmiary obrazu

W repo jest gotowy przykład .NET 10 z dwoma plikami Dockerfile: `Dockerfile` (multi-stage: SDK do budowania, sam runtime w obrazie końcowym) i `Dockerfile.single` (wszystko w jednym etapie, na obrazie SDK).

```bash
cd ../../przyklady/docker/build/3-dotnet-multistage
```

Przeczytaj oba pliki. Znajdź w `Dockerfile` etapy (`FROM … AS …`) i instrukcję `COPY --from=…`. Potem zbuduj oba:

```bash
docker build -t sample:multi .
docker build -f Dockerfile.single -t sample:single .
docker images sample
```

Uruchom wersję multi-stage:

```bash
docker run --rm -d --name sample -p 8080:8080 sample:multi
curl http://localhost:8080
docker exec sample id
docker stop sample
cd -
```

✅ `docker images sample` pokazuje dwa obrazy o wyraźnie różnym rozmiarze. Zapisz oba rozmiary.
✅ Aplikacja odpowiada na `localhost:8080`, `id` pokazuje UID inny niż 0.

Odpowiedz sobie: czego brakuje w obrazie `sample:multi`, co jest w `sample:single`? Dlaczego to dobrze z punktu widzenia bezpieczeństwa?

### 4. Tag z wersją i push do rejestru

Obraz w rejestrze ma pełną nazwę: `<REJESTR>/<nazwa>:<wersja>`, np. `<REJESTR>/node-app:1.0.0`, gdzie `<REJESTR>` to adres rejestru ECR razem z Twoją przestrzenią (karta dostępowa, punkt 1). Szczegóły w [`setup/rejestr.md`](../../setup/rejestr.md).

Najpierw zaloguj się do rejestru (karta, punkt 3; adres w `docker login` to `<REJESTR>` bez `/<login>`):

```bash
aws login --profile szkolenie
aws ecr get-login-password --profile szkolenie --region eu-central-1 | docker login --username AWS --password-stdin <konto>.dkr.ecr.eu-central-1.amazonaws.com
```

Repozytorium `<login>/node-app` powstanie samo przy pierwszym `docker push`.

**Linux, Windows, Mac Intel (amd64):**

```bash
docker tag node-app:1.0.0 <REJESTR>/node-app:1.0.0
docker push <REJESTR>/node-app:1.0.0
```

**Mac z procesorem M (arm64):** obraz zbudowany lokalnie jest arm64 i na węzłach amd64 się nie uruchomi (`exec format error`). Zbuduj go od razu dla amd64 i wypchnij jedną komendą:

```bash
docker buildx build --platform linux/amd64 -t <REJESTR>/node-app:1.0.0 --push node
```

Sprawdź, co jest w rejestrze:

```bash
docker buildx imagetools inspect <REJESTR>/node-app:1.0.0
docker buildx imagetools inspect <REJESTR>/node-app:1.0.0 --format '{{.Image.Architecture}}'
```

✅ `docker push` (albo `buildx … --push`) kończy się linią z `digest: sha256:…`.
✅ Druga komenda wypisuje `amd64` (na Macu M właśnie o to chodzi).
✅ Wklej na czacie pełną nazwę swojego obrazu.

---

## Dla chętnych

### A. Multi-stage w Go

W katalogu `go/` są `main.go` i `go.mod` (bez zależności zewnętrznych). Napisz **dwa** pliki:

- `go/Dockerfile.single`: `FROM golang:1.25`, skopiuj kod, `go build`, uruchom binarkę.
- `go/Dockerfile`: etap `build` na `golang:1.25` buduje statyczną binarkę (`CGO_ENABLED=0`), etap końcowy na `alpine:3.22` (albo `gcr.io/distroless/static-debian12:nonroot`) zawiera **tylko** binarkę i uruchamia ją jako użytkownik bez roota. Najpierw skopiuj `go.mod` (i ewentualnie `go.sum`), potem kod.

```bash
docker build -f go/Dockerfile.single -t go-app:single go
docker build -t go-app:1.0.0 go
docker images go-app
docker run --rm -d --name go-app -p 8090:8080 go-app:1.0.0
curl http://localhost:8090
docker stop go-app
```

✅ `go-app:1.0.0` ma kilkanaście MB, `go-app:single` kilkadziesiąt razy więcej (ok. 950 MB). Odpowiedź z `curl` zawiera `uid` różny od 0.

### B. Python: `ARG`, `ENV` i `USER`

W katalogu `python/` są `app.py` i `requirements.txt` (Flask). Napisz `python/Dockerfile` na `python:3.13-slim`, który:

- przyjmuje przy budowaniu argument `APP_VERSION` (domyślnie `1.0.0`) i przekazuje go do zmiennej środowiskowej `APP_VERSION`, którą czyta aplikacja,
- ustawia `APP_NAME` na `lab03`,
- instaluje zależności z `requirements.txt` bez cache pip (`pip install --no-cache-dir`), przed skopiowaniem kodu,
- tworzy użytkownika systemowego `app` i uruchamia aplikację jako on,
- uruchamia `python app.py` w formie exec.

Dodaj też `python/.dockerignore` (`__pycache__`, `*.pyc`, `.venv`, `.env`).

```bash
docker build -t py-app:1.0.0 python
docker build --build-arg APP_VERSION=2.0.0 -t py-app:2.0.0 python
docker run --rm -d --name py-app -p 5001:5000 py-app:2.0.0
curl http://localhost:5001
curl http://localhost:5001/whoami
docker stop py-app
```

✅ `/` zwraca „wersja 2.0.0”, `/whoami` pokazuje `uid` różny od 0 i `"env_USER": "(brak)"`.

Port 5001 na hoście nie jest przypadkowy: na macOS port 5000 zajmuje AirPlay Receiver.

### C. `HEALTHCHECK`

Dopisz do `node/Dockerfile` instrukcję `HEALTHCHECK`, która co 10 s odpytuje `http://localhost:3000/health`. W `node:22-alpine` nie ma `curl`, ale jest `wget` z BusyBoxa.

```bash
docker build -t node-app:1.0.2 node
docker run -d --name node-hc node-app:1.0.2
docker ps --filter name=node-hc        # po ok. 10 s: (healthy)
docker inspect -f '{{.State.Health.Status}}' node-hc
docker rm -f node-hc
```

✅ Status zmienia się ze `starting` na `healthy`.

### D. Warstwy i `apt-get` bez pytań

W nowym katalogu `warstwy/` napisz dwa pliki na `ubuntu:24.04`, które instalują `curl`, `ca-certificates` i `tzdata`:

- `Dockerfile.zle`: osobny `RUN` dla `apt-get update`, dla każdego pakietu i na końcu osobny `RUN rm -rf /var/lib/apt/lists/*`,
- `Dockerfile.dobre`: jeden `RUN` z `apt-get update && apt-get install -y --no-install-recommends … && rm -rf /var/lib/apt/lists/*`.

```bash
mkdir -p warstwy
# … napisz pliki …
docker build -f warstwy/Dockerfile.zle -t warstwy:zle warstwy
docker build -f warstwy/Dockerfile.dobre -t warstwy:dobre warstwy
docker images warstwy
docker history warstwy:zle
```

Najpierw zbuduj wersję bez żadnych zmiennych i przejrzyj log z `--progress=plain`: pakiet `tzdata` próbuje zadać pytanie o strefę czasową (`debconf: unable to initialize frontend: Dialog`, `Configuring tzdata`). W BuildKicie nie ma terminala, więc dostaje domyślną odpowiedź, ale w starszym builderze albo przy instalacji w `docker run -it` instalacja staje na `Geographic area:`. Dodaj przed instalacją `ARG DEBIAN_FRONTEND=noninteractive` i porównaj log.

✅ `warstwy:dobre` jest mniejszy. W `docker history warstwy:zle` warstwa z `rm -rf` ma 0 B: plików nie da się usunąć z warstwy, która już powstała.

Dlaczego `ARG`, a nie `ENV DEBIAN_FRONTEND=noninteractive`? Sprawdź `docker run --rm warstwy:dobre env`.

### E. Sekret w buildzie bez śladu w obrazie

Czasem build potrzebuje tokenu (prywatny rejestr npm, pip, git). Utwórz atrapę tokenu i katalog:

```bash
mkdir -p sekret
echo "changeme-token-lab03" > sekret/token.txt
```

Napisz dwa Dockerfile na `alpine:3.22`:

- `sekret/Dockerfile.arg`: token przychodzi przez `ARG TOKEN` i jest „używany” w `RUN` (wystarczy `echo "mam token o długości ${#TOKEN}"`),
- `sekret/Dockerfile`: token przychodzi przez `RUN --mount=type=secret,id=token …` i jest czytany z `/run/secrets/token`.

```bash
docker build -f sekret/Dockerfile.arg --build-arg TOKEN="$(cat sekret/token.txt)" -t sekret:arg sekret
docker build --secret id=token,src=sekret/token.txt -t sekret:mount sekret
docker history --no-trunc sekret:arg | grep changeme
docker history --no-trunc sekret:mount | grep changeme
```

✅ W historii `sekret:arg` widać token, w `sekret:mount` nie. BuildKit może też ostrzec `SecretsUsedInArgOrEnv`: to ten sam problem.

Uwaga: plik `token.txt` nie może trafić do obrazu przez `COPY`. Dopisz go do `sekret/.dockerignore`.

### F. Obraz na dwie platformy naraz

Domyślny builder Docker Desktop (sterownik `docker`) buduje wiele platform tylko z włączonym containerd image store (Settings → General → „Use containerd for pulling and storing images”). Bez tego utwórz osobny builder:

```bash
docker buildx create --name multi --driver docker-container --use
docker buildx build --platform linux/amd64,linux/arm64 -t <REJESTR>/node-app:1.0.1 --push node
docker buildx imagetools inspect <REJESTR>/node-app:1.0.1
docker buildx use desktop-linux   # powrót do domyślnego buildera (Linux: docker buildx use default)
docker buildx rm multi
```

✅ `imagetools inspect` pokazuje listę manifestów z `linux/amd64` i `linux/arm64`: ten sam tag działa na Macu M i na węzłach amd64.

### Sprzątanie

```bash
docker rm -f moja-strona node-app node-hc sample go-app py-app 2>/dev/null
docker rmi moja-strona:1.0.0 node-app:1.0.0 node-app:1.0.1 node-app:1.0.2 sample:multi sample:single go-app:single go-app:1.0.0 py-app:1.0.0 py-app:2.0.0 warstwy:zle warstwy:dobre sekret:arg sekret:mount 2>/dev/null
rm -f node/.env
```

Obraz w rejestrze zostaw: przyda się w kolejnych dniach.

---

## SUKCES

- [ ] `moja-strona:1.0.0` serwuje Twój `index.html`, a `docker history` pokazuje Twoje warstwy
- [ ] `node-app` działa jako `uid=1000(node)`, po zmianie `app.js` krok `npm ci` jest `CACHED`, a `.env` nie trafił do obrazu
- [ ] `docker images sample` pokazuje dwa obrazy o wyraźnie różnym rozmiarze i umiesz powiedzieć, skąd ta różnica
- [ ] Twój obraz jest w rejestrze jako `<REJESTR>/node-app:1.0.0` (na Macu M z platformą `linux/amd64`), a pełna nazwa jest na czacie

## Gdy coś nie działa

| Objaw | Co zrobić |
|---|---|
| `failed to read dockerfile: open Dockerfile: no such file or directory` | Plik ma inną nazwę (np. `dockerfile`, `Dockerfile.txt`) albo podałeś zły katalog kontekstu. Nazwa `Dockerfile`, albo wskaż plik `-f ścieżka/do/pliku` |
| `COPY failed: … not found` / `"/package-lock.json": not found` | Plik nie istnieje w kontekście budowania albo wyklucza go `.dockerignore`. Kontekst to ostatni argument `docker build` (tu: `node`) |
| `npm ci` kończy się `The npm ci command can only install with an existing package-lock.json` | Nie skopiowałeś `package-lock.json` przed `npm ci` (`COPY package*.json ./`) |
| `EACCES: permission denied` przy starcie Node | Pliki należą do roota, a proces działa jako `node`. Aplikacja tylko czyta pliki, więc to zwykle zapis do `/app`. Użyj `COPY --chown=node:node` albo zapisuj do `/tmp` |
| `go: cannot find main module` | Brak `go.mod` w kontekście albo `COPY` w złej kolejności. `go.mod` jest w katalogu `go/`, skopiuj go do `WORKDIR` |
| Kontener Go: `exec ./app: no such file or directory` na `alpine` | Binarka jest zlinkowana dynamicznie z glibc. Buduj z `CGO_ENABLED=0` |
| Build albo `apt-get install` w kontenerze wisi na `Geographic area:` / w logu `debconf: unable to initialize frontend` | `tzdata` (i inne pakiety) pytają o konfigurację. `ARG DEBIAN_FRONTEND=noninteractive` przed `RUN apt-get …`, w `docker exec`: `DEBIAN_FRONTEND=noninteractive apt-get install -y …` |
| `port is already allocated` | Port zajęty przez kontener z poprzedniego kroku albo labu. `docker ps`, usuń go albo zmień port hosta |
| Mac: `curl localhost:5000` zwraca `403` z nagłówkiem `AirTunes` | Port 5000 zajmuje AirPlay Receiver. Mapuj `-p 5001:5000` albo wyłącz AirPlay Receiver w Ustawieniach systemowych |
| `WARNING: The requested image's platform (linux/amd64) does not match the detected host platform (linux/arm64/v8)` | Uruchamiasz na Macu M obraz zbudowany dla amd64. Lokalnie działa w emulacji (wolniej), dla klastra to właściwa platforma |
| Pod w Kubernetesie (później): `exec format error` | Obraz jest arm64, a węzeł amd64. Zbuduj ponownie z `--platform linux/amd64` |
| `denied` / `no basic auth credentials` / `authorization token has expired` przy `docker push` | Nie jesteś zalogowany do ECR, hasło wygasło (12 h) albo nazwa obrazu nie zaczyna się od Twojego `<REJESTR>`. Powtórz logowanie z karty (punkt 3), sprawdź nazwę w [`setup/rejestr.md`](../../setup/rejestr.md) |
| `An image does not exist locally with the tag` | Najpierw `docker tag`, potem `docker push`, i ta sama nazwa w obu komendach |
| `Multi-platform build is not supported for the docker driver` | Domyślny builder nie zbuduje kilku platform naraz. Włącz containerd image store w Docker Desktop albo `docker buildx create --name multi --driver docker-container --use` (krok F). Jedna platforma (`--platform linux/amd64`) działa bez tego |
| `429 Too Many Requests` z `registry-1.docker.io` (często w builderze `docker-container`) | Limit anonimowych pobrań z Docker Hub. `docker login` (darmowe konto) i powtórz; builder `docker-container` korzysta z tego samego logowania |
| `Cannot connect to the Docker daemon` | Docker Desktop nie działa. Uruchom go i poczekaj na zielony status |
| `no space left on device` | Dysk maszyny wirtualnej Dockera jest pełny. `docker system df`, usuń swoje stare obrazy (`docker rmi …`, `docker image prune`) albo powiększ dysk w Settings → Resources |
| Windows: `docker build` nie widzi zmian w plikach / CRLF w skryptach | Edytor zapisał pliki z końcami linii CRLF. Dla `*.sh` ustaw LF |
