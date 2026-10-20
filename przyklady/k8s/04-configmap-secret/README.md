# Przykłady: ConfigMap i Secret

| Plik | Co pokazuje |
|---|---|
| `configmap.yaml` | klucz-wartość i cały plik jako klucz |
| `secret.yaml` | Secret `Opaque` z atrapą hasła (`stringData`) |
| `deployment-config.yaml` | `envFrom`, `env.valueFrom.secretKeyRef`, ConfigMap jako wolumen |

```bash
kubectl apply -f configmap.yaml -f secret.yaml -f deployment-config.yaml
kubectl logs deploy/przyklad-config
```

## Tworzenie z linii komend
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

## Typy Secretów
| Typ | Do czego |
|---|---|
| `Opaque` (`generic`) | dowolne klucze: hasła, tokeny |
| `kubernetes.io/tls` | certyfikat i klucz (`tls.crt`, `tls.key`) dla Ingressu/Gatewaya |
| `kubernetes.io/dockerconfigjson` | logowanie do prywatnego rejestru (`imagePullSecrets`) |
| `kubernetes.io/service-account-token` | stary, długowieczny token ServiceAccount — od 1.24 nie tworzy się automatycznie |

Tokeny ServiceAccount: pody dostają krótkotrwały token *projected* automatycznie, a ręcznie wydajesz go komendą `kubectl create token <serviceaccount>`. Długowieczny token w Secrecie tworzy się tylko świadomie, manifestem z adnotacją `kubernetes.io/service-account.name` — zwykle niepotrzebny (dzień 4).

## Pamiętaj
- Secret to **base64, nie szyfrowanie**: `kubectl get secret przyklad-db -o jsonpath='{.data.password}' | base64 -d`.
- Zmiana ConfigMapy/Secretu nie restartuje podów. Zmienne: `kubectl rollout restart deploy/<nazwa>`. Pliki z wolumenu odświeżą się same, ale **nie** przy `subPath`.
- `immutable: true` — nikt nie zmieni obiektu przez pomyłkę; zmiana = nowy obiekt z nową nazwą.
- Limit rozmiaru: 1 MiB na obiekt.
