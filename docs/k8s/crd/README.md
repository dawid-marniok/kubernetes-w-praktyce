# Dzień 4 — ściąga: CRD, czyli własny typ w API

**Wizualizacja:** [crd.html](crd.html). Otwórz plik w przeglądarce (dwuklik albo `open crd.html`). Jest tam diagram całości, symulator (wgrywasz CRD i obiekt `Backup`, psujesz walidację, włączasz i wyłączasz kontroler, usuwasz CRD), pętla kontrolera, cert-manager i CloudNativePG jako ten sam wzorzec, anatomia CRD i RBAC.

Gotowe manifesty: [`przyklady/k8s/20-crd/`](../../../przyklady/k8s/20-crd/) (`crd-backup.yaml`, `backup-nightly.yaml`, `rbac-backups-edit.yaml`). Lab: [`labs/lab16-downward-api-crd/`](../../../labs/lab16-downward-api-crd/).

## Jak działa CRD w 5 punktach

1. **CRD to obiekt, który dopisuje typ do API.** Po `kubectl apply` CRD `backups.szkolenie.example.com` kube-apiserver obsługuje nowy endpoint `/apis/szkolenie.example.com/v1/namespaces/<ns>/backups` i ogłasza go w discovery: `kubectl api-resources` pokazuje `backups` ze skrótem `bk`, a `kubectl explain backup.spec` czyta opisy pól ze schematu.
2. **Obiekt nowego typu przechodzi te same bramki co Pod:** uwierzytelnienie, RBAC (zasób `backups` w grupie `szkolenie.example.com`), admission, a do tego walidację schematem z CRD. `retention: 0` odrzuca `minimum: 1`, pole spoza schematu odrzuca walidacja Strict (z `--validate=warn` kubectl tylko ostrzega, a kube-apiserver usuwa pole przed zapisem: pruning). Potem zapis w etcd.
3. **Na tym koniec.** Bez kontrolera obiekt `Backup` to tylko rekord w etcd: `kubectl get bk` działa, żaden backup się nie wykonuje.
4. **Kontroler daje działanie.** Osobny program w podzie obserwuje obiekty (watch), porównuje stan zadany ze stanem rzeczywistym i doprowadza do zgodności: tworzy np. CronJob z `ownerReferences` i zapisuje `status`. Robi to bez końca, nie raz.
5. **CRD + kontroler z wiedzą o aplikacji = operator.** cert-manager: `Certificate` → Secret z certyfikatem TLS. CloudNativePG (dzień 5): `Cluster` → pody, PVC, Service'y `pg-rw`/`pg-ro`/`pg-r`, Secret `pg-app`.

## Najważniejsze pola CRD

| Pole | Co daje |
|---|---|
| `metadata.name` | zawsze `<plural>.<group>` |
| `scope` | `Namespaced` (obiekty w namespace, jak Pod) albo `Cluster` (jak Node) |
| `versions[].served` / `storage` | wersja dostępna w API / wersja zapisywana w etcd (dokładnie jedna) |
| `schema.openAPIV3Schema` | obowiązkowy: typy, `required`, `minimum`; usuwa pola spoza schematu; źródło dla `kubectl explain` |
| `additionalPrinterColumns` | dodatkowe kolumny w `kubectl get` |
| `subresources.status` | osobny endpoint `/status`: użytkownik pisze `spec`, kontroler `status` |
| `x-kubernetes-validations` | reguły CEL w kube-apiserverze, np. `self.retention <= 30` (GA od 1.29) |

## Kto co może

- **CRD tworzy administrator klastra** (zasób klastrowy `customresourcedefinitions` w grupie `apiextensions.k8s.io`). Na naszym klastrze: trener. Ty możesz je czytać (`kubectl get crd`).
- **Obiekty `Backup` tworzysz Ty** w swoim namespace. Prawo dostajesz przez ClusterRole z etykietą `rbac.authorization.k8s.io/aggregate-to-edit: "true"` (`rbac-backups-edit.yaml`, wgrywa trener), której reguły kube-controller-manager dokleja do wbudowanej roli `edit`.
- Do `view` nic nie doklejono, więc `kubectl get bk -A` daje Ci `forbidden`.

## Komendy

```bash
kubectl get crd                                           # jakie typy doinstalowano
kubectl api-resources --api-group=szkolenie.example.com   # nazwa, skrót, wersja, NAMESPACED
kubectl explain backup.spec                               # pola i opisy ze schematu
kubectl get bk                                            # Twoje obiekty (kolumny z additionalPrinterColumns)
kubectl get bk nightly -o yaml
kubectl get bk -A                                         # wszystkie namespace'y: trener tak, Ty forbidden
kubectl auth can-i create backups
```

## Wersje API: alpha, beta, v1

Słowo `alpha` w `apiVersion` znaczy co innego w API wbudowanym i w CRD projektu.

**API wbudowane w Kubernetesa** (np. `batch/v1`, `networking.k8s.io/v1`) przechodzi ustalone etapy:

| Etap | Domyślnie | Gwarancje | Na produkcji |
|---|---|---|---|
| `v1alpha1` | wyłączone (feature gate) | mogą się zmienić albo zniknąć bez migracji | nie; na EKS i AKS i tak nie włączysz feature gate'ów control plane |
| `v1beta1` | od 1.24 nowe bety też wyłączone | pola mogą się zmienić, jest okres deprecjacji | ostrożnie, z planem przejścia |
| `v1` (GA) | włączone | stabilne, usuwane tylko po długiej deprecjacji | tak |

Stare bety znikają: `extensions/v1beta1` Ingress usunięto w 1.22, `policy/v1beta1` PodSecurityPolicy w 1.25. Przed upgrade klastra sprawdź manifesty i charty narzędziem `pluto` albo `kubent`. Jakie wersje serwuje Twój klaster: `kubectl api-versions`.

**CRD projektu**: wersję nazywa projekt i znaczy ona tyle, ile mówi jego polityka. Przykłady z naszego klastra:

| apiVersion | Co to | Stan |
|---|---|---|
| `traefik.io/v1alpha1` | Middleware, IngressRoute (Traefik) | jedyne i produkcyjne API Traefika od wersji 2 |
| `keda.sh/v1alpha1` | ScaledObject (KEDA) | KEDA jest projektem graduated w CNCF; API stabilne mimo nazwy |
| `external-secrets.io/v1beta1` | ExternalSecret (External Secrets) | w ESO 2.x już nieserwowane; działa tylko `v1` |
| `postgresql.cnpg.io/v1` | Cluster (CloudNativePG) | stabilne |

Zanim oprzesz produkcję na CRD w wersji alpha albo beta, sprawdź:
- czy dokumentacja projektu nazywa API stabilnym, czy experimental;
- politykę wersjonowania i deprecjacji: ile wersji wstecz, czy jest conversion webhook (`kubectl get crd <nazwa> -o jsonpath='{.spec.versions[*].name}'`, kolumny `served` i `storage`);
- jak długo API się nie zmienia, kto go używa, czy projekt jest w CNCF i na jakim poziomie;
- czy jest standardowa alternatywa (np. Gateway API zamiast adnotacji kontrolera);
- CHANGELOG przed każdym upgrade'em operatora: szukaj „removed”, „no longer served”, „deprecated”.

## Pułapki

- **CRD bez kontrolera nic nie robi.** To typ, walidacja i endpoint REST. Nic się nie uruchamia.
- **`kubectl delete crd` usuwa wszystkie obiekty tego typu we wszystkich namespace'ach**, bez pytania. Odinstalowanie operatora razem z CRD = utrata wszystkich jego obiektów.
- **Nazwa CRD to `<plural>.<group>`**, np. `backups.szkolenie.example.com`. Ten sam `kind` może istnieć w dwóch grupach (CloudNativePG też ma `Backup`): wtedy pisz `kubectl get backups.postgresql.cnpg.io`.
- **`forbidden … customresourcedefinitions`**: nie masz prawa tworzyć CRD. Tworzysz tylko obiekty.
- `no matches for kind "Backup" in version "szkolenie.example.com/v1"`: CRD jeszcze nie ma albo literówka w `apiVersion`.
- `the server doesn't have a resource type "bk"`: CRD nie ma (jeszcze albo już).
- `helm upgrade` nie aktualizuje CRD z katalogu `crds/` charta.
