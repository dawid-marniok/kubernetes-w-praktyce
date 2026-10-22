# lab13 — RBAC i ServiceAccount w Twoim namespace

**Cel:** dajesz aplikacji (ServiceAccountowi) dokładnie te uprawnienia, których potrzebuje, i sprawdzasz je przez `kubectl auth can-i`, zanim cokolwiek wdrożysz.

**Po labie masz:** ServiceAccount `pod-reader-sa`, który może czytać pody i ich logi, ale nie może ich usuwać ani czytać Secretów, oraz pod, który używa tego konta do rozmowy z API.

## Zanim zaczniesz

- `kubectl` 1.34+ i dostęp do klastra szkoleniowego; Twój namespace (login) jest domyślny w kontekście. W tym labie **nie piszesz `-n`** ani `namespace:` w YAML-ach.
- Pliki startowe w tym katalogu: `role-pod-reader.yaml`, `nginx-sa.yaml`, `kubectl-test.yaml`.
- Sprawdź, kim jesteś i co możesz:

```bash
kubectl auth whoami
kubectl auth can-i create roles
kubectl auth can-i create rolebindings
```

Oba `can-i` powinny dać `yes`. Jeśli dostajesz `no`, napisz na czat.

W komendach poniżej `<login>` zamieniasz na swój login (np. `user07`). Pełna nazwa ServiceAccountu w RBAC to `system:serviceaccount:<namespace>:<nazwa>`.

## Poziom podstawowy

### 1. Role i RoleBinding dla czytelnika podów

1. Utwórz ServiceAccount:
   ```bash
   kubectl create serviceaccount pod-reader-sa
   ```
2. Uzupełnij `role-pod-reader.yaml` (miejsca `___`) i wgraj go: `kubectl apply -f role-pod-reader.yaml`.
3. Utwórz RoleBinding `read-pods`, który łączy rolę `pod-reader` z kontem `pod-reader-sa`. Możesz napisać YAML sam albo wygenerować go:
   ```bash
   kubectl create rolebinding read-pods --role=pod-reader \
     --serviceaccount=<login>:pod-reader-sa --dry-run=client -o yaml > rolebinding-read-pods.yaml
   ```
   Obejrzyj plik: `namespace` jest tylko w `subjects` (bez `-n` kubectl nie wpisuje go do `metadata`). Wgraj: `kubectl apply -f rolebinding-read-pods.yaml`.
4. Sprawdź uprawnienia z perspektywy konta aplikacji:
   ```bash
   SA=system:serviceaccount:<login>:pod-reader-sa
   kubectl auth can-i list pods --as=$SA
   kubectl auth can-i get pods --subresource=log --as=$SA
   kubectl auth can-i delete pods --as=$SA
   kubectl auth can-i get secrets --as=$SA
   ```

✅ `list pods` i `get pods/log` → `yes`, `delete pods` i `get secrets` → `no`.

### 2. Rola do zarządzania Deploymentami

Utwórz ServiceAccount `deploy-sa`, Role `deployment-manager` i RoleBinding `deploy-binding`. Rola ma pozwalać na `create, get, list, watch, update, patch, delete` dla **Deploymentów i ReplicaSetów**. Bez gwiazdki w `verbs`.

```bash
SA=system:serviceaccount:<login>:deploy-sa
kubectl auth can-i create deployments --as=$SA
kubectl auth can-i delete replicasets --as=$SA
kubectl auth can-i get secrets --as=$SA
kubectl auth can-i create deployments --as=$SA -n kube-system
```

✅ dwa pierwsze `yes`, dwa ostatnie `no`.

### 3. ServiceAccount w podzie

1. `kubectl create serviceaccount my-service-account`
2. Uzupełnij `nginx-sa.yaml` (jedno pole), wgraj i sprawdź, co kubelet zamontował w kontenerze:
   ```bash
   kubectl exec nginx-sa -- ls /var/run/secrets/kubernetes.io/serviceaccount
   kubectl exec nginx-sa -- cat /var/run/secrets/kubernetes.io/serviceaccount/namespace
   kubectl get pod nginx-sa -o jsonpath='{.spec.serviceAccountName}{"\n"}'
   ```
3. Utwórz ServiceAccount `app-sa` z wyłączonym montowaniem tokenu (`automountServiceAccountToken: false` w YAML) i Deployment `app-deploy` (2 repliki, `nginx:1.29`, etykieta `app: app`, `resources` jak w `nginx-sa.yaml`), który go używa.
   ```bash
   kubectl exec deploy/app-deploy -- ls /var/run/secrets/kubernetes.io/serviceaccount
   ```

✅ W `nginx-sa` są pliki `ca.crt`, `namespace`, `token`. W podach `app-deploy` katalogu nie ma (`No such file or directory`).

### 4. Pod rozmawia z API jako pod-reader-sa

```bash
kubectl apply -f kubectl-test.yaml
kubectl logs kubectl-test
```

Potem zmień w pliku `args` na `["delete", "pod", "nginx-sa"]`, usuń stary pod i uruchom ponownie:

```bash
kubectl delete pod kubectl-test
kubectl apply -f kubectl-test.yaml
kubectl logs kubectl-test
```

✅ Pierwszy przebieg wypisuje listę podów, drugi kończy się `Forbidden` z nazwą konta, czasownikiem i zasobem.

## SUKCES

- [ ] `can-i list pods` → `yes`, `can-i delete pods` → `no` dla `pod-reader-sa`
- [ ] `deploy-sa` zarządza Deploymentami, ale nie czyta Secretów i nie ma nic w `kube-system`
- [ ] pod `kubectl-test` listuje pody, a przy `delete` dostaje `Forbidden`

## Dla chętnych

- **Token na żądanie.** Wygeneruj krótki token i obejrzyj jego zawartość (to JWT, środkowa część to JSON):
  ```bash
  kubectl create token pod-reader-sa --duration=10m | cut -d. -f2 | base64 -d 2>/dev/null; echo
  ```
  Znajdź pola `sub`, `aud` i `exp`. Ile minut żyje token?
- **Brak Secretu z tokenem.** `kubectl get secrets` — czy powstał Secret dla któregoś z Twoich ServiceAccountów? Dlaczego nie?
- **imagePullSecrets na SA.** Utwórz Secret typu `docker-registry` (dane atrapy, np. serwer `<REJESTR>`, hasło `changeme`), ServiceAccount `image-puller` z `imagePullSecrets` i pod z tym SA. Sprawdź: `kubectl get pod <pod> -o jsonpath='{.spec.imagePullSecrets}'` — kto dopisał to pole do poda?
- **ClusterRole w jednym namespace.** ClusterRoleBindingów na wspólnym klastrze nie tworzysz, ale gotową ClusterRole możesz podpiąć zwykłym RoleBindingiem we własnym namespace. Utwórz ServiceAccount `viewer-sa` i RoleBinding `viewer-ns` do wbudowanej ClusterRole `view`:
  ```bash
  kubectl create serviceaccount viewer-sa
  kubectl create rolebinding viewer-ns --clusterrole=view --serviceaccount=<login>:viewer-sa
  SA=system:serviceaccount:<login>:viewer-sa
  kubectl auth can-i list deployments --as=$SA
  kubectl auth can-i get secrets --as=$SA
  kubectl auth can-i list pods --as=$SA -n kube-system
  kubectl auth can-i list nodes --as=$SA
  ```
  Które odpowiedzi Cię zaskoczyły? Teraz spróbuj dać temu samemu kontu ClusterRole `admin`:
  ```bash
  kubectl create rolebinding viewer-admin --clusterrole=admin --serviceaccount=<login>:viewer-sa
  ```
  RoleBindingi tworzyć możesz, a jednak API odmawia. Dlaczego?

## Wskazówki

**Gotowe wzorce manifestów:** [`przyklady/k8s/17-rbac/`](../../przyklady/k8s/17-rbac/). Skopiuj i przerób, zamiast pisać YAML od zera.

| Objaw | Co zrobić |
|---|---|
| `error: error parsing ...: did not find expected key` | Wcięcia albo zły znak na początku listy. W YAML lista zaczyna się zwykłym myślnikiem `-`, nie półpauzą `–` (częsty błąd po kopiowaniu z dokumentów) |
| RoleBinding jest, a `can-i` daje `no` | Literówka w nazwie SA albo namespace w `subjects`; `kubectl describe rolebinding read-pods` |
| `deployments` w `apiGroups: [""]` → `no` | Deployment i ReplicaSet są w grupie `apps` (`kubectl api-resources \| grep deploy`) |
| `kubectl logs` nie działa dla konta z `get pods` | Logi to osobny podzasób `pods/log` |
| `exceeded quota` / `must specify limits` | Każdy pod w Twoim namespace potrzebuje `resources.requests` i `limits` |
| `cannot impersonate` przy `--as` | Napisz na czat; zastępczo użyj kroku 4 (pod z kontem SA) |
| Chcesz zmienić rolę w RoleBindingu | `roleRef` jest niezmienne: usuń binding i utwórz od nowa |

Sprzątanie po labie: `kubectl delete pod kubectl-test nginx-sa` i `kubectl delete deploy app-deploy` (role i konta możesz zostawić).
