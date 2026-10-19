# Od Dockera do Kubernetesa — repo ćwiczeniowe

Szkolenie Sages „Docker i Kubernetes”, 5 dni. Dzień 1 pracujemy z Dockerem na Twoim laptopie, dni 2–4 na wspólnym klastrze Kubernetes (Amazon EKS), dzień 5 kończymy projektem: aplikacja ToDos z dnia 1 wdrożona na Kubernetesa tak, jak na produkcję.
Każdy temat to krótka teoria, pokaz prowadzącego i lab, który robisz samodzielnie.

## Jak zacząć

1. Przed szkoleniem: Docker Desktop, git i klon tego repo — [`setup/README.md`](setup/README.md), część „Dzień 1”.
2. Rano w dniu 2: `kubectl` i logowanie do klastra kontem AWS z karty dostępowej — [`setup/README.md`](setup/README.md), część „Dni 2–5”.
3. Ćwiczenia z węzłami (taint, drain, etykiety węzłów) robisz na lokalnym klastrze kind — [`setup/kind.md`](setup/kind.md).

Laby z danego dnia pojawiają się w repo rano. Na start każdego dnia:

```bash
git stash          # jeśli masz zmiany w plikach z repo (Twoje nowe pliki zostają)
git pull
git stash pop
```

## Plan

| Dzień | Tematy | Laby |
|---|---|---|
| 1 · Docker | Kontenery i podstawy · Sieci i dane · Obrazy i Dockerfile · Bezpieczeństwo i Compose | [lab01 — Docker: podstawy](labs/lab01-docker-podstawy/) · [lab02 — Sieci i wolumeny](labs/lab02-sieci-wolumeny/) · [lab03 — Dockerfile i rejestr](labs/lab03-dockerfile/) · [lab04 — Compose: ToDos](labs/lab04-compose-todos/) |
| 2 · Kubernetes | Architektura i kubectl · Pod i Namespace · Deployment i konfiguracja · Service, Ingress, Gateway API | [lab05 — kubectl](labs/lab05-kubectl/) · [lab06 — Pod](labs/lab06-pod/) · [lab07 — Deployment, ConfigMap, Secret](labs/lab07-deployment-konfiguracja/) · [lab08 — Service i Ingress](labs/lab08-service-ingress/) |
| 3 · Kubernetes | Storage i StatefulSet · DaemonSet, Job, CronJob · Zasoby, QoS, autoskalowanie · Planowanie podów i utrzymanie | [lab09 — Storage i StatefulSet](labs/lab09-storage-statefulset/) · [lab10 — Job, CronJob, DaemonSet](labs/lab10-job-cronjob-daemonset/) · [lab11 — Zasoby, quota, HPA](labs/lab11-zasoby-quota-hpa/) · [lab12 — Affinity i taints](labs/lab12-affinity-taints/) (kind) |
| 4 · Kubernetes | RBAC i ServiceAccount · Pod Security i admission · Sieć: CNI, NetworkPolicy, DNS · Rozszerzanie API | [lab13 — RBAC](labs/lab13-rbac/) · [lab14 — Skanowanie](labs/lab14-skanowanie/) · [lab15 — NetworkPolicy](labs/lab15-networkpolicy/) · [lab16 — Downward API i CRD](labs/lab16-downward-api-crd/) |
| 5 · Kubernetes | Helm · Operatory · Monitoring i observability · Projekt końcowy ToDos | [lab17 — Helm](labs/lab17-helm/) · [lab18 — Operator CloudNativePG](labs/lab18-operator-cnpg/) · [lab19 — Observability](labs/lab19-observability/) · [lab20 — Projekt ToDos](labs/lab20-projekt-todos/) |

Zajęcia 9:00–17:00, przerwy 10:45–11:00, 13:00–13:45 (obiad) i 15:00–15:15.

## Co jest w repo

| Katalog | Co tam jest |
|---|---|
| [`setup/`](setup/) | przygotowanie laptopa, dostęp do klastra, lokalny klaster kind |
| [`labs/`](labs/) | laby: cel, kroki (podstawowe i dla chętnych), warunek SUKCES, wskazówki |
| [`app/`](app/) | aplikacje do labów, m.in. ToDos (frontend React, API Node.js, MongoDB) |
| [`przyklady/`](przyklady/) | gotowe Dockerfile i manifesty z zajęć (`docker/`, `k8s/`) |
| [`docs/`](docs/) | ściągi do tematów (dochodzą razem z labami danego dnia), np. [podstawy Dockera i komendy](docs/d1-docker-podstawy.md) |

## Zasady na wspólnym klastrze

- Pracujesz w swoim namespace (nazwa = Twój login, `user01` …). Jest ustawiony jako domyślny, więc w labach **nie piszesz `-n`**.
- W namespace jest limit zasobów (ResourceQuota). Kontener bez `resources` dostaje wartości domyślne, ale w labach i tak je wpisujemy.
- Obrazy zawsze z wersją (`nginx:1.29`), nigdy `latest`.
- Plik kubeconfig to Twoje hasło do klastra: nie wrzucaj go do repo ani na czat ogólny.
- Coś nie działa (dostęp, `Forbidden`, pod wisi w `Pending`) — pisz od razu na czacie.
