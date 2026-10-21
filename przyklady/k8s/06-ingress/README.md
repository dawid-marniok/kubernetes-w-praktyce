# Przykłady: Ingress

**Cel:** wystawić aplikację pod własnym hostem przez wspólny kontroler Ingress (Traefik), z kilkoma ścieżkami i z certyfikatem TLS od Let's Encrypt.

**Gdzie:** klaster szkoleniowy EKS, Twój namespace. Komendy wydajesz w tym katalogu (`cd przyklady/k8s/06-ingress`).

| Plik | Co pokazuje |
|---|---|
| `ingress.yaml` | host → Service; host z Twoim loginem do uzupełnienia |
| `ingress-sciezki.yaml` | jeden host, dwie ścieżki (`Prefix`) |
| `ingress-tls.yaml` | TLS z cert-managera (Let's Encrypt): adnotacja + sekcja `tls`; wariant z własnym Secretem w komentarzu |
| `cluster-issuer.yaml` | cert-manager + Let's Encrypt (produkcja, staging w komentarzu), solver HTTP-01 — obiekt klastrowy, tworzy administrator |

Miejsca `<…>` są celowo niepoprawne — `kubectl apply` bez ich podmiany kończy się błędem walidacji. Poniżej podmieniasz je w locie przez `sed`. Ustaw raz w terminalu:
```bash
LOGIN=user07                  # Twój login
DOMENA=k8s.marniok.dev        # domena szkolenia (od prowadzącego)
```

## Krok po kroku

**1. Kontroler i backend**
```bash
kubectl get ingressclass
kubectl get clusterissuer
kubectl apply -f ../03-deployment/deployment-rolling.yaml -f ../05-service/clusterip.yaml
```
Co powinieneś zobaczyć: klasa `traefik` (kontroler `traefik.io/ingress-controller`), ClusterIssuer `letsencrypt-prod` z `READY True`, Deployment `przyklad-deploy` i Service o tej samej nazwie.

**2. Ingress z hostem**
```bash
sed "s/<login>/$LOGIN/g; s/<DOMENA>/$DOMENA/g" ingress.yaml | kubectl apply -f -
kubectl get ingress przyklad-ingress
curl -s http://$LOGIN.$DOMENA | grep title
```
Co powinieneś zobaczyć: `CLASS traefik`, `HOSTS user07.k8s.marniok.dev`, w `ADDRESS` nazwa load balancera AWS. `curl` zwraca `<title>Welcome to nginx!</title>`. DNS wildcard `*.k8s.marniok.dev` wskazuje na load balancer Traefika, Traefik po nagłówku `Host` wybiera Twój Ingress.

**3. TLS z cert-managerem**
```bash
kubectl delete ingress przyklad-ingress                # ten sam host co w ingress-tls.yaml
sed "s/<login>/$LOGIN/g; s/<DOMENA>/$DOMENA/g" ingress-tls.yaml | kubectl apply -f -
kubectl get certificate -w                             # Ctrl+C po READY True (ok. minuty)
curl -sv https://$LOGIN.$DOMENA 2>&1 | grep -E 'issuer|title'
```
Co powinieneś zobaczyć: Certificate `przyklad-tls` przechodzi z `READY False` w `True`. Jeśli długo stoi, zajrzyj w `kubectl get order,challenge` i `kubectl describe challenge`. `curl` pokazuje wystawcę `Let's Encrypt` i stronę nginx. Secret `przyklad-tls` (`kubectl get secret przyklad-tls`) utworzył cert-manager.

**4. Dwie ścieżki na jednym hoście**
```bash
kubectl create deployment app1 --image=traefik/whoami:v1.11.0
kubectl create deployment app2 --image=traefik/whoami:v1.11.0
kubectl expose deployment app1 --port=80
kubectl expose deployment app2 --port=80
sed "s/<login>/$LOGIN/g; s/<DOMENA>/$DOMENA/g" ingress-sciezki.yaml | kubectl apply -f -
curl -s http://apps-$LOGIN.$DOMENA/app1 | grep -E 'Hostname|GET'
curl -s http://apps-$LOGIN.$DOMENA/app2 | grep -E 'Hostname|GET'
```
Co powinieneś zobaczyć: `/app1` odpowiada pod `app1-…`, `/app2` pod `app2-…`. W obu `GET /app1 …` / `GET /app2 …`: kontroler przekazuje ścieżkę bez zmian, więc aplikacja musi umieć obsłużyć prefiks. Przepisanie ścieżki w standardzie ma Gateway API (`../07-gateway-api/httproute-rewrite.yaml`). Zasoby dla `app1`/`app2` uzupełni LimitRange namespace'u.

## Sprzątanie
```bash
kubectl delete ingress przyklad-tls przyklad-sciezki --ignore-not-found
kubectl delete secret przyklad-tls --ignore-not-found
kubectl delete deployment,service app1 app2
kubectl delete -f ../05-service/clusterip.yaml -f ../03-deployment/deployment-rolling.yaml
```

## Uwagi

| Środowisko | Klasa | Host | Jak wejść |
|---|---|---|---|
| klaster szkoleniowy (EKS) | `traefik` | `<login>.<DOMENA>` (DNS wildcard → load balancer Traefika) | `curl http://<login>.<DOMENA>`, przeglądarka: `https://` z cert-managerem |
| kind z Traefikiem | `traefik` | `<login>.local` | `kubectl port-forward -n traefik svc/traefik 8080:80`, `curl -H "Host: <login>.local" localhost:8080` |

- Host tylko jeden poziom pod domeną: `apps-<login>.<DOMENA>`, nie `apps.<login>.<DOMENA>` (wildcard DNS i certyfikaty obejmują jeden poziom). Więcej: [`docs/k8s/ingress-gateway/README.md`](../../../docs/k8s/ingress-gateway/README.md).
- API `networking.k8s.io/v1` (Ingress) jest stabilne i zostaje. `extensions/v1beta1` i `networking.k8s.io/v1beta1` nie istnieją od 1.22.
- Community **ingress-nginx** (kubernetes/ingress-nginx) jest wycofany: koniec utrzymania 03.2026, bez poprawek bezpieczeństwa. Adnotacja `configuration-snippet` jest w nim domyślnie wyłączona od CVE-2025-1974. Nowe projekty: Gateway API (`../07-gateway-api/`).
- Wszystko poza hostem, ścieżką i TLS (rewrite, przekierowania, limity) to adnotacje konkretnego kontrolera — przy zmianie kontrolera do przepisania.
- `pathType: ImplementationSpecific` zależy od kontrolera — unikaj.
