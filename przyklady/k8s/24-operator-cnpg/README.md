# Przykłady: operator CloudNativePG i failover

**Cel:** zobaczyć operator w akcji: usuwasz pod primary PostgreSQL, a operator sam promuje replikę i przepina Service `pg-rw`. Dane zostają.

**Gdzie:** klaster szkoleniowy EKS, Twój namespace. Operator CloudNativePG instaluje prowadzący; Ty tworzysz obiekt `Cluster` (rola `edit` obejmuje typy CNPG). Komendy wydajesz w tym katalogu (`cd przyklady/k8s/24-operator-cnpg`).

| Plik | Co pokazuje |
|---|---|
| `pg-cluster.yaml` | `Cluster` z 3 instancjami PostgreSQL 17: jeden obiekt zamiast StatefulSetu, Service'ów, Secretów i skryptów replikacji |

To samo krok po kroku, od jednej instancji, robisz w [`labs/lab18-operator-cnpg/`](../../../labs/lab18-operator-cnpg/). Jeśli masz już klaster `pg` z labu, nie wgrywaj drugiego: nazwa jest ta sama.

## Krok po kroku

**0. Klaster i dane testowe** (pierwszy start 2–3 min)
```bash
kubectl apply -f pg-cluster.yaml
kubectl get cluster pg -w                # Ctrl+C po „Cluster in healthy state”
P=$(kubectl get cluster pg -o jsonpath='{.status.currentPrimary}')
kubectl exec "$P" -c postgres -- psql -d app -c "create table t(x int); insert into t values (1),(2),(3);"
```

**1. Kto jest primary**
```bash
kubectl get cluster pg
kubectl get endpointslices -l kubernetes.io/service-name=pg-rw -o wide
kubectl get pods -o wide -L cnpg.io/instanceRole
```
Co powinieneś zobaczyć: `PRIMARY pg-1`, `Cluster in healthy state`; adres w endpointach `pg-rw` to adres poda `pg-1`. Aplikacja zna tylko nazwę `pg-rw`, zawsze wskazuje ona primary.

**2. Awaria**

Drugi terminal: `kubectl get pods -L cnpg.io/instanceRole -w`. W pierwszym:
```bash
kubectl delete pod pg-1                  # albo nazwa primary z kroku 1
kubectl get cluster pg -w                # Ctrl+C po „Cluster in healthy state”
```
Co powinieneś zobaczyć: `Failing over` → `Waiting for the instances to become active` → `Cluster in healthy state`, nowy `PRIMARY` (`pg-2` albo `pg-3`). Na próbie trwało to ok. 13 s. Sam StatefulSet zrestartowałby poda, ale z repliki primary by nie zrobił.

**3. Service i dane**
```bash
kubectl get endpointslices -l kubernetes.io/service-name=pg-rw -o wide
kubectl exec -it pg-2 -c postgres -- psql -d app -c "select * from t;"   # nazwa nowego primary
kubectl get pods -L cnpg.io/instanceRole
```
Co powinieneś zobaczyć: nowy adres w `pg-rw`, trzy wiersze w `t`, a `pg-1` wraca jako `replica`.

**4. Co robił operator** (logi operatora w namespace `cnpg-system` możesz czytać, zmieniać nic tam nie możesz)
```bash
kubectl logs -n cnpg-system deploy/cnpg-cloudnative-pg --since=2m | grep -i failover | head -3
```
Co powinieneś zobaczyć: `Current primary isn't healthy, initiating a failover`.

## Sprzątanie
```bash
kubectl delete -f pg-cluster.yaml
kubectl get pvc -l cnpg.io/cluster=pg         # pusto: PVC należą do Cluster (ownerReference) i znikają razem z nim
```
Przed projektem końcowym posprzątaj: trzy instancje zajmują sporą część quoty namespace'u.

## Uwagi
- Operator = CRD + kontroler (dzień 4) z wiedzą administratora bazy w kodzie. Replika to nadal nie backup: do backupu jest obiekt `ScheduledBackup` (lab18, „Dla chętnych”).
- Plugin `kubectl cnpg` (`kubectl krew install cnpg`): `kubectl cnpg status pg`, kontrolowany switchover `kubectl cnpg promote pg pg-1`.
- Zanim postawisz bazę z chartu, sprawdź, czy jest do niej operator (CloudNativePG, Strimzi dla Kafki, MongoDB Community Operator) i co robi przy awarii.
