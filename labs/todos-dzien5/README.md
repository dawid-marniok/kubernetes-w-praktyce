# ToDos · dzień 5 — jeden chart zamiast dziesięciu plików

**Cel:** ToDos z wczoraj działa tak samo, ale od teraz jest **releasem Helma**: jedna komenda wdraża całość, wartości dla „produkcji” są w osobnym pliku, a zła zmiana cofa się `helm rollback`. Zadania z poprzednich dni mają przetrwać: release **przejmuje** działające obiekty, niczego nie usuwasz.
**Środowisko:** wspólny klaster, Twój namespace. Nie piszesz `-n` ani `namespace:`.
**Czas:** ok. 30 minut.

Tu masz tylko wymagania. Jak je spełnisz, decydujesz sam. Utknąłeś: gotowy chart i opis są w [`rozwiazanie/`](rozwiazanie/). Zajrzyj najpierw do jednego pliku, a nie od razu do wszystkich.

```
dzień 4:  kubectl apply -f serviceaccounts.yaml -f mongo.yaml -f api.yaml -f web.yaml -f networkpolicy.yaml …
dzień 5:  helm upgrade --install todos ./todos-chart -f values-prod.yaml      → rewizja 1, 2, 3 … i helm rollback
```

**Od trenera na czacie:** nic nowego. Adres ten sam: `https://todos-<login>.<DOMENA>`, rejestr z karty (`<REJESTR>`).

## Zanim zaczniesz

ToDos z dnia 4 musi działać:

```bash
kubectl get sts,deploy,svc,ingress,hpa,sa,networkpolicy -l app.kubernetes.io/part-of=todos
curl -s https://todos-<login>.<DOMENA>/api/todos         # Twoje zadania
helm version --short                                      # v4.x albo v3.17+ (różnice niżej)
```

Nie masz go albo nie działa: wdróż [`../todos-dzien4/rozwiazanie/`](../todos-dzien4/rozwiazanie/) (polecenia w jego README, ok. 5 minut).

Posprzątaj po labach 17–19, żeby nie zabierały quoty:

```bash
helm list                                       # release'y z lab17 (t1, podinfo …): helm uninstall <nazwa>
kubectl get clusters.postgresql.cnpg.io         # klaster z lab18: kubectl delete cluster <nazwa>
kubectl delete pod crash --ignore-not-found      # lab19
```

Zrobiłeś w lab19 krok 6 (trace'y ToDos, `kubectl patch deployment api`)? Zapamiętaj to: w chartcie ta zmiana musi być wartością (`otel.enabled`), inaczej pierwszy `helm upgrade` ją zdejmie.

## Wymagania

**Chart `todos-chart` w Twoim katalogu roboczym**
- wszystkie obiekty ToDos z dnia 4 są w `templates/`: ConfigMap, ServiceAccounty, api (Deployment, Service, HPA), web (Deployment, Service), Ingress, mongo (headless Service, StatefulSet), NetworkPolicy; z gwiazdką także backup i polityki egress, jeśli je masz,
- możesz zacząć od `helm create todos-chart` i wyrzucić z `templates/` wszystko poza `_helpers.tpl` i `NOTES.txt`, albo pisać od zera,
- **Secret `todos-mongo` nie trafia do chartu.** Chart tylko się do niego odwołuje (nazwa w values). Dlaczego nie jako szablon z hasłem w `values.yaml`? Gdzie kończy `values.yaml`?

**Wartości zamiast wpisanych na sztywno**
- w `values.yaml` co najmniej: rejestr, tag obrazów, host Ingressu, liczba replik web, `minReplicas`/`maxReplicas` HPA i włącznik NetworkPolicy,
- bez rejestru albo hosta `helm template` kończy się czytelnym błędem (funkcja `required`), a nie Deploymentem z obrazem `/todos-api:1.0.0`,
- `helm lint` bez błędów, `helm template` daje te same obiekty co pliki z dnia 4.

**Te same nazwy i selektory co wczoraj**
- obiekty nazywają się jak w dniu 4 (`api`, `web`, `mongo`, `todos-config`, `todos-tls`…), a selektory Deploymentów i StatefulSetu (`app: todos-api` itd.) zostają bez zmian. Dlaczego nie nazwy z release'u, jak w `helm create`? Sprawdź, czego szuka nginx w obrazie web i które pola Deploymentu i StatefulSetu są niezmienne,
- skutek: jeden release ToDos na namespace. I dobrze.

**Release `todos` przejmuje działające obiekty**
- pierwsza instalacja chartu nie usuwa ani nie tworzy od nowa Deploymentów, StatefulSetu ani PVC. Zadania z poprzednich dni są na liście po instalacji,
- najpierw spróbuj zwykłego `helm upgrade --install todos ./todos-chart …` i przeczytaj błąd. Co Helm sprawdza, zanim cokolwiek zmieni?

> **Pułapka: Helm nie przejmuje cudzych obiektów.** Obiekt bez etykiety `app.kubernetes.io/managed-by: Helm` i adnotacji `meta.helm.sh/release-name`/`release-namespace` kończy instalację błędem `invalid ownership metadata`. Helm od 3.17 ma na to flagę `--take-ownership`. **Helm 4** wdraża domyślnie przez server-side apply i dostaje drugi błąd: `conflict … with "kubectl-client-side-apply"`, bo pola ustawił wcześniej `kubectl apply`. Przy przejmowaniu obiektów z `kubectl apply` dodaj `--server-side=false` (Helm zrobi to tak jak Helm 3, a kolejne `upgrade` zapamiętają ten tryb). Starszy Helm 3: etykieta i dwie adnotacje ręcznie, `kubectl label`/`kubectl annotate` na każdym obiekcie.

**Środowiska jako pliki wartości**
- `values-prod.yaml` zawiera **tylko różnice** względem `values.yaml`: np. 3 repliki web, `minReplicas: 3`, z gwiazdką egress i alerty,
- `helm upgrade` z `-f values-prod.yaml`, potem `helm rollback` do pierwszej rewizji. Po rollbacku web ma znowu 2 repliki, a HPA `minReplicas` 2,
- maksimum replik w obu plikach mieści się w quocie namespace'u (licz jak w dniu 3).

**(\*) Alerty ToDos w chartcie**
- `PrometheusRule` za włącznikiem `alerts.enabled`: co najmniej „żaden pod api nie jest Ready” (`kube_deployment_status_replicas_available`) z `for: 2m`,
- namespace w zapytaniu z `{{ .Release.Namespace }}`, nie wpisany ręcznie,
- `{{ $value }}` i `{{ $labels.pod }}` w adnotacjach to szablony Prometheusa, nie Helma. Helm musi je przepuścić dosłownie: jak?
- test: `kubectl scale deploy api --replicas=0`, po ok. 2 minutach alert w Grafanie (Alerting → Alert rules) przechodzi w Firing, potem `kubectl scale deploy api --replicas=2`.

**(\*) Trace'y z lab19 jako wartość**
- `otel.enabled: true` dokłada adnotację `instrumentation.opentelemetry.io/inject-nodejs`, `OTEL_SERVICE_NAME` z namespace'em i wyższy limit pamięci api, a przy egress także politykę do `monitoring:4318`.

**(\*) Chart w rejestrze OCI**
- `helm package todos-chart` i `helm push` do Twojego ECR (`oci://<REJESTR>`), potem `helm show chart oci://<REJESTR>/todos-chart --version 0.1.0`. Logowanie: `aws ecr get-login-password | helm registry login --username AWS --password-stdin <konto>.dkr.ecr.eu-central-1.amazonaws.com`.

Ściąga: `helm create`, `helm lint`, `helm template … | less`, `helm get values todos`, `helm get manifest todos`, `helm history todos`, składnia szablonów w `docs/k8s/helm/skladnia.md`, wzorzec chartu z warunkami w [`przyklady/k8s/22-helm/`](../../przyklady/k8s/22-helm/).

## Jak sprawdzić

```bash
helm list                                                       # todos, STATUS deployed
helm history todos                                              # 3+ rewizje, ostatnia „Rollback to 1”
kubectl get deploy,sts,svc,ingress,hpa,networkpolicy -l app.kubernetes.io/managed-by=Helm
kubectl get pvc data-mongo-0                                    # ten sam dysk co wczoraj (AGE!)
curl -s https://todos-<login>.<DOMENA>/api/todos                # zadania z poprzednich dni
helm get values todos --all | head -20                          # z jakimi wartościami działa release
```

## SUKCES

`helm history todos` pokazuje co najmniej trzy rewizje (instalacja, upgrade z `values-prod.yaml`, rollback), wszystkie obiekty ToDos mają `managed-by: Helm`, a zadania z poprzednich dni są na liście. **Wklej na czat** wynik `helm history todos`.

Nie usuwaj ToDos.

## Dla chętnych

- **Co zostaje po `helm uninstall`?** Nie rób tego na swoim ToDos, tylko pomyśl (albo sprawdź w rozwiązaniu): PVC `data-mongo-0`, Secret `todos-mongo`, PVC backupu. Kto je utworzył i co robi adnotacja `helm.sh/resource-policy: keep`?
- **`--wait` a PVC.** Z backupem dodaj do `upgrade` flagę `--wait`. Dlaczego Helm 4 czeka do timeoutu, choć wszystkie pody są `Ready`? (Podpowiedź: `kubectl get pvc todos-backup` i StorageClass `WaitForFirstConsumer`.)
- **`helm diff`.** `helm plugin install https://github.com/databus23/helm-diff`, potem `helm diff upgrade todos ./todos-chart -f values-prod.yaml …`: zmiany przed upgrade, jak `terraform plan`.

## Gdy coś nie działa

| Objaw | Co zrobić |
|---|---|
| `invalid ownership metadata; label validation error: missing key "app.kubernetes.io/managed-by"` | obiekt z `kubectl apply`: `--take-ownership` (Helm ≥ 3.17) |
| `conflict occurred while applying object … conflicts with "kubectl-client-side-apply"` | Helm 4 i server-side apply: pierwsza instalacja z `--take-ownership --server-side=false`. Release już jest i zawiódł → to samo jeszcze raz albo `--force-conflicts` |
| `execution error … Ustaw registry` (albo Twój komunikat z `required`) | brak wartości: `--set registry=<REJESTR> --set host=…` albo wpis w pliku wartości |
| `StatefulSet … Forbidden: updates to statefulset spec for fields other than 'replicas', 'ordinals', 'template', 'updateStrategy'…` | w chartcie zmieniony `serviceName`, `selector` albo `volumeClaimTemplates` (też etykiety w nich). Muszą być identyczne jak w dniu 4 |
| `Deployment … spec.selector: Invalid value … field is immutable` | selektor z `helm create` (`app.kubernetes.io/name`, `instance`) zamiast `app: todos-api` |
| web `CrashLoopBackOff`, `host not found in upstream "api"` | Service api nazywa się inaczej (np. `todos-api` z nazwy release'u) |
| po pierwszej instalacji `mongo-0` i pody api/web startują od nowa | normalne: Helm dopisał etykiety do szablonu poda, więc to nowa wersja szablonu. Baza ok. 30 s niedostępna, dane zostają |
| `function "humanizePercentage" not defined` albo `undefined variable "$value"` | szablon Prometheusa czyta Helm: `{{ "{{" }} $value {{ "}}" }}` albo cały tekst w `` {{` … `}} `` |
| `--wait` kończy się `PersistentVolumeClaim … todos-backup not ready … PVC is not Bound` | PVC backupu czeka na pierwszego poda (`WaitForFirstConsumer`): upgrade bez `--wait`, gotowość przez `kubectl rollout status` |
| po `helm rollback` HPA ma inne repliki niż `minReplicas` | HPA dostosowuje się w ciągu kilkunastu sekund: `kubectl get hpa -w` |
| api traci trace'y po pierwszym `upgrade` | patch z lab19 nie jest w chartcie: `--set otel.enabled=true` |
| `helm push` → `denied` / `unauthorized` | `helm registry login` do hosta ECR (bez `/<login>` w adresie), token ważny 12 h |
