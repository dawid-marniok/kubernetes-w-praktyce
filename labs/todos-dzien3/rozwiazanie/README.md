# ToDos · dzień 3 — rozwiązanie

Jedno z możliwych rozwiązań. Twoje może wyglądać inaczej (inne wartości `resources`, inna godzina backupu, backup do logu zamiast na PVC) i też jest dobre, jeśli spełnia wymagania z [`../README.md`](../README.md).

| Plik | Co w nim jest | Zmiana od wczoraj |
|---|---|---|
| `mongo.yaml` | headless Service `mongo` i StatefulSet `mongo`: PVC `data-mongo-0` (1Gi, domyślna klasa) w `/data/db`, QoS `Guaranteed` | nowy (zamiast Deploymentu) |
| `api.yaml` | Deployment i Service `api`, `requests.cpu: 50m` | bez pola `replicas` |
| `hpa.yaml` | HPA `api`: `autoscaling/v2`, 2–4 repliki, 60% CPU | nowy |
| `backup.yaml` | (\*) PVC `todos-backup` i CronJob `mongo-backup`: `mongodump` co dobę o 2:00, 7 ostatnich archiwów | nowy |
| `web.yaml`, `configmap.yaml`, `ingress.yaml` | jak wczoraj, dla kompletu | bez zmian |

Secret `todos-mongo` z wczoraj zostaje bez zmian (nie ma pliku, bo hasło nie powinno trafić do repo).

## Wdrożenie

W `api.yaml` podmień `<REJESTR>`. Potem w tej kolejności:

```bash
kubectl delete deploy mongo             # wczorajsza baza bez dysku; zadania przepadną
kubectl delete svc mongo                # Service ClusterIP nie da się zmienić na headless
kubectl apply -f mongo.yaml
kubectl get pods,pvc -w                 # data-mongo-0 Pending → Bound, mongo-0 0/1 → 1/1, Ctrl-C
kubectl apply -f api.yaml -f hpa.yaml
kubectl get hpa api                     # po minucie TARGETS z liczbą
kubectl apply -f backup.yaml            # (*) opcjonalnie
```

api nie trzeba restartować: łączy się z nowym `mongo-0` samo, w ciągu kilkunastu sekund.

## Ile to zajmuje z quoty

| | requests CPU / pamięć | limits CPU / pamięć |
|---|---|---|
| mongo (1 pod, Guaranteed) | 300m / 512Mi | 300m / 512Mi |
| api, 2 pody (minimum HPA) | 100m / 192Mi | 600m / 512Mi |
| api, 4 pody (maksimum HPA) | 200m / 384Mi | 1200m / 1Gi |
| web, 2 pody | 50m / 64Mi | 200m / 128Mi |
| **Razem przy 4 podach api** | **550m / 960Mi** | **1700m / 1664Mi** |
| Quota w namespace (Hard) | 1 / 2Gi | 3 / 4Gi |

Do tego 2 PVC (2Gi) z 6 PVC i 30Gi. Zostaje zapas na generator ruchu (50m / 64Mi z LimitRange) i na Job backupu (50m / 128Mi).

## Dlaczego tak

- **StatefulSet, a nie Deployment z PVC.** Przy jednej replice oba działają. StatefulSet daje stałą nazwę `mongo-0`, PVC z szablonu przypięty do tej nazwy i pewność, że nigdy nie będą działać dwa pody bazy z tym samym dyskiem (Deployment potrzebował do tego `strategy: Recreate`).
- **Headless Service `mongo`.** Nazwa `mongo` dalej działa w adresie bazy (DNS zwraca adres poda), a do tego jest `mongo-0.mongo`. Bez `serviceName` StatefulSet się utworzy, ale bez rekordów DNS per pod.
- **Bez `storageClassName`.** PVC dostaje domyślną klasę klastra (na EKS `gp3`, na kind `standard`). Ten sam plik działa w obu miejscach.
- **PVC zostaje po usunięciu StatefulSetu.** Celowo: `kubectl delete sts mongo` nie kasuje danych. Pełne usunięcie bazy to `kubectl delete sts mongo` i `kubectl delete pvc data-mongo-0`.
- **Mongo `Guaranteed`.** Przy braku pamięci na węźle kubelet wyrzuca najpierw pody, które zużywają ponad swoje requesty. Baza z requests = limits idzie na końcu.
- **`requests.cpu: 50m` w api.** HPA liczy procent od requestu: 60% to ok. 30m na pod. Za duży request = HPA nigdy nie zareaguje, brak requestu = `<unknown>`.
- **Brak `replicas` w Deploymencie api.** Z `replicas: 2` w pliku każdy `kubectl apply` ustawiałby 2 repliki, choć HPA chciał 4. Pierwszy `apply` po usunięciu pola na chwilę zostawia 1 replikę, HPA wraca do 2 w kilkanaście sekund.
- **Backup na osobnym PVC.** Archiwum na dysku bazy zginęłoby razem z nim. `concurrencyPolicy: Forbid`, bo dwa `mongodump` naraz tylko obciążają bazę. To dalej ten sam wolumen EBS w tej samej strefie, więc na produkcji kopia idzie poza klaster (np. do S3).

## Sprzątanie (dopiero po szkoleniu)

```bash
kubectl delete -f .                     # Deploymenty, StatefulSet, Service, HPA, CronJob, Ingress
kubectl delete pvc data-mongo-0 todos-backup
kubectl delete secret todos-mongo
```
