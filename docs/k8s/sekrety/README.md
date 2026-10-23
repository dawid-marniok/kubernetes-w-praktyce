# Dzień 5 — ściąga: sekrety z sejfu (Key Vault, Secrets Manager, Vault)

**Wizualizacja:** [sekrety.html](sekrety.html) (otwórz plik w przeglądarce: dwuklik albo `open sekrety.html`). Animowana droga sekretu dla ośmiu podejść (zwykły Secret, Sealed Secrets, SOPS, zmienne w CI/CD, External Secrets, Secrets Store CSI, Vault Agent Injector, SDK w aplikacji): kto pobiera, gdzie ląduje, czy powstaje kopia w etcd. Do tego rotacja hasła krok po kroku (plik kontra `env`), podpięcie AWS, Azure i Vault w ESO oraz wybór podejścia.

W dniu 2 Secret był base64 w YAML-u. base64 to kodowanie, nie szyfrowanie: plik `secret.yaml` w repo to hasło w repo. W firmach hasła mieszkają w sejfie: Azure Key Vault, AWS Secrets Manager albo Parameter Store, HashiCorp Vault, Google Secret Manager. Ta ściąga mówi, jak dowieźć je do poda i czy sejf zastępuje Secret, czy działa razem z nim.

Demo prowadzącego krok po kroku, z plikami: [`przyklady/k8s/25-external-secrets/`](../../../przyklady/k8s/25-external-secrets/) (AWS Secrets Manager → Secret, rotacja). Na k8s-sages magazyn wpuszcza tylko namespace prowadzącego, więc sam ćwiczysz po szkoleniu, na własnym klastrze i z własnym sejfem.

## Zamiast czy razem?

Prawie zawsze **razem**. Źródłem prawdy jest sejf, a w klastrze i tak powstaje kopia: zwykły `Secret` (External Secrets) albo plik w podzie (Secrets Store CSI). Dlatego zasady z dnia 4 dalej obowiązują: kto ma `get secrets` w namespace, ten widzi wartość, więc RBAC i szyfrowanie etcd mają znaczenie (na EKS i AKS etcd szyfruje się kluczem KMS).

## Pięć podejść

| Podejście | Jak działa | Plusy | Minusy | Kiedy |
|---|---|---|---|---|
| **External Secrets Operator (ESO)** | operator czyta sejf i tworzy zwykły `Secret`, odświeża co `refreshInterval` | aplikacja bez zmian (`envFrom`, wolumen), wiele sejfów, rotacja bez commita | kopia sekretu w etcd; kolejny operator do utrzymania | domyślny wybór: sejf już jest, aplikacje czytają Secret |
| **Secrets Store CSI Driver** + provider (Azure, AWS, GCP, Vault) | sterownik CSI montuje sekret jako plik prosto z sejfu przy starcie poda | sekretu nie ma w etcd (chyba że włączysz synchronizację do Secret) | pod nie wstanie, gdy sejf nie odpowiada; aplikacja czyta plik; zmienna środowiskowa tylko przez synchronizację do Secret | wymóg „sekret nie leży w klastrze”; dodatek AKS „Key Vault provider” |
| **Sealed Secrets** / **SOPS** | zaszyfrowany plik w Gicie; odszyfrowuje kontroler w klastrze (Sealed Secrets) albo narzędzie GitOps z kluczem w KMS (SOPS z Flux, Argo CD) | GitOps bez zewnętrznego sejfu, historia zmian w Gicie | rotacja = nowy commit; utrata klucza = utrata sekretów | małe zespoły, GitOps, brak sejfu w firmie |
| **Zmienne w CI/CD** | w Gicie placeholder (`${DB_PASSWORD}`), pipeline podstawia wartość ze zmiennej protected/masked (`envsubst`, `helm --set`) i robi `apply` | zero komponentów w klastrze, każdy CI to ma, osobne wartości per środowisko | CI staje się sejfem bez audytu odczytów; hasło zna każdy, kto może zmienić pipeline; wartość przechodzi przez runnera; CI potrzebuje prawa zapisu do klastra; nie pasuje do Argo CD i Flux | brak sejfu i GitOps, wdrożenia z pipeline'u |
| **Zwykły Secret** | `kubectl create secret` albo YAML z base64 | zero dodatków | wartość w YAML-u albo w historii shella | lab, demo, nic poza klastrem |

### Zmienne w CI/CD: na co uważać

```yaml
# k8s/secret.yaml w repo: tylko placeholder
apiVersion: v1
kind: Secret
metadata: {name: db}
stringData:
  DB_PASSWORD: ${DB_PASSWORD}
```

```yaml
# .gitlab-ci.yml: DB_PASSWORD to zmienna protected + masked (tylko chronione gałęzie)
deploy:
  script:
    - envsubst < k8s/secret.yaml | kubectl apply -f -
```

- **Maskowanie to nie ochrona.** `echo $DB_PASSWORD | base64` w jobie omija maskę. Hasło zna każdy, kto może zmienić pipeline na chronionej gałęzi.
- **Nie zapisuj wyrenderowanego pliku jako artefaktu** i nie włączaj `set -x` w kroku z hasłem.
- **`helm --set` zostawia ślad.** Wartość ląduje w historii release'u (Secrety `sh.helm.release.v1.*`), więc kto ma `get secrets`, widzi też stare hasła.
- **GitOps (Argo CD, Flux) tego nie obsłuży**, bo renderuje z Gita, a tam jest placeholder. Odpowiednik w modelu pull: argocd-vault-plugin (placeholder podmieniany wartością z Vaulta albo Secrets Managera) albo po prostu ESO.
- Krok dalej: pipeline loguje się do chmury przez **OIDC** i czyta hasło z sejfu. Wtedy CI nie przechowuje hasła.

## External Secrets: jak to wygląda

```
Secrets Manager / Key Vault ──► ESO (operator) ──► Secret todos-sejf ──► Pod (env albo plik)
              ▲                      │
     rola IAM / Workload Identity    └── co refreshInterval porównuje i aktualizuje
```

Zespół aplikacji pisze tylko `ExternalSecret`. W pliku nie ma wartości, więc może leżeć w Gicie:

```yaml
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: todos-sejf
spec:
  refreshInterval: 1h               # każde odświeżenie to płatne wywołanie API sejfu
  secretStoreRef:
    kind: ClusterSecretStore        # albo SecretStore w tym samym namespace
    name: aws-secrets-manager
  target:
    name: todos-sejf                # Secret, który powstanie
    creationPolicy: Owner           # usuniesz ExternalSecret → zniknie Secret
  data:
  - secretKey: MONGODB_URI
    remoteRef:
      key: szkolenie/demo/todos     # nazwa sekretu w sejfie
      property: MONGODB_URI         # pole w JSON-ie
```

Cały sekret JSON jako osobne klucze: `dataFrom: [{extract: {key: szkolenie/demo/todos}}]`.

Magazyn ustawia platforma, raz. Różni się tylko blokiem `provider`:

```yaml
# AWS (EKS): rola IAM przez Pod Identity albo IRSA, bez kluczy w YAML-u
apiVersion: external-secrets.io/v1
kind: ClusterSecretStore
metadata:
  name: aws-secrets-manager
spec:
  provider:
    aws: {service: SecretsManager, region: eu-central-1}
  conditions:
  - namespaces: [demo]              # które namespace'y mogą z niego czytać
---
# Azure (AKS): Workload Identity, ServiceAccount sfederowany z tożsamością w Entra ID
apiVersion: external-secrets.io/v1
kind: SecretStore
metadata:
  name: azure-kv
spec:
  provider:
    azurekv:
      vaultUrl: https://<nazwa-sejfu>.vault.azure.net
      authType: WorkloadIdentity
      serviceAccountRef: {name: eso-keyvault}   # adnotacja azure.workload.identity/client-id
```

**SecretStore czy ClusterSecretStore.** `SecretStore` żyje w namespace zespołu i używa jego tożsamości: zespół A nie przeczyta sejfu zespołu B. `ClusterSecretStore` to jeden magazyn dla klastra; bez `conditions` każdy, kto może tworzyć `ExternalSecret`, przeczyta wszystko, do czego ma dostęp rola kontrolera.

## Rotacja hasła

1. Zmieniasz wartość w sejfie.
2. Po `refreshInterval` ESO aktualizuje Secret.
3. Plik z wolumenu w podzie zmienia się sam po ok. minucie (kubelet), **zmienna środowiskowa nie**: proces czyta ją raz, przy starcie.
4. Restart podów: `kubectl rollout restart deployment <nazwa>` albo automatycznie, np. Reloader (Stakater) obserwuje Secret i restartuje Deployment.

Natychmiastowe odświeżenie bez czekania: `kubectl annotate externalsecret todos-sejf force-sync=$(date +%s) --overwrite`.

## Diagnoza

```bash
kubectl get clustersecretstore,secretstore          # STATUS Valid, READY True
kubectl get externalsecret                           # STATUS SecretSynced
kubectl describe externalsecret todos-sejf           # Events: powód błędu
kubectl logs -n external-secrets deploy/external-secrets
```

| Objaw | Przyczyna |
|---|---|
| `SecretSyncedError` + `AccessDeniedException` | polityka IAM nie obejmuje tego ARN-u albo brak Pod Identity / Workload Identity dla ServiceAccount ESO |
| `SecretSyncedError` + `Secret does not exist` | literówka w `remoteRef.key`, inny region niż w magazynie |
| `could not find property` | `property` nie istnieje w JSON-ie albo sekret nie jest JSON-em (wtedy bez `property`) |
| `no matches for kind "ExternalSecret" in version "external-secrets.io/v1beta1"` | ESO 2.x serwuje tylko `v1`; zmień `apiVersion` (zob. [wersje API](../crd/README.md#wersje-api-alpha-beta-v1)) |
| ExternalSecret: magazyn „not allowed” w tym namespace | `conditions` w ClusterSecretStore nie obejmuje Twojego namespace'u |
| Store nie jest `Valid` | zły `vaultUrl` / region albo kontroler bez tożsamości: `kubectl describe clustersecretstore` |

## Zobacz też

- Secret, `envFrom` i wolumen: dzień 2, [`przyklady/k8s/04-configmap-secret/`](../../../przyklady/k8s/04-configmap-secret/)
- RBAC na `secrets`: [`rbac/README.md`](../rbac/README.md)
- Operator jako wzorzec: [`crd/README.md`](../crd/README.md)
- external-secrets.io (dokumentacja providerów), secrets-store-csi-driver.sigs.k8s.io
