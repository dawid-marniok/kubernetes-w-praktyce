# ToDos — aplikacja do labów

Prosta lista zadań w trzech warstwach, plus panel do podglądu bazy. Uruchamiamy ją w dniu 1 w Docker Compose, od dnia 2 żyje na Kubernetesie (blok ToDos na koniec każdego dnia), a w dniu 5 dostaje chart Helma.

```
przeglądarka ──► web (nginx + React) ──/api──► api (Node.js + Express) ──► mongo (MongoDB)
  :3000            kontener :8080                   :3001                      :27017
                                                                     mongo-express :8081 (profil debug)
```

| Usługa | Obraz | Port w kontenerze | Port na hoście | Co robi |
|---|---|---|---|---|
| `web` | budowany z `frontend/` (finalnie `nginxinc/nginx-unprivileged:1.29-alpine`) | 8080 | 3000 | serwuje zbudowanego Reacta, a `/api/…` przekazuje do `api` |
| `api` | budowany z `backend/` (`node:22-alpine`) | 3001 | 3001 | REST API, zapisuje zadania w MongoDB |
| `mongo` | `mongo:7.0` (zmienna `MONGO_IMAGE`, patrz niżej) | 27017 | — (tylko w sieci compose) | baza, dane w wolumenie `mongodb_data` |
| `mongo-express` | `mongo-express:1.0.2-20-alpine3.19` | 8081 | 8081 | panel WWW do bazy, tylko z `--profile debug` |

## Uruchomienie

Polecenia wydajesz w katalogu `app/todos`.

```bash
docker compose up -d --build          # buduje obrazy web i api, startuje web, api, mongo
docker compose ps                     # po chwili wszystkie usługi mają status (healthy)
docker compose logs -f api            # logi API

docker compose --profile debug up -d  # dodatkowo mongo-express

docker compose down                   # zatrzymuje i usuwa kontenery (dane w wolumenie zostają)
docker compose down -v                # ... i usuwa wolumen z danymi
```

> **Dlaczego `mongo:7.0`, a nie 8.0?** MongoDB 8.x nie startuje na jądrze Linuksa 6.19–7.0.13, a takie jądro ma obecny Docker Desktop. W logach kontenera pojawia się wtedy `MongoDB cannot start: Linux kernel versions 6.19 and newer has a known incompatibility…` ([SERVER-121912](https://jira.mongodb.org/browse/SERVER-121912)). Na klastrze EKS i na starszym Docker Desktop działa 8.0: `MONGO_IMAGE=mongo:8.0 docker compose up -d` albo wpis w `.env`.

Kolejność startu pilnują healthchecki: `api` czeka, aż `mongo` będzie `healthy`, a `web` czeka na `healthy` od `api`.

### Tryb developerski: `docker compose watch`

```bash
docker compose watch
```

Compose startuje aplikację i obserwuje pliki:
- zmiana w `backend/` (np. `routes/index.js`): plik jest kopiowany do kontenera `api`, a proces się restartuje (`sync+restart`), bez przebudowy obrazu;
- zmiana w `backend/package.json` albo `package-lock.json`: obraz `api` jest przebudowywany (`rebuild`).

Zatrzymanie: `Ctrl+C`, potem `docker compose down`.

## Adresy

| Adres | Co tam jest |
|---|---|
| http://localhost:3000 | aplikacja (frontend) |
| http://localhost:3000/api/todos | API przez nginx we froncie, tak samo woła je przeglądarka |
| http://localhost:3001/api/todos | API bezpośrednio (podgląd z hosta) |
| http://localhost:3001/api/health | stan API: `200 {"status":"ok","db":"connected"}` albo `503`, gdy nie ma bazy |
| http://localhost:8081 | mongo-express (login `admin`, hasło `changeme-panel`), tylko z `--profile debug` |

## API

Wszystkie ścieżki zaczynają się od `/api` (`backend/routes/`).

| Metoda i ścieżka | Opis | Kto używa |
|---|---|---|
| `GET /api/health` | 200 gdy jest połączenie z MongoDB, w przeciwnym razie 503 | healthcheck w compose, sondy w Kubernetesie |
| `GET /api/todos` | lista **nieukończonych** zadań (`is_complete: false`) | frontend (`home.jsx`) |
| `POST /api/todos` | nowe zadanie: `{"title","description","due_date"}` | frontend (formularz `todo-form.jsx`) |
| `PATCH /api/todos/:id` | zmiana pól, np. `{"is_complete": true}` | frontend (checkbox: oznacza zadanie jako zrobione, a ono znika z listy) |
| `GET /api/todos/:id` | jedno zadanie (404, gdy go nie ma) | — |
| `DELETE /api/todos/:id` | usunięcie zadania (204) | — |
| `GET /api` | napis `main page!` | — |

`frontend/src/components/login.jsx` to pusta zaślepka bez podpiętej logiki, aplikacja nie ma logowania.

Przykłady z terminala:

```bash
curl -s -X POST localhost:3000/api/todos \
  -H 'Content-Type: application/json' \
  -d '{"title":"Kupić mleko","description":"2 litry","due_date":"2026-12-01"}'
curl -s localhost:3000/api/todos
curl -s localhost:3001/api/health
```

## Konfiguracja (zmienne środowiskowe)

| Zmienna | Gdzie | Domyślnie | Znaczenie |
|---|---|---|---|
| `MONGODB_URI` | api | `mongodb://mongo:27017/todos` (w compose z loginem i hasłem) | adres bazy |
| `PORT` | api | `3001` | port API |
| `API_HOST`, `API_PORT` | web | `api`, `3001` | dokąd nginx przekazuje `/api/` (szablon `frontend/nginx/default.conf.template`) |
| `MONGO_USER`, `MONGO_PASSWORD` | plik `.env` obok `compose.yaml` | `root`, `changeme-mongo` | użytkownik root bazy (wzór w `.env.example`) |
| `MONGO_IMAGE` | plik `.env` | `mongo:7.0` | obraz bazy |

Frontend woła API ścieżką względną `/api`, więc nie ma w nim żadnego `localhost:3001`. Nginx w kontenerze `web` przekazuje `/api/` do `http://${API_HOST}:${API_PORT}`. W Kubernetesie wystarczy więc nazwać Service backendu `api` albo ustawić `API_HOST`.

Hasła w repo to atrapy. Własne wpisz do `.env` (`cp .env.example .env`), bo ten plik nie trafia do gita. `mongo-init.js` uruchamia się tylko przy pierwszym starcie, na pustym wolumenie: przy zmianie hasła na istniejącym wolumenie zrób `docker compose down -v`.

## Struktura

```
todos/
├── compose.yaml            # web, api, mongo, mongo-express (profil debug)
├── .env.example            # wzór pliku .env z hasłem do bazy
├── mongo-init.js           # tworzy kolekcję todos przy pierwszym starcie bazy
├── backend/                # API: Node.js 22 + Express 5 + Mongoose 8
│   ├── Dockerfile          # node:22-alpine, npm ci, USER node
│   ├── server.js           # start serwera, łączenie z MongoDB z ponawianiem
│   ├── routes/             # index.js (/api, /api/health), todos.js (/api/todos)
│   └── models/todo.js      # schemat zadania
└── frontend/               # React 18 + Vite + reactstrap (Bootstrap 5) + axios
    ├── Dockerfile          # multi-stage: build na node:22-alpine, serwowanie przez nginx-unprivileged (port 8080)
    ├── nginx/default.conf.template   # proxy /api/ + fallback SPA
    ├── index.html, vite.config.js
    └── src/                # App.jsx, components/ (home, todo-form, login)
```

Frontend bez Dockera: `cd frontend && npm install && npm run dev` (http://localhost:3000, `/api` idzie do `localhost:3001`, więc API musi działać, np. z compose).
