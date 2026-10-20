# Przykłady z zajęć

Gotowe, działające pliki do tematów ze slajdów: pełne wersje YAML-i i Dockerfile, które na slajdzie są skrócone. Każdy katalog ma własny `README.md` (co jest w środku i jak uruchomić).

Jak z nich korzystać:
- **Na zajęciach:** prowadzący odsyła do pliku, kiedy na slajdzie jest tylko fragment.
- **W labie:** gdy nie wiesz, jak zacząć YAML, otwórz przykład z tego samego tematu, skopiuj i przerób. Lab każe zwykle napisać coś trochę innego niż przykład.
- **Po szkoleniu:** wzorce do własnych projektów.

Manifesty Kubernetesa nie mają `namespace:` (trafiają do Twojego domyślnego) i mają `resources` (w namespace jest quota). Katalogi `k8s/` są ponumerowane w kolejności zajęć (`01-pod` … `22-helm`). Uruchamiasz je z katalogu repo: `kubectl apply -f przyklady/k8s/<katalog>/<plik>.yaml`. Katalogi dochodzą razem z labami danego dnia (`git pull`).

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
