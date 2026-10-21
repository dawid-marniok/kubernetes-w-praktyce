# Przykłady: Docker Compose

**Cel:** uruchomić kilka kontenerów jednym plikiem: sieć, wolumeny, kolejność startu z healthcheckami i skalowanie usługi.

**Gdzie:** lokalnie, Docker Desktop. Komendy wydajesz w katalogu danego przykładu (`cd przyklady/docker/compose/<katalog>`). Każdy katalog z własnym `README.md` ma tam kroki i oczekiwane wyniki.

| Katalog | Co pokazuje | Start | Adres |
|---|---|---|---|
| `1-nginx/` | jedna usługa, bind mount, healthcheck; `compose.advanced.yaml`: sieci, wolumen nazwany, limity, `container_name` | `docker compose up -d` | http://localhost:8888 (advanced: 8889) |
| `3-shoppinglist/` | aplikacja + baza: `build`, `depends_on` z `service_healthy`, wolumen na dane, profil `debug` z pgAdminem | `docker compose up -d --build` | http://localhost:5001/items |
| `4-nginx-skalowanie/` | `--scale web=3` za nginx jako load balancerem | `docker compose up -d --build --scale web=3` | http://localhost:8080/whoami |
| `../../../app/todos/` | aplikacja ToDos z labu (web + api + mongo + mongo-express, `docker compose watch`) | `docker compose up -d --build` | http://localhost:3000 |

Numer 2 jest wolny: stary przykład ELK (Elasticsearch + Kibana 7.14) nie wszedł do repo. Obecne wersje 8.x/9.x mają domyślnie włączone zabezpieczenia, a oba obrazy zajmują razem ok. 2,5 GB i potrzebują 2–4 GB RAM, co na laptopie z Docker Desktop jest uciążliwe. Na tym przykładzie nie uczymy niczego, czego nie pokazują pozostałe.

## 1-nginx krok po kroku

```bash
cd 1-nginx
docker compose up -d
docker compose ps                    # nginx: Up … (healthy) po ok. 10 s
curl localhost:8888                  # strona z html/index.html
```
Zmień coś w `html/index.html` i odśwież: zmianę widać od razu (bind mount, bez przebudowy). Wariant z sieciami, wolumenem i limitami: `docker compose -f compose.advanced.yaml up -d` → http://localhost:8889.

Sprzątanie: `docker compose down` (i `docker compose -f compose.advanced.yaml down -v`).

## Najczęstsze polecenia

```bash
docker compose up -d                 # start w tle (plik compose.yaml z bieżącego katalogu)
docker compose up -d --build         # przebuduj obrazy z sekcji build: przed startem
docker compose ps                    # stan usług (w tym healthy/unhealthy)
docker compose logs -f web           # logi usługi
docker compose exec web sh           # powłoka w działającym kontenerze
docker compose config                # wynikowa konfiguracja (po podstawieniu zmiennych), wykrywa błędy
docker compose --profile debug up -d # dodatkowo usługi z profiles: ["debug"]
docker compose -f compose.advanced.yaml up -d   # inny plik
docker compose -p moj-projekt up -d  # inna nazwa projektu (prefiks kontenerów, sieci, wolumenów)
docker compose down                  # usuń kontenery i sieć
docker compose down -v               # ... i wolumeny (dane!)
```

Pliki nazywają się `compose.yaml` i nie mają pola `version:`. Obecny Docker Compose (v2, polecenie `docker compose` ze spacją) go nie potrzebuje i ostrzega, gdy je widzi.
