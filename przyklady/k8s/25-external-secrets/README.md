# Przykłady: sekrety z sejfu (External Secrets Operator)

**Cel:** zobaczyć, jak sekret z sejfu chmury (AWS Secrets Manager, Azure Key Vault) staje się zwykłym `Secret` w namespace i jak przechodzi rotacja: plik w podzie zmienia się sam, zmienna środowiskowa dopiero po restarcie.

**Gdzie:** klaster szkoleniowy EKS. Na szkoleniu pokazuje to prowadzący w swoim namespace: magazyn (`ClusterSecretStore aws-secrets-manager`) wpuszcza tylko ten namespace, a zmiana wartości w sejfie wymaga uprawnień do AWS. Ty czytasz pliki i możesz podejrzeć stan (`kubectl get clustersecretstore`, `kubectl get pods -n external-secrets`). Po szkoleniu: na własnym klastrze z ESO i własnym sejfem. Komendy w tym katalogu (`cd przyklady/k8s/25-external-secrets`).

| Plik | Co pokazuje |
|---|---|
| `externalsecret.yaml` | `ExternalSecret`: odnośnik do sekretu `szkolenie/demo/todos` w Secrets Manager → Secret `todos-sejf` (2 klucze z jednego JSON-a), bez żadnej wartości w repo |
| `app.yaml` | busybox, który co 10 s wypisuje `API_KEY` ze zmiennej (`envFrom`) i z pliku (wolumen) |
| `secretstore-azure.yaml` | ten sam wzorzec na Azure Key Vault z Workload Identity (tylko do przeczytania) |

Teoria i porównanie z Sealed Secrets, SOPS i Secrets Store CSI: [`docs/k8s/sekrety/`](../../../docs/k8s/sekrety/README.md).

## Krok po kroku

**1. Operator i magazyn**
```bash
kubectl get pods -n external-secrets
kubectl get clustersecretstore
kubectl api-resources --api-group=external-secrets.io
```
Co powinieneś zobaczyć: trzy pody (kontroler, webhook, cert-controller), `aws-secrets-manager` z `STATUS Valid`, `READY True`. Kolejny operator: CRD + kontroler. Magazyn ustawia admin klastra raz, zespoły piszą tylko `ExternalSecret`. Kluczy AWS w YAML-u nie ma: kontroler dostaje rolę IAM przez EKS Pod Identity.

**2. ExternalSecret → Secret** (namespace, który magazyn wpuszcza)
```bash
kubectl apply -f externalsecret.yaml
kubectl get externalsecret todos-sejf
kubectl get secret todos-sejf -o jsonpath='{.data.API_KEY}' | base64 -d; echo
```
Co powinieneś zobaczyć: `STATUS SecretSynced`, `READY True`, a potem wartość z sejfu (`sejf-wersja-1`). W repo jest tylko odnośnik, wartość nigdy nie trafia do gita.

**3. Aplikacja czyta Secret**
```bash
kubectl apply -f app.yaml
kubectl logs -f deploy/sejf-app
```
Co powinieneś zobaczyć: co 10 s `env=sejf-wersja-1 plik=sejf-wersja-1`. Aplikacja nie wie o sejfie, to zwykły Secret jak w dniu 2.

**4. Rotacja w sejfie** (uprawnienia `secretsmanager:PutSecretValue`)
```bash
aws secretsmanager put-secret-value --secret-id szkolenie/demo/todos \
  --secret-string '{"MONGODB_URI":"mongodb://mongo:27017/todos","API_KEY":"sejf-wersja-2"}'
kubectl get secret todos-sejf -o jsonpath='{.data.API_KEY}' | base64 -d; echo   # po ok. 30 s
```
Co powinieneś zobaczyć: Secret ma `sejf-wersja-2` po `refreshInterval` (30 s). W logach po kolejnej minucie `env=sejf-wersja-1 plik=sejf-wersja-2`: plik z wolumenu się odświeżył, zmienną proces przeczytał raz, przy starcie.
```bash
kubectl rollout restart deploy/sejf-app
```
Po restarcie: `env=sejf-wersja-2 plik=sejf-wersja-2`.

**5. Azure Key Vault**
```bash
cat secretstore-azure.yaml
```
Zmienia się tylko magazyn (provider `azurekv`, Workload Identity zamiast Pod Identity). `ExternalSecret` wygląda tak samo.

## Sprzątanie
```bash
kubectl delete -f app.yaml
kubectl delete -f externalsecret.yaml
kubectl get secret todos-sejf            # NotFound: creationPolicy Owner usuwa Secret razem z ExternalSecret
```

## Uwagi
- `SecretSyncedError` → `kubectl describe externalsecret todos-sejf`. Zwykle `AccessDeniedException` (polityka IAM nie obejmuje sekretu), zła nazwa `key`/`property` albo namespace, którego magazyn nie wpuszcza (`spec.conditions` w `ClusterSecretStore`).
- `refreshInterval: 30s` jest na pokaz. Na produkcji raczej `1h`: każde odświeżenie to płatne zapytanie do API sejfu.
- Źródłem prawdy jest sejf, ale w klastrze i tak ląduje Secret. RBAC na `secrets` i szyfrowanie etcd dalej mają znaczenie.
- Automatyczny restart podów po zmianie Secretu: np. [Reloader](https://github.com/stakater/Reloader).
- Na co dzień: zamiast `secret.yaml` w repo (nawet „tylko base64”) trzymaj `ExternalSecret`, a wartość w sejfie, który firma już ma.
