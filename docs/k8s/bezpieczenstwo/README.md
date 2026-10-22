# Dzień 4 — ściąga: RBAC, Pod Security, NetworkPolicy, CRD

Gotowe manifesty: `przyklady/k8s/17-rbac/`, `18-pod-security/`, `19-networkpolicy/`, `20-crd/`, `21-downward-api/`.

RBAC i ServiceAccount szerzej (symulator `can-i`, uwierzytelnianie na EKS, użytkownik z certyfikatem): [`../rbac/`](../rbac/README.md).

## Kim jestem i co mogę

```bash
kubectl auth whoami
kubectl auth can-i create deployments
kubectl auth can-i --list
kubectl auth can-i list pods --as=system:serviceaccount:<ns>:<sa>
kubectl create token <sa> --duration=10m
```

| Kod | Znaczy |
|---|---|
| 401 Unauthorized | zły lub wygasły dowód tożsamości (token, certyfikat, kubeconfig z innego klastra) |
| 403 Forbidden | wiem, kim jesteś, ale brakuje uprawnienia; komunikat podaje użytkownika, czasownik i zasób |

## RBAC w trzech komendach

```bash
kubectl create serviceaccount app-sa
kubectl create role pod-reader --verb=get,list,watch --resource=pods,pods/log
kubectl create rolebinding read-pods --role=pod-reader --serviceaccount=<ns>:app-sa
```

- Grupy API: `""` (pods, services, configmaps, secrets), `apps` (deployments, replicasets, statefulsets), `batch` (jobs, cronjobs), `networking.k8s.io` (ingresses, networkpolicies). Sprawdzisz w `kubectl api-resources`.
- Wbudowane ClusterRole: `view` (bez Secretów), `edit`, `admin`, `cluster-admin`.
- `automountServiceAccountToken: false` w SA albo podzie, gdy aplikacja nie rozmawia z API.

## securityContext dla poziomu restricted

```yaml
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 10001            # numeryczny UID zgodny z obrazem
    seccompProfile:
      type: RuntimeDefault
  containers:
  - name: app
    securityContext:
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true      # + emptyDir na katalogi, w których aplikacja pisze
      capabilities:
        drop: ["ALL"]
```

Etykiety namespace (wymagają `patch` na namespace; na szkoleniu masz je dla swojego, `enforce` tylko z `--dry-run=server`): `pod-security.kubernetes.io/enforce|warn|audit=privileged|baseline|restricted`.

## Skanowanie

```bash
trivy image --severity HIGH,CRITICAL --ignore-unfixed <obraz>:<tag>
trivy image --format cyclonedx -o sbom.json <obraz>:<tag>
trivy config <katalog z YAML>
trivy fs .                                   # zależności i sekrety w kodzie
kubescape scan framework nsa <katalog>
```

## NetworkPolicy

- Najpierw deny-all, potem DNS, potem pojedyncze strzałki (ingress po stronie celu + egress po stronie źródła).
- Namespace wybierasz etykietą `kubernetes.io/metadata.name: <nazwa>`.
- Internet: `ipBlock` (`0.0.0.0/0` z `except` sieci prywatnych), nie `namespaceSelector: {}`.
- Port = port kontenera.

| Komunikat w teście | Warstwa |
|---|---|
| `Resolving timed out`, `Could not resolve host`, `bad address` | DNS |
| `Connection timed out`, `download timed out` | polityka |
| `Connection refused` | aplikacja |

## DNS w podzie

```bash
kubectl exec <pod> -- cat /etc/resolv.conf
kubectl run t --rm -it --restart=Never --image=nicolaka/netshoot:v0.14 -- dig <service>.<ns>.svc.cluster.local
```

`<service>` w swoim namespace, `<service>.<ns>` w innym, `<pod>.<headless-service>` dla StatefulSetu. `ndots:5`: nazwy z mniej niż 5 kropkami najpierw dostają domeny z `search`.

## CRD i Downward API

```bash
kubectl get crd
kubectl api-resources --api-group=<grupa>
kubectl explain <typ>.spec
```

- CRD bez kontrolera nic nie robi. `kubectl delete crd` usuwa wszystkie obiekty tego typu.
- Jak działa CRD krok po kroku (diagramy, symulator, operatory, RBAC): [`../crd/`](../crd/).
- Downward API: env (`fieldRef`, `resourceFieldRef`) ustawiane przy starcie; wolumen `downwardAPI` odświeża etykiety i adnotacje.
