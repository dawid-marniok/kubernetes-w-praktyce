# Przykłady: Service

| Plik | Typ | Co pokazuje |
|---|---|---|
| `clusterip.yaml` | ClusterIP | domyślny, ruch wewnątrz klastra; `targetPort` jako nazwa portu |
| `nodeport.yaml` | NodePort | port na każdym węźle, **bez** sztywnego `nodePort` |
| `loadbalancer.yaml` | LoadBalancer | adres od chmury; tylko za zgodą (koszt, publiczne IP) |
| `headless.yaml` | headless | `clusterIP: None`, DNS zwraca IP podów |
| `externalname.yaml` | ExternalName | CNAME do nazwy spoza klastra |
| `pusty-endpointslice.yaml` | ClusterIP | selektor bez podów → pusty EndpointSlice |

Wszystkie (poza ExternalName i pustym) wskazują pody z `../03-deployment/deployment-rolling.yaml` (`app: przyklad-deploy`).

```bash
kubectl apply -f ../03-deployment/deployment-rolling.yaml -f clusterip.yaml
kubectl get endpointslices -l kubernetes.io/service-name=przyklad-deploy
kubectl exec deploy/przyklad-deploy -- curl -s http://przyklad-deploy | head -4
kubectl exec deploy/przyklad-deploy -- getent hosts przyklad-deploy
kubectl port-forward svc/przyklad-deploy 8080:80       # http://localhost:8080
```
- `kubectl get endpoints` jest wycofane od 1.33 — używaj `endpointslices`.
- W obrazie nginx jest `curl` i `getent`, nie ma `wget` ani `nslookup`.
