# lab18 — Operator: klaster PostgreSQL z failoverem (CloudNativePG)

**Cel:** stawiasz PostgreSQL jednym obiektem `Cluster`, skalujesz go do trzech instancji i sprawdzasz, że po awarii primary operator sam promuje replikę, a dane zostają.

**Po labie masz:** klaster `pg` z trzema instancjami i tabelę, która przeżyła usunięcie primary.

Operator CloudNativePG jest już zainstalowany w klastrze (namespace `cnpg-system`). Instaluje go prowadzący: CRD i operator to obiekty całego klastra, do których nie masz uprawnień. Ty tworzysz tylko obiekty `Cluster` w swoim namespace.

## Pliki

| Plik | Do czego |
|---|---|
| `cluster.yaml` | klaster `pg`: 1 instancja, PostgreSQL 17, 1Gi, zasoby. Startujesz od niego |
| `traditional-postgres.yaml` | to samo „po staremu”: Deployment + PVC + Secret + Service, do porównania |
| `app-credentials.yaml` | dla chętnych: własne hasło właściciela bazy |
| `scheduled-backup.yaml` | do przeczytania: backup co noc (wymaga object storage, którego tu nie ma) |

## Poziom podstawowy

### 1. Co dodał operator

```bash
kubectl api-resources | grep cnpg
kubectl explain cluster.spec.instances
kubectl get crd | grep cnpg.io        # podgląd CRD masz (rola tylko do odczytu)
```

✅ Na liście m.in. `clusters`, `backups`, `scheduledbackups`, `poolers`. To nowe typy w API, tak jak wczoraj Wasze CRD `Backup`.

### 2. Klaster z jedną instancją

Przeczytaj `cluster.yaml`. Zwróć uwagę: nie ma `namespace:` (idzie do Twojego), nie ma `storageClass` (domyślna klasy klastra), są `resources` (quota w namespace).

```bash
kubectl apply -f cluster.yaml
kubectl get cluster pg -w          # Ctrl+C, gdy STATUS = Cluster in healthy state (1–3 min)
```

### 3. Co operator utworzył za Ciebie

```bash
kubectl get pods,pvc,svc -l cnpg.io/cluster=pg
kubectl get secret | grep pg-
kubectl get secret pg-app -o jsonpath='{.data.uri}' | base64 -d; echo
```

Zanotuj: ile jest Service'ów i czym się różnią `pg-rw`, `pg-ro`, `pg-r`? Skąd wzięło się hasło w `pg-app`?

### 4. Skalowanie do trzech instancji

Zmień w `cluster.yaml` `instances: 1` na `instances: 3` i `kubectl apply -f cluster.yaml` (albo: `kubectl patch cluster pg --type merge -p '{"spec":{"instances":3}}'`).

```bash
kubectl get pods -L cnpg.io/instanceRole -w     # Ctrl+C, gdy są 3 pody Running
kubectl get cluster pg
```

✅ `INSTANCES 3`, `READY 3`, w kolumnie `INSTANCEROLE` jeden `primary` i dwa `replica`.

### 5. Dane testowe na primary

```bash
kubectl get cluster pg                 # kolumna PRIMARY, np. pg-1
kubectl exec -it pg-1 -c postgres -- psql -d app
```

```sql
create table t(x int);
insert into t values (1),(2),(3);
select * from t;
\q
```

Spróbuj tego samego `insert` na replice (`kubectl exec -it pg-2 -c postgres -- psql -d app`). Co odpowiada baza?

### 6. Awaria primary

Drugi terminal: `kubectl get pods -L cnpg.io/instanceRole -w`. W pierwszym:

```bash
kubectl get endpointslices -l kubernetes.io/service-name=pg-rw -o wide   # IP obecnego primary
kubectl delete pod pg-1                                                 # nazwa primary z kroku 5
kubectl get cluster pg -w                                               # Failing over → healthy
```

Po kilkunastu sekundach:

```bash
kubectl get cluster pg                                                  # nowy PRIMARY
kubectl get endpointslices -l kubernetes.io/service-name=pg-rw -o wide  # IP nowego primary
kubectl exec -it <nowy-primary> -c postgres -- psql -d app -c "select * from t;"
kubectl get pods -L cnpg.io/instanceRole                                # stary primary wrócił jako?
```

### SUKCES

- [ ] `kubectl get cluster pg` pokazuje innego primary niż przed usunięciem poda
- [ ] `select * from t` na nowym primary zwraca te same 3 wiersze
- [ ] `pg-rw` wskazuje IP nowego primary, a stary primary wrócił jako replika

## Dla chętnych

**A. Porównanie z „klasycznym” Postgresem.** Przeczytaj `traditional-postgres.yaml`. Wypisz trzy rzeczy, które operator zrobił za Ciebie, a których tam nie ma. (Wdrażać nie musisz; jeśli wdrożysz, pamiętaj o limicie PVC w quocie: `kubectl describe quota`.)

**B. Aplikacja łączy się przez Service.** Klient w osobnym podzie, hasło z Secretu:

```bash
kubectl run psql --rm -it --image=ghcr.io/cloudnative-pg/postgresql:17.11 --restart=Never \
  --env="DATABASE_URL=$(kubectl get secret pg-app -o jsonpath='{.data.uri}' | base64 -d)" \
  -- sh -c 'psql "$DATABASE_URL" -c "select inet_server_addr(), pg_is_in_recovery();"'
```

Obraz klienta to ten sam, którego używa klaster: węzeł ma go już w cache, a ghcr.io nie ma limitów pobrań jak Docker Hub. `pg_is_in_recovery() = f` znaczy: rozmawiasz z primary. Zamień w URI host `pg-rw` na `pg-ro` i powtórz.

**C. Operator naprawia, co zepsujesz.** `kubectl delete svc pg-rw`, a po kilku sekundach `kubectl get svc`. Co się stało?

**D. Kontrolowany switchover** (z pluginem `kubectl cnpg`, jeśli masz krew: `kubectl krew install cnpg`): `kubectl cnpg status pg`, potem `kubectl cnpg promote pg <replika>`.

**E. Własne hasło.** Usuń klaster (`kubectl delete cluster pg`), odkomentuj w `cluster.yaml` sekcję `secret:`, `kubectl apply -f app-credentials.yaml -f cluster.yaml`. Czy powstał Secret `pg-app`? Dlaczego?

**F. Backup.** Przeczytaj `scheduled-backup.yaml`: ile pól ma harmonogram i co oznacza pierwsze? Dlaczego replika to nie backup?

## Gdy coś nie działa

| Objaw | Co zrobić |
|---|---|
| `no matches for kind "Cluster"` | Operatora nie ma w klastrze albo literówka w `apiVersion`; zgłoś prowadzącemu |
| `forbidden: … clusters.postgresql.cnpg.io` | Brak uprawnień do CRD w namespace; zgłoś prowadzącemu |
| PVC `Pending` | Wpisałeś `storageClass`, której nie ma (`kubectl get storageclass`); usuń pole |
| `exceeded quota: … persistentvolumeclaims` | Za dużo PVC: maks. 3 instancje, usuń stare PVC z poprzednich labów |
| `exceeded quota: … requests.memory` | Za duże `resources` albo inne pody zajmują quotę: `kubectl describe quota` |
| `STATUS` długo „Setting up primary” | `kubectl describe cluster pg`, `kubectl logs pg-1-initdb-…`; zwykle pobieranie obrazu |
| `psql: … role "root" does not exist` | Brak `-c postgres` albo `psql` bez `-d app` w innym kontenerze: skopiuj komendę z kroku 5 |
| `cannot execute INSERT in a read-only transaction` | Jesteś na replice. To dobrze: zapisuje tylko primary |

## Sprzątanie (przed projektem!)

Klaster zajmuje 3 PVC z quoty, a projekt potrzebuje miejsca na Mongo:

```bash
kubectl delete cluster pg
kubectl get pvc          # PVC klastra znikają razem z nim
```
