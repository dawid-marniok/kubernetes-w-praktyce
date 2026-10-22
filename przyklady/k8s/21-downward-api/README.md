# Przykłady: Downward API

**Cel:** przekazać podowi jego własne metadane (nazwę, węzeł, limity, etykiety) bez pytania API Kubernetesa.

**Gdzie:** klaster szkoleniowy EKS, Twój namespace. Komendy wydajesz w tym katalogu (`cd przyklady/k8s/21-downward-api`).

| Plik | Co pokazuje |
|---|---|
| `pod-info.yaml` | pod (busybox:1.37) z metadanymi w **env** (`fieldRef`, `resourceFieldRef`, ustawiane raz przy starcie) i w **wolumenie** `downwardAPI` (pliki aktualizowane przez kubelet) |

## Krok po kroku

**1. Metadane w zmiennych**
```bash
kubectl apply -f pod-info.yaml
kubectl logs info
```
Co powinieneś zobaczyć: `POD_NAME=info NODE_NAME=ip-10-… MEM_LIMIT=33554432` (32Mi w bajtach).

**2. Metadane w plikach**
```bash
kubectl exec info -- cat /etc/podinfo/labels /etc/podinfo/annotations
```
Co powinieneś zobaczyć: `app="info"` i `build="1234"` (plus adnotacje dodane przez klaster).

**3. Zmiana etykiety: plik tak, zmienna nie**
```bash
kubectl label pod info wersja=2
kubectl exec info -- cat /etc/podinfo/labels      # powtórz po kilku sekundach
```
Co powinieneś zobaczyć: po kilku sekundach (najdłużej ok. minuty, zależy od cyklu kubeleta) w pliku pojawia się `wersja="2"`. Zmienne środowiskowe się nie zmieniają, bo ustawia się je raz, przy starcie kontenera.

## Sprzątanie
```bash
kubectl delete -f pod-info.yaml
```

## Uwagi

| Pole | env | wolumen |
|---|---|---|
| `metadata.name`, `metadata.namespace`, `metadata.uid` | ✅ | ✅ |
| `metadata.labels['klucz']`, `metadata.annotations['klucz']` | ✅ | ✅ |
| `metadata.labels`, `metadata.annotations` (całe) | ❌ | ✅ |
| `spec.nodeName`, `spec.serviceAccountName`, `status.podIP`, `status.hostIP` | ✅ | ❌ |
| `limits.cpu`, `limits.memory`, `requests.*` (`resourceFieldRef`) | ✅ | ✅ (z `containerName`) |

Bez ustawionego limitu `resourceFieldRef` zwraca pojemność węzła.
