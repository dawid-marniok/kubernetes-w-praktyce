# Przykłady: Deployment

| Plik | Co pokazuje |
|---|---|
| `deployment-rolling.yaml` | RollingUpdate z `maxSurge: 1`, `maxUnavailable: 0`, adnotacja `change-cause` |
| `deployment-sondy-zasoby.yaml` | startup/readiness/liveness + requests/limits; rollout czeka na gotowość |
| `deployment-recreate.yaml` | `strategy: Recreate` — zły tag = pełny przestój |

Rollout w pięciu komendach:
```bash
kubectl apply -f deployment-rolling.yaml
kubectl set image deploy/przyklad-deploy nginx=nginx:1.29
kubectl annotate deploy/przyklad-deploy kubernetes.io/change-cause="nginx 1.29" --overwrite
kubectl rollout status deploy/przyklad-deploy
kubectl rollout history deploy/przyklad-deploy
kubectl set image deploy/przyklad-deploy nginx=nginx:111   # zły tag: 1 nowy pod ImagePullBackOff, 3 stare dalej działają
kubectl rollout undo deploy/przyklad-deploy           # --to-revision=N
kubectl rollout restart deploy/przyklad-deploy        # nowe pody bez zmiany obrazu
```
- `--record` jest wycofane — opis zmiany daje adnotacja `kubernetes.io/change-cause` (nadpisuj ją przy każdej zmianie, inaczej przejdzie na następną rewizję).
- `spec.selector` jest niezmienny; zmiana = usunięcie i utworzenie Deploymentu.
- Konfiguracja z ConfigMapy i hasło z Secretu: `../04-configmap-secret/`.
