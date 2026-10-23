# Dzień 2 — ściąga: Service, Ingress i Gateway API

Jak ruch z internetu dochodzi do Twojego poda. Ten katalog:

| Plik | Co w nim jest |
|---|---|
| `README.md` (ten plik) | typy Service i co tworzą w AWS, Ingress, Gateway API, [kiedy Ingress, kiedy Gateway API](#kiedy-ingress-kiedy-gateway-api), diagnoza |
| [`cert-manager.md`](cert-manager.md) | jak powstaje certyfikat HTTPS: cert-manager, Let's Encrypt, HTTP-01 i DNS-01, alternatywy |
| [`on-prem.md`](on-prem.md) | to samo na własnych serwerach: MetalLB, zewnętrzny load balancer, DNS, wewnętrzne CA |
| [`diagram.html`](diagram.html) | interaktywny diagram drogi żądania i wystawiania certyfikatu — **otwórz w przeglądarce** (`open diagram.html`) |

Gotowe manifesty: `przyklady/k8s/05-service/` (typy Service), `przyklady/k8s/06-ingress/` (host, ścieżki, TLS), `przyklady/k8s/07-gateway-api/` (HTTPRoute, canary, rewrite). Ingress ćwiczysz w [lab08](../../../labs/lab08-service-ingress/) (kroki 3–5); Gateway API pokazuje prowadzący w demie.

**Od trenera na czacie:** domena szkolenia `<DOMENA>` (np. `k8s.marniok.dev`) i nazwa ClusterIssuera. Klasa Ingress na naszym klastrze: `traefik`.

## Po co Ingress

| Sposób | Skąd dostępny | Ile adresów | Warstwa |
|---|---|---|---|
| Service **ClusterIP** | tylko z wnętrza klastra | — | L4 (TCP/UDP) |
| Service **LoadBalancer** | z zewnątrz | **osobny load balancer AWS na każdy Service** — osobny adres i osobny rachunek | L4 |
| **Ingress** | z zewnątrz | **jeden adres dla wielu usług**, routing po hoście i ścieżce | L7 (HTTP/HTTPS) |

Na naszym klastrze jest jeden NLB przed Traefikiem i wszyscy z niego korzystają. W DNS jest rekord wildcard `*.<DOMENA>` → ten NLB, więc każda nazwa pod domeną trafia do Traefika, a on wybiera Service po hoście. Każdy ma swój namespace (= login), więc host zawiera login: `<login>.<DOMENA>`.

## Typy Service i co naprawdę robią na EKS

Każdy Service dostaje nazwę DNS (`<svc>.<namespace>.svc.cluster.local`) i — poza headless i ExternalName — wirtualny adres ClusterIP. Typy różnią się tym, **skąd** da się do niego dojść. Kolejne typy są nadbudową poprzednich: NodePort to ClusterIP plus port na węzłach, LoadBalancer to NodePort plus load balancer przed węzłami.

| Typ | Skąd dostępny | Co powstaje | Na naszym klastrze |
|---|---|---|---|
| `ClusterIP` (domyślny) | z podów w klastrze | wirtualny IP + reguły kube-proxy na węzłach | podstawa wszystkiego, w tym Ingressu |
| `NodePort` | z sieci, w której są węzły | port 30000–32767 otwarty na **każdym** węźle | tylko z wnętrza VPC — węzły nie mają publicznych IP |
| `LoadBalancer` | z internetu (albo z VPC przy `internal`) | NodePort + load balancer AWS | działa, ale każdy to osobny LB i koszt; nie tworzymy |
| headless (`clusterIP: None`) | z podów w klastrze | brak ClusterIP; DNS zwraca adresy podów | StatefulSet (dzień 3) |
| `ExternalName` | z podów w klastrze | tylko rekord CNAME do nazwy spoza klastra | bez proxy, portów i selektora |

Poniższe wyniki pochodzą z naszego klastra (EKS 1.35, `k8s-sages`, test 20.10.2026).

### NodePort

```bash
kubectl get svc lab08-web-np
# NAME           TYPE       CLUSTER-IP      EXTERNAL-IP   PORT(S)        AGE
# lab08-web-np   NodePort   172.20.3.12     <none>        80:30281/TCP   5s
kubectl get nodes -o wide                        # kolumna INTERNAL-IP, EXTERNAL-IP pusta
kubectl exec deploy/lab08-web -- curl -s -o /dev/null -w '%{http_code}\n' http://<INTERNAL-IP węzła>:30281
# 200
```

- Port wybiera klaster z zakresu 30000–32767 (tu 30281). Działa na każdym węźle, także tam, gdzie nie ma Twojego poda: kube-proxy przekazuje ruch dalej.
- Z poda albo z maszyny w tym samym VPC: `200`. **Z laptopa nie zadziała**, bo węzły stoją w prywatnych podsieciach i nie mają publicznych adresów.
- Sztywny `nodePort` w YAML-u to proszenie się o konflikt: drugi uczestnik dostanie `provided port is already allocated`.

### LoadBalancer bez adnotacji → Classic Load Balancer

Manifest `przyklady/k8s/05-service/loadbalancer.yaml` (Service `przyklad-deploy-lb`, testowany w namespace `demo`):

```bash
kubectl apply -f przyklady/k8s/05-service/loadbalancer.yaml
kubectl get svc przyklad-deploy-lb
# NAME                 TYPE           EXTERNAL-IP                                                                PORT(S)
# przyklad-deploy-lb   LoadBalancer   a3b8b4eabf83c46d2995a5892d6f909c-1968439010.eu-central-1.elb.amazonaws.com   80:30586/TCP
kubectl describe svc przyklad-deploy-lb | tail -4
#   Normal  EnsuringLoadBalancer  6s  service-controller  Ensuring load balancer
#   Normal  EnsuredLoadBalancer   1s  service-controller  Ensured load balancer
```

Co się stało po drodze:

1. Kubernetes przydzielił Service **NodePort** (30586) — LoadBalancer zawsze ma NodePort pod spodem.
2. Kontroler `service-controller` (cloud provider AWS, działa w control plane EKS) zawołał API AWS. Na tym klastrze **nie ma** AWS Load Balancer Controllera, więc bez adnotacji powstaje **Classic Load Balancer** (starszy typ LB w AWS). Po ok. 5 s zdarzenie `EnsuredLoadBalancer`, a w `EXTERNAL-IP` nazwa DNS load balancera.
3. LB ma listener `TCP:80` → port `30586` na węzłach. Zarejestrowane są **wszystkie 3 instancje** EC2, health check to `TCP:30586`. Na początku instancje są `OutOfService`, dopóki nie przejdą sprawdzenia.
4. Powstał nowy security group `k8s-elb-<id>` (wejście `0.0.0.0/0` na port 80 i ICMP typ 3), a security group węzłów `k8s-sages-node-…` dostał regułę, która wpuszcza ruch z tego SG.
5. LB ma tagi `kubernetes.io/service-name=demo/przyklad-deploy-lb` i `kubernetes.io/cluster/k8s-sages=owned` — po nich kontroler wie, że to jego zasób.
6. Strona odpowiedziała z internetu po ok. **1 min 40 s**: tyle trwało rozejście się nazwy DNS i przejście health checków.
7. `kubectl delete svc przyklad-deploy-lb` → LB i security group zniknęły po ok. 12 s.

### LoadBalancer z adnotacjami → NLB

| Adnotacja na Service | Efekt |
|---|---|
| `service.beta.kubernetes.io/aws-load-balancer-type: nlb` | **Network Load Balancer** zamiast Classic. Tak jest wystawiony nasz Traefik: `afe21dba47a48490992de4b3793117eb-88ecc87c381c9d83.elb.eu-central-1.amazonaws.com` |
| `service.beta.kubernetes.io/aws-load-balancer-scheme: internal` | LB z adresem prywatnym, dostępny tylko z VPC (i sieci do niego podłączonych) |

Rozpoznasz typ po nazwie: Classic ma `…-<liczba>.<region>.elb.amazonaws.com`, NLB ma `…-<hex>.elb.<region>.amazonaws.com`.

Z doinstalowanym **AWS Load Balancer Controllerem** (u nas go nie ma) dochodzą dwie rzeczy: NLB, który kieruje ruch prosto na IP podów (z pominięciem NodePort), i **ALB** jako kontroler Ingress (IngressClass `alb`, TLS z certyfikatem z AWS ACM).

### Dlaczego jeden Traefik dla wszystkich

Każdy Service typu LoadBalancer to osobny load balancer AWS, płatny za każdą godzinę działania (plus ruch), z osobnym adresem i osobnym security group. Przy 15 uczestnikach i kilku aplikacjach na głowę to dziesiątki LB. Dlatego jeden Service LoadBalancer (Traefik za NLB), a aplikacje wystawiamy przez Ingress.

```
LoadBalancer na każdą aplikację:        Ingress:
  LB-1 → app1                             NLB → Traefik ─┬─ host a → app1
  LB-2 → app2                                            ├─ host b → app2
  LB-3 → app3                                            └─ host c → app3
```

## Dwa elementy: obiekt i kontroler

| Element | Co to jest | Kto tworzy |
|---|---|---|
| **Ingress** (obiekt) | reguły: host + ścieżka → Service. Sam w sobie to **tylko wpis w API**, nic nie przekierowuje | Ty, w swoim namespace |
| **Kontroler Ingress** | reverse proxy działające w klastrze; czyta obiekty Ingress i konfiguruje się według nich. U nas **Traefik** | administrator klastra |

Kontroler to odpowiednik nginx albo Traefika, którego w dniu 1 stawiałeś w compose przed aplikacjami — tylko konfiguracji nie piszesz w pliku proxy, a w obiektach Ingress.

- Bez kontrolera Ingress da się utworzyć, ale nic się nie dzieje.
- `spec.ingressClassName` wybiera kontroler. Lista klas: `kubectl get ingressclass`. `traefik` jest u nas klasą domyślną, ale i tak wpisuj ją jawnie.
- Kolumna `ADDRESS` w `kubectl get ingress` pokazuje adres NLB, gdy Traefik przyjął Ingress.

## Droga żądania

```
klient (curl, przeglądarka)
   │  DNS: <login>.<DOMENA> → *.<DOMENA> (CNAME) → IP load balancera
   ▼
AWS NLB  (Service traefik typu LoadBalancer, ns traefik)
   ▼
Traefik  ── HTTPS: certyfikat z Secretu wybrany po nazwie (SNI)
   │        reguły z obiektów Ingress: Host + ścieżka
   │        brak pasującej reguły → 404
   ▼
Service <nazwa>  ── selektor wybiera pody
   ▼
EndpointSlice  ── lista IP:port GOTOWYCH podów (readiness)
   ▼
pod  (Traefik łączy się bezpośrednio z IP poda, z pominięciem ClusterIP)
```

Service jest tu „książką adresową”: Traefik bierze z jego EndpointSlice adresy podów i sam rozkłada ruch. Pod bez readiness wypada z EndpointSlice, więc nie dostaje ruchu także z Ingressu ([sondy](../deployment/sondy.md)). Każde ogniwo z komendą do sprawdzenia: [`diagram.html`](diagram.html).

## Manifest

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: web
spec:
  ingressClassName: traefik      # który kontroler
  rules:
  - host: <login>.<DOMENA>       # nagłówek Host żądania; unikalny na wspólnym kontrolerze
    http:
      paths:
      - path: /
        pathType: Prefix         # / pasuje do wszystkiego
        backend:
          service:
            name: web            # Service w TWOIM namespace
            port:
              number: 80         # port Service (nie containerPort); można też name: http
```

Dwie ścieżki, dwa Service (jeden host):

```yaml
  rules:
  - host: apps-<login>.<DOMENA>   # jeden poziom pod domeną: apps-<login>, nie apps.<login>
    http:
      paths:
      - path: /app1
        pathType: Prefix
        backend: {service: {name: app1, port: {number: 80}}}
      - path: /app2
        pathType: Prefix
        backend: {service: {name: app2, port: {number: 80}}}
```

Kontroler przekazuje ścieżkę **bez zmian**: pod `app1` dostaje `/app1/...`, więc aplikacja musi ją obsługiwać (albo potrzebny rewrite, patrz niżej).

## TLS z cert-managerem — w skrócie

Certyfikat leży w Secrecie typu `kubernetes.io/tls` w tym samym namespace. Nie robisz go sam: w klastrze działa **cert-manager**, a administrator utworzył `ClusterIssuer` (konto w Let's Encrypt). Dopisujesz do Ingressu adnotację i sekcję `tls`:

```yaml
metadata:
  name: web
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod   # nazwa od trenera: kubectl get clusterissuer
spec:
  ingressClassName: traefik
  tls:
  - hosts: [<login>.<DOMENA>]    # musi zgadzać się z host w rules
    secretName: web-tls          # tu cert-manager zapisze certyfikat
  rules: ...                     # bez zmian
```

cert-manager tworzy z tego `Certificate`, zamawia certyfikat w Let's Encrypt, a Let's Encrypt sprawdza przez HTTP (wyzwanie HTTP-01), czy Twój host naprawdę prowadzi do naszego klastra. Na klastrze trwa to ok. 30 s. Potem:

```bash
kubectl get certificate                      # READY True
curl -sI https://<login>.<DOMENA> | head -1  # 200, bez -k
```

Najważniejsze pułapki:
- **Domena `.dev` działa w przeglądarce tylko po HTTPS** (lista HSTS preload). Ingress bez `tls` → przeglądarka dostaje certyfikat `TRAEFIK DEFAULT CERT` i ostrzega. `curl http://` działa.
- **Limit Let's Encrypt** jest wspólny dla całej domeny (50 nowych certyfikatów tygodniowo). Nie kasuj i nie twórz Ingressu z Secretem w pętli.
- **Wildcard to jeden poziom:** `apps-<login>.<DOMENA>` działa, `apps.<login>.<DOMENA>` nie (ani w DNS, ani w certyfikacie).

Krok po kroku (Certificate → Order → Challenge → Secret), DNS-01, odnawianie, NetworkPolicy, Gateway API, diagnoza i alternatywy dla Let's Encrypt: [`cert-manager.md`](cert-manager.md).

Bez cert-managera (np. na kind): self-signed `openssl req -x509 -nodes -days 7 -newkey rsa:2048 -keyout tls.key -out tls.crt -subj "/CN=<login>.local"` i `kubectl create secret tls web-tls --cert=tls.crt --key=tls.key`; przeglądarka ostrzeże, `curl` potrzebuje `-k`. `tls.key` nie trafia do repo.

## Testowanie

Na klastrze szkoleniowym DNS jest gotowy, więc po prostu:

```bash
curl -s http://<login>.<DOMENA> | grep title
curl -s -o /dev/null -w '%{http_code}\n' http://apps-<login>.<DOMENA>/app1/
curl -sI https://<login>.<DOMENA>                # po dodaniu tls
dig +short <login>.<DOMENA>                      # → nazwa NLB i jego adresy IP
```

Na kind nie ma DNS ani publicznego adresu. Kontrolerowi wystarczy nagłówek `Host`: port-forward do Traefika i host podany ręcznie (`.local` nie wpisuj w przeglądarce: na macOS idzie przez mDNS):

```bash
kubectl port-forward -n traefik svc/traefik 8080:80     # osobny terminal
curl -s -H "Host: <login>.local" http://localhost:8080 | grep title
```

| Odpowiedź | Kto odpowiada | Znaczy |
|---|---|---|
| `200` / treść strony | aplikacja | wszystko działa |
| `404 page not found` | Traefik | host albo ścieżka nie pasuje do żadnej reguły; także Ingress z nieistniejącym Service albo złą klasą |
| `503` / `no available server` | Traefik | reguła pasuje, ale Service nie ma gotowych podów (pusty EndpointSlice) |
| `502 Bad Gateway` | Traefik | pod jest na liście, ale nie przyjmuje połączenia (zły `targetPort`, aplikacja nie słucha) |
| `504 Gateway Timeout` | Traefik | pod nie odpowiada w czasie (zawieszona aplikacja, blokada sieci) |
| brak odpowiedzi / `Could not resolve host` | — | literówka w domenie, dwa poziomy pod domeną (`a.<login>.<DOMENA>`), świeży rekord DNS (odczekaj kilka minut) |
| `301` na `.../app1/` | aplikacja (nginx) | dopisuje `/` do katalogu — wołaj `/app1/` |

## pathType

| pathType | Dopasowanie | `/app1` pasuje do |
|---|---|---|
| `Prefix` | po segmentach ścieżki (rozdzielonych `/`) | `/app1`, `/app1/`, `/app1/x` — **nie** `/app10` |
| `Exact` | dokładnie ta ścieżka | tylko `/app1` (nie `/app1/`) |
| `ImplementationSpecific` | zależy od kontrolera | **unikaj** — przy zmianie kontrolera zachowa się inaczej |

Gdy pasuje kilka reguł: wygrywa **najdłuższy pasujący prefiks**, a przy równej długości `Exact` przed `Prefix`. Kolejność w YAML-u nie ma znaczenia. Ścieżka `/` łapie wszystko, czego nie złapały dłuższe.

## Adnotacje i Middleware

Ingress standardowo zna tylko host, ścieżkę, TLS i backend. Wszystko inne (rewrite, przekierowanie HTTP→HTTPS, limity, uwierzytelnianie) to **adnotacje konkretnego kontrolera**. Adnotacje nginx nic nie znaczą dla Traefika i odwrotnie — przy zmianie kontrolera trzeba je przepisać.

W Traefiku dodatki to osobne obiekty **Middleware** (CRD `traefik.io/v1alpha1`), podpinane adnotacją w formacie `<namespace>-<nazwa>@kubernetescrd`:

```yaml
apiVersion: traefik.io/v1alpha1
kind: Middleware
metadata:
  name: strip-app1
spec:
  stripPrefix:
    prefixes: [/app1]            # /app1/x → /x w podzie
---
# w Ingressie:
metadata:
  annotations:
    traefik.ingress.kubernetes.io/router.middlewares: <login>-strip-app1@kubernetescrd
```

Community **ingress-nginx** jest wycofany (koniec utrzymania 03.2026, bez poprawek bezpieczeństwa) — w nowych projektach go nie wybieraj.

## Ingress a Gateway API

Gateway API (`gateway.networking.k8s.io/v1`) to następca Ingressu. W labie ćwiczysz Ingress, a Gateway API pokazuje prowadzący w demie. Jego CRD nie są wbudowane w Kubernetesa: administrator klastra je doinstalowuje i włącza obsługę w kontrolerze (oraz w cert-managerze, jeśli certyfikat ma zamawiać Gateway). Na k8s-sages są: CRD v1.6.1 z kanału standard i GatewayClass `traefik` (`kubectl get crd | grep gateway.networking.k8s.io`, `kubectl get gatewayclass`). Rola kursanta nie obejmuje tworzenia `HTTPRoute`, więc ćwiczysz je lokalnie albo na własnym klastrze.

Podział ról: zespół platformy tworzy **Gateway** (porty, hosty, TLS, kto może się podpiąć), zespół aplikacji tylko **HTTPRoute** z `parentRefs` wskazującym ten Gateway. Gotowa para do przećwiczenia na kind albo własnym klastrze: `przyklady/k8s/07-gateway-api/gateway.yaml` (Gateway `przyklad-gw`, listenery na portach entrypointów Traefika 8000/8443, certyfikat z cert-managera) i `httproute.yaml` (host `gw-<login>.<DOMENA>`).

| | Ingress | Gateway API |
|---|---|---|
| Obiekty i role | jeden obiekt, wszystko w nim | GatewayClass (kontroler), Gateway (platforma: porty, TLS, kto może się podpiąć), **HTTPRoute** (zespół aplikacji) |
| Wybór kontrolera | `ingressClassName` | `parentRefs` → konkretny Gateway |
| Host, ścieżka | `rules[].host`, `paths[]` | `hostnames[]`, `matches[].path` |
| Nagłówki, metoda, query | adnotacje kontrolera | natywnie w `matches` |
| Wagi / canary | adnotacje kontrolera | `backendRefs[].weight` |
| Rewrite, redirect, nagłówki | adnotacje / Middleware | natywnie w `filters` (`URLRewrite`, `RequestRedirect`…) |
| TLS | `spec.tls` w Ingressie | listener w Gateway (`certificateRefs`) |
| Status | `ADDRESS` | warunki `Accepted`, `ResolvedRefs` (`kubectl describe httproute`) |
| CRD | wbudowany w Kubernetesa | doinstalowane CRD |

Ten sam routing (host + `/` → Service `web`):

```yaml
# Ingress                               # HTTPRoute
apiVersion: networking.k8s.io/v1        apiVersion: gateway.networking.k8s.io/v1
kind: Ingress                           kind: HTTPRoute
metadata:                               metadata:
  name: web                               name: web
spec:                                   spec:
  ingressClassName: traefik               parentRefs:
  rules:                                  - name: przyklad-gw   # Gateway w innym ns: + namespace
  - host: <login>.<DOMENA>                hostnames: [gw-<login>.<DOMENA>]
    http:
      paths:                              rules:
      - path: /                           - matches:
        pathType: Prefix                    - path: {type: PathPrefix, value: /}
        backend:                            backendRefs:
          service:                          - name: web
            name: web                         port: 80
            port: {number: 80}                weight: 100     # canary: drugi backend z weight: 10
```

### Kiedy Ingress, kiedy Gateway API

**Dojrzałość.** Gateway API jest GA od wersji 1.0 (październik 2023): `GatewayClass`, `Gateway`, `HTTPRoute` i `GRPCRoute` są w `v1`, kanał **standard**. Obok jest kanał **experimental** z funkcjami w trakcie projektowania. Kanał jest ważniejszy niż numer wersji: na produkcji instaluj CRD z kanału standard, a z experimental bierz tylko to, czego świadomie potrzebujesz. Ingress jest stabilny od 1.19 (`networking.k8s.io/v1`), ale **zamrożony**: nie dostaje nowych funkcji i nie zniknie z Kubernetesa.

**Dlaczego w ogóle Gateway.** Ingress opisuje tylko host, ścieżkę, TLS i backend. Wszystko inne to adnotacje jednego kontrolera, więc YAML przestaje być przenośny, a zespół aplikacji musi znać szczegóły kontrolera. Gateway API ma te funkcje w specyfikacji i dzieli odpowiedzialność: platforma trzyma `Gateway` (porty, certyfikaty, kto może się podpiąć), zespół aplikacji tylko `HTTPRoute`.

| Sytuacja | Wybierz | Dlaczego |
|---|---|---|
| Prosta aplikacja: host + ścieżka + TLS, jeden zespół | **Ingress** | mniej obiektów, każdy kontroler i każdy poradnik to zna, cert-manager działa od lat |
| Istniejący projekt na Ingressie, który działa | **Ingress**, migracja przy okazji | Ingress nie zniknie; migruj, gdy potrzebujesz czegoś z wierszy niżej albo zmieniasz kontroler |
| Kontroler ingress-nginx (wycofany 03.2026) | **migracja**: Gateway API albo Ingress na innym kontrolerze | bez poprawek bezpieczeństwa; adnotacje nginx i tak trzeba przepisać, więc to dobry moment na Gateway |
| Kilka zespołów na jednym klastrze, platforma zarządza certyfikatami i portami | **Gateway API** | `Gateway` w namespace platformy, `HTTPRoute` w namespace'ach zespołów, `allowedRoutes` i `ReferenceGrant` pilnują, kto może się podpiąć |
| Canary, podział ruchu wagami, blue-green | **Gateway API** | `backendRefs[].weight` w standardzie zamiast adnotacji kontrolera |
| Routing po nagłówku, metodzie, query string | **Gateway API** | natywnie w `matches` |
| gRPC, TCP, TLS passthrough | **Gateway API** | `GRPCRoute` (GA), `TLSRoute`/`TCPRoute` (sprawdź kanał w swojej wersji); Ingress obsługuje tylko HTTP(S) |
| Możliwa zmiana kontrolera (Traefik ↔ Envoy Gateway ↔ Istio ↔ kontroler chmury) | **Gateway API** | ten sam YAML działa z każdą implementacją zgodną ze specyfikacją |
| Funkcja tylko w jednym kontrolerze (np. Middleware Traefika) | oba | w Ingressie adnotacja, w `HTTPRoute` filtr `ExtensionRef` wskazujący `Middleware`; tak czy inaczej to kawałek niezależny od standardu |

**Na co uważać przy Gateway API.**
- CRD instaluje administrator i to on wybiera wersję. Kontroler musi wspierać tę wersję (Traefik, Envoy Gateway i inne publikują tabelę zgodności).
- Status czytasz z warunków: `kubectl describe httproute` → `Accepted`, `ResolvedRefs`. Trasa, której Gateway nie przyjął (zły `parentRefs`, namespace niedozwolony w `allowedRoutes`), nie daje błędu przy `apply`, tylko nie działa.
- cert-manager zamawia certyfikat z adnotacji na `Gateway`, nie na trasie (obsługę Gateway API włącza się w konfiguracji cert-managera, `enableGatewayAPI`).
- Narzędzie do migracji: `ingress2gateway` (projekt Kubernetes SIG Network) tłumaczy Ingress z adnotacjami popularnych kontrolerów na Gateway + HTTPRoute. Wynik trzeba przejrzeć.

Krótko: **Ingress wystarczy, gdy jest prosto i działa. Gateway API wybierz w nowym projekcie, przy wielu zespołach, przy canary i wszędzie tam, gdzie piszesz adnotacje kontrolera.**

## Na EKS, a on-prem?

Lab08 robimy na EKS, gdzie load balancer i publiczny adres daje chmura. Na własnych serwerach każde ogniwo trzeba czymś zastąpić, ale Twój Ingress i HTTPRoute wyglądają tak samo.

| Ogniwo | EKS (nasz klaster) | On-prem |
|---|---|---|
| DNS | wildcard CNAME `*.<DOMENA>` → nazwa NLB | wildcard w wewnętrznym DNS → adres VIP |
| Adres i load balancer | AWS NLB z Service LoadBalancer | MetalLB / kube-vip / Cilium albo zewnętrzny HAProxy, F5 |
| Kontroler | Traefik | Traefik (albo inny kontroler) — bez zmian |
| Certyfikat | Let's Encrypt, HTTP-01 | DNS-01 albo wewnętrzne CA |
| Service LoadBalancer bez dodatków | adres od AWS | `EXTERNAL-IP <pending>` na zawsze |

Szczegóły i lab08 przełożony na własną serwerownię: [`on-prem.md`](on-prem.md).

## Diagnoza krok po kroku (od końca)

```bash
kubectl get pods -l app=<app>                                  # 1. pody Running i READY 1/1?
kubectl get endpointslices -l kubernetes.io/service-name=<svc> # 2. są adresy? pusto = selektor albo readiness
kubectl describe svc <svc>                                     # 3. Selector, Port, TargetPort
kubectl describe ingress <ingress>                             # 4. klasa, host, backend (svc:port + IP podów), Events
kubectl get ingressclass                                       # 5. czy klasa istnieje
kubectl describe httproute <route>                             # Gateway API: Accepted, ResolvedRefs
```

Najpierw sprawdź, czy Service działa wewnątrz klastra (`kubectl port-forward svc/<svc> 8080:80`). Jeśli nie — problem nie leży w Ingressie.

| Objaw | Przyczyna | Co zrobić |
|---|---|---|
| `404` dla Twojego hosta | inny host w curl niż w Ingressie, literówka w loginie, brak reguły dla ścieżki | porównaj `Host:` z `kubectl get ingress` (kolumna HOSTS) |
| `404`, Ingress wygląda dobrze | `backend.service.name` wskazuje nieistniejący Service | `describe ingress` → `<error: services "x" not found>` |
| Ingress bez `ADDRESS` | zła `ingressClassName`, kontroler go ignoruje | `kubectl get ingressclass`, wpisz `traefik` |
| `503` | pusty EndpointSlice: selektor nie pasuje do etykiet albo pody nie są Ready | `get pods --show-labels`, sondy |
| `502` | `targetPort` w Service nie zgadza się z portem aplikacji | `describe svc` vs `containerPort` |
| `404`/`503` mimo działającego Service | `port` w Ingressie ≠ `port` Service (wpisany port kontenera) | w Ingressie port **Service**, nie kontenera |
| aplikacja dostaje `/app1/...` i zwraca 404 | ścieżka przekazywana bez zmian | aplikacja pod `/app1/` albo rewrite (Middleware / `URLRewrite`) |
| HTTPS: certyfikat „TRAEFIK DEFAULT CERT” | brak/zły Secret albo host w `tls` ≠ host w `rules` | `kubectl get secret <tls>`, popraw `hosts`; więcej w [`cert-manager.md`](cert-manager.md#diagnoza) |
| Service LoadBalancer: `EXTERNAL-IP <pending>` | brak integracji z chmurą (kind, on-prem) | [`on-prem.md`](on-prem.md) |
| NodePort działa z poda, z laptopa nie | węzły bez publicznych adresów | to normalne na EKS; wystaw przez Ingress |
| HTTPRoute `Accepted=False` | zły `parentRefs` albo Gateway nie wpuszcza Twojego namespace | nazwa/namespace z `kubectl get gateway -A` |
| HTTPRoute `ResolvedRefs=False` | zła nazwa lub port Service w `backendRefs` | `kubectl get svc` |
| `no matches for kind "HTTPRoute"` | na klastrze nie ma CRD Gateway API | zapytaj trenera |

## Linki

- W tym katalogu: [`cert-manager.md`](cert-manager.md), [`on-prem.md`](on-prem.md), [`diagram.html`](diagram.html)
- Lab: [`labs/lab08-service-ingress/`](../../../labs/lab08-service-ingress/)
- Przykłady: [`przyklady/k8s/05-service/`](../../../przyklady/k8s/05-service), [`przyklady/k8s/06-ingress/`](../../../przyklady/k8s/06-ingress), [`przyklady/k8s/07-gateway-api/`](../../../przyklady/k8s/07-gateway-api)
- Kubernetes: [Service](https://kubernetes.io/docs/concepts/services-networking/service/), [Ingress](https://kubernetes.io/docs/concepts/services-networking/ingress/), [Ingress Controllers](https://kubernetes.io/docs/concepts/services-networking/ingress-controllers/), [Gateway API](https://kubernetes.io/docs/concepts/services-networking/gateway/)
- AWS: [Service LoadBalancer na EKS](https://docs.aws.amazon.com/eks/latest/userguide/network-load-balancing.html), [AWS Load Balancer Controller](https://kubernetes-sigs.github.io/aws-load-balancer-controller/)
- Traefik: [Kubernetes Ingress](https://doc.traefik.io/traefik/routing/providers/kubernetes-ingress/), [Middleware](https://doc.traefik.io/traefik/middlewares/overview/)
- Gateway API: [gateway-api.sigs.k8s.io](https://gateway-api.sigs.k8s.io/), [HTTPRoute](https://gateway-api.sigs.k8s.io/api-types/httproute/)
