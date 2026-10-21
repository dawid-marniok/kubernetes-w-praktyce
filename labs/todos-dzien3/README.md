# ToDos · dzień 3 — baza na dysku, zasoby i autoskalowanie

**Cel:** ToDos z wczoraj przestaje gubić zadania i sam reaguje na ruch. Mongo dostaje własny dysk w StatefulSecie, każdy kontener ma przemyślane `resources`, a api dokłada repliki pod obciążeniem. Wszystko z obiektów z dzisiaj.
**Środowisko:** wspólny klaster, Twój namespace. Nie piszesz `-n` ani `namespace:`.

Wczorajsza baza nie miała dysku: usuń pod `mongo`, a zadania znikną. Dziś to naprawiasz. Adres, Ingress, Secret i ConfigMap zostają bez zmian.

Tu masz tylko wymagania. Jak je spełnisz, decydujesz sam. Utknąłeś: gotowe manifesty i opis są w [`rozwiazanie/`](rozwiazanie/). Zajrzyj najpierw do jednego pliku, a nie od razu do wszystkich.

```
przeglądarka ──► Ingress ──► web ──/api──► Service api ──► pody api (HPA: 2–4) ──► Service mongo (headless) ──► mongo-0 ──► PVC data-mongo-0 (1Gi)
```

**Od trenera na czacie:** nic nowego. Adres ten sam co wczoraj: `https://todos-<login>.<DOMENA>`, `<REJESTR>` z karty dostępowej (punkt 1).

## Zanim zaczniesz

ToDos z dnia 2 musi działać:

```bash
kubectl get deploy,svc,ingress -l app.kubernetes.io/part-of=todos   # 3 Deploymenty, 3 Service, Ingress
```

Nie masz go albo nie działa: wdróż [`../todos-dzien2/rozwiazanie/`](../todos-dzien2/rozwiazanie/) (polecenia w jego README, ok. 5 minut).

Quota liczy wszystko w namespace. Usuń obiekty z labów 09–11, ToDos zostaje:

```bash
kubectl delete sts,deploy,ds,job,cronjob,hpa,pod,svc,ingress -l 'app.kubernetes.io/part-of!=todos'
kubectl delete pvc -l 'app.kubernetes.io/part-of!=todos'
kubectl get pvc                         # pusto
kubectl describe resourcequota          # zapisz sobie Hard dla requests.cpu, limits.cpu i persistentvolumeclaims
kubectl top pods -l app.kubernetes.io/part-of=todos    # ile ToDos zużywa naprawdę
```

## Wymagania

**Wszystkie nowe obiekty**
- mają etykietę `app.kubernetes.io/part-of: todos`, także pody z szablonów i PVC z `volumeClaimTemplates` (po niej wieczorne sprzątanie omija ToDos).

**MongoDB na dysku**
- StatefulSet `mongo` z jedną repliką zamiast wczorajszego Deploymentu. Obraz, użytkownik root z Secretu `todos-mongo` i sonda gotowości jak wczoraj,
- dysk z `volumeClaimTemplates`: `ReadWriteOnce`, `1Gi`, **bez** `storageClassName` (działa domyślna klasa klastra, sprawdź którą: `kubectl get storageclass`), zamontowany tam, gdzie Mongo trzyma pliki bazy: `/data/db`,
- Service `mongo` jako headless (`clusterIP: None`), StatefulSet wskazuje go w `serviceName`. Nazwa `mongo` zostaje, bo jest w adresie bazy w Secrecie,
- wczorajsze zadania przepadną (baza nie miała dysku) i to jest w porządku. Zanim zastosujesz StatefulSet, usuń stary Deployment i Service `mongo`: Service z adresem IP nie da się przerobić na headless w miejscu, `clusterIP` jest niezmienne.

**Zasoby**
- każdy kontener ma `requests` i `limits` (api, web, mongo, a w zadaniu z gwiazdką także backup),
- Mongo w klasie QoS `Guaranteed`: requests równe limits dla CPU i pamięci, pamięć co najmniej `512Mi`. Baza ma być ostatnia do wyrzucenia z węzła,
- api zostaje `Burstable` z `requests.cpu: 50m`: od tej wartości HPA liczy procenty,
- całość mieści się w quocie także wtedy, gdy HPA podniesie api do maksimum. Policz sumę requests i limits przy 4 replikach api i porównaj z `Hard` z `kubectl describe resourcequota`.

**Autoskalowanie api**
- HPA `api` w `autoscaling/v2`: Deployment `api`, od 2 do 4 replik, cel 60% CPU,
- w manifeście Deploymentu `api` nie ma pola `replicas` (dlaczego? co zrobi każdy kolejny `kubectl apply`, gdy ono tam jest?).

**(\*) Kopia zapasowa bazy**
- CronJob `mongo-backup` raz na dobę (np. o 2:00) robi `mongodump` bazy. Obraz `mongo:7.0` ma `mongodump`, adres bazy weź z Secretu `todos-mongo` (klucz `uri`),
- archiwum ląduje na osobnym PVC `todos-backup` (1Gi), w nazwie pliku data i godzina, zostaje kilka ostatnich plików,
- nigdy dwa backupy naraz, w historii najwyżej 3 udane i 1 nieudany Job,
- prostsza wersja, jeśli brakuje czasu: bez PVC, `mongodump --archive` do `/tmp` i rozmiar pliku w logu.

Ściąga: `kubectl explain statefulset.spec.volumeClaimTemplates`, `kubectl explain hpa.spec --api-version=autoscaling/v2`, `kubectl explain cronjob.spec`, `kubectl create job --help`, wzorce w [`przyklady/k8s/`](../../przyklady/k8s/) (`09-statefulset`, `12-zasoby-qos`, `14-hpa`, `11-job-cronjob`).

## Jak sprawdzić

```bash
kubectl get sts,pods,pvc -l app.kubernetes.io/part-of=todos       # mongo-0 1/1, PVC data-mongo-0 Bound
kubectl get pod mongo-0 -o jsonpath='{.status.qosClass}'; echo    # Guaranteed
kubectl logs deploy/api | tail -3                                 # „Połączono z MongoDB”
kubectl describe resourcequota                                    # Used poniżej Hard
```

**Dane przeżywają poda.** Dodaj zadanie w przeglądarce albo z terminala, usuń pod bazy i sprawdź listę:

```bash
curl -s -X POST https://todos-<login>.<DOMENA>/api/todos \
  -H 'Content-Type: application/json' -d '{"title":"przeżyję restart"}'
kubectl delete pod mongo-0
kubectl get pod mongo-0 -w                                       # wraca jako mongo-0, 0/1 → 1/1, Ctrl-C
curl -s https://todos-<login>.<DOMENA>/api/todos                 # zadanie jest
```

Przez kilkanaście sekund po usunięciu poda strona zwraca błąd. Dlaczego? (Podpowiedź: `kubectl get pods -l app=todos-api` w tym czasie i sonda gotowości api.)

**HPA pod obciążeniem.** Generator ruchu bez `resources` dostanie wartości domyślne z LimitRange:

```bash
kubectl get hpa api                          # po minucie TARGETS cpu: <liczba>%/60%, REPLICAS 2
kubectl run load --image=busybox:1.37 --restart=Never -- \
  sh -c 'while true; do wget -q -O- http://api:3001/api/todos >/dev/null; done'
kubectl get hpa api -w                       # po 1–2 min REPLICAS rośnie do 3–4, Ctrl-C
kubectl top pods -l app=todos-api
kubectl delete pod load                      # repliki zejdą do 2 dopiero po ok. 5 min
```

**(\*) Backup bez czekania do 2:00:**

```bash
kubectl create job --from=cronjob/mongo-backup backup-test
kubectl logs -f job/backup-test              # „done dumping todos.todos (N documents)” i lista plików
```

## SUKCES

ToDos działa pod tym samym adresem, zadanie dodane przed `kubectl delete pod mongo-0` jest na liście po jego powrocie, `mongo-0` ma QoS `Guaranteed`, a `kubectl get hpa api` pokazuje procent CPU (nie `<unknown>`) i pod obciążeniem więcej niż 2 repliki. **Wklej na czat** wynik `kubectl get hpa api` pod obciążeniem.

Nie usuwaj ToDos. Zostaje na jutro.

## Dla chętnych

- **Dysk zostaje po StatefulSecie.** `kubectl delete sts mongo`, potem `kubectl get pvc` i `kubectl apply -f` Twojego pliku jeszcze raz. Są Twoje zadania? Dlaczego?
- **Gdzie leży dysk.** `kubectl get pv`, potem `kubectl describe pv <nazwa>`: znajdź identyfikator wolumenu w chmurze (`VolumeHandle`) i strefę w `Node Affinity`. Porównaj ze strefą węzła poda: `kubectl get pod mongo-0 -o wide` i `kubectl get nodes -L topology.kubernetes.io/zone`.
- **Większy dysk bez restartu.** `kubectl patch pvc data-mongo-0 -p '{"spec":{"resources":{"requests":{"storage":"2Gi"}}}}'` i `kubectl get pvc data-mongo-0 -w`. Czy pod się restartował? Co się stanie, gdy zamiast tego zmienisz rozmiar w `volumeClaimTemplates`?
- **Łagodniejsze schodzenie.** Dopisz do HPA `behavior.scaleDown`: okno 60 s i najwyżej 1 pod na minutę. Powtórz test obciążenia i porównaj, jak szybko repliki wracają do 2.

## Gdy coś nie działa

| Objaw | Co zrobić |
|---|---|
| `spec.clusterIP: Invalid value: "None": field is immutable` | został wczorajszy Service `mongo`: `kubectl delete svc mongo`, potem `apply` |
| PVC `Pending`, w eventach `WaitForFirstConsumer` | to normalne, dopóki `mongo-0` nie dostanie węzła |
| PVC `Pending` z `storageclass … not found` | w szablonie jest `storageClassName` z innego klastra: usuń tę linię, usuń StatefulSet i PVC, `apply` od nowa |
| `exceeded quota … persistentvolumeclaims` albo `requests.storage` | zostały PVC z lab09 (`data-db-*`, `app-data`): „Zanim zaczniesz” |
| `mongo-0` nie powstaje, `kubectl describe sts mongo` → `exceeded quota` | za duże `resources` albo pody z labów zajmują quotę: `kubectl describe resourcequota` |
| api `0/1` zaraz po migracji, w logach „Brak połączenia z MongoDB” | `mongo-0` jeszcze nie jest `Ready` (sonda co kilkanaście sekund); api połączy się samo |
| api `0/1`, w logach `Authentication failed` | Secret zmieniony po pierwszym starcie bazy: `MONGO_INITDB_*` działa tylko na pustym dysku. Usuń StatefulSet i PVC `data-mongo-0`, potem `apply` |
| `mongo-0` restartuje się z `OOMKilled` | za mały limit pamięci: co najmniej `512Mi` |
| HPA `TARGETS <unknown>/60%` | pierwsza minuta po utworzeniu to normalne; dłużej: brak `requests.cpu` w api (`kubectl describe hpa api`) |
| `REPLICAS` nie rośnie | jeden generator to za mało: drugi, `kubectl run load2 …` z tą samą komendą |
| HPA chce 4 repliki, a są 3; w `kubectl describe rs -l app=todos-api` `exceeded quota` | quota się skończyła: sprzątanie z „Zanim zaczniesz” albo mniejsze requests |
| po `kubectl apply` api na chwilę ma 1 replikę | `replicas` zniknęło z pliku, HPA za kilkanaście sekund wróci do 2. Tak ma być |
| backup `Error`, w logach `error parsing uri` albo `authentication failed` | adres bazy z klucza `uri` w Secrecie, w komendzie w cudzysłowie: `--uri="$MONGODB_URI"` |
