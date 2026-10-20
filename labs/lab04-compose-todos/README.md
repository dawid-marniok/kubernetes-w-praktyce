# lab04 — ToDos w Compose: złóż, zabezpiecz, wypchnij

**Cel:** opisać aplikację ToDos (frontend, API, baza, panel) w jednym `compose.yaml` tak, żeby dane przetrwały `down`, usługi startowały we właściwej kolejności, a obrazy trafiły do rejestru.

Podstawa: kroki 1–6, reszta dla chętnych.

**Po labie masz:** działającą aplikację ToDos pod `localhost:3000`, plik `compose.yaml`, który rozumiesz linijka po linijce, i obrazy `todos-web:1.0.0` oraz `todos-api:1.0.0` w swoim rejestrze. Tych obrazów użyjesz już jutro wieczorem: od dnia 2 ToDos żyje w Twoim namespace na klastrze i co dzień dokładasz do niego to, czego się nauczysz.

Aplikację ToDos opisuje [`app/todos/README.md`](../../app/todos/README.md): `web` to nginx z aplikacją React, który przekazuje `/api` do usługi `api`; `api` to Node.js + Express; dane trzyma MongoDB.

## Zanim zaczniesz

- Docker Desktop działa (`docker version` pokazuje Client i Server), repo kursantów po `git pull`
- Wolne porty 3000 i 8081 na laptopie (`docker ps` — usuń kontenery z poprzednich labów)
- Rejestr i logowanie z lab03 ([`setup/rejestr.md`](../../setup/rejestr.md)); `<REJESTR>` to adres z karty dostępowej (punkt 1). Hasło Dockera do ECR jest ważne 12 h, rano zaloguj się ponownie
- Pracujesz w katalogu labu:
  ```bash
  cd labs/lab04-compose-todos
  ```
  Plik `compose.yaml` w tym katalogu to **plik startowy**: działa, ale ma kilka braków, które naprawisz w krokach 3–5. Ścieżki `build:` wskazują na kod w `../../app/todos`.

## Poziom podstawowy

### 1. Uruchom aplikację

```bash
docker compose up -d --build
docker compose ps
docker compose logs api
```

Pierwszy build trwa kilka minut (`npm ci` dla frontendu i backendu), kolejne idą z cache.

✅ `docker compose ps` pokazuje trzy usługi `web`, `api`, `mongo` w stanie `Up`. W logach `api` jest `Połączono z MongoDB` (czasem poprzedzone `Brak połączenia z MongoDB … ponawiam za 5 s`).

Otwórz `http://localhost:3000` i dodaj dwa zadania. To samo z terminala:

```bash
curl -s -X POST -H 'Content-Type: application/json' -d '{"title":"kupić mleko"}' localhost:3000/api/todos
curl -s localhost:3000/api/todos
```

Sprawdź, co się dzieje, gdy baza zniknie na chwilę:

```bash
docker compose stop mongo
curl -s localhost:3000/api/todos; echo
docker compose start mongo
docker compose logs api | tail -n 5
```

✅ Bez bazy `curl` po kilku sekundach zwraca błąd, a po `start` api znów odpowiada listą zadań. Pytanie do siebie: kto tu chroni aplikację, Compose czy kod `api`? (Odpowiedź w kroku 4).

### 2. Zajrzyj do środka

```bash
docker compose exec api id
docker compose exec web id
docker compose exec web grep proxy_pass /etc/nginx/conf.d/default.conf
docker network ls | grep lab04
```

✅ `api` działa jako `uid=1000(node)`, `web` jako `uid=101(nginx)` — żaden kontener nie jest rootem. nginx przekazuje `/api` pod `http://api:3001`: `api` to **nazwa usługi**, którą rozwiązuje DNS w sieci `lab04_default`, utworzonej przez Compose.

### 3. Dane, które przeżyją `down`

Zatrzymaj i usuń projekt, potem uruchom go ponownie:

```bash
docker compose down
docker compose up -d
curl -s localhost:3000/api/todos
```

✅ Lista jest pusta: `[]`. Mongo trzymało dane w anonimowym wolumenie, a nowy kontener dostał nowy.

Popraw `compose.yaml`: w usłudze `mongo` zamontuj nazwany wolumen `mongodb_data` w katalogu `/data/db` i zadeklaruj go na końcu pliku w sekcji `volumes:` najwyższego poziomu. Potem:

```bash
docker compose up -d
# dodaj zadanie w przeglądarce albo curl -X POST jak w kroku 1
docker compose down
docker compose up -d
curl -s localhost:3000/api/todos
docker volume ls | grep lab04
```

✅ Zadanie jest na liście po `down` i `up`, `docker volume ls` pokazuje `lab04_mongodb_data`.

### 4. Kolejność startu: healthcheck i `service_healthy`

`depends_on: [mongo]` czeka tylko, aż kontener `mongo` **powstanie**, a nie aż baza przyjmuje połączenia. Przed wolną bazą chroni nas tylko pętla ponawiania w kodzie `api` (krok 1); tu Compose dostaje informację o gotowości bazy.

Dopisz:

1. W `mongo` — `healthcheck` z testem `["CMD", "mongosh", "--quiet", "--eval", "db.adminCommand('ping')"]`, `interval: 10s`, `timeout: 5s`, `retries: 5`, `start_period: 20s`.
2. W `api` — `depends_on` w formie długiej z `condition: service_healthy` dla `mongo`, `restart: unless-stopped` oraz własny `healthcheck`: `["CMD", "wget", "-q", "-O", "/dev/null", "http://127.0.0.1:3001/api/health"]` z `interval: 10s`, `timeout: 3s`, `retries: 3`, `start_period: 10s` (endpoint zwraca 200, gdy API ma połączenie z bazą). Bez `interval` pierwszy test odbywa się po 30 s i `up` wygląda na zawieszone.
3. W `web` — `depends_on` z `condition: service_healthy` dla `api`.

```bash
docker compose down
docker compose up -d
docker compose ps
docker compose logs api | head -3
```

✅ Podczas `up` widać `Waiting` i `Healthy` przy `mongo` i `api`. `docker compose ps` pokazuje `(healthy)` przy `mongo` i `api`. W logach `api` od razu `Połączono z MongoDB`, bez ponawiania.

Składnię sprawdzisz komendą `docker compose config` — wypisze plik po scaleniu albo pokaże linię z błędem.

### 5. Panel bazy tylko na żądanie: profil `debug`

Dodaj usługę `mongo-express`:

- obraz `mongo-express:1.0.2-20-alpine3.19`, port `8081:8081`
- `profiles: ["debug"]`
- zmienne: `ME_CONFIG_MONGODB_URL: mongodb://root:changeme-mongo@mongo:27017/?authSource=admin`, `ME_CONFIG_BASICAUTH: "true"`, `ME_CONFIG_BASICAUTH_USERNAME: admin`, `ME_CONFIG_BASICAUTH_PASSWORD: changeme-panel`
- `depends_on` na zdrowe `mongo`

```bash
docker compose up -d
docker compose ps
docker compose --profile debug up -d
docker compose --profile debug ps
```

✅ Zwykłe `up` nie uruchamia panelu. Z `--profile debug` pojawia się `mongo-express`, a `http://localhost:8081` (login `admin` / `changeme-panel`) pokazuje bazę `todos` i kolekcję `todos` z Twoimi zadaniami.

### 6. Bezpieczeństwo obrazów i push do rejestru

Sprawdź, co jest w obrazach, które zbudował Compose:

```bash
docker images | grep lab04
docker inspect lab04-api --format 'USER={{.Config.User}}'
docker inspect lab04-web --format 'USER={{.Config.User}}'
```

✅ Obrazy mają ustawionego użytkownika (`node`, `101`).

Skan lokalny (jeśli masz narzędzie): `trivy image --severity HIGH,CRITICAL lab04-api` albo `docker scout quickview lab04-api` (wymaga `docker login` do Docker Hub). Bez narzędzi skan zrobi za Ciebie ECR przy pushu (niżej).

Otaguj i wypchnij oba obrazy z wersją:

```bash
docker tag lab04-api <REJESTR>/todos-api:1.0.0
docker tag lab04-web <REJESTR>/todos-web:1.0.0
docker push <REJESTR>/todos-api:1.0.0
docker push <REJESTR>/todos-web:1.0.0
```

**Mac z procesorem M** (klaster w dniach 2–5 ma węzły amd64) — zamiast tag + push zbuduj od razu na właściwą platformę:

```bash
docker buildx build --platform linux/amd64 -t <REJESTR>/todos-api:1.0.0 --push ../../app/todos/backend
docker buildx build --platform linux/amd64 -t <REJESTR>/todos-web:1.0.0 --push ../../app/todos/frontend
```

Skan przy pushu (ECR robi go sam, wynik po ok. minucie; to samo w konsoli AWS → ECR → repozytorium → obraz):

```bash
aws ecr describe-image-scan-findings --profile szkolenie --region eu-central-1 --repository-name <login>/todos-api --image-id imageTag=1.0.0 --query 'imageScanFindings.findingSeverityCounts'
```

✅ Oba obrazy są w rejestrze z tagiem `1.0.0`, skan pokazuje liczby podatności według ważności. Wklej na czat pełną nazwę `todos-api`.

### Sprzątanie

```bash
docker compose --profile debug down          # dane zostają w wolumenie
# docker compose --profile debug down -v     # tylko gdy chcesz skasować też dane
```

## Dla chętnych

### A. `docker compose watch`: kod z edytora od razu w kontenerze

Pełny plik aplikacji `app/todos/compose.yaml` ma w usłudze `api` sekcję `develop.watch`. Uruchom go:

```bash
cd ../../app/todos
docker compose up -d --build
docker compose watch
```

W drugim terminalu zmień tekst `main page!` w `backend/routes/index.js` i zapisz. Po kilku sekundach:

```bash
curl -s localhost:3000/api/
```

✅ W terminalu z `watch` widać synchronizację i restart `api`, a `curl` zwraca nowy tekst. Zastanów się: którą akcję (`sync+restart` czy `rebuild`) wywoła zmiana w `package.json`? Na koniec przywróć tekst, `Ctrl+C` i `docker compose down`.

### B. Hasło poza plikiem `compose.yaml`

Zamień w swoim pliku wpisane na sztywno `changeme-mongo` na `${MONGO_PASSWORD:-changeme-mongo}` (w `mongo`, `api` i `mongo-express`). Utwórz obok plik `.env` z linią `MONGO_PASSWORD=…` i sprawdź `docker compose config | grep MONGO`.

✅ `config` pokazuje wartość z `.env`. Pamiętaj: hasło jest użyte przy **pierwszej** inicjalizacji bazy — przy istniejącym wolumenie zmiana wymaga `down -v`.

### C. Minimum uprawnień dla `api`

Dopisz w `api`: `read_only: true`, `tmpfs: [/tmp]`, `cap_drop: [ALL]`, `security_opt: ["no-new-privileges:true"]`, `mem_limit: 256m`. `docker compose up -d`, potem:

```bash
docker inspect lab04-api-1 --format 'ro={{.HostConfig.ReadonlyRootfs}} cap={{.HostConfig.CapDrop}} mem={{.HostConfig.Memory}}'
```

✅ `api` nadal jest `healthy`, a `inspect` pokazuje `ro=true cap=[ALL]`. Spróbuj tego samego dla `web` i wyjaśnij, czemu nginx wymaga dodatkowych `tmpfs`.

### D. Skalowanie za nginx

W `przyklady/docker/compose/4-nginx-skalowanie` uruchom `docker compose up -d --build --scale web=3` i kilka razy `curl -s localhost:8080/whoami`. Każda odpowiedź może przyjść z innego kontenera, a nginx zna tylko nazwę `web`.

## SUKCES

- [ ] `localhost:3000` pokazuje ToDos, a zadanie przeżywa `docker compose down` i `up` (wolumen `lab04_mongodb_data`)
- [ ] `docker compose ps` pokazuje `(healthy)` przy `mongo` i `api`, a `api` nie ponawia połączenia przy starcie
- [ ] `mongo-express` startuje tylko z `--profile debug`
- [ ] `<REJESTR>/todos-api:1.0.0` i `<REJESTR>/todos-web:1.0.0` są w rejestrze (na Macu M w wersji `linux/amd64`)

## Gdy coś nie działa

| Objaw | Co zrobić |
|---|---|
| `port is already allocated` na 3000 albo 8081 | Port zajmuje kontener z poprzedniego labu albo inny program. `docker ps`, usuń go albo zmień lewą stronę mapowania, np. `"3005:8080"` |
| `docker compose ps` pokazuje `api` jako `unhealthy` | `docker compose logs api` — zwykle brak połączenia z bazą (literówka w `MONGODB_URI`, inne hasło niż w `mongo`) |
| Po zmianie hasła `api` nie łączy się z bazą (`Authentication failed`) | Mongo ustawia hasło tylko przy pierwszym starcie na pustym wolumenie. `docker compose down -v` i `up` (dane znikną) |
| `dependency failed to start: container lab04-mongo-1 is unhealthy` | Test healthchecka jest błędny (literówka w `mongosh`/`ping`) albo za krótki `start_period`. `docker inspect lab04-mongo-1 --format '{{json .State.Health}}'` pokaże wynik testu |
| `yaml: line …: did not find expected key` | Wcięcia w YAML: tylko spacje, po dwie na poziom. `docker compose config` wskaże linię |
| `mongo` na `mongo:8.0` kończy się `MongoDB cannot start: Linux kernel versions 6.19 and newer…` | Aktualne jądro Docker Desktop nie jest wspierane przez MongoDB 8.x. Zostań przy `mongo:7.0` |
| Strona `localhost:3000` działa, ale dodawanie zadań zwraca 502 | `web` nie widzi `api`: usługa `api` nie działa albo ma inną nazwę. Nazwa usługi musi być `api` |
| `trivy`: `Cannot connect to the Docker daemon` na Macu | Trivy szuka gniazda w `/var/run/docker.sock`. `export DOCKER_HOST=$(docker context inspect --format '{{.Endpoints.docker.Host}}')` albo `docker scout quickview` |
| `denied` / `no basic auth credentials` / `authorization token has expired` przy `docker push` | Zaloguj się ponownie do ECR (karta, punkty 3–4; hasło ważne 12 h), sprawdź nazwę (`<REJESTR>` z karty) |
| `ScanNotFoundException` / brak wyników skanu | Skan jeszcze trwa: odczekaj minutę i powtórz |
| `toomanyrequests` przy pobieraniu obrazów | Limit anonimowych pobrań z Docker Hub: `docker login` darmowym kontem |
| `no space left on device` | `docker system df`; usuń swoje stare obrazy (`docker image prune`) albo powiększ dysk w Settings → Resources |
