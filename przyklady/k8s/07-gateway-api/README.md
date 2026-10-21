# Przykłady: Gateway API

**Cel:** wystawić aplikację przez Gateway i HTTPRoute oraz zobaczyć w standardzie to, co w Ingressie wymaga adnotacji: rewrite i podział ruchu (canary).

**Gdzie:** klaster szkoleniowy EKS, Twój namespace (wariant na kind na końcu). Komendy wydajesz w tym katalogu (`cd przyklady/k8s/07-gateway-api`).

Gateway API (`gateway.networking.k8s.io/v1`) to następca Ingressu. Ingress łączy w jednym obiekcie wybór kontrolera, TLS i reguły routingu, a wszystko ponad host i ścieżkę (wagi, nagłówki, rewrite) chowa w adnotacjach konkretnego kontrolera. Gateway API dzieli to na trzy obiekty dla trzech ról i ma te funkcje w specyfikacji, więc ten sam YAML działa z Traefikiem, Envoy Gateway, Istio czy Cilium.

| Obiekt | Kto tworzy | Co opisuje |
|---|---|---|
| GatewayClass | dostawca / kontroler | który kontroler obsługuje bramy tej klasy (tu: `traefik`, tworzy ją chart Traefika) |
| Gateway | zespół platformy | wejście: porty, protokoły, hosty, certyfikat TLS i z których namespace'ów wolno się podpiąć |
| HTTPRoute | zespół aplikacji | host + ścieżka / nagłówki → Service, z wagami i filtrami |

## Jak płynie ruch

```
curl https://gw-trener.k8s.marniok.dev/app1/abc
  │  DNS: *.k8s.marniok.dev → NLB
  ▼
NLB :443 ──► Traefik, entrypoint websecure (:8443)
  ▼
Gateway przyklad-gw, listener https (hostname + port 8443, TLS z Secretu przyklad-gw-tls)
  ▼
HTTPRoute podpięte pod ten Gateway (parentRefs), dopasowanie hosta i ścieżki
  ▼
Service ──► pod
```

HTTPRoute nie wie nic o Traefiku. Wskazuje Gateway (`parentRefs`), a Gateway wskazuje kontroler przez `gatewayClassName`. Zmiana kontrolera to zmiana jednej linii w Gatewayu, routy zostają bez zmian.

## Pliki

| Plik | Co pokazuje |
|---|---|
| `aplikacje.yaml` | backendy do demo: `web-v1`, `web-v2`, `app1` (`traefik/whoami`: odpowiada nazwą wersji i ścieżką, którą dostał pod) |
| `gateway.yaml` | Gateway z listenerami HTTP (8000) i HTTPS (8443); certyfikat Let's Encrypt zamawia cert-manager z adnotacji |
| `httproute.yaml` | host + `PathPrefix /` → Service `przyklad-deploy` (nginx z `../03-deployment`), czyli to samo co `../06-ingress/ingress.yaml` |
| `httproute-canary.yaml` | wagi 90/10 między `web-v1` a `web-v2`; przesunięcie ruchu = zmiana wag i `apply` |
| `httproute-rewrite.yaml` | filtr `URLRewrite`: `/app1/abc` → pod dostaje `/abc` |

Host w plikach to `gw-trener.k8s.marniok.dev`. Kursant podmienia `trener` na swój login, bo Traefik jest wspólny i host musi być unikalny. Wildcard DNS obejmuje jeden poziom: `gw-<login>.k8s.marniok.dev` działa, `a.b.k8s.marniok.dev` nie.

Porty listenerów to porty entrypointów Traefika (`web` = 8000, `websecure` = 8443), a nie 80/443. NLB przyjmuje ruch na 80/443 i przekazuje go na 8000/8443. Gateway z portem 80 będzie miał `Accepted=False` (`PortUnavailable`).

## Krok po kroku

Na szkoleniu Gateway API pokazuje prowadzący (host `gw-trener…`), a w labie kursanci ćwiczą Ingress. Możesz powtórzyć demo u siebie: wszystkie pliki mają host `gw-trener.k8s.marniok.dev`, więc podmieniasz `trener` na swój login w locie przez `sed`. Klaster `k8s-sages` ma już wszystko, czego trzeba: CRD Gateway API v1.6.1, Traefik z providerem `kubernetesGateway` i cert-manager z `enableGatewayAPI`.

```bash
LOGIN=user07          # Twój login
```

**1. CRD i klasa**
```bash
kubectl get crd | grep gateway.networking.k8s.io
kubectl get gatewayclass
```
Co powinieneś zobaczyć: CRD `gateways…`, `httproutes…`, `referencegrants…` itd. oraz `traefik` z `ACCEPTED True`. Bez CRD każdy `apply` skończy się `no matches for kind "Gateway"`.

**2. Backendy**
```bash
kubectl apply -f ../03-deployment/deployment-rolling.yaml -f ../05-service/clusterip.yaml
kubectl apply -f aplikacje.yaml
kubectl get deploy
```
Co powinieneś zobaczyć: `przyklad-deploy` 3/3 oraz `web-v1`, `web-v2`, `app1` po 1/1.

**3. Gateway (rola platformy)**
```bash
sed "s/gw-trener/gw-$LOGIN/g" gateway.yaml | kubectl apply -f -
kubectl get gateway przyklad-gw
kubectl get certificate -w                    # Ctrl+C po READY True (ok. 30–60 s, HTTP-01)
```
Co powinieneś zobaczyć: `CLASS traefik`, `PROGRAMMED True`, w `ADDRESS` adres load balancera Traefika. Certificate `przyklad-gw-tls` z `READY True`.

**4. HTTPRoute (rola aplikacji)**
```bash
sed "s/gw-trener/gw-$LOGIN/g" httproute.yaml | kubectl apply -f -
kubectl get httproute przyklad-route -o jsonpath='{range .status.parents[*].conditions[*]}{.type}={.status}{"\n"}{end}'
curl -s https://gw-$LOGIN.k8s.marniok.dev | grep title
```
Co powinieneś zobaczyć: `Accepted=True` i `ResolvedRefs=True` (pełny opis: `kubectl describe httproute przyklad-route`). `curl` zwraca `<title>Welcome to nginx!</title>`.

**5. Rewrite**
```bash
sed "s/gw-trener/gw-$LOGIN/g" httproute-rewrite.yaml | kubectl apply -f -
curl -s https://gw-$LOGIN.k8s.marniok.dev/app1/abc | grep -E 'Name|GET'
```
Co powinieneś zobaczyć: `Name: app1` i `GET /abc HTTP/1.1`: pod dostał ścieżkę bez `/app1`. Działa obok `httproute.yaml`, bo `/app1` jest dłuższe niż `/` i wygrywa.

**6. Canary 90/10**
```bash
kubectl delete httproute przyklad-route       # ten sam host i ścieżka / co canary
sed "s/gw-trener/gw-$LOGIN/g" httproute-canary.yaml | kubectl apply -f -
for i in $(seq 100); do curl -s https://gw-$LOGIN.k8s.marniok.dev | grep ^Name; done | sort | uniq -c
```
Co powinieneś zobaczyć: około `90 Name: web-v1` i `10 Name: web-v2` (rozkład losowy, więc np. 87/13). Zmień wagi w kopii pliku (np. 50/50 albo 0/100), `apply` i powtórz pętlę.

## Sprzątanie
```bash
kubectl delete -f httproute-canary.yaml -f httproute-rewrite.yaml -f gateway.yaml -f aplikacje.yaml --ignore-not-found
kubectl delete httproute przyklad-route --ignore-not-found
kubectl delete secret przyklad-gw-tls     # opcjonalnie; zostawiony Secret = brak ponownego zamawiania certyfikatu
kubectl delete -f ../05-service/clusterip.yaml -f ../03-deployment/deployment-rolling.yaml
```

## Uwagi

### Ingress a Gateway API: gdzie jest co

| | Ingress | Gateway API |
|---|---|---|
| wybór kontrolera | `ingressClassName: traefik` w Ingressie | `gatewayClassName: traefik` w Gatewayu |
| reguły host/ścieżka | w tym samym obiekcie | w HTTPRoute (`parentRefs` → Gateway) |
| certyfikat TLS | `spec.tls` + adnotacja cert-managera na Ingressie | listener HTTPS (`certificateRefs`) + adnotacja cert-managera na Gatewayu |
| kto może się podpiąć | każdy, kto może tworzyć Ingress | `allowedRoutes` w listenerze (`Same`, `All`, selektor namespace'ów) |
| wagi, nagłówki, rewrite | adnotacje / Middleware kontrolera | w specyfikacji (`weight`, `matches`, `filters`) |
| backend w innym namespace | niemożliwe | `ReferenceGrant` w namespace docelowym |

### Na kind

CRD nie przychodzą z chartem Traefika, więc instalujesz je najpierw:
```bash
kubectl apply --server-side -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.6.1/standard-install.yaml
helm upgrade --install traefik traefik/traefik -n traefik --create-namespace --set providers.kubernetesGateway.enabled=true
```
Chart tworzy GatewayClass `traefik` i domyślny Gateway `traefik-gateway` w namespace `traefik`. W `gateway.yaml` ustaw host `gw-<login>.local`, usuń listener `https` i adnotację cert-managera. Ruch puszczasz przez `kubectl port-forward -n traefik svc/traefik 8080:80`, a potem `curl -H 'Host: gw-<login>.local' localhost:8080`.

### Typowe problemy

- `no matches for kind "Gateway"` / `"HTTPRoute"` → na klastrze nie ma CRD Gateway API.
- Gateway bez `PROGRAMMED` / listener `Accepted=False` → port spoza entrypointów Traefika (80/443 zamiast 8000/8443) albo zła `gatewayClassName`.
- HTTPRoute `Accepted=False` → zły `parentRefs`, host spoza `hostname` listenera albo Gateway nie wpuszcza routów z Twojego namespace (`allowedRoutes`).
- HTTPRoute `ResolvedRefs=False` → zła nazwa lub port Service; Service w innym namespace wymaga `ReferenceGrant` w namespace docelowym.
- `kubectl get certificate` pusto → cert-manager bez `enableGatewayAPI` albo uruchomiony przed instalacją CRD (pomaga `kubectl rollout restart deploy -n cert-manager`).
- Dwa HTTPRoute z tym samym hostem i ścieżką → ruch dostaje tylko jeden (starszy). Dlatego przed canary usuwasz `przyklad-route`.
