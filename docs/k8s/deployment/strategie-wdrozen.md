[← Deployment: spis](README.md)

# Dzień 2 — ściąga: strategie wdrożeń

Gotowe manifesty: `przyklady/k8s/03-deployment/` (RollingUpdate, Recreate), `przyklady/k8s/07-gateway-api/httproute-canary.yaml` (canary z wagami). Ćwiczysz w lab07 (rollout i rollback) i lab08 (blue/green, dla chętnych).

## Wbudowane w Deployment

Deployment ma dwie strategie, ustawiane w `spec.strategy.type`. Każda zmiana szablonu poda (`spec.template`: obraz, zmienne, sondy, zasoby, etykiety) tworzy nowy ReplicaSet i uruchamia rollout. Zmiana `replicas` rolloutu nie uruchamia.

### RollingUpdate (domyślna)

Nowe pody wchodzą stopniowo, stare wychodzą stopniowo. Przez chwilę działają obie wersje naraz.

```yaml
spec:
  replicas: 4
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1          # ile podów może być PONAD replicas w trakcie rolloutu
      maxUnavailable: 0    # ile podów może być NIEGOTOWYCH poniżej replicas
```

Wartości to liczby albo procenty z `replicas`. Procent `maxSurge` zaokrągla się w górę, `maxUnavailable` w dół. Oba naraz nie mogą być zerem.

| `maxSurge` / `maxUnavailable` | Jak przebiega (4 repliki) | Kiedy |
|---|---|---|
| `25%` / `25%` (domyślnie) | do 5 podów, min. 3 gotowe | rozsądny kompromis |
| `1` / `0` | do 5 podów, zawsze 4 gotowe; wolniej | **pełna przepustowość przez cały rollout**, potrzebny zapas na 1 pod |
| `0` / `1` | max 4 pody, min. 3 gotowe | **brak zapasu zasobów** (np. ciasna ResourceQuota), za to chwilowo mniejsza przepustowość |
| `100%` / `0` | od razu 8 podów, potem stare znikają | szybko i bez spadku przepustowości, ale chwilowo podwójne zasoby |

Na wspólnym klastrze z ResourceQuota `maxSurge` może zablokować rollout: dodatkowy pod nie mieści się w quocie i nie powstaje. Widać to w `kubectl describe rs <nowy-rs>` (`exceeded quota`). Wtedy `maxSurge: 0`, `maxUnavailable: 1`.

Warunek działania: **readinessProbe**. Bez niej Deployment uznaje nowy pod za gotowy, gdy tylko kontener wystartuje (szczegóły: [docs/k8s/deployment/sondy.md](sondy.md)).

### Recreate

Najpierw usuwa **wszystkie** stare pody, potem tworzy nowe. Między jednym a drugim aplikacja nie działa.

```yaml
spec:
  strategy:
    type: Recreate
```

Kiedy ma sens:
- wolumen `ReadWriteOnce` (np. dysk EBS) — może być podpięty tylko do jednego węzła. Przy RollingUpdate nowy pod na innym węźle wisi w `ContainerCreating` z błędem `Multi-Attach error`;
- dwie wersje aplikacji nie mogą działać jednocześnie (np. niezgodny schemat bazy, wyłączny dostęp do pliku lub kolejki);
- środowiska dev/test, gdzie przestój nie przeszkadza.

Zły obraz przy Recreate oznacza pełny przestój: stare pody już usunięte, nowe w `ImagePullBackOff`. Przykład: `przyklady/k8s/03-deployment/deployment-recreate.yaml`.

### Pola, które chronią rollout

| Pole | Domyślnie | Co robi |
|---|---|---|
| `minReadySeconds` | 0 | nowy pod musi być Ready przez tyle sekund, zanim liczy się jako dostępny. Łapie aplikacje, które padają chwilę po starcie |
| `progressDeadlineSeconds` | 600 | po tylu sekundach bez postępu Deployment dostaje warunek `Progressing=False`, powód `ProgressDeadlineExceeded`. **Nie cofa się sam** |
| `revisionHistoryLimit` | 10 | ile starych ReplicaSetów (z 0 replik) trzymać do `rollout undo` |

## Sterowanie rolloutem

```bash
kubectl rollout status deploy/<nazwa>               # czeka na koniec; kod wyjścia ≠ 0 po deadline
kubectl rollout history deploy/<nazwa>              # rewizje + change-cause
kubectl rollout undo deploy/<nazwa>                 # poprzednia rewizja; --to-revision=N
kubectl rollout pause deploy/<nazwa>                # kilka zmian bez rolloutu po każdej...
kubectl rollout resume deploy/<nazwa>               # ...i jeden rollout na koniec
kubectl rollout restart deploy/<nazwa>              # nowe pody bez zmiany obrazu (np. po zmianie ConfigMapy)
kubectl get rs -l app=<etykieta>                    # stary i nowy ReplicaSet, ile replik ma każdy
```

Opis zmiany: adnotacja `kubernetes.io/change-cause` (szczegóły w `przyklady/k8s/03-deployment/README.md`).

## Strategie spoza Deploymentu

Kubernetes nie ma typu `BlueGreen` ani `Canary`. Robi się je z kilku zwykłych zasobów: dwóch Deploymentów i Service albo trasy z wagami.

### Blue/green

Dwie pełne wersje działają obok siebie. Ruch idzie do jednej, przełączenie jest natychmiastowe i dotyczy wszystkich użytkowników naraz.

```
                Service web
                selector: app=web, version=blue    ← przełączasz tylko to pole
                       │
         ┌─────────────┴──────────────┐
  Deployment web-blue          Deployment web-green
  version: blue (v1, ruch)     version: green (v2, testy)
```

```bash
kubectl apply -f web-green.yaml                     # v2 wstaje obok, bez ruchu
kubectl port-forward deploy/web-green 8080:80       # testujesz v2 bezpośrednio
kubectl patch svc web -p '{"spec":{"selector":{"app":"web","version":"green"}}}'    # przełączenie
kubectl patch svc web -p '{"spec":{"selector":{"app":"web","version":"blue"}}}'     # rollback
kubectl delete deploy web-blue                      # gdy v2 się sprawdziła
```

- Plusy: v2 testujesz przed wpuszczeniem ruchu; rollback w sekundę, bo stare pody działają.
- Minusy: **podwójne zasoby** przez cały czas trwania; obie wersje muszą umieć pracować z tą samą bazą.
- Ćwiczenie: lab08, dla chętnych.

### Canary

Nowa wersja dostaje mały procent ruchu. Gdy metryki i logi są w porządku, zwiększasz procent aż do 100%.

**Wersja prosta — proporcja replik.** Dwa Deploymenty z tą samą etykietą `app`, jeden Service z selektorem tylko po `app`:

```
Service web (selector: app=web)
   ├── Deployment web-v1: 9 replik   → ok. 90% ruchu
   └── Deployment web-v2: 1 replika  → ok. 10% ruchu
```

Procent zależy od liczby podów, więc 1% wymaga 100 replik. Ruch rozkłada się mniej więcej, nie dokładnie.

**Wersja właściwa — wagi w HTTPRoute (Gateway API).** Dwa Service, a podział ruchu ustawiasz wagami niezależnie od liczby replik:

```yaml
rules:
- backendRefs:
  - name: web-v1
    port: 80
    weight: 90
  - name: web-v2
    port: 80
    weight: 10
```

Pełny plik: `przyklady/k8s/07-gateway-api/httproute-canary.yaml`. Przesunięcie ruchu = zmiana wag i `apply`.

### Automatyzacja

Ręczne przełączanie i zmiana wag sprawdzają się na szkoleniu. W produkcji robią to narzędzia, które same przesuwają ruch, sprawdzają metryki (np. procent błędów z Prometheusa) i cofają wdrożenie, gdy coś idzie źle:
- **Argo Rollouts** — zasób `Rollout` zamiast `Deployment`, strategie `blueGreen` i `canary`;
- **Flagger** — działa obok zwykłego Deploymentu, współpracuje z Gateway API, Istio, Linkerd, NGINX.

## Porównanie

| | Przestój | Dodatkowe zasoby | Rollback | Dwie wersje naraz | Kiedy |
|---|---|---|---|---|---|
| **RollingUpdate** | brak (z readiness) | 0–`maxSurge` podów | `rollout undo`, kolejny rollout | tak, przez chwilę | domyślnie, większość aplikacji |
| **Recreate** | **tak** | brak | `rollout undo` + kolejny przestój | nie | RWO, niezgodne wersje, dev |
| **Blue/green** | brak | **2×** przez czas wdrożenia | natychmiastowy (selektor) | tak, ale ruch tylko do jednej | ryzykowne wdrożenia, test przed ruchem |
| **Canary** | brak | mało (kilka podów v2) | szybki (waga 0 / usunięcie v2) | tak, celowo | sprawdzenie v2 na części użytkowników |

## PodDisruptionBudget a rollout

PDB (PodDisruptionBudget, dzień 3) **nie dotyczy rolloutu**. Chroni przed dobrowolnymi zakłóceniami: `kubectl drain`, aktualizacją węzłów, autoskalerem węzłów. O tym, ile podów może zniknąć w trakcie rolloutu, decydują `maxUnavailable` i readinessProbe.
