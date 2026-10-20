# Przykłady: Ingress

| Plik | Co pokazuje |
|---|---|
| `ingress.yaml` | host → Service; host z Twoim loginem do uzupełnienia |
| `ingress-sciezki.yaml` | jeden host, dwie ścieżki (`Prefix`) |
| `ingress-tls.yaml` | TLS z cert-managera (Let's Encrypt): adnotacja + sekcja `tls`; wariant z własnym Secretem w komentarzu |
| `cluster-issuer.yaml` | cert-manager + Let's Encrypt (produkcja, staging w komentarzu), solver HTTP-01 — obiekt klastrowy, tworzy administrator |

Miejsca `<…>` są celowo niepoprawne — `kubectl apply` bez ich podmiany kończy się błędem walidacji.

## Jaka klasa?
```bash
kubectl get ingressclass
```
| Środowisko | Klasa | Host | Jak wejść |
|---|---|---|---|
| klaster szkoleniowy (EKS) | `traefik` | `<login>.<DOMENA>` (domena od trenera; DNS wildcard → load balancer) | `curl http://<login>.<DOMENA>`, przeglądarka: `https://` z cert-managerem |
| kind z Traefikiem | `traefik` | `<login>.local` | `kubectl port-forward -n traefik svc/traefik 8080:80`, `curl -H "Host: <login>.local" localhost:8080` |

Host tylko jeden poziom pod domeną: `apps-<login>.<DOMENA>`, nie `apps.<login>.<DOMENA>`. Więcej: [`docs/k8s/ingress-gateway/README.md`](../../../docs/k8s/ingress-gateway/README.md).

## Stan obecny
- API `networking.k8s.io/v1` (Ingress) jest stabilne i zostaje. `extensions/v1beta1` i `networking.k8s.io/v1beta1` nie istnieją od 1.22.
- Community **ingress-nginx** (kubernetes/ingress-nginx) jest wycofany: koniec utrzymania 03.2026, bez poprawek bezpieczeństwa. Adnotacja `configuration-snippet` jest w nim domyślnie wyłączona od CVE-2025-1974. Nowe projekty: Gateway API (`../07-gateway-api/`).
- Wszystko poza hostem, ścieżką i TLS (rewrite, przekierowania, limity) to adnotacje konkretnego kontrolera — przy zmianie kontrolera do przepisania.
- `pathType: ImplementationSpecific` zależy od kontrolera — unikaj.
