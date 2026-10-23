# ToDos · dzień 5 — rozwiązanie

Jedno z możliwych rozwiązań. Twój chart może wyglądać inaczej (inne nazwy wartości, jeden plik szablonu zamiast kilku, bez backupu) i też jest dobry, jeśli spełnia wymagania z [`../README.md`](../README.md).

| Plik | Co w nim jest |
|---|---|
| `todos/Chart.yaml` | nazwa `todos`, wersja chartu 0.1.0, `appVersion` 1.0.0 = domyślny tag obrazów |
| `todos/values.yaml` | wartości domyślne z komentarzami; `registry` i `host` puste, wymagane |
| `todos/templates/_helpers.tpl` | etykiety (`part-of: todos`, `managed-by`, `helm.sh/chart`), pełna nazwa obrazu z `required`, wspólny `securityContext` kontenera |
| `todos/templates/config.yaml` | ConfigMap `todos-config`, ServiceAccounty `api`, `web`, `mongo` (i `mongo-backup` przy backupie) |
| `todos/templates/api.yaml` | Deployment, Service i HPA `api`; przy `otel.enabled` adnotacja OpenTelemetry i 384Mi |
| `todos/templates/web.yaml` | Deployment i Service `web`, Ingress `todos` z TLS |
| `todos/templates/mongo.yaml` | headless Service i StatefulSet `mongo` |
| `todos/templates/networkpolicy.yaml` | polityki z dnia 4; egress i OTLP za włącznikami |
| `todos/templates/backup.yaml` | (\*) PVC `todos-backup` z `resource-policy: keep` i CronJob `mongo-backup` |
| `todos/templates/prometheusrule.yaml` | (\*) trzy alerty: api niedostępne, mongo nie Ready, mało miejsca na dysku bazy |
| `values-prod.yaml` | tylko różnice: web 3, HPA 3–4, egress, alerty |

## Wdrożenie

```bash
cd labs/todos-dzien5/rozwiazanie
helm lint todos --set registry=<REJESTR> --set host=todos-<login>.<DOMENA>

# 1. przejęcie działającego ToDos z dnia 4 (Helm 4; na Helm 3.17+ bez --server-side)
helm upgrade --install todos ./todos --take-ownership --server-side=false \
  --set registry=<REJESTR> --set host=todos-<login>.<DOMENA>
#    + --set backup.enabled=true, jeśli masz CronJob z dnia 3, --set otel.enabled=true po lab19
kubectl rollout status sts/mongo; kubectl rollout status deploy/api

# 2. „produkcja”
helm upgrade todos ./todos -f values-prod.yaml --set registry=<REJESTR> --set host=todos-<login>.<DOMENA>
kubectl get deploy web; kubectl get hpa api                # 3 repliki web, HPA 3–4

# 3. powrót
helm rollback todos 1
helm history todos
```

`--set registry` i `--set host` możesz zastąpić własnym plikiem `values-<login>.yaml` z tymi dwiema liniami.

## Dlaczego tak

- **Stałe nazwy, nie z release'u.** `helm create` nazywa obiekty `<release>-<chart>`. Tu to nie przejdzie: nginx w obrazie web woła `http://api:3001` (ConfigMap `API_HOST`), URI w Secrecie wskazuje host `mongo`, a przejmowane obiekty mają nazwy z dnia 4. Ceną jest jeden release ToDos na namespace, co przy namespace na zespół jest normalne.
- **Selektory bez zmian.** `spec.selector` Deploymentu i `selector`, `serviceName`, `volumeClaimTemplates` StatefulSetu są niezmienne. Chart dokłada etykiety do metadanych i szablonów podów (to wolno), selektory zostają `app: todos-*`. W `volumeClaimTemplates` etykieta dokładnie jak w dniu 4, bez etykiet Helma.
- **Secret poza chartem.** `values.yaml` ląduje w gicie, a `helm get values` pokaże go każdemu z dostępem do release'u. Hasło zostaje w Secrecie z dnia 2, chart zna tylko jego nazwę (`existingSecret`). Na produkcji ten Secret robi ExternalSecret z sejfu (temat 2).
- **`--take-ownership --server-side=false`.** Bez flagi Helm odmawia (`invalid ownership metadata`): nie nadpisze obiektu, którego nie utworzył. `--take-ownership` dopisuje etykietę i adnotacje release'u. Helm 4 domyślnie robi server-side apply i wtedy pola ustawione przez `kubectl apply` należą do menedżera `kubectl-client-side-apply`: konflikt na każdym polu, w którym wartość się różni albo jest domyślna (sprawdzone: `fieldRef` w env, `volumeClaimTemplates`, `command` w CronJobie, potem `replicas` i `minReplicas` przy kolejnym upgrade). `--server-side=false` przy pierwszej instalacji usuwa problem, a kolejne `upgrade` (`--server-side=auto`) zostają przy trybie z poprzedniej rewizji.
- **Pierwsza instalacja restartuje pody.** Nowe etykiety w szablonie poda = nowa wersja szablonu. Deploymenty wymieniają pody bez przerwy, `mongo-0` (jedna replika) ok. 30 s.
- **PVC.** `data-mongo-0` tworzy StatefulSet, nie Helm: `helm uninstall` go nie dotyka. `todos-backup` jest w chartcie, więc ma `helm.sh/resource-policy: keep`. Sprawdzone: po `helm uninstall` zostają oba PVC i Secret, a po ponownej instalacji zadania są na miejscu.
- **Bez `--wait` przy backupie.** Helm 4 przy `--wait` czeka też na PVC `Bound`. PVC backupu w klasie `WaitForFirstConsumer` czeka na pierwszego poda CronJobu, czyli do 2:00 w nocy. Gotowość sprawdzamy `kubectl rollout status`.
- **Alerty bez `/metrics` w aplikacji.** api nie wystawia metryk, ale kube-state-metrics zna stan Deploymentu i StatefulSetu, a kubelet zajętość PVC. `{{ "{{" }} $value {{ "}}" }}` w adnotacji: Helm wypisuje dosłownie `{{ $value }}`, który dopiero Prometheus wypełnia.
- **`replicas` api tylko w HPA.** Jak w dniach 3–4: z `replicas` w szablonie każdy `helm upgrade` cofałby decyzję HPA.

## Sprzątanie (dopiero po szkoleniu)

```bash
helm uninstall todos
kubectl delete pvc data-mongo-0 todos-backup
kubectl delete secret todos-mongo
```
