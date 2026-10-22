# ToDos · dzień 4 — rozwiązanie

Jedno z możliwych rozwiązań. Twoje może wyglądać inaczej (inne nazwy kont i polityk, jedna polityka zamiast czterech, mniej `emptyDir`, jeśli coś działa bez nich) i też jest dobre, jeśli spełnia wymagania z [`../README.md`](../README.md).

| Plik | Co w nim jest | Zmiana od wczoraj |
|---|---|---|
| `serviceaccounts.yaml` | ServiceAccounty `api`, `web`, `mongo` i (\*) `mongo-backup`, wszystkie z `automountServiceAccountToken: false` | nowy |
| `api.yaml` | Deployment i Service `api`: konto `api`, UID/GID 1000, system plików tylko do odczytu, (\*) `POD_NAME` i `NODE_NAME` z Downward API | `serviceAccountName`, `securityContext`, env |
| `web.yaml` | Deployment i Service `web`: konto `web`, UID/GID 101, `emptyDir` w `/tmp` i `/etc/nginx/conf.d` | `serviceAccountName`, `securityContext`, wolumeny |
| `mongo.yaml` | headless Service i StatefulSet `mongo`: konto `mongo`, UID/GID 999, `fsGroup: 999`, `emptyDir` w `/tmp` i `/data/configdb` | `serviceAccountName`, `securityContext`, wolumeny |
| `networkpolicy.yaml` | default-deny dla podów ToDos, traefik → web:8080, web → api:3001, api i (\*) backup → mongo:27017 | nowy |
| `networkpolicy-egress.yaml` | (\*) ruch wychodzący: DNS dla wszystkich podów ToDos, web → api, api i backup → mongo | nowy |
| `backup.yaml` | (\*) PVC `todos-backup` i CronJob `mongo-backup`: konto `mongo-backup`, UID/GID 999, `fsGroup: 999` | `serviceAccountName`, `securityContext` |
| `configmap.yaml`, `ingress.yaml`, `hpa.yaml` | jak wczoraj, dla kompletu | bez zmian |

Secret `todos-mongo` i PVC `data-mongo-0` z wczoraj zostają bez zmian. Zasoby (`resources`) też, więc quota jak wczoraj: `emptyDir` leży na dysku węzła i nie liczy się do quoty CPU ani pamięci.

## Wdrożenie

W `api.yaml` i `web.yaml` podmień `<REJESTR>`. Potem w tej kolejności:

```bash
kubectl label namespace <login> pod-security.kubernetes.io/enforce=restricted --dry-run=server   # PRZED: lista naruszeń
kubectl label namespace <login> pod-security.kubernetes.io/warn=restricted pod-security.kubernetes.io/audit=restricted --overwrite

kubectl apply -f serviceaccounts.yaml                 # najpierw konta: pod z nieistniejącym kontem nie powstanie
kubectl apply -f mongo.yaml
kubectl rollout status sts/mongo                      # mongo-0 wymieniony na nowy, ok. 30 s przerwy
kubectl apply -f api.yaml -f web.yaml
kubectl rollout status deploy/api; kubectl rollout status deploy/web
kubectl apply -f backup.yaml                          # (*) jeśli masz backup z dnia 3
kubectl delete job -l app.kubernetes.io/part-of=todos # (*) stare Joby backupu: ich pody (Completed) dry-run też zgłasza

kubectl label namespace <login> pod-security.kubernetes.io/enforce=restricted --dry-run=server   # PO: bez Warning
kubectl apply -f networkpolicy.yaml
kubectl apply -f networkpolicy-egress.yaml            # (*) opcjonalnie
```

Żaden `apply` po zmianie etykiet nie powinien pokazać `Warning: would violate PodSecurity`. Jeśli pokazuje, czytasz, które pole, i poprawiasz.

Test sieci (pod testowy dostanie ostrzeżenie `warn`, ale powstanie):

```bash
kubectl run nptest --rm -it --restart=Never --image=busybox:1.37 -- sh -c '
  for c in mongo:27017 api:3001 web:80; do
    nc -z -w 3 ${c%:*} ${c#*:} && echo "$c OTWARTE" || echo "$c zablokowane"
  done'
curl -s https://todos-<login>.<DOMENA>/api/todos      # zadania z wczoraj
```

## Jakie UID i skąd

| Obraz | Użytkownik w obrazie | `runAsUser` / `runAsGroup` | Gdzie pisze przy `readOnlyRootFilesystem` |
|---|---|---|---|
| `todos-api` (`node:22-alpine`) | `USER node` (nazwa!) = 1000:1000 | 1000 / 1000 | nigdzie |
| `todos-web` (`nginx-unprivileged`) | `USER 101` = nginx 101:101 | 101 / 101 | `/tmp` (pid, bufory), `/etc/nginx/conf.d` (konfiguracja z szablonu) |
| `mongo:7.0` | root, entrypoint przechodzi na `mongodb` = 999:999 | 999 / 999, `fsGroup: 999` | `/data/db` (PVC), `/tmp` (gniazdo, pliki startowe), `/data/configdb` |
| `mongo:7.0` w backupie | jak wyżej | 999 / 999, `fsGroup: 999` | `/backup` (PVC) |

Sprawdzone `kubectl exec … -- id` w działających podach. Na innej wersji obrazu sprawdź jeszcze raz: UID to szczegół obrazu, nie Kubernetesa.

## Dlaczego tak

- **ServiceAccount bez ról i bez tokenu.** Bez własnego konta pod dostaje `default` i token do API w `/var/run/secrets/kubernetes.io/serviceaccount`. Kto przejmie kontener, ma gotowe poświadczenia: dziś bez uprawnień, ale wystarczy, że ktoś kiedyś da kontu `default` rolę. Osobne konto na składnik daje osobną tożsamość (w logach audytu, w przyszłych rolach), a `automountServiceAccountToken: false` zabiera token. Role nie dodajemy, bo ToDos niczego z API nie czyta. Potrzebna byłaby dla aplikacji, która woła API (operator, Job z `kubectl`, wybór lidera przez Lease, wykrywanie podów), i wtedy tylko z koniecznymi czasownikami, sprawdzona `kubectl auth can-i --as`. Pole jest w ServiceAccount i w podzie: wystarczy jedno, w podzie wygrywa przy konflikcie, tu jest w obu dla czytelności.
- **Liczbowe `runAsUser`.** `runAsNonRoot: true` każe kubeletowi sprawdzić UID przed startem. Przy `USER node` kubelet nie zna UID (nazwa jest w `/etc/passwd` obrazu, do którego nie zagląda) i odmawia startu. `runAsUser` liczbowo usuwa problem i dokumentuje UID w manifeście.
- **Mongo od razu jako 999.** Wczoraj kontener startował jako root, a entrypoint robił `chown` na `/data/db` i przechodził na `mongodb` (`gosu`). Bez roota tego nie zrobi, więc prawo zapisu do PVC daje `fsGroup: 999`: kubelet ustawia grupę 999 na plikach dysku przy montowaniu. Wczorajsze pliki i tak należą do 999, a nowy, pusty dysk też zadziała (sprawdzone: inicjalizacja użytkownika root na pustym PVC przechodzi). `fsGroupChangePolicy: OnRootMismatch` pomija `chown` całego dysku, gdy katalog główny już ma dobrą grupę: przy dużej bazie to różnica między sekundami a minutami startu.
- **`readOnlyRootFilesystem` i `emptyDir`.** Atakujący nie dopisze nic do obrazu (skryptu, binarki, zmienionej konfiguracji). Każdy katalog, w którym program musi pisać, dostaje własny `emptyDir`; `sizeLimit` chroni węzeł przed zapchaniem dysku. Pułapka nginx: obraz web generuje `default.conf` z szablonu przy starcie. Bez zapisu do `/etc/nginx/conf.d` kontener kończy się błędem `can't create /etc/nginx/conf.d/default.conf: Read-only file system`.
- **`warn` i `audit`, bez `enforce`.** `warn` ostrzega przy każdym `apply`, `audit` zapisuje naruszenia w logu audytu klastra. `--dry-run=server` z `enforce` pokazuje, które działające pody zostałyby zablokowane przy następnym tworzeniu, bez blokowania czegokolwiek. `enforce` byłby właściwy na produkcji, ale na szkoleniu zablokowałby pody testowe i jutrzejsze laby.
- **Default-deny tylko dla ToDos.** `podSelector` po `app.kubernetes.io/part-of: todos`, a nie `{}`. Polityka na cały namespace zablokowałaby też pod solvera cert-managera (port 8089) przy odnawianiu certyfikatu `todos-tls` i pody z innych labów. W projekcie (lab20) jest wersja na cały namespace z osobną regułą dla solvera.
- **Porty podów.** NetworkPolicy działa na adresach i portach podów, po DNAT z Service: web to 8080 (Service 80), api 3001, mongo 27017.
- **Traefik po `kubernetes.io/metadata.name`.** Tę etykietę każdy namespace dostaje od Kubernetesa i nie da się jej zmienić. Etykiety typu `name: traefik` ktoś musiał nadać ręcznie.
- **Sondy dalej działają.** Kubelet sprawdza gotowość z węzła, a vpc-cni przepuszcza ten ruch mimo default-deny. Sprawdzone: pody `Ready` po `apply` polityk i po `kubectl delete pod mongo-0`.
- **(\*) Egress z DNS.** Po zamknięciu ruchu wychodzącego pierwsze, co przestaje działać, to DNS. `namespaceSelector` i `podSelector` w jednym elemencie listy (AND): tylko kube-dns z `kube-system`, nie cały `kube-system`. Mongo ma w efekcie tylko DNS, bo nigdzie się nie łączy.
- **(\*) Downward API.** Nazwa poda i węzła w zmiennych, bez tokenu i bez uprawnień do API. Aplikacja może je dopisywać do logów; teraz sprawdzisz je przez `kubectl exec deploy/api -- printenv POD_NAME NODE_NAME`.

## Skan: przed i po

`trivy config` na katalogu z plikami dnia 3: po 3 HIGH w każdym pliku z podem (root, eskalacja uprawnień, system plików do zapisu). Na plikach dnia 4: 0 HIGH. Zostają:

- KSV-0020/0021 (LOW): UID/GID ≤ 10000. Wymagałyby przebudowy obrazów z innym użytkownikiem; w labie pomijamy,
- KSV-0032…0035, 0125 (MEDIUM): obrazy spoza „zaufanego rejestru” i z Docker Hub (`mongo:7.0`). Polityka firmy, w labie pomijamy,
- KSV-0110 (LOW): brak `namespace` w YAML. Celowo, pracujesz w domyślnym namespace kontekstu,
- AVD-KSV-01010 w `configmap.yaml` (MEDIUM): skaner bierze `PORT` i `API_PORT` za hasła (pasuje mu słowo z listy). Fałszywy alarm.

`kubescape scan framework nsa`: dzień 3 ok. 70%, dzień 4 100% (0 nieudanych kontroli).

## Sprzątanie (dopiero po szkoleniu)

```bash
kubectl delete -f .                     # Deploymenty, StatefulSet, Service, HPA, CronJob, Ingress, ServiceAccounty, NetworkPolicy
kubectl delete pvc data-mongo-0 todos-backup
kubectl delete secret todos-mongo
kubectl label namespace <login> pod-security.kubernetes.io/warn=baseline pod-security.kubernetes.io/audit=baseline --overwrite
```
