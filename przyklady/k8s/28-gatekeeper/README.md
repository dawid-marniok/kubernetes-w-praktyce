# Przykłady: OPA Gatekeeper, własne reguły admission

**Cel:** zapisać regułę firmy („obrazy tylko z naszego rejestru”, „tag wersji, bez `:latest`”) jako obiekt w klastrze i zobaczyć, jak Gatekeeper najpierw tylko raportuje (`dryrun`), potem ostrzega (`warn`), a na końcu odrzuca (`deny`). Ta sama reguła z kryteriów projektu ToDos: obrazy z tagiem wersji, bez `latest`.

**Gdzie:** klaster szkoleniowy EKS. `ConstraintTemplate` i Constrainty są obiektami klastrowymi: tworzy je tylko prowadzący (kursant dostaje `forbidden`). Ty możesz włączyć reguły dla swojego namespace etykietą (krok 2) i sprawdzić, co by się stało z Twoimi obiektami. Po szkoleniu całość na własnym klastrze (kind wystarczy) z Gatekeeperem. Komendy w tym katalogu (`cd przyklady/k8s/28-gatekeeper`).

| Plik | Co pokazuje |
|---|---|
| `template-allowed-repos.yaml` | `ConstraintTemplate` w Rego: nowy typ `K8sAllowedRepos` z parametrem `repos` (lista prefiksów) |
| `constraint-allowed-repos.yaml` | `K8sAllowedRepos`: tylko ECR szkolenia i `registry.k8s.io/`, Pody w namespace'ach z etykietą `polityki=gatekeeper`, tryb `dryrun` |
| `template-image-tag.yaml` | `ConstraintTemplate` w CEL (silnik `K8sNativeValidation`): obraz musi mieć tag wersji, `:latest` i brak tagu odpadają, digest `@sha256:` przechodzi |
| `constraint-image-tag.yaml` | `K8sImageTag`: ten sam zakres, tryb `dryrun` |
| `template-required-labels.yaml`, `constraint-required-labels.yaml` | Deployment musi mieć etykietę `app.kubernetes.io/part-of` (zawsze `dryrun`: tylko audyt) |
| `pod-dobry.yaml`, `pod-zly-latest.yaml`, `pod-zly-rejestr.yaml` | pody do sprawdzenia reguł |
| `gator/` | testy reguł bez klastra: `gator verify gator/` (do CI) |

Teoria: admission i polityki z dnia 4 (Pod Security, VAP, Kyverno, Gatekeeper), CRD z dnia 4 ([`20-crd/`](../20-crd/)).

## Jak to działa w trzech zdaniach
1. `ConstraintTemplate` opisuje **regułę** (Rego albo CEL) i jej parametry. Gatekeeper robi z niej nowy CRD, np. `K8sAllowedRepos`.
2. **Constraint** to obiekt tego nowego typu: konkretne parametry (`repos`), zakres (`match`) i co robić z naruszeniem (`enforcementAction`).
3. Webhook Gatekeepera sprawdza każdy nowy obiekt, a **audit** co minutę sprawdza obiekty, które już są w klastrze, i wpisuje naruszenia do `status` Constraintu.

## Krok po kroku (na szkoleniu)

**1. Co jest w klastrze**
```bash
kubectl get constrainttemplates
kubectl get constraints
kubectl api-resources --api-group=constraints.gatekeeper.sh
```
Co powinieneś zobaczyć: szablony `k8sallowedrepos`, `k8simagetag` i Constrainty z kolumną `ENFORCEMENT-ACTION`. `get constraints` może zwrócić `forbidden`: Constrainty są klastrowe, a Twoja rola `edit` działa tylko w Twoim namespace. Wtedy patrz na ekran prowadzącego.

**2. Włącz reguły dla swojego namespace** (tylko gdy prowadzący przełączył reguły na `warn`)
```bash
NS=$(kubectl config view --minify -o jsonpath='{..namespace}'); echo $NS
kubectl label namespace $NS polityki=gatekeeper
```
Constrainty mają `namespaceSelector` z tą etykietą: od teraz Twój namespace jest sprawdzany.

**3. Spróbuj złamać regułę**
```bash
kubectl run x --image=nginx
kubectl run y --image=nginx:1.29
kubectl get events --field-selector reason=WarningAdmission
```
Co powinieneś zobaczyć: przy `x` trzy linie `Warning:` (rejestr spoza listy, brak tagu, druga z nich podwójnie: raz od Gatekeepera, raz od wbudowanej `ValidatingAdmissionPolicy`), przy `y` jedna (tylko rejestr). Pody powstają, bo tryb to `warn`. W trybie `deny` dostałbyś `Error from server (Forbidden)` i poda by nie było.

**4. Twoje ToDos a reguły**

Po ok. minucie audit sprawdzi wszystkie Twoje pody. Prowadzący pokaże na ekranie listę naruszeń (`kubectl get k8simagetag tag-wersji-bez-latest -o yaml`, sekcja `status.violations`). Pody ToDos z obrazami z ECR z tagiem wersji (`…/todos-api:1.2.0`) nie powinny się tam pojawić. `mongo:latest` albo `nginx` bez tagu: pojawią się.

**5. Sprzątanie**
```bash
kubectl delete pod x y --ignore-not-found
kubectl label namespace $NS polityki-
```

## Na własnym klastrze (po szkoleniu)
```bash
kind create cluster --name gk
helm repo add gatekeeper https://open-policy-agent.github.io/gatekeeper/charts
helm install gatekeeper gatekeeper/gatekeeper --version 3.23.1 -n gatekeeper-system --create-namespace --wait
kubectl create namespace demo
kubectl label namespace demo polityki=gatekeeper
kubectl apply -f template-allowed-repos.yaml -f template-image-tag.yaml
sed "s/<konto>/123456789012/" constraint-allowed-repos.yaml | kubectl apply -f -
kubectl apply -f constraint-image-tag.yaml
kubectl -n demo apply -f pod-zly-latest.yaml          # dryrun: powstaje
kubectl get constraints                               # po ok. 60 s: TOTAL-VIOLATIONS
kubectl patch k8simagetag tag-wersji-bez-latest --type merge -p '{"spec":{"enforcementAction":"deny"}}'
kubectl -n demo delete pod zly-latest
kubectl -n demo apply -f pod-zly-latest.yaml          # odrzucony
kubectl -n demo apply -f pod-dobry.yaml               # przechodzi
```

**Testy w CI, bez klastra** ([gator](https://open-policy-agent.github.io/gatekeeper/website/docs/gator), binarka z GitHub Releases albo `brew install gator`):
```bash
gator verify gator/                                   # PASS: 6 przypadków z gator/suite.yaml
gator test -f template-image-tag.yaml -f constraint-image-tag.yaml -f gator/namespace-demo.yaml -f gator/pod-latest.yaml
```
`gator test` kończy się kodem 1 tylko przy naruszeniu reguły w trybie `deny` (przy `dryrun` wypisuje naruszenie, ale zwraca 0). Constrainty z `namespaceSelector` potrzebują w danych wejściowych obiektu `Namespace` z etykietą (`gator/namespace-demo.yaml`); bez niego `gator test` niczego nie sprawdzi, a `gator verify` zgłosi błąd `missing Namespace`.

## Uwagi
- **Najpierw `dryrun`, potem `warn`, na końcu `deny`.** Ta sama droga co `audit` → `warn` → `enforce` w Pod Security z dnia 4.
- **Pod z Deploymentu:** reguła na Podach odrzuca też pody tworzone przez ReplicaSet. `kubectl apply` Deploymentu przechodzi, a podów brak: przyczyna w `kubectl get events --field-selector reason=FailedCreate`. Jak przy `enforce` w Pod Security.
- **Szablon w CEL = także wbudowana VAP.** Z szablonu `k8simagetag` Gatekeeper wygenerował `ValidatingAdmissionPolicy` (`kubectl get validatingadmissionpolicies`). Odrzucenie przychodzi wtedy z API servera: `ValidatingAdmissionPolicy 'gatekeeper-k8simagetag' … denied request`. Reguła w Rego: `admission webhook "validation.gatekeeper.sh" denied the request`.
- **Etykieta na namespace to nie zabezpieczenie,** jeśli użytkownik może ją zdjąć (na szkoleniu możesz, bo zmieniasz etykiety Pod Security). W firmie Constrainty łapią wszystkie namespace'y i wykluczają tylko systemowe (`excludedNamespaces`).
- Gotowe reguły (ponad 50, Rego i CEL, z testami): [gatekeeper-library](https://open-policy-agent.github.io/gatekeeper-library/website/). Wersje uproszczone w tym katalogu pochodzą z `k8sallowedrepos`, `k8sdisallowedtags` i `k8srequiredlabels`.
