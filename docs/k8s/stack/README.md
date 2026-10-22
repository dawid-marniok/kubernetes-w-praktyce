# Nasz stack: AWS, klaster i ToDos

Przez całe szkolenie budujesz jedną aplikację, ToDos (frontend React z nginx, API w Node.js, MongoDB), i stawiasz ją na coraz pełniejszej platformie. Dzień 1 to Docker na Twoim laptopie i obrazy w Amazon ECR. Od dnia 2 ToDos działa w Twoim namespace na klastrze EKS `k8s-sages` (region `eu-central-1`) i każdego dnia dokładasz do niego to, co poznałeś.

Platformę przygotował trener przed szkoleniem: konto AWS z użytkownikami IAM i rejestrem ECR, sieć VPC z NAT, klaster EKS z trzema węzłami `m6i.xlarge`, dodatki EKS (vpc-cni z NetworkPolicy, kube-proxy, CoreDNS, metrics-server, sterownik EBS CSI), StorageClass `gp3`, Traefik za jednym NLB, DNS `*.k8s.marniok.dev`, cert-manager z ClusterIssuerem `letsencrypt-prod`, a dla każdego kursanta namespace z ResourceQuota, LimitRange i RBAC. Ty tworzysz obrazy i wszystko w swoim namespace.

**Otwórz [`stack.html`](stack.html) w przeglądarce** (dwuklik w Finderze lub Eksploratorze albo `open stack.html`). Znajdziesz tam mapę całości z przełącznikiem dni, opis każdego obiektu (co to jest, po co jest w ToDos, kto go tworzy, jaką komendą go zobaczysz), drogę żądania „dodaj zadanie” od przeglądarki do dysku EBS, drogę obrazu z laptopa do poda i tabelę wszystkich obiektów.

| Dzień | Co dokładamy do ToDos | Z platformy |
|---|---|---|
| 1 · Docker | Compose na laptopie: kontenery `web`, `api`, `mongo`, sieć i wolumen `mongodb_data`; obrazy `todos-api:1.0.0` i `todos-web:1.0.0` w ECR (`<login>/…`) | konto IAM `<login>`, rejestr ECR ze skanem przy push |
| 2 · na klaster | Secret z hasłem do bazy, ConfigMap `todos-config`, Deploymenty i Service `web`, `api`, `mongo` (Mongo bez dysku), Ingress `todos` z TLS pod `todos-<login>.k8s.marniok.dev` | VPC, EKS, węzły, Traefik + NLB, DNS, cert-manager, namespace z quotą i RBAC |
| 3 · dane i zasoby | Mongo jako StatefulSet z headless Service i PVC `data-mongo-0` (gp3 → wolumen EBS), sensowne `requests`/`limits`, HPA dla api (2–5 replik, CPU 70%) | StorageClass `gp3`, EBS CSI, metrics-server |
| 4 · bezpieczeństwo | skan obrazów, ServiceAccount bez tokenu dla każdego składnika, `securityContext` na poziomie `restricted` (bez roota, UID z obrazu, `fsGroup` dla dysku Mongo) sprawdzony etykietami Pod Security na namespace, NetworkPolicy: default-deny dla podów ToDos i łańcuch traefik → web:8080 → api:3001 → mongo:27017 (ToDos · dzień 4; w projekcie default-deny na cały namespace plus reguła dla solvera cert-managera, 8089) | vpc-cni egzekwuje NetworkPolicy |
| 5 · Helm i monitoring | chart Helm `todos` (`values-dev.yaml`, `values-prod.yaml`), release `todos`, metryki i logi Twoich podów w Grafanie; projekt lab20 | Prometheus, Loki, Tempo, Alloy i Grafana w ns `monitoring` |

Czego nie zdążysz w bloku ToDos danego dnia, dokładasz w projekcie końcowym (lab20): jego etapy obejmują wszystkie punkty z tabeli.
