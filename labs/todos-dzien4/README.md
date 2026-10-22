# ToDos · dzień 4 — bez roota, bez tokenu, bez zbędnego ruchu

**Cel:** ToDos z wczoraj działa tak samo, ale ciaśniej. Każdy składnik ma własne konto bez tokenu do API, żaden kontener nie działa jako root i każdy przechodzi Pod Security `restricted`. Do podów ToDos wchodzi tylko ruch ze strzałek na diagramie. Wszystko z obiektów z dzisiaj.
**Środowisko:** wspólny klaster, Twój namespace. Nie piszesz `-n` ani `namespace:`.

Adres, Ingress, Secret, ConfigMap, HPA i dysk bazy zostają bez zmian. Zadania z wczoraj mają przetrwać: **nie usuwaj PVC `data-mongo-0`**.

Tu masz tylko wymagania. Jak je spełnisz, decydujesz sam. Utknąłeś: gotowe manifesty i opis są w [`rozwiazanie/`](rozwiazanie/). Zajrzyj najpierw do jednego pliku, a nie od razu do wszystkich.

```
Traefik (ns traefik) ──:8080──► web ──:3001──► api ──:27017──► mongo-0 ──► PVC data-mongo-0
                                                  (*) Job mongo-backup ──:27017──┘
każdy inny pod ──✕──► web, api, mongo                 NetworkPolicy: default-deny dla podów ToDos
każdy pod ToDos: własny ServiceAccount bez tokenu, UID ≠ 0, Pod Security restricted
```

**Od trenera na czacie:** nic nowego. Adres ten sam: `https://todos-<login>.<DOMENA>`.

## Zanim zaczniesz

ToDos z dnia 3 musi działać:

```bash
kubectl get sts,deploy,svc,ingress,hpa -l app.kubernetes.io/part-of=todos   # StatefulSet mongo, 2 Deploymenty, 3 Service, Ingress, HPA
kubectl get pods -l app.kubernetes.io/part-of=todos                         # wszystko Running i READY
curl -s https://todos-<login>.<DOMENA>/api/todos                            # Twoje zadania z wczoraj
```

Nie masz go albo nie działa: wdróż [`../todos-dzien3/rozwiazanie/`](../todos-dzien3/rozwiazanie/) (polecenia w jego README, ok. 5 minut).

Usuń to, co zostało z labów 13–16. Polityki z lab15 i pody bez `securityContext` zaciemnią Ci wyniki testów:

```bash
kubectl delete deploy,sts,ds,job,pod,svc -l 'app.kubernetes.io/part-of!=todos'
kubectl delete networkpolicy -l 'app.kubernetes.io/part-of!=todos'
kubectl get networkpolicy                        # pusto
kubectl get namespace <login> --show-labels      # warn i audit: baseline, bez enforce (jak po lab14)
```

## Wymagania

**Wszystkie nowe obiekty**
- mają etykietę `app.kubernetes.io/part-of: todos`, także pody z szablonów (ServiceAccounty i NetworkPolicy też).

**Własne konto dla każdego składnika**
- ServiceAccount dla api, web i mongo (a w zadaniu z gwiazdką z dnia 3 także dla CronJobu backupu), pody używają swojego konta zamiast `default`,
- w żadnym podzie ToDos nie ma tokenu do API: katalogu `/var/run/secrets/kubernetes.io/serviceaccount` nie ma (`automountServiceAccountToken: false`),
- **bez Role i RoleBindingu.** ToDos nie rozmawia z API Kubernetesa: api gada z Mongo, web z api, a konfigurację dostają przez zmienne środowiskowe. Konto bez żadnego RoleBindingu nie może nic poza podstawowym odczytem informacji o API, i o to chodzi. Rola byłaby potrzebna, gdyby aplikacja sama czytała obiekty z API: np. ConfigMapę „na żywo”, listę podów do wykrywania usług, Lease przy wyborze lidera, albo gdyby był to operator czy Job z `kubectl` w środku. Wtedy Role z tylko tymi czasownikami i zasobami, które są potrzebne, i sprawdzenie `kubectl auth can-i --as=system:serviceaccount:<login>:<konto>` jak w lab13.

**Każdy pod przechodzi Pod Security `restricted`** (api, web, mongo, a z gwiazdką także pod backupu)
- na poziomie poda: `runAsNonRoot: true`, **liczbowe** `runAsUser` i `runAsGroup` zgodne z użytkownikiem z obrazu, `seccompProfile: RuntimeDefault`, a tam, gdzie pod pisze na PVC (mongo, backup), `fsGroup`,
- na poziomie kontenera: `allowPrivilegeEscalation: false`, `capabilities.drop: ["ALL"]`, `readOnlyRootFilesystem: true`. Tam, gdzie program musi coś zapisać, dostaje wolumen `emptyDir` w tym jednym katalogu. Których? Dowiesz się z logów (`Read-only file system`),
- jakie UID mają obrazy, sprawdź sam, zanim cokolwiek zmienisz:
  ```bash
  kubectl exec deploy/api -- id
  kubectl exec deploy/web -- id
  kubectl exec mongo-0 -- id mongodb      # baza startuje jako root i dopiero entrypoint przechodzi na mongodb
  ```
- zadania z wczoraj zostają na liście po zmianie.

> **Pułapka: `USER node`.** Dockerfile api kończy się `USER node`: to nazwa, nie liczba. Z samym `runAsNonRoot: true` kubelet nie umie sprawdzić, czy `node` to nie root, i nie uruchomi kontenera (`CreateContainerConfigError`, `image has non-numeric user (node)`). Dlatego `runAsUser` liczbowo, zgodnie z `id` z obrazu. Ta sama zasada dla każdego obrazu, który ma użytkownika po nazwie.

**Etykieta Pod Security na Twoim namespace**
- `warn` i `audit` na poziomie `restricted` (zmieniasz tylko te dwie etykiety, `--overwrite`). Od teraz każdy `kubectl apply` z podem, który nie spełnia `restricted`, pokaże ostrzeżenie,
- sprawdź, co by się stało po włączeniu `enforce=restricted`, **bez włączania go**: `kubectl label namespace <login> pod-security.kubernetes.io/enforce=restricted --dry-run=server`. Przed zmianami lista podów ToDos z naruszeniami, po zmianach żadnego `Warning`,
- **nie ustawiaj `enforce` naprawdę**: jutrzejsze laby i pody testowe z `busybox` (np. ten z testu niżej) nie mają `securityContext` i nie powstałyby. Jak wygląda blokada, widziałeś na demie.

**NetworkPolicy dla ToDos**
- domyślnie nic nie wchodzi do podów ToDos: polityka wybiera pody po `app.kubernetes.io/part-of: todos`, a nie wszystkie (`podSelector: {}`). Pody z innych labów i pod solvera cert-managera, który odnawia certyfikat `todos-tls`, zostają bez zmian,
- do web wchodzi tylko ruch z namespace'u `traefik` (wybierz go po etykiecie `kubernetes.io/metadata.name`), do api tylko z web, do mongo tylko z api (i z gwiazdką z poda backupu),
- porty w politykach to porty **podów** (`containerPort`), nie Service. Sprawdź je w swoich manifestach z dnia 3,
- ruch wychodzący zostaje wolny (zamykasz go w zadaniu z gwiazdką).

**(\*) Ruch wychodzący**
- pody ToDos wychodzą tylko tam, gdzie wskazują strzałki: web do api, api (i backup) do mongo. Bez reguły na DNS (kube-dns w `kube-system`, UDP i TCP 53) web nie znajdzie `api`, a api nie znajdzie `mongo`,
- api nie dojdzie do internetu.

**(\*) Downward API**
- api ma w zmiennych `POD_NAME` i `NODE_NAME`: nazwę swojego poda i węzła, bez tokenu i bez uprawnień do API.

**(\*) Skan własnych manifestów**
- `trivy config` i `kubescape scan framework nsa` na katalogu z Twoimi plikami z dnia 3 i z dnia 4. Ile znalezisk HIGH było wczoraj, a ile jest dziś? Które z pozostałych pomijasz i dlaczego? (lab14, krok 3)

Ściąga: `kubectl explain pod.spec.securityContext`, `kubectl explain pod.spec.containers.securityContext`, `kubectl explain networkpolicy.spec.ingress`, `kubectl explain serviceaccount`, wzorce w [`przyklady/k8s/`](../../przyklady/k8s/) (`17-rbac`, `18-pod-security`, `19-networkpolicy`, `21-downward-api`).

## Jak sprawdzić

```bash
kubectl get sa,networkpolicy -l app.kubernetes.io/part-of=todos
kubectl get pods -l app.kubernetes.io/part-of=todos \
  -o custom-columns=POD:.metadata.name,SA:.spec.serviceAccountName,UID:.spec.securityContext.runAsUser
kubectl exec deploy/api -- ls /var/run/secrets/kubernetes.io/serviceaccount     # No such file or directory
kubectl exec deploy/api -- touch /x                                            # Read-only file system
kubectl label namespace <login> pod-security.kubernetes.io/enforce=restricted --dry-run=server   # bez Warning
curl -s https://todos-<login>.<DOMENA>/api/todos                               # zadania z wczoraj są
```

**Sieć: kto się dobija, a kto nie.** Pod testowy nie jest ani web, ani api (ostrzeżenie Pod Security przy `kubectl run` jest w porządku: to tylko `warn`):

```bash
kubectl run nptest --rm -it --restart=Never --image=busybox:1.37 -- sh -c '
  for c in mongo:27017 api:3001 web:80; do
    nc -z -w 3 ${c%:*} ${c#*:} && echo "$c OTWARTE" || echo "$c zablokowane"
  done'
```

Wszystkie trzy `zablokowane`, a strona w przeglądarce działa i dodaje zadania. Generator ruchu z wczorajszego testu HPA też dostanie teraz timeout: tak ma być.

**(\*) Backup po zmianach:**

```bash
kubectl create job --from=cronjob/mongo-backup backup-d4
kubectl logs -f job/backup-d4                # „done dumping…”, nowy plik właściciela mongodb obok wczorajszych
```

## SUKCES

ToDos działa pod tym samym adresem z wczorajszymi zadaniami, pody ToDos mają własne konta bez tokenu, `--dry-run=server` z `enforce=restricted` nie zgłasza żadnego poda, a `nptest` dostaje `zablokowane` do mongo, api i web. **Wklej na czat** wynik `kubectl label namespace <login> pod-security.kubernetes.io/enforce=restricted --dry-run=server`.

Nie usuwaj ToDos. Zostaje na jutro. Etykiety `warn`/`audit` `restricted` możesz zostawić (tylko ostrzegają). Jeśli jutro ostrzeżenia będą przeszkadzać, wróć do stanu z początku szkolenia:

```bash
kubectl label namespace <login> pod-security.kubernetes.io/warn=baseline pod-security.kubernetes.io/audit=baseline --overwrite
```

## Dla chętnych

- **Co może konto bez ról?** `kubectl auth can-i --list --as=system:serviceaccount:<login>:api`. Skąd te kilka linii, skoro nie ma żadnego RoleBindingu? A `kubectl auth can-i get configmaps --as=…`?
- **port-forward a NetworkPolicy.** `kubectl port-forward svc/web 8080:80` i `curl localhost:8080/api/health`. Działa, choć do web wpuszczasz tylko Traefika. Dlaczego? (Podpowiedź: skąd przychodzi ruch z port-forward do kontenera.)
- **Kubescape na klastrze.** `kubescape scan framework nsa --include-namespaces <login>`: co widzi w działających obiektach, czego nie było w plikach?
- **Bez `fsGroupChangePolicy`.** Po co `OnRootMismatch`? Co kubelet robi z każdym plikiem na dysku przy każdym starcie poda bez tego pola, gdy baza ma milion plików?

## Gdy coś nie działa

| Objaw | Co zrobić |
|---|---|
| api `CreateContainerConfigError`, w `describe` `image has non-numeric user (node), cannot verify user is non-root` | brak `runAsUser`: dopisz `runAsUser: 1000` (`id` z obrazu) |
| pod nie powstaje, w `kubectl describe rs`/`sts` `error looking up service account <login>/api` | najpierw ServiceAccounty, potem Deploymenty: `kubectl apply` pliku z kontami |
| web `Error`/`CrashLoopBackOff`, w logach `can't create /etc/nginx/conf.d/default.conf: Read-only file system` | entrypoint nginx generuje konfigurację z szablonu: `emptyDir` w `/etc/nginx/conf.d` |
| web albo mongo, w logach `Read-only file system` przy `/tmp/…` | `emptyDir` w `/tmp` |
| mongo-0 restartuje się, w logach `Read-only file system` albo `Permission denied` przy `/data/configdb` | `emptyDir` w `/data/configdb` (to `VOLUME` z obrazu) |
| mongo-0 restartuje się, `Permission denied` przy `/data/db` | `runAsUser: 999` i `fsGroup: 999`: pliki bazy z wczoraj należą do UID 999 |
| przez ok. pół minuty po `apply` strona zwraca błąd | StatefulSet wymienia `mongo-0` na nowy pod. Jedna replika bazy = przerwa przy każdej zmianie, jak wczoraj |
| przy `apply` `Warning: would violate PodSecurity "restricted:latest": …` | to `warn`, obiekt powstał. Przeczytaj, które pole, i popraw manifest |
| `--dry-run=server` zgłasza pody, które nie są ToDos | pozostałości z labów albo `nptest`/`load`: usuń je („Zanim zaczniesz”) |
| (\*) `--dry-run=server` zgłasza `Completed` pody `mongo-backup-…` | Joby backupu z wczoraj, ze starego szablonu bez `securityContext`. Po `apply` nowego CronJobu: `kubectl delete job -l app.kubernetes.io/part-of=todos` (archiwa na PVC zostają) |
| `kubectl label namespace` → `Forbidden` | napisz na czat |
| po NetworkPolicy strona nie odpowiada (502/504, timeout) | w polityce web port Service `80` zamiast `8080` albo zła etykieta namespace'u: `kubectl get ns traefik --show-labels` |
| strona się ładuje, ale lista pusta, `/api/…` → 502 | polityka api: etykieta `app: todos-web` w `from` albo port `3001` (`kubectl get pods --show-labels`) |
| api `0/1`, w logach `Brak połączenia z MongoDB` | polityka mongo: `from` z etykietą api, port `27017` |
| (\*) backup `Error` po NetworkPolicy, `server selection error` | do mongo wchodzi tylko api: dopisz pod backupu (`app: todos-backup`) |
| (\*) backup `Permission denied` przy `/backup/…` | `fsGroup: 999`: wczorajsze archiwa zapisał root |
| (\*) po polityce egress nic nie działa, w logach `host not found` / `getaddrinfo EAI_AGAIN` | brak reguły DNS: UDP **i** TCP 53 do `k8s-app: kube-dns` w `kube-system`, `namespaceSelector` i `podSelector` w jednym elemencie |
| polityka nie działa wcale | etykiety w `podSelector` (`kubectl get pods --show-labels`) i port poda, nie Service. Testuj nowym połączeniem |
