# Przykłady: Pod

**Cel:** uruchomić pod, zajrzeć do niego i rozpoznać trzy typowe awarie po objawach.

**Gdzie:** klaster szkoleniowy EKS, Twój namespace. Komendy wydajesz w tym katalogu (`cd przyklady/k8s/01-pod`).

| Plik | Co pokazuje |
|---|---|
| `pod.yaml` | najprostszy pod: obraz z tagiem, etykieta, port, requests/limits |
| `pod-multi-container.yaml` | dwa kontenery, wspólny `emptyDir`, komunikacja przez localhost |
| `pod-env-vars.yaml` | zmienne środowiskowe w manifeście |
| `pod-command-args.yaml` | `command` i `args` (opis: `DOCKER-vs-KUBERNETES-command-args.md`) |
| `pod-restart-policy.yaml` | `restartPolicy: OnFailure` i proces kończący się błędem |
| `pod-probes.yaml` | startupProbe, readinessProbe, livenessProbe |
| `pod-zly-obraz.yaml` | awaria: literówka w obrazie → `ImagePullBackOff` (diagnoza: Events w `describe`) |
| `pod-crashloop.yaml` | awaria: proces kończy się błędem → `CrashLoopBackOff` (diagnoza: `logs --previous`) |
| `pod-oom.yaml` | awaria: przekroczony limit pamięci → `OOMKilled`, kod 137 (diagnoza: Last State w `describe`) |

## Krok po kroku

**1. Najprostszy pod**
```bash
kubectl apply -f pod.yaml
kubectl get pod przyklad-pod -o wide
kubectl port-forward pod/przyklad-pod 8080:80      # w drugim terminalu: curl localhost:8080, potem Ctrl+C
```
Co powinieneś zobaczyć: `READY 1/1`, `STATUS Running`, adres IP poda i nazwę węzła (`ip-10-…`). `curl` zwraca stronę `Welcome to nginx!`.

**2. Dwa kontenery w jednym podzie**
```bash
kubectl apply -f pod-multi-container.yaml
kubectl get pod przyklad-multi
kubectl exec przyklad-multi -c nginx -- curl -s localhost
```
Co powinieneś zobaczyć: `READY 2/2`. `curl` z kontenera nginx zwraca `Hello z busyboxa`: plik zapisał drugi kontener do wspólnego `emptyDir`. Przy `exec` i `logs` w podzie z kilkoma kontenerami wskazujesz kontener przez `-c`.

**3. Zmienne, command i args**
```bash
kubectl apply -f pod-env-vars.yaml -f pod-command-args.yaml
kubectl exec przyklad-env -- env | grep -E 'ENVIRONMENT|APP_NAME|VERSION'
kubectl logs przyklad-command-args
```
Co powinieneś zobaczyć: `ENVIRONMENT=production`, `APP_NAME=my-app`, `VERSION=1.0.0`, a w logach `Hello z Kubernetesa`. Jak `command`/`args` mają się do `ENTRYPOINT`/`CMD`: `DOCKER-vs-KUBERNETES-command-args.md`.

**4. Sondy**
```bash
kubectl apply -f pod-probes.yaml
kubectl describe pod przyklad-sondy | grep -E 'Startup|Readiness|Liveness'
```
Co powinieneś zobaczyć: trzy linie z parametrami sond (`http-get http://:http/ delay=0s timeout=… period=… #success=1 #failure=…`). Pod jest `READY 1/1` dopiero po udanej readinessProbe.

**5. restartPolicy**
```bash
kubectl apply -f pod-restart-policy.yaml
kubectl get pod przyklad-restart-policy -w      # Ctrl+C po ok. minucie
```
Co powinieneś zobaczyć: `Error` → `CrashLoopBackOff`, kolumna `RESTARTS` rośnie, przerwy między restartami coraz dłuższe. Przy `restartPolicy: Never` pod zostałby w `Error` bez restartów.

**6. Trzy awarie i ich diagnoza**
```bash
kubectl apply -f pod-zly-obraz.yaml -f pod-crashloop.yaml -f pod-oom.yaml
kubectl get pods
kubectl describe pod przyklad-zly-obraz | tail -5
kubectl logs przyklad-crashloop --previous
kubectl describe pod przyklad-oom | grep -A3 "Last State"
```
Co powinieneś zobaczyć:
- `przyklad-zly-obraz`: `ErrImagePull`, potem `ImagePullBackOff`; w Events `pull access denied` / `repository does not exist` dla `nginxx`.
- `przyklad-crashloop`: `CrashLoopBackOff`; w logach poprzedniego uruchomienia `Brak zmiennej DB_HOST, koncze prace`.
- `przyklad-oom`: `OOMKilled`, potem `CrashLoopBackOff`; `Last State: Terminated`, `Reason: OOMKilled`, `Exit Code: 137`. W logach pusto.

## Sprzątanie
```bash
kubectl delete -f .
```

## Uwagi
- Pod nie wstaje? Zawsze ta sama kolejność: `kubectl get pods` → `kubectl describe pod <nazwa>` (Events, Last State) → `kubectl logs <nazwa> --previous` → `kubectl events`.
- Każdy przykład ma `resources` (wymagane przez ResourceQuota na wspólnym klastrze) i własną etykietę `app: przyklad-…`, więc nie zderzy się z labami.
