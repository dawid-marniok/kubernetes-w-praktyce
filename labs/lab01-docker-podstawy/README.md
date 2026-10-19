# lab01 — Pierwsze kontenery na Twoim laptopie

**Cel:** uruchomić, obejrzeć, zatrzymać i usunąć kontener; wystawić port, przekazać konfigurację przez zmienne środowiskowe i zachować plik w wolumenie.

**Czas:** ~30 min (kroki 1–7). Kroki „dla chętnych” robisz, jeśli skończysz wcześniej.

**Po labie masz:** stronę nginx na `http://localhost:8080`, bazę PostgreSQL skonfigurowaną zmiennymi z pliku i plik, który przeżył usunięcie kontenera, bo leżał w wolumenie.

## Zanim zaczniesz

- Docker Desktop (Mac, Windows) albo Docker Engine (Linux) działa: [`setup/docker-desktop.md`](../../setup/docker-desktop.md).
- Terminal otwarty w katalogu tego labu (są tu pliki `db.env` i `app.env`):
  ```bash
  cd labs/lab01-docker-podstawy
  ```
- Windows: komendy działają w PowerShellu i w Git Bash. W PowerShellu zamiast `curl` pisz `curl.exe` albo otwórz adres w przeglądarce.
- Wszystkie obrazy mają przypięty tag (`nginx:1.29`, `postgres:18`). Tag `latest` w labach nie występuje (wyjątek: testowy `hello-world`): za tydzień może oznaczać inny obraz.

Komendy wpisuj po kolei. Gdy coś pójdzie inaczej niż w opisie, zajrzyj do tabeli [Gdy coś nie działa](#gdy-coś-nie-działa).

---

## Poziom podstawowy

### 1. Czy Docker działa

```bash
docker version
docker run hello-world
docker ps
docker ps -a
```

✅ `docker version` pokazuje dwie sekcje: **Client** i **Server**. Brak sekcji Server oznacza, że demon (Docker Desktop) nie działa.
✅ `hello-world` wypisuje „Hello from Docker!”. Za pierwszym razem zobaczysz też `Unable to find image … Pulling from library/hello-world`.
✅ `docker ps` nie pokazuje kontenera `hello-world`, a `docker ps -a` pokazuje go ze statusem `Exited (0)`.

Usuń go. Nie nadałeś mu nazwy, więc użyj ID albo losowej nazwy z ostatniej kolumny `docker ps -a`:

```bash
docker rm <ID albo nazwa>
```

Zapisz odpowiedź (przyda się na omówieniu): dlaczego kontener `hello-world` sam się zatrzymał?

### 2. Kontener interaktywny

```bash
docker run -it --name ubuntu-test ubuntu:24.04 bash
```

Jesteś w kontenerze (znak zachęty się zmienił). Wykonaj:

```bash
whoami
cat /etc/os-release
ls -la /
exit
```

Po `exit` jesteś z powrotem na hoście.

```bash
docker ps -a --filter name=ubuntu-test
docker start -ai ubuntu-test     # wracasz do tego samego kontenera; wyjdź przez exit
docker rm ubuntu-test
```

Kontenery „na jeden raz” uruchamiaj z `--rm`, wtedy po wyjściu same znikają:

```bash
docker run --rm ubuntu:24.04 cat /etc/os-release
docker ps -a --filter ancestor=ubuntu:24.04
```

✅ `whoami` → `root`, `/etc/os-release` → Ubuntu 24.04.
✅ Po `exit` kontener ma status `Exited (0)`, a po `docker run --rm` nie zostaje po nim ślad w `docker ps -a`.

### 3. Serwer WWW w tle i cykl życia kontenera

```bash
docker run -d --name web -p 8080:80 nginx:1.29
docker ps
```

Otwórz `http://localhost:8080` w przeglądarce albo:

```bash
curl http://localhost:8080
```

Teraz obejrzyj kontener z każdej strony:

```bash
docker logs web                                  # widać Twoje żądanie GET /
docker exec web nginx -v                         # polecenie w działającym kontenerze
docker exec -it web bash                         # powłoka w środku; wyjdź przez exit
docker inspect -f '{{.State.Status}}' web
docker inspect -f '{{.NetworkSettings.Ports}}' web
docker port web
```

Przejdź przez cykl życia:

```bash
docker stop web
docker ps -a --filter name=web
docker start web
docker rm web            # co się stanie?
```

Kontenera `web` na razie nie usuwaj (jeśli udało Ci się go usunąć, uruchom go jeszcze raz pierwszą komendą z tego kroku). Przyda się w kroku 4.

✅ Strona „Welcome to nginx!” pod `localhost:8080`.
✅ `docker logs web` pokazuje linię z `"GET / HTTP/1.1" 200`.
✅ Po `docker stop` status to `Exited (0)`, po `docker start` znowu `Up`.
✅ `docker rm web` na działającym kontenerze kończy się błędem. Znajdź w komunikacie, co proponuje Docker.

### 4. Konflikt portu na hoście

Kontener `web` zajmuje port **8080 na Twoim laptopie**. Uruchom drugi nginx z tym samym mapowaniem:

```bash
docker run -d --name web2 -p 8080:80 nginx:1.29
docker ps -a --filter name=web2
```

✅ `docker run` kończy się błędem `port is already allocated` (albo `address already in use`).
✅ Kontener `web2` mimo to istnieje, ze statusem `Created`: Docker go utworzył, ale nie uruchomił.

Usuń `web2` i uruchom go na innym porcie hosta:

```bash
docker rm web2
docker run -d --name web2 -p 8081:80 nginx:1.29
curl http://localhost:8081
```

✅ Oba kontenery działają: `web` na `localhost:8080`, `web2` na `localhost:8081`.

Odpowiedz sobie: oba nginxy słuchają w środku na porcie 80. Dlaczego to nie przeszkadza, a przeszkadzał ten sam port 8080?

Posprzątaj: `docker rm -f web2`.

### 5. Konfiguracja przez zmienne środowiskowe

Obraz `postgres:18` wymaga hasła superużytkownika. Zobacz najpierw, co się dzieje bez niego:

```bash
docker run -d --name db postgres:18
docker ps -a --filter name=db
docker logs db
```

✅ Kontener ma status `Exited (1)`, a w logach jest wyjaśnienie, której zmiennej brakuje.

Usuń go i uruchom ze zmiennymi z pliku `db.env` (zajrzyj do niego). Flaga `-v` przy `docker rm` usuwa też anonimowy wolumen, który obraz `postgres` tworzy dla katalogu z danymi (zobaczysz go w `docker volume ls` jako długi hash):

```bash
docker rm -v db
docker run -d --name db --env-file db.env postgres:18
docker logs -f db        # czekaj na „database system is ready to accept connections”, potem Ctrl+C
```

Sprawdź, że baza `sklep` i użytkownik `app` powstały:

```bash
docker exec db psql -U app -d sklep -c '\l'
```

Gdzie widać te zmienne?

```bash
docker exec db env | grep POSTGRES
docker inspect -f '{{json .Config.Env}}' db
```

✅ `psql` wypisuje listę baz z `sklep`, właścicielem jest `app`.
✅ Hasło `changeme-lab01` widać zarówno w `env`, jak i w `docker inspect`. Zastanów się, kto na Twojej maszynie może wykonać `docker inspect`.

Na koniec `-e` i `--env-file` razem, na małym obrazie `busybox`:

```bash
docker run --rm --env-file app.env busybox:1.37 env
docker run --rm --env-file app.env -e LOG_LEVEL=debug -e WERSJA=1.0.0 busybox:1.37 env
```

✅ Druga komenda pokazuje `WERSJA=1.0.0`, a `LOG_LEVEL` ma jedną z dwóch wartości. Zapisz którą.

Kontener `db` usuń razem z jego anonimowym wolumenem: `docker rm -f -v db`.

### 6. Pierwszy wolumen: plik, który przeżywa kontener

```bash
docker volume create strona
docker run -d --name web-v -p 8082:80 -v strona:/usr/share/nginx/html nginx:1.29
docker exec web-v sh -c 'echo "<h1>Plik z wolumenu</h1>" > /usr/share/nginx/html/test.html'
curl http://localhost:8082/test.html
```

Usuń kontener i uruchom nowy z tym samym wolumenem:

```bash
docker rm -f web-v
docker run -d --name web-v2 -p 8082:80 -v strona:/usr/share/nginx/html nginx:1.29
curl http://localhost:8082/test.html
docker volume inspect strona
```

Dla porównania zrób to samo **bez** wolumenu, na kontenerze `web` z kroku 3:

```bash
docker exec web sh -c 'echo "bez wolumenu" > /usr/share/nginx/html/test.html'
curl http://localhost:8080/test.html
docker rm -f web
docker run -d --name web -p 8080:80 nginx:1.29
curl http://localhost:8080/test.html
```

✅ Nowy kontener `web-v2` serwuje `test.html` z poprzedniego kontenera.
✅ W kontenerze bez wolumenu plik po `docker rm` znika (odpowiedź `404 Not Found`).
✅ Nowy, pusty wolumen `strona` nie przykrył strony startowej nginx: `curl http://localhost:8082/` nadal pokazuje „Welcome to nginx!”. Zastanów się, skąd się tam wziął `index.html`.

### 7. Sprzątanie

```bash
docker rm -f web web-v2
docker volume rm strona
docker ps -a
docker volume ls
```

✅ `docker ps -a` nie pokazuje żadnego kontenera z tego labu, `docker volume ls` nie pokazuje `strona`.

---

## Dla chętnych

### A. Zajrzyj do działającego kontenera

```bash
docker run -d --name cache redis:8.2-alpine
docker exec cache redis-cli ping
docker top cache
docker exec cache ps aux
docker stats --no-stream cache
docker logs -f cache     # Ctrl+C kończy podgląd, kontener działa dalej
```

✅ `redis-cli ping` → `PONG`. Porównaj `docker top` (procesy widziane z hosta) z `ps aux` w kontenerze: jaki PID ma `redis-server` w środku?

Usuń: `docker rm -f cache`.

### B. Dlaczego `docker stop` czasem trwa długo

```bash
docker run -d --name zegar busybox:1.37 sh -c 'while true; do date; sleep 2; done'
docker logs -t zegar
time docker stop -t 10 zegar
docker inspect -f '{{.State.ExitCode}}' zegar
docker rm zegar
```

✅ `docker stop -t 10` trwa około 10 s, a kod wyjścia to `137` (128 + 9, czyli SIGKILL). Sprawdź w `docker stop --help`, co oznacza `-t`. Co Docker wysyła najpierw, a co po upływie czasu? Jaki proces jest w tym kontenerze PID 1 i dlaczego nie reaguje na pierwszy sygnał?

Uruchom go jeszcze raz z flagą `--init` (`docker run -d --init --name zegar …`) i porównaj czas zatrzymania oraz kod wyjścia.

### C. Tagi to tylko etykiety

```bash
docker tag nginx:1.29 moj-nginx:1.0.0
docker images --filter reference='*nginx*'
docker rmi moj-nginx:1.0.0
docker images --filter reference='*nginx*'
```

✅ `nginx:1.29` i `moj-nginx:1.0.0` mają to samo `IMAGE ID`. `docker rmi` usuwa tylko etykietę (`Untagged`), obraz `nginx:1.29` zostaje.

### D. Co zmieniło się w kontenerze

```bash
docker run -d --name zmiany nginx:1.29
docker exec zmiany sh -c 'echo test > /tmp/nowy.txt'
docker diff zmiany
docker cp zmiany:/etc/nginx/nginx.conf /tmp/nginx.conf
docker rm -f zmiany
```

✅ `docker diff` pokazuje `A /tmp/nowy.txt` (A = dodany, C = zmieniony, D = usunięty), a `nginx.conf` leży w `/tmp` na Twoim laptopie.

### E. Ile miejsca zajmuje Docker

```bash
docker system df
docker container prune
```

Uwaga: `container prune` usuwa **wszystkie** zatrzymane kontenery na Twojej maszynie, nie tylko te z labu. Przeczytaj pytanie, zanim potwierdzisz. Jest też `docker system prune`, które czyści więcej naraz. Na komputerze, na którym pracujesz także przy innych projektach, uruchamiaj je świadomie.

---

## SUKCES

- [ ] `docker version` pokazuje Client i Server, `hello-world` działa
- [ ] strona nginx była dostępna pod `localhost:8080`, a `docker logs web` pokazał Twoje żądanie
- [ ] umiesz wywołać i naprawić błąd `port is already allocated`
- [ ] `postgres:18` działał ze zmiennymi z `db.env`, a `psql` pokazał bazę `sklep`
- [ ] `test.html` przeżył `docker rm`, bo leżał w wolumenie `strona`
- [ ] po sprzątaniu `docker ps -a` nie pokazuje kontenerów z tego labu

## Gdy coś nie działa

| Objaw | Co zrobić |
|---|---|
| `Cannot connect to the Docker daemon` / `error during connect` / brak sekcji Server w `docker version` | Docker Desktop nie działa albo jeszcze startuje. Uruchom go i poczekaj na zielony status. Linux: `sudo systemctl start docker`, użytkownik w grupie `docker` |
| `port is already allocated` / `address already in use` | Port na hoście jest zajęty (Twój wcześniejszy kontener albo inny program). `docker ps` pokaże kontener, który go trzyma. Usuń go albo zmień port hosta, np. `-p 8090:80`. Kontener po nieudanym starcie ma status `Created`: usuń go `docker rm <nazwa>` |
| `Conflict. The container name "/web" is already in use` | Kontener o tej nazwie już istnieje (może zatrzymany). `docker rm -f web` i powtórz |
| `curl` w PowerShellu pyta o parametry albo zwraca obiekt | W Windows PowerShell `curl` to alias `Invoke-WebRequest`. Pisz `curl.exe http://localhost:8080` albo użyj przeglądarki |
| `the input device is not a TTY` (Git Bash na Windows) | Dodaj `winpty` przed komendą: `winpty docker run -it …` albo użyj PowerShella |
| `WARNING: The requested image's platform (linux/amd64) does not match …` | Na Macu z procesorem M obraz nie ma wersji arm64 i działa w emulacji. Obrazy z tego labu mają wersję arm64, więc ostrzeżenie oznacza zwykle literówkę w nazwie albo tagu |
| `psql: … the database system is starting up` | Baza jeszcze się inicjuje. `docker logs -f db` i poczekaj na `ready to accept connections` |
| `docker logs db` po kroku 5 pokazuje tylko błąd o haśle | Uruchamiasz stary kontener `db` bez zmiennych. `docker rm -f -v db` i uruchom ponownie z `--env-file db.env` |
| `open db.env: no such file or directory` | Jesteś w złym katalogu. `cd labs/lab01-docker-podstawy` |
| `toomanyrequests: You have reached your pull rate limit` | Limit pobrań z Docker Hub dla anonimowych użytkowników. `docker login` (darmowe konto) albo napisz na czacie |
| `no space left on device` | Dysk maszyny wirtualnej Dockera jest pełny. `docker system df`, usuń nieużywane obrazy (`docker image prune`) albo powiększ dysk w Settings → Resources |
