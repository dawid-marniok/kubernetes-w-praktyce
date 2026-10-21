# lab10 — Job, CronJob i DaemonSet

**Gdzie:** klaster szkoleniowy, Twój namespace (punkt dla chętnych z hostPath: kind)

**Po labie masz:** cztery Joby (trzy `Complete`, jeden `Failed` z `DeadlineExceeded`), poprawiony CronJob, który wypisuje prawdziwą datę, i DaemonSet z jednym podem na każdym węźle.

## Zanim zaczniesz

- Bez `namespace:` w manifestach, obrazy z tagiem (`busybox:1.37`), w każdym kontenerze `resources`, np.:
  ```yaml
  resources:
    requests: {cpu: 10m, memory: 16Mi}
    limits: {cpu: 100m, memory: 32Mi}
  ```
- Każdy Job dostaje `ttlSecondsAfterFinished: 600`. Job **nie** usuwa się sam po zakończeniu, a jego pody liczą się do quoty podów.
- Drugi terminal z `kubectl get pods -w` bardzo pomaga.

Plik startowy: `cronjob-zepsuty.yaml` (krok 4).

## Poziom podstawowy

### 1. Pierwszy Job

Napisz `job-hello.yaml`: Job `hello-job`, `restartPolicy: Never`, `backoffLimit: 4`, kontener `busybox:1.37` z komendą
`["sh", "-c", "echo \"Hello from Kubernetes Job! $(date)\"; sleep 5"]`.

```bash
kubectl apply -f job-hello.yaml
kubectl get job hello-job
kubectl logs job/hello-job
kubectl get pods -l job-name=hello-job
```

✅ `COMPLETIONS 1/1`, w logu prawdziwa data, pod w stanie `Completed` (nie znika).

### 2. Wiele ukończeń: po kolei i równolegle

1. `batch-job`: `completions: 5`, `parallelism: 1`, `completionMode: Indexed`. Kontener wypisuje `Processing item $JOB_COMPLETION_INDEX` i śpi 2 s.
2. `parallel-job`: `completions: 10`, `parallelism: 3`, komenda `echo "Task $TASK_ID"; sleep 10`, gdzie `TASK_ID` to nazwa poda z Downward API (`valueFrom.fieldRef.fieldPath: metadata.name`).

```bash
kubectl get pods -l job-name=parallel-job -w     # ile naraz?
kubectl logs -l job-name=batch-job --prefix
```

✅ W `batch-job` pięć numerów 0–4 po kolei; w `parallel-job` nigdy więcej niż 3 pody `Running` naraz.

### 3. Limit czasu

`timeout-job`: `sleep 300`, `activeDeadlineSeconds: 60`, `backoffLimit: 3`.

```bash
kubectl get job timeout-job -w        # ok. 60 s
kubectl describe job timeout-job | tail -5
```

✅ Job `Failed`, w eventach `DeadlineExceeded`. Który limit wygrał: czas czy liczba prób?

### 4. Popraw zepsuty CronJob

```bash
kubectl apply -f cronjob-zepsuty.yaml
kubectl get jobs -w                   # poczekaj na pierwszy Job (do minuty)
kubectl logs job/<nazwa-joba>
```

W logu zamiast daty jest dosłownie `$(date)`. Znajdź przyczynę w pliku, popraw, zastosuj ponownie i uruchom przebieg od razu, bez czekania na harmonogram:

```bash
kubectl apply -f cronjob-zepsuty.yaml
kubectl create job hello-teraz --from=cronjob/hello-cronjob
kubectl logs job/hello-teraz
```

Dopisz jeszcze `timeZone: Europe/Warsaw`, `successfulJobsHistoryLimit: 3`, `failedJobsHistoryLimit: 1`. W jakiej strefie jest data w logu? Na co wpływa `timeZone`?

### 5. CronJob, który się nie nakłada

`long-running`: co minutę, `sleep 90`, `concurrencyPolicy: Forbid`. Po 3 minutach:

```bash
kubectl get jobs
kubectl describe cronjob long-running | tail -6
```

✅ Nigdy dwa Joby `long-running` w `Running` naraz, w eventach `JobAlreadyActive`.

### 6. DaemonSet: pod na każdym węźle

DaemonSet `node-agent`, etykieta `app: node-agent`, kontener `busybox:1.37`, który co 30 s wypisuje nazwę swojego węzła (`NODE_NAME` z `fieldPath: spec.nodeName`).

```bash
kubectl get nodes
kubectl get daemonset node-agent
kubectl get pods -l app=node-agent -o wide
kubectl logs ds/node-agent
```

✅ `DESIRED` równe liczbie węzłów, na których mogą stać zwykłe pody; każdy pod na innym węźle.

### 7. Sprzątanie

```bash
kubectl delete cronjob --all
kubectl delete job --all
kubectl delete daemonset node-agent
```

## SUKCES

- [ ] `hello-job`, `batch-job`, `parallel-job` w stanie `Complete`, `timeout-job` `Failed` z `DeadlineExceeded`
- [ ] CronJob wypisuje prawdziwą datę i umiesz powiedzieć, co było nie tak
- [ ] `long-running` pokazał `JobAlreadyActive`
- [ ] DaemonSet: `DESIRED` = liczba węzłów roboczych
- [ ] po labie `kubectl get cronjobs,jobs,ds` jest puste

## Dla chętnych

- **Porażka na indeks.** W `batch-job` dodaj `backoffLimitPerIndex: 1` i komendę, która kończy się błędem tylko dla indeksu 3 (`[ "$JOB_COMPLETION_INDEX" != 3 ]`). Jaki status ma Job i które indeksy się udały (`kubectl get job batch-job -o jsonpath='{.status.failedIndexes}'`)?
- **Agent logów na kind** (namespace bez Pod Security, `kubectl` z kontekstem kind): DaemonSet `log-agent`, który montuje `hostPath` `/var/log/pods` tylko do odczytu i co 30 s wypisuje, ile katalogów z logami podów widzi. Dodaj toleracje dla `node-role.kubernetes.io/control-plane:NoSchedule`. Na ilu węzłach stoi z toleracją, a na ilu bez niej? Dlaczego nie `tail -F` wszystkich plików z `/var/log/pods`?

## Gdy coś nie działa

**Gotowe wzorce manifestów:** [`przyklady/k8s/11-job-cronjob/`](../../przyklady/k8s/11-job-cronjob/), [`przyklady/k8s/10-daemonset/`](../../przyklady/k8s/10-daemonset/). Skopiuj i przerób, zamiast pisać YAML od zera.

| Objaw | Co zrobić |
|---|---|
| W logu dosłownie `$(date)` albo `$TASK_ID` | zmienna jest w apostrofach wewnątrz `sh -c`, shell jej nie rozwija; użyj cudzysłowów |
| `exceeded quota … pods` | `kubectl delete job --all`, zakończone pody też się liczą |
| `spec.template.spec.restartPolicy: Unsupported value: "Always"` | w Jobie tylko `Never` albo `OnFailure` |
| `field is immutable` przy ponownym `apply` Joba | szablon Joba się nie zmienia: `kubectl delete job …`, potem `apply` |
| Pierwszy Job CronJoba nie pojawia się | harmonogram liczy pełne minuty, poczekaj do 60 s albo `kubectl create job --from=cronjob/…` |
| `kubectl logs -l …` pokazuje mało | domyślnie ostatnie 10 linii na pod: `--tail=-1` |
