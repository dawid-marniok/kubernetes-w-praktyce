# Przykłady: Deployment

**Cel:** przeprowadzić aktualizację bez przestoju, cofnąć złą wersję i zobaczyć różnicę między RollingUpdate a Recreate.

**Gdzie:** klaster szkoleniowy EKS, Twój namespace. Komendy wydajesz w tym katalogu (`cd przyklady/k8s/03-deployment`).

| Plik | Co pokazuje |
|---|---|
| `deployment-rolling.yaml` | RollingUpdate z `maxSurge: 1`, `maxUnavailable: 0`, adnotacja `change-cause` |
| `deployment-sondy-zasoby.yaml` | startup/readiness/liveness + requests/limits; rollout czeka na gotowość |
| `deployment-recreate.yaml` | `strategy: Recreate` — zły tag = pełny przestój |

## Krok po kroku

**1. Deployment na nginx 1.28**

W drugim terminalu: `kubectl get pods -l app=przyklad-deploy -w`.
```bash
kubectl apply -f deployment-rolling.yaml
kubectl get deploy,rs -l app=przyklad-deploy
```
Co powinieneś zobaczyć: Deployment `3/3`, jeden ReplicaSet `przyklad-deploy-<hash>` z 3 podami.

**2. Aktualizacja do 1.29**
```bash
kubectl set image deploy/przyklad-deploy nginx=nginx:1.29
kubectl annotate deploy/przyklad-deploy kubernetes.io/change-cause="nginx 1.29" --overwrite
kubectl rollout status deploy/przyklad-deploy
kubectl rollout history deploy/przyklad-deploy
kubectl get rs -l app=przyklad-deploy
```
Co powinieneś zobaczyć: w drugim terminalu pody wymieniane po jednym: najpierw powstaje nowy, dopiero gdy jest gotowy, znika stary (`maxSurge: 1`, `maxUnavailable: 0`). `rollout status` kończy się `successfully rolled out`. W historii rewizje `1 nginx 1.28` i `2 nginx 1.29`. Stary ReplicaSet zostaje z 0 replik (do rollbacku).

**3. Zły tag i rollback**
```bash
kubectl set image deploy/przyklad-deploy nginx=nginx:111
kubectl get pods -l app=przyklad-deploy
kubectl rollout undo deploy/przyklad-deploy           # --to-revision=N cofa do konkretnej rewizji
kubectl rollout status deploy/przyklad-deploy
```
Co powinieneś zobaczyć: 1 nowy pod `ImagePullBackOff`, 3 stare dalej `Running`: aplikacja działa, bo `maxUnavailable: 0`. Po `undo` błędny pod znika, Deployment znów `3/3`.

**4. Restart bez zmiany obrazu**
```bash
kubectl rollout restart deploy/przyklad-deploy
```
Co powinieneś zobaczyć: wszystkie pody wymienione po kolei na nowe (np. żeby wczytały zmienioną ConfigMapę).

**5. Recreate: przestój wpisany w strategię**

W drugim terminalu: `kubectl get pods -l app=przyklad-recreate -w`.
```bash
kubectl apply -f deployment-recreate.yaml
kubectl set image deploy/przyklad-recreate nginx=nginx:111
kubectl get deploy przyklad-recreate
```
Co powinieneś zobaczyć: wszystkie 3 pody `Terminating` naraz, potem 3 nowe w `ImagePullBackOff`. Deployment `0/3`: pełny przestój.

**6. Sondy i zasoby**
```bash
kubectl apply -f deployment-sondy-zasoby.yaml
kubectl get pods -l app=przyklad-sondy -w             # Ctrl+C, gdy 4 × 1/1
```
Co powinieneś zobaczyć: pody najpierw `0/1 Running` (czekają na startup i readiness), po kilku sekundach `1/1`.

## Sprzątanie
```bash
kubectl delete -f .
```

## Uwagi
- `--record` jest wycofane — opis zmiany daje adnotacja `kubernetes.io/change-cause` (nadpisuj ją przy każdej zmianie, inaczej przejdzie na następną rewizję).
- `spec.selector` jest niezmienny; zmiana = usunięcie i utworzenie Deploymentu.
- Konfiguracja z ConfigMapy i hasło z Secretu: `../04-configmap-secret/`.
