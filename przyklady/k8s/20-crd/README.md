# Przykłady: CRD

**Cel:** dodać do API Kubernetesa własny typ obiektu (`Backup`) i zobaczyć, że bez kontrolera to tylko zapisany rekord z walidacją.

**Gdzie:** klaster szkoleniowy EKS. CRD to zasób klastrowy, więc wgrywa go prowadzący na żywo na początku tematu 4 (krok 0); Ty tworzysz obiekty `Backup` w swoim namespace, dopóki CRD jest w klastrze (do końca lab16). Komendy wydajesz w tym katalogu (`cd przyklady/k8s/20-crd`).

Sprawdź, czy typ jest w klastrze: `kubectl api-resources | grep szkolenie`. Pusto = CRD jeszcze nie wgrany albo już usunięty. Na własnym klastrze (po szkoleniu, z uprawnieniami admina) zrób krok 0 sam.

| Plik | Co pokazuje |
|---|---|
| `crd-backup.yaml` | typ `Backup`, grupa `szkolenie.example.com`, skrót `bk`, schemat z walidacją, dodatkowe kolumny |
| `backup-nightly.yaml` | pierwszy obiekt typu `Backup` |
| `rbac-backups-edit.yaml` | ClusterRole z etykietą `aggregate-to-edit`: dokleja prawo do obiektów `Backup` do wbudowanej roli `edit` (tylko prowadzący) |

## Krok po kroku

**0. Prowadzący: nowy typ i uprawnienia** (kontekst z uprawnieniami klastrowymi; kursant dostanie `forbidden`)
```bash
kubectl apply -f crd-backup.yaml -f rbac-backups-edit.yaml
kubectl get crd backups.szkolenie.example.com
```
Co powinieneś zobaczyć: CRD z datą utworzenia. Od tej chwili rola `edit`, którą kursanci mają w swoich namespace'ach, obejmuje też `backups` (`kubectl auth can-i create backups` → `yes`).

**1. Nowy typ w API**
```bash
cat crd-backup.yaml                          # tylko przeczytaj: to wgrał prowadzący w kroku 0
kubectl api-resources | grep szkolenie
kubectl explain backup.spec
```
Co powinieneś zobaczyć: `backups  bk  szkolenie.example.com/v1  true  Backup`. `explain` pokazuje pola `schedule` (wymagane) i `retention` z opisami ze schematu.

**2. Pierwszy obiekt**
```bash
kubectl apply -f backup-nightly.yaml
kubectl get bk
```
Co powinieneś zobaczyć: `NAME nightly`, `SCHEDULE 0 2 * * *`, `RETENTION 7` (kolumny z `additionalPrinterColumns`). Nic się nie wykonuje: nie ma kontrolera.

**3. Walidacja schematu**
```bash
sed 's/retention: 7/retention: 0/' backup-nightly.yaml | kubectl apply -f -
```
Co powinieneś zobaczyć: `The Backup "nightly" is invalid: spec.retention: Invalid value: 0: spec.retention in body should be greater than or equal to 1`.

## Sprzątanie
```bash
kubectl delete -f backup-nightly.yaml
```
Prowadzący po lab16 usuwa typ i uprawnienia (`kubectl delete -f crd-backup.yaml -f rbac-backups-edit.yaml`): razem z CRD znikają WSZYSTKIE obiekty `Backup` we wszystkich namespace'ach. Sprawdź potem `kubectl get bk`.

## Uwagi
- Nazwa CRD to zawsze `<plural>.<group>`.
- `forbidden … customresourcedefinitions`: CRD tworzy administrator klastra. Prawo do samych obiektów `Backup` dostajesz przez ClusterRole z etykietą `rbac.authorization.k8s.io/aggregate-to-edit`, doklejaną do roli `edit`.
- `the server doesn't have a resource type "bk"`: CRD jeszcze nie ma albo już go usunięto.
- Schemat (`openAPIV3Schema`) jest obowiązkowy; kube-apiserver odrzuca obiekty niezgodne ze schematem (`minimum`, `required`).
- Pola spoza schematu: `kubectl apply` je odrzuci (walidacja Strict); przy `--validate=warn` ostrzeże, a pole zniknie (pruning).
- CRD bez kontrolera nic nie robi — to tylko typ, walidacja i endpoint REST. Kontroler + CRD = operator (dzień 5).
