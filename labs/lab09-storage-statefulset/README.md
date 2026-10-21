# lab09 — Dysk, który przeżyje poda, i StatefulSet

**Gdzie:** klaster szkoleniowy, Twój namespace

**Po labie masz:** PVC z plikiem, który przeżył usunięcie poda, i StatefulSet `db`, w którym każdy pod ma własny dysk `data-db-<numer>`.

## Zanim zaczniesz

```bash
kubectl config get-contexts                  # kolumna NAMESPACE = Twój login
kubectl get storageclass                     # która ma (default)?
kubectl describe resourcequota               # ile PVC możesz mieć (persistentvolumeclaims)
kubectl get pvc                              # najlepiej pusto
```

- W manifestach **nie wpisuj `namespace:`** ani `storageClassName:` — wtedy działa domyślna klasa: na klastrze szkoleniowym `gp3` (wolumen EBS przez sterownik CSI `ebs.csi.aws.com`), na kind `standard`. Ten sam plik zadziała w obu miejscach.
- Każdy kontener ma mieć `resources` (requests i limits). Pliki startowe w tym katalogu już je mają.
- Quota pozwala na kilka PVC. Licz je: ten lab zużywa 4 naraz.

Pliki startowe: `app-pod.yaml` (pod montujący PVC `app-data`), `db-headless.yaml` (Service dla kroku 2).

## Poziom podstawowy

### 1. PVC i plik, który przeżyje poda

1. Napisz `app-data-pvc.yaml`: PVC `app-data`, `ReadWriteOnce`, `1Gi`, bez `storageClassName`.
2. Zastosuj PVC i od razu sprawdź status. Dlaczego jest `Pending`? Przeczytaj eventy:
   ```bash
   kubectl apply -f app-data-pvc.yaml
   kubectl get pvc app-data
   kubectl describe pvc app-data | tail -3
   ```
3. Uruchom poda z `app-pod.yaml`. Sprawdź znowu PVC i znajdź PV, który powstał (`kubectl get pv`).
4. Zapisz plik, usuń poda, uruchom go jeszcze raz i odczytaj plik:
   ```bash
   kubectl exec app-pod -- sh -c 'echo "zapisane $(date)" > /data/test.txt'
   kubectl delete pod app-pod
   kubectl apply -f app-pod.yaml
   kubectl exec app-pod -- cat /data/test.txt
   ```

✅ Plik jest na miejscu, choć pod jest nowy.

### 2. StatefulSet z dyskiem per pod

1. Zastosuj `db-headless.yaml`. Co znaczy `clusterIP: None`?
2. Napisz `db-sts.yaml`: StatefulSet `db`, `serviceName: db`, 2 repliki, etykieta `app: db`, obraz `nginx:1.29` (resources jak w `app-pod.yaml`, ale memory 64Mi/128Mi), `volumeClaimTemplates` o nazwie `data` (RWO, 1Gi) zamontowany w `/usr/share/nginx/html`.
3. W drugim terminalu obserwuj pody, w pierwszym zastosuj plik:
   ```bash
   kubectl get pods -l app=db -w
   kubectl apply -f db-sts.yaml
   ```
4. Sprawdź nazwy PVC (`kubectl get pvc`). Z czego składa się nazwa?
5. Zapisz w każdym podzie inną stronę i sprawdź, że pody nie widzą swoich plików:
   ```bash
   kubectl exec db-0 -- sh -c 'echo "to jest db-0" > /usr/share/nginx/html/index.html'
   kubectl exec db-1 -- ls /usr/share/nginx/html
   ```
6. Usuń `db-0` i sprawdź, pod jaką nazwą wraca, który PVC montuje i co serwuje:
   ```bash
   kubectl delete pod db-0
   kubectl get pod db-0 -o jsonpath='{.spec.volumes[0].persistentVolumeClaim.claimName}'; echo
   kubectl run test --rm -it --image=busybox:1.37 --restart=Never -- wget -qO- http://db-0.db
   ```

✅ `db-0` wrócił z PVC `data-db-0` i serwuje „to jest db-0”.

### 3. Skalowanie i kolejność

```bash
kubectl scale statefulset db --replicas=3     # obserwuj -w w drugim terminalu
kubectl scale statefulset db --replicas=1
kubectl get pods,pvc
```

Zanotuj: w jakiej kolejności pody powstają, a w jakiej znikają? Co stało się z PVC `data-db-1` i `data-db-2`?

### 4. Sprzątanie (obowiązkowe, bo quota)

```bash
kubectl delete statefulset db
kubectl get pvc                    # PVC nadal są — dlaczego?
kubectl delete pvc data-db-0 data-db-1 data-db-2
kubectl delete pod app-pod
kubectl delete pvc app-data
```

## SUKCES

- [ ] plik w `/data` przeżył usunięcie i ponowne utworzenie `app-pod`
- [ ] PVC `data-db-0` i `data-db-1` były `Bound`, a `db-0` po usunięciu wrócił z tym samym PVC
- [ ] umiesz powiedzieć, dlaczego PVC zostały po `kubectl delete statefulset`
- [ ] po labie `kubectl get pvc` jest puste

## Dla chętnych

- **Sprzątanie automatyczne.** Dopisz do StatefulSetu `persistentVolumeClaimRetentionPolicy` z `whenScaled: Delete` i `whenDeleted: Delete`. Powtórz krok 3 i 4: co się zmieniło?
- **Jeden dysk RWO, dwa pody na różnych węzłach.** Deployment `shared` z 2 replikami, oba montują ten sam PVC `shared-rwo` (RWO), a `podAntiAffinity` po `kubernetes.io/hostname` rozpycha je na różne węzły. Który pod nie wystartuje i jaki event zobaczysz? Porównaj `nodeAffinity` w PV na klastrze szkoleniowym i na kind: przypięcie do strefy czy do węzła?
- **RWX na klastrze szkoleniowym.** PVC `shared-rwx` z `ReadWriteMany`, bez `storageClassName`, i pod, który go montuje. Jaki event zobaczysz w `kubectl describe pvc shared-rwx`? Która usługa AWS dałaby RWX (podpowiedź: [`docs/k8s/storage/`](../../docs/k8s/storage/)) i dlaczego bazy nie trzyma się na dysku sieciowym NFS?
- **Tylko kind (zasoby klastra):** statyczny PV `local-pv` (`hostPath`, 2Gi, `storageClassName: local-storage`, `persistentVolumeReclaimPolicy: Retain`) i PVC `local-pvc` 1Gi z tą samą klasą. Ile ma PVC po związaniu? Co się dzieje z PV po usunięciu PVC?

## Gdy coś nie działa

**Gotowe wzorce manifestów:** [`przyklady/k8s/08-storage/`](../../przyklady/k8s/08-storage/), [`przyklady/k8s/09-statefulset/`](../../przyklady/k8s/09-statefulset/). Skopiuj i przerób, zamiast pisać YAML od zera.

| Objaw | Co zrobić |
|---|---|
| `failed quota: must specify limits.cpu…` | brakuje `resources` w kontenerze albo w szablonie StatefulSetu |
| `exceeded quota … persistentvolumeclaims` | `kubectl get pvc`, usuń PVC z poprzednich kroków |
| PVC `Pending` z `WaitForFirstConsumer` | to normalne, dopóki nie ma poda z tym PVC |
| PVC `Pending` z `storageclass … not found` | w PVC jest `storageClassName` z innego klastra (np. `default` na kind) — usuń tę linię |
| pod w `ContainerCreating`, event `Multi-Attach error` | dysk RWO jest jeszcze przypięty do innego węzła; poczekaj albo usuń drugi pod |
| `nslookup db-0.db` zwraca 127.0.53.53 | busybox pyta najpierw internet; użyj `wget -qO- http://db-0.db` albo pełnej nazwy `db-0.db.<namespace>.svc.cluster.local` |
