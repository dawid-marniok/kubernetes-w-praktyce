# Przykłady: GitOps z Argo CD i Helmem

**Cel:** zobaczyć, jak klaster sam dociąga stan z repozytorium Git. Nikt nie robi `kubectl apply` na produkcji: zmiana to commit, a Argo CD w klastrze ją wdraża i pilnuje, żeby nikt jej ręcznie nie zmienił.

**Gdzie:** na szkoleniu pokazuje to prowadzący (Argo CD instaluje się w całym klastrze, kursanci nie mają do tego uprawnień). Po szkoleniu: na własnym kind, krok po kroku niżej.

## GitOps w pięciu zdaniach

1. Stan klastra opisują pliki w Gicie (chart Helm z wartościami, czysty YAML albo Kustomize). Git jest źródłem prawdy.
2. W klastrze działa agent (Argo CD albo Flux), który sam pobiera zmiany z repo (pull). CI nie potrzebuje kubeconfiga do produkcji.
3. Zmiana w klastrze = commit i merge request. Historia zmian i audyt to historia gita.
4. Ręczna zmiana w klastrze (`kubectl edit`, `scale`, `delete`) to **drift**: agent ją widzi i przy włączonym self-heal przywraca stan z gita.
5. Rollback = `git revert`.

## Przepływ

```
  ty                    repozytorium Git                 klaster Kubernetes
  ──                    ────────────────                 ──────────────────
  edycja values-prod.yaml
  git commit + push ──► main: app/ (chart)       ◄─────── Argo CD (namespace argocd)
                                                  pull     │ co 3 min albo Refresh
                                                           │ 1. helm template + values-prod.yaml (repo-server)
                                                           │ 2. porównanie: git vs klaster
                                                           │ 3. różnica → sync (kubectl apply)
                                                           ▼
                                                     namespace gitops-demo
                                                     Deployment, Service, ConfigMap
                                                           ▲
  kubectl scale/edit/delete ───── drift ───────────────────┘
                                  self-heal: Argo CD przywraca stan z gita po kilku sekundach
```

## Pliki

| Plik | Co pokazuje |
|---|---|
| `app/` | chart podinfo (mała aplikacja webowa z napisem i kolorem): Deployment, Service, ConfigMap |
| `app/values.yaml` | wartości wspólne: 1 replika, napis `baza` |
| `app/values-dev.yaml` | podinfo 6.15.0, napis `dev`, zielony |
| `app/values-prod.yaml` | 2 repliki, podinfo 6.14.1, napis `prod v1`, granatowy. Te wartości wdraża Argo CD |
| `application.yaml` | Argo CD `Application`: repo, ścieżka chartu, plik wartości, namespace docelowy, automatyczny sync z `prune` i `selfHeal` |

Ten sam podział co w lab17: jeden chart, osobny plik wartości na środowisko.

## Helm w Argo CD: co tu się dzieje

Podgląd bez klastra (w tym katalogu):
```bash
helm template podinfo-prod app -f app/values-prod.yaml
diff <(helm template podinfo-prod app -f app/values-dev.yaml) <(helm template podinfo-prod app -f app/values-prod.yaml)
```
Co zobaczysz:
- nazwy obiektów od nazwy releasu: `podinfo-prod`, `podinfo-prod-config`. Argo CD ustawia release na nazwę Application;
- `replicas: 2` i tag `6.14.1` z `values-prod.yaml`, bez edycji szablonu;
- adnotacja `checksum/config` w szablonie poda: suma kontrolna ConfigMapy. Zmiana napisu = inna suma = nowy szablon poda = rollout. Bez niej zmiana ConfigMapy nie restartuje podów (dzień 2).

Argo CD robi dokładnie to samo: widzi `Chart.yaml` w ścieżce i uruchamia `helm template` z plikami z `valueFiles`, a wynik porównuje z klastrem. Nie robi `helm install`, więc `helm list` jest pusty, a historią wdrożeń jest git (i zakładka History w Argo CD), nie Secrety Helma. Czysty YAML i Kustomize obsługuje tak samo.

## Spróbuj sam (kind, po szkoleniu)

Potrzebujesz: kind, kubectl, helm, konto na GitHubie.

**1. Fork i klaster**

Zrób fork tego repo na GitHubie (przycisk Fork), potem:
```bash
kind create cluster --name gitops
```

**2. Argo CD**
```bash
helm repo add argo https://argoproj.github.io/argo-helm
helm install argocd argo/argo-cd --version 10.10.5 -n argocd --create-namespace \
  --set dex.enabled=false --set notifications.enabled=false --wait
kubectl get pods -n argocd
```
Co powinieneś zobaczyć: `argocd-server`, `argocd-repo-server`, `argocd-application-controller-0`, `argocd-redis`, `argocd-applicationset-controller` w stanie `Running` (Argo CD 3.5).

**3. UI**

Drugi terminal:
```bash
kubectl -n argocd port-forward svc/argocd-server 8080:443
```
Otwórz https://localhost:8080 (certyfikat samopodpisany, zaakceptuj). Login `admin`, hasło:
```bash
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d; echo
```

**4. Application wskazująca na Twój fork**

W `application.yaml` zmień `repoURL` na adres swojego forka (`https://github.com/<Twój-login>/kubernetes-w-praktyce.git`), potem:
```bash
kubectl apply -f application.yaml
kubectl get applications -n argocd
kubectl get all -n gitops-demo
```
Co powinieneś zobaczyć: `podinfo-prod` z `Synced` i `Healthy` po kilkunastu sekundach, dwa pody `podinfo-prod-…`. W UI: drzewo Application → Service, ConfigMap, Deployment → ReplicaSet → Pody.

Aplikacja w przeglądarce: `kubectl -n gitops-demo port-forward svc/podinfo-prod 9898:9898` → http://localhost:9898 (napis `prod v1`, granatowe tło).

**5. Drift: zmiana ręczna**
```bash
kubectl get pods -n gitops-demo -w          # drugi terminal
kubectl scale deploy podinfo-prod -n gitops-demo --replicas=5
kubectl delete svc podinfo-prod -n gitops-demo
```
Co powinieneś zobaczyć: 3 nowe pody i po ok. 2 s ich `Terminating`; Service wraca po kilku sekundach. W UI → podinfo-prod → History and Rollback i zdarzenia: automatyczny sync.

**6. Zmiana w gicie**

W swoim forku w `app/values-prod.yaml` zmień `message: prod v1` na np. `prod v2` i `color`. Commit i push (albo edycja w przeglądarce na GitHubie). Potem jedno z trzech:
- czekaj do 3 min (Argo CD odpytuje repo co 120 s + do 60 s),
- w UI kliknij **Refresh**,
- `kubectl -n argocd annotate application podinfo-prod argocd.argoproj.io/refresh=normal --overwrite`

Co powinieneś zobaczyć: ConfigMapa z nową treścią, nowa suma `checksum/config` w szablonie poda, pody się wymieniają, po odświeżeniu strony nowy napis i kolor.

**7. Rollback**
```bash
git revert --no-edit HEAD && git push
```
Po odświeżeniu: znowu `prod v1`, ta sama suma `checksum/config` co na początku (ta sama treść).

## Sprzątanie
```bash
kubectl delete -f application.yaml       # finalizer usuwa też Deployment, Service i ConfigMapę
kubectl delete namespace gitops-demo
kind delete cluster --name gitops
```

## Warto wiedzieć

- **Sekrety nie trafiają do gita jawnym tekstem.** W GitOps: External Secrets (przykład `25-external-secrets/`), Sealed Secrets albo SOPS.
- **Webhook zamiast czekania.** GitHub może powiadomić Argo CD o pushu (webhook), wtedy sync rusza od razu. Wymaga adresu Argo CD dostępnego z internetu.
- **Wiele środowisk i klastrów.** `ApplicationSet` generuje wiele Application z jednego wzoru (np. dev i prod z dwóch plików wartości). Flux robi to samo innymi CRD (`GitRepository`, `HelmRelease`).
- **GitOps a zwykły pipeline CI/CD:** ściąga [`docs/k8s/gitops/`](../../../docs/k8s/gitops/README.md) i [wizualizacja](../../../docs/k8s/gitops/gitops.html): push i pull krok po kroku, symulator driftu, plusy i minusy.
- **Dokumentacja:** https://argo-cd.readthedocs.io/en/stable/ (Getting Started, Automated Sync Policy, Helm)
