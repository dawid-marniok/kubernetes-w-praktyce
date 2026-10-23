# lab17 — Helm: własny chart, upgrade i rollback

**Cel:** pakujesz aplikację w chart, wdrażasz ją jako release, zmieniasz wartości i cofasz zepsutą zmianę jedną komendą. Potem stawiasz cudzy, gotowy chart z rejestru: RabbitMQ albo bazę danych.

**Po labie masz:** chart `todos-chart` i release `t1` z czterema rewizjami w historii oraz drugi release z gotowego chartu (RabbitMQ, PostgreSQL albo Valkey).

Na tym labie chart wdraża zwykły `nginx:1.29`. Swój ToDos zapakujesz w chart po południu (`labs/todos-dzien5/`), tu chodzi o mechanikę Helma.

## Zanim zaczniesz

```bash
helm version --short          # v4.x (v3.1x też zadziała, różnice opisane niżej)
kubectl config view --minify -o jsonpath='{..namespace}'; echo   # Twój login
helm list                     # pusto
```

Pracujesz w swoim namespace (domyślny w kontekście), więc w komendach nie ma `-n`. Ściąga składni szablonów: `docs/k8s/helm/skladnia.md`.

## Poziom podstawowy

### 1. Szkielet chartu

```bash
helm create todos-chart
tree todos-chart            # albo: find todos-chart
```

Przeczytaj trzy pliki: `values.yaml`, `templates/deployment.yaml` i `templates/_helpers.tpl`. Znajdź w szablonie miejsce, z którego bierze się obraz i liczba replik.

### 2. Wartości: obraz i zasoby

W `todos-chart/values.yaml` ustaw:

- `image.repository: nginx` i `image.tag: "1.29"` (w cudzysłowie, inaczej to liczba),
- w `todos-chart/Chart.yaml`: `appVersion: "1.29"` (wersja aplikacji; `version` to wersja samego chartu),
- `resources` z requests i limits zamiast `resources: {}`: requests `cpu: 50m`, `memory: 64Mi`, limits `cpu: 200m`, `memory: 128Mi`.

### 3. Sprawdź bez klastra

```bash
helm lint ./todos-chart
helm template t1 ./todos-chart | grep 'image:'      # druga linia (busybox) to pod testowy z templates/tests/
helm template t1 ./todos-chart | grep -A6 "resources:"
```

✅ `helm lint` bez błędów, w wyniku `image: "nginx:1.29"` i Twoje zasoby.

### 4. Instalacja

```bash
helm upgrade --install t1 ./todos-chart --wait
helm list
kubectl get deploy,pods,svc -l app.kubernetes.io/instance=t1
```

✅ `STATUS deployed`, `REVISION 1`, jeden pod `Running`.

### 5. Upgrade: trzy repliki

```bash
helm upgrade t1 ./todos-chart --set replicaCount=3 --wait
kubectl get pods -l app.kubernetes.io/instance=t1
helm history t1
```

✅ Trzy pody, w historii rewizje 1 i 2.

### 6. Zepsuty upgrade

```bash
helm upgrade t1 ./todos-chart --set replicaCount=3 --set image.tag=9.99
kubectl get pods -l app.kubernetes.io/instance=t1      # po chwili: ErrImagePull / ImagePullBackOff
helm history t1
```

Zanotuj: jaki `STATUS` ma rewizja 3 w `helm history`? Dlaczego Helm uważa, że się udało?

### 7. Rollback

```bash
helm rollback t1 1 --wait
helm history t1
kubectl get pods -l app.kubernetes.io/instance=t1
```

✅ Rewizja 4 z opisem `Rollback to 1`, jeden pod z `nginx:1.29`.

### 8. Gdzie Helm trzyma historię

```bash
helm get values t1            # tylko Twoje nadpisania
helm get values t1 --all      # wszystkie wartości
helm get manifest t1 | grep image:
kubectl get secret -l owner=helm
```

Ile Secretów widzisz i dlaczego tyle?

### 9. Gotowy chart z rejestru: wybierz jeden

Własny chart piszesz rzadko. Częściej instalujesz cudzy i nadpisujesz kilka wartości. Charty Bitnami odpadają (darmowe obrazy z wersjami zniknęły w 08.2025), więc bierzesz charty [CloudPirates](https://artifacthub.io/packages/search?org=cloudpirates): otwarte, z oficjalnymi obrazami, w rejestrze OCI.

| Wybór | Release | Chart (OCI) | Wersja chartu | Aplikacja |
|---|---|---|---|---|
| RabbitMQ (kolejka, panel www) | `mq` | `oci://registry-1.docker.io/cloudpirates/rabbitmq` | `0.21.32` | RabbitMQ 4.4.0 |
| PostgreSQL | `pg` | `oci://registry-1.docker.io/cloudpirates/postgres` | `0.21.2` | PostgreSQL 18.6 |
| Valkey (otwarty fork Redisa) | `kv` | `oci://registry-1.docker.io/cloudpirates/valkey` | `0.25.16` | Valkey 9.1.0 |

Poniżej przykład dla RabbitMQ. Dla innego wyboru podmień nazwę chartu, release i plik wartości według tabeli.

**a) Co chart umie, zanim cokolwiek zainstalujesz**

```bash
helm show chart oci://registry-1.docker.io/cloudpirates/rabbitmq --version 0.21.32
helm show values oci://registry-1.docker.io/cloudpirates/rabbitmq --version 0.21.32 > rabbitmq-defaults.yaml
grep -n -E '^(image|auth|persistence|resources):' -A4 rabbitmq-defaults.yaml
```

Porównaj z gotowym plikiem `gotowy-chart/values-rabbitmq.yaml`: nadpisujesz tylko `imagePullPolicy`, hasło, rozmiar dysku i zasoby. Obraz i reszta zostają z chartu. Zwróć uwagę na `image.tag`: autor chartu przypiął wersję i digest (`@sha256:…`), więc ta sama wersja chartu zawsze daje ten sam obraz.

**b) Twoje wartości i podgląd**

```bash
cp gotowy-chart/values-rabbitmq.yaml my-rabbitmq.yaml
helm template mq oci://registry-1.docker.io/cloudpirates/rabbitmq --version 0.21.32 -f my-rabbitmq.yaml | grep -E 'image:|imagePullPolicy:|storage:'
```

✅ Obraz `docker.io/rabbitmq:4.4.0-management@sha256:…` prosto z chartu, `imagePullPolicy: IfNotPresent`, dysk `1Gi`.

**c) Instalacja i sprawdzenie**

```bash
helm upgrade --install mq oci://registry-1.docker.io/cloudpirates/rabbitmq --version 0.21.32 -f my-rabbitmq.yaml --wait --timeout 5m
helm list
kubectl get statefulset,pods,pvc,svc -l app.kubernetes.io/instance=mq
```

✅ Release `mq` `deployed`, pod `mq-rabbitmq-0` `Running` i `1/1`, PVC `data-mq-rabbitmq-0` `Bound` (StatefulSet z dnia 3, tylko napisany przez kogoś innego).

Czy działa:

| Wybór | Sprawdzenie |
|---|---|
| RabbitMQ | `kubectl exec mq-rabbitmq-0 -- rabbitmq-diagnostics -q ping` → `Ping succeeded`. Panel: `kubectl port-forward svc/mq-rabbitmq 15672:15672` → http://localhost:15672, login `admin`, hasło z pliku wartości. Zakładka **Queues** → dodaj kolejkę `test`, opublikuj w niej wiadomość (**Publish message**) i odbierz ją (**Get messages**) |
| PostgreSQL | `kubectl exec pg-postgres-0 -- psql -U postgres -c 'select version();'` → `PostgreSQL 18.6` (w podzie chart ufa połączeniom lokalnym, z innego poda potrzebne hasło z pliku wartości). Potem `-c 'create table kurs(dzien int); insert into kurs values (5);'` |
| Valkey | `kubectl exec kv-valkey-0 -- valkey-cli -a szkolenie-valkey --no-auth-warning SET kurs k8s` → `OK`, potem `… GET kurs` → `"k8s"` |

**d) Upgrade cudzego chartu**

Zmień w `my-rabbitmq.yaml` (albo swoim pliku) limit pamięci na `640Mi` i:

```bash
helm upgrade mq oci://registry-1.docker.io/cloudpirates/rabbitmq --version 0.21.32 -f my-rabbitmq.yaml --wait --timeout 5m
helm history mq
helm get values mq
```

Zanotuj: co zrobił StatefulSet z podem? Czy dane (kolejka `test`, klucz `kurs`, baza) przetrwały restart poda? Dlaczego?

### SUKCES

- [ ] `helm history t1` pokazuje rewizje 1–4, ostatnia `Rollback to 1`
- [ ] działa jeden pod `nginx:1.29`
- [ ] umiesz powiedzieć, dlaczego rewizja 3 miała status `deployed`, choć pody nie wstały
- [ ] release z gotowego chartu (`mq`, `pg` albo `kv`) ma 2 rewizje, pod `Running`, sprawdzenie z tabeli przechodzi

## Dla chętnych

**A. Wartości na środowiska.** Utwórz `values-dev.yaml` (1 replika) i `values-prod.yaml` (3 repliki, większe limity). Porównaj:

```bash
diff <(helm template t1 ./todos-chart -f values-dev.yaml) <(helm template t1 ./todos-chart -f values-prod.yaml)
helm upgrade t1 ./todos-chart -f values-prod.yaml --wait
helm upgrade t1 ./todos-chart --wait          # bez -f: co się stało z liczbą replik?
```

**B. Automatyczny rollback.** Powtórz zepsuty upgrade z krokiem bezpieczeństwa:

```bash
helm upgrade t1 ./todos-chart --set image.tag=9.99 --rollback-on-failure --timeout 90s   # Helm 4
# Helm 3: --atomic --timeout 90s
helm history t1
```

**C. Chart z klasycznego repozytorium HTTP** (krok 9 był z rejestru OCI; tu `helm repo add` i `index.yaml`):

```bash
helm repo add podinfo https://stefanprodan.github.io/podinfo
helm search repo podinfo --versions | head -3
helm show values podinfo/podinfo --version 6.15.0 | less
helm upgrade --install pi podinfo/podinfo --version 6.15.0 \
  --set replicaCount=2 --set ui.message="Czesc od <login>" --wait
kubectl port-forward svc/pi-podinfo 9898:9898      # http://localhost:9898
```

Ten sam chart jest w rejestrze OCI, bez `repo add`: `helm show chart oci://ghcr.io/stefanprodan/charts/podinfo --version 6.15.0`.

**D. Paczka i OCI.** `helm package ./todos-chart` → `todos-chart-0.1.0.tgz`. Chart trafia do tego samego ECR co obrazy (repozytorium `<login>/todos-chart` powstanie samo):

```bash
aws ecr get-login-password --profile szkolenie --region eu-central-1 \
  | helm registry login --username AWS --password-stdin <konto>.dkr.ecr.eu-central-1.amazonaws.com
helm push todos-chart-0.1.0.tgz oci://<REJESTR>        # <REJESTR> z karty, kończy się na /<login>
helm show chart oci://<REJESTR>/todos-chart --version 0.1.0
```

Podbij `version` w `Chart.yaml`, spakuj i wypchnij jeszcze raz: w ECR są dwie wersje.

## Gdy coś nie działa

**Gotowe wzorce manifestów:** [`przyklady/k8s/22-helm/`](../../przyklady/k8s/22-helm/). Skopiuj i przerób, zamiast pisać YAML od zera.

| Objaw | Co zrobić |
|---|---|
| `cannot re-use a name that is still in use` | Release już istnieje: `helm upgrade --install` zamiast `helm install` |
| `exceeded quota` przy upgrade | Za dużo replik albo za duże requests względem quoty: `kubectl describe quota` |
| `helm lint`: `found character that cannot start any token` | Tabulator w YAML-u albo złe wcięcie w `values.yaml` |
| W `helm template` tag `1.3` zamiast `1.30` | Tag bez cudzysłowu został liczbą: `tag: "1.30"` |
| `UPGRADE FAILED: … has no deployed releases` | Pierwsza instalacja się nie udała: `helm uninstall t1` i od nowa |
| `unknown flag: --rollback-on-failure` | Masz Helm 3: użyj `--atomic` |
| Krok 9: pod w `ImagePullBackOff`, w zdarzeniach `429 Too Many Requests` | Limit pobrań Docker Hub z adresu klastra: odczekaj kilka minut, kubelet sam ponowi pobranie (`kubectl describe pod mq-rabbitmq-0`) |
| Krok 9: `--wait` kończy się `timed out`, pod `Pending` | PVC czeka na dysk (`kubectl get pvc`, `kubectl describe pod mq-rabbitmq-0`); `exceeded quota` → usuń zbędne pody albo zmniejsz `resources` |
| Krok 9: `Error: ... 429 Too Many Requests` przy `helm show`/`install` | Limit Docker Hub na pobranie chartu: odczekaj minutę albo poproś prowadzącego o paczkę `.tgz` (`helm install mq ./rabbitmq-0.21.32.tgz -f my-rabbitmq.yaml`) |
| Krok 9: RabbitMQ restartuje się (`OOMKilled`) | Limit pamięci za niski: zostaw `512Mi` lub więcej |

## Sprzątanie

```bash
helm uninstall t1
helm uninstall pi 2>/dev/null
helm uninstall mq pg kv --ignore-not-found
kubectl delete pvc data-mq-rabbitmq-0 data-pg-postgres-0 data-kv-valkey-0 --ignore-not-found   # helm uninstall nie usuwa PVC ze StatefulSetu
rm -f my-rabbitmq.yaml my-postgres.yaml my-valkey.yaml rabbitmq-defaults.yaml
```
