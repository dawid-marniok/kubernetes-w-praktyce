# Przykłady: ReplicaSet

**Cel:** zobaczyć, jak ReplicaSet pilnuje liczby podów i że „swoje” pody rozpoznaje wyłącznie po etykietach.

**Gdzie:** klaster szkoleniowy EKS, Twój namespace. Komendy wydajesz w tym katalogu (`cd przyklady/k8s/02-replicaset`).

| Plik | Co pokazuje |
|---|---|
| `rs-nginx.yaml` | ReplicaSet z 3 replikami, selektor = etykiety szablonu |
| `pod-sierota.yaml` | adopcja: goły pod z pasującą etykietą zostaje przejęty przez ReplicaSet |
| `rs-selektor-zbiorowy.yaml` | `matchLabels` + `matchExpressions` (`environment in (dev,test)`) |

W drugim terminalu: `kubectl get pods -l app=przyklad-rs -w`.

## Krok po kroku

**1. Pod-sierota, potem ReplicaSet**
```bash
kubectl apply -f pod-sierota.yaml
kubectl apply -f rs-nginx.yaml
kubectl get pods -l app=przyklad-rs
kubectl get pod przyklad-rs-sierota -o jsonpath='{.metadata.ownerReferences[0].name}{"\n"}'
```
Co powinieneś zobaczyć: 3 pody, w tym `przyklad-rs-sierota`, i tylko 2 nowe `przyklad-rs-…`. Właściciel sieroty to `przyklad-rs`: ReplicaSet ją adoptował, bo pasuje etykietami.

**2. ReplicaSet odtwarza pody**
```bash
kubectl delete pod -l app=przyklad-rs --wait=false
kubectl get pods -l app=przyklad-rs
```
Co powinieneś zobaczyć: stare pody `Terminating`, od razu 3 nowe `przyklad-rs-…` (sierota nie wraca, nowe pody mają nazwy z szablonu).

**3. Skalowanie**
```bash
kubectl scale rs przyklad-rs --replicas=5
kubectl get rs przyklad-rs
```
Co powinieneś zobaczyć: `DESIRED 5`, `CURRENT 5`, po chwili `READY 5`.

**4. Selektor z wyrażeniem**
```bash
kubectl apply -f rs-selektor-zbiorowy.yaml
kubectl get pods -l 'app=przyklad-rs-env,environment in (dev,test)'
```
Co powinieneś zobaczyć: 2 pody z etykietami `app=przyklad-rs-env` i `environment=dev`.

## Sprzątanie
```bash
kubectl delete -f rs-nginx.yaml -f rs-selektor-zbiorowy.yaml
kubectl delete -f pod-sierota.yaml --ignore-not-found
```

## Uwagi
- Dwa obiekty z tym samym selektorem w jednym namespace walczą o te same pody. Dlatego każdy przykład i lab ma własną etykietę.
- Na co dzień nie piszesz ReplicaSetów: Deployment tworzy je sam (`../03-deployment/`).
- Zmiana szablonu w ReplicaSecie nie podmienia działających podów, dotyczy tylko nowych. Podmianę robi dopiero Deployment.
