# Przykłady: ConfigMap i Secret

**Cel:** podać aplikacji konfigurację i hasło z zewnątrz (zmienne i pliki) i zobaczyć, że Secret to tylko base64.

**Gdzie:** klaster szkoleniowy EKS, Twój namespace. Komendy wydajesz w tym katalogu (`cd przyklady/k8s/04-configmap-secret`).

| Plik | Co pokazuje |
|---|---|
| `configmap.yaml` | klucz-wartość i cały plik jako klucz |
| `secret.yaml` | Secret `Opaque` z atrapą hasła (`stringData`) |
| `deployment-config.yaml` | `envFrom`, `env.valueFrom.secretKeyRef`, ConfigMap jako wolumen |

## Krok po kroku

**1. ConfigMap, Secret i Deployment**
```bash
kubectl apply -f configmap.yaml -f secret.yaml -f deployment-config.yaml
kubectl get configmap przyklad-config
kubectl get secret przyklad-db
kubectl logs deploy/przyklad-config
```
Co powinieneś zobaczyć: ConfigMap z `DATA 2`, Secret `TYPE Opaque`, `DATA 1`. W logach `LOG_LEVEL=info`, `DB_PASSWORD=changeme-przyklad` oraz zawartość pliku: `feature.x=true`, `timeout.seconds=30`. Kontener nie wie, skąd przyszły wartości.

**2. Secret to base64, nie szyfrowanie**
```bash
kubectl get secret przyklad-db -o yaml | grep password
kubectl get secret przyklad-db -o jsonpath='{.data.password}' | base64 -d; echo
```
Co powinieneś zobaczyć: pole `password:` z wartością `Y2hhbmdlbWUtcHJ6eWtsYWQ=`, a po zdekodowaniu `changeme-przyklad`. Kto ma `get secrets` w namespace, zna hasło.

**3. Zmiana ConfigMapy: plik tak, zmienna nie**
```bash
kubectl patch configmap przyklad-config --type merge -p '{"data":{"LOG_LEVEL":"debug","app.properties":"feature.x=false\n"}}'
kubectl exec deploy/przyklad-config -- sh -c 'echo $LOG_LEVEL; cat /etc/app/app.properties'   # powtórz po ok. minucie
kubectl rollout restart deploy/przyklad-config
kubectl logs deploy/przyklad-config | head -1
```
Co powinieneś zobaczyć: po ok. minucie plik ma już `feature.x=false`, ale `$LOG_LEVEL` dalej `info`. Zmienne czyta się raz, przy starcie. Po `rollout restart` nowy pod wypisuje `LOG_LEVEL=debug`.

## Sprzątanie
```bash
kubectl delete -f .
```

## Uwagi

### Tworzenie z linii komend
```bash
# ConfigMap
kubectl create configmap <nazwa> --from-literal=<klucz>=<wartość>
kubectl create configmap <nazwa> --from-file=<plik>            # klucz = nazwa pliku
kubectl create configmap <nazwa> --from-file=<katalog>/        # każdy plik = klucz
kubectl create configmap <nazwa> --from-env-file=<plik.env>

# Secret
kubectl create secret generic <nazwa> --from-literal=<klucz>=<wartość>
kubectl create secret tls <nazwa> --cert=tls.crt --key=tls.key
kubectl create secret docker-registry <nazwa> --docker-server=<REJESTR> --docker-username=<użytkownik> --docker-password=<hasło>

# plik do repo zamiast tworzenia w klastrze
kubectl create configmap <nazwa> --from-file=<plik> --dry-run=client -o yaml > configmap.yaml
```

### Typy Secretów
| Typ | Do czego |
|---|---|
| `Opaque` (`generic`) | dowolne klucze: hasła, tokeny |
| `kubernetes.io/tls` | certyfikat i klucz (`tls.crt`, `tls.key`) dla Ingressu/Gatewaya |
| `kubernetes.io/dockerconfigjson` | logowanie do prywatnego rejestru (`imagePullSecrets`); na EKS obrazy z ECR pobiera węzeł swoją rolą IAM, bez Secretu |
| `kubernetes.io/service-account-token` | stary, długowieczny token ServiceAccount — od 1.24 nie tworzy się automatycznie |

Tokeny ServiceAccount: pody dostają krótkotrwały token *projected* automatycznie, a ręcznie wydajesz go komendą `kubectl create token <serviceaccount>`. Długowieczny token w Secrecie tworzy się tylko świadomie, manifestem z adnotacją `kubernetes.io/service-account.name` — zwykle niepotrzebny (dzień 4).

### Pamiętaj
- Secret to **base64, nie szyfrowanie**. Prawdziwych haseł nie trzymasz w repo: Sealed Secrets, SOPS albo zewnętrzny sejf (AWS Secrets Manager przez External Secrets Operator).
- Zmiana ConfigMapy/Secretu nie restartuje podów. Zmienne: `kubectl rollout restart deploy/<nazwa>`. Pliki z wolumenu odświeżą się same, ale **nie** przy `subPath`.
- `immutable: true` — nikt nie zmieni obiektu przez pomyłkę; zmiana = nowy obiekt z nową nazwą.
- Limit rozmiaru: 1 MiB na obiekt.
