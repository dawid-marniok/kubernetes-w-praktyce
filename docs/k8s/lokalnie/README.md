# Kubernetes na własnym laptopie: kind i alternatywy

Po szkoleniu wspólny klaster znika. Jeśli chcesz dalej ćwiczyć albo nie masz dostępu do klastra, postaw Kubernetesa u siebie. Ten plik pomaga wybrać narzędzie, postawić klaster i przenieść na niego laby.

Na szkoleniu używamy **kind** (lab12: tainty, drain). Instalację i nasz klaster z pliku `setup/kind/kind-szkolenie.yaml` opisuje [`setup/kind.md`](../../../setup/kind.md) — tu tego nie powtarzam, tylko uzupełniam.

| Sekcja | Co w niej jest |
|---|---|
| [Kiedy lokalny klaster wystarczy](#kiedy-lokalny-klaster-wystarczy) | czego się nauczysz lokalnie, a czego nie |
| [Porównanie narzędzi](#porównanie-narzędzi) | kind, minikube, k3d, Docker Desktop i inne w jednej tabeli |
| [kind](#kind), [minikube](#minikube), [k3d](#k3d) | instalacja, klaster wielowęzłowy, obrazy, Ingress, LoadBalancer, sprzątanie |
| [Laby szkolenia na lokalnym klastrze](#laby-szkolenia-na-lokalnym-klastrze) | namespace, Traefik, hosty, TLS, StorageClass, obrazy, ARM |
| [Typowe problemy](#typowe-problemy) | RAM, porty, pomylony kontekst, `.local` na macOS |

## Kiedy lokalny klaster wystarczy

Lokalny klaster to prawdziwy Kubernetes: ten sam API server, scheduler, kubelet i te same obiekty. Pody, Deploymenty, ConfigMapy, Secrety, Service, Ingress, Helm, RBAC, NetworkPolicy, CRD i operatory działają tak samo jak na EKS. Lokalnie masz też coś, czego na wspólnym klastrze nie było: **pełne uprawnienia administratora** (węzły, StorageClass, CRD, kontrolery).

Różnice zaczynają się tam, gdzie Kubernetes rozmawia z infrastrukturą:

| Temat | Na EKS (szkolenie) | Lokalnie |
|---|---|---|
| Service `LoadBalancer` | kontroler zamawia load balancer AWS z publicznym adresem | nikt nie zamawia; `EXTERNAL-IP` zostaje `<pending>`, dopóki nie dołożysz zastępstwa (cloud-provider-kind, `minikube tunnel`, ServiceLB w k3d) |
| DNS i TLS | rekord wildcard w publicznym DNS, certyfikaty z Let's Encrypt | brak publicznej nazwy; `localhost`, nagłówek `Host`, `nip.io`; certyfikaty self-signed |
| Wiele węzłów | osobne maszyny EC2 | kontenery na **jednym** laptopie. Scheduler widzi kilka węzłów, ale awaria laptopa to awaria wszystkich, a dysk i CPU są wspólne |
| StorageClass | `gp3` (dysk EBS, przypięty do strefy) | katalog na dysku węzła (`standard`, `local-path`); brak snapshotów, RWX i przenoszenia dysku między węzłami |
| IAM chmury | dostęp przez IAM, Pod Identity, ECR | brak; nie przećwiczysz uprawnień AWS ani pobierania z prywatnego ECR bez ręcznego Secreta |
| Zasoby | węzły po kilka GB RAM, autoskalowanie | tyle, ile dasz Dockerowi; HPA zadziała, autoskalowanie węzłów nie |

Wniosek: do nauki obiektów Kubernetesa, Helma, operatorów i diagnozy lokalny klaster wystarczy w większości przypadków. Do ćwiczeń z load balancerami chmury, prawdziwym DNS, certyfikatami publicznymi i IAM potrzebujesz konta w chmurze (EKS, AKS, GKE — wszystkie liczą za godziny działania).

## Porównanie narzędzi

| Narzędzie | Co to | Wymagania | Wiele węzłów | LoadBalancer | Ingress | Licencja / koszt | System | Kiedy wybrać |
|---|---|---|---|---|---|---|---|---|
| **kind** | węzły jako kontenery Dockera, czysty Kubernetes (kubeadm) | Docker albo Podman; ok. 3 GB RAM na nasz klaster | tak, w pliku konfiguracji | osobno: cloud-provider-kind | brak w zestawie; instalujesz sam (np. Traefik) | Apache 2.0, darmowy | macOS, Windows, Linux | testy, CI, laby z węzłami; to używamy na szkoleniu |
| **minikube** | klaster w kontenerze albo VM, dużo dodatków (`addons`) | 2 CPU, 2 GB RAM, 20 GB dysku; Docker, Podman albo hypervisor | tak, `--nodes` | `minikube tunnel` | addon `ingress` (ingress-nginx) | Apache 2.0, darmowy | macOS, Windows, Linux | nauka od zera, gotowe dodatki jednym poleceniem |
| **k3d** | k3s (lekka dystrybucja od Rancher/SUSE) w kontenerach Dockera | Docker; mało RAM | tak, `--agents` | wbudowany ServiceLB + mapowanie portów | Traefik w zestawie (klasa `traefik`) | MIT, darmowy | macOS, Windows, Linux | najszybszy start, Ingress i LB od razu, mało pamięci |
| **Docker Desktop** (wbudowany Kubernetes) | klaster w Docker Desktop; tryb `kubeadm` (1 węzeł) albo od 4.38 tryb `kind` (wiele węzłów, wybór wersji) | Docker Desktop; tryb kind wymaga magazynu obrazów containerd | tak, w trybie kind | Service `LoadBalancer` dostępny na `localhost` (sprawdź w swojej wersji) | brak w zestawie | darmowy dla osób prywatnych, edukacji i małych firm; w większych firmach płatna subskrypcja | macOS, Windows, Linux | masz już Docker Desktop i chcesz klaster jednym kliknięciem |
| **Rancher Desktop** | aplikacja z k3s w VM, do wyboru containerd albo dockerd | ok. 4 GB RAM dla VM | nie | ServiceLB z k3s | Traefik w zestawie | Apache 2.0, darmowy | macOS, Windows, Linux | darmowa alternatywa dla Docker Desktop z Kubernetesem |
| **OrbStack** | lekka alternatywa Docker Desktop z jednowęzłowym Kubernetesem | macOS | nie | tak, adresy dostępne z Maca | brak w zestawie | darmowy do użytku prywatnego, płatny komercyjnie | tylko macOS | szybki i oszczędny na Macu |
| **Podman Desktop** | GUI do Podmana; Kubernetes przez rozszerzenia kind albo minikube | Podman (na macOS/Windows maszyna Podmana) | tak (przez kind/minikube) | jak w kind/minikube | jak w kind/minikube | Apache 2.0, darmowy | macOS, Windows, Linux | firma nie pozwala na Docker Desktop |
| **MicroK8s** | Kubernetes od Canonical, pakiet snap | Linux (na macOS/Windows przez VM Multipass) | tak, `microk8s add-node` na kolejnych maszynach | addon `metallb` | addon `ingress` | Apache 2.0, darmowy | głównie Linux | Ubuntu, serwer domowy, klaster z kilku maszyn |
| **k3s na VM / Raspberry Pi** | ta sama dystrybucja co w k3d, ale na prawdziwych maszynach | VM albo Raspberry Pi 4/5, ok. 1–2 GB RAM na węzeł | tak, prawdziwe osobne maszyny | ServiceLB albo MetalLB | Traefik w zestawie | Apache 2.0, darmowy (sprzęt Twój) | Linux | prawdziwa sieć, prawdziwy drain i awaria węzła |
| **Talos / kubeadm** | klaster składany samodzielnie: Talos (system tylko pod Kubernetesa) albo kubeadm na zwykłym Linuksie | kilka VM | tak | MetalLB | instalujesz sam | darmowe (Talos: MPL 2.0, kubeadm: Apache 2.0) | Linux na VM (Talos ma też tryb w Dockerze) | chcesz zrozumieć instalację klastra, certyfikaty, etcd, aktualizacje; przygotowanie do CKA |

Jeśli nie wiesz, co wybrać: **kind**, bo znasz go ze szkolenia. Jeśli chcesz Ingress i LoadBalancer bez dokładania czegokolwiek: **k3d**.

## kind

Instalacja (macOS `brew`, Windows `winget`, Linux `curl`), nasz klaster 1 + 2, kontekst, metrics-server, `kind load` i sprzątanie: [`setup/kind.md`](../../../setup/kind.md). Wersja: v0.33.0 lub nowsza. Na Windowsie jest też `choco install kind`.

Skrót najważniejszych poleceń:

```bash
kind create cluster --config setup/kind/kind-szkolenie.yaml   # z katalogu głównego repo; kontekst kind-szkolenie
kubectl config current-context                                # kind-szkolenie
kind load docker-image todos-api:1.0.0 --name szkolenie       # obraz z laptopa do węzłów, bez rejestru
kubectl apply -k setup/kind/metrics-server                    # kubectl top, HPA
kind delete cluster --name szkolenie
```

Własny klaster wielowęzłowy bez naszego pliku:

```yaml
# moj-kind.yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: lokalny
nodes:
- role: control-plane
- role: worker
- role: worker
```

```bash
kind create cluster --config moj-kind.yaml     # kontekst kind-lokalny
```

Bez pola `image` kind bierze domyślną wersję Kubernetesa dla swojej wersji. Konkretną wersję wybierasz polem `image: kindest/node:v1.35.x` — listę obrazów do danej wersji kind znajdziesz w opisie wydania na GitHubie.

**Ingress.** kind nie ma kontrolera w zestawie. Nasz plik konfiguracji przekierowuje `localhost:8088` → port 80 i `localhost:8443` → 443 na węźle `control-plane` (z etykietą `ingress-ready=true`). Kontroler musi słuchać na tych portach węzła — przepis na Traefika jest niżej, w sekcji [Traefik zamiast klasy z klastra](#traefik-zamiast-klasy-z-klastra).

Starsze poradniki (także dokumentacja kind) pokazują **ingress-nginx**. Projekt społecznościowy ingress-nginx został wycofany w marcu 2026: manifesty nadal da się pobrać i do nauki działają, ale nie dostają już poprawek, także bezpieczeństwa. Na szkoleniu używaliśmy Traefika, więc lokalnie też go weź.

**LoadBalancer: cloud-provider-kind.** Osobny program z projektu Kubernetes. Działa w tle, patrzy na klastry kind i dla każdego Service `LoadBalancer` stawia kontener z Envoyem, który dostaje adres.

```bash
brew install cloud-provider-kind     # macOS; na Linuksie i Windowsie: go install albo plik z wydań na GitHubie
sudo cloud-provider-kind             # zostaw w osobnym terminalu; na macOS i WSL2 sudo jest wymagane
kubectl get svc                      # EXTERNAL-IP wypełnione po kilku sekundach
```

Na Linuksie łączysz się wprost z `EXTERNAL-IP`. Na macOS i Windowsie węzły są w VM Dockera i ten adres nie jest osiągalny z laptopa. cloud-provider-kind sam mapuje wtedy port na `localhost` — numer portu znajdziesz w `docker ps` przy kontenerze load balancera. cloud-provider-kind obsługuje też Gateway API (`Gateway`, `HTTPRoute`).

## minikube

Instalacja (strona projektu: minikube.sigs.k8s.io):

| System | Instalacja |
|---|---|
| macOS | `brew install minikube` |
| Windows | `winget install Kubernetes.minikube` albo `choco install minikube` |
| Linux (x86_64) | `curl -LO https://github.com/kubernetes/minikube/releases/latest/download/minikube-linux-amd64 && sudo install minikube-linux-amd64 /usr/local/bin/minikube && rm minikube-linux-amd64` |

Klaster z trzema węzłami w Dockerze:

```bash
minikube start --driver=docker --nodes 3 --cpus 2 --memory 3g   # pamięć i CPU na każdy węzeł
kubectl config current-context                                   # minikube
kubectl get nodes                                                # minikube, minikube-m02, minikube-m03
```

**Nie nazywaj profilu `szkolenie`** (`-p szkolenie`). minikube nazywa kontekst tak samo jak profil, więc nadpisałbyś kontekst klastra szkoleniowego. Zostań przy domyślnym `minikube` albo wybierz inną nazwę.

Obraz z laptopa, bez rejestru:

```bash
docker build -t todos-api:1.0.0 .
minikube image load todos-api:1.0.0
minikube image ls | grep todos-api
```

Dodatki:

```bash
minikube addons list
minikube addons enable metrics-server     # kubectl top, HPA
minikube addons enable ingress            # ingress-nginx, klasa nginx
```

Addon `ingress` to ingress-nginx — wycofany w marcu 2026, bez poprawek. Do nauki wystarczy, ale klasa nazywa się `nginx`, nie `traefik`. Żeby laby działały bez zmian, zainstaluj Traefika z Helma jako Service `LoadBalancer` (przepis niżej) i wystaw go przez `minikube tunnel`.

**LoadBalancer: `minikube tunnel`.**

```bash
minikube tunnel        # zostaw w osobnym terminalu; może poprosić o hasło (porty poniżej 1024)
kubectl get svc        # EXTERNAL-IP: 127.0.0.1 albo adres z sieci minikube
```

Z driverem `docker` na macOS i Windowsie bez tunelu nie dojdziesz z laptopa ani do LoadBalancera, ani do Ingressu. Pojedynczy Service otworzysz też przez `minikube service <nazwa> --url`.

**StorageClass.** Domyślna klasa to `standard` (provisioner hostpath). W klastrze z kilkoma węzłami bywa z nim kłopot, bo dane powstają na jednym węźle. Wtedy włącz addon `csi-hostpath-driver` i używaj jego klasy.

Sprzątanie:

```bash
minikube stop          # zatrzymuje, zostawia dane
minikube delete        # usuwa klaster i kontekst (--all: wszystkie profile)
```

## k3d

k3d uruchamia k3s w kontenerach Dockera. k3s ma w zestawie Traefika (klasa `traefik`, jak na szkoleniu), ServiceLB, metrics-server i klasę `local-path`.

Instalacja (strona projektu: k3d.io):

| System | Instalacja |
|---|---|
| macOS / Linux | `brew install k3d` |
| Windows | `choco install k3d` albo `scoop install k3d` |
| Linux / WSL | `curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh \| bash` |

Klaster: 1 serwer + 2 agenty, port 80 Traefika na `localhost:8088`:

```bash
k3d cluster create szkolenie --agents 2 -p "8088:80@loadbalancer" -p "8443:443@loadbalancer"
kubectl config current-context        # k3d-szkolenie
kubectl get nodes                     # k3d-szkolenie-server-0, k3d-szkolenie-agent-0, -agent-1
kubectl get ingressclass              # traefik
kubectl top nodes                     # metrics-server jest od razu
```

`-p "8088:80@loadbalancer"` mapuje port laptopa na kontener `k3d-szkolenie-serverlb`, który przekazuje ruch do węzłów, a tam do Traefika.

Obraz z laptopa, bez rejestru:

```bash
docker build -t todos-api:1.0.0 .
k3d image import todos-api:1.0.0 -c szkolenie
```

**LoadBalancer.** ServiceLB (dawniej klipper-lb) w k3s obsługuje Service `LoadBalancer` od razu: `EXTERNAL-IP` dostaje adresy węzłów. Z laptopa dojdziesz do niego tylko przez port zmapowany przy `k3d cluster create` (`-p "<port laptopa>:<port Service>@loadbalancer"`). Portów nie dodasz łatwo po utworzeniu klastra, więc zaplanuj je od razu. Traefik już zajmuje 80 i 443 — Twój Service `LoadBalancer` musi mieć inny port.

Sprzątanie:

```bash
k3d cluster list
k3d cluster delete szkolenie         # usuwa kontenery i kontekst k3d-szkolenie
```

## Laby szkolenia na lokalnym klastrze

Laby dni 2–5 pisaliśmy pod wspólny klaster. Lokalnie zadziałają prawie bez zmian, jeśli odtworzysz kilka rzeczy, które przygotował prowadzący.

### Namespace = login

Laby zakładają, że bieżący namespace to Twój login i że w plikach nie ma `namespace:`. Odtwórz to:

```bash
kubectl config current-context                          # najpierw upewnij się, gdzie jesteś
kubectl create namespace user07
kubectl config set-context --current --namespace=user07
kubectl config view --minify | grep namespace           # namespace: user07
```

### ResourceQuota (opcjonalnie)

Na wspólnym klastrze namespace miał limity. Lokalnie nie musisz ich mieć, ale z nimi szybciej zauważysz brak `resources` w manifeście (lab11):

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: limity
spec:
  hard:
    requests.cpu: "2"
    requests.memory: 2Gi
    limits.cpu: "4"
    limits.memory: 4Gi
    pods: "20"
```

### Traefik zamiast klasy z klastra

Ingressy z labów mają `ingressClassName: traefik`. Na k3d ta klasa jest od razu. Na kind i minikube zainstaluj Traefika z Helma — tego samego chartu co na klastrze szkoleniowym.

**kind** z naszym plikiem `kind-szkolenie.yaml`: Traefik na węźle `control-plane`, na portach 80/443 węzła, które kind wystawia jako `localhost:8088` i `localhost:8443`.

```yaml
# traefik-kind.yaml
service:
  type: ClusterIP
ports:
  web:
    hostPort: 80
  websecure:
    hostPort: 443
nodeSelector:
  ingress-ready: "true"
tolerations:
- key: node-role.kubernetes.io/control-plane
  operator: Exists
  effect: NoSchedule
ingressClass:
  enabled: true
  isDefaultClass: true
# hostPort na jednym węźle: stary pod musi zwolnić port, zanim wstanie nowy
updateStrategy:
  rollingUpdate:
    maxUnavailable: 1
    maxSurge: 0
```

```bash
helm repo add traefik https://traefik.github.io/charts
helm upgrade --install traefik traefik/traefik -n traefik --create-namespace -f traefik-kind.yaml --wait
kubectl get ingressclass                   # traefik (default)
curl -i http://localhost:8088/             # 404 page not found = Traefik odpowiada, tylko nie ma reguły
```

**minikube**: bez pliku wartości, z domyślnym Service `LoadBalancer`, plus `minikube tunnel` w osobnym terminalu:

```bash
helm upgrade --install traefik traefik/traefik -n traefik --create-namespace --set ingressClass.isDefaultClass=true --wait
kubectl -n traefik get svc traefik         # EXTERNAL-IP przy działającym tunelu
```

Kontroler ma namespace `traefik`, tak jak na szkoleniu, więc NetworkPolicy z labów (wpuszczanie ruchu z namespace'u kontrolera) też zadziała.

### Host w Ingressie

Na szkoleniu host to `<login>.<DOMENA>` z rekordem wildcard w publicznym DNS. Lokalnie masz trzy możliwości:

| Sposób | Host w Ingressie | Jak wywołać | Uwagi |
|---|---|---|---|
| nagłówek `Host` | `user07.local` | `curl -H "Host: user07.local" http://localhost:8088/` | bez DNS; w przeglądarce nie zadziała bez wpisu w `/etc/hosts` |
| nip.io | `user07.127.0.0.1.nip.io` | `curl http://user07.127.0.0.1.nip.io:8088/` | publiczny DNS zwraca adres zapisany w nazwie; działa też w przeglądarce. Wymaga internetu |
| localtest.me | `user07.localtest.me` | `curl http://user07.localtest.me:8088/` | każda nazwa `*.localtest.me` wskazuje na 127.0.0.1 |

Port (`:8088`) zależy od klastra: nasz kind i k3d z poleceniem wyżej → 8088, minikube z tunelem → 80. Część domowych routerów blokuje odpowiedzi DNS z adresem 127.0.0.1 (ochrona przed DNS rebinding). Jeśli `nip.io` nie odpowiada, sprawdź `nslookup user07.127.0.0.1.nip.io 1.1.1.1` — wtedy winny jest router.

### TLS bez Let's Encrypt

Let's Encrypt lokalnie nie zadziała: musi połączyć się z Twoim hostem z internetu (HTTP-01) albo zobaczyć rekord w Twojej domenie (DNS-01). Masz dwie drogi.

**Self-signed ręcznie**, gdy wystarczy jeden certyfikat:

```bash
openssl req -x509 -newkey rsa:2048 -nodes -days 30 -keyout tls.key -out tls.crt \
  -subj "/CN=user07.127.0.0.1.nip.io" -addext "subjectAltName=DNS:user07.127.0.0.1.nip.io"
kubectl create secret tls todos-tls --cert=tls.crt --key=tls.key
```

W Ingressie `tls.secretName: todos-tls`, bez adnotacji cert-managera. Wywołanie: `curl -k https://user07.127.0.0.1.nip.io:8443/` (`-k`, bo certyfikatu nikt nie podpisał).

**cert-manager z własnym CA**, gdy chcesz ćwiczyć tak jak na szkoleniu (adnotacja na Ingressie, cert-manager sam wystawia i odnawia certyfikaty). Instalacja:

```bash
helm repo add jetstack https://charts.jetstack.io
helm upgrade --install cert-manager jetstack/cert-manager -n cert-manager --create-namespace --set crds.enabled=true --wait
```

Issuer `selfSigned` podpisuje certyfikat CA, a ClusterIssuer `ca` podpisuje nim certyfikaty aplikacji:

```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: selfsigned
spec:
  selfSigned: {}
---
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: lokalne-ca
  namespace: cert-manager
spec:
  isCA: true
  commonName: lokalne-ca
  secretName: lokalne-ca
  privateKey:
    algorithm: ECDSA
    size: 256
  issuerRef:
    name: selfsigned
    kind: ClusterIssuer
---
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: lokalne-ca
spec:
  ca:
    secretName: lokalne-ca     # ClusterIssuer szuka tego Secreta w namespace cert-manager
```

W Ingressie zamiast ClusterIssuera z Let's Encrypt wpisz `cert-manager.io/cluster-issuer: lokalne-ca`. Przeglądarka nadal ostrzeże, bo nie zna Twojego CA. W curl zamiast `-k`:

```bash
kubectl -n cert-manager get secret lokalne-ca -o jsonpath='{.data.ca\.crt}' | base64 -d > lokalne-ca.crt
curl --cacert lokalne-ca.crt https://user07.127.0.0.1.nip.io:8443/
```

Ten sam układ (własne CA zamiast Let's Encrypt) opisuje [`on-prem.md`](../ingress-gateway/on-prem.md), a działanie cert-managera [`cert-manager.md`](../ingress-gateway/cert-manager.md).

### StorageClass

Laby nie wpisują `storageClassName`, więc PVC dostaje domyślną klasę klastra. Lokalnie to:

| Klaster | Domyślna klasa | Gdzie są dane |
|---|---|---|
| kind | `standard` (local-path-provisioner) | katalog w kontenerze węzła |
| minikube | `standard` (hostpath) | katalog w węźle minikube |
| k3d | `local-path` | katalog w kontenerze węzła |

PV jest przypięty do węzła, na którym powstał. Po `kubectl drain` tego węzła pod z PVC zostanie `Pending`, dopóki węzeł nie wróci — trochę jak dysk EBS przypięty do strefy. RWX (`ReadWriteMany`) lokalnie nie ma. Wszystkie dane giną razem z `delete cluster`.

### Obrazy: zamiast ECR

Na szkoleniu obrazy szły do Twojego repozytorium w ECR. Lokalnie ECR nie jest potrzebny:

- budujesz lokalnie i ładujesz do klastra: `kind load docker-image`, `minikube image load`, `k3d image import`. W manifeście tag z wersją (np. `todos-api:1.0.0`) i `imagePullPolicy: IfNotPresent`;
- albo wypychasz na Docker Hub (darmowe konto, repozytoria publiczne) i w manifeście piszesz `<twój-login>/todos-api:1.0.0`;
- obrazy z ECR szkolenia przestaną działać po zamknięciu konta szkoleniowego. Zmień `image:` w manifestach i wartościach Helma.

Po załadowaniu sprawdź, że obraz jest na węźle: `docker exec szkolenie-worker crictl images | grep todos` (kind) albo `minikube image ls`.

### ARM na Macach z procesorem M

Węzły lokalnego klastra mają architekturę laptopa: na Macu M to `arm64`, a węzły EKS na szkoleniu były `amd64`. Dlatego do ECR budowałeś z `--platform linux/amd64`, a lokalnie tej flagi **nie** dajesz.

- Oficjalne obrazy z Docker Hub (nginx, postgres, mongo, node) są multi-arch i działają od razu.
- Obraz tylko dla `amd64` na węźle `arm64` kończy się `exec format error` w logach albo `no match for platform` przy pobieraniu. Sprawdzisz to tak: `docker buildx imagetools inspect <obraz>` — lista platform w sekcji `Manifests`.
- Jeden obraz na obie architektury: `docker buildx build --platform linux/amd64,linux/arm64 -t <login>/todos-api:1.0.0 --push .` (wymaga rejestru, bo lokalny magazyn obrazów nie zawsze trzyma kilka architektur naraz).

## Typowe problemy

| Objaw | Przyczyna i co zrobić |
|---|---|
| węzły `NotReady`, pody `Pending` z `Insufficient memory`, Docker Desktop zamarza | za mało RAM-u dla VM Dockera. Settings → Resources: 6–8 GB dla klastra z trzema węzłami. W minikube zmniejsz `--memory` albo liczbę węzłów |
| `address already in use` / `port is already allocated` przy tworzeniu klastra | port 8088, 8443, 80 albo 30000–30002 zajęty przez kontener z dnia 1 albo inny klaster. `docker ps`, `lsof -i :8088`; zatrzymaj go albo wybierz inny port. Dwa klastry kind z tym samym plikiem nie wstaną naraz |
| `kubectl apply` poszło nie tam, gdzie chciałeś | pomylony kontekst: lokalny klaster i klaster szkoleniowy (albo firmowy) są w tym samym `~/.kube/config`. **Przed każdym `apply` i `delete`: `kubectl config current-context`.** Bezpieczniej: `kubectl --context kind-szkolenie apply -f …` |
| po `minikube start -p szkolenie` zniknął dostęp do klastra szkoleniowego | profil nadpisał kontekst `szkolenie`. `minikube delete -p szkolenie`, potem odtwórz kontekst (`aws eks update-kubeconfig … --alias szkolenie`, jeśli klaster jeszcze istnieje) |
| `EXTERNAL-IP` ciągle `<pending>` | nikt nie obsługuje Service `LoadBalancer`: uruchom `cloud-provider-kind` (kind) albo `minikube tunnel` (minikube); w k3d sprawdź pody `svclb-*` w `kube-system` |
| Ingress utworzony, `curl` wisi albo `connection refused` | brak kontrolera (`kubectl get ingressclass`, `kubectl get pods -n traefik`), inna klasa niż `traefik` albo zły port (`localhost:8088`, nie 80) |
| `curl http://user07.local` czeka kilka sekund albo nie znajduje hosta na macOS | macOS rozwiązuje `.local` przez mDNS (Bonjour), nie przez zwykły DNS, i wpis w `/etc/hosts` bywa ignorowany albo powolny. Używaj nagłówka `Host` albo `nip.io` / `localtest.me` |
| `ErrImagePull` dla obrazu załadowanego do klastra | inna nazwa lub tag niż przy `docker build`, brak `imagePullPolicy: IfNotPresent` albo obraz załadowany do innego klastra (`--name` / `-c`) |
| `exec format error` w logach poda | obraz zbudowany dla innej architektury (patrz [ARM na Macach z procesorem M](#arm-na-macach-z-procesorem-m)) |
| po restarcie laptopa klaster nie odpowiada | uruchom Docker Desktop i poczekaj; kind i k3d startują razem z kontenerami. minikube: `minikube start` |

## Zobacz też

- [`setup/kind.md`](../../../setup/kind.md) — instalacja kind i klaster do labów ze szkolenia
- [`podstawy/README.md`](../podstawy/README.md) — podstawy Kubernetesa i kubectl, konteksty
- [`ingress-gateway/on-prem.md`](../ingress-gateway/on-prem.md) — Ingress, LoadBalancer i certyfikaty poza chmurą (MetalLB, własne CA)
- [lab12](../../../labs/d3-lab12-affinity-taints/README.md) — affinity, tainty i drain na kind
