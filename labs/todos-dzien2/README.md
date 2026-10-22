# ToDos · dzień 2 — Twoja aplikacja pod własnym adresem

**Cel:** ToDos z dnia 1 (obrazy `todos-api` i `todos-web` w Twoim rejestrze) działa w Twoim namespace i ma adres z internetu. Manifesty piszesz sam, z obiektów z dzisiaj: Secret, ConfigMap, Deployment, Service, Ingress.
**Środowisko:** wspólny klaster, Twój namespace. Nie piszesz `-n` ani `namespace:`.

ToDos zostaje w Twoim namespace do końca szkolenia. Każdego dnia na koniec dokładasz do niego to, co poznałeś: jutro dysk dla bazy i zasoby, w dniu 4 bezpieczeństwo, w dniu 5 Helm i monitoring.

Tu masz tylko wymagania. Jak je spełnisz, decydujesz sam. Utknąłeś: gotowe manifesty i opis są w [`rozwiazanie/`](rozwiazanie/). Zajrzyj najpierw do jednego pliku, a nie od razu do wszystkich.

```
przeglądarka ──► Ingress ──► Service web:80 ──► pody web (nginx :8080) ──/api──► Service api:3001 ──► pody api ──► Service mongo:27017 ──► pod mongo
```

**Od trenera na czacie:** domena szkolenia (`<DOMENA>`) i nazwa ClusterIssuera (ten sam co w lab08, krok 4). Twój adres: `https://todos-<login>.<DOMENA>`.
`<REJESTR>` masz w punkcie 1 karty dostępowej (ten sam co w lab04, np. `123456789012.dkr.ecr.eu-central-1.amazonaws.com/jkowalski`).

## Zanim zaczniesz

Quota liczy wszystko w namespace. Usuń obiekty z labów 06–08:

```bash
kubectl delete deploy,pod,svc,ingress -l 'app.kubernetes.io/part-of!=todos'
kubectl describe resourcequota          # Used dla pods i requests.cpu blisko zera
```

Obrazy z lab04 muszą być w rejestrze:

```bash
aws ecr describe-images --profile szkolenie --region eu-central-1 --repository-name <login>/todos-api --query 'imageDetails[].imageTags'
```

Brak obrazu → wróć do lab04, krok 6 (Mac M: `buildx --platform linux/amd64`).

## Wymagania

**Wszystkie obiekty**
- mają etykietę `app.kubernetes.io/part-of: todos` (po niej sprzątanie wieczorem omija ToDos),
- każdy kontener ma `resources` (requests i limits). Quota w namespace jest ciasna: Mongo potrzebuje ok. 256Mi, api i web po kilkadziesiąt Mi.

**Secret z danymi do bazy**
- użytkownik `root` i hasło, które wymyślisz sam: litery i cyfry, bez znaków specjalnych (trafia do adresu URI). Nie zapisuj go w plikach w repo, Secret utwórz z linii poleceń,
- api potrzebuje pełnego adresu bazy: `mongodb://root:<hasło>@mongo:27017/todos?authSource=admin`. Trzymaj go w tym samym Secrecie.

**ConfigMap z konfiguracją**
- web (nginx) czyta `API_HOST` i `API_PORT`: pod jaką nazwą i na jakim porcie szukać api,
- api czyta `PORT`: na jakim porcie słucha (3001).

**MongoDB**
- Deployment z jedną repliką, obraz `mongo:7.0`, **bez dysku** (celowo, jutro zobaczysz, co z tego wynika),
- użytkownika root tworzą zmienne `MONGO_INITDB_ROOT_USERNAME` i `MONGO_INITDB_ROOT_PASSWORD`, wartości z Secretu,
- przy zmianie wersji stary pod ma zniknąć, zanim wstanie nowy: dwa pody bazy naraz to proszenie się o kłopoty (którą strategię wybierzesz?),
- Service o nazwie `mongo` na porcie 27017. Ta nazwa jest w adresie bazy.

**api**
- Deployment z dwiema replikami, obraz `<REJESTR>/todos-api:1.0.0`, kontener słucha na 3001,
- `MONGODB_URI` z Secretu, reszta konfiguracji z ConfigMapy,
- pod jest gotowy dopiero, gdy api ma połączenie z bazą: `GET /api/health` zwraca wtedy 200, a bez bazy 503,
- Service o nazwie `api` na porcie 3001. Pod tą nazwą szuka go nginx w obrazie web.

**web**
- Deployment z dwiema replikami, obraz `<REJESTR>/todos-web:1.0.0`, kontener słucha na 8080,
- konfiguracja z ConfigMapy,
- Service `web` na porcie 80.

**Ingress**
- klasa `traefik` (jak w lab08), host `todos-<login>.<DOMENA>`, ścieżka `/` do Service `web`. Ścieżka `/api` nie jest potrzebna: nginx w web sam przekazuje ją do api.
- HTTPS z certyfikatem od Let's Encrypt jak w lab08 (krok 4): adnotacja `cert-manager.io/cluster-issuer` i sekcja `tls` z Secretem `todos-tls`. Bez tego przeglądarka pokaże ostrzeżenie (domena `.dev` działa w przeglądarce tylko po HTTPS). Ten sam host i Secret wykorzystasz w dniu 5.

> **Skąd klaster ma dostęp do ECR?** Nie tworzysz Secretu `docker-registry` ani `imagePullSecrets`. Obraz pobiera węzeł, nie pod: rola IAM węzłów ma `AmazonEC2ContainerRegistryReadOnly`, a kubelet sam bierze token do ECR i go odnawia. Działa to dla ECR na tym samym koncie AWS. Prywatny Docker Hub czy GHCR wymagałyby Secretu. Więcej: [`docs/k8s/rejestr/ecr.html`](../../docs/k8s/rejestr/ecr.html) (otwórz w przeglądarce).

Ściąga: `kubectl explain deployment.spec.strategy`, `kubectl explain pod.spec.containers.env.valueFrom`, `kubectl create secret generic --help`, wzorce w [`przyklady/k8s/`](../../przyklady/k8s/).

## Jak sprawdzić

```bash
kubectl get pods -l app.kubernetes.io/part-of=todos      # wszystko Running i READY
kubectl logs deploy/api                                  # „Połączono z MongoDB”
kubectl port-forward svc/web 8080:80                     # http://localhost:8080, Ctrl-C po teście
kubectl get certificate                                  # todos-tls  READY True (po ok. minucie)
curl -s https://todos-<login>.<DOMENA>/api/health        # {"status":"ok","db":"connected"}
```

## SUKCES

Twój ToDos działa pod `https://todos-<login>.<DOMENA>` bez ostrzeżenia o certyfikacie, dodane zadanie zostaje po odświeżeniu strony, a `kubectl get all,ingress -l app.kubernetes.io/part-of=todos` pokazuje 3 Deploymenty, 3 Service i Ingress. **Wklej adres na czat** — sprawdzimy sobie nawzajem.

Nie usuwaj ToDos. Zostaje na jutro.

## Dla chętnych

- `kubectl scale deploy api --replicas=3` i usuwaj pody api pojedynczo (`kubectl delete pod <nazwa>`): czy aplikacja w przeglądarce choć na chwilę przestała działać? Dlaczego nie?
- Zepsuj selektor Service `api` (`kubectl edit svc api`). Co pokazuje przeglądarka, a co `endpointslices`? Przywróć.
- Nowa wersja: zmień coś w `app/todos/frontend/src`, zbuduj `todos-web:1.0.1`, wypchnij i zrób rollout. Sprawdź `kubectl rollout history deploy/web`.

## Gdy coś nie działa

| Objaw | Co zrobić |
|---|---|
| `ImagePullBackOff` w api lub web | literówka w `<REJESTR>` albo obraz nie istnieje; `kubectl describe pod` → Events. `no match for platform` → obraz z Maca M zbudowany bez `--platform linux/amd64` |
| `CreateContainerConfigError` | brak Secretu albo klucza: `kubectl get secret <nazwa> -o jsonpath='{.data}'` |
| `exceeded quota` | zostały obiekty z labów („Zanim zaczniesz”) albo za duże `resources`; jeśli dalej brakuje, napisz na czat |
| api `0/1`, w logach „Brak połączenia z MongoDB” | Mongo jeszcze startuje albo złe hasło w adresie bazy; hasło w adresie musi być takie samo jak dla Mongo |
| api `0/1` mimo działającej bazy, w logach `Authentication failed` | Secret zmieniony po pierwszym starcie Mongo: usuń pod mongo (baza bez dysku startuje od zera) |
| web `CrashLoopBackOff`, w logach `host not found in upstream "api"` | nie ma Service `api` (albo ma inną nazwę). Utwórz go, potem `kubectl rollout restart deploy/web` |
| strona działa, a dodanie zadania zwraca błąd | web nie widzi api: `kubectl get endpointslices -l kubernetes.io/service-name=api` |
| Ingress bez ADDRESS | zła `ingressClassName`: `kubectl get ingressclass`, `kubectl describe ingress` |
| 404 pod Twoim adresem | host w Ingressie inny niż w przeglądarce (literówka w loginie albo domenie) |
| ostrzeżenie o certyfikacie (`TRAEFIK DEFAULT CERT`) | brak sekcji `tls` albo certyfikat jeszcze się wystawia: `kubectl get certificate`, przy `False` dłużej niż 2 min `kubectl describe challenge` |
