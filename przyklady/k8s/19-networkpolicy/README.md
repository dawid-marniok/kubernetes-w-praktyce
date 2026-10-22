# Przykłady: NetworkPolicy

**Cel:** zamknąć ruch w namespace (deny-all) i otwierać go strzałka po strzałce: DNS, frontend → backend, kontroler Ingress, internet po HTTPS.

**Gdzie:** klaster szkoleniowy EKS, Twój namespace. NetworkPolicy egzekwuje tam vpc-cni (network policy agent). Komendy wydajesz w tym katalogu (`cd przyklady/k8s/19-networkpolicy`).

| Plik | Co robi |
|---|---|
| `default-deny.yaml` | cały namespace: nic nie wchodzi, nic nie wychodzi |
| `allow-dns.yaml` | wszystkie pody mogą pytać kube-dns (UDP/TCP 53) |
| `backend-from-frontend.yaml` | jedna strzałka frontend → backend = ingress backendu + egress frontendu |
| `isolate-namespace.yaml` | wejście tylko z podów z tego samego namespace |
| `egress-https-internet.yaml` | wyjście do internetu po 443 przez `ipBlock` (pody `app: restricted`) |
| `allow-from-ingress-controller.yaml` | wejście z namespace kontrolera Ingress/Gateway (`traefik`) do podów `app: frontend` |

## Krok po kroku

**1. Dwie aplikacje i ruch bez polityk**
```bash
kubectl create deployment backend --image=nginxinc/nginx-unprivileged:1.29 --port=8080
kubectl expose deployment backend --port=80 --target-port=8080
kubectl create deployment frontend --image=nginxinc/nginx-unprivileged:1.29
kubectl wait --for=condition=Available deploy/backend deploy/frontend --timeout=90s
kubectl exec deploy/frontend -- curl -sS -m 3 http://backend | grep title
```
Co powinieneś zobaczyć: `condition met` dla obu Deploymentów (etykiety `app=backend` i `app=frontend` nadaje `kubectl create deployment`, na nie patrzą polityki). `curl` zwraca `<title>Welcome to nginx!</title>`: bez polityk wszystko jest otwarte. Zasoby uzupełni LimitRange namespace'u.

**2. Deny-all**
```bash
kubectl apply -f default-deny.yaml
kubectl exec deploy/frontend -- curl -sS -m 3 http://backend
```
Co powinieneś zobaczyć: `Resolving timed out after 3000 milliseconds`. Pierwsza ofiara deny-all to DNS: frontend nie może nawet zapytać kube-dns.

**3. DNS**
```bash
kubectl apply -f allow-dns.yaml
kubectl exec deploy/frontend -- curl -sS -m 3 http://backend
```
Co powinieneś zobaczyć: `Connection timed out` (albo `Operation timed out`). Nazwa już się rozwiązuje, ale ruch do backendu blokuje polityka.

**4. Frontend → backend**
```bash
kubectl apply -f backend-from-frontend.yaml
kubectl exec deploy/frontend -- curl -sS -m 3 http://backend | grep title
kubectl run t --rm -i --restart=Never --image=busybox:1.37 -- wget -qO- -T 3 http://backend
```
Co powinieneś zobaczyć: z frontendu znów `Welcome to nginx!`. Pod `t` (bez etykiety `app=frontend`) dostaje `download timed out`. W polityce jest port **8080** (kontenera), choć Service słucha na 80.

**5. Wyjście do internetu tylko po HTTPS**
```bash
kubectl apply -f egress-https-internet.yaml
kubectl run r --labels=app=restricted --image=curlimages/curl:8.11.1 -- sleep 3600
kubectl wait --for=condition=Ready pod/r
kubectl exec r -- curl -sS -m 5 -o /dev/null -w '%{http_code}\n' https://example.com
kubectl exec r -- curl -sS -m 5 -o /dev/null -w '%{http_code}\n' http://example.com
kubectl exec deploy/frontend -- curl -sS -m 5 -o /dev/null -w '%{http_code}\n' https://example.com
```
Co powinieneś zobaczyć: z `r` po HTTPS `200`, po HTTP (port 80) `Connection timed out`. Frontend (bez etykiety `app=restricted`) nie wychodzi do internetu wcale: timeout. Jeśli `http://` z `r` zwrócił `200`, powtórz po kilku sekundach: świeży pod przez pierwsze sekundy nie jest jeszcze objęty politykami (vpc-cni dopisuje jego IP z opóźnieniem). Dlatego test z poda, który już działa, a nie z jednorazowego `kubectl run --rm`.

**6. Dla chętnych:** `isolate-namespace.yaml` (wejście tylko z własnego namespace) i `allow-from-ingress-controller.yaml` (bez niej aplikacja za Ingressem po deny-all przestaje odpowiadać z internetu: kontroler Traefik działa w namespace `traefik`). Do sprawdzenia drugiej potrzebujesz Service i Ingressu przed frontendem (krok 1 ich nie tworzy): wzór w [`../06-ingress/`](../06-ingress/), port kontenera 8080.

## Sprzątanie
```bash
kubectl delete -f . --ignore-not-found
kubectl delete pod r
kubectl delete deployment backend frontend
kubectl delete service backend
```

## Uwagi

### Jak to działa
- NetworkPolicy egzekwuje CNI: na EKS vpc-cni z włączonym network policy agent (tak jest na naszym klastrze), poza tym Calico, Cilium, kindnet w kind ≥ v0.24. Flannel przyjmie obiekt i nic nie zablokuje.
- Pod bez żadnej polityki: wszystko otwarte. Pod wybrany przez politykę danego typu: tylko to, co polityki jawnie wpuszczają.
- Polityki się sumują (OR). Nie ma reguł deny.
- `podSelector: {}` = wszystkie pody w namespace. `namespaceSelector: {}` = wszystkie namespace'y (czyli cały klaster, nie internet).
- W jednym elemencie `from`/`to`: `namespaceSelector` + `podSelector` = AND. Jako dwa elementy listy (dwa myślniki) = OR.
- Namespace ma automatycznie etykietę `kubernetes.io/metadata.name: <nazwa>`. Etykiety `name` nie ma, dopóki ktoś jej nie doda.
- Port w polityce to port kontenera, nie port Service.
- Domeny (`api.github.com`) nie zadziałają w zwykłej NetworkPolicy — tylko IP/CIDR. Domeny: Cilium (`toFQDNs`) albo rozwiązania komercyjne.

### Testowanie
```bash
kubectl run t --rm -i --restart=Never --image=busybox:1.37 -- wget -qO- -T 2 http://<service>
kubectl run t --rm -it --restart=Never --image=nicolaka/netshoot:v0.14 -- bash      # curl, dig, nc, tcpdump
kubectl exec deploy/<app> -- curl -sS -m 2 http://<service>                          # obrazy nginx mają curl
kubectl describe networkpolicy <nazwa>
```

Polityki **egress** testuj z poda, który działa już kilka sekund (`kubectl exec`): jednorazowy `kubectl run --rm` startuje, zanim vpc-cni obejmie go politykami, i może przepuścić ruch, który powinien być zablokowany.

| Komunikat | Warstwa |
|---|---|
| `Resolving timed out` / `Could not resolve host` / `bad address` | DNS (brak egress na 53) |
| `Connection timed out` / `download timed out` | polityka |
| `Connection refused` | aplikacja (nic nie słucha na porcie) |
