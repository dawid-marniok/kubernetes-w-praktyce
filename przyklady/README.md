# Przykłady z zajęć

Gotowe, działające pliki do tematów ze slajdów: pełne wersje YAML-i i Dockerfile, które na slajdzie są skrócone. Każdy katalog ma własny `README.md` według tego samego wzoru: **Cel**, **Gdzie** (klaster szkoleniowy EKS w Twoim namespace albo lokalny kind), tabela plików, **Krok po kroku** (komendy i to, co powinieneś zobaczyć), **Sprzątanie** i **Uwagi**. Przykład przerobisz sam, bez prowadzącego.

Jak z nich korzystać:
- **Na zajęciach:** prowadzący odsyła do pliku, kiedy na slajdzie jest tylko fragment.
- **W labie:** gdy nie wiesz, jak zacząć YAML, otwórz przykład z tego samego tematu, skopiuj i przerób. Lab każe zwykle napisać coś trochę innego niż przykład.
- **Po szkoleniu:** wzorce do własnych projektów.

Manifesty Kubernetesa nie mają `namespace:` (trafiają do Twojego domyślnego) i mają `resources` (w namespace jest quota). Katalogi `k8s/` są ponumerowane w kolejności zajęć (`01-pod` … `22-helm`). Komendy z README wydajesz w katalogu przykładu (`cd przyklady/k8s/<katalog>`). Nietrywialne pola w YAML-ach mają krótki komentarz: co robią i jakie wartości przyjmują. Katalogi dochodzą razem z labami danego dnia (`git pull`).

| Katalog | Dzień | Temat | Lab | Co jest w środku |
|---|---|---|---|---|
| [`docker/build/`](docker/build/) | 1 | Obrazy i Dockerfile | lab03 | Dockerfile: nginx, Node z cache zależności, .NET multi-stage |
| [`docker/compose/`](docker/compose/) | 1 | Bezpieczeństwo i Compose | lab04 | Compose: nginx, shoppinglist (Flask + PostgreSQL), skalowanie za nginx |
| [`k8s/01-pod/`](k8s/01-pod/) | 2 | Pod i Namespace | lab06 | pod, kilka kontenerów, zmienne, sondy, `restartPolicy`, `command`/`args` kontra Docker |
| [`k8s/02-replicaset/`](k8s/02-replicaset/) | 2 | Deployment i konfiguracja | lab07 | ReplicaSet, pod-sierota, za szeroki selektor |
| [`k8s/03-deployment/`](k8s/03-deployment/) | 2 | Deployment i konfiguracja | lab07 | RollingUpdate, Recreate, sondy i zasoby |
| [`k8s/04-configmap-secret/`](k8s/04-configmap-secret/) | 2 | Deployment i konfiguracja | lab07 | ConfigMap, Secret, Deployment z konfiguracją z zewnątrz |
| [`k8s/05-service/`](k8s/05-service/) | 2 | Service, Ingress, Gateway API | lab08 | ClusterIP, NodePort, LoadBalancer, headless, ExternalName, pusty EndpointSlice |
| [`k8s/06-ingress/`](k8s/06-ingress/) | 2 | Service, Ingress, Gateway API | lab08 | Ingress z hostem, ścieżki, TLS, ClusterIssuer cert-managera |
| [`k8s/07-gateway-api/`](k8s/07-gateway-api/) | 2 | Service, Ingress, Gateway API | lab08 | Gateway, HTTPRoute, canary, rewrite |
| [`k8s/08-storage/`](k8s/08-storage/) | 3 | Storage i StatefulSet | lab09 | PVC, pod z PVC, PostgreSQL na PVC, StorageClass EKS (gp3), PV statyczny EBS/EFS (admin) i kind |
| [`k8s/09-statefulset/`](k8s/09-statefulset/) | 3 | Storage i StatefulSet | lab09 | StatefulSet z headless Service i PVC na pod |
| [`k8s/10-daemonset/`](k8s/10-daemonset/) | 3 | DaemonSet, Job, CronJob | lab10 | agent na każdym węźle, zbieranie logów (kind) |
| [`k8s/11-job-cronjob/`](k8s/11-job-cronjob/) | 3 | DaemonSet, Job, CronJob | lab10 | Job, Job Indexed, CronJob |
| [`k8s/12-zasoby-qos/`](k8s/12-zasoby-qos/) | 3 | Zasoby, QoS, HPA | lab11 | Guaranteed, Burstable, OOMKilled, PriorityClass |
| [`k8s/13-quota-limitrange/`](k8s/13-quota-limitrange/) | 3 | Zasoby, QoS, HPA | lab11 | ResourceQuota, quota z zakresem, LimitRange |
| [`k8s/14-hpa/`](k8s/14-hpa/) | 3 | Zasoby, QoS, HPA | lab11 | HPA `autoscaling/v2`, zachowanie przy skalowaniu, generator ruchu |
| [`k8s/15-affinity-taints/`](k8s/15-affinity-taints/) | 3 | Planowanie i utrzymanie | — | nodeAffinity, pod (anti-)affinity, topologySpread, taint i toleracja; ćwiczenie taint + PDB + drain na kind |
| [`k8s/16-pdb/`](k8s/16-pdb/) | 3 | Planowanie i utrzymanie | — | PodDisruptionBudget i drain węzła (kind) |
