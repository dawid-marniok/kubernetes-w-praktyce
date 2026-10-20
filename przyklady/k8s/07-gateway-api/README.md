# Przykłady: Gateway API

Gateway API (`gateway.networking.k8s.io/v1`) to następca Ingressu. Trzy obiekty dla trzech ról:

| Obiekt | Kto | Co |
|---|---|---|
| GatewayClass | dostawca / kontroler | który kontroler obsługuje bramy (instaluje się z kontrolerem) |
| Gateway | zespół platformy | porty, protokoły, TLS, z których namespace'ów wolno się podpiąć |
| HTTPRoute | zespół aplikacji | host, ścieżka, wagi, filtry → Service |

| Plik | Co pokazuje |
|---|---|
| `gateway.yaml` | Gateway z listenerami HTTP i HTTPS, certyfikat z cert-managera (tworzy platforma) |
| `httproute.yaml` | host + `PathPrefix /` → Service, podpięty pod `przyklad-gw` |
| `httproute-canary.yaml` | wagi 90/10 między dwoma Service |
| `httproute-rewrite.yaml` | filtr `URLRewrite` (`/app1/x` → `/x`) |

Na szkoleniu Gateway API pokazuje prowadzący (demo); w labie ćwiczysz Ingress. Kolejność, gdy chcesz spróbować sam (na kind albo we własnym klastrze):
```bash
kubectl get crd | grep gateway.networking.k8s.io     # CRD nie są wbudowane w Kubernetesa
kubectl get gatewayclass
kubectl apply -f gateway.yaml                        # po podmianie <…>
kubectl get gateway przyklad-gw                      # PROGRAMMED True
kubectl get certificate                              # przyklad-gw-tls READY True (cert-manager)
kubectl apply -f httproute.yaml
kubectl describe httproute przyklad-route            # warunki Accepted i ResolvedRefs = True
curl -s https://gw-<login>.<DOMENA>
```

## Ingress a Gateway API: gdzie jest co
| | Ingress | Gateway API |
|---|---|---|
| wybór kontrolera | `ingressClassName: traefik` w Ingressie | `gatewayClassName: traefik` w Gatewayu |
| reguły host/ścieżka | w tym samym obiekcie | w HTTPRoute (`parentRefs` → Gateway) |
| certyfikat TLS | `spec.tls` + adnotacja cert-managera na Ingressie | listener HTTPS + adnotacja cert-managera na Gatewayu |
| wagi, nagłówki, rewrite | adnotacje / Middleware kontrolera | w specyfikacji (`weight`, `matches`, `filters`) |

## Na kind
Traefik z chartu Helm ma GatewayClass `traefik` i Gateway `traefik-gateway` (namespace `traefik`); wymaga wcześniej CRD Gateway API v1.5.x. Ruch: `kubectl port-forward -n traefik svc/traefik 8080:80`.

## Typowe problemy
- `Accepted=False` → zły `parentRefs` albo Gateway nie wpuszcza routów z Twojego namespace (`allowedRoutes`).
- `ResolvedRefs=False` → zła nazwa/port Service; Service w innym namespace wymaga `ReferenceGrant` w namespace docelowym.
- `no matches for kind "HTTPRoute"` → na klastrze nie ma CRD Gateway API.
