# Przykłady: GitOps z Argo CD i Kustomize

**Cel:** zobaczyć, jak klaster sam dociąga stan z repozytorium Git. Nikt nie robi `kubectl apply` na produkcji: zmiana to commit, a Argo CD w klastrze ją wdraża i pilnuje, żeby nikt jej ręcznie nie zmienił.

**Gdzie:** na szkoleniu pokazuje to prowadzący (Argo CD instaluje się w całym klastrze, kursanci nie mają do tego uprawnień). Po szkoleniu: na własnym kind, krok po kroku niżej.

## GitOps w pięciu zdaniach

1. Stan klastra opisują pliki w Gicie (YAML, Kustomize, chart Helm). Git jest źródłem prawdy.
2. W klastrze działa agent (Argo CD albo Flux), który sam pobiera zmiany z repo (pull). CI nie potrzebuje kubeconfiga do produkcji.
3. Zmiana w klastrze = commit i merge request. Historia zmian i audyt to historia gita.
4. Ręczna zmiana w klastrze (`kubectl edit`, `scale`, `delete`) to **drift**: agent ją widzi i przy włączonym self-heal przywraca stan z gita.
5. Rollback = `git revert`.

## Przepływ

```
  ty                    repozytorium Git                 klaster Kubernetes
  ──                    ────────────────                 ──────────────────
  edycja overlays/prod
  git commit + push ──► main: app/overlays/prod  ◄─────── Argo CD (namespace argocd)
                                                  pull     │ co 3 min albo Refresh
                                                           │ 1. kustomize build (repo-server)
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
| `app/base/` | podinfo (mała aplikacja webowa z napisem i kolorem): Deployment, Service, ConfigMap z `configMapGenerator` |
| `app/overlays/dev/` | 1 replika, podinfo 6.15.0, napis `dev`, zielony |
| `app/overlays/prod/` | 2 repliki, podinfo 6.14.1, napis `prod v1`, granatowy. Tę nakładkę wdraża Argo CD |
| `application.yaml` | Argo CD `Application`: repo, ścieżka, namespace docelowy, automatyczny sync z `prune` i `selfHeal` |

Ten sam układ base + overlays co w lab17 (katalog `kustomize/`), tylko z obrazem, który pokazuje wersję i kolor w przeglądarce.

## Kustomize: co tu się dzieje

Kustomize nie ma szablonów. Baza to zwykły YAML, nakładka mówi tylko, co zmienić. Podgląd bez klastra (w tym katalogu):
```bash
kubectl kustomize app/overlays/prod
diff <(kubectl kustomize app/overlays/dev) <(kubectl kustomize app/overlays/prod)
```
Co zobaczysz:
- `nameSuffix: -prod` → `podinfo-prod`, i to w Deploymencie, Service i odwołaniu do ConfigMapy;
- `labels` z `includeSelectors: true` → `env: prod` także w selektorach (dev i prod się nie mieszają);
- `images` → tag `6.14.1` bez edycji Deploymentu;
- `replicas` → 2;
- `configMapGenerator` z `behavior: merge` → ConfigMap `podinfo-config-prod-<hash>`. Hash liczy się z treści: zmiana napisu = nowa nazwa ConfigMapy = nowy szablon poda = rollout. Bez generatora zmiana ConfigMapy nie restartuje podów (dzień 2).

Argo CD robi dokładnie to samo: widzi `kustomization.yaml` w ścieżce i uruchamia `kustomize build`. Charty Helm i czysty YAML obsługuje tak samo.

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

W swoim forku w `app/overlays/prod/kustomization.yaml` zmień `PODINFO_UI_MESSAGE=prod v1` na np. `prod v2` i kolor `PODINFO_UI_COLOR`. Commit i push (albo edycja w przeglądarce na GitHubie). Potem jedno z trzech:
- czekaj do 3 min (Argo CD odpytuje repo co 120 s + do 60 s),
- w UI kliknij **Refresh**,
- `kubectl -n argocd annotate application podinfo-prod argocd.argoproj.io/refresh=normal --overwrite`

Co powinieneś zobaczyć: nowa ConfigMapa z innym hashem, stara znika (`prune: true`), pody się wymieniają, po odświeżeniu strony nowy napis i kolor.

**7. Rollback**
```bash
git revert --no-edit HEAD && git push
```
Po odświeżeniu: znowu `prod v1`, ConfigMapa z tym samym hashem co na początku.

## Sprzątanie
```bash
kubectl delete -f application.yaml       # finalizer usuwa też Deployment, Service i ConfigMapę
kubectl delete namespace gitops-demo
kind delete cluster --name gitops
```

## Warto wiedzieć

- **Sekrety nie trafiają do gita jawnym tekstem.** W GitOps: External Secrets (przykład `25-external-secrets/`), Sealed Secrets albo SOPS.
- **Webhook zamiast czekania.** GitHub może powiadomić Argo CD o pushu (webhook), wtedy sync rusza od razu. Wymaga adresu Argo CD dostępnego z internetu.
- **Wiele środowisk i klastrów.** `ApplicationSet` generuje wiele Application z jednego wzoru (np. dev i prod z dwóch nakładek). Flux robi to samo innymi CRD (`GitRepository`, `Kustomization`, `HelmRelease`).
- **Dokumentacja:** https://argo-cd.readthedocs.io/en/stable/ (Getting Started, Automated Sync Policy), https://kubectl.docs.kubernetes.io/references/kustomize/
