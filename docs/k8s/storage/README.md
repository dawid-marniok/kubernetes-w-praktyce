# Dzień 3 — ściąga: dyski (PVC, PV, StorageClass)

**Wizualizacja:** [storage.html](storage.html) — otwórz plik w przeglądarce (dwuklik albo `open storage.html`). Jest tam animacja krok po kroku: od PVC do dysku EBS zamontowanego w kontenerze, z tym, co w danym momencie pokazuje `kubectl get`.

Gotowe manifesty: `przyklady/k8s/08-storage/` (PVC, pod z PVC, Postgres na PVC), `przyklady/k8s/09-statefulset/`. Ćwiczysz w [d3-lab09-storage-statefulset](../../../labs/d3-lab09-storage-statefulset/).

Nasz klaster: EKS `k8s-sages` w `eu-central-1`, 3 węzły w 3 strefach (AZ), domyślna klasa `gp3` (sterownik EBS CSI `ebs.csi.aws.com`, dodatek EKS). Ty tworzysz PVC w swoim namespace. PV i StorageClass tylko czytasz.

## Po co dysk

System plików kontenera znika razem z kontenerem. Restart po awarii, nowy pod z ReplicaSetu, przeniesienie na inny węzeł: za każdym razem startujesz od czystego obrazu.

| Gdzie zapisujesz | Restart kontenera | Usunięcie poda | Pod na innym węźle | Do czego |
|---|---|---|---|---|
| system plików kontenera | ginie | ginie | ginie | pliki tymczasowe |
| `emptyDir` | zostaje | ginie | ginie | cache, wymiana plików między kontenerami poda |
| `hostPath` | zostaje | zostaje na tym węźle | brak danych | tylko agenci systemowi, nie aplikacje |
| **PVC** | zostaje | zostaje | dysk idzie za podem (EBS: w tej samej AZ) | bazy, pliki użytkowników |

## Trzy obiekty

| Obiekt | Co to jest | Zasięg | Kto tworzy |
|---|---|---|---|
| **PersistentVolumeClaim** (`pvc`) | zamówienie: rozmiar, tryb dostępu, klasa | namespace | Ty |
| **PersistentVolume** (`pv`) | konkretny dysk: ID wolumenu, strefa, `reclaimPolicy` | cały klaster | sterownik CSI (dynamicznie) albo admin (statycznie) |
| **StorageClass** (`sc`) | przepis: sterownik, parametry, `volumeBindingMode` | cały klaster | admin |

PVC i PV łączą się parami (1:1), stan `Bound`. Pod odwołuje się tylko do PVC: `volumes[].persistentVolumeClaim.claimName`.

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: dane
spec:
  accessModes: [ReadWriteOnce]
  resources:
    requests:
      storage: 10Gi
  # storageClassName pominięte = gp3 (domyślna)
```

Klasa gp3 na naszym klastrze:

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: gp3
  annotations:
    storageclass.kubernetes.io/is-default-class: "true"
provisioner: ebs.csi.aws.com
parameters:
  type: gp3
  fsType: ext4
volumeBindingMode: WaitForFirstConsumer
allowVolumeExpansion: true
reclaimPolicy: Delete
```

## Dynamiczne tworzenie dysku krok po kroku

1. **PVC.** Bez `storageClassName` admission wpisuje domyślną `gp3`. PVC jest `Pending`, zdarzenie `WaitForFirstConsumer`. To normalne.
2. **Pod** z tym PVC. Pod `Pending`.
3. **Scheduler** wybiera węzeł (zasoby, taints, affinity, topologia) i zapisuje go na PVC w adnotacji `volume.kubernetes.io/selected-node`.
4. **external-provisioner** w `ebs-csi-controller` czyta klasę i woła sterownik (`CreateVolume`). Sterownik zakłada wolumen EBS gp3 w strefie wybranego węzła.
5. **PV** `pvc-<UID>` powstaje z `volumeHandle` (ID dysku), `nodeAffinity` (strefa) i `claimRef`. PVC i PV są `Bound`. Scheduler przypisuje pod do węzła.
6. **Attach.** VolumeAttachment → `external-attacher` → EC2 `AttachVolume`. Pod `ContainerCreating`.
7. **Mount.** Kubelet woła `ebs-csi-node` (DaemonSet): formatowanie ext4 przy pierwszym użyciu i montowanie. Pod `Running`.

### Dlaczego WaitForFirstConsumer

Dysk EBS żyje w jednej AZ i podepniesz go tylko do instancji w tej samej AZ. Przy `Immediate` dysk powstaje od razu w losowej strefie, a pod potem musi się tam zmieścić (inaczej `volume node affinity conflict`). Przy `WaitForFirstConsumer` najpierw jest decyzja schedulera, potem dysk w strefie węzła.

Raz utworzony dysk zostaje w swojej strefie. U nas jest jeden węzeł na strefę, więc pod z dyskiem EBS jest w praktyce przywiązany do jednego węzła.

## Tryby dostępu, reclaimPolicy, powiększanie

| Tryb | Pełna nazwa | Znaczenie | Przykłady |
|---|---|---|---|
| **RWO** | ReadWriteOnce | zapis z **jednego węzła** (kilka podów na tym węźle może go używać) | EBS, Azure Disk, GCE PD |
| **ROX** | ReadOnlyMany | odczyt z wielu węzłów | EFS, NFS, S3 (Mountpoint) |
| **RWX** | ReadWriteMany | zapis z wielu węzłów | EFS, FSx, NFS, Azure Files, Filestore |
| **RWOP** | ReadWriteOncePod | zapis przez **jednego poda** w klastrze (GA od 1.29, tylko CSI) | EBS |

**RWO = jeden węzeł, nie jeden pod.** Wyłączność daje dopiero RWOP. Deployment z dyskiem RWO: `strategy: Recreate`, bo nowy pod na innym węźle nie podepnie dysku, dopóki stary go trzyma.

- `reclaimPolicy: Delete` (domyślna w gp3): usunięcie PVC usuwa PV i dysk EBS. Dane przepadają.
- `reclaimPolicy: Retain`: PV przechodzi w `Released`, dysk z danymi zostaje. Nowy PVC nie zwiąże się z nim sam; admin decyduje, co dalej. `Recycle` jest wycofane.
- `allowVolumeExpansion: true`: zwiększasz `spec.resources.requests.storage` w PVC. Tylko w górę, EBS rośnie online razem z systemem plików. AWS pozwala modyfikować wolumen raz na 6 godzin.

```bash
kubectl patch pvc dane -p '{"spec":{"resources":{"requests":{"storage":"20Gi"}}}}'
```

## Rodzaje StorageClass i backendów

| Backend | Sterownik | Tryby | Zasięg | Kiedy |
|---|---|---|---|---|
| **EBS gp3** (nasza domyślna) | `ebs.csi.aws.com`, `type: gp3` | RWO, RWOP | 1 AZ | bazy, aplikacje z dyskiem; 3000 IOPS i 125 MiB/s bazowo, więcej parametrami `iops`, `throughput` |
| EBS io2 | `ebs.csi.aws.com`, `type: io2` | RWO, RWOP | 1 AZ | gwarantowane wysokie IOPS, drożej |
| EFS | `efs.csi.aws.com` (`provisioningMode: efs-ap`, `fileSystemId`) | RWX, ROX, RWO | region | wspólne pliki dla wielu podów; system plików zakłada admin |
| FSx for Lustre | `fsx.csi.aws.com` | RWX | 1 AZ | HPC, ML, duża przepustowość |
| Mountpoint for S3 | `s3.csi.aws.com` | RWX, ROX | region | odczyt dużych plików z bucketu; tylko statyczne PV, niepełny POSIX |
| NFS | wolumen `nfs` w PV albo `nfs.csi.k8s.io` | RWX, ROX, RWO | serwer NFS | on-prem, istniejący serwer plików |
| local PV | `kubernetes.io/no-provisioner` + PV `local` | RWO | 1 węzeł | szybki lokalny dysk dla baz, które same replikują |
| hostPath | bez klasy | — | 1 węzeł | **nie dla aplikacji**: dane na jednym węźle, dostęp do systemu plików węzła, blokuje go Pod Security `baseline` |
| Azure Disk / Files | `disk.csi.azure.com` (`managed-csi`), `file.csi.azure.com` (`azurefile-csi`) | RWO / RWX | strefa / region | odpowiedniki EBS i EFS na AKS |
| GCE PD / Filestore | `pd.csi.storage.gke.io` (`standard-rwo`), `filestore.csi.storage.gke.io` | RWO / RWX | strefa / region | odpowiedniki na GKE |
| kind `standard` | `rancher.io/local-path` | RWO | 1 węzeł | lokalne ćwiczenia |

- Wbudowane sterowniki chmurowe (`kubernetes.io/aws-ebs`, `kubernetes.io/azure-disk`, `kubernetes.io/gce-pd`…) usunięto z kodu Kubernetesa. Stara klasa `gp2` z `kubernetes.io/aws-ebs` działa tylko przez migrację do CSI. Nowe klasy pisz z nazwą sterownika CSI.
- Domyślna klasa ma adnotację `storageclass.kubernetes.io/is-default-class: "true"`, a `kubectl get sc` pokazuje przy niej `(default)`. EKS sam żadnej nie oznacza, dlatego admin oznaczył gp3.

## Kto tworzy statyczne PV i jakie są rodzaje

**PV jest obiektem całego klastra, a nie namespace'u.** Tworzy go więc tylko admin klastra, czyli ktoś z uprawnieniami RBAC do `persistentvolumes`. Kursanci ich nie mają, mogą tylko zamówić PVC.

Jak to wygląda w AWS:

1. **Admin zakłada dysk poza Kubernetesem**, np. `aws ec2 create-volume`, w tej samej strefie (AZ), w której są węzły.
2. **Admin pisze PV** z `csi.driver: ebs.csi.aws.com` i `volumeHandle: vol-0abc…`. Dodaje `nodeAffinity` na strefę (`topology.kubernetes.io/zone`) i `storageClassName: ""`, żeby żadna klasa nie utworzyła dysku dynamicznie. Może też dodać `claimRef`, czyli zarezerwować ten PV dla konkretnego PVC.
3. **Użytkownik tworzy PVC** o pasującym rozmiarze, trybie dostępu (`accessModes`) i klasie (`storageClassName: ""`). Kubernetes sam łączy go z tym PV.

```bash
# 1. admin: dysk w strefie węzła
aws ec2 create-volume --region eu-central-1 --availability-zone eu-central-1a \
  --size 20 --volume-type gp3 \
  --tag-specifications 'ResourceType=volume,Tags=[{Key=Name,Value=pg-dane}]'
kubectl get nodes -L topology.kubernetes.io/zone
```

```yaml
# 2. admin: statyczne PV dla EBS
apiVersion: v1
kind: PersistentVolume
metadata:
  name: pg-dane-pv
spec:
  capacity:
    storage: 20Gi
  volumeMode: Filesystem
  accessModes: [ReadWriteOnce]
  persistentVolumeReclaimPolicy: Retain   # dysk przeżyje usunięcie PVC
  storageClassName: ""                    # bez klasy
  claimRef:                               # opcjonalnie: rezerwacja dla jednego PVC
    namespace: anna
    name: pg-dane
  csi:
    driver: ebs.csi.aws.com
    volumeHandle: vol-0abc1234def567890
    fsType: ext4                          # pusty dysk sterownik sformatuje
  nodeAffinity:
    required:
      nodeSelectorTerms:
      - matchExpressions:
        - key: topology.kubernetes.io/zone
          operator: In
          values: [eu-central-1a]
---
# 3. użytkownik: pasujący PVC
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: pg-dane
  namespace: anna
spec:
  storageClassName: ""        # musi być "", inaczej wskoczy domyślna gp3 i zamówi nowy dysk
  accessModes: [ReadWriteOnce]
  resources:
    requests:
      storage: 20Gi
  volumeName: pg-dane-pv      # opcjonalnie: wskazanie PV wprost
```

Statyczne PV dla EFS (RWX, wiele stref, bez `nodeAffinity`). Wcześniej potrzebny sterownik EFS CSI, system plików z mount targetami w podsieciach węzłów i security group wpuszczająca NFS (2049):

```yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: wspolne-pliki-pv
spec:
  capacity:
    storage: 5Gi              # API wymaga, EFS tego nie ogranicza
  volumeMode: Filesystem
  accessModes: [ReadWriteMany]
  persistentVolumeReclaimPolicy: Retain
  storageClassName: ""
  csi:
    driver: efs.csi.aws.com
    volumeHandle: fs-0123456789abcdef0    # z access pointem: fs-…::fsap-…
```

Rodzaje statycznych PV:

| Rodzaj | Co w PV | Tryby | Uwagi |
|---|---|---|---|
| EBS | `driver: ebs.csi.aws.com`, `volumeHandle: vol-…` | RWO | jedna AZ, `nodeAffinity` na strefę |
| EFS | `driver: efs.csi.aws.com`, `volumeHandle: fs-…` | RWX | wiele AZ |
| FSx for Lustre | `driver: fsx.csi.aws.com`, `volumeHandle: fs-…`, `volumeAttributes`: `dnsname`, `mountname` | RWX | jedna AZ |
| S3 (Mountpoint CSI) | `driver: s3.csi.aws.com`, `volumeAttributes.bucketName` | RWX, ROX | tylko statycznie |
| NFS | `nfs.server`, `nfs.path` | RWX, ROX, RWO | dowolny serwer NFS |
| local PV | `local.path` + `nodeAffinity` na węzeł | RWO | klasa `kubernetes.io/no-provisioner` |

**Kiedy statycznie:** istniejące dane, odtworzenie ze snapshotu, dysk ma przeżyć klaster.

## StatefulSet: dysk dla każdego poda

`volumeClaimTemplates` tworzy osobny PVC dla każdego poda: `<szablon>-<statefulset>-<numer>`, np. `data-db-0`, `data-db-1`, `data-db-2`. Pod `db-1` zawsze wraca do `data-db-1`.

```yaml
spec:
  persistentVolumeClaimRetentionPolicy:   # GA 1.32; domyślnie Retain/Retain
    whenDeleted: Retain
    whenScaled: Retain
  volumeClaimTemplates:
  - metadata:
      name: data
    spec:
      accessModes: [ReadWriteOnce]
      resources:
        requests:
          storage: 10Gi
```

- **PVC przeżywają usunięcie StatefulSetu** i skalowanie w dół. Po ponownym utworzeniu pody wracają do swoich danych.
- Sprzątanie: `persistentVolumeClaimRetentionPolicy` z `Delete` albo ręcznie `kubectl delete pvc -l app=db`.
- Szablonu `volumeClaimTemplates` w istniejącym StatefulSecie nie zmienisz. Powiększasz każdy PVC osobno.
- StatefulSet nie replikuje danych. Replikację robi baza albo operator (dzień 5).

## Typowe problemy

| Objaw | Przyczyna | Co zrobić |
|---|---|---|
| PVC `Pending`, `waiting for first consumer to be created before binding` | WaitForFirstConsumer, brak poda | nic, utwórz pod |
| PVC `Pending`, `no persistent volumes available for this claim and no storage class is set` | brak domyślnej klasy albo `storageClassName: ""` bez pasującego PV | `kubectl get sc`, wpisz klasę |
| `storageclass.storage.k8s.io "…" not found` | klasa z innego klastra (`managed-csi`, `standard`) | na EKS: `gp3` albo bez pola |
| `exceeded quota: … requests.storage` | ResourceQuota na dyski | `kubectl describe quota` |
| `Multi-Attach error for volume "pvc-…" Volume is already exclusively attached to one node…` | RWO + rolling update na inny węzeł | `strategy: Recreate` albo StatefulSet |
| pod `Pending`, `volume node affinity conflict` | dysk w innej AZ niż dostępne węzły | porównaj `nodeAffinity` PV z `kubectl get nodes -L topology.kubernetes.io/zone` |
| Postgres: `directory "/var/lib/postgresql/data" exists but is not empty` | `lost+found` na świeżym ext4 | `PGDATA=/var/lib/postgresql/data/pgdata` albo `subPath`; w `postgres:18` PGDATA jest już w podkatalogu, montujesz `/var/lib/postgresql` |
| `Permission denied` na dysku | kontener nie-root, katalog roota | `securityContext.fsGroup` |
| PVC wisi w `Terminating` | finalizer `kubernetes.io/pvc-protection`, pod dalej go używa | usuń pod / przeskaluj |
| po usunięciu PVC dane zniknęły | `reclaimPolicy: Delete` | `Retain`, kopie, VolumeSnapshot |

## Komendy

```bash
kubectl get sc                                   # klasy; domyślna z dopiskiem (default)
kubectl get pvc,pv                               # STATUS, VOLUME, CLAIM
kubectl describe pvc dane                        # Events: WaitForFirstConsumer, Provisioning, błędy; Used By
kubectl describe pod <pod>                       # SuccessfulAttachVolume, Multi-Attach, FailedMount
kubectl get pv <pv> -o yaml                      # volumeHandle, nodeAffinity, reclaimPolicy, claimRef
kubectl get nodes -L topology.kubernetes.io/zone # strefy węzłów
kubectl exec -it <pod> -- df -h <mountPath>      # czy dysk jest zamontowany
kubectl explain pvc.spec
```
