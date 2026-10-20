# Lab 05 — Rozpoznaj swój klaster z kubectl

**Cel:** wiesz, z jakim klastrem rozmawiasz (kontekst, namespace, wersja, węzły), umiesz zapytać API o dostępne typy zasobów i znaleźć w zdarzeniach powód problemu.
**Środowisko:** wspólny klaster, Twój namespace = Twój login (ustawiony w kontekście na początku dnia). Nie piszesz `-n`.

Pliki startowe w tym katalogu: `lab05-ping.yaml` (zwykły pod), `lab05-zly.yaml` (pod z celowym błędem).

> Na Windows w PowerShell zamiast `| wc -l` użyj `| Measure-Object -Line`, a zamiast `| grep x` — `| Select-String x`.

---

## Poziom podstawowy

### Krok 1. Kontekst i namespace
```bash
kubectl config current-context
kubectl config get-contexts
kubectl config view --minify
```
- Który kontekst ma gwiazdkę? Jaki namespace jest w nim ustawiony?
- Jeśli kolumna `NAMESPACE` jest pusta: `kubectl config set-context --current --namespace=<login>`.

⚠ Nie uruchamiaj na udostępnionym ekranie `kubectl config view --raw` — pokazuje klucze i tokeny.

**Szybciej: `kubectx` i `kubens`** (opcjonalnie). Dwa małe narzędzia do przełączania kontekstu i domyślnego namespace'u — to samo co `kubectl config use-context` i `set-context --current --namespace=…`, tylko krócej.
```bash
# instalacja: macOS  brew install kubectx  ·  Windows  winget install -e --id ahmetb.kubectx  (kubens: ahmetb.kubens)  ·  Linux/WSL  sudo apt install kubectx
kubectx                 # lista kontekstów, bieżący podświetlony
kubectx szkolenie       # przełącz na klaster szkoleniowy
kubectx -               # wróć do poprzedniego kontekstu
kubens                  # lista namespace'ów
kubens <login>          # ustaw domyślny namespace w bieżącym kontekście
```
Jako wtyczki `kubectl` (przez [krew](https://krew.sigs.k8s.io/)): `kubectl krew install ctx ns` → `kubectl ctx`, `kubectl ns`. Bieżący kontekst i namespace w prompcie terminala pokaże np. `kube-ps1` albo `starship`.

### Krok 2. Wersja i API
```bash
kubectl version
kubectl api-resources | wc -l
kubectl api-resources --namespaced=false
kubectl explain pod.spec
kubectl explain deployment.spec.strategy
```
- Zapisz **wersję serwera** (`Server Version`). Wersję samego klienta pokazuje `kubectl version --client`.
- Ile typów zasobów zna klaster? Które z nich **nie** należą do żadnego namespace?
- Co oznaczają pola `type` i `rollingUpdate` w strategii Deploymentu?

### Krok 3. Zdarzenia
Utwórz dwa pody — jeden zadziała, drugi nie:
```bash
kubectl apply -f lab05-ping.yaml -f lab05-zly.yaml
kubectl get pods
```
Po ok. 20 s przejrzyj zdarzenia:
```bash
kubectl get events --sort-by=.lastTimestamp
kubectl events --for pod/lab05-ping
kubectl events --types=Warning
kubectl get events --field-selector type=Warning
```
- Jakie kroki przeszedł `lab05-ping` od `Scheduled` do `Started`?
- Jaki jest powód problemu z `lab05-zly`? Znajdź go w zdarzeniach, nie w `get pods`.

### Krok 4. Węzły i Twoje limity
```bash
kubectl get nodes -o wide
kubectl auth can-i create deployments
kubectl describe resourcequota
```
- Odczytaj kolumny `VERSION`, `CONTAINER-RUNTIME`, `INTERNAL-IP`.
- Ile CPU i pamięci możesz jeszcze zarezerwować w swoim namespace?

**SUKCES:** na czacie wersja serwera, runtime węzłów (np. `containerd://2.x`) i liczba typów zasobów z `api-resources`.

---

## Dla chętnych

1. Wyciągnij tylko potrzebne dane, bez przewijania:
   ```bash
   kubectl get nodes -o custom-columns=NAZWA:.metadata.name,WERSJA:.status.nodeInfo.kubeletVersion,RUNTIME:.status.nodeInfo.containerRuntimeVersion
   kubectl get pod lab05-ping -o jsonpath='{.spec.nodeName}{" "}{.status.podIP}{"\n"}'
   ```
2. Czego Ci nie wolno? `kubectl auth can-i --list` — porównaj z sąsiadem z czatu.
3. Surowe API: `kubectl get --raw /version` i `kubectl get --raw /api/v1/namespaces/<login>/pods | head -c 300`. To samo, co robi `kubectl get`, tylko bez formatowania.
4. `kubectl api-versions | grep -E 'apps|networking|gateway'` — które grupy API są na klastrze? Czy jest `gateway.networking.k8s.io`?

---

## Wskazówki
- Jak działa klaster (architektura, droga od `kubectl apply` do kontenera, ruch do podów) na diagramach: otwórz w przeglądarce [`docs/k8s/podstawy/jak-dziala-kubernetes.html`](../../docs/k8s/podstawy/jak-dziala-kubernetes.html).
- Brak zdarzeń? W nowym namespace jeszcze nic się nie wydarzyło — zrób krok 3. Zdarzenia znikają po godzinie.
- `kubectl get events` sortuje „jak leci”; `kubectl events` od razu po czasie i ma wygodne `--for` i `--types`.
- Filtr po czasie w `--field-selector` nie działa (pola czasu nie są wspierane w selektorze). Do „ostatnich minut” wystarczy `--sort-by=.lastTimestamp` i koniec listy.
- `kubectl explain` pokazuje dokumentację z Twojego klastra, w jego wersji. `kubectl explain pod.spec.containers --recursive | less` — całe drzewo pól.

## Sprzątanie
```bash
kubectl delete -f lab05-ping.yaml -f lab05-zly.yaml
```
