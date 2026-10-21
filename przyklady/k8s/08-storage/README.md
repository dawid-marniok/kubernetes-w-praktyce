# Przykłady: Storage (PVC, PV, StorageClass)

**Cel:** zamówić dysk przez PVC, zobaczyć, że dane przeżywają restart poda, i zrozumieć, kto w klastrze tworzy PV i StorageClass.

**Gdzie:** kroki 1–4 na klastrze szkoleniowym EKS (Twój namespace), krok 6 na kind. Pliki z dopiskiem „tylko admin” czytasz, nie wgrywasz. Komendy wydajesz w tym katalogu (`cd przyklady/k8s/08-storage`).

| Plik | Co pokazuje | Kto tworzy |
|---|---|---|
| `pvc.yaml` + `pod-z-pvc.yaml` | PVC na domyślnej klasie i pod, który go montuje | kursant |
| `postgres-deployment-pvc.yaml` | `postgres:17` na PVC: dane przeżywają restart poda (`PGDATA` w podkatalogu, `strategy: Recreate`) | kursant |
| `storageclass-eks.yaml` | własna StorageClass na EBS (`ebs.csi.aws.com`), gp3, `Retain`, rozszerzanie, `WaitForFirstConsumer` | tylko admin |
| `pv-statyczny-ebs.yaml` | statyczny PV na istniejącym dysku EBS (`volumeHandle: vol-…`, `nodeAffinity` na strefę) + PVC do niego | PV: admin, PVC: kursant |
| `pv-statyczny-efs.yaml` | statyczny PV na EFS (`ReadWriteMany`, `volumeHandle: fs-…`) + PVC; sterownika EFS nie ma na naszym klastrze | PV: admin, PVC: kursant |
| `pv-statyczny-kind.yaml` | statyczny PV `hostPath` + PVC | kind (jesteś adminem) |

**Kto co tworzy.** PV i StorageClass to zasoby klastrowe. Tworzy je administrator klastra (RBAC na `persistentvolumes` i `storageclasses`). Kursant tworzy tylko PVC w swoim namespace, a dysk dostaje automatycznie z klasy domyślnej albo z PV przygotowanego przez admina.

**StorageClass na naszym klastrze:** domyślna `gp3` (sterownik EBS CSI, dysk EBS w jednej strefie AZ, `ReadWriteOnce`, `reclaimPolicy: Delete`, `WaitForFirstConsumer`). W manifestach aplikacji zwykle nie wpisujesz `storageClassName`, wtedy działa klasa domyślna. Na kind domyślna jest `standard` (local-path).

## Krok po kroku

**1. Jakie klasy ma klaster**
```bash
kubectl get storageclass
```
Co powinieneś zobaczyć: `gp3 (default)` z `PROVISIONER ebs.csi.aws.com`, `RECLAIMPOLICY Delete`, `VOLUMEBINDINGMODE WaitForFirstConsumer`, `ALLOWVOLUMEEXPANSION true`. Obok stara `gp2`, już nie domyślna.

**2. PVC czeka na pod**
```bash
kubectl apply -f pvc.yaml
kubectl get pvc przyklad-pvc
kubectl describe pvc przyklad-pvc | tail -3
```
Co powinieneś zobaczyć: `STATUS Pending`, a w Events `WaitForFirstConsumer … waiting for first consumer to be created before binding`. To nie błąd: dysk EBS powstanie dopiero w strefie AZ węzła, na którym wyląduje pod.

**3. Pod z PVC, dane w /data**
```bash
kubectl apply -f pod-z-pvc.yaml
kubectl get pvc przyklad-pvc -w                 # Ctrl+C po Bound (10–30 s)
kubectl exec przyklad-pod-pvc -- sh -c 'echo hej > /data/plik; ls /data'
kubectl delete pod przyklad-pod-pvc
kubectl apply -f pod-z-pvc.yaml
kubectl exec przyklad-pod-pvc -- cat /data/plik
```
Co powinieneś zobaczyć: PVC przechodzi w `Bound`, w kolumnie `VOLUME` pojawia się `pvc-<uuid>` (PV utworzony automatycznie przez sterownik). W `/data` są `lost+found` (świeży system plików ext4) i `plik`. Po usunięciu i ponownym utworzeniu poda `cat` dalej wypisuje `hej`.

**4. PostgreSQL na PVC**

W drugim terminalu: `kubectl get pods -l app=przyklad-postgres -w`.
```bash
kubectl apply -f postgres-deployment-pvc.yaml
kubectl exec deploy/przyklad-postgres -- ls /var/lib/postgresql/data
kubectl exec deploy/przyklad-postgres -- psql -U demo -d demo -c "create table t(x int); insert into t values (42);"
kubectl delete pod -l app=przyklad-postgres
kubectl exec deploy/przyklad-postgres -- psql -U demo -d demo -c "select * from t;"
```
Co powinieneś zobaczyć: pod `1/1 Running` po kilkunastu sekundach (readiness z `pg_isready`). W katalogu wolumenu `lost+found` i `pgdata`: dlatego `PGDATA` wskazuje podkatalog, bo `initdb` odmawia pracy w niepustym katalogu. Po usunięciu poda Deployment tworzy nowy, który podpina ten sam dysk, i `select` zwraca `42`.

**5. Pliki tylko dla admina: przeczytaj i sprawdź uprawnienia**
```bash
kubectl auth can-i create persistentvolumeclaims    # yes
kubectl auth can-i create persistentvolumes         # no
kubectl auth can-i create storageclasses            # no
kubectl apply -f storageclass-eks.yaml --dry-run=server
```
Co powinieneś zobaczyć: `Forbidden … cannot create resource "storageclasses" … at the cluster scope`. Przejrzyj komentarze w `storageclass-eks.yaml`, `pv-statyczny-ebs.yaml` i `pv-statyczny-efs.yaml`: co ustawia admin (sterownik, `volumeHandle`, strefa, reclaim policy), a co Ty (PVC z `storageClassName: ""`).

**6. Statyczny PV na kind**
```bash
kubectl config use-context kind-szkolenie
kubectl apply -f pv-statyczny-kind.yaml
kubectl get pv,pvc
kubectl delete pvc przyklad-local-pvc
kubectl get pv przyklad-local-pv
kubectl delete pv przyklad-local-pv
kubectl config use-context szkolenie
```
Co powinieneś zobaczyć: PVC `Bound` do `przyklad-local-pv` od razu (statyczny PV, ta sama klasa, rozmiar 2Gi ≥ 1Gi). Po usunięciu PVC PV ma `STATUS Released`: przy `Retain` nic nie jest kasowane, ale PV nie wróci sam do puli. Usuwa go admin.

## Sprzątanie
```bash
kubectl delete -f pod-z-pvc.yaml -f pvc.yaml -f postgres-deployment-pvc.yaml
kubectl get pvc                                     # pusto; dyski EBS znikają razem z PVC (Delete w gp3)
```

## Uwagi
- Tryby dostępu: `ReadWriteOnce` (jeden węzeł, EBS), `ReadWriteMany` (wiele węzłów, EFS/NFS), `ReadOnlyMany`, `ReadWriteOncePod` (jeden pod). EBS nie da RWX.
- Dysk EBS jest w jednej strefie AZ. Pod z takim PVC może potem wystartować tylko na węźle z tej strefy. Gdy w strefie zabraknie miejsca, pod będzie `Pending` (`volume node affinity conflict`).
- `allowVolumeExpansion: true` w klasie: powiększasz PVC, zmieniając `resources.requests.storage` (`kubectl edit pvc`). Zmniejszyć się nie da.
- W innych chmurach to samo robią inne sterowniki CSI: Azure Disk (`disk.csi.azure.com`) i Azure Files (RWX) na AKS, Persistent Disk (`pd.csi.storage.gke.io`) na GKE. PVC w aplikacji wygląda tak samo.
- Więcej: [Storage w Kubernetesie](../../../docs/k8s/storage/storage.html).
