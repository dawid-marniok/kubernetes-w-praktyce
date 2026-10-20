[← Deployment: spis](README.md)

# Dzień 2 — ściąga: sondy (startup, readiness, liveness)

Gotowe manifesty: `przyklady/k8s/01-pod/pod-probes.yaml` (goły pod), `przyklady/k8s/03-deployment/deployment-sondy-zasoby.yaml` (Deployment). Ćwiczysz w lab06 (krok 4 i dla chętnych) i lab07 (krok 2).

## Po co sondy

Bez sond Kubernetes wie tylko, czy proces w kontenerze żyje. Nie wie, czy aplikacja odpowiada. Kontener z zawieszoną aplikacją albo z aplikacją, która jeszcze ładuje dane, ma status `Running` i dostaje ruch z Service.

Sondę wykonuje kubelet na węźle, na którym działa pod. Każda sonda ma swoje pytanie i swój skutek porażki.

## Trzy sondy

| Sonda | Pytanie | Gdy nie przechodzi | Kiedy jej używać |
|---|---|---|---|
| **startupProbe** | Czy aplikacja już wystartowała? | po `failureThreshold` porażkach: restart kontenera. Do pierwszego sukcesu readiness i liveness **nie działają** | wolny start (Java, migracje, duży cache) |
| **readinessProbe** | Czy mogę teraz przyjmować ruch? | pod **wypada z EndpointSlice** Service, ruch do niego nie idzie. **Bez restartu**. Wraca sam, gdy sonda znów przejdzie | prawie zawsze, gdy pod stoi za Service |
| **livenessProbe** | Czy aplikacja się nie zawiesiła? | **restart kontenera** (licznik RESTARTS rośnie) | gdy aplikacja potrafi się zawiesić i sama z tego nie wyjdzie |

Kolejność: najpierw startup (jeśli jest), po jej sukcesie readiness i liveness działają równolegle przez całe życie kontenera. Readiness nie kończy się po pierwszym sukcesie — pod może wypaść z ruchu w dowolnym momencie i wrócić.

Krótko: **readiness = odetnij od ruchu, liveness = zrestartuj**.

## Jak sonda sprawdza

```yaml
httpGet:                 # sukces: kod HTTP 200–399
  path: /healthz
  port: http             # numer albo nazwa portu z containers[].ports
```
```yaml
tcpSocket:               # sukces: da się otworzyć połączenie TCP (np. baza, Redis)
  port: 5432
```
```yaml
exec:                    # sukces: komenda kończy się kodem 0
  command: ["pg_isready", "-U", "postgres"]
```
```yaml
grpc:                    # sukces: gRPC Health Checking zwraca SERVING
  port: 9090
```

`exec` uruchamia proces w kontenerze przy każdym sprawdzeniu — przy krótkim `periodSeconds` i wielu podach to widać na CPU. Jeśli aplikacja ma HTTP, wybierz `httpGet`.

## Parametry i liczenie czasu

| Pole | Domyślnie | Znaczy |
|---|---|---|
| `initialDelaySeconds` | 0 | ile czekać po starcie kontenera przed pierwszym sprawdzeniem |
| `periodSeconds` | 10 | co ile sekund sprawdzać |
| `timeoutSeconds` | 1 | ile czekać na odpowiedź; dłużej = porażka |
| `failureThreshold` | 3 | ile porażek z rzędu, zanim kubelet zareaguje |
| `successThreshold` | 1 | ile sukcesów z rzędu, żeby uznać sondę za zaliczoną (dla liveness i startup musi być 1) |

Ile czasu do reakcji: **`periodSeconds × failureThreshold`**.

- Liveness z `periodSeconds: 10`, `failureThreshold: 3` → zawieszona aplikacja zostanie zrestartowana po ok. 30 s.
- Startup z `periodSeconds: 2`, `failureThreshold: 30` → aplikacja ma maksymalnie 60 s na start. Po tym czasie restart.

Zamiast dużego `initialDelaySeconds` w liveness lepiej dać startupProbe: liveness zacznie sprawdzać dokładnie wtedy, gdy aplikacja wstanie, a nie po sztywno zgadniętym czasie.

## Pełny przykład

```yaml
containers:
- name: api
  image: rejestr/api:1.4.2
  ports:
  - name: http
    containerPort: 8080
  startupProbe:              # do 60 s na start (30 × 2 s)
    httpGet: {path: /healthz, port: http}
    periodSeconds: 2
    failureThreshold: 30
  readinessProbe:            # czy przyjmować ruch: aplikacja + jej zależności
    httpGet: {path: /ready, port: http}
    periodSeconds: 5
    failureThreshold: 2
  livenessProbe:             # czy proces żyje: tylko sama aplikacja
    httpGet: {path: /healthz, port: http}
    periodSeconds: 10
    timeoutSeconds: 2
    failureThreshold: 3
```

Dobra praktyka: dwa osobne endpointy w aplikacji.
- `/healthz` (liveness) — odpowiada `200`, jeśli proces działa. **Nie sprawdza bazy ani innych usług.**
- `/ready` (readiness) — odpowiada `200`, gdy aplikacja może obsłużyć żądanie, czyli także gdy ma połączenie z bazą.

## Jak to wygląda w kubectl

```bash
kubectl get pods                         # READY 0/1 przy STATUS Running = readiness nie przechodzi
                                         # rosnący RESTARTS = liveness (albo startup) nie przechodzi
kubectl describe pod <pod>               # sekcje Liveness/Readiness/Startup + Events na dole
kubectl get endpointslices -l kubernetes.io/service-name=<service>
kubectl explain pod.spec.containers.readinessProbe
```

Typowe Events:

| Event | Co się dzieje |
|---|---|
| `Readiness probe failed: HTTP probe failed with statuscode: 404` | zła ścieżka albo aplikacja jeszcze nie gotowa; pod bez ruchu, bez restartu |
| `Liveness probe failed: ... Container nginx failed liveness probe, will be restarted` | kubelet zabija kontener i uruchamia go od nowa |
| `Startup probe failed: ...` | aplikacja nie zdążyła wystartować w `periodSeconds × failureThreshold` |
| `connect: connection refused` | nic nie słucha na tym porcie (zły port albo aplikacja nie wstała) |
| `context deadline exceeded` | aplikacja odpowiada za wolno — przekroczony `timeoutSeconds` |

Po kilku restartach z rzędu status zmienia się na `CrashLoopBackOff`: kubelet czeka coraz dłużej (do 5 min) przed kolejnym startem.

## Sondy a rollout Deploymentu

Deployment przy RollingUpdate usuwa stary pod dopiero wtedy, gdy nowy jest **gotowy**. „Gotowy” znaczy: readinessProbe przeszła.

- **Bez readiness** pod jest gotowy, gdy tylko kontener wystartuje. Aplikacja może jeszcze się ładować, a stare pody już znikają — użytkownicy dostają błędy 502/503.
- **Z readiness** zepsuta wersja nigdy nie staje się gotowa, więc rollout stoi, a stare pody dalej obsługują ruch. `kubectl rollout status` czeka, a po `progressDeadlineSeconds` (domyślnie 600 s) Deployment dostaje warunek `ProgressDeadlineExceeded`. Cofnięcie robisz sam: `kubectl rollout undo`.

Więcej o strategiach: [docs/k8s/deployment/strategie-wdrozen.md](strategie-wdrozen.md).

## Zmiana sond w podzie i w Deploymencie

- **Goły pod:** sond nie zmienisz przez `apply` (`Forbidden: pod updates may not change fields other than ...`). Trzeba usunąć i utworzyć pod od nowa.
- **Deployment:** zmiana sond to zmiana szablonu poda → nowy ReplicaSet i normalny rollout. Działa przez `apply`.

## Częste błędy

| Błąd | Skutek | Jak lepiej |
|---|---|---|
| liveness sprawdza bazę danych | baza ma chwilową awarię → **wszystkie** pody restartują się naraz, choć same są zdrowe | zależności sprawdzaj w readiness, liveness tylko sam proces |
| liveness bez startupProbe przy wolnym starcie | aplikacja nie zdąży wstać, liveness ją zabija, pętla `CrashLoopBackOff` | dodaj startupProbe z zapasem czasu |
| `timeoutSeconds: 1` (domyślne) przy aplikacji pod obciążeniem | wolna odpowiedź = porażka → restart w najgorszym momencie | 2–5 s dla liveness, `failureThreshold` ≥ 3 |
| ta sama ścieżka i te same progi dla readiness i liveness | pod jednocześnie wypada z ruchu i jest restartowany; readiness traci sens | liveness z większym `failureThreshold` niż readiness |
| sonda na port, którego aplikacja nie otwiera (np. `80` zamiast `8080`) | `connection refused`, pod nigdy nie jest Ready | używaj nazwanego portu (`port: http`) |
| sonda `exec` z narzędziem, którego nie ma w obrazie (`curl` w busyboxie) | `executable file not found`, sonda zawsze nie przechodzi | sprawdź: `kubectl exec <pod> -- which curl` |
