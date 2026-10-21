# Przykłady: HorizontalPodAutoscaler (autoscaling/v2)

**Cel:** zobaczyć, jak HPA dokłada repliki, gdy CPU przekracza cel, i jak powoli je zabiera, gdy obciążenie mija.

**Gdzie:** klaster szkoleniowy EKS, Twój namespace (metrics-server jest zainstalowany jako add-on EKS). Na kind najpierw zainstaluj metrics-server: [`setup/kind.md`](../../../setup/kind.md), punkt 3. Komendy wydajesz w tym katalogu (`cd przyklady/k8s/14-hpa`).

| Plik | Co pokazuje |
|---|---|
| `deployment.yaml` | aplikacja `hpa-test` (nginx) z `requests.cpu: 20m` (od requestu HPA liczy procent), bez pola `replicas` |
| `service.yaml` | Service ClusterIP `hpa-service` przed podami `hpa-test` |
| `hpa.yaml` | 1–5 replik, cel 50% CPU, łagodne schodzenie w dół |
| `hpa-advanced.yaml` | wariant z `behavior.scaleUp` i `scaleDown` (polityki Percent/Pods), 2–10 replik |
| `load.yaml` | generator ruchu w klastrze: pod, który w pętli pobiera stronę z `hpa-service` (`wget`) |
| `load_test.py` | generator z laptopa (Python + `requests`) przez `kubectl port-forward` |

Przyda się **trzy terminale**: T1 na komendy, T2 i T3 na podgląd.

## Krok po kroku

**1. Aplikacja, Service i HPA**

T1:
```bash
kubectl apply -f deployment.yaml -f service.yaml -f hpa.yaml
kubectl get deploy hpa-test
kubectl get hpa hpa-test
```
Co powinieneś zobaczyć: Deployment `1/1`. W HPA `TARGETS` przez pierwsze 30–60 s ma `cpu: <unknown>/50%`, bo metrics-server nie zebrał jeszcze pomiarów z nowego poda.

**2. Poczekaj na metryki**
```bash
kubectl get hpa hpa-test          # powtarzaj co kilkanaście sekund
kubectl top pods -l app=hpa-test
```
Co powinieneś zobaczyć: `TARGETS cpu: 0%/50%`, `MINPODS 1`, `MAXPODS 5`, `REPLICAS 1`. `kubectl top` pokazuje zużycie CPU poda (np. `0m`–`1m`). Dopóki jest `<unknown>`, HPA nic nie skaluje. Jeśli `<unknown>` zostaje dłużej niż 2 min: `kubectl describe hpa hpa-test` (Events) — zwykle brak metrics-server albo brak `requests.cpu` w podzie.

**3. Podgląd w dwóch terminalach**

T2: `kubectl get hpa hpa-test -w`
T3: `kubectl get pods -l app=hpa-test -w`

**4a. Obciążenie — wariant A: generator w klastrze (zalecany)**

T1:
```bash
kubectl apply -f load.yaml
kubectl get pods -l app=load       # 1/1 Running
```
`load.yaml` to Deployment z jednym podem `busybox`, który w nieskończonej pętli robi `wget http://hpa-service`. Ruch idzie przez Service, więc trafia do wszystkich replik `hpa-test`, także tych dołożonych przez HPA.

Co powinieneś zobaczyć po 1–2 min:
- T2: `TARGETS` rośnie wysoko ponad cel (np. `cpu: 250%/50%`), a `REPLICAS` rośnie: 1 → 4 → 5. Więcej niż 5 nie będzie (`maxReplicas`).
- T3: nowe pody `hpa-test-…` w `ContainerCreating`, po chwili `Running`.
- Po dołożeniu replik procent na pod spada, bo ten sam ruch dzieli się na więcej podów.

Za mało obciążenia (`TARGETS` poniżej 50%)? `kubectl scale deploy load --replicas=3`.

**4b. Obciążenie — wariant B: skrypt z laptopa**

Potrzebny Python 3 i biblioteka `requests`:
```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install requests
```
W osobnym terminalu (T4) tunel do Service: `kubectl port-forward svc/hpa-service 8080:80`. Potem w T1:
```bash
python3 load_test.py --url http://localhost:8080 --concurrency 50 --duration 300
```
Skrypt przez 300 s wysyła równolegle (50 wątków) żądania GET i POST i co kilka sekund wypisuje postęp: liczbę zapytań, udanych, nieudanych i RPS. Przerwiesz go `Ctrl+C`. Uwaga: `port-forward` wysyła cały ruch do **jednego** poda, a nie przez Service. HPA doda repliki, ale nowe pody nie dostaną ruchu, więc średni procent szybko spadnie. Dlatego na pokaz skalowania lepszy jest wariant A.

**5. Koniec obciążenia i skalowanie w dół**

T1:
```bash
kubectl delete -f load.yaml        # albo Ctrl+C w load_test.py
```
Co powinieneś zobaczyć:
- T2: w ciągu ok. minuty `TARGETS` spada do `cpu: 0%/50%`, ale `REPLICAS` zostaje na 5. To okno stabilizacji `stabilizationWindowSeconds: 300`: HPA czeka 5 min, zanim zacznie zabierać repliki (chroni przed „piłą” przy chwilowym spadku ruchu).
- Po ok. 5 min `REPLICAS` spada o 1 na minutę (polityka `Pods: 1 / 60 s`): 5 → 4 → 3 → 2 → 1. W T3 pody przechodzą w `Terminating`.

**6. Dla chętnych: hpa-advanced.yaml**
```bash
kubectl apply -f hpa-advanced.yaml   # ta sama nazwa hpa-test: podmienia hpa.yaml
kubectl get hpa hpa-test             # MINPODS 2, REPLICAS od razu 2
kubectl apply -f load.yaml
```
Co powinieneś zobaczyć: przy obciążeniu repliki rosną szybciej (bez okna w górę, +50% albo +2 pody co 15 s, wygrywa większa liczba), aż do 10. W dół znów co najwyżej 1 pod na minutę, nigdy poniżej 2.

## Sprzątanie
```bash
kubectl delete -f load.yaml --ignore-not-found
kubectl delete -f hpa.yaml -f service.yaml -f deployment.yaml
deactivate 2>/dev/null; rm -rf .venv   # jeśli tworzyłeś venv
```

## Uwagi
- HPA liczy procent od **requestu**, nie od limitu. Pod bez `requests.cpu` = `<unknown>` i brak skalowania.
- Deployment pod HPA nie powinien mieć `replicas` w pliku: każdy `kubectl apply` cofałby liczbę replik ustawioną przez HPA.
- HPA na pamięci ma sens rzadko: większość runtime'ów nie oddaje pamięci, repliki nie schodzą.
- Skalowanie od zdarzeń (kolejka, cron, Prometheus) i do zera: KEDA (https://keda.sh).
- HPA dodaje pody, ale nie węzły. Gdy w klastrze zabraknie miejsca, nowe pody są `Pending`, a węzły dokłada autoskaler węzłów (na EKS: Cluster Autoscaler albo Karpenter).
