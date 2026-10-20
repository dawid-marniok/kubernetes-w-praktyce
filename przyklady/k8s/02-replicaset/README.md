# Przykłady: ReplicaSet

| Plik | Co pokazuje |
|---|---|
| `rs-nginx.yaml` | ReplicaSet z 3 replikami, selektor = etykiety szablonu |
| `pod-sierota.yaml` | adopcja: goły pod z pasującą etykietą zostaje przejęty przez ReplicaSet |
| `rs-selektor-zbiorowy.yaml` | `matchLabels` + `matchExpressions` (`environment in (dev,test)`) |

```bash
kubectl apply -f pod-sierota.yaml
kubectl apply -f rs-nginx.yaml
kubectl get pods -l app=przyklad-rs                 # 3 pody, w tym sierota
kubectl get pod przyklad-rs-sierota -o jsonpath='{.metadata.ownerReferences[0].name}{"\n"}'
kubectl delete pod -l app=przyklad-rs --wait=false  # usuń wszystkie — RS odtworzy 3
kubectl delete -f rs-nginx.yaml
```
Uwaga: dwa obiekty z tym samym selektorem w jednym namespace walczą o te same pody. Dlatego każdy przykład i lab ma własną etykietę.
