# Skalowanie usługi za nginx

**Cel:** uruchomić usługę w kilku replikach i rozdzielić między nie ruch przez nginx; zmieniać liczbę replik w locie.

**Gdzie:** lokalnie, Docker Desktop. Komendy wydajesz w tym katalogu (`cd przyklady/docker/compose/4-nginx-skalowanie`).

Ta sama lista zakupów co w `3-shoppinglist`, ale usługa `web` działa w kilku replikach, a ruch rozdziela między nie nginx.

```
curl ──► nginx :8080 ──► web (replika 1) ┐
                    ├──► web (replika 2) ├──► db (PostgreSQL 18)
                    └──► web (replika 3) ┘
```

| Usługa | Obraz | Port na hoście | Uwagi |
|---|---|---|---|
| `nginx` | `nginx:1.29-alpine` | 8080 → 80 | load balancer, konfiguracja `nginx/nginx.conf` |
| `web` | budowany z `app/` (`python:3.13-slim`) | — (tylko `expose: 5000`) | Flask, `/whoami` zwraca nazwę kontenera |
| `db` | `postgres:18` | — | wolumen `postgres_data` |
| `pgadmin` | `dpage/pgadmin4:9.18` | 5050 → 80 | tylko z `--profile debug` |

## Demo

```bash
docker compose up -d --build --scale web=3
docker compose ps                        # web-1, web-2, web-3, nginx, db

for i in 1 2 3 4 5 6; do curl -s localhost:8080/whoami; done
```

Wynik z próby (nazwy to ID kontenerów, u Ciebie będą inne). Kolejne żądania trafiają po kolei do trzech replik:

```
f2ca507741c4
05ec81e6047f
2130b268c374
f2ca507741c4
05ec81e6047f
2130b268c374
```

Skąd wiadomo, kto odpowiedział: nagłówek `X-Served-By` ustawia aplikacja, a `X-Upstream-Addr` dokłada nginx (adres IP repliki).

```bash
curl -sI localhost:8080/whoami | grep -i x-
# X-Served-By: f2ca507741c4
# X-Upstream-Addr: 172.23.0.3:5000
```

Zmiana liczby replik w locie, bez restartu nginx:

```bash
docker compose up -d --scale web=5
for i in $(seq 1 10); do curl -s localhost:8080/whoami; done | sort | uniq -c
#    2 05ec81e6047f
#    2 2130b268c374
#    2 6c737d54e6a3
#    2 debda8b318c1
#    2 f2ca507741c4

docker compose up -d --scale web=2       # po kilku sekundach ruch idzie już tylko do 2 replik
```

API działa jak w `3-shoppinglist`, tylko przez nginx: `curl -s localhost:8080/items`. Wszystkie repliki korzystają z tej samej bazy, więc każda widzi te same dane.

Sprzątanie: `docker compose down -v`.

## Jak to działa

- `web` nie ma `ports:`, tylko `expose:`. Gdyby repliki publikowały port hosta, druga i trzecia nie wystartowałyby („port is already allocated”). Z tego samego powodu usługa skalowana nie może mieć `container_name`.
- W sieci compose nazwa `web` rozwiązuje się przez wbudowany DNS Dockera (`127.0.0.11`) na adresy **wszystkich** replik.
- `nginx.conf`:
  ```nginx
  resolver 127.0.0.11 valid=5s ipv6=off;
  upstream web_servers {
      zone web_servers 64k;
      server web:5000 resolve;
  }
  ```
  Parametr `resolve` (otwarty nginx od wersji 1.27.3) każe co `valid=5s` pytać DNS o aktualną listę adresów, dlatego nowe repliki wchodzą do puli bez restartu. Bez `resolve` (samo `server web:5000;`) nginx rozwiązuje nazwę **raz, przy starcie**. Działałoby to dla stałej liczby replik, ale po każdym `--scale` trzeba by zrobić `docker compose restart nginx`.
- `nginx` ma `depends_on: web: condition: service_healthy`, a `web` ma `depends_on: db: condition: service_healthy`. Kolejność startu wyznaczają healthchecki, a nie zwykłe „kontener wystartował”. Healthcheck `web` korzysta z samego Pythona (`urllib`), bo obraz `python:3.13-slim` nie ma `curl`.
- Domyślny algorytm to round robin. Inne (np. `least_conn;`) wpisuje się w bloku `upstream`.

W Kubernetesie to samo robią Deployment z `replicas: 3` i Service, a nginx do rozdzielania ruchu nie jest już potrzebny.
