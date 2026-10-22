# lab15 — NetworkPolicy w Twoim namespace

**Cel:** zamykasz ruch do i z podów do niezbędnego minimum i każdą regułę sprawdzasz testem połączenia, a nie czytaniem YAML-a.

**Po labie masz:** pod `web-app` odcięty od sieci, backend dostępny tylko z frontendu i pod `restricted-app`, który wychodzi tylko na DNS, HTTPS do internetu i HTTP do podów w Twoim namespace.

## Zanim zaczniesz

- Klaster szkoleniowy egzekwuje NetworkPolicy (Amazon VPC CNI z włączonymi politykami).
- Pliki startowe: `app.yaml` (4 aplikacje: `web-app`, `frontend`, `backend`, `restricted-app`, każda z Service), `test-pod.yaml` (pod bez etykiety `app`, z `wget` i `nslookup`), `restrict-egress.yaml` (szkielet do kroku 3).
- Bez `-n` w komendach: pracujesz w swoim namespace.

```bash
kubectl apply -f app.yaml -f test-pod.yaml
kubectl get pods --show-labels
kubectl exec test-pod -- wget -qO- -T 2 http://backend | grep title
```

✅ Wszystkie pody `Running`, a `test-pod` dostaje stronę nginx z backendu: sieć jest płaska, każdy rozmawia z każdym.

**Jak czytać wynik testu:**

| Komunikat | Co znaczy |
|---|---|
| strona nginx (`<title>Welcome to nginx!</title>`) | połączenie przeszło |
| `download timed out` (wget), `Connection timed out` (curl) | ruch zablokowany przez politykę |
| `bad address` (wget), `Resolving timed out` / `Could not resolve host` (curl) | nie działa DNS: brak reguły egress na port 53 |
| `Connection refused` | sieć przepuściła, ale nic nie słucha na tym porcie |

## Poziom podstawowy

### 1. Deny-all dla jednej aplikacji

Napisz NetworkPolicy `deny-all`, która dla podów `app: web` blokuje cały ruch przychodzący i wychodzący. Podpowiedź: wystarczy `podSelector` i `policyTypes` z oboma typami, bez żadnych reguł.

```bash
kubectl exec test-pod -- wget -qO- -T 2 http://web-app
kubectl exec deploy/web-app -- curl -sS -m 2 http://backend
kubectl describe networkpolicy deny-all
```

✅ Pierwszy test kończy się timeoutem (nic nie wchodzi). Drugi: `Resolving timed out`, bo zablokowany jest także egress, łącznie z DNS.

### 2. Tylko frontend do backendu

Napisz NetworkPolicy `allow-frontend-to-backend`: do podów `app: backend` wolno wejść tylko z podów `app: frontend`, na port TCP 80.

```bash
kubectl exec deploy/frontend -- curl -s -m 2 http://backend | grep title
kubectl exec test-pod -- wget -qO- -T 2 http://backend
```

✅ Z frontendu strona nginx, z `test-pod` timeout.

❓ Czy frontend nadal może łączyć się z `restricted-app`? Dlaczego? (Polityka chroni tylko pody, które wybiera.)

### 3. Egress: tylko DNS, HTTPS i HTTP wewnątrz namespace

Uzupełnij `restrict-egress.yaml` (trzy miejsca `___`) i wgraj go. Pody `app: restricted` mają móc tylko:

- pytać kube-dns (UDP i TCP 53) w namespace `kube-system`,
- łączyć się z internetem po HTTPS (443),
- łączyć się po HTTP (80) z podami w Twoim namespace.

```bash
kubectl exec deploy/restricted-app -- getent hosts backend
kubectl exec deploy/restricted-app -- curl -sS -m 5 -o /dev/null -w '%{http_code}\n' https://example.com
kubectl exec deploy/restricted-app -- curl -sS -m 3 -o /dev/null -w '%{http_code}\n' http://example.com
kubectl exec deploy/restricted-app -- curl -s -m 2 http://frontend | grep title
```

✅ DNS zwraca adres, `https://` → `200`, `http://example.com` → timeout, `http://frontend` → strona nginx.

## SUKCES

- [ ] `test-pod` nie dochodzi do `web-app` ani do `backend`, frontend do backendu dochodzi
- [ ] z `restricted-app` działa `curl https://example.com`, a `curl http://example.com` kończy się timeoutem
- [ ] umiesz po komunikacie błędu powiedzieć, czy to DNS, polityka, czy aplikacja

## Dla chętnych

- **Cały namespace na deny-all.** Polityka z pustym `podSelector: {}` i oboma typami, plus druga, która wszystkim podom otwiera DNS. Co teraz przestało działać z kroków 1–3 i jakie strzałki trzeba dodać, żeby frontend znów doszedł do backendu? **Po ćwiczeniu usuń obie polityki**, inaczej jutrzejsze laby trafią na zamknięty namespace.
- **AND czy OR.** W regule `from` wpisz `namespaceSelector` i `podSelector` raz w jednym elemencie listy, raz jako dwa elementy (z myślnikiem przed `podSelector`). Porównaj `kubectl describe networkpolicy` w obu wersjach.
- **Port Service czy kontenera.** Backend ma Service na porcie 80 i kontener na 80. Gdyby kontener słuchał na 8080, a Service na 80, jaki port wpisujesz w polityce?
- **W parach: ruch z innego namespace.** Dobierz się z sąsiadem; `<sasiad>` to jego login.
  1. `kubectl get namespace <login> --show-labels` — jakie etykiety ma namespace bez niczyjej ingerencji?
  2. U siebie: Deployment i Service `monitored-app` (`app: monitored`, `nginx:1.29`, port 80) i polityka `allow-from-sasiad`, która wpuszcza do niego ruch tylko z namespace `<sasiad>` (`namespaceSelector` po etykiecie z punktu 1).
  3. Test z `test-pod`: sąsiad ze swojego namespace, Ty ze swojego:
     ```bash
     kubectl exec test-pod -- wget -qO- -T 2 http://monitored-app.<login>   # sąsiad: strona nginx
     kubectl exec test-pod -- wget -qO- -T 2 http://monitored-app           # Ty: timeout
     ```
     Timeout u sąsiada zaraz po wgraniu polityki: powtórz po kilku sekundach. Klaster przekłada selektory polityki na adresy IP podów, a to chwilę trwa.
  4. Zamień w polityce klucz etykiety na `name: <sasiad>` (częsta rada w starych tutorialach). Co się dzieje i dlaczego `kubectl` nie zgłosił błędu?

  Jeśli sąsiad ma deny-all na cały namespace (ćwiczenie wyżej), jego pody nigdzie nie wyjdą: najpierw usuńcie tamte polityki.

## Wskazówki

**Gotowe wzorce manifestów:** [`przyklady/k8s/19-networkpolicy/`](../../przyklady/k8s/19-networkpolicy/). Skopiuj i przerób, zamiast pisać YAML od zera.

| Objaw | Co zrobić |
|---|---|
| Polityka nie działa wcale | `kubectl get pods --show-labels`: czy etykiety w `podSelector` się zgadzają? Czy port to port kontenera? |
| `wget: not found` / `nslookup: not found` | Obraz nginx ma tylko `curl` i `getent`; `wget` i `nslookup` są w `test-pod` (busybox) |
| `nslookup backend` w `test-pod`: `NXDOMAIN` | nslookup z busyboxa nie dokleja domen z `search`: podaj pełną nazwę `backend.<login>.svc.cluster.local` albo testuj `wget` |
| `curl https://…` z `restricted-app` nie działa | Reguła 443 z `namespaceSelector: {}` obejmuje tylko pody w klastrze, nie internet. Do internetu: `ipBlock` z `cidr: 0.0.0.0/0` |
| Po deny-all `Resolving timed out` | Brakuje egress na port 53 (UDP i TCP) do kube-dns |
| Stare połączenie dalej działa po dodaniu polityki | Testuj nowym połączeniem (nowy `curl`), nie otwartą sesją |
| Coś po labie dziwnie nie działa | `kubectl get networkpolicy` i usuń polityki z labu: `kubectl delete networkpolicy --all` |

Sprzątanie: `kubectl delete -f app.yaml -f test-pod.yaml`, `kubectl delete deploy,svc monitored-app --ignore-not-found` i `kubectl delete networkpolicy --all`.
