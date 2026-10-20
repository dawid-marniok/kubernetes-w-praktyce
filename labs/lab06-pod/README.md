# Lab 06 — Pierwsze pody w Twoim namespace

**Cel:** piszesz manifest poda od zera (jeden i dwa kontenery, zasoby, zmienne), czytasz jego stan i naprawiasz pod, który nie wstaje.
**Środowisko:** wspólny klaster, Twój namespace. Nie piszesz `-n` ani `namespace:` w plikach.

**Start:** `cd labs/lab06-pod` i `mkdir -p moje` — tu zapisujesz swoje pliki (katalog `moje/` jest w `.gitignore`).

Plik startowy: `pod-failed.yaml` (pod z błędem do znalezienia). Resztę plików piszesz sam — np. w katalogu `moje/`.

**Zasady na wspólnym klastrze**
- Obrazy zawsze z tagiem: `nginx:1.29`, `busybox:1.37`. Nigdy `:latest`.
- Każdy kontener ma `resources.requests` i `resources.limits` (cpu i memory). Jeśli ich nie wpiszesz, LimitRange w namespace dopisze wartości domyślne (50m/64Mi → 250m/256Mi) — działa, ale zużywa więcej quoty, niż trzeba.
- Etykiety z prefiksem labu: `app: lab06-…`. Dzięki temu Twoje ReplicaSety i Service z kolejnych labów nie „złapią” tych podów.

Szkielet poda bez pisania z pamięci:
```bash
kubectl run lab06-web --image=nginx:1.29 --port=80 --labels=app=lab06-web --dry-run=client -o yaml > moje/lab06-web.yaml
```
Potem w miejsce `resources: {}` wpisz requests i limits, a `status: {}` usuń.

---

## Poziom podstawowy

### Krok 1. Pod z jednym kontenerem
Pod `lab06-web`: obraz `nginx:1.29`, etykieta `app: lab06-web`, port 80, requests `50m`/`32Mi`, limits `100m`/`64Mi`.
```bash
kubectl apply -f moje/lab06-web.yaml
kubectl get pods -o wide
kubectl describe pod lab06-web
kubectl logs lab06-web
```
- Na którym węźle działa pod i jaki ma IP?

### Krok 2. Trzy kolejne pody
1. `lab06-duo` — dwa kontenery: `nginx` (`nginx:1.29`, port 80) i `busybox` (`busybox:1.37`, komenda, która zapisuje `index.html` do wspólnego wolumenu (np. zamontowanego w `/shared`), a potem `sleep 3600`, np. `sh -c 'echo "witaj z busyboxa" > /shared/index.html; sleep 3600'`). Wspólny wolumen `emptyDir`: busybox zapisuje `index.html`, nginx go serwuje.
   ```bash
   kubectl get pod lab06-duo                                  # READY 2/2
   kubectl exec lab06-duo -c nginx -- curl -s localhost       # treść z busyboxa
   kubectl exec -it lab06-duo -c busybox -- sh                # wyjście: exit
   ```
2. `lab06-limity` — `nginx:1.29`, requests `100m`/`128Mi`, limits `200m`/`256Mi`.
   ```bash
   kubectl get pod lab06-limity -o jsonpath='{.status.qosClass}{"\n"}'
   ```
3. `lab06-env` — `nginx:1.29` ze zmiennymi `ENV_NAME=production` i `APP_VERSION=1.0.0`.
   ```bash
   kubectl exec lab06-env -- env | grep -E 'ENV_NAME|APP_VERSION'
   ```

### Krok 3. Pod, który nie wstaje
```bash
kubectl apply -f pod-failed.yaml
kubectl get pod lab06-failed
kubectl describe pod lab06-failed
kubectl logs lab06-failed
```
- Jaki jest status i co mówią Events na dole `describe`?
- Co zwróciło `kubectl logs`? Dlaczego nie ma tu logów aplikacji? Kiedy przyczynę znajdziesz w logach, a kiedy tylko w zdarzeniach?
- Popraw `pod-failed.yaml` i zastosuj ponownie. Pod ma przejść w `Running`. Nie tak są dwie rzeczy: jedna blokuje start poda (znajdziesz ją w Events), druga go nie blokuje, ale łamie zasady wspólnego klastra z początku labu.

### Krok 4. Gotowość: readinessProbe
Dopisz do `lab06-web` sondę `readinessProbe` (HTTP GET na `/`, port 80, `initialDelaySeconds: 5`, `periodSeconds: 5`) i zastosuj plik.
- Co odpowiedział klaster? Co trzeba zrobić, żeby pod miał sondę?
- Obserwuj: `kubectl get pod lab06-web -w` — kolumna READY `0/1` → `1/1`. Wyjście: Ctrl-C.

### Krok 5. Etykiety
```bash
kubectl get pods --show-labels
kubectl label pod lab06-env env=dev
kubectl get pods -l env=dev
kubectl get pods -l 'app in (lab06-web,lab06-env)'
```

**SUKCES:** 5 podów `lab06-…` w stanie Running (`lab06-duo` 2/2), `lab06-failed` naprawiony, a powód błędu umiesz pokazać w `describe`.

---

## Dla chętnych

1. **Sonda, która nie przechodzi.** Pod `lab06-zla-sonda` z readinessProbe na `/zdrowie`. Jaki jest STATUS, a jaki READY? Czy pod się restartuje? Co pokazuje `describe` w Events? Zamień readiness na liveness — co się zmienia?
2. **command i args.** `przyklady/k8s/01-pod/pod-command-args.yaml` i `przyklady/k8s/01-pod/DOCKER-vs-KUBERNETES-command-args.md`: który z nich nadpisuje `ENTRYPOINT`, a który `CMD`?
3. **Restart kontenera a emptyDir.** W `lab06-duo` zabij proces nginx: `kubectl exec lab06-duo -c nginx -- nginx -s stop`. Czy `index.html` przetrwał restart kontenera? A usunięcie i ponowne utworzenie poda?

---

## Wskazówki

**Gotowe wzorce manifestów:** [`przyklady/k8s/01-pod/`](../../przyklady/k8s/01-pod/). Skopiuj i przerób, zamiast pisać YAML od zera.

- Sondy (startup, readiness, liveness) — co robią, jak liczyć czas, typowe błędy: [`docs/k8s/deployment/sondy.md`](../../docs/k8s/deployment/sondy.md).
- `kubectl explain pod.spec.containers.readinessProbe` — pola sondy z Twojego klastra.
- Zmiana obrazu w istniejącym podzie przez `apply` działa. Zmiana sond, portów czy zasobów — nie (`Forbidden: pod updates may not change fields…`). Wtedy `kubectl delete -f plik.yaml` i `kubectl apply -f plik.yaml`.
- `-c <kontener>` przy `exec` i `logs` w podzie z kilkoma kontenerami; bez tego trafiasz do pierwszego.
- W obrazie nginx jest `curl`, nie ma `wget`. W busyboxie odwrotnie.
- `kubectl top pod` wymaga metrics-server — na klastrze szkoleniowym jest, na kind trzeba go doinstalować. Nie jest potrzebny do labu.

## Sprzątanie
Przed lab07 usuń pody z tego labu:
```bash
kubectl delete pod -l 'app in (lab06-web,lab06-duo,lab06-limity,lab06-env,lab06-failed,lab06-zla-sonda)'
```
