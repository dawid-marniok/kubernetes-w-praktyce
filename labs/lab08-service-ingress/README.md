# Lab 08 — Twoja aplikacja pod własnym hostem

**Cel:** wystawiasz Deployment przez Service w klastrze, diagnozujesz pusty EndpointSlice, a potem dajesz aplikacji adres z zewnątrz przez Ingress (host, HTTPS z certyfikatem od Let's Encrypt, ścieżki).
Podstawa: kroki 1–4, krok 5 i reszta dla chętnych. Po labie wdrażasz swój ToDos (`labs/todos-dzien2/`).
**Środowisko:** wspólny klaster, Twój namespace. Jeden kontroler Ingress dla wszystkich — dlatego host zawiera Twój login.

**Start:** `cd labs/lab08-service-ingress` i `mkdir -p moje` — tu zapisujesz swoje pliki (katalog `moje/` jest w `.gitignore`).

Pliki startowe w tym katalogu:
| Plik | Do czego |
|---|---|
| `web-deployment.yaml` | Deployment `lab08-web` (3 × `nginx:1.29`, port o nazwie `http`) |
| `ingress-szkielet.yaml` | szkielet Ingressu z miejscami `<…>` do uzupełnienia |
| `apps.yaml` | dwie aplikacje (`lab08-app1` nginx, `lab08-app2` httpd) z Service'ami, strony w `/app1/` i `/app2/` |
| `bluegreen-blue.yaml` | dla chętnych: blue/green — wersja blue (`nginx:1.28`) i Service `lab08-bg` |

**Od trenera na czacie:** domena szkolenia (`<DOMENA>`, np. `k8s.marniok.dev`) i nazwa `ClusterIssuera` (do kroku 4). Klasa Ingress: `traefik` (`kubectl get ingressclass`). Każda nazwa `cokolwiek.<DOMENA>` wskazuje już w DNS na load balancer AWS, za którym stoi Traefik (rekord wildcard), więc Twój host działa bez wpisów w `hosts`. Jak to działa: [`docs/k8s/ingress-gateway/README.md`](../../docs/k8s/ingress-gateway/README.md).

> Na kind (bez klastra szkoleniowego): klasa `traefik`, host `<login>.local` zamiast `<login>.<DOMENA>`, a zamiast DNS port-forward: `kubectl port-forward -n traefik svc/traefik 8080:80` w osobnym terminalu i `curl -H "Host: <login>.local" localhost:8080`. Krok 4 (Let's Encrypt) na kind nie zadziała: Let's Encrypt nie dotrze do Twojego laptopa. Instalację Traefika na kind pokaże trener.

> **Lab robimy na EKS. U Ciebie on-prem?** Twoje polecenia w labie prawie się nie zmienią: ten sam Service, Ingress i adnotacja cert-managera. Zmienia się to, co przygotowuje administrator: adres dla kontrolera daje MetalLB albo kube-vip zamiast load balancera AWS, DNS to wildcard w firmowym DNS, a certyfikaty zwykle wystawia firmowe CA albo Let's Encrypt przez DNS-01. Porównanie ogniwo po ogniwie: [`docs/k8s/ingress-gateway/on-prem.md`](../../docs/k8s/ingress-gateway/on-prem.md), diagram z przełącznikiem EKS / on-prem: [`docs/k8s/ingress-gateway/diagram.html`](../../docs/k8s/ingress-gateway/diagram.html) (otwórz w przeglądarce).

---

## Poziom podstawowy

### Krok 1. Service ClusterIP
```bash
kubectl apply -f web-deployment.yaml
kubectl get pods -l app=lab08-web --show-labels
```
Napisz Service `lab08-web` typu ClusterIP: selektor taki jak etykieta podów, `port: 80`, `targetPort: http` (nazwa portu z kontenera). Szkielet: `kubectl create service clusterip lab08-web --tcp=80:80 --dry-run=client -o yaml > moje/lab08-web-svc.yaml` — sprawdź selektor (kubectl wstawia `app: lab08-web`; czy pasuje do `--show-labels`?) i **zmień `targetPort: 80` na `targetPort: http`**.
```bash
kubectl apply -f moje/lab08-web-svc.yaml
kubectl get svc lab08-web
kubectl port-forward svc/lab08-web 8080:80      # przeglądarka: http://localhost:8080, potem Ctrl-C
```

### Krok 2. EndpointSlice i test z wnętrza klastra
```bash
kubectl get endpointslices -l kubernetes.io/service-name=lab08-web
kubectl exec deploy/lab08-web -- curl -s http://lab08-web | grep title
kubectl exec deploy/lab08-web -- getent hosts lab08-web
```
Teraz zepsuj selektor i obserwuj:
```bash
kubectl patch svc lab08-web -p '{"spec":{"selector":{"app":"zle"}}}'
kubectl get endpointslices -l kubernetes.io/service-name=lab08-web
kubectl exec deploy/lab08-web -- curl -s -m 3 http://lab08-web
```
- Co jest w kolumnie `ENDPOINTS`? Co zwraca curl i po jakim czasie?
- Przywróć: `kubectl apply -f moje/lab08-web-svc.yaml`.

### Krok 3. Ingress z własnym hostem
Skopiuj `ingress-szkielet.yaml` do `moje/lab08-ingress.yaml` i podmień `<login>`, `<DOMENA>` i `<nazwa-service>` (klasa `traefik` jest już wpisana). Bez podmiany `apply` zwróci błąd walidacji — to celowe.
```bash
kubectl apply -f moje/lab08-ingress.yaml
kubectl get ingress                                 # ADDRESS = adres load balancera (po kilku sekundach)
curl -s http://<login>.<DOMENA> | grep title
curl -s -o /dev/null -w '%{http_code}\n' http://nie-ma-takiego-<login>.<DOMENA>
dig +short <login>.<DOMENA>                         # ta sama nazwa load balancera dla każdego hosta
```
- Obie nazwy prowadzą w DNS do tego samego load balancera. Skąd Traefik wie, do którego Service wysłać żądanie?
- Co zwraca kontroler dla hosta, którego nie ma w żadnym Ingressie?
- Otwórz `http://<login>.<DOMENA>` w przeglądarce. Co się stało z `http://` i dlaczego przeglądarka ostrzega o certyfikacie? (Podpowiedź: domena `.dev` i HSTS. Naprawisz to w kroku 4.)

### Krok 4. HTTPS z certyfikatem od Let's Encrypt
Certyfikatu nie generujesz sam. Dopisujesz do Ingressu dwie rzeczy, a cert-manager w klastrze zamawia certyfikat w Let's Encrypt i zapisuje go w Secrecie:
- w `metadata.annotations`: `cert-manager.io/cluster-issuer: <ClusterIssuer od trenera>`,
- w `spec`: sekcję `tls` z `hosts: [<login>.<DOMENA>]` (ten sam host co w `rules`) i `secretName: lab08-web-tls`.

Wzór: [`przyklady/k8s/06-ingress/ingress-tls.yaml`](../../przyklady/k8s/06-ingress/ingress-tls.yaml).
```bash
kubectl apply -f moje/lab08-ingress.yaml
kubectl get certificate,order,challenge -w          # zwykle 30–90 s do READY True, potem Ctrl-C
kubectl describe certificate lab08-web-tls          # Events: kto co utworzył
kubectl get secret lab08-web-tls                    # typ kubernetes.io/tls
curl -sI https://<login>.<DOMENA> | head -1         # 200, bez -k
openssl s_client -connect <login>.<DOMENA>:443 -servername <login>.<DOMENA> </dev/null 2>/dev/null | openssl x509 -noout -subject -issuer -dates
```
- Kto utworzył obiekt `Certificate`? Ty go nie pisałeś.
- W trakcie `challenge` w Twoim namespace pojawia się na chwilę dodatkowy pod i Ingress (`kubectl get pods,ingress`). Do czego służą i kto się z nimi łączy?
- Kto wystawił certyfikat i do kiedy jest ważny? Co się stanie, gdy zacznie wygasać?

### Krok 5 (dla chętnych). Dwie aplikacje, dwie ścieżki
```bash
kubectl apply -f apps.yaml
kubectl get pods,svc -l 'app in (lab08-app1,lab08-app2)'
```
Napisz Ingress `lab08-apps` (`ingressClassName: traefik`) dla hosta `apps-<login>.<DOMENA>`: `/app1` → Service `lab08-app1`, `/app2` → Service `lab08-app2` (oba port 80, `pathType: Prefix`).
```bash
curl -s http://apps-<login>.<DOMENA>/app1/
curl -s http://apps-<login>.<DOMENA>/app2/
curl -s -o /dev/null -w '%{http_code}\n' http://apps-<login>.<DOMENA>/
```

**SUKCES:** `https://<login>.<DOMENA>` otwiera się w przeglądarce bez ostrzeżenia, a certyfikat wystawił Let's Encrypt. Dla chętnych: `/app1/` zwraca „app1 · nginx”, a `/app2/` „app2 · httpd”.

---

## Dla chętnych

1. **Skalowanie do zera.** `kubectl scale deploy lab08-web --replicas=0`, potem curl z kroku 3 i `get endpointslices`. Jaki kod i jaki tekst zwraca Traefik? Przywróć 3 repliki.
2. **NodePort bez sztywnego portu.** Service `lab08-web-np` typu NodePort **bez** pola `nodePort` (klaster wybierze wolny port). Odczytaj port z `kubectl get svc lab08-web-np` i sprawdź z wnętrza klastra:
   ```bash
   kubectl get nodes -o wide                                   # INTERNAL-IP
   kubectl exec deploy/lab08-web -- curl -s -o /dev/null -w '%{http_code}\n' http://<INTERNAL-IP>:<NODEPORT>
   ```
   Dlaczego na wspólnym klastrze nie wpisujemy `nodePort: 30036` na sztywno?
3. **Blue/green przez selektor Service.** Dwie wersje działają obok siebie, a ruch przełączasz jednym polem w Service. Opis strategii: [`docs/k8s/deployment/strategie-wdrozen.md`](../../docs/k8s/deployment/strategie-wdrozen.md).
   1. Wersja blue i Service. Wersję rozpoznasz po nagłówku `Server` (`nginx/1.28.x` albo `nginx/1.29.x`):
      ```bash
      kubectl apply -f bluegreen-blue.yaml
      kubectl get pods -l app=lab08-bg -L version
      kubectl exec deploy/lab08-web -- curl -sI http://lab08-bg | grep Server
      ```
   2. Skopiuj Deployment z `bluegreen-blue.yaml` do `moje/lab08-bg-green.yaml` (bez Service) i zmień: nazwę na `lab08-bg-green`, `version: blue` na `version: green` (we **wszystkich trzech** miejscach), obraz na `nginx:1.29`. Zastosuj i przetestuj green **bezpośrednio**, zanim dostanie ruch:
      ```bash
      kubectl apply -f moje/lab08-bg-green.yaml
      kubectl get pods -l app=lab08-bg -L version                # 2 × blue, 2 × green, wszystkie 1/1
      kubectl port-forward deploy/lab08-bg-green 8082:80         # drugi terminal: curl -sI localhost:8082 | grep Server
      kubectl exec deploy/lab08-web -- curl -sI http://lab08-bg | grep Server    # Service dalej odpowiada 1.28
      ```
   3. W drugim terminalu uruchom pętlę, która co sekundę pyta Service, i w pierwszym przełącz ruch:
      ```bash
      # terminal 2:
      kubectl exec deploy/lab08-web -- sh -c 'for i in $(seq 40); do curl -sI -m 2 http://lab08-bg | grep Server || echo BLAD; sleep 1; done'
      # terminal 1:
      kubectl patch svc lab08-bg -p '{"spec":{"selector":{"app":"lab08-bg","version":"green"}}}'
      kubectl get endpointslices -l kubernetes.io/service-name=lab08-bg
      ```
   4. Rollback: ten sam `patch` z `"version":"blue"`. Pętla z terminala 2 pokazuje, kiedy wraca `1.28`.
   - Czy w pętli pojawił się `BLAD` albo mieszanka wersji? Ile trwało przełączenie?
   - Ile podów `lab08-bg` działało przez całe ćwiczenie, a ile działałoby przy RollingUpdate z `maxSurge: 1`? Co to oznacza przy ResourceQuota?
   - Czym różni się ten rollback od `kubectl rollout undo`?
   - Przy `exceeded quota` zmniejsz `lab08-web` do 1 repliki: `kubectl scale deploy lab08-web --replicas=1` (pętla potrzebuje tylko jednego poda `lab08-web`).

---

## Wskazówki

**Gotowe wzorce manifestów:** [`przyklady/k8s/05-service/`](../../przyklady/k8s/05-service/), [`przyklady/k8s/06-ingress/`](../../przyklady/k8s/06-ingress/), [`przyklady/k8s/07-gateway-api/`](../../przyklady/k8s/07-gateway-api/). Skopiuj i przerób, zamiast pisać YAML od zera.

- Droga ruchu od końca: pody `Ready`? → `endpointslices` → `describe svc` (selektor, targetPort) → `describe ingress` (klasa, host, backend).
- Ingress bez `ADDRESS` na klastrze szkoleniowym → zła `ingressClassName` (ma być `traefik`); `kubectl describe ingress`. Na kind kolumna `ADDRESS` zostaje pusta — to normalne, ruch idzie przez port-forward.
- 404 od kontrolera → inny host w curl niż w Ingressie albo ścieżka, której nie ma w regułach.
- Certyfikat długo `READY False` → `kubectl describe challenge`. Najczęściej literówka w hoście albo host w `tls` inny niż w `rules`. Nie usuwaj i nie twórz Ingressu z Secretem w kółko: Let's Encrypt ma limit wystawień na domenę (wspólny dla całej grupy).
- Przeglądarka ostrzega, certyfikat `TRAEFIK DEFAULT CERT` → Ingress bez sekcji `tls` albo certyfikat jeszcze się nie wystawił.
- Host tylko jeden poziom pod domeną: `apps-<login>.<DOMENA>` działa, `apps.<login>.<DOMENA>` nie (DNS wildcard i certyfikat obejmują jeden poziom).
- 503 → Service bez gotowych podów (selektor, readiness). Sondy: [`docs/k8s/deployment/sondy.md`](../../docs/k8s/deployment/sondy.md).
- `curl …/app1` bez ukośnika zwraca `301` na `http://apps-<login>.<DOMENA>/app1/` (nginx dopisuje `/` do katalogu) — używaj `/app1/` albo `curl -L`.
- `kubectl get endpoints` jest wycofane (ostrzeżenie od 1.33) — używaj `endpointslices`.
- W obrazie nginx jest `curl` i `getent`, nie ma `wget` ani `nslookup`.
- Service typu LoadBalancer tworzy osobny load balancer AWS (i rachunek) — na wspólnym klastrze nie tworzymy; wszyscy wchodzą przez jeden Traefik.
- Gateway API (Gateway + HTTPRoute) pokazuje prowadzący w demie; w labie ćwiczysz Ingress. Manifesty i porównanie z Ingressem: [`przyklady/k8s/07-gateway-api/`](../../przyklady/k8s/07-gateway-api/).

## Sprzątanie
```bash
kubectl delete -f apps.yaml -f web-deployment.yaml
kubectl delete svc lab08-web lab08-web-np --ignore-not-found
kubectl delete -f bluegreen-blue.yaml --ignore-not-found
kubectl delete deploy lab08-bg-green --ignore-not-found
kubectl delete ingress lab08-web lab08-apps --ignore-not-found
kubectl delete secret lab08-web-tls --ignore-not-found
```
