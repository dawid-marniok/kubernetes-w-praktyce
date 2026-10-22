# Przykłady: Pod Security

**Cel:** uruchomić aplikację zgodną z poziomem `restricted` i zobaczyć, jak Pod Security Admission odrzuca pody, które go nie spełniają.

**Gdzie:** klaster szkoleniowy EKS, Twój namespace. Etykiety Pod Security na swoim namespace możesz zmieniać, ale `enforce` sprawdzasz tylko na sucho (`--dry-run=server`): prawdziwe zablokowałoby Twoje pozostałe aplikacje. Komendy wydajesz w tym katalogu (`cd przyklady/k8s/18-pod-security`).

| Plik | Co pokazuje |
|---|---|
| `deployment-restricted.yaml` | Deployment, który przechodzi poziom `restricted`: `nginxinc/nginx-unprivileged:1.29` (UID 101, port 8080), `runAsNonRoot`, `seccompProfile: RuntimeDefault`, `allowPrivilegeEscalation: false`, `capabilities.drop: [ALL]`, `readOnlyRootFilesystem` + `emptyDir` na `/tmp`, limity |

## Krok po kroku

**1. Aplikacja zgodna z restricted**
```bash
kubectl apply -f deployment-restricted.yaml
kubectl get pods -l app=web
kubectl exec deploy/web -- id
kubectl exec deploy/web -- touch /test
```
Co powinieneś zobaczyć: pod `1/1 Running`, `uid=101(nginx)`, a `touch` kończy się `Read-only file system`. Zapis działa tylko w `/tmp` (emptyDir).

**2. Co by zrobiło enforce=restricted (na sucho)**
```bash
NS=$(kubectl config view --minify -o jsonpath='{..namespace}'); echo $NS    # Twój namespace
kubectl get namespace $NS --show-labels
kubectl label namespace $NS pod-security.kubernetes.io/enforce=restricted --dry-run=server
```
Co powinieneś zobaczyć: namespace ma `warn` i `audit` na `baseline`. Dry-run kończy się `namespace/<ns> labeled (server dry run)`, a etykieta się nie zmienia. Jeśli w namespace działają pody niezgodne z `restricted` (np. aplikacje z wcześniejszych labów na `nginx:1.29`), przed tym wypisuje `Warning: existing pods in namespace "<ns>" violate the new PodSecurity enforce level "restricted:latest"` i linię z naruszeniami (pody z tymi samymi błędami zbiera w jedną: `<pod> (and N other pods): …`). Podów `web` z kroku 1 na tej liście nie ma.

**3. Tryb warn**
```bash
kubectl label namespace $NS pod-security.kubernetes.io/warn=restricted --overwrite
kubectl run zwykly-nginx --image=nginx:1.29
kubectl rollout restart deploy/web
kubectl label namespace $NS pod-security.kubernetes.io/warn=baseline --overwrite    # przywróć poprzednie ustawienie
```
Co powinieneś zobaczyć: `kubectl run` wypisuje `Warning: would violate PodSecurity "restricted:latest": allowPrivilegeEscalation != false …, runAsNonRoot != true …`, ale pod powstaje. Restart `web` przechodzi bez ostrzeżenia. Tak wprowadza się restricted bez psucia działających aplikacji: najpierw `warn` i `audit`, poprawki, dopiero potem `enforce`.

⚠ Nie ustawiaj `enforce` naprawdę. Odrzucenie poda (`Error from server (Forbidden): … violates PodSecurity "restricted:latest"`) zobaczysz na demie prowadzącego.

## Sprzątanie
```bash
kubectl delete pod zwykly-nginx --ignore-not-found
kubectl delete -f deployment-restricted.yaml
kubectl get namespace $NS --show-labels      # warn=baseline, bez enforce
```

## Uwagi
Etykiety namespace:
```bash
kubectl label ns <ns> pod-security.kubernetes.io/enforce=baseline
kubectl label ns <ns> pod-security.kubernetes.io/warn=restricted pod-security.kubernetes.io/audit=restricted
kubectl label ns <ns> pod-security.kubernetes.io/enforce-version=v1.35     # opcjonalnie: przypięta wersja reguł
```

| Objaw | Przyczyna |
|---|---|
| `Warning: would violate PodSecurity …` przy apply | `warn` — pod powstanie, ale trzeba poprawić |
| Deployment jest, podów brak | `enforce` — przyczyna w `kubectl get events --field-selector reason=FailedCreate` |
| `CreateContainerConfigError`, `runAsNonRoot` | obraz działa jako root albo ma nienumeryczny `USER` |
| `CrashLoopBackOff`, `Read-only file system` | `readOnlyRootFilesystem` bez `emptyDir` na katalog, w którym aplikacja pisze |
