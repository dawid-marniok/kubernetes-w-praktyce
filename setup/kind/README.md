# kind: pliki klastra lokalnego

Pełna instrukcja (instalacja kind, konteksty, `kind load`, typowe problemy): [`../kind.md`](../kind.md).

| Plik | Co |
|---|---|
| `kind-szkolenie.yaml` | klaster `szkolenie`: 1 control plane + 2 workery, Kubernetes 1.35, porty `localhost:8088`→80, `8443`→443, `30000`–`30002` → NodePorty |
| `metrics-server/metrics-server.yaml` | metrics-server pod `kubectl top` i HPA, zwykły YAML (`kubectl apply -f`) |

## Szybki start

Wymagane: Docker Desktop i kind ≥ v0.33.0 (`brew install kind`, `kind version`). Z katalogu głównego repo:

```bash
kind create cluster --config setup/kind/kind-szkolenie.yaml
kubectl get nodes                          # 3 węzły Ready
kubectl apply -f setup/kind/metrics-server/metrics-server.yaml   # opcjonalnie: kubectl top; tylko na kind!
```

Po `kind create` bieżący kontekst to `kind-szkolenie`. Na wspólny klaster wracasz przez `kubectl config use-context szkolenie`.

## Czym jest `kind-szkolenie.yaml`

To **jeden obiekt** `kind: Cluster` (`apiVersion: kind.x-k8s.io/v1alpha4`) i opisuje cały klaster. Nie jest to obiekt Kubernetesa:
- czyta go tylko polecenie `kind create cluster --config …`, a `kubectl apply -f` zwróci `no matches for kind "Cluster"`;
- nie trafia do klastra, a po utworzeniu klastra nie ma po nim śladu w API;
- **nie da się go zmienić w działającym klastrze.** Po zmianie pliku robisz `kind delete cluster --name szkolenie` i tworzysz klaster od nowa.

Z tego jednego pliku kind robi wszystko sam: uruchamia kontener Dockera dla każdego węzła, stawia control plane przez `kubeadm`, dołącza workery i instaluje dodatki: sieć (kindnet, egzekwuje też NetworkPolicy), CoreDNS, kube-proxy i StorageClass `standard` (local-path). Na koniec dopisuje kontekst do `~/.kube/config`.

### Co jest w naszym pliku

| Pole | Po co |
|---|---|
| `name: szkolenie` | nazwa klastra. Z niej biorą się nazwy kontenerów (`szkolenie-control-plane`, `szkolenie-worker`, …) i kontekst `kind-szkolenie` |
| `nodes[].role` | `control-plane` albo `worker`. Ile wpisów, tyle węzłów |
| `nodes[].image` | obraz węzła `kindest/node:v1.35.8@sha256:…`, czyli wersja Kubernetesa. Przypięty digest daje wszystkim ten sam obraz |
| `kubeadmConfigPatches` | etykieta `ingress-ready=true` na control plane, żeby kontroler Ingress/Gateway wylądował na węźle z przekierowanymi portami |
| `extraPortMappings` | porty z laptopa do kontenera węzła: `8088`→80, `8443`→443, `30000`–`30002` → NodePorty. Bez tego do klastra dostaniesz się tylko przez `kubectl port-forward` |

### Co jeszcze można ustawić (wybór)

| Pole | Do czego |
|---|---|
| `nodes[].labels` | etykiety węzłów bez patchy kubeadm, np. `zone: a` do ćwiczeń z affinity |
| `nodes[].extraMounts` | katalog z laptopa zamontowany w węźle (np. dane dla `hostPath`) |
| `networking.podSubnet` / `serviceSubnet` | inne pule adresów, gdy kolidują z VPN-em albo siecią firmową |
| `networking.disableDefaultCNI: true` | bez kindnet, żeby samemu zainstalować Calico albo Cilium. Do czasu instalacji CNI węzły są `NotReady` |
| `networking.kubeProxyMode` | `iptables` (domyślnie), `ipvs`, `nftables` albo `none` (np. pod Cilium) |
| `networking.apiServerAddress` / `apiServerPort` | adres i port API. Domyślnie `127.0.0.1` i losowy port, czyli API dostępne tylko z Twojego laptopa |
| `featureGates`, `runtimeConfig` | włączenie funkcji i API w wersji alpha/beta |
| `containerdConfigPatches` | konfiguracja containerd w węzłach, np. lokalny rejestr (mirror) |

Pełna lista pól: <https://kind.sigs.k8s.io/docs/user/configuration/>.

### Na co uważać

- **Obraz węzła pasuje do wersji kind.** Każde wydanie kind ma listę obrazów w release notes. Starszy kind ze świeżym obrazem potrafi utworzyć klaster, a potem wyłożyć się np. na `kind load`. Bez pola `image` kind bierze swój domyślny obraz (kind v0.33.0 bierze `v1.37.0`), czyli inną wersję niż na szkoleniu.
- **Zajęte porty.** Każdy `hostPort` musi być wolny na laptopie, inaczej dostaniesz `address already in use`. Drugi klaster z tym samym plikiem też się nie uruchomi. Zmień porty albo usuń `extraPortMappings`.
- **`extraPortMappings` działa tylko na węźle, na którym go wpiszesz.** U nas jest na control plane, stąd etykieta `ingress-ready`: kontroler Ingress/Gateway musi działać właśnie na tym węźle (nodeSelector i toleracja na taint control plane).
- **Nie montuj `/var/run/docker.sock` w węzłach.** Pod z `hostPath` na ten socket ma roota na Twoim laptopie.
- **Nie wystawiaj API na zewnątrz** (`apiServerAddress: 0.0.0.0`), chyba że wiesz, po co. Certyfikat admina leży w `~/.kube/config`.
- **Zasoby.** Każdy węzeł to osobny kontener. Trzy węzły potrzebują ok. 3 GB RAM w Docker Desktop, a z labami dnia 3 i 5 lepiej przydzielić 6 GB.

## metrics-server (`kubectl top`, HPA)

kind nie instaluje metrics-servera, więc bez niego `kubectl top` zwraca `Metrics API not available`, a HPA pokazuje `<unknown>/50%`.

`metrics-server/metrics-server.yaml` to oficjalny `components.yaml` z wydania v0.9.0. Jest w nim 9 obiektów oddzielonych `---`: ServiceAccount, 2× ClusterRole, RoleBinding, 2× ClusterRoleBinding, Service, Deployment i APIService. Jedyna zmiana to argument `--kubelet-insecure-tls` w Deployment (oznaczony komentarzem). Kubelet w kind ma certyfikat self-signed i bez tej flagi metrics-server nie pobierze metryk z węzłów.

> ⚠ **Tylko na kind.** Na klastrze szkoleniowym (EKS) metrics-server jest dodatkiem EKS. Ten plik nadpisuje jego Service tak, że selektor nie pasuje do żadnego poda, i `kubectl top` oraz HPA przestają działać wszystkim. Przed `apply` sprawdź kontekst.

```bash
kubectl config use-context kind-szkolenie
kubectl config current-context                  # musi być kind-szkolenie
kubectl apply -f setup/kind/metrics-server/metrics-server.yaml
kubectl -n kube-system rollout status deploy/metrics-server
kubectl get apiservice v1beta1.metrics.k8s.io   # AVAILABLE: True
kubectl top nodes                               # po ok. 30–60 s liczby dla 3 węzłów
kubectl top pods -A
```

Usunięcie: `kubectl delete -f setup/kind/metrics-server/metrics-server.yaml`. Na klastrze szkoleniowym (EKS) tego nie robisz: tam metrics-server jest dodatkiem EKS.

Nowsza wersja: pobierz `components.yaml` z <https://github.com/kubernetes-sigs/metrics-server/releases> i dopisz `- --kubelet-insecure-tls` pod pozostałymi `args` kontenera.

## kind z terminala a Kubernetes wyklikany w Docker Desktop

Docker Desktop (Settings → Kubernetes) od wersji 4.38 ma dwa tryby: `kubeadm` (1 węzeł) i `kind` (wiele węzłów). W trybie `kind` pod spodem działa to samo narzędzie, ale bez Twojego pliku konfiguracyjnego.

| | `kind create cluster --config …` | Docker Desktop → Kubernetes |
|---|---|---|
| Konfiguracja | plik YAML: węzły, porty, etykiety, sieć, patche | kilka pól w GUI: tryb, wersja, liczba węzłów (tryb kind) |
| Liczba klastrów | dowolna, każdy z inną nazwą | jeden |
| Kontekst | `kind-<nazwa>`, np. `kind-szkolenie` | `docker-desktop` |
| Wersja Kubernetesa | dowolny obraz `kindest/node` | `kubeadm`: wersja narzucona przez Docker Desktop; `kind`: wybór z listy |
| Porty z laptopa | `extraPortMappings` | bez tego pola. Zostają `port-forward` i Service `LoadBalancer` na `localhost` (zachowanie zależy od wersji, sprawdź) |
| Obraz zbudowany lokalnie | `kind load docker-image` | `kubeadm` z magazynem obrazów Dockera: zwykle widoczny od razu. Tryb `kind` wymaga magazynu containerd, sprawdź w swojej wersji, inaczej wypchnij obraz do rejestru |
| Kontenery węzłów | widać w `docker ps` i w Docker Desktop → Containers | domyślnie ukryte (opcja „Show system containers”) |
| Usunięcie | `kind delete cluster --name …` | Stop (usuwa kontenery Kubernetesa) albo Reset cluster |
| Powtarzalność | ten sam plik w repo, w CI i u każdego kursanta | ustawienia klikane ręcznie u każdego osobno |

Do labów szkolenia używaj `kind-szkolenie.yaml`. Klaster wyklikany w Docker Desktop wystarczy do szybkich prób z Deploymentem i Service. Nie da się w nim jednak ustawić naszych portów i etykiet, a komendy z `kind.md` (kontekst `kind-szkolenie`, `kind load --name szkolenie`) trzeba w nim zamienić na wersję dla `docker-desktop`.

## Sprzątanie

```bash
kind delete cluster --name szkolenie
```
