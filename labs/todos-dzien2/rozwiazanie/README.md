# ToDos · dzień 2 — rozwiązanie

Jedno z możliwych rozwiązań. Twoje może wyglądać inaczej (inne etykiety, inne wartości `resources`, Secret z pliku) i też jest dobre, jeśli spełnia wymagania z [`../README.md`](../README.md).

| Plik | Co w nim jest |
|---|---|
| `configmap.yaml` | ConfigMap `todos-config`: `API_HOST`, `API_PORT` dla web i `PORT` dla api |
| `mongo.yaml` | Deployment i Service `mongo`: MongoDB bez dysku, `strategy: Recreate`, użytkownik z Secretu |
| `api.yaml` | Deployment i Service `api`: `MONGODB_URI` z Secretu, `envFrom` z ConfigMapy, `readinessProbe` na `/api/health` |
| `web.yaml` | Deployment i Service `web`: `envFrom` z ConfigMapy, Service 80 → port `http` (8080) |
| `ingress.yaml` | Ingress `todos`: host `todos-<login>.<DOMENA>`, `/` → `web:80`, TLS z cert-managera (Secret `todos-tls`) |

## Wdrożenie

Secret nie ma pliku, bo hasło nie powinno trafić do repo:

```bash
HASLO=<twoje-haslo>                     # litery i cyfry
kubectl create secret generic todos-mongo \
  --from-literal=username=root \
  --from-literal=password="$HASLO" \
  --from-literal=uri="mongodb://root:$HASLO@mongo:27017/todos?authSource=admin"
kubectl label secret todos-mongo app.kubernetes.io/part-of=todos
```

W plikach podmień `<REJESTR>` (api.yaml, web.yaml) oraz `<login>`, `<DOMENA>` (ingress.yaml). Potem w tej kolejności:

```bash
kubectl apply -f configmap.yaml
kubectl apply -f mongo.yaml             # poczekaj na 1/1
kubectl apply -f api.yaml               # 2 × 1/1, w logach „Połączono z MongoDB”
kubectl apply -f web.yaml
kubectl apply -f ingress.yaml
```

Kolejność ma znaczenie: nginx w web sprawdza nazwę `api` przy starcie, a api bez bazy nie jest gotowe.

## Dlaczego tak

- **Nazwy Service `mongo` i `api` są narzucone.** `mongo` jest w adresie bazy w Secrecie, `api` jest w `API_HOST`, którego używa nginx w web. Inna nazwa = inna wartość w Secrecie albo w ConfigMapie.
- **`strategy: Recreate` dla Mongo.** Domyślny `RollingUpdate` najpierw stawia nowy pod, potem usuwa stary, więc przez chwilę działałyby dwie bazy. `Recreate` najpierw usuwa stary.
- **`readinessProbe` na `/api/health` w api.** Dopóki api nie połączy się z bazą, endpoint zwraca 503, pod nie jest `Ready` i Service nie kieruje do niego ruchu. Web nie dostaje błędów zaraz po starcie.
- **`envFrom` zamiast pojedynczych `env`.** Cała ConfigMapa trafia do kontenera jako zmienne, nowy klucz nie wymaga zmiany Deploymentu.
- **Porty po nazwie (`targetPort: http`).** Service wskazuje nazwę portu z kontenera, więc zmiana numeru w obrazie to zmiana w jednym miejscu.
- **Mongo bez dysku.** Zadania znikają razem z podem. To celowe — jutro rano przerabiasz bazę na StatefulSet z PVC.
