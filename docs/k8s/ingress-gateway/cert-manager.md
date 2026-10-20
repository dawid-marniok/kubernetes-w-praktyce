# cert-manager i TLS na Ingressie

Jak powstaje certyfikat, który Traefik pokazuje pod `https://<login>.<DOMENA>`. Skrót i manifest do labu są w [`README.md`](README.md#tls-z-cert-managerem--w-skrócie), ćwiczysz to w [lab08](../../../labs/lab08-service-ingress/) (krok 4). Animacja przepływu: [`diagram.html`](diagram.html) (otwórz w przeglądarce).

Na naszym klastrze: cert-manager w namespace `cert-manager`, `ClusterIssuer` `letsencrypt-prod` (Let's Encrypt, wyzwanie HTTP-01 rozwiązywane przez Traefika), domena `k8s.marniok.dev`.

## Po co cert-manager

Przeglądarka ufa certyfikatowi, jeśli podpisało go zaufane CA. Let's Encrypt wystawia takie certyfikaty za darmo, automatycznie, przez protokół **ACME**, ale tylko na 90 dni. Ręczne zamawianie i podmienianie Secretów co dwa miesiące dla kilkudziesięciu hostów nie ma sensu. cert-manager robi to za Ciebie: zamawia, zapisuje do Secretu, pilnuje daty ważności i odnawia.

## Komponenty

| Element | Co robi |
|---|---|
| **controller** (Deployment `cert-manager`) | główna pętla: obserwuje obiekty, rozmawia z ACME, tworzy solvery, zapisuje Secrety |
| **webhook** (`cert-manager-webhook`) | waliduje i uzupełnia obiekty cert-managera przy `apply`; bez niego `apply` kończy się błędem `failed calling webhook` |
| **cainjector** (`cert-manager-cainjector`) | wstrzykuje certyfikat CA do konfiguracji webhooków i CRD (np. webhooka samego cert-managera) |

CRD, które zobaczysz:

| Obiekt | Kto tworzy | Co to jest |
|---|---|---|
| `Issuer` / `ClusterIssuer` | administrator | **skąd** brać certyfikaty: Let's Encrypt (ACME), własne CA, Vault… |
| `Certificate` | Ty albo cert-manager z adnotacji (ingress-shim) | **jaki** certyfikat: hosty, nazwa Secretu, Issuer |
| `CertificateRequest` | cert-manager | jedno żądanie podpisania (CSR) dla danego `Certificate` |
| `Order` | cert-manager (tylko ACME) | zamówienie w Let's Encrypt |
| `Challenge` | cert-manager (tylko ACME) | jedno wyzwanie na jeden host: dowód, że kontrolujesz domenę |

Dla Issuerów innych niż ACME (np. `ca`, `vault`) nie ma `Order` ani `Challenge`: `CertificateRequest` jest podpisywany od razu.

## Issuer czy ClusterIssuer

| | `Issuer` | `ClusterIssuer` |
|---|---|---|
| Zasięg | jeden namespace | cały klaster |
| Adnotacja na Ingressie | `cert-manager.io/issuer: <nazwa>` | `cert-manager.io/cluster-issuer: <nazwa>` |
| Sekrety (klucz konta ACME, dane do DNS) | w tym samym namespace | w namespace cert-managera |
| Kiedy | zespół ma własne konto / własne CA | wspólna konfiguracja dla wszystkich — **u nas** |

Na wspólnym klastrze nie tworzysz własnego Issuera z kontem Let's Encrypt: limity liczą się na domenę, nie na konto.

## Ingress → Certificate (ingress-shim)

Nie piszesz obiektu `Certificate`. Część cert-managera zwana **ingress-shim** obserwuje Ingressy. Gdy Ingress ma adnotację `cert-manager.io/cluster-issuer` (albo `cert-manager.io/issuer`) i sekcję `tls`, tworzy `Certificate`:

| Z Ingressu | Do `Certificate` |
|---|---|
| `spec.tls[].secretName` | `metadata.name` i `spec.secretName` (Certificate ma taką nazwę jak Secret) |
| `spec.tls[].hosts` | `spec.dnsNames` |
| adnotacja | `spec.issuerRef` |

Właścicielem `Certificate` jest Ingress: usunięcie Ingressu usuwa `Certificate`, ale **Secret zostaje**.

Ten sam certyfikat jako jawny obiekt (gdy np. Secret ma użyć kilka Ingressów albo coś innego niż Ingress):

```yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: web-tls
spec:
  secretName: web-tls
  dnsNames:
  - <login>.<DOMENA>
  issuerRef:
    kind: ClusterIssuer
    name: letsencrypt-prod
```

## HTTP-01 krok po kroku

Tak to działa na naszym klastrze.

1. **Ty:** `kubectl apply` Ingressu z adnotacją `cert-manager.io/cluster-issuer: letsencrypt-prod` i sekcją `tls`.
2. **ingress-shim** tworzy `Certificate` `web-tls`. Secret jeszcze nie istnieje, więc cert-manager zaczyna wystawianie: generuje klucz prywatny (najpierw w tymczasowym Secrecie) i tworzy `CertificateRequest` `web-tls-1` z CSR.
3. Issuer jest typu ACME, więc powstaje **`Order`** w Let's Encrypt. Let's Encrypt odpowiada: dla hosta `<login>.<DOMENA>` udowodnij kontrolę przez HTTP-01, oto token.
4. cert-manager tworzy **`Challenge`** i rozwiązanie wyzwania w Twoim namespace:
   - pod `cm-acme-http-solver-<losowe>` — mały serwer HTTP na porcie **8089**, który zwraca token, etykieta `acme.cert-manager.io/http01-solver: "true"`,
   - Service do tego poda (domyślnie typu NodePort),
   - tymczasowy Ingress `cm-acme-http-solver-<losowe>` z klasą `traefik`, hostem `<login>.<DOMENA>` i ścieżką `/.well-known/acme-challenge/<token>`.
5. **Self-check:** cert-manager sam wywołuje `http://<login>.<DOMENA>/.well-known/acme-challenge/<token>` (przez DNS, NLB i Traefika). Dopóki nie dostanie tokenu, czeka i ponawia. Dopiero potem zgłasza Let's Encrypt gotowość.
6. **Let's Encrypt** łączy się z internetu po HTTP na **port 80** z Twoim hostem i pobiera token. Zgadza się → wyzwanie zaliczone, `Order` przechodzi w `valid`.
7. cert-manager pobiera podpisany certyfikat i zapisuje go razem z kluczem w Secrecie `web-tls` (typ `kubernetes.io/tls`, klucze `tls.crt` i `tls.key`). `Certificate` dostaje `READY True`.
8. Pod solvera, jego Service i tymczasowy Ingress znikają. **Traefik** widzi Secret wskazany w `spec.tls` Twojego Ingressu i od tej chwili pokazuje ten certyfikat klientom, którzy w TLS (SNI) proszą o `<login>.<DOMENA>`.

Prawdziwy przebieg na naszym klastrze (20.10.2026, namespace testowy, host `lab08test.k8s.marniok.dev`):

```text
$ kubectl get certificate,order,challenge          # po ok. 4 s
certificate.cert-manager.io/lab08-web-tls   False   lab08-web-tls   4s
order.acme.cert-manager.io/lab08-web-tls-1-377731385   pending   4s
challenge.acme.cert-manager.io/lab08-web-tls-1-377731385-556202022   pending   lab08test.k8s.marniok.dev   2s

$ kubectl get pods,ingress | grep acme
pod/cm-acme-http-solver-qcqm6    1/1     Running   0          2s
ingress.networking.k8s.io/cm-acme-http-solver-9hfwd   traefik   lab08test.k8s.marniok.dev   …elb.eu-central-1.amazonaws.com   80   2s

$ kubectl describe certificate lab08-web-tls       # po 27 s READY True
  Normal  Issuing    28s   cert-manager-certificates-trigger          Issuing certificate as Secret does not exist
  Normal  Generated  28s   cert-manager-certificates-key-manager      Stored new private key in temporary Secret resource "lab08-web-tls-dtm8z"
  Normal  Requested  28s   cert-manager-certificates-request-manager  Created new CertificateRequest resource "lab08-web-tls-1"
  Normal  Issuing    2s    cert-manager-certificates-issuing          The certificate has been successfully issued

$ curl -sI https://lab08test.k8s.marniok.dev | head -1
HTTP/2 200

$ openssl s_client -connect lab08test.k8s.marniok.dev:443 -servername lab08test.k8s.marniok.dev </dev/null 2>/dev/null \
    | openssl x509 -noout -subject -issuer -dates
subject=CN=lab08test.k8s.marniok.dev
issuer=C=US, O=Let's Encrypt, CN=YR2
notBefore=Oct 20 04:10:58 2026 GMT
notAfter=Jan 18 04:10:57 2027 GMT
```

Na żywo: `kubectl get certificate,order,challenge -w` w drugim terminalu.

Warunki HTTP-01:
- host musi być **publiczny**: Let's Encrypt łączy się z internetu, a nie z Twojej sieci,
- port **80** musi być otwarty aż do kontrolera Ingress (nawet jeśli sama aplikacja ma działać tylko po HTTPS),
- **nie da się** zamówić tak certyfikatu wildcard (`*.<DOMENA>`).

## DNS-01

Zamiast pliku pod adresem HTTP dowodem jest rekord TXT `_acme-challenge.<host>` w DNS. cert-manager wpisuje go przez API dostawcy DNS, Let's Encrypt go odczytuje, cert-manager go kasuje. Do klastra nikt z zewnątrz się nie łączy.

Kiedy DNS-01:
- **wildcard** (`*.example.com`) — tylko tą metodą,
- host **niedostępny z internetu** (aplikacja wewnętrzna, VPN, środowisko testowe za firewallem),
- **on-prem**: klaster w firmowej sieci, bez publicznego adresu dla Ingressu ([`on-prem.md`](on-prem.md)),
- port 80 zamknięty z polityki bezpieczeństwa.

Wbudowane solvery: `route53` (AWS), `cloudflare`, `azureDNS`, `cloudDNS` (Google), `digitalocean`, `akamai`, `acmeDNS` i **`rfc2136`** (standardowe dynamiczne aktualizacje DNS z kluczem TSIG — BIND, PowerDNS, Windows DNS po konfiguracji). Inni dostawcy: solver `webhook` z dodatkowym komponentem od społeczności albo dostawcy.

ClusterIssuer z DNS-01 przez Cloudflare (token API w Secrecie w namespace `cert-manager`):

```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-dns
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: <e-mail>
    privateKeySecretRef:
      name: letsencrypt-dns-konto        # klucz konta ACME, tworzy cert-manager
    solvers:
    - selector:
        dnsZones: [example.com]          # ten solver tylko dla tej strefy
      dns01:
        cloudflare:
          apiTokenSecretRef:
            name: cloudflare-api-token
            key: api-token
```

Na EKS z Route53 zamiast klucza w Secrecie daje się cert-managerowi rolę IAM (IRSA albo EKS Pod Identity) z prawem do zmiany rekordów w strefie. Naszej domeny pilnuje zenbox.pl, dla którego nie ma solvera, dlatego na klastrze szkoleniowym używamy HTTP-01.

Jeden ClusterIssuer może mieć kilka solverów: `selector` (`dnsZones`, `dnsNames`, `matchLabels`) decyduje, który obsłuży dany host. Typowo: HTTP-01 dla zwykłych hostów, DNS-01 dla wildcardu.

## Staging i produkcja

| | `letsencrypt-staging` | `letsencrypt-prod` |
|---|---|---|
| Adres ACME | `https://acme-staging-v02.api.letsencrypt.org/directory` | `https://acme-v02.api.letsencrypt.org/directory` |
| Przeglądarka ufa | **nie** (testowe CA) | tak |
| Limity | dużo wyższe | ostre, patrz niżej |
| Kiedy | pierwsze próby, testy w pętli, CI | gdy staging działa |

Wzór ClusterIssuera dla stagingu: `przyklady/k8s/06-ingress/cluster-issuer.yaml`. Przejście na produkcję: zmień adnotację na Ingressie i usuń stary Secret (inaczej cert-manager uzna, że certyfikat już jest).

## Limity Let's Encrypt

| Limit | Wartość | Co to znaczy u nas |
|---|---|---|
| Nowe certyfikaty na **zarejestrowaną domenę** | 50 na tydzień | wspólne dla całego `marniok.dev`: wszyscy uczestnicy i trener |
| Duplikaty (dokładnie ten sam zestaw hostów) | 5 na tydzień | 6. raz kasujesz Secret i zamawiasz ten sam host → `rateLimited` |
| Nieudane walidacje | kilka na godzinę na host i konto | literówki w pętli szybko blokują host na godzinę |

Jak nie wpaść w limit:
- **Secret zostaje** po `kubectl delete ingress`. Ponowny `apply` tego samego Ingressu z tym samym `secretName` i tym samym hostem → cert-manager widzi ważny certyfikat i **nie zamawia** nowego.
- Nie kasuj Secretu „żeby odświeżyć”. Odnowienie zrobi cert-manager.
- Eksperymentujesz → `letsencrypt-staging`.

## Odnawianie

- Certyfikat Let's Encrypt jest ważny **90 dni**.
- cert-manager odnawia go sam, domyślnie gdy zostaje 1/3 ważności, czyli ok. **30 dni przed końcem** (pole `spec.renewBefore` w `Certificate` to zmienia).
- Kiedy: `status.notAfter` (koniec ważności) i `status.renewalTime` (planowane odnowienie):

```bash
kubectl get certificate web-tls -o jsonpath='{.status.notAfter}{"  odnowienie: "}{.status.renewalTime}{"\n"}'
```

- Odnowienie przechodzi tę samą drogę (`CertificateRequest` `web-tls-2`, `Order`, `Challenge`), więc wymaga, żeby host dalej był osiągalny. Traefik podmienia certyfikat bez restartu, gdy zmieni się Secret.

## NetworkPolicy blokuje solver

Jeśli w namespace działa NetworkPolicy **default-deny** na ruch przychodzący (dzień 4, lab15), pod `cm-acme-http-solver-*` też jest odcięty. Self-check nie dostaje tokenu, `Challenge` wisi w `pending`, w `describe challenge`: `failed to perform self check GET request ... context deadline exceeded`.

Ruch do solvera przychodzi od kontrolera Ingress (u nas Traefik w namespace `traefik`), bo to on przekazuje żądanie z tymczasowego Ingressu. Wpuść go na port 8089:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-acme-http01-solver
spec:
  podSelector:
    matchLabels:
      acme.cert-manager.io/http01-solver: "true"
  policyTypes: [Ingress]
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: traefik     # namespace kontrolera Ingress
    ports:
    - protocol: TCP
      port: 8089
```

## Gateway API

Na Gatewayu działa to podobnie, ale adnotację i TLS ma **Gateway**, a nie HTTPRoute. To zespół platformy decyduje o certyfikatach, zespół aplikacji pisze tylko trasy.

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: przyklad-gw
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  gatewayClassName: traefik
  listeners:
  - name: https
    protocol: HTTPS
    port: 8443                    # port entrypointu Traefika (websecure), nie 443
    hostname: gw-<login>.<DOMENA> # z hostname cert-manager bierze dnsNames
    tls:
      mode: Terminate
      certificateRefs:
      - name: przyklad-gw-tls     # Secret, który utworzy cert-manager
```

- cert-manager tworzy `Certificate` dla każdego listenera z `hostname` i `tls.certificateRefs`. Obsługę Gatewayów trzeba w nim włączyć (`config.enableGatewayAPI: true` w konfiguracji cert-managera), a w klastrze muszą być CRD Gateway API.
- Wyzwanie HTTP-01 można rozwiązać tymczasowym Ingressem (jak wyżej) albo tymczasowym **HTTPRoute**: solver `http01.gatewayHTTPRoute` z `parentRefs` wskazującym Gateway z listenerem HTTP.
- Pełny przykład: `przyklady/k8s/07-gateway-api/gateway.yaml`. Na klastrze szkoleniowym Gateway API pokazuje prowadzący w demie; CRD sprawdzisz `kubectl get crd | grep gateway.networking.k8s.io`.

## Domena `.dev` i HSTS

Domena najwyższego poziomu `.dev` jest w całości na liście **HSTS preload** wbudowanej w przeglądarki. Przeglądarka zamienia każdy adres `http://<host>.dev` na `https://` jeszcze przed wysłaniem żądania i nie pozwala kliknąć „przejdź mimo to” przy złym certyfikacie.

- Ingress bez `tls` → w przeglądarce `TRAEFIK DEFAULT CERT` i błąd bez obejścia.
- `curl http://<login>.<DOMENA>` działa, bo curl nie korzysta z listy HSTS przeglądarek.
- Certyfikat jeszcze się wystawia → odczekaj, aż `READY True`, i odśwież.

## Diagnoza

Idź po łańcuchu od góry, aż trafisz na obiekt z problemem:

```bash
kubectl get certificate                        # READY? 
kubectl describe certificate web-tls           # Events: Issuing, Requested…
kubectl get certificaterequest                 # APPROVED, READY
kubectl describe order <nazwa>                 # State, Reason
kubectl describe challenge <nazwa>             # najczęściej tu jest odpowiedź
kubectl get pods,svc,ingress | grep acme       # czy solver istnieje
kubectl get secret web-tls                     # typ kubernetes.io/tls
```

| Objaw / komunikat | Przyczyna | Co zrobić |
|---|---|---|
| Brak obiektu `Certificate` | brak adnotacji, literówka w adnotacji albo brak `spec.tls` | `kubectl get ingress <nazwa> -o yaml`, dopisz obie rzeczy |
| `Certificate` `False`, `Issuer ... not found` / `not ready` | zła nazwa Issuera albo `issuer` zamiast `cluster-issuer` | `kubectl get clusterissuer` |
| Challenge: `no such host` / `NXDOMAIN` | literówka w hoście, dwa poziomy pod domeną (`a.<login>.<DOMENA>`) | popraw host w `rules` i `tls` |
| Challenge: self check `404` | host w `tls` ≠ host w `rules`, inny Ingress z tym samym hostem przejmuje ruch | ten sam host w obu miejscach, unikalny host |
| Challenge: self check `context deadline exceeded` / `connection refused` | NetworkPolicy odcina solver, port 80 zamknięty, DNS jeszcze nie wskazuje na LB | reguła NetworkPolicy wyżej, `dig +short <host>` |
| Order `invalid`, `rateLimited` / `too many certificates` | limit Let's Encrypt | poczekaj (limit tygodniowy), na próby `letsencrypt-staging` |
| `READY True`, a przeglądarka ostrzega | certyfikat ze stagingu albo `TRAEFIK DEFAULT CERT` (Secret w innym namespace, inny host) | `openssl s_client … \| openssl x509 -noout -issuer -subject` |
| `failed calling webhook "webhook.cert-manager.io"` | webhook cert-managera nie działa | sprawa administratora: `kubectl get pods -n cert-manager` |

Zwykle `READY True` jest po 30–90 s. Gdy `False` dłużej niż 2 minuty, patrz w `describe challenge`. Nieudane wyzwanie cert-manager ponawia z rosnącymi przerwami, więc po poprawce może minąć chwila, zanim spróbuje znowu.

## Bez Let's Encrypt: alternatywy

| Rozwiązanie | Jak działa | Kiedy |
|---|---|---|
| **Issuer `ca`** (własne CA w cert-managerze) | cert-manager podpisuje certyfikaty kluczem CA z Secretu | klaster wewnętrzny, testy; klienci muszą ufać Twojemu CA |
| **Issuer `selfSigned`** | certyfikat podpisany sam sobą | głównie do „zasiania” własnego CA (bootstrap), nie do aplikacji |
| **HashiCorp Vault PKI** (Issuer `vault`) | cert-manager prosi Vault o podpis; Vault trzyma CA i polityki | firma już ma Vaulta, krótkie certyfikaty, audyt |
| **step-ca** (Smallstep) | własny serwer CA z protokołem ACME; cert-manager używa go jak Let's Encrypt (Issuer `acme` z adresem step-ca) | on-prem, chcesz ACME bez internetu |
| **Venafi / korporacyjne CA** (Issuer `venafi`, AD CS przez zewnętrzne Issuery) | cert-manager zamawia w firmowym systemie PKI | duże firmy z centralną polityką certyfikatów |
| **Certyfikat wgrany ręcznie** | `kubectl create secret tls web-tls --cert=tls.crt --key=tls.key` | certyfikat kupiony albo wydany poza klastrem; odnawiasz sam |
| **AWS ACM na load balancerze** | TLS kończy się na NLB/ALB, do Traefika idzie już HTTP; certyfikat odnawia AWS | wszystko w AWS, nie chcesz kluczy w klastrze |

Własne CA w cert-managerze, od zera:

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
  name: firmowe-ca
  namespace: cert-manager          # wyjątek: dla ClusterIssuera Secret CA musi być w namespace cert-managera
spec:
  isCA: true
  commonName: Firmowe CA
  secretName: firmowe-ca
  duration: 87600h                 # 10 lat
  privateKey:
    algorithm: ECDSA
    size: 256
  issuerRef:
    kind: ClusterIssuer
    name: selfsigned
---
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: firmowe-ca
spec:
  ca:
    secretName: firmowe-ca
```

Od tej chwili Ingress z `cert-manager.io/cluster-issuer: firmowe-ca` dostaje certyfikat od razu, bez `Order` i `Challenge`. Przeglądarki zaufają mu dopiero po dodaniu certyfikatu CA do zaufanych (GPO, MDM, obraz systemu). Do rozprowadzania CA do podów w klastrze służy osobny projekt **trust-manager**.

AWS ACM na Service LoadBalancer (NLB kończy TLS):

```yaml
metadata:
  annotations:
    service.beta.kubernetes.io/aws-load-balancer-type: nlb
    service.beta.kubernetes.io/aws-load-balancer-ssl-cert: arn:aws:acm:eu-central-1:<konto>:certificate/<id>
    service.beta.kubernetes.io/aws-load-balancer-ssl-ports: "443"
```

Z ALB (wymaga AWS Load Balancer Controllera, u nas go nie ma) certyfikat wskazujesz adnotacją Ingressu `alb.ingress.kubernetes.io/certificate-arn`. W obu przypadkach Traefik nie widzi TLS, a hosty i certyfikaty zarządza się po stronie AWS, nie w Kubernetesie.

## Linki

- cert-manager: [dokumentacja](https://cert-manager.io/docs/), [Ingress (ingress-shim)](https://cert-manager.io/docs/usage/ingress/), [Gateway API](https://cert-manager.io/docs/usage/gateway/), [HTTP-01](https://cert-manager.io/docs/configuration/acme/http01/), [DNS-01](https://cert-manager.io/docs/configuration/acme/dns01/), [Issuer CA](https://cert-manager.io/docs/configuration/ca/), [diagnoza](https://cert-manager.io/docs/troubleshooting/acme/)
- Let's Encrypt: [typy wyzwań](https://letsencrypt.org/docs/challenge-types/), [limity](https://letsencrypt.org/docs/rate-limits/), [staging](https://letsencrypt.org/docs/staging-environment/)
- [Lista HSTS preload](https://hstspreload.org/)
