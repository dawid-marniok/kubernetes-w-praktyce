# Dzień 1 — tmpfs na przykładach

Rozwinięcie tabeli „Dane: wolumen, bind mount, tmpfs” z [ściągi z podstaw Dockera](podstawy.md).

## Czym jest tmpfs

tmpfs to system plików w RAM, który Docker montuje w kontenerze pod wskazaną ścieżką. Nic z niego nie trafia na dysk, a przy zatrzymaniu kontenera jego zawartość znika.

Najlepiej to widać w zestawieniu z warstwą zapisu kontenera, która przeżywa restart i znika dopiero przy `docker rm`:

| Gdzie zapisano | stop + start / restart | docker rm |
|---|---|---|
| warstwa zapisu kontenera | przeżywa | znika |
| tmpfs | **znika** | znika |
| wolumen | przeżywa | przeżywa |

Restart nie czyści kontenera. Tylko tmpfs jest czyszczony już przy zatrzymaniu.

## Przykład 1: dane znikają po restarcie

```bash
docker run -d --name tmp --tmpfs /cache alpine:3.22 sleep 1d
docker exec tmp sh -c 'echo w-ram > /cache/a; echo na-dysku > /root/b'
docker restart tmp
docker exec tmp ls /cache /root
# /cache -> pusto
# /root  -> plik b nadal jest (warstwa zapisu przeżyła restart)
docker rm -f tmp
```

## Przykład 2: --read-only + tmpfs

System plików tylko do odczytu sprawia, że atakujący nic nie dopisze. Aplikacja wciąż musi jednak gdzieś zapisać PID, cache i pliki tymczasowe.

```bash
docker run --rm -p 8080:80 --read-only nginx:1.29
# nginx pada: nie może utworzyć /var/cache/nginx/... ani /run/nginx.pid

docker run --rm -p 8080:80 --read-only \
  --tmpfs /var/cache/nginx --tmpfs /run --tmpfs /tmp nginx:1.29
# działa: curl localhost:8080 -> 200
```

Reszta systemu plików jest zablokowana. Zapisywać można tylko w tych trzech katalogach, w RAM, i nic z nich nie przetrwa restartu.

## Przykład 3: pliki wrażliwe poza dyskiem

Na przykład tymczasowo rozszyfrowany klucz, token pobrany przy starcie albo pliki sesji. W tmpfs nie zostaną w warstwie kontenera ani w `docker commit` i nie da się ich odzyskać z dysku hosta.

## Przykład 4: limit rozmiaru i składnia

Krótka składnia z opcjami po dwukropku:

```bash
docker run --tmpfs /tmp:rw,size=64m,mode=1777 ...
```

Dłuższa, czytelniejsza składnia `--mount`:

```bash
docker run --mount type=tmpfs,dst=/tmp,tmpfs-size=64m ...
```

W Compose:

```yaml
services:
  web:
    read_only: true
    tmpfs:
      - /tmp:size=64m
      - /run
```

## Na co uważać

- **To jest RAM.** Bez `size` aplikacja może zapełnić pamięć. Zapis do tmpfs liczy się do limitu pamięci kontenera (`--memory`), więc duży plik w `/tmp` może skończyć się OOM-killem.
- **Nie da się go współdzielić.** Każdy kontener ma własny tmpfs.
- **Działa tylko na Linuksie.** W Docker Desktop to nie przeszkadza, bo kontenery i tak działają w linuksowej VM.
- **Skrypt w tmpfs się nie uruchamia („permission denied”)?** Sprawdź opcje montowania: `docker exec <kontener> mount | grep tmpfs`. Jeśli jest tam `noexec`, uruchamianie plików z tego katalogu jest zablokowane.
- **W Kubernetesie (dzień 3)** odpowiednikiem jest `emptyDir` z `medium: Memory`. Też działa w RAM i liczy się do limitu pamięci, ale żyje tak długo jak pod, więc przeżywa restart kontenera.

## W jednym zdaniu

Wolumen na dane, które mają przetrwać. Bind mount na pliki z hosta. tmpfs na pliki, które mają zniknąć, i na zapis, gdy reszta kontenera jest read-only.
