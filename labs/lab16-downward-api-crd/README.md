# lab16 — Downward API i własny typ w API (CRD)

**Cel:** pod poznaje swoje metadane (nazwa, IP, etykiety, limit pamięci) bez tokenu i bez uprawnień do API; tworzysz obiekty własnego typu `Backup`, który trener dodał do API.

**Po labie masz:** pod `pod-info`, który wypisuje swoje dane z env, plik z etykietami, który zmienia się po `kubectl label`, i obiekt `Backup` o nazwie `nightly` w swoim namespace.

## Zanim zaczniesz

- Pliki: `pod-info.yaml` (szkielet do uzupełnienia), `crd-backup.yaml` (definicja typu `Backup`, którą trener wgrał na klaster; tylko do przeczytania).
- W Twoim namespace działa ResourceQuota, więc pod ma już `resources`: nie usuwaj ich.

## Poziom podstawowy

### 1. Zmienne środowiskowe z Downward API

Uzupełnij w `pod-info.yaml` cztery miejsca `___`: nazwa poda, namespace, IP poda i limit pamięci kontenera. Nazwy pól znajdziesz w dokumentacji albo w `kubectl explain pod.spec.containers.env.valueFrom.fieldRef`.

```bash
kubectl apply -f pod-info.yaml
kubectl logs pod-info
```

✅ W logach widać `POD_NAME=pod-info`, Twój namespace, adres IP, `POD_VERSION=1` i `MEMORY_LIMIT=33554432` (32 MiB w bajtach).

### 2. Porównaj z tym, co mówi klaster

```bash
kubectl get pod pod-info -o wide
kubectl exec pod-info -- env | grep -E 'POD_|MEMORY_'
```

✅ IP i nazwa w env zgadzają się z `kubectl get -o wide`.

### 3. Wolumen downwardAPI

Dopisz do poda wolumen `podinfo` typu `downwardAPI` z dwoma plikami: `labels` (`metadata.labels`) i `annotations` (`metadata.annotations`), zamontowany w `/etc/podinfo`. Pod trzeba utworzyć od nowa (`kubectl delete pod pod-info`, potem `apply`).

```bash
kubectl exec pod-info -- cat /etc/podinfo/labels
kubectl label pod pod-info wersja=2 --overwrite
kubectl exec pod-info -- cat /etc/podinfo/labels        # powtórz po kilku sekundach
kubectl exec pod-info -- sh -c 'echo $POD_VERSION'
```

✅ Plik `labels` pokazuje `wersja="2"`, a zmienna `POD_VERSION` dalej ma `1`.

❓ Dlaczego plik się zmienił, a zmienna nie? Skąd w pliku etykiety, których nie nadawałeś?

### 4. Własny typ: Backup

Trener po demie zostawił w klastrze CRD `backups.szkolenie.example.com` i dał Ci prawo do obiektów `Backup` w Twoim namespace. Sam CRD to zasób klastrowy, więc go nie tworzysz.

```bash
kubectl api-resources | grep szkolenie
kubectl explain backup.spec
kubectl auth can-i create backups
```

1. Napisz obiekt `kind: Backup` (`apiVersion: szkolenie.example.com/v1`) o nazwie `nightly` (`spec.schedule: "0 2 * * *"`, `spec.retention: 7`), wgraj go i zobacz `kubectl get bk`.
2. Zmień `retention` na `0` i wgraj jeszcze raz. Kto odrzucił obiekt i na jakiej podstawie?
3. Czy jakiś backup się wykonał? Czego brakuje? (Wrócimy do tego jutro przy operatorach.)

✅ `kubectl get bk` pokazuje `nightly` z kolumnami `SCHEDULE` i `RETENTION`, a `retention: 0` kończy się `Invalid value: 0`.

## SUKCES

- [ ] w podzie widać nazwę, namespace, IP i limit pamięci
- [ ] plik `/etc/podinfo/labels` zmienia się po `kubectl label`, zmienna środowiskowa nie
- [ ] `kubectl get bk` pokazuje Twój `nightly`

Na koniec tematu trener usunie CRD. Zrób wtedy `kubectl get bk`: co stało się z Twoimi obiektami?

## Dla chętnych

- **Limit CPU w pliku.** Dodaj do wolumenu plik `cpu_limit_millicores` z `resourceFieldRef` (`limits.cpu`, `divisor: 1m`). Co jest wymagane w `resourceFieldRef` w wolumenie, a czego nie trzeba było w env?
- **Skąd ten limit?** Utwórz kopię poda pod nazwą `pod-info-bez` i usuń z niej całe `resources`. Quota wymaga limitów, a jednak pod powstaje. Co pokazuje `MEMORY_LIMIT` i skąd się wzięła ta wartość? (`kubectl get limitrange -o yaml`, `kubectl get pod pod-info-bez -o jsonpath='{.spec.containers[0].resources}'`)
- **Pole spoza schematu.** Dodaj do `spec` swojego `Backup` pole, którego nie ma w schemacie (np. `literowka: true`). Co zrobi `kubectl apply`? A `kubectl apply --validate=warn`? Co jest potem w `kubectl get bk <nazwa> -o yaml`?
- **Cudze obiekty.** `kubectl get bk -A` — czy widzisz Backupy innych? A `kubectl auth can-i create backups -n <sasiad>`?

## Wskazówki

**Gotowe wzorce manifestów:** [`przyklady/k8s/21-downward-api/`](../../przyklady/k8s/21-downward-api/), [`przyklady/k8s/20-crd/`](../../przyklady/k8s/20-crd/). Skopiuj i przerób, zamiast pisać YAML od zera.

| Objaw | Co zrobić |
|---|---|
| `exceeded quota` / `must specify limits` | Przywróć `resources` w kontenerze |
| `Pod "pod-info" is invalid: spec: Forbidden: pod updates may not change fields…` | Większości pól poda nie zmienisz w miejscu: `kubectl delete pod pod-info` i `apply` od nowa |
| `resourceFieldRef` w wolumenie: błąd walidacji | W wolumenie `containerName` jest wymagane |
| `metadata.labels` w env nie działa | Całe etykiety i adnotacje tylko jako plik w wolumenie; w env pojedyncza etykieta: `metadata.labels['wersja']` |
| `the server doesn't have a resource type "bk"` | CRD jeszcze nie ma (albo już go nie ma): napisz na czat |
| `backups.szkolenie.example.com is forbidden` po usunięciu CRD | kubectl pamięta typ z poprzedniego razu, a trener usunął już też uprawnienia. `kubectl api-resources \| grep szkolenie`: pusto = typu nie ma |
| `no matches for kind "Backup"` | Literówka w `apiVersion`: ma być `szkolenie.example.com/v1` |
| `forbidden … customresourcedefinitions` | CRD tworzy trener; Ty tworzysz tylko obiekty `Backup` |

Sprzątanie: `kubectl delete pod pod-info pod-info-bez --ignore-not-found` (obiekty `Backup` znikną razem z CRD).
