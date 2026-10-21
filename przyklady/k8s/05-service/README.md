# Przykłady: Service

**Cel:** dać podom stałą nazwę i adres w klastrze i zobaczyć, czym różnią się typy Service.

**Gdzie:** klaster szkoleniowy EKS, Twój namespace. Komendy wydajesz w tym katalogu (`cd przyklady/k8s/05-service`).

| Plik | Typ | Co pokazuje |
|---|---|---|
| `clusterip.yaml` | ClusterIP | domyślny, ruch wewnątrz klastra; `targetPort` jako nazwa portu |
| `nodeport.yaml` | NodePort | port na każdym węźle, **bez** sztywnego `nodePort` |
| `loadbalancer.yaml` | LoadBalancer | load balancer AWS (CLB albo NLB); tylko za zgodą prowadzącego (koszt, publiczny adres) |
| `headless.yaml` | headless | `clusterIP: None`, DNS zwraca IP podów |
| `externalname.yaml` | ExternalName | CNAME do nazwy spoza klastra |
| `pusty-endpointslice.yaml` | ClusterIP | selektor bez podów → pusty EndpointSlice |

Wszystkie (poza ExternalName i pustym) wskazują pody z `../03-deployment/deployment-rolling.yaml` (`app: przyklad-deploy`).

## Krok po kroku

**1. Pody i ClusterIP**
```bash
kubectl apply -f ../03-deployment/deployment-rolling.yaml -f clusterip.yaml
kubectl get svc przyklad-deploy
kubectl get endpointslices -l kubernetes.io/service-name=przyklad-deploy
```
Co powinieneś zobaczyć: Service `TYPE ClusterIP` z adresem `CLUSTER-IP` (np. `172.20.x.x`) i `PORT(S) 80/TCP`. W EndpointSlice 3 adresy IP podów i port `80`.

**2. Nazwa w DNS i ruch przez Service**
```bash
kubectl exec deploy/przyklad-deploy -- curl -s http://przyklad-deploy | head -4
kubectl exec deploy/przyklad-deploy -- getent hosts przyklad-deploy
kubectl port-forward svc/przyklad-deploy 8080:80       # http://localhost:8080, Ctrl+C kończy
```
Co powinieneś zobaczyć: początek strony `Welcome to nginx!`. `getent` zwraca adres CLUSTER-IP i pełną nazwę `przyklad-deploy.<namespace>.svc.cluster.local`.

**3. Headless**
```bash
kubectl apply -f headless.yaml
kubectl run dns --rm -it --image=busybox:1.37 --restart=Never -- nslookup przyklad-deploy-headless
```
Co powinieneś zobaczyć: zamiast jednego adresu trzy, po jednym na pod. `kubectl get svc przyklad-deploy-headless` ma `CLUSTER-IP None`.

**4. NodePort**
```bash
kubectl apply -f nodeport.yaml
kubectl get svc przyklad-deploy-np
```
Co powinieneś zobaczyć: `TYPE NodePort`, `PORT(S) 80:3xxxx/TCP`: drugi numer to port otwarty na każdym węźle, wybrany przez klaster. Na EKS węzły są w prywatnej sieci, więc z laptopa przez NodePort nie wejdziesz. Na kind `setup/kind.md` przekierowuje z laptopa porty 30000–30002.

**5. ExternalName i pusty selektor**
```bash
kubectl apply -f externalname.yaml -f pusty-endpointslice.yaml
kubectl get svc przyklad-zewnetrzne-api
kubectl get endpointslices -l kubernetes.io/service-name=przyklad-pusty
kubectl exec deploy/przyklad-deploy -- curl -sS -m 3 http://przyklad-pusty
```
Co powinieneś zobaczyć: `przyklad-zewnetrzne-api` ma `EXTERNAL-IP api.example.com` i nie ma CLUSTER-IP. Pusty EndpointSlice ma `ENDPOINTS <unset>`, a `curl` kończy się błędem połączenia: nazwa się rozwiązuje, ale za Service nie stoi żaden pod. Pierwsza rzecz do sprawdzenia, gdy „Service nie działa”: czy selektor pasuje do etykiet podów.

**6. LoadBalancer (tylko za zgodą prowadzącego)**
```bash
kubectl apply -f loadbalancer.yaml
kubectl get svc przyklad-deploy-lb -w                  # Ctrl+C, gdy pojawi się adres
```
Co powinieneś zobaczyć: `EXTERNAL-IP <pending>`, po 1–2 min nazwa `…elb.amazonaws.com`. Strona odpowiada po kolejnych 1–3 min (DNS i rejestracja węzłów). Jeśli quota namespace'u nie pozwala na load balancery, API odrzuci Service (`exceeded quota: … services.loadbalancers`).

## Sprzątanie
```bash
kubectl delete -f .
kubectl delete -f ../03-deployment/deployment-rolling.yaml
```

## Uwagi
- `kubectl get endpoints` jest wycofane od 1.33 — używaj `endpointslices`.
- W obrazie nginx jest `curl` i `getent`, nie ma `wget` ani `nslookup`.
- `port` to port Service, `targetPort` to port kontenera (liczba albo nazwa portu z poda).
- Na produkcji ruch HTTP z internetu wpuszczasz przez Ingress albo Gateway API (jeden load balancer dla wielu aplikacji), a nie przez osobny LoadBalancer na każdą usługę.
