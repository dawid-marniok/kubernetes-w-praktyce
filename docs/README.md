# Ściągi

Teoria do tematów ze slajdów, do czytania w trakcie labów i po szkoleniu. Pliki `.md` czytasz w VS Code (podgląd: Ctrl+Shift+V / Cmd+Shift+V) albo na GitHubie, pliki `.html` otwierasz w przeglądarce (dwuklik w Finderze / Eksploratorze albo `open plik.html`).

Katalogi dochodzą razem z labami danego dnia (`git pull`).

Gdzie śledzić DevOps, AI w DevOps i Kubernetesa po szkoleniu: [zrodla.md](zrodla.md).

| Katalog | Dzień | Co jest w środku |
|---|---|---|
| [`docker/`](docker/) | 1 | [podstawy Dockera i komendy](docker/podstawy.md), [tmpfs](docker/tmpfs.md) |
| [`k8s/stack/`](k8s/stack/) | 2 | [mapa całego stacku: AWS, klaster i ToDos dzień po dniu](k8s/stack/stack.html) (HTML), [opis](k8s/stack/README.md) |
| [`k8s/podstawy/`](k8s/podstawy/) | 2 | [kubectl: podstawowe komendy z opisem](k8s/podstawy/README.md), [jak działa Kubernetes](k8s/podstawy/jak-dziala-kubernetes.html) (HTML) |
| [`k8s/deployment/`](k8s/deployment/) | 2 | [Deployment od środka: rollout, sondy, strategie](k8s/deployment/README.md), [sondy](k8s/deployment/sondy.md), [strategie wdrożeń](k8s/deployment/strategie-wdrozen.md), [wizualizacja](k8s/deployment/deployment.html) (HTML) |
| [`k8s/ingress-gateway/`](k8s/ingress-gateway/) | 2 | [Service, Ingress, Gateway API](k8s/ingress-gateway/README.md) (z tabelą [kiedy Ingress, kiedy Gateway API](k8s/ingress-gateway/README.md#kiedy-ingress-kiedy-gateway-api)), [cert-manager i TLS](k8s/ingress-gateway/cert-manager.md), [on-prem: co zamiast load balancera chmury](k8s/ingress-gateway/on-prem.md), [diagram ruchu](k8s/ingress-gateway/diagram.html) (HTML), [canary w Gateway API: jak wagi dzielą ruch](k8s/ingress-gateway/canary.html) (HTML) |
| [`k8s/rejestr/`](k8s/rejestr/) | 2 | [skąd klaster ma dostęp do ECR i kiedy potrzebny jest Secret docker-registry](k8s/rejestr/ecr.html) (HTML) |
| [`k8s/lokalnie/`](k8s/lokalnie/) | 2, 5 | [Kubernetes na laptopie: kind, minikube, k3d i inne](k8s/lokalnie/README.md) |
| [`k8s/storage/`](k8s/storage/) | 3 | [PVC, PV i StorageClass, rodzaje klas, statyczne PV](k8s/storage/README.md), [wizualizacja](k8s/storage/storage.html) (HTML) |
| [`k8s/autoskalowanie/`](k8s/autoskalowanie/) | 3 | [HPA, VPA, KEDA (też po metryce z Prometheusa), in-place resize i skalowanie węzłów](k8s/autoskalowanie/README.md), [diagramy i symulator HPA](k8s/autoskalowanie/autoskalowanie.html) (HTML) |
| [`k8s/planowanie/`](k8s/planowanie/) | 3 | [scheduler, affinity, taints, PDB, cordon i drain](k8s/planowanie/README.md), [symulacje](k8s/planowanie/planowanie.html) (HTML) |
| [`k8s/rbac/`](k8s/rbac/) | 4 | [RBAC, ServiceAccount, użytkownik z certyfikatem](k8s/rbac/README.md), [droga żądania, symulator can-i, ServiceAccount](k8s/rbac/rbac.html) (HTML), [jak klaster wie, kim jesteś: zwykły Kubernetes a EKS](k8s/rbac/uwierzytelnianie.html) (HTML) |
| [`k8s/bezpieczenstwo/`](k8s/bezpieczenstwo/) | 4 | [bezpieczeństwo i sieć](k8s/bezpieczenstwo/README.md) |
| [`k8s/crd/`](k8s/crd/) | 4 | [CRD: własny typ w API, kontroler i operator](k8s/crd/README.md) (z [wersjami API: alpha, beta, v1](k8s/crd/README.md#wersje-api-alpha-beta-v1)), [jak działa CRD: diagramy i symulator](k8s/crd/crd.html) (HTML) |
| [`k8s/helm/`](k8s/helm/) | 5 | [składnia szablonów Helm](k8s/helm/skladnia.md) |
| [`k8s/gitops/`](k8s/gitops/) | 5 | [GitOps z Argo CD a zwykły pipeline: push i pull, drift, plusy i minusy](k8s/gitops/README.md), [model push i pull krok po kroku, symulator driftu, obiekt Application](k8s/gitops/gitops.html) (HTML) |
| [`k8s/sekrety/`](k8s/sekrety/) | 5 | [sekrety z sejfu: External Secrets, Secrets Store CSI, Sealed Secrets, Key Vault i Secrets Manager](k8s/sekrety/README.md) |
| [`k8s/observability/`](k8s/observability/) | 5 | [metryki, logi, trace'y i instrumentacja OpenTelemetry](k8s/observability/README.md), [architektura stosu, droga żądania ToDos, instalacja i ściąga zapytań](k8s/observability/observability.html) (HTML), [aplikacja Kantyna](k8s/observability/stos-i-kantyna.html) (HTML) |
| [`prezentacja/`](prezentacja/) | 1–5 | slajdy w PDF: [dzień 1](prezentacja/Docker-K8s-D1.pdf), [dzień 2](prezentacja/Docker-K8s-D2.pdf), [dzień 3](prezentacja/Docker-K8s-D3.pdf), [dzień 4](prezentacja/Docker-K8s-D4.pdf), [dzień 5](prezentacja/Docker-K8s-D5.pdf) |
