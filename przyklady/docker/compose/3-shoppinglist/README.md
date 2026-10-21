# Lista zakupów: Flask + PostgreSQL 18 (+ pgAdmin)

**Cel:** aplikacja z bazą w Compose: budowanie obrazu, `depends_on` z healthcheckiem, dane w wolumenie, profil `debug`.

**Gdzie:** lokalnie, Docker Desktop. Komendy wydajesz w tym katalogu (`cd przyklady/docker/compose/3-shoppinglist`).

| Usługa | Obraz | Port na hoście | Uwagi |
|---|---|---|---|
| `web` | budowany z `app/` (`python:3.13-slim`) | 5001 → 5000 | REST API, healthcheck na `/health` |
| `db` | `postgres:18` | — | dane w wolumenie `postgres_data` |
| `pgadmin` | `dpage/pgadmin4:9.18` | 5050 → 80 | tylko z `--profile debug` |

## Uruchomienie

```bash
docker compose up -d --build
docker compose ps                        # web i db: (healthy)

curl -s -X POST localhost:5001/items \
  -H "Content-Type: application/json" \
  -d '{"name": "Mleko", "quantity": 2, "unit": "l", "price": 4.99}'
curl -s localhost:5001/items
curl -s -X PUT localhost:5001/items/1 -H "Content-Type: application/json" -d '{"bought": true}'
curl -s -X DELETE localhost:5001/items/1 -o /dev/null -w '%{http_code}\n'   # 204
curl -s localhost:5001/health
```

## Dane przeżywają restart

```bash
docker compose down                      # kontenery usunięte, wolumen zostaje
docker compose up -d
curl -s localhost:5001/items             # pozycje nadal są
docker compose down -v                   # -v usuwa też wolumen, dane znikają
```

**PostgreSQL 18:** obraz trzyma dane w `/var/lib/postgresql/18/docker` i wolumen montujemy na `/var/lib/postgresql`, a nie na `.../data` jak w wersjach do 17. Stary sposób montowania kończy się błędem przy starcie kontenera.

## pgAdmin

```bash
docker compose --profile debug up -d
```

http://localhost:5050, login `admin@example.com` / `changeme-pgadmin`. Serwer dodajesz ręcznie: host `db`, port `5432`, użytkownik `shop`, hasło `changeme-postgres`. Host to nazwa usługi, bo pgAdmin działa w tej samej sieci compose.

Hasła w `compose.yaml` to atrapy na potrzeby zajęć.

## Sprzątanie

```bash
docker compose --profile debug down -v   # kontenery, sieć i wolumen z danymi
```

## Endpointy

| Metoda i ścieżka | Opis |
|---|---|
| `GET /items` | lista pozycji |
| `POST /items` | nowa pozycja: `name` (wymagane), `quantity`, `unit`, `price` |
| `PUT /items/<id>` | zmiana pól (`name`, `quantity`, `unit`, `bought`, `price`) |
| `DELETE /items/<id>` | usunięcie |
| `GET /health` | 200, gdy jest połączenie z bazą, inaczej 503 |
