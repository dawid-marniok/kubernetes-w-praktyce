# Lab08 robimy na EKS. Jak to wygląda on-prem?

Na klastrze szkoleniowym połowę pracy robi za nas AWS: daje load balancer z publicznym adresem, a Let's Encrypt może się do niego połączyć z internetu. Na własnych serwerach (bare metal, VMware, Proxmox, OpenShift bez chmury pod spodem) tych rzeczy nie ma. Ten plik pokazuje, czego brakuje i czym to się zastępuje. Ogólny opis Service i Ingressu: [`README.md`](README.md), certyfikaty: [`cert-manager.md`](cert-manager.md), przełącznik EKS / on-prem na diagramie: [`diagram.html`](diagram.html) (otwórz w przeglądarce).

**Puenta na początek:** Twoje polecenia z lab08 prawie się nie zmieniają. Ten sam Deployment, ten sam Service, ten sam Ingress. Zmienia się domena i nazwa Issuera. Reszta to praca administratora klastra.

## Co daje chmura, a czego brakuje

| Potrzeba | EKS robi to sam | Na własnych serwerach |
|---|---|---|
| Adres z zewnątrz dla Service `LoadBalancer` | `service-controller` tworzy NLB/Classic LB w AWS | nikt — `EXTERNAL-IP` zostaje `<pending>` |
| Rozkład ruchu na węzły i health check | load balancer AWS | trzeba postawić: MetalLB, kube-vip, HAProxy, F5… |
| Reguły zapory | security groupy tworzone automatycznie | firewall ustawiają sieciowcy |
| DNS | rekord w publicznym DNS → nazwa NLB | wpis w firmowym DNS → adres VIP |
| Certyfikat zaufany w przeglądarkach | Let's Encrypt HTTP-01 (host publiczny) | zwykle DNS-01 albo firmowe CA |

## Service LoadBalancer bez chmury

Na gołym klastrze (kubeadm, k0s, RKE2, kind) Service typu LoadBalancer wygląda tak bez końca:

```
NAME      TYPE           CLUSTER-IP     EXTERNAL-IP   PORT(S)
traefik   LoadBalancer   10.96.12.34    <pending>     80:31234/TCP,443:30443/TCP
```

NodePort jest przydzielony (LoadBalancer zawsze ma go pod spodem), ale nikt nie przydziela adresu, bo w klastrze nie ma kontrolera, który zawołałby API chmury. Tę rolę przejmuje jeden z projektów:

| Projekt | Jak ogłasza adres | Uwagi |
|---|---|---|
| **MetalLB** | L2 (ARP/NDP) albo BGP | najpopularniejszy, sam w sobie tylko do adresów Service |
| **kube-vip** | ARP albo BGP | często już jest w klastrze jako VIP dla API serwera; adresy dla Service z puli (kube-vip-cloud-provider) |
| **Cilium** LB IPAM + L2 announcements / BGP | ARP albo BGP | ma sens, gdy Cilium i tak jest siecią klastra (CNI) |
| **OpenELB** | ARP albo BGP | projekt CNCF, rzadziej spotykany |
| k3s ServiceLB | otwiera porty na węzłach | wbudowany w k3s, do małych instalacji |

### MetalLB w dwóch obiektach

MetalLB ma dwa komponenty: **controller** (Deployment) przydziela adres z puli, **speaker** (DaemonSet z `hostNetwork`) ogłasza go w sieci. Konfiguracja to CRD (`metallb.io/v1beta1`); stare tutoriale z ConfigMapą `config` są nieaktualne. Instalację i pule robi administrator, w namespace `metallb-system`:

```yaml
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata:
  name: ingress
  namespace: metallb-system
spec:
  addresses:
  - 10.20.30.200-10.20.30.220     # wolne adresy z podsieci węzłów, poza zakresem DHCP
---
apiVersion: metallb.io/v1beta1
kind: L2Advertisement
metadata:
  name: ingress-l2
  namespace: metallb-system
spec:
  ipAddressPools: [ingress]       # bez tej listy ogłasza wszystkie pule
```

Po tym `kubectl get svc -n traefik` pokazuje `EXTERNAL-IP 10.20.30.200` zamiast `<pending>`. Konkretny adres dla Traefika (żeby DNS się nie rozjechał po reinstalacji): adnotacja `metallb.io/loadBalancerIPs: 10.20.30.200` na Service. Starsze pole `spec.loadBalancerIP` jest wycofywane.

Pule adresów:
- adresy muszą być osiągalne dla klientów: w trybie L2 z tej samej podsieci co węzły, w BGP dowolne, które router rozgłosi dalej,
- **nie mogą** kolidować z DHCP ani z innymi urządzeniami (konflikt IP = losowe przerwy),
- kilka pul: `autoAssign: false` na puli „na żądanie” sprawia, że adres z niej dostaje tylko Service z adnotacją `metallb.io/address-pool: <pula>`,
- pula bez `L2Advertisement` / `BGPAdvertisement`: adres jest przydzielony, ale nikt go nie ogłasza — `EXTERNAL-IP` jest, a połączenie wisi.

Przy kube-proxy w trybie IPVS trzeba włączyć `strictARP: true` w jego konfiguracji, inaczej tryb L2 nie działa poprawnie.

### L2 a BGP

| | L2 (ARP) | BGP |
|---|---|---|
| Jak działa | jeden węzeł odpowiada na ARP „to ja mam 10.20.30.200” | każdy węzeł ogłasza trasę do adresu routerowi |
| Co trzeba mieć | wspólny segment sieci z klientami | router z BGP, numery ASN, współpraca z sieciowcami |
| Rozkład ruchu | **brak**: cały ruch dla adresu wchodzi przez jeden węzeł | router rozkłada na węzły (ECMP) |
| Awaria węzła | inny węzeł przejmuje adres (gratuitous ARP), przerwa kilka sekund | router wycofuje trasę |
| Kiedy | lab, małe on-prem, homelab | produkcja w centrum danych |

Ograniczenia L2 w praktyce:
- przepustowość wejścia to przepustowość **jednego** węzła (lidera dla danego adresu); dalej kube-proxy rozkłada ruch na pody na wszystkich węzłach,
- przy awarii węzła klienci widzą kilka sekund przerwy, a urządzenia z długim cache ARP mogą łączyć się ze starym węzłem dłużej,
- z `externalTrafficPolicy: Local` (zachowuje adres IP klienta) adres ogłaszają tylko węzły z działającym podem tego Service.

## Bez Service LoadBalancer

Wiele firm ma już load balancery sprzętowe albo zespół, który ich pilnuje. Wtedy klaster nie musi przydzielać adresów sam.

**1. Kontroler Ingress na NodePort + zewnętrzny load balancer.** Service Traefika typu `NodePort` ze stałymi portami (np. 30080 i 30443). Przed klastrem stoi HAProxy z keepalived (adres VIP przechodzi między dwiema maszynami), F5 BIG-IP, Citrix ADC albo NGINX. LB przekazuje `:80` → `<węzeł>:30080`, `:443` → `<węzeł>:30443` na wszystkie węzły i sprawdza je health checkiem. Tak wygląda to samo, co AWS zrobił nam automatycznie z Classic LB (`TCP:80` → NodePort na każdej instancji), tylko konfigurację pisze człowiek.

```
klient → VIP 10.20.30.10 (HAProxy + keepalived) → węzły :30080/:30443 → Traefik → Service → pody
```

Adres klienta znika po drodze (LB łączy się z węzłem we własnym imieniu). Jeśli aplikacja go potrzebuje: PROXY protocol między LB a Traefikiem albo nagłówek `X-Forwarded-For` przy LB działającym w L7.

**2. DaemonSet z `hostNetwork` albo `hostPort` na węzłach brzegowych.** Kilka węzłów oznaczonych etykietą (np. `node-role/edge`) i taintem, na każdym pod kontrolera słucha bezpośrednio na portach 80 i 443 węzła. Przed nimi DNS z kilkoma adresami albo VIP z keepalived. Bez NodePort i bez dodatkowego skoku, ale pody kontrolera zajmują porty węzła, a węzły brzegowe trzeba utrzymywać osobno.

## DNS

| | EKS (nasz klaster) | On-prem |
|---|---|---|
| Rekord | `*.k8s.marniok.dev` CNAME → nazwa NLB (w zenbox.pl) | `*.apps.firma.internal` A → VIP (np. 10.20.30.200) |
| Gdzie | publiczny DNS | firmowy DNS: Active Directory, BIND, Infoblox, PowerDNS |
| Kto wpisuje | administrator raz | administrator raz albo ExternalDNS |

Jeden rekord wildcard wystarczy na wszystkie hosty, tak jak u nas. Jeśli hosty mają powstawać i znikać automatycznie (np. środowisko na każdy branch), **ExternalDNS** czyta Ingressy i Service w klastrze i zakłada rekordy sam — obsługuje m.in. RFC2136 (BIND, Windows DNS), Infoblox, PowerDNS i Route53.

Częsty układ to split-horizon: ta sama nazwa w sieci firmowej wskazuje na wewnętrzny VIP, a z internetu nie istnieje albo wskazuje na inny adres.

## TLS on-prem

| Sytuacja | Co wybrać |
|---|---|
| Host publiczny, port 80 osiągalny z internetu | Let's Encrypt HTTP-01 — dokładnie jak na naszym klastrze |
| Domena publiczna, ale klaster tylko w sieci firmowej | Let's Encrypt **DNS-01** (dostawca DNS z API albo RFC2136) |
| Domena wewnętrzna (`.internal`, `.corp`; `.local` odradzane, bo koliduje z mDNS) | **firmowe CA**: Issuer `ca`, Vault PKI, step-ca (ACME bez internetu), Venafi / AD CS |
| Certyfikat kupiony albo wydany ręcznie | Secret `kubernetes.io/tls` wgrany przez `kubectl create secret tls` |

Let's Encrypt nie wystawi certyfikatu dla nazwy, której nie ma w publicznym DNS (np. `.internal`). Przy DNS-01 dla hostów wewnętrznych pamiętaj, że każdy wystawiony certyfikat trafia do publicznych logów Certificate Transparency, więc nazwy hostów stają się jawne. Dla firmowego CA klienci (przeglądarki, inne aplikacje) muszą ufać certyfikatowi CA — rozprowadza się go przez GPO, MDM albo obraz systemu. Konfiguracje Issuerów: [`cert-manager.md`](cert-manager.md#dns-01) i [`cert-manager.md`](cert-manager.md#bez-lets-encrypt-alternatywy).

## Który kontroler

Wybór kontrolera nie zależy od tego, czy klaster jest w chmurze. Na on-prem decyduje raczej to, co firma już zna i czy kontroler obsługuje Gateway API.

| Kontroler | Ingress | Gateway API | Uwagi |
|---|---|---|---|
| **Traefik** | tak | tak | u nas; Middleware jako CRD, prosty start |
| **NGINX Gateway Fabric** (F5 NGINX) | nie | tak | następca nginx w świecie Gateway API |
| F5 NGINX Ingress Controller | tak | — | komercyjny projekt F5, osobny od community ingress-nginx |
| **HAProxy** Kubernetes Ingress | tak | częściowo | gdy firma ma kompetencje HAProxy |
| **Envoy Gateway** | nie | tak | Envoy, projekt Envoy/CNCF |
| **Cilium** | tak | tak | gdy Cilium jest CNI; razem z LB IPAM daje cały stos bez dodatków |
| **Istio** | tak | tak | gdy i tak jest service mesh |

Community **ingress-nginx** (`kubernetes/ingress-nginx`) jest wycofany: koniec utrzymania w marcu 2026, bez poprawek bezpieczeństwa. Spotkasz go w wielu istniejących klastrach on-prem — to dobry moment na migrację, najlepiej od razu na Gateway API.

## EKS a on-prem: ogniwo po ogniwie

| Ogniwo | EKS (`k8s-sages`) | On-prem (przykład) | Kto utrzymuje on-prem |
|---|---|---|---|
| DNS | `*.k8s.marniok.dev` CNAME → NLB | `*.apps.firma.internal` → `10.20.30.200` | zespół DNS / AD |
| Adres wejściowy | nazwa DNS NLB, adresy publiczne AWS | VIP z puli MetalLB albo VIP na HAProxy | sieciowcy + administrator klastra |
| Load balancer | AWS NLB (Service LoadBalancer z adnotacją `nlb`) | MetalLB / kube-vip / Cilium albo F5, HAProxy + keepalived | administrator klastra albo zespół sieci |
| Zapora | security groupy tworzone przez Kubernetesa | firewall, ręczne reguły | sieciowcy |
| Kontroler Ingress | Traefik, ns `traefik` | ten sam Traefik (albo inny z tabeli wyżej) | administrator klastra |
| Certyfikat | cert-manager + Let's Encrypt HTTP-01 | cert-manager + DNS-01 albo firmowe CA | administrator klastra + zespół PKI |
| Service, EndpointSlice, pody | Ty | Ty — bez zmian | zespół aplikacji |

## Lab08 on-prem krok po kroku

Załóżmy klaster on-prem przygotowany przez administratora: MetalLB z pulą, Traefik z adresem `10.20.30.200`, wildcard `*.apps.firma.internal` → ten adres, `ClusterIssuer` `firmowe-ca`.

| Krok lab08 | Na EKS | On-prem | Co się zmienia |
|---|---|---|---|
| 1. Service ClusterIP | `kubectl apply -f …` | to samo | nic |
| 2. EndpointSlice, test z poda | `kubectl get endpointslices …`, `curl http://lab08-web` | to samo | nic |
| 3. Ingress | `host: <login>.k8s.marniok.dev`, `ingressClassName: traefik` | `host: <login>.apps.firma.internal`, `ingressClassName: traefik` | domena; `ADDRESS` pokazuje `10.20.30.200` zamiast nazwy NLB |
| 4. HTTPS | `cert-manager.io/cluster-issuer: letsencrypt-prod` | `cert-manager.io/cluster-issuer: firmowe-ca` | nazwa Issuera; certyfikat od razu, bez `Order` i `Challenge` |
| 5. Dwie ścieżki | `apps-<login>.k8s.marniok.dev` | `apps-<login>.apps.firma.internal` | domena |
| Dla chętnych: NodePort | z laptopa nie działa (węzły bez publicznych IP) | z laptopa w sieci firmowej często działa, jeśli firewall przepuszcza porty 30000–32767 | zależy od sieci, nie od Kubernetesa |
| Service LoadBalancer | osobny LB w AWS po kilku sekundach, płatny | adres z puli MetalLB od razu, bez kosztu, ale pula jest mała | adresy są ograniczonym zasobem |

Krok 3 i 4 on-prem w całości:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: lab08-web
  annotations:
    cert-manager.io/cluster-issuer: firmowe-ca      # na EKS: letsencrypt-prod
spec:
  ingressClassName: traefik
  tls:
  - hosts: [<login>.apps.firma.internal]               # na EKS: <login>.k8s.marniok.dev
    secretName: lab08-web-tls
  rules:
  - host: <login>.apps.firma.internal
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: lab08-web
            port:
              number: 80
```

Sprawdzenie wygląda tak samo, tylko adresy są inne:

```bash
kubectl get ingress lab08-web                     # ADDRESS: 10.20.30.200
dig +short <login>.apps.firma.internal               # 10.20.30.200 (firmowy DNS)
curl -sI https://<login>.apps.firma.internal         # bez -k, jeśli system ufa firmowemu CA
kubectl get svc -n traefik traefik                # EXTERNAL-IP z puli MetalLB
```

Różnica jest w tym, kto i co przygotował wcześniej. Na EKS: wildcard w DNS, Traefik z adnotacją `nlb`, cert-manager z ClusterIssuerem. On-prem: dodatkowo MetalLB (albo zewnętrzny LB), pula adresów uzgodniona z sieciowcami, wpis w firmowym DNS i Issuer dopasowany do firmowego PKI. Obiekty, które piszesz Ty, pozostają przenośne — i o to w Kubernetesie chodzi.

## Diagnoza on-prem

| Objaw | Przyczyna | Co sprawdzić |
|---|---|---|
| `EXTERNAL-IP <pending>` | brak MetalLB/kube-vip, pula wyczerpana, `autoAssign: false` bez adnotacji | `kubectl get ipaddresspool -n metallb-system`, logi controllera MetalLB |
| Adres jest, połączenie wisi | brak `L2Advertisement` dla puli, adres spoza podsieci węzłów, firewall | `kubectl get l2advertisement -n metallb-system`, `arping <VIP>` z innej maszyny |
| Działa, po restarcie węzła przestaje | konflikt IP z DHCP albo innym urządzeniem | uzgodnij pulę z sieciowcami |
| Wszystko wolne przy dużym ruchu (L2) | cały ruch przez jeden węzeł | BGP albo zewnętrzny LB |
| `Could not resolve host` | brak wpisu w firmowym DNS, laptop używa innego DNS (VPN) | `dig +short <host>` z laptopa i z poda |
| Certyfikat nieznanego wystawcy | system nie ufa firmowemu CA | dodaj CA do zaufanych; w `curl` tymczasowo `--cacert ca.crt` |
| Challenge Let's Encrypt `connection timed out` | HTTP-01 na hoście niedostępnym z internetu | DNS-01 albo firmowe CA |

## Linki

- MetalLB: [dokumentacja](https://metallb.io/), [konfiguracja](https://metallb.io/configuration/), [L2 a BGP](https://metallb.io/concepts/)
- [kube-vip](https://kube-vip.io/), [Cilium LB IPAM](https://docs.cilium.io/en/stable/network/lb-ipam/), [Cilium L2 announcements](https://docs.cilium.io/en/stable/network/l2-announcements/), [OpenELB](https://openelb.io/)
- [ExternalDNS](https://kubernetes-sigs.github.io/external-dns/)
- [Gateway API — implementacje](https://gateway-api.sigs.k8s.io/implementations/)
- Kubernetes: [Service type LoadBalancer](https://kubernetes.io/docs/concepts/services-networking/service/#loadbalancer)
