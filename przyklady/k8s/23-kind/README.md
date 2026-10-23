# Przykłady: kind, Kubernetes na laptopie

**Cel:** postawić lokalny klaster w kilkadziesiąt sekund, zobaczyć, że węzeł to kontener Dockera, wgrać do niego obraz bez rejestru i wrócić na klaster szkoleniowy.

**Gdzie:** lokalnie, Docker Desktop + [kind](https://kind.sigs.k8s.io/) (≥ v0.33, `kind version`). Na szkoleniu pokazuje to prowadzący na początku dnia 5, a Ty pracujesz dalej na EKS. Po szkoleniu tak ćwiczysz bez chmury. Instalacja: [`setup/kind.md`](../../../setup/kind.md), wybór narzędzia i laby lokalnie: [`docs/k8s/lokalnie/`](../../../docs/k8s/lokalnie/README.md).

Plików tu nie ma: wszystko robią komendy `kind`, `docker` i `kubectl`. Klaster wielowęzłowy do labów opisuje `setup/kind/kind-szkolenie.yaml`.

## Krok po kroku

**1. Klaster**
```bash
kind create cluster --name lokalny
docker ps --filter name=lokalny          # węzeł = kontener
kubectl get nodes
```
Co powinieneś zobaczyć: po ok. 40 s `lokalny-control-plane Ready`, a w Docker Desktop (Containers) kontener o tej samej nazwie. Kubernetes IN Docker.

**2. Dwa klastry w jednym kubeconfigu**
```bash
kubectl config get-contexts
kubectl config current-context
```
Co powinieneś zobaczyć: gwiazdkę przy `kind-lokalny`, obok kontekst klastra szkoleniowego (`szkolenie`). `kind create` przełączył kontekst: następne `kubectl apply` poleci na laptop, nie na EKS. To najczęstszy błąd po instalacji lokalnego klastra; kontekst w prompcie (kube-ps1, Starship) chroni przed pomyłką.

**3. Obraz z laptopa bez rejestru**
```bash
docker pull nginx:1.29
kind load docker-image nginx:1.29 --name lokalny
kubectl create deployment web --image=nginx:1.29
kubectl rollout status deployment web
kubectl port-forward deployment/web 8080:80   # Ctrl+C po sprawdzeniu
```
Co powinieneś zobaczyć: `successfully rolled out`, a pod http://localhost:8080 stronę nginx. Na EKS obraz budowałeś z `--platform linux/amd64` i wypychałeś do ECR. Lokalnie `kind load` wgrywa go wprost do węzła, w architekturze laptopa.

**4. Co działa, a czego nie**

Działa: Deployment, Service, ConfigMap, Helm, CRD, RBAC, taints i drain (jesteś adminem klastra). Nie ma: load balancera z chmury (zastępstwo: cloud-provider-kind), kontrolera Ingress (Traefik instalujesz Helmem), ról IAM i dysków EBS. Przepisy: [`docs/k8s/lokalnie/`](../../../docs/k8s/lokalnie/README.md).

## Sprzątanie
```bash
kind delete cluster --name lokalny
kubectl config use-context szkolenie
kubectl get pods                         # znowu klaster szkoleniowy
```

## Uwagi
- Alternatywy: minikube (dodatki jednym poleceniem), k3d (k3s w Dockerze, najlżejszy, Traefik w zestawie), Kubernetes w Docker Desktop i Rancher Desktop (klaster jednym kliknięciem). Porównanie w [`docs/k8s/lokalnie/`](../../../docs/k8s/lokalnie/README.md).
- `kind load` na starszym kind (< v0.33) z węzłem Kubernetes 1.35 nie działa: `brew upgrade kind`.
- Na co dzień: `kind create cluster` w CI (np. GitHub Actions) do testów manifestów i chartów Helm przed wdrożeniem.
- Ćwiczenie z węzłami (taint, PDB, drain), którego nie zrobisz na wspólnym klastrze: [`15-affinity-taints/kind-taint-pdb-drain/`](../15-affinity-taints/kind-taint-pdb-drain/).
