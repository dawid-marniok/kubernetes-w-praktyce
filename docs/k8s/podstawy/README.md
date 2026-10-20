# Dzień 2 — ściąga: podstawy Kubernetesa i kubectl

Jak działa klaster (architektura, droga od `kubectl apply` do kontenera, ruch do podów) na diagramach: otwórz w przeglądarce [`jak-dziala-kubernetes.html`](jak-dziala-kubernetes.html).

Gotowe manifesty: `przyklady/k8s/01-pod/` (pody, w tym trzy celowe awarie). Ćwiczysz w lab05 (kubectl) i lab06 (pody).

**Na naszym klastrze:** kontekst `szkolenie`, Twój namespace = Twój login, ustawiony w kontekście jako domyślny. W labach nie piszesz `-n` ani `namespace:` w plikach.

## Model w pięciu zdaniach

| Pojęcie | Czym jest |
|---|---|
| **Klaster** | control plane (mózg) + węzły robocze (maszyny, na których działają kontenery). U nas EKS: control plane prowadzi AWS, węzły to instancje EC2 |
| **Control plane** | API server, etcd (baza stanu), scheduler (wybiera węzeł dla poda), controller manager (pętle, które doprowadzają stan do opisanego) |
| **Węzeł** | maszyna z kubeletem i runtime'em kontenerów (containerd). Kubelet uruchamia pody, które scheduler przypisał do węzła |
| **API server** | jedyne wejście do klastra. kubectl, kontrolery i kubelety rozmawiają tylko z nim, przez HTTPS i REST |
| **Obiekt** | wpis w API: `spec` = co chcesz (Ty piszesz), `status` = co jest (pisze klaster). Kontrolery w pętli zbliżają `status` do `spec` |
| **Namespace** | przegródka na obiekty: nazwy, uprawnienia i quota obowiązują w jej obrębie. Część zasobów (węzły, PV, StorageClass) nie należy do żadnego namespace'u |

Opisujesz stan docelowy (deklaratywnie), a nie kroki. „Chcę 3 pody nginx:1.29” — klaster sam tworzy brakujące i zastępuje te, które padły.

## Jak kubectl rozmawia z API

kubectl czyta plik **kubeconfig** (`~/.kube/config`, albo ścieżka w zmiennej `KUBECONFIG`). Są w nim trzy listy:

| Wpis | Co zawiera |
|---|---|
| `clusters` | adres API servera i certyfikat CA klastra |
| `users` | jak się uwierzytelnić: token, certyfikat albo komenda (u nas `aws eks get-token` — tożsamość z konta AWS) |
| `contexts` | para klaster + użytkownik + **domyślny namespace**; `current-context` mówi, którego używasz teraz |

Każda komenda kubectl to żądanie HTTP do API servera. API sprawdza kim jesteś (uwierzytelnienie), co Ci wolno (RBAC) i czy obiekt jest poprawny (walidacja, admission, quota). Dopiero potem zapisuje go w etcd.

Co możesz na naszym klastrze:
- w swoim namespace: tworzyć, zmieniać i usuwać prawie wszystko (rola `edit` + Role i LimitRange do labów),
- w całym klastrze: tylko czytać (rola `view`, bez Secretów) + podgląd węzłów, PV, StorageClass, CRD,
- ResourceQuota w swoim namespace: tylko odczyt.

## Kontekst i namespace

```bash
kubectl config current-context                  # z którym klastrem rozmawiasz
kubectl config get-contexts                     # wszystkie konteksty; * = bieżący, kolumna NAMESPACE
kubectl config use-context szkolenie            # przełącz kontekst
kubectl config set-context --current --namespace=<login>   # domyślny namespace w bieżącym kontekście
kubectl config view --minify                    # tylko bieżący kontekst (bez sekretów)
kubectl auth whoami                             # kim jesteś dla API (użytkownik, grupy)
kubectl auth can-i create deployments           # czy wolno; odpowiedź yes/no
kubectl auth can-i delete pods -n <inny-login>  # w cudzym namespace: no
kubectl auth can-i --list                       # wszystko, co wolno Ci w bieżącym namespace
```

- Zanim coś usuniesz albo zmienisz, sprawdź kontekst. Masz kilka klastrów (kind, praca) — łatwo trafić w zły.
- `-n <namespace>` w jednej komendzie nadpisuje domyślny namespace. W labach go nie potrzebujesz.
- ⚠ Nie pokazuj na udostępnionym ekranie `kubectl config view --raw` — są tam klucze i tokeny.

## Poznawanie API

```bash
kubectl version                                 # wersja klienta i serwera
kubectl api-resources                           # wszystkie typy: nazwa, skrót, grupa API, NAMESPACED, KIND
kubectl api-resources --namespaced=false        # typy poza namespace'ami (nodes, persistentvolumes…)
kubectl api-resources --api-group=apps          # tylko jedna grupa
kubectl api-versions                            # grupy i wersje API na klastrze
kubectl explain pod                             # opis typu
kubectl explain pod.spec.containers.resources   # opis jednego pola
kubectl explain deployment.spec --recursive     # całe drzewo pól, bez opisów
```

`explain` pokazuje dokumentację z Twojego klastra, w jego wersji. Gdy nie pamiętasz, jak się nazywa pole albo gdzie leży w YAML-u — zacznij tutaj, nie w wyszukiwarce.

## Czytanie: get

```bash
kubectl get pods                                # pody w Twoim namespace
kubectl get pods -o wide                        # + IP poda, węzeł
kubectl get pod web -o yaml                     # pełny obiekt: spec, status, metadata
kubectl get pod web -o json
kubectl get pods,svc,deploy                     # kilka typów naraz
kubectl get all                                 # najczęstsze typy (bez ConfigMap, Secret, Ingress, PVC)
kubectl get pods --show-labels                  # + etykiety
kubectl get pods -l app=web                     # filtr po etykiecie
kubectl get pods -l 'app in (web,api),env!=prod'
kubectl get pods --field-selector status.phase=Running
kubectl get pods -w                             # obserwuj zmiany na żywo; wyjście Ctrl-C
kubectl get pods -A                             # wszystkie namespace'y (tylko do czytania!)
kubectl get pods --sort-by=.metadata.creationTimestamp
```

Wyciąganie pojedynczych pól:

```bash
kubectl get pod web -o jsonpath='{.status.podIP}{"\n"}'
kubectl get pods -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.spec.nodeName}{"\n"}{end}'
kubectl get pods -o custom-columns=NAZWA:.metadata.name,OBRAZ:.spec.containers[0].image,WEZEL:.spec.nodeName
kubectl get pods -o name                        # pod/web, pod/api… — wygodne w skryptach
```

| Format `-o` | Kiedy |
|---|---|
| `wide` | szybki przegląd z IP i węzłem |
| `yaml` / `json` | cały obiekt; szukasz pola do `jsonpath` albo powodu w `status` |
| `jsonpath='{…}'` | jedno albo kilka pól, do skryptu lub na czat |
| `custom-columns=…` | własna tabela z wybranych pól |
| `name` | same nazwy `typ/nazwa` |

> W PowerShell `jsonpath` i `custom-columns` też działają; apostrofy zostaw, a `{"\n"}` zamień na `{"`n"}` albo pomiń.

## Opis i zdarzenia: describe, events

```bash
kubectl describe pod web                        # stan, kontenery, Last State, warunki, Events na dole
kubectl describe deploy web
kubectl describe resourcequota                  # ile quoty zużyłeś i ile zostało
kubectl get events --sort-by=.lastTimestamp     # zdarzenia w namespace, najnowsze na końcu
kubectl events                                  # to samo, od razu posortowane po czasie
kubectl events --for pod/web                    # zdarzenia jednego obiektu
kubectl events --types=Warning                  # tylko ostrzeżenia
kubectl get events --field-selector type=Warning
```

- `describe` to najważniejsza komenda przy awarii. Sekcja **Events** mówi, co klaster próbował zrobić i na czym utknął.
- Zdarzenia znikają po godzinie. Brak zdarzeń dla starego poda nie znaczy, że nic się nie stało.

## Tworzenie i zmiany

```bash
kubectl apply -f moje/web.yaml                  # utwórz albo zaktualizuj z pliku
kubectl apply -f moje/                          # wszystkie pliki z katalogu
kubectl apply -f moje/web.yaml -f moje/svc.yaml
kubectl diff -f moje/web.yaml                   # co by się zmieniło, bez zmieniania
kubectl delete -f moje/web.yaml                 # usuń to, co jest w pliku
```

Szkielety YAML zamiast pisania z pamięci (`--dry-run=client` nic nie tworzy na klastrze):

```bash
kubectl run web --image=nginx:1.29 --port=80 --labels=app=web --dry-run=client -o yaml > moje/pod.yaml
kubectl create deployment web --image=nginx:1.29 --replicas=2 --port=80 --dry-run=client -o yaml > moje/deploy.yaml
kubectl create service clusterip web --tcp=80:80 --dry-run=client -o yaml > moje/svc.yaml
kubectl create configmap app-config --from-literal=ENV=dev --dry-run=client -o yaml > moje/cm.yaml
kubectl create secret generic db --from-literal=PASSWORD=changeme --dry-run=client -o yaml > moje/secret.yaml
kubectl create job raz --image=busybox:1.37 --dry-run=client -o yaml -- echo ok > moje/job.yaml
```

Potem dopisz `resources`, usuń `status: {}` i `creationTimestamp: null`, zapisz i zrób `apply`.

Szybkie zmiany na żywym obiekcie (wygodne przy eksperymentach, ale plik w `moje/` przestaje się zgadzać z klastrem):

```bash
kubectl edit deploy web                         # otwiera obiekt w edytorze; zapis = zmiana (KUBE_EDITOR="code --wait")
kubectl scale deploy web --replicas=3           # liczba replik
kubectl set image deploy/web web=nginx:1.29     # nowy obraz kontenera "web" → nowy rollout
kubectl patch deploy web -p '{"spec":{"replicas":2}}'          # zmiana fragmentu (strategic merge)
kubectl patch deploy web --type=merge --patch-file=zmiana.yaml # łatka z pliku (wygodne w PowerShell)
kubectl label pod web env=dev                   # dodaj etykietę
kubectl label pod web env=prod --overwrite      # zmień istniejącą
kubectl label pod web env-                      # usuń etykietę (minus na końcu)
kubectl annotate deploy web opis="wersja testowa"
kubectl annotate deploy web opis-               # usuń adnotację
```

Usuwanie:

```bash
kubectl delete pod web                          # jeden obiekt (czeka na łagodne zamknięcie, domyślnie do 30 s)
kubectl delete pod -l app=web                   # wszystkie z etykietą
kubectl delete pod web --grace-period=5         # krótszy czas na SIGTERM
kubectl delete pod web --now                    # od razu (grace-period 1 s)
kubectl delete pod -l app=web --interactive     # zapyta przed usunięciem
```

- Pod zarządzany przez Deployment po `delete` wraca z nową nazwą: kontroler odtwarza liczbę replik. Usuwasz Deployment, nie pod.
- `--force --grace-period=0` zostaw na sytuację, gdy węzeł nie odpowiada. Na zwykłym podzie nie przyspiesza niczego, co ma znaczenie.

## Imperatywnie czy deklaratywnie

| | Imperatywnie: `run`, `create`, `scale`, `set`, `edit` | Deklaratywnie: `apply -f` |
|---|---|---|
| Co mówisz | „zrób to teraz” | „ma być tak, jak w pliku” |
| Ślad | tylko w historii terminala | plik, który leży w gicie |
| Powtórzenie | `create` drugi raz → `AlreadyExists` | `apply` drugi raz → `unchanged` |
| Kiedy | szybki test, generowanie szkieletu (`--dry-run=client -o yaml`), awaria o 3 w nocy | wszystko, co ma przetrwać i dać się odtworzyć |

W labach piszesz pliki do `moje/` i robisz `kubectl apply -f moje/…`. Masz wtedy zapis tego, co zrobiłeś, możesz poprawić plik i zastosować go ponownie, a na koniec usunąć wszystko jedną komendą `kubectl delete -f moje/…`. Tak samo pracuje się w zespole: manifesty w repozytorium, a na klaster trafiają przez `apply`, Helm albo GitOps.

Po `kubectl edit` czy `scale` przenieś zmianę do pliku. Inaczej następny `apply` ją cofnie.

## Debug: logs, exec, port-forward, cp, debug, top

```bash
kubectl logs web                                # stdout i stderr kontenera
kubectl logs -f web                             # śledź na żywo; wyjście Ctrl-C
kubectl logs web --tail=20 --since=10m          # ostatnie 20 linii z 10 minut
kubectl logs web --previous                     # poprzednie uruchomienie (po restarcie, CrashLoopBackOff)
kubectl logs web -c sidecar                     # wybrany kontener w podzie z kilkoma
kubectl logs web --all-containers
kubectl logs -l app=web --prefix                # z wielu podów naraz, z nazwą poda
kubectl logs deploy/web                         # z jednego poda Deploymentu

kubectl exec web -- env                         # jedna komenda w kontenerze
kubectl exec -it web -- sh                      # powłoka (bash, jeśli jest w obrazie); wyjście: exit
kubectl exec -it web -c sidecar -- sh

kubectl port-forward pod/web 8080:80            # localhost:8080 → port 80 poda; działa, dopóki nie Ctrl-C
kubectl port-forward svc/web 8080:80            # przez Service (wybiera jeden pod)

kubectl cp web:/etc/nginx/nginx.conf ./nginx.conf   # z poda na laptop (w obrazie musi być tar)
kubectl cp ./index.html web:/tmp/index.html          # z laptopa do poda

kubectl debug -it web --image=busybox:1.37 --target=web   # ephemeral container obok działającego kontenera
kubectl debug web -it --image=busybox:1.37 --copy-to=web-debug   # kopia poda z dodatkowym kontenerem

kubectl top pod                                 # zużycie CPU i pamięci (metrics-server)
kubectl top pod --containers
kubectl top node
```

- `--` oddziela opcje kubectl od komendy w kontenerze. Bez tego `kubectl exec web ls -la` potraktuje `-la` jako flagę kubectl.
- `-c <kontener>` przy `logs` i `exec` w podzie z kilkoma kontenerami. Bez tego trafiasz do domyślnego (zwykle pierwszego).
- `kubectl debug` przydaje się, gdy w obrazie nie ma powłoki (distroless) albo narzędzi. `--target` pozwala widzieć procesy kontenera aplikacji. Ephemeral container zostaje w podzie do jego usunięcia. Kopię (`--copy-to`) usuń sam: `kubectl delete pod web-debug`.
- `port-forward` to narzędzie do testów z laptopa, nie sposób na wystawienie aplikacji. Do tego są Service i Ingress ([ingress-gateway](../ingress-gateway/README.md)).

## Rollout

```bash
kubectl rollout status deploy/web               # czekaj, aż nowa wersja wstanie
kubectl rollout history deploy/web              # rewizje
kubectl rollout undo deploy/web                 # wróć do poprzedniej
kubectl rollout restart deploy/web              # nowe pody z tą samą konfiguracją
```

Flaga `--record` jest wycofana. Opis zmiany w historii daje adnotacja `kubernetes.io/change-cause`. Więcej o rolloutach, sondach i strategiach: [`../deployment/README.md`](../deployment/README.md).

## Pod nie działa: wzorzec diagnozy

Zawsze ta sama kolejność:

1. **`kubectl get pods`** — STATUS, READY, RESTARTS. Daje kierunek.
2. **`kubectl describe pod <nazwa>`** — Events na dole, `State` i `Last State` kontenera (powód, kod wyjścia).
3. **`kubectl logs <nazwa> --previous`** — co aplikacja napisała, zanim padła. Bez `--previous` widzisz bieżące uruchomienie, często puste.
4. **`kubectl exec -it <nazwa> -- sh`** — gdy pod działa, ale zachowuje się źle: zmienne, pliki, połączenia z wnętrza.

| STATUS | Co znaczy | Co sprawdzić |
|---|---|---|
| `Pending` | scheduler nie znalazł węzła albo czeka | `describe` → Events: `Insufficient cpu/memory` (za duże requests), PVC bez wolumenu, nodeSelector/affinity, taint węzła |
| `ContainerCreating` | węzeł przygotowuje pod | długo? `describe`: wolumen się nie podpina, brak ConfigMap/Secret montowanego jako plik, problem z siecią |
| `ErrImagePull`, `ImagePullBackOff` | nie da się pobrać obrazu | literówka w nazwie lub tagu, prywatny rejestr bez dostępu, limit Docker Hub. Events pokażą dokładny komunikat |
| `CrashLoopBackOff` | kontener startuje i kończy się, klaster restartuje go coraz rzadziej | `logs --previous`, `describe` → `Last State` i `Exit Code`, zła komenda lub brak zmiennej |
| `OOMKilled` (w `Last State`), kod 137 | przekroczony limit pamięci | `describe`, `resources.limits.memory`, `kubectl top pod` |
| `CreateContainerConfigError` | brakuje czegoś do konfiguracji kontenera | ConfigMap, Secret lub klucz z `env`/`envFrom` nie istnieje — nazwa w Events |
| `Completed` | proces skończył się kodem 0 | dla Joba to sukces; dla serwera (Deployment) znaczy, że komenda nie działa w tle — sprawdź `command`/`args` |
| `Running`, ale READY `0/1` | readinessProbe nie przechodzi | `describe` → Events `Readiness probe failed`, ścieżka i port sondy ([sondy](../deployment/sondy.md)) |
| `Terminating` długo | pod czeka na zamknięcie procesu | proces ignoruje SIGTERM; poczekaj do końca `terminationGracePeriodSeconds` |

Pod w ogóle się nie pojawił po `apply` Deploymentu? Problem jest piętro wyżej: `kubectl describe rs` albo `kubectl get events` (np. quota, Pod Security, brak `resources`).

## Skróty i wygoda

Krótkie nazwy zasobów (pełna lista: kolumna SHORTNAMES w `kubectl api-resources`):

| Skrót | Zasób | Skrót | Zasób |
|---|---|---|---|
| `po` | pods | `cm` | configmaps |
| `deploy` | deployments | `sa` | serviceaccounts |
| `rs` | replicasets | `pvc` / `pv` | persistentvolumeclaims / persistentvolumes |
| `svc` | services | `ns` | namespaces |
| `ing` | ingresses | `no` | nodes |
| `sts` | statefulsets | `ds` | daemonsets |
| `cj` | cronjobs | `hpa` | horizontalpodautoscalers |
| `netpol` | networkpolicies | `ev` | events |
| `quota` | resourcequotas | `limits` | limitranges |

Secret nie ma skrótu: `kubectl get secret`.

Alias `k` i autouzupełnianie (Tab uzupełnia komendy, typy i nazwy obiektów z klastra):

```bash
# bash (~/.bashrc)
alias k=kubectl
source <(kubectl completion bash)
complete -o default -F __start_kubectl k

# zsh (~/.zshrc)
alias k=kubectl
source <(kubectl completion zsh)          # alias k uzupełnia się sam
```

```powershell
# PowerShell ($PROFILE)
Set-Alias -Name k -Value kubectl
kubectl completion powershell | Out-String | Invoke-Expression
Register-ArgumentCompleter -CommandName k -ScriptBlock $__kubectlCompleterBlock
```

`kubectx` i `kubens` (opcjonalnie): to samo co `kubectl config use-context` i `set-context --current --namespace=…`, tylko krócej. Instalacja i przykłady w lab05.

```bash
kubectx szkolenie        # przełącz kontekst
kubectx -                # wróć do poprzedniego
kubens <login>           # domyślny namespace
```

Bieżący kontekst i namespace w prompcie terminala: `kube-ps1` albo `starship`. Przy kilku klastrach to oszczędza pomyłek.

## Na wspólnym klastrze: czego unikać

- **`kubectl delete … --all` albo `-A` przy `delete`.** Do cudzych namespace'ów nie masz prawa zapisu, więc tam dostaniesz `Forbidden`. Ale w swoim usuniesz wszystko, łącznie z rzeczami z poprzednich labów. Usuwaj po pliku (`-f`) albo po etykiecie (`-l app=lab06-…`).
- **Komend „na ślepo” w złym kontekście.** Przed `delete` i `apply` spójrz na `kubectl config current-context`. To samo `--all` na klastrze w pracy kosztuje dużo więcej.
- **Pracy w cudzym namespace.** `-n <inny-login>` do czytania działa (rola `view`), do zmian nie. Nie podglądaj sąsiadom ConfigMap z hasłami tylko dlatego, że możesz.
- **Obrazów bez tagu i `:latest`.** Zawsze `nginx:1.29`, `busybox:1.37`.
- **Kontenerów bez `resources`.** LimitRange dopisze domyślne wartości, ale zużyjesz więcej quoty, niż trzeba. Brak quoty = kolejne pody w `Pending`.
- **Nieposprzątanych zasobów.** Każdy lab kończy się sekcją „Sprzątanie”. Pody, PVC i Service LoadBalancer zajmują wspólne zasoby i kosztują.
- **`kubectl config view --raw` na udostępnionym ekranie.**

## Sprzątanie

```bash
kubectl delete -f moje/                         # wszystko, co utworzyłeś z plików w moje/
kubectl delete pod,deploy,svc -l app=lab06-web  # po etykiecie, kilka typów naraz
kubectl get all                                 # co jeszcze zostało
kubectl get pvc,cm,secret,ing                   # tego get all nie pokazuje
```

## Gdzie to ćwiczysz

- [Lab 05 — kubectl: kontekst, API, zdarzenia, węzły](../../../labs/lab05-kubectl/)
- [Lab 06 — pierwsze pody, diagnoza poda, etykiety](../../../labs/lab06-pod/)
- [Przykłady: Pod](../../../przyklady/k8s/01-pod/) — `pod-zly-obraz.yaml`, `pod-crashloop.yaml`, `pod-oom.yaml` to trzy awarie z tabeli wyżej do samodzielnej diagnozy
