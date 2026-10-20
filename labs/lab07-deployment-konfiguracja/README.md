# Lab 07 — Deployment, rollback i konfiguracja z zewnątrz

**Cel:** wdrażasz nową wersję bez przestoju, cofasz ją, dodajesz sondy i podajesz aplikacji konfigurację z ConfigMapy oraz hasło z Secretu — bez przebudowy obrazu.
**Środowisko:** wspólny klaster, Twój namespace. Nie piszesz `-n` ani `namespace:`.

**Start:** `cd labs/lab07-deployment-konfiguracja` i `mkdir -p moje` — tu zapisujesz swoje pliki (katalog `moje/` jest w `.gitignore`).

Pliki startowe w tym katalogu:
| Plik | Do czego |
|---|---|
| `httpd.conf` | konfiguracja Apache (domyślna z obrazu `httpd:2.4` + dwie zmiany na końcu) |
| `apache-deployment.yaml` | Apache, który czyta `httpd.conf` z ConfigMapy `lab07-httpd-conf` |
| `mysql-deployment.yaml` | MySQL 8.4, który bierze hasło roota z Secretu `lab07-mysql` |

**Zanim zaczniesz:** usuń pody z lab06 (`kubectl get pods` → `kubectl delete pod …`). Obrazy z tagiem, zawsze `resources`, etykiety `app: lab07-…`.

---

## Poziom podstawowy

### Krok 1. Deployment, aktualizacja i rollback
1. Napisz Deployment `lab07-web`: 3 repliki, `nginx:1.28`, etykiety poda `app: lab07-web` i `version: v1`, port 80, requests `50m`/`32Mi`, limits `100m`/`64Mi`. Szkielet:
   ```bash
   kubectl create deployment lab07-web --image=nginx:1.28 --replicas=3 --port=80 --dry-run=client -o yaml > moje/lab07-web.yaml
   ```
   Etykietę `app: lab07-web` kubectl wstawi sam. Dopisz `version: v1` w `spec.template.metadata.labels`, a w miejsce `resources: {}` — requests i limits.
2. Zastosuj i sprawdź, co powstało:
   ```bash
   kubectl apply -f moje/lab07-web.yaml
   kubectl annotate deploy/lab07-web kubernetes.io/change-cause="nginx 1.28 - start" --overwrite
   kubectl get deploy,rs,pods -l app=lab07-web
   ```
3. Nowa wersja — obserwuj w drugim terminalu `kubectl get pods -l app=lab07-web -w`:
   ```bash
   kubectl set image deploy/lab07-web nginx=nginx:1.29
   kubectl annotate deploy/lab07-web kubernetes.io/change-cause="nginx 1.29" --overwrite
   kubectl rollout status deploy/lab07-web
   kubectl get rs -l app=lab07-web
   kubectl rollout history deploy/lab07-web
   ```
4. Cofnij i sprawdź, jaki obraz jest teraz w Deploymencie:
   ```bash
   kubectl rollout undo deploy/lab07-web
   kubectl rollout status deploy/lab07-web
   kubectl get deploy lab07-web -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
   kubectl rollout history deploy/lab07-web
   ```
- Ile ReplicaSetów masz po kroku 3? Ile replik ma każdy?
- Jakie numery rewizji widzisz po undo i dlaczego jednego brakuje?

### Krok 2. Sondy
W swoim pliku: obraz `nginx:1.29`, adnotacja `kubernetes.io/change-cause: "sondy"` w `metadata.annotations` i sondy w kontenerze:
- `readinessProbe`: HTTP GET `/`, port 80, `initialDelaySeconds: 5`, `periodSeconds: 5`
- `livenessProbe`: HTTP GET `/`, port 80, `initialDelaySeconds: 30`, `periodSeconds: 10`
```bash
kubectl apply -f moje/lab07-web.yaml
kubectl rollout status deploy/lab07-web
kubectl describe pod -l app=lab07-web | grep -E 'Liveness|Readiness'
```
- Dlaczego tym razem nie trzeba było usuwać podów, jak w lab06?

### Krok 3. ConfigMap z pliku
```bash
kubectl create configmap lab07-httpd-conf --from-file=httpd.conf
kubectl apply -f apache-deployment.yaml
kubectl rollout status deploy/lab07-apache
kubectl exec deploy/lab07-apache -- head -2 /usr/local/apache2/conf/httpd.conf
```
Sprawdź, czy Apache używa tej konfiguracji (w obrazie httpd nie ma `curl`, więc z laptopa):
```bash
kubectl port-forward deploy/lab07-apache 8081:80
# w drugim terminalu:
curl -sI http://localhost:8081 | grep -i server
```
- Co jest w nagłówku `Server`? Którą linią z `httpd.conf` to ustawiłeś?

### Krok 4. Secret z hasłem
Wymyśl własne hasło (to ćwiczenie — nie używaj prawdziwego):
```bash
kubectl create secret generic lab07-mysql --from-literal=root-password=changeme-<login>
kubectl apply -f mysql-deployment.yaml
kubectl get pods -l app=lab07-mysql -w        # start ok. 30–60 s, Ctrl-C po Running 1/1
kubectl exec deploy/lab07-mysql -- printenv MYSQL_ROOT_PASSWORD
kubectl exec deploy/lab07-mysql -- mysql -uroot -pchangeme-<login> -e 'select version();'
```
- Gdzie w `mysql-deployment.yaml` jest hasło? (Nie ma go — jest tylko odwołanie do Secretu.)

**SUKCES:** `rollout history` ma co najmniej 3 rewizje z opisem, Apache odpowiada nagłówkiem `Server: Apache` (bez wersji) z konfiguracji z ConfigMapy, MySQL ma hasło z Secretu.

---

## Dla chętnych

1. **Zmienne i pliki z ConfigMapy.** Utwórz ConfigMapę `lab07-config` z kluczami `LOG_LEVEL=info` i `FEATURE_X=true` i pod `lab07-config` (`nginx:1.29`), który ma ją jednocześnie jako zmienne (`envFrom`) i jako wolumen w `/etc/lab07` (bez `subPath`). Zmień `LOG_LEVEL` na `debug` (`kubectl edit configmap lab07-config`) i po ok. minucie porównaj:
   ```bash
   kubectl exec lab07-config -- sh -c 'echo env=$LOG_LEVEL; echo plik=$(cat /etc/lab07/LOG_LEVEL)'
   ```
   Co się odświeżyło, a co nie? A w Apache z kroku 3 (montowanym przez `subPath`)?
2. **Secret to base64.** `kubectl get secret lab07-mysql -o yaml`, potem odkoduj wartość: `kubectl get secret lab07-mysql -o jsonpath='{.data.root-password}' | base64 -d`. Kto w Twoim namespace może to zrobić?
3. **ReplicaSet adoptuje cudze pody.** Utwórz goły pod `lab07-sierota` z etykietą `app: lab07-rs`, a potem ReplicaSet `lab07-rs` z `replicas: 3` i selektorem `app: lab07-rs`. Ile podów utworzył ReplicaSet? Kto jest właścicielem sieroty (`kubectl get pod lab07-sierota -o jsonpath='{.metadata.ownerReferences[0].name}'`)?
4. **Zły tag.** `kubectl set image deploy/lab07-web nginx=nginx:111`. Ile podów działa, ile nie? Co pokazuje `kubectl rollout status`? Wróć przez `rollout undo`.

---

## Wskazówki

**Gotowe wzorce manifestów:** [`przyklady/k8s/03-deployment/`](../../przyklady/k8s/03-deployment/), [`przyklady/k8s/02-replicaset/`](../../przyklady/k8s/02-replicaset/), [`przyklady/k8s/04-configmap-secret/`](../../przyklady/k8s/04-configmap-secret/). Skopiuj i przerób, zamiast pisać YAML od zera.

- Ściągi: [`docs/k8s/deployment/strategie-wdrozen.md`](../../docs/k8s/deployment/strategie-wdrozen.md) (RollingUpdate, Recreate, blue/green, canary) i [`docs/k8s/deployment/sondy.md`](../../docs/k8s/deployment/sondy.md).
- `kubectl explain deployment.spec.strategy.rollingUpdate` — pola strategii.
- Etykieta `version: v1` w podach nie jest potrzebna do rolloutu. Przyda się w lab08: na etykiecie wersji opiera się blue/green.
- Adnotacja `change-cause` przechodzi na kolejną rewizję, jeśli jej nie nadpiszesz. Po każdej zmianie: nowy opis (`--overwrite`) albo adnotacja w pliku.
- `--record` przy `kubectl set image` jest wycofane — opis zmiany daje adnotacja.
- Selektor Deploymentu (`spec.selector`) jest niezmienny. Zmiana etykiet w selektorze → `field is immutable`; wtedy `kubectl delete deploy …` i `apply` od nowa.
- `rollout undo` ostrzega o `last-applied-configuration`: po cofnięciu popraw też swój plik, inaczej następny `apply` wróci do złej wersji.
- MySQL potrzebuje ok. 450 MiB pamięci. Przy mniejszym limicie dostaniesz `OOMKilled`; przy braku miejsca w quocie (`exceeded quota`) zmniejsz `lab07-web` do 1 repliki.
- Zmienne z ConfigMapy/Secretu kontener czyta raz, przy starcie. Po zmianie: `kubectl rollout restart deploy/<nazwa>`.

## Sprzątanie
```bash
kubectl delete deploy lab07-web lab07-apache lab07-mysql
kubectl delete configmap lab07-httpd-conf
kubectl delete secret lab07-mysql
# dla chętnych:
kubectl delete pod lab07-config lab07-sierota --ignore-not-found
kubectl delete rs lab07-rs --ignore-not-found
kubectl delete configmap lab07-config --ignore-not-found
```
