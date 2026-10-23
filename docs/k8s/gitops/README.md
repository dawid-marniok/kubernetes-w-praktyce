# Dzień 5 · ściąga: GitOps z Argo CD a zwykły pipeline CI/CD

**Wizualizacja:** [gitops.html](gitops.html). Otwórz plik w przeglądarce (dwuklik albo `open gitops.html`). Jest tam model push i pull krok po kroku, symulator driftu z przełączaniem trybów (`automated`, `selfHeal`, `prune`), obiekt `Application` z opisem pól, porównanie „kto ma klucze do klastra” i tabela plusów i minusów z filtrem.

Demo prowadzącego z plikami: [`przyklady/k8s/29-gitops-argocd/`](../../../przyklady/k8s/29-gitops-argocd/README.md). Na szkoleniu tylko oglądasz: Argo CD działa na naszym EKS, kursanci nie mają tam konta.

## W skrócie

1. **Push:** pipeline (GitHub Actions, GitLab CI) robi testy, build, push obrazu i sam wgrywa zmianę do klastra (`helm upgrade --install`). Do tego CI musi mieć kubeconfig albo rolę IAM z dostępem do klastra. Po wdrożeniu pipeline kończy pracę i nikt nie pilnuje klastra.
2. **Pull (GitOps):** CI robi testy, build, push obrazu i commit z nowym tagiem do repo konfiguracji. Argo CD w klastrze sam odpytuje repo (co 120 s + do 60 s, Refresh albo webhook: od razu), renderuje manifesty (`helm template`) i robi sync.
3. **Argo CD nie nasłuchuje na push.** To pętla rekoncyliacji, jak kontroler z dnia 4: obserwuj, porównaj git z klastrem, działaj. Dlatego widzi też ręczne zmiany w klastrze (drift).
4. **Tryby:** bez `automated` Argo CD tylko pokazuje OutOfSync i Diff. `automated` wdraża nowe commity. `selfHeal` cofa ręczne zmiany (u nas `scale` wraca w mniej niż 2 s). `prune` usuwa z klastra to, co zniknęło z gita.
5. **Argo CD nie robi `helm install`:** `helm list` jest pusty, `helm rollback` nie działa. Historia to git, rollback to `git revert`. Flux robi prawdziwy release przez `HelmRelease`.
6. **Bezpieczeństwo:** w push klucze do produkcji leżą w CI. W pull zostają w klastrze, a CI potrzebuje tylko prawa zapisu do repo. Za to zapis do repo konfiguracji staje się dostępem do klastra: branch protection i review są obowiązkowe.
7. **Cena GitOps:** commit to jeszcze nie wdrożenie (do ok. 3 min), wynik trzeba sprawdzać w Argo CD, migracje robi się hookami `PreSync`, a sam Argo CD jest kolejną aplikacją do utrzymania. Sekrety nie trafiają do gita jawnym tekstem: [sekrety z sejfu](../sekrety/README.md).
8. **Najczęściej model mieszany:** CI buduje i podbija tag w gicie, Argo CD wdraża i pilnuje. Push wystarcza przy jednym klastrze i małym zespole.

Dokumentacja: https://argo-cd.readthedocs.io/en/stable/ (Argo CD 3.5, chart `argo/argo-cd` 10.10.5).
