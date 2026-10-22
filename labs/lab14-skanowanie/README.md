# lab14 — Skanowanie obrazów i manifestów

**Cel:** znajdujesz podatności w obrazie i błędy bezpieczeństwa w YAML-u, zanim trafią do klastra, i poprawiasz manifest tak, żeby przeszedł Pod Security `restricted`.

**Po labie masz:** porównanie CVE dwóch wariantów obrazu, SBOM obrazu i poprawiony `do-skanu/web.yaml`, w którym skaner nie zgłasza już błędów z `securityContext`.

## Zanim zaczniesz

Zainstaluj narzędzia (skanują lokalnie, klaster nie jest potrzebny):

| System | Trivy | Kubescape |
|---|---|---|
| macOS | `brew install trivy` | `brew install kubescape` |
| Windows | `winget install AquaSecurity.Trivy` albo `scoop install trivy` | `winget install kubescape` |
| Linux (Debian/Ubuntu) | patrz niżej | binarka z [GitHub Releases](https://github.com/kubescape/kubescape/releases) |

Trivy na Debianie/Ubuntu (repozytorium z kluczem w keyringu; stare `apt-key` nie działa na nowych wydaniach):

```bash
sudo apt-get install -y wget gnupg
wget -qO - https://aquasecurity.github.io/trivy-repo/deb/public.key | gpg --dearmor | sudo tee /usr/share/keyrings/trivy.gpg > /dev/null
echo "deb [signed-by=/usr/share/keyrings/trivy.gpg] https://aquasecurity.github.io/trivy-repo/deb generic main" | sudo tee /etc/apt/sources.list.d/trivy.list
sudo apt-get update && sudo apt-get install -y trivy
```

Sprawdź: `trivy --version`, `kubescape version`. **Zacznij od pobrania bazy CVE** (kilkaset MB, chwilę trwa):

```bash
trivy image --download-db-only
```

## Poziom podstawowy

### 1. Podatności w obrazie

```bash
trivy image --severity HIGH,CRITICAL nginx:1.29
trivy image --severity HIGH,CRITICAL --ignore-unfixed nginx:1.29
trivy image --severity HIGH,CRITICAL --ignore-unfixed nginx:1.29-alpine
```

Zanotuj z linii `Total:` liczby HIGH i CRITICAL dla każdego wariantu. Co zmienia `--ignore-unfixed`? Który obraz wybrałbyś do produkcji?

✅ Masz trzy linie `Total: …` i umiesz powiedzieć, skąd różnica.

### 2. SBOM: lista składników obrazu

```bash
trivy image --format cyclonedx -o sbom.json nginx:1.29-alpine
trivy sbom --severity HIGH,CRITICAL sbom.json
```

Ile składników jest w SBOM? (`jq '.components | length' sbom.json` albo poszukaj w pliku). Drugi skan nie pobiera już obrazu: wystarcza mu lista składników.

✅ `trivy sbom` pokazuje te same podatności co skan obrazu.

### 3. Błędy w manifeście

```bash
trivy config do-skanu/
kubescape scan framework nsa do-skanu/
```

Przeczytaj znaleziska HIGH i MEDIUM. Popraw `do-skanu/web.yaml` tak, żeby:

- kontener nie działał jako root i nie mógł podnieść uprawnień,
- miał zabrane wszystkie capabilities i profil seccomp `RuntimeDefault`,
- miał system plików tylko do odczytu (podpowiedź: nginx musi gdzieś pisać, potrzebny wolumen `emptyDir`),
- miał limity CPU i pamięci.

Wskazówka do obrazu: `nginx:1.29` startuje jako root i słucha na porcie 80. Wariant `nginxinc/nginx-unprivileged:1.29` działa jako UID 101 i słucha na 8080.

Skanuj po każdej zmianie. Wgraj poprawiony Deployment do swojego namespace i sprawdź, że pod działa:

```bash
kubectl apply -f do-skanu/web.yaml
kubectl get pods -l app=skan-web
kubectl logs deploy/skan-web
```

✅ `trivy config do-skanu/` nie zgłasza już KSV-0001, 0003, 0012, 0014, 0030, 0118 ani braku limitów, a pod jest `Running`.

### 4. Kubescape na Twoim namespace

```bash
kubescape scan framework nsa --include-namespaces <login>
```

Porównaj wynik z plikami. Co kubescape widzi w klastrze, czego nie widział w pliku?

✅ Wynik dla Twojego namespace, w nim Deployment `skan-web` bez błędów z `securityContext`.

## SUKCES

- [ ] liczby HIGH/CRITICAL dla `nginx:1.29` i `nginx:1.29-alpine` (z `--ignore-unfixed` i bez)
- [ ] `sbom.json` i wynik `trivy sbom`
- [ ] poprawiony `do-skanu/web.yaml`: pod działa, skaner nie zgłasza błędów `securityContext` ani limitów

## Dla chętnych

### Skan w pipeline (GitHub Actions)

Przykład kroku z przypiętymi wersjami. Tag można przesunąć, SHA commita już nie, dlatego na produkcji przypnij akcję do SHA (wersję i SHA sprawdź na stronie wydań akcji):

```yaml
name: security-scan
on: [push, pull_request]
jobs:
  trivy:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v5            # na produkcji: @<SHA>  # v5
      - uses: aquasecurity/trivy-action@0.33.1   # na produkcji: @<SHA>  # 0.33.1
        with:
          scan-type: config
          scan-ref: .
          exit-code: "1"
          severity: HIGH,CRITICAL
```

Ten sam skan bez CI: `trivy config --exit-code 1 --severity HIGH,CRITICAL .; echo "kod wyjścia: $?"`.

### Pod Security w Twoim namespace

Etykiety Pod Security na swoim namespace możesz zmieniać. Zobacz, co jest ustawione teraz:

```bash
kubectl get namespace <login> --show-labels
```

Twój namespace ma `warn` i `audit` na poziomie `baseline`. Sprawdź, co by się stało po włączeniu `enforce=restricted`, **bez włączania go** (dry-run po stronie serwera):

```bash
kubectl label namespace <login> pod-security.kubernetes.io/enforce=restricted --dry-run=server
```

Które pody nie przeszłyby kontroli? Czy jest wśród nich `skan-web`? Teraz włącz na chwilę samo ostrzeganie na poziomie `restricted`:

```bash
kubectl label namespace <login> pod-security.kubernetes.io/warn=restricted --overwrite
kubectl create deployment psa-test --image=nginx:1.29   # ostrzeżenie, ale Deployment i pod powstają
kubectl rollout restart deploy/skan-web                 # bez ostrzeżenia, jeśli poprawka jest kompletna
kubectl delete deployment psa-test
kubectl label namespace <login> pod-security.kubernetes.io/warn=baseline --overwrite
```

⚠ Ostatnia linia przywraca poprzednie ustawienie. Nie ustawiaj `enforce` naprawdę: zablokowałby nowe pody Twojego ToDos i aplikacji z lab15 (`nginx:1.29` działa jako root). Jak wygląda blokada, widziałeś na demie.

### Skanowanie w klastrze (do poczytania)

Na produkcji skanuje się też to, co już działa: Trivy Operator albo operator Kubescape skanują obrazy i konfigurację podów w klastrze i zapisują wyniki jako obiekty w API (`vulnerabilityreports`, `configauditreports`). Instalacja wymaga uprawnień klastrowych, więc na wspólnym klastrze go nie instalujemy. Jeśli masz już Helma, możesz bez klastra zobaczyć, jakie typy obiektów operator dodaje do API:

```bash
helm repo add aquasecurity https://aquasecurity.github.io/helm-charts/
helm show crds aquasecurity/trivy-operator --version 0.37.0 | grep '^  name:'
```

Same raporty, bez obiektów z polityką: konfiguracja operatora idzie przez values Helma (`helm show values aquasecurity/trivy-operator`). Do CRD wrócimy w lab16.

## Wskazówki

**Gotowe wzorce manifestów:** [`przyklady/k8s/18-pod-security/`](../../przyklady/k8s/18-pod-security/). Skopiuj i przerób, zamiast pisać YAML od zera.

| Objaw | Co zrobić |
|---|---|
| `TOOMANYREQUESTS` przy pobieraniu bazy | `trivy image --db-repository public.ecr.aws/aquasecurity/trivy-db nginx:1.29` |
| Skan trwa bardzo długo | Pierwszy skan pobiera bazę i obraz; kolejne są szybkie |
| Pod po poprawkach w `CrashLoopBackOff`, w logach `Read-only file system` | Brakuje `emptyDir` zamontowanego w `/tmp` |
| `CreateContainerConfigError`, `runAsNonRoot` | Obraz działa jako root; zmień obraz albo ustaw numeryczny `runAsUser` zgodny z obrazem |
| Pod działa, ale nie odpowiada | `nginx-unprivileged` słucha na 8080, popraw `containerPort` |
| Znaleziska o rejestrze (KSV-0032…0035, 0125) i o namespace `default` (KSV-0110) | Dotyczą polityki firmy (własny rejestr, namespace w YAML), w labie je pomijamy |
| `kubescape` na klastrze: brak uprawnień do zasobów klastrowych | Skanuj tylko swój namespace (`--include-namespaces`) albo pliki |
