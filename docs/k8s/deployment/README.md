# Dzień 2 — ściąga: Deployment

**Wizualizacja:** [deployment.html](deployment.html) — otwórz plik w przeglądarce (dwuklik albo `open deployment.html`). Jest tam symulator rolloutu z suwakami `maxSurge` i `maxUnavailable`, oś czasu sond i porównanie strategii.

Gotowe manifesty: `przyklady/k8s/03-deployment/` (RollingUpdate, Recreate, sondy), `przyklady/k8s/02-replicaset/`, `przyklady/k8s/04-configmap-secret/`. Ćwiczysz w lab07 (rollout, rollback, sondy, konfiguracja) i lab08 (blue/green, dla chętnych).

## W tym katalogu

| Plik | Co jest w środku |
|---|---|
| `README.md` (ten plik) | Deployment od początku do końca: obiekty, rollout, komendy, typowe problemy |
| [deployment.html](deployment.html) | to samo na rysunkach, z symulatorem rolloutu |
| [sondy.md](sondy.md) | startup, readiness, liveness: parametry, przykłady, częste błędy |
| [strategie-wdrozen.md](strategie-wdrozen.md) | RollingUpdate, Recreate, blue/green, canary, Argo Rollouts i Flagger |

## Od manifestu do działającej wersji

Deployment nie uruchamia podów sam. Tworzy ReplicaSet, a ReplicaSet tworzy pody. Każdy obiekt ma swój kontroler w controller-managerze.

```
Ty: kubectl apply -f web.yaml
        │
        ▼
Deployment web                        ← piszesz Ty: replicas, strategia, szablon poda
  │  tworzy po jednym ReplicaSecie na każdą wersję szablonu
  ├── ReplicaSet web-5d59d67564       ← rewizja 1, replicas: 0 (stara wersja, czeka na rollback)
  └── ReplicaSet web-7c6d8f9b4d       ← rewizja 2, replicas: 3 (aktualny szablon)
        │  tworzy pody z szablonu i pilnuje ich liczby
        ├── Pod web-7c6d8f9b4d-x2k9p
        ├── Pod web-7c6d8f9b4d-m4tqz
        └── Pod web-7c6d8f9b4d-r8bnc
```

| Obiekt | Za co odpowiada | Kto go tworzy |
|---|---|---|
| **Deployment** | wersje aplikacji: rollout, historia, rollback | Ty (`kubectl apply`) |
| **ReplicaSet** | liczba podów jednej wersji. Brakuje poda → tworzy nowy | Deployment |
| **Pod** | kontenery, które faktycznie działają na węźle | ReplicaSet |

Nazwy mówią, kto jest czyim rodzicem: ReplicaSet = nazwa Deploymentu + hash szablonu, pod = nazwa ReplicaSetu + losowy sufiks. Sprawdzisz to też w `ownerReferences`:

```bash
kubectl get deploy,rs,pods -l app=web
kubectl get pod <pod> -o jsonpath='{.metadata.ownerReferences[0].kind}/{.metadata.ownerReferences[0].name}{"\n"}'
```

ReplicaSetów nie edytujesz ręcznie. Zmieniasz Deployment, a on zarządza ReplicaSetami.

### Selektor i etykiety

Kontrolery nie szukają podów po nazwach, tylko po etykietach.

- `spec.selector.matchLabels` mówi, które pody należą do Deploymentu.
- `spec.template.metadata.labels` to etykiety, które dostanie każdy nowy pod. **Muszą zawierać wszystkie etykiety z selektora**, inaczej API odrzuci Deployment.
- Deployment dopisuje ReplicaSetom i podom etykietę `pod-template-hash`. Dzięki niej stary i nowy ReplicaSet nie liczą sobie nawzajem podów.
- Selektor jest **niezmienny**. Zmiana selektora = usunięcie Deploymentu i utworzenie od nowa.
- Dwa Deploymenty z takim samym selektorem w jednym namespace walczą o pody. Każda aplikacja ma mieć własną etykietę `app`.

### Manifest

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
  labels:
    app: web
  annotations:
    kubernetes.io/change-cause: "nginx 1.29"   # opis tej wersji w rollout history
spec:
  replicas: 3
  revisionHistoryLimit: 5          # ile starych ReplicaSetów trzymać do rollbacku
  progressDeadlineSeconds: 300     # po tylu sekundach bez postępu: ProgressDeadlineExceeded
  minReadySeconds: 5               # nowy pod musi być Ready tyle sekund, zanim się liczy
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app: web                     # niezmienne po utworzeniu
  template:
    metadata:
      labels:
        app: web                   # musi pasować do selektora
    spec:
      containers:
      - name: nginx                # tę nazwę podajesz w kubectl set image
        image: nginx:1.29
        ports:
        - name: http
          containerPort: 80
        readinessProbe:
          httpGet: {path: /, port: http}
          periodSeconds: 5
        resources:
          requests: {cpu: 50m, memory: 32Mi}
          limits: {cpu: 100m, memory: 64Mi}
```

## Rollout: co się dzieje przy zmianie obrazu

Rollout uruchamia **każda zmiana szablonu poda** (`spec.template`): obraz, zmienne, sondy, zasoby, etykiety, adnotacje szablonu. Zmiana `replicas` rolloutu nie uruchamia, to tylko skalowanie.

Po `kubectl set image deploy/web nginx=nginx:1.30` (albo po `apply` zmienionego pliku):

1. Deployment liczy hash nowego szablonu i tworzy nowy ReplicaSet z 0 replik.
2. Zwiększa liczbę replik nowego ReplicaSetu, a zmniejsza starego. O tempie decydują `maxSurge` i `maxUnavailable`.
3. Stary pod usuwa dopiero wtedy, gdy nowy jest **gotowy** (readinessProbe przeszła i minęło `minReadySeconds`).
4. Na końcu stary ReplicaSet ma 0 replik i zostaje w historii.

### maxSurge i maxUnavailable na 3 replikach

- `maxSurge` — ile podów może być **ponad** `replicas` w trakcie rolloutu. Ogranicza liczbę podów naraz, a więc i zużycie quoty.
- `maxUnavailable` — ile podów może być **niegotowych** poniżej `replicas`. Ogranicza spadek przepustowości.
- Oba pola przyjmują liczbę albo procent. Procent `maxSurge` zaokrągla się w górę, `maxUnavailable` w dół. Domyślne `25%`/`25%` przy 3 replikach daje więc `1`/`0`.
- Oba naraz nie mogą być zerem: rollout nie miałby jak ruszyć.

`maxSurge: 1`, `maxUnavailable: 0` — najwyżej 4 pody, zawsze 3 gotowe:

| Krok | Stare (v1) | Nowe (v2) | Podów razem | Gotowych |
|---|---|---|---|---|
| start | 3 | 0 | 3 | 3 |
| 1 | 3 | 1 startuje | 4 | 3 |
| 2 | 2 | 1 gotowy + 1 startuje | 4 | 3 |
| 3 | 1 | 2 gotowe + 1 startuje | 4 | 3 |
| koniec | 0 | 3 gotowe | 3 | 3 |

`maxSurge: 0`, `maxUnavailable: 1` — nigdy więcej niż 3 pody, chwilowo tylko 2 gotowe:

| Krok | Stare (v1) | Nowe (v2) | Podów razem | Gotowych |
|---|---|---|---|---|
| start | 3 | 0 | 3 | 3 |
| 1 | 2 | 1 startuje | 3 | 2 |
| 2 | 1 | 1 gotowy + 1 startuje | 3 | 2 |
| 3 | 0 | 2 gotowe + 1 startuje | 3 | 2 |
| koniec | 0 | 3 gotowe | 3 | 3 |

Na naszym klastrze każdy namespace ma ResourceQuota. Dodatkowy pod z `maxSurge` też musi się w niej zmieścić. Jeśli się nie mieści, nowy ReplicaSet nie utworzy poda i rollout stoi. Wtedy `maxSurge: 0`, `maxUnavailable: 1`.

### Sterowanie rolloutem

```bash
kubectl set image deploy/web nginx=nginx:1.30        # nowa wersja; nginx = nazwa kontenera
kubectl rollout status deploy/web                    # czeka na koniec; --timeout=2m
kubectl rollout history deploy/web                   # rewizje i CHANGE-CAUSE
kubectl rollout history deploy/web --revision=2      # szablon poda z rewizji 2
kubectl rollout undo deploy/web                      # wraca do poprzedniej rewizji
kubectl rollout undo deploy/web --to-revision=1      # wraca do konkretnej rewizji
kubectl rollout pause deploy/web                     # zmiany szablonu nie uruchamiają rolloutu...
kubectl rollout resume deploy/web                    # ...aż do resume: jeden rollout ze wszystkimi zmianami
kubectl rollout restart deploy/web                   # nowe pody z tym samym obrazem
kubectl get rs -l app=web                            # stary i nowy ReplicaSet, ile replik ma każdy
```

- `rollout undo` też jest rolloutem: tworzy nową rewizję z szablonem starej wersji.
- `rollout undo` nie zmienia Twojego pliku YAML. Po cofnięciu popraw plik, inaczej następny `apply` wróci do złej wersji.
- Na wstrzymanym Deploymencie `rollout undo` nie działa. Najpierw `resume`.
- `rollout restart` dopisuje do szablonu adnotację `kubectl.kubernetes.io/restartedAt` z aktualną datą. Szablon się zmienia, więc powstaje nowy ReplicaSet i normalny rollout.

### Opis zmian i historia

Flaga `--record` jest wycofana. Opis wersji daje adnotacja `kubernetes.io/change-cause` na Deploymencie:

```bash
kubectl set image deploy/web nginx=nginx:1.30
kubectl annotate deploy/web kubernetes.io/change-cause="nginx 1.30" --overwrite
kubectl rollout history deploy/web
```

Wygodniej trzymać adnotację w pliku (`metadata.annotations`) i zmieniać ją razem z obrazem. Adnotacja, której nie nadpiszesz, przechodzi na następną rewizję z tym samym opisem.

### Pola, które pilnują rolloutu

| Pole | Domyślnie | Co robi |
|---|---|---|
| `revisionHistoryLimit` | 10 | ile starych ReplicaSetów (z 0 replik) zostaje. Starsze są usuwane. `0` = brak rollbacku |
| `progressDeadlineSeconds` | 600 | po tylu sekundach bez postępu warunek `Progressing=False`, powód `ProgressDeadlineExceeded`. **Deployment nie cofa się sam**, `rollout status` kończy się błędem |
| `minReadySeconds` | 0 | ile sekund nowy pod musi być Ready, zanim liczy się jako dostępny. Łapie aplikacje, które padają chwilę po starcie |

W `kubectl get deploy`: `READY` = gotowe/żądane, `UP-TO-DATE` = pody z aktualnym szablonem, `AVAILABLE` = gotowe od co najmniej `minReadySeconds`.

## Sondy w skrócie

Sonda startowa (startupProbe) daje aplikacji czas na start i wstrzymuje pozostałe sondy. Sonda gotowości (readinessProbe) decyduje, czy pod dostaje ruch i czy rollout może iść dalej. Sonda żywotności (livenessProbe) restartuje kontener, który się zawiesił.

| Sonda | Gdy nie przejdzie |
|---|---|
| **startupProbe** | po `failureThreshold` porażkach restart kontenera; do pierwszego sukcesu readiness i liveness nie działają |
| **readinessProbe** | pod wypada z EndpointSlice Service, nie dostaje ruchu. **Bez restartu.** W rolloucie: stary pod nie zostanie usunięty |
| **livenessProbe** | restart kontenera, rośnie licznik `RESTARTS`. Po kilku restartach z rzędu `CrashLoopBackOff` |

Bez readinessProbe pod jest gotowy, gdy tylko kontener wystartuje. Rollout usuwa wtedy stare pody, zanim nowe naprawdę działają. Szczegóły, parametry i częste błędy: [sondy.md](sondy.md).

## Strategie w skrócie

| Strategia | Kiedy | Koszt | Rollback |
|---|---|---|---|
| **RollingUpdate** (domyślna) | większość aplikacji bezstanowych | 0–`maxSurge` podów więcej przez czas rolloutu | `rollout undo`, czyli kolejny rollout |
| **Recreate** | wolumen `ReadWriteOnce`, dwie wersje nie mogą działać naraz, dev | brak dodatkowych podów, ale **przerwa w działaniu** | `rollout undo` i kolejna przerwa |
| **Blue/green** | ryzykowne wdrożenie, test nowej wersji przed wpuszczeniem ruchu | **2×** pody przez czas wdrożenia | natychmiastowy: selektor Service z powrotem na starą wersję |
| **Canary** | sprawdzenie nowej wersji na części użytkowników | kilka podów nowej wersji | szybki: waga 0 albo usunięcie nowej wersji |

Deployment ma tylko RollingUpdate i Recreate (`spec.strategy.type`). Blue/green i canary składasz z dwóch Deploymentów i Service albo HTTPRoute z wagami. Manifesty i porównanie: [strategie-wdrozen.md](strategie-wdrozen.md).

## Konfiguracja a rollout

Zmiana ConfigMapy albo Secretu **nie restartuje podów**. ConfigMapa to osobny obiekt, szablon poda się nie zmienia, więc Deployment nie ma czego wdrażać.

| Jak pod używa ConfigMapy | Co się dzieje po zmianie |
|---|---|
| zmienne (`env`, `envFrom`) | nic. Kontener przeczytał je raz, przy starcie |
| wolumen bez `subPath` | pliki odświeżają się po ok. minucie. Aplikacja musi sama je przeczytać od nowa (nginx czy Apache tego nie zrobią) |
| wolumen z `subPath` | nic. Plik nigdy się nie odświeża |

Trzy sposoby, żeby pody dostały nową konfigurację:

1. **`kubectl rollout restart deploy/web`** — najprostsze. Nowe pody czytają aktualną ConfigMapę.
2. **Hash konfiguracji w adnotacji szablonu.** Zmieniasz wartość przy każdej zmianie ConfigMapy, więc zmienia się szablon i rusza zwykły rollout. Tak robi Helm (`checksum/config`, dzień 5).
   ```yaml
   spec:
     template:
       metadata:
         annotations:
           config-hash: "3f9a1c2e"     # np. pierwsze znaki z: shasum -a 256 configmap.yaml
   ```
3. **Nowa ConfigMapa z nową nazwą** (`web-config-v2`) i zmiana odwołania w szablonie. Stara zostaje, więc `rollout undo` wraca też do starej konfiguracji.

Sam restart nie zapisuje w historii, co się zmieniło. Przy sposobach 2 i 3 widać to w `rollout history --revision=N`.

## Typowe problemy

| Objaw | Przyczyna | Co zrobić |
|---|---|---|
| `rollout status` wisi na `Waiting for deployment "web" rollout to finish: 1 out of 3 new replicas have been updated...` | nowy pod nie jest gotowy: readiness nie przechodzi, `ImagePullBackOff`, `CrashLoopBackOff` | `kubectl get pods -l app=web`, `kubectl describe pod <nowy-pod>` (Events). Nie da się szybko naprawić: `kubectl rollout undo deploy/web` |
| `error: deployment "web" exceeded its progress deadline`, w `describe deploy` warunek `ProgressDeadlineExceeded` | przez `progressDeadlineSeconds` rollout nie ruszył | jak wyżej. Deployment nie cofa się sam, stare pody dalej działają |
| nowy ReplicaSet ma `DESIRED 1`, `CURRENT 0`; w `kubectl describe rs <nowy-rs>`: `exceeded quota` | dodatkowy pod z `maxSurge` nie mieści się w ResourceQuota | `kubectl describe quota`. Ustaw `maxSurge: 0`, `maxUnavailable: 1`, zmniejsz `replicas` albo `requests` |
| `failed quota: ... must specify limits.cpu` (albo `requests.memory`...) | quota liczy zasoby, a kontener nie ma `resources` | dopisz `requests` i `limits` do każdego kontenera |
| `spec.template.metadata.labels: Invalid value: ...: selector does not match template labels` | etykiety szablonu nie zawierają etykiet z selektora | popraw `spec.template.metadata.labels` |
| `spec.selector: Invalid value: ...: field is immutable` | próbujesz zmienić selektor istniejącego Deploymentu | `kubectl delete deploy web` i `apply` od nowa |
| pody `Running`, ale `READY 0/1` | readinessProbe nie przechodzi: zła ścieżka, zły port, aplikacja jeszcze startuje | `kubectl describe pod` (Events: `Readiness probe failed`), `kubectl get endpointslices -l kubernetes.io/service-name=<service>` |
| po zmianie ConfigMapy aplikacja działa po staremu | ConfigMapa nie restartuje podów | `kubectl rollout restart deploy/web` (sekcja wyżej) |
| po `rollout undo` kolejny `apply` przywraca złą wersję | plik YAML dalej ma zły obraz | popraw plik; `undo` zmienia tylko obiekt w klastrze |
| po `set image` nic się nie dzieje | Deployment jest wstrzymany (`rollout pause`) | `kubectl rollout resume deploy/web` |

## Gdzie to ćwiczysz

| Co | Gdzie |
|---|---|
| Deployment, `set image`, `rollout status/history/undo`, sondy, ConfigMap, Secret | [lab07](../../../labs/lab07-deployment-konfiguracja/) |
| blue/green przez selektor Service (dla chętnych, zadanie 3) | [lab08](../../../labs/lab08-service-ingress/) |
| RollingUpdate z `change-cause`, Recreate, sondy z zasobami | [przyklady/k8s/03-deployment](../../../przyklady/k8s/03-deployment/) |
| ReplicaSet bez Deploymentu, adopcja „sierot” | [przyklady/k8s/02-replicaset](../../../przyklady/k8s/02-replicaset/) |
| konfiguracja z ConfigMapy i hasło z Secretu w Deploymencie | [przyklady/k8s/04-configmap-secret](../../../przyklady/k8s/04-configmap-secret/) |

Pola i ich opisy prosto z klastra:

```bash
kubectl explain deployment.spec.strategy.rollingUpdate
kubectl explain deployment.spec --recursive | less
```
