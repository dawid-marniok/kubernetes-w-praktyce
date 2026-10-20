# Ściągi

Teoria do tematów ze slajdów, do czytania w trakcie labów i po szkoleniu. Pliki `.md` czytasz w VS Code (podgląd: Ctrl+Shift+V / Cmd+Shift+V) albo na GitHubie, pliki `.html` otwierasz w przeglądarce (dwuklik w Finderze / Eksploratorze albo `open plik.html`).

Katalogi dochodzą razem z labami danego dnia (`git pull`).

| Katalog | Dzień | Co jest w środku |
|---|---|---|
| [`docker/`](docker/) | 1 | [podstawy Dockera i komendy](docker/podstawy.md), [tmpfs](docker/tmpfs.md) |
| [`k8s/stack/`](k8s/stack/) | 2 | [mapa całego stacku: AWS, klaster i ToDos dzień po dniu](k8s/stack/stack.html) (HTML), [opis](k8s/stack/README.md) |
| [`k8s/podstawy/`](k8s/podstawy/) | 2 | [kubectl: podstawowe komendy z opisem](k8s/podstawy/README.md), [jak działa Kubernetes](k8s/podstawy/jak-dziala-kubernetes.html) (HTML) |
| [`k8s/deployment/`](k8s/deployment/) | 2 | [Deployment od środka: rollout, sondy, strategie](k8s/deployment/README.md), [sondy](k8s/deployment/sondy.md), [strategie wdrożeń](k8s/deployment/strategie-wdrozen.md), [wizualizacja](k8s/deployment/deployment.html) (HTML) |
| [`k8s/ingress-gateway/`](k8s/ingress-gateway/) | 2 | [Service, Ingress, Gateway API](k8s/ingress-gateway/README.md), [cert-manager i TLS](k8s/ingress-gateway/cert-manager.md), [on-prem: co zamiast load balancera chmury](k8s/ingress-gateway/on-prem.md), [diagram ruchu](k8s/ingress-gateway/diagram.html) (HTML) |
| [`k8s/lokalnie/`](k8s/lokalnie/) | 2 | [Kubernetes na laptopie: kind, minikube, k3d i inne](k8s/lokalnie/README.md) |
