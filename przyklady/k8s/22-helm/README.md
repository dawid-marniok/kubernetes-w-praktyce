# 22 · Helm: przykładowy chart

Gotowy chart do przeczytania i porównania z tym, co generuje `helm create`: [`example-chart/`](example-chart/) (opis w [`example-chart/README.md`](example-chart/README.md)).

```bash
helm lint example-chart
helm template demo example-chart | less          # zwykłe manifesty, nic nie trafia do klastra
helm upgrade --install demo example-chart --wait # w swoim namespace
helm uninstall demo
```

## Na zajęciach: od `helm create` do rollbacku

```bash
helm create demo-chart                       # szkielet: Deployment, Service, Ingress, HTTPRoute, HPA, _helpers.tpl
# w demo-chart/values.yaml: image.repository: nginx, image.tag: "1.29" (w cudzysłowie!), resources z requests/limits
helm lint ./demo-chart
helm template demo ./demo-chart | grep image:
helm upgrade --install demo ./demo-chart --wait          # REVISION 1
helm upgrade demo ./demo-chart --set replicaCount=3 --wait
helm upgrade demo ./demo-chart --set replicaCount=3 --set image.tag=9.99   # bez --wait
helm history demo                            # rewizja 3: deployed, choć pod ma ImagePullBackOff
helm rollback demo 2 --wait                  # rewizja 4 „Rollback to 2”
kubectl get secret -l owner=helm             # historia release'u to Secrety w namespace
helm uninstall demo && rm -rf demo-chart
```

Bez `--wait` Helm uznaje sukces, gdy API przyjęło YAML; czy aplikacja działa, mówią mu dopiero `--wait` i sondy. W CI: `helm upgrade --install … --wait --rollback-on-failure --timeout 5m` (Helm 3: `--atomic`). Podgląd zmian przed upgrade'em: plugin [helm-diff](https://github.com/databus23/helm-diff) (`helm diff upgrade …`).

Ćwiczysz w [`labs/lab17-helm/`](../../../labs/lab17-helm/), składnia szablonów: [`docs/k8s/helm/skladnia.md`](../../../docs/k8s/helm/skladnia.md).
