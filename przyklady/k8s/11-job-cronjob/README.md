# Przykłady: Job i CronJob

**Cel:** zobaczyć, jak Job doprowadza zadanie do końca (ponowienia, limit czasu, sprzątanie), jak dzieli pracę na numerowane części i jak CronJob uruchamia Joby według harmonogramu.

**Gdzie:** klaster szkoleniowy EKS, Twój namespace. Komendy wydajesz w tym katalogu (`cd przyklady/k8s/11-job-cronjob`).

| Plik | Co pokazuje |
|---|---|
| `job.yaml` | Job z `backoffLimit`, `activeDeadlineSeconds`, `ttlSecondsAfterFinished` |
| `job-indexed.yaml` | `completionMode: Indexed`: 5 części, 2 naraz, numer w `JOB_COMPLETION_INDEX` |
| `cronjob.yaml` | CronJob z `timeZone`, `concurrencyPolicy: Forbid`, historią i TTL |

Każde pole spoza oczywistych ma w pliku komentarz: co robi i jakie przyjmuje wartości.

## Krok po kroku

**1. Zwykły Job**
```bash
kubectl apply -f job.yaml
kubectl get job przyklad-thumbnails -w        # Ctrl+C, gdy zobaczysz Complete
kubectl logs job/przyklad-thumbnails
```
Co powinieneś zobaczyć: `STATUS Running`, `COMPLETIONS 0/1`, po ok. 10 s `Complete` i `1/1`. W logach `start …`, `obraz 1` … `obraz 5`, `koniec`. Pod zostaje w stanie `Completed` (`kubectl get pods`), a po 10 min (`ttlSecondsAfterFinished`) znika razem z Jobem.

**2. Job, który się nie udaje (backoffLimit)**
```bash
sed 's/echo koniec/exit 1/; s/przyklad-thumbnails/przyklad-blad/' job.yaml | kubectl apply -f -
kubectl get pods -l job-name=przyklad-blad -w   # Ctrl+C po ok. 2 min
kubectl get job przyklad-blad                  # STATUS Failed
kubectl get job przyklad-blad -o jsonpath='{.status.conditions[*].reason}'; echo
```
Co powinieneś zobaczyć: ten sam pod przechodzi `Error` → `CrashLoopBackOff`, a `RESTARTS` rośnie (to `restartPolicy: OnFailure`: restart w tym samym podzie, z coraz dłuższą przerwą 10 s, 20 s, 40 s). Po 3 porażkach Job dostaje `Failed`, a w warunkach (`conditions`) jest `BackoffLimitExceeded`. Z `restartPolicy: Never` zobaczyłbyś zamiast restartów kolejne nowe pody.

**3. Job Indexed: praca w częściach**

W drugim terminalu: `kubectl get pods -l job-name=przyklad-resize -w`.
```bash
kubectl apply -f job-indexed.yaml
kubectl get job przyklad-resize                # po ok. 45 s COMPLETIONS 5/5
kubectl logs -l job-name=przyklad-resize --prefix
```
Co powinieneś zobaczyć: w drugim terminalu nigdy więcej niż 2 pody `Running` naraz (`parallelism: 2`). Nazwy podów zawierają numer części: `przyklad-resize-0-…`, `przyklad-resize-1-…`. W logach każda część wypisuje swój numer: `część 0 z 5`, `część 3 z 5` itd.

**4. CronJob**

W drugim terminalu: `kubectl get jobs -w`.
```bash
kubectl apply -f cronjob.yaml
kubectl get cronjob przyklad-cleanup
kubectl create job przyklad-cleanup-teraz --from=cronjob/przyklad-cleanup   # przebieg na żądanie, bez czekania
kubectl logs job/przyklad-cleanup-teraz
```
Co powinieneś zobaczyć: `SCHEDULE */2 * * * *`, `TIMEZONE Europe/Warsaw`, `SUSPEND False`. Co 2 minuty (o parzystej minucie) w drugim terminalu pojawia się nowy Job `przyklad-cleanup-<liczba>`. W logach `czyszczenie <data>` i `gotowe`. Po kilku przebiegach zostają najwyżej 3 udane Joby (`successfulJobsHistoryLimit`).

**5. Wstrzymanie CronJoba**
```bash
kubectl patch cronjob przyklad-cleanup -p '{"spec":{"suspend":true}}'
kubectl get cronjob przyklad-cleanup
```
Co powinieneś zobaczyć: `SUSPEND True`, nowe Joby przestają się pojawiać. Przywrócenie: to samo z `false`.

## Sprzątanie
```bash
kubectl delete -f .
kubectl delete job przyklad-blad przyklad-cleanup-teraz --ignore-not-found
```

## Uwagi
- Job nie znika sam po zakończeniu: bez `ttlSecondsAfterFinished` Joby i ich pody zostają w namespace (i liczą się do quoty).
- `backoffLimit` liczy porażki całego Joba, `activeDeadlineSeconds` ma pierwszeństwo: po jego upływie Job kończy się `Failed` niezależnie od liczby prób.
- Przy `Indexed` lepiej ustawić `backoffLimitPerIndex`: jedna zepsuta część nie zabiera prób pozostałym.
- Przy `concurrencyPolicy: Allow` długi przebieg i kolejny mogą działać naraz. Dla zadań, które nie mogą się nakładać (backup, migracja), ustaw `Forbid`.
