# Przykłady: RBAC i ServiceAccount

**Cel:** dać aplikacji (ServiceAccount) dokładnie te uprawnienia, których potrzebuje, i sprawdzić je, zanim coś się zepsuje.

**Gdzie:** klaster szkoleniowy EKS, Twój namespace (Role i RoleBinding w namespace). Zasobów klastrowych (ClusterRole, ClusterRoleBinding) nie tworzysz: na wspólnym klastrze robi to administrator. Komendy wydajesz w tym katalogu (`cd przyklady/k8s/17-rbac`).

| Plik | Co pokazuje |
|---|---|
| `developer-role.yaml` | Role z `resourceNames` (dostęp do jednego Secretu), SA, RoleBinding |
| `pod-reader-z-kubectl.yaml` | SA tylko do odczytu podów i pod z `registry.k8s.io/kubectl`, który tego konta używa |
| `ANTYWZORZEC-cluster-admin.yaml` | czego nie robić: `*/*/*` i `cluster-admin` dla aplikacji — **nie wgrywaj** |

```bash
NS=$(kubectl config view --minify -o jsonpath='{..namespace}'); echo $NS    # Twój namespace
```

## Krok po kroku

**1. Pod z kubectl na koncie tylko do odczytu**
```bash
kubectl apply -f pod-reader-z-kubectl.yaml
kubectl get pod test-readonly-sa -w          # Ctrl+C po Completed
kubectl logs test-readonly-sa
```
Co powinieneś zobaczyć: pod kończy się `Completed`, a w logach lista podów z Twojego namespace: kubectl w podzie użył tokenu ServiceAccount `pod-reader`.

**2. To samo konto próbuje usunąć pod**
```bash
kubectl run test-delete --image=registry.k8s.io/kubectl:v1.35.0 --restart=Never \
  --overrides='{"spec":{"serviceAccountName":"pod-reader"}}' -- delete pod test-readonly-sa
kubectl logs test-delete
```
Co powinieneś zobaczyć: `Error from server (Forbidden): pods "test-readonly-sa" is forbidden: User "system:serviceaccount:<ns>:pod-reader" cannot delete resource "pods" …`. Rola ma tylko `get` i `list`.

**3. Rola developera z dostępem do jednego Secretu**
```bash
sed "s/<NAMESPACE>/$NS/" developer-role.yaml | kubectl apply -f -
kubectl auth can-i get secrets/mongodb-secret --as=system:serviceaccount:${NS}:contoso
kubectl auth can-i get secrets/inny-secret   --as=system:serviceaccount:${NS}:contoso
kubectl auth can-i list secrets              --as=system:serviceaccount:${NS}:contoso
kubectl auth can-i --list                    --as=system:serviceaccount:${NS}:contoso
```
Co powinieneś zobaczyć: `yes`, `no`, `no` i listę reguł roli (na EKS z ostrzeżeniem `the list may be incomplete`). `${NS}` w klamrach celowo: w zsh `$NS:c…` obcina nazwę (`:c` to modyfikator zsh). `resourceNames` zawęża dostęp do jednego obiektu, ale nie działa z `list`. Jeśli zamiast odpowiedzi dostaniesz `cannot impersonate`, Twoje konto nie ma prawa `impersonate`: sprawdź to samo przez pod z kubectl jak w kroku 2.

**4. Antywzorzec: tylko przeczytaj**
```bash
cat ANTYWZORZEC-cluster-admin.yaml
```
Co powinieneś zobaczyć: ClusterRole `*/*/*` i ClusterRoleBinding z `cluster-admin` dla SA aplikacji. Włamanie do takiego poda = przejęcie klastra.

## Sprzątanie
```bash
kubectl delete -f pod-reader-z-kubectl.yaml
kubectl delete pod test-delete
sed "s/<NAMESPACE>/$NS/" developer-role.yaml | kubectl delete -f -
```

## Uwagi
Najważniejsze komendy:
```bash
kubectl create role pod-reader --verb=get,list,watch --resource=pods --dry-run=client -o yaml
kubectl create rolebinding read-pods --role=pod-reader --serviceaccount=<ns>:<sa> --dry-run=client -o yaml
kubectl auth can-i list pods --as=system:serviceaccount:<ns>:<sa>
kubectl auth can-i --list --as=system:serviceaccount:<ns>:<sa>
kubectl create token <sa> --duration=10m      # token na żądanie (od 1.24 SA nie dostaje Secretu z tokenem)
```
- RBAC ma tylko zezwolenia, uprawnienia się sumują. Nie ma reguł deny.
- `roleRef` w bindingu jest niezmienne: zmiana roli = nowy binding.
- Podzasoby osobno: `pods/log`, `pods/exec`.
- Lista w YAML zaczyna się myślnikiem `-`. Półpauza `–` skopiowana z dokumentu psuje plik.
- Od Kubernetes 1.22 tylko `rbac.authorization.k8s.io/v1` (`v1beta1` usunięte).
- Zasoby klastrowe (nodes, namespaces, CRD) wymagają ClusterRole + ClusterRoleBinding, a te nadaje administrator klastra. Gotową ClusterRole (np. `view`) możesz za to podpiąć RoleBindingiem w swoim namespace: działa wtedy tylko w nim.
- Na EKS ludzie logują się przez IAM (`aws eks update-kubeconfig`), a uprawnienia w klastrze nadaje wpis dostępu EKS (access entry) powiązany z rolą/grupą RBAC. Podom uprawnienia do usług AWS daje EKS Pod Identity albo IRSA, nie klucze w Secrecie.
