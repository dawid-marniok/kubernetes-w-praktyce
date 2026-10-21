# Przykłady: StatefulSet

**Cel:** zobaczyć, że pody StatefulSetu mają stałe nazwy, stałe adresy DNS i każdy własny dysk, który wraca do niego po restarcie.

**Gdzie:** klaster szkoleniowy EKS, Twój namespace (PVC z klasy domyślnej `gp3`). Komendy wydajesz w tym katalogu (`cd przyklady/k8s/09-statefulset`).

| Plik | Co pokazuje |
|---|---|
| `statefulset.yaml` | headless Service + StatefulSet z `volumeClaimTemplates` i `persistentVolumeClaimRetentionPolicy` |

## Krok po kroku

**1. Start po kolei**

W drugim terminalu: `kubectl get pods -l app=przyklad-web -w`.
```bash
kubectl apply -f statefulset.yaml
kubectl get pvc
```
Co powinieneś zobaczyć: `przyklad-web-0` startuje pierwszy, `przyklad-web-1` dopiero, gdy `-0` jest gotowy, potem `-2`. Trzy PVC `www-przyklad-web-0`, `-1`, `-2` w stanie `Bound` (nazwa: `<szablon>-<statefulset>-<numer>`).

**2. Każdy pod ma własne dane i własną nazwę DNS**
```bash
for i in 0 1 2; do kubectl exec przyklad-web-$i -- sh -c "echo pod-$i > /usr/share/nginx/html/index.html"; done
kubectl run dns --rm -it --image=busybox:1.37 --restart=Never -- wget -qO- http://przyklad-web-0.przyklad-web
kubectl run dns --rm -it --image=busybox:1.37 --restart=Never -- wget -qO- http://przyklad-web-2.przyklad-web
```
Co powinieneś zobaczyć: `pod-0` i `pod-2`. Adres `<pod>.<headless-service>` zawsze trafia do konkretnego poda.

**3. Pod wraca z tą samą nazwą i tym samym dyskiem**
```bash
kubectl delete pod przyklad-web-1
kubectl get pods -l app=przyklad-web
kubectl exec przyklad-web-1 -- cat /usr/share/nginx/html/index.html
```
Co powinieneś zobaczyć: nowy pod znów nazywa się `przyklad-web-1` (nie losowo, jak w Deploymencie) i wypisuje `pod-1`: podpiął ten sam PVC.

**4. Skalowanie w dół i w górę**
```bash
kubectl scale statefulset przyklad-web --replicas=1
kubectl get pods,pvc
kubectl scale statefulset przyklad-web --replicas=3
kubectl exec przyklad-web-2 -- cat /usr/share/nginx/html/index.html
```
Co powinieneś zobaczyć: najpierw znika `-2`, potem `-1` (od najwyższego numeru). PVC zostają (`whenScaled: Retain`). Po powrocie do 3 replik `przyklad-web-2` znów ma `pod-2`.

## Sprzątanie
```bash
kubectl delete -f statefulset.yaml
kubectl delete pvc www-przyklad-web-0 www-przyklad-web-1 www-przyklad-web-2
```
Po `kubectl delete statefulset` PVC zostają (`whenDeleted: Retain`): dane są bezpieczne, ale dyski EBS dalej istnieją i kosztują, dopóki nie usuniesz PVC.

## Uwagi
- Dysk EBS jest w jednej strefie AZ. Pod StatefulSetu wraca zawsze w strefę swojego dysku.
- StatefulSet nie robi replikacji danych: każdy pod ma osobny, pusty dysk. Replikację (np. PostgreSQL primary/replica) robi aplikacja albo operator (dzień 5).
- Storage i klasy: `../08-storage/`.
