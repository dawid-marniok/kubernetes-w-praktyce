# lab02 — Sieci, dane i logi

**Cel:** połączyć kontenery po nazwie we własnej sieci, sprawdzić izolację sieci, porównać wolumen, bind mount i tmpfs oraz ograniczyć rozmiar logów kontenera.

**Czas:** ~30 min (kroki 1–4). Kroki „dla chętnych” robisz, jeśli skończysz wcześniej.

**Po labie masz:** dwa kontenery, które rozmawiają po nazwie, stronę serwowaną z katalogu na Twoim laptopie i kontener, którego logi nie urosną ponad ustawiony limit.

## Zanim zaczniesz

- Docker działa (`docker version` pokazuje Client i Server), lab01 za Tobą.
- Terminal w katalogu tego labu (jest tu katalog `strona/` z plikiem `index.html`):
  ```bash
  cd labs/lab02-sieci-wolumeny
  ```
- Narzędzia sieciowe bierzemy z małych obrazów: `busybox:1.37` (`ping`, `wget`, `nslookup`) i `nicolaka/netshoot:v0.14` (`ss`, `ip`, `dig`, `curl`). Nie trzeba niczego instalować w kontenerach.
- Ścieżki do katalogów hosta podajemy względnie: `-v ./strona:/…`. Na Windows w PowerShellu, jeśli względna ścieżka nie zadziała, użyj `-v ${PWD}/strona:/…`; w Git Bash `-v "$(pwd)/strona":/…`.

---

## Poziom podstawowy

### 1. Własna sieć i DNS po nazwie

Najpierw domyślna sieć `bridge`, do której trafia każdy kontener bez `--network`:

```bash
docker network ls
docker run -d --name sasiad busybox:1.37 sleep 3600
docker run --rm busybox:1.37 ping -c 1 sasiad
```

✅ `ping: bad address 'sasiad'`: w domyślnej sieci kontenery nie widzą się po nazwie.

Teraz własna sieć:

```bash
docker network create app-net
docker run -d --name web --network app-net nginx:1.29-alpine
docker run --rm --network app-net busybox:1.37 ping -c 2 web
docker run --rm --network app-net busybox:1.37 nslookup web
docker run --rm --network app-net busybox:1.37 wget -qO- http://web
docker network inspect app-net
```

✅ `ping web` dostaje odpowiedzi, `nslookup` podaje adres `web` z podsieci `app-net` (serwer DNS to `127.0.0.11`, wbudowany DNS Dockera), `wget` zwraca HTML strony nginx.
✅ W `docker network inspect app-net` w sekcji `Containers` widać kontener `web` z adresem IP.

Zauważ: kontener `web` nie ma `-p`, a mimo to inne kontenery w `app-net` się z nim łączą. `-p` jest potrzebne tylko do ruchu **z hosta**.

### 2. Izolacja sieci i `docker network connect`

```bash
docker network create inna-net
docker run -d --name obcy --network inna-net busybox:1.37 sleep 3600
docker exec obcy wget -qO- -T 3 http://web
```

✅ `wget: bad address 'web'`: kontener z innej sieci nie widzi `web`.

Podłącz `obcy` do drugiej sieci, bez restartu:

```bash
docker network connect app-net obcy
docker exec obcy wget -qO- -T 3 http://web
docker inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{$v.IPAddress}}{{println}}{{end}}' obcy
```

✅ Teraz `wget` zwraca stronę, a `obcy` ma dwa adresy IP, po jednym w każdej sieci.

### 3. Wolumen, bind mount, tmpfs

W lab01 plik przeżył kontener w **named volume**. Teraz dwa pozostałe sposoby.

**Bind mount: katalog z Twojego laptopa w kontenerze.**

```bash
docker run -d --name strona -p 8080:80 -v ./strona:/usr/share/nginx/html:ro nginx:1.29-alpine
curl http://localhost:8080
```

Otwórz `strona/index.html` w edytorze, zmień nagłówek, zapisz i odśwież `http://localhost:8080`. Spróbuj też zapisać plik z wnętrza kontenera:

```bash
docker exec strona sh -c 'echo test > /usr/share/nginx/html/test.html'
```

Ten sam katalog, ale do zapisu, w kontenerze `busybox`. Zwróć uwagę na `sh -c '…'`: przekierowanie `>` musi wykonać powłoka **w kontenerze**. Bez `sh -c` wykona je powłoka na Twoim laptopie i plik nie trafi do kontenera.

```bash
docker run --rm -v ./strona:/dane busybox:1.37 sh -c 'echo "zapisane w kontenerze" > /dane/z-kontenera.txt'
ls strona
cat strona/z-kontenera.txt
```

✅ Zmiana w edytorze jest od razu widoczna w przeglądarce, bez restartu kontenera.
✅ Zapis w kontenerze `strona` kończy się `Read-only file system` (to robi `:ro`), a plik z `busybox` pojawia się w katalogu `strona/` na Twoim laptopie.

**tmpfs: katalog w pamięci, znika po zatrzymaniu.**

```bash
docker run -d --name tymczasowy --tmpfs /cache busybox:1.37 sleep 3600
docker exec tymczasowy sh -c 'echo "w pamięci" > /cache/plik.txt && ls /cache && df -h /cache'
docker restart tymczasowy      # trwa kilka sekund: sleep jako PID 1 nie reaguje na SIGTERM
docker exec tymczasowy ls -la /cache
```

✅ `df -h /cache` pokazuje system plików `tmpfs`, a po `docker restart` katalog `/cache` jest pusty.

Uzupełnij tabelę (na omówienie):

| | named volume | bind mount | tmpfs |
|---|---|---|---|
| Gdzie leżą dane? | | | |
| Przeżywa `docker rm`? | | | |
| Przeżywa `docker restart`? | | | |
| Do czego go użyjesz? | | | |

### 4. Logi kontenera i limit ich rozmiaru

Logi to to, co proces w kontenerze wypisuje na stdout i stderr. `docker logs` oddaje je też na dwa strumienie, dlatego przed `| grep` dopisz `2>&1` (nginx pisze komunikaty błędów na stderr):

```bash
curl -s http://localhost:8080 > /dev/null
docker logs strona
docker logs --tail 3 -t strona
docker logs --since 5m strona 2>&1 | grep GET
docker info -f '{{.LoggingDriver}}'
```

Domyślnie (sterownik `json-file`) logi rosną bez limitu. Kontener, który dużo pisze, może zapełnić dysk. Uruchom „gadułę” z limitem: 2 pliki po 10 KB.

```bash
docker run -d --name gadula --log-opt max-size=10k --log-opt max-file=2 busybox:1.37 sh -c 'i=0; while true; do i=$((i+1)); echo "linia $i"; done'
```

Odczekaj kilka sekund i sprawdź:

```bash
docker logs gadula | head -n 1
docker logs gadula | wc -l
docker inspect -f '{{.HostConfig.LogConfig}}' gadula
docker inspect -f '{{.LogPath}}' gadula
docker rm -f gadula
```

✅ Pierwsza linia w `docker logs` to nie `linia 1`: starsze wpisy zostały usunięte przy rotacji. `wc -l` pokazuje kilkaset linii, choć kontener wypisał ich ponad milion: zostały tylko ostatnie 2 pliki po 10 KB.
✅ `LogConfig` pokazuje `json-file` z `max-size:10k` i `max-file:2`, a `LogPath` ścieżkę do pliku `…-json.log`.

Na Linuksie ten plik znajdziesz pod podaną ścieżką (`sudo ls -la <ścieżka>`). Na Macu i Windowsie leży w maszynie wirtualnej Docker Desktop, więc z laptopa go nie zobaczysz. Wtedy zostaje `docker logs`.

### Sprzątanie

```bash
docker rm -f sasiad web obcy strona tymczasowy
docker network rm app-net inna-net
rm strona/z-kontenera.txt
```

✅ `docker ps -a` i `docker network ls` nie pokazują niczego z tego labu (zostają tylko sieci `bridge`, `host`, `none` i Twoje własne z innych projektów).

---

## Dla chętnych

### A. Baza, która przeżywa kontener, i klient po nazwie

```bash
docker network create app-net
docker volume create pgdata
docker run -d --name db --network app-net -e POSTGRES_PASSWORD=changeme-lab02 -v pgdata:/var/lib/postgresql postgres:18
docker logs -f db        # poczekaj na „ready to accept connections”, Ctrl+C
```

Połącz się z **drugiego** kontenera po nazwie `db` i dodaj dane:

```bash
docker run --rm --network app-net -e PGPASSWORD=changeme-lab02 postgres:18 psql -h db -U postgres -c "CREATE TABLE notatki (tresc text); INSERT INTO notatki VALUES ('przeżyłam docker rm');"
```

Usuń kontener bazy i uruchom nowy z tym samym wolumenem:

```bash
docker rm -f db
docker run -d --name db --network app-net -e POSTGRES_PASSWORD=changeme-lab02 -v pgdata:/var/lib/postgresql postgres:18
docker run --rm --network app-net -e PGPASSWORD=changeme-lab02 postgres:18 psql -h db -U postgres -c "SELECT * FROM notatki;"
```

✅ `SELECT` zwraca wiersz `przeżyłam docker rm`. Jeśli łączysz się za szybko po starcie, dostaniesz `Connection refused`: poczekaj kilka sekund.

Nie usuwaj jeszcze wolumenu `pgdata`, przyda się w kroku B.

### B. Kopia zapasowa wolumenu przez `tar`

Wolumen nie ma komendy „backup”. Robi się to kontenerem, który widzi wolumen i katalog na hoście:

```bash
docker stop db
docker run --rm -v pgdata:/dane:ro -v ./:/backup busybox:1.37 tar czf /backup/pgdata.tar.gz -C /dane .
ls -la pgdata.tar.gz      # kilka MB
```

Przywróć do nowego wolumenu i uruchom na nim bazę:

```bash
docker volume create pgdata-kopia
docker run --rm -v pgdata-kopia:/dane -v ./:/backup busybox:1.37 tar xzf /backup/pgdata.tar.gz -C /dane
docker rm -f db
docker run -d --name db --network app-net -e POSTGRES_PASSWORD=changeme-lab02 -v pgdata-kopia:/var/lib/postgresql postgres:18
docker run --rm --network app-net -e PGPASSWORD=changeme-lab02 postgres:18 psql -h db -U postgres -c "SELECT * FROM notatki;"
```

✅ Baza na wolumenie `pgdata-kopia` ma tabelę `notatki` z tym samym wierszem.

Dlaczego przed `tar` zatrzymaliśmy bazę?

### C. Zajrzyj do sieci kontenera narzędziami z `netshoot`

`--network container:<nazwa>` uruchamia kontener we **wspólnej przestrzeni sieciowej** z innym. Widzisz wtedy jego interfejsy i porty, a do obrazu nie trzeba niczego instalować:

```bash
docker run -d --name web --network app-net nginx:1.29-alpine
docker run --rm --network container:web nicolaka/netshoot:v0.14 ss -tln
docker run --rm --network container:web --pid container:web nicolaka/netshoot:v0.14 ss -tlnp
docker run --rm --network container:web nicolaka/netshoot:v0.14 ip -br addr
docker run --rm --network app-net nicolaka/netshoot:v0.14 dig +short web
docker run --rm --network app-net nicolaka/netshoot:v0.14 curl -sI http://web
```

✅ `ss -tln` pokazuje port 80 w stanie `LISTEN`, ale bez nazwy procesu. Dopiero z `--pid container:web` (wspólna przestrzeń procesów) widać `users:(("nginx",pid=1,…))`. `dig` zwraca adres IP `web`, a `curl -sI` nagłówek `Server: nginx/1.29…`.

### D. Sieć z własną podsiecią i stałym adresem

```bash
docker network create --subnet 172.30.0.0/24 --gateway 172.30.0.1 lab-subnet
docker run -d --name staly-ip --network lab-subnet --ip 172.30.0.10 busybox:1.37 sleep 3600
docker exec staly-ip ip addr show eth0
docker network inspect -f '{{json .IPAM.Config}}' lab-subnet
```

✅ Kontener ma adres `172.30.0.10`. Gdy `docker network create` zgłosi `Pool overlaps with other one on this address space`, wybierz inną podsieć (np. `172.31.50.0/24`).

### E. Host networking (tylko Linux, opcjonalne)

Na Linuksie z Docker Engine:

```bash
docker run -d --name nginx-host --network host nginx:1.29-alpine
curl http://localhost:80
docker run --rm --network host nicolaka/netshoot:v0.14 ss -tlnp | grep ':80 '
docker rm -f nginx-host
```

Kontener nie ma własnej sieci, nginx słucha bezpośrednio na porcie 80 hosta, a `-p` nie ma znaczenia. Na Docker Desktop (Mac, Windows) „host” to maszyna wirtualna Dockera, nie Twój laptop: bez włączenia funkcji host networking w ustawieniach Docker Desktop `localhost:80` nie odpowie. Na Macu i Windowsie ten krok możesz pominąć.

### Sprzątanie po krokach dla chętnych

```bash
docker rm -f db web staly-ip
docker network rm app-net lab-subnet
docker volume rm pgdata pgdata-kopia
rm pgdata.tar.gz
```

---

## SUKCES

- [ ] w domyślnej sieci `ping sasiad` nie działał, a we własnej `app-net` kontenery łączyły się po nazwie `web`
- [ ] `obcy` z `inna-net` nie widział `web`, dopóki nie wykonałeś `docker network connect`
- [ ] zmiana `strona/index.html` w edytorze była od razu widoczna pod `localhost:8080`, a plik z `/cache` (tmpfs) zniknął po restarcie
- [ ] logi kontenera `gadula` zostały przycięte przez `max-size` / `max-file`, a `docker inspect -f '{{.LogPath}}'` pokazał plik logu
- [ ] tabela named volume / bind mount / tmpfs jest wypełniona

## Gdy coś nie działa

| Objaw | Co zrobić |
|---|---|
| `Cannot connect to the Docker daemon` | Docker Desktop nie działa. Uruchom go i poczekaj na zielony status |
| `ping: bad address 'web'` w kroku 1, choć powinno działać | Kontener z `ping` nie jest w `app-net`. Sprawdź, czy dodałeś `--network app-net` |
| `ping: not found` / `ip: not found` | Używasz obrazu bez tych narzędzi (np. `ubuntu`). Weź `busybox:1.37` albo `nicolaka/netshoot:v0.14`. Instalacja w ubuntu tylko w jednym `sh -c`: `docker exec <kontener> sh -c "apt-get update && apt-get install -y iputils-ping iproute2"` |
| Plik zapisany przez `docker exec … echo … > plik` pojawił się na laptopie, a nie w kontenerze | Przekierowanie `>` wykonała Twoja powłoka. Owiń komendę w `sh -c '…'` |
| `port is already allocated` na 8080 | Został kontener z lab01 albo inny program. `docker ps`, usuń go albo zmień port: `-p 8090:80` |
| `invalid reference format` / `includes invalid characters for a local volume name` przy `-v ./strona:…` | Starszy Docker albo powłoka nie rozwija ścieżki. Podaj pełną: `-v "$(pwd)/strona":/usr/share/nginx/html:ro` (PowerShell: `-v ${PWD}/strona:/usr/share/nginx/html:ro`) |
| Zaraz po zapisaniu pliku w edytorze `404 Not Found`, chwilę później działa | Edytor zapisuje plik jako nowy i podmienia stary. Docker Desktop potrzebuje chwili, żeby to zobaczyć. Odśwież jeszcze raz |
| Strona pod `localhost:8080` jest pusta albo `403 Forbidden` | Zamontowałeś pusty albo zły katalog. Jesteś w `labs/lab02-sieci-wolumeny`? `docker inspect -f '{{json .Mounts}}' strona` pokaże ścieżkę źródłową |
| Windows: zmiany w pliku nie są widoczne od razu | Katalog leży na dysku Windows, a Docker działa w WSL 2. Odśwież z `Ctrl+F5`; przy dużych projektach trzymaj pliki w systemie plików WSL (`\\wsl$\…`) |
| `error while removing network: … has active endpoints` | W sieci są jeszcze kontenery. Najpierw `docker rm -f …`, potem `docker network rm` |
| `Pool overlaps with other one on this address space` | Podsieć jest już używana (inna sieć Dockera, VPN). Wybierz inną |
| `db` ma status `Exited (1)`, w logach `Error: in 18+, these Docker images are configured to store database data …` | Wolumen zamontowany pod starą ścieżką `/var/lib/postgresql/data` (tak było do `postgres:17`). Dla `postgres:18` montuj `-v pgdata:/var/lib/postgresql` |
| `Connection refused` przy `psql -h db` | Baza jeszcze startuje. `docker logs -f db` i poczekaj na `ready to accept connections` |
| `curl` w PowerShellu zachowuje się dziwnie | Pisz `curl.exe` albo otwórz adres w przeglądarce |
