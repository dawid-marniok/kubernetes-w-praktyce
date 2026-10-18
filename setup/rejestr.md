# Rejestr obrazów

W lab03 wypychasz własny obraz do rejestru, a w dniach 2–5 klaster pobiera go stamtąd. W labach adres rejestru razem z Twoją przestrzenią to **`<REJESTR>`**, a pełna nazwa obrazu:

```text
<REJESTR>/<nazwa-obrazu>:<wersja>        np. <REJESTR>/node-app:1.0.0
```

Którego wariantu używa grupa, mówi prowadzący na początku lab03. Jeśli nic nie ustalono, weź Docker Hub.

| Wariant | `<REJESTR>` | Przykład pełnej nazwy |
|---|---|---|
| Docker Hub, własne konto | `docker.io/<login-docker-hub>` | `docker.io/jkowalski/node-app:1.0.0` |
| GitHub Container Registry | `ghcr.io/<login-github>` (małymi literami) | `ghcr.io/jkowalski/node-app:1.0.0` |
| Rejestr szkoleniowy (Azure Container Registry) | `<nazwa>.azurecr.io/<login>` | `<nazwa>.azurecr.io/user07/node-app:1.0.0` |

## Docker Hub

1. Załóż konto: <https://hub.docker.com/signup> (darmowe).
2. Zamiast hasła lepiej użyć tokenu: Account settings → Personal access tokens → Generate, uprawnienia **Read & Write**.
3. Zaloguj się:
   ```bash
   docker login -u <login-docker-hub>     # hasło = token
   ```
4. Repozytorium tworzy się samo przy pierwszym `docker push` i jest **publiczne**. Nie wypychaj obrazów z hasłami ani kodem, którego nie wolno publikować.

Zalogowanie do Docker Hub podnosi też limit pobrań obrazów, który na szkoleniu (wiele osób z jednego adresu IP) potrafi się skończyć.

## GitHub Container Registry (GHCR)

1. GitHub → Settings → Developer settings → Personal access tokens → **Tokens (classic)** → Generate new token, zaznacz `write:packages` (doda się `read:packages`). Skopiuj token.
2. Zaloguj się:
   ```bash
   docker login ghcr.io -u <login-github>     # hasło = token
   ```
   PowerShell, bez pokazywania tokenu w historii: `$env:GHCR_TOKEN | docker login ghcr.io -u <login-github> --password-stdin`.
3. Po pierwszym `docker push` pakiet jest **prywatny**. Żeby klaster mógł go pobrać bez dodatkowej konfiguracji: github.com → Twój profil → Packages → pakiet → Package settings → Change visibility → Public.

## Rejestr szkoleniowy (Azure Container Registry)

Jeśli prowadzący udostępnia rejestr szkoleniowy, nazwę rejestru i Twój login podaje w czacie (dane edycji nie są w repo).

```bash
az login                              # jeśli prowadzący dał konto Azure
az acr login -n <nazwa>               # <nazwa> = część adresu przed .azurecr.io
```

Bez Azure CLI prowadzący może dać login i hasło (token) do rejestru:

```bash
docker login <nazwa>.azurecr.io -u <login-rejestru>
```

## Tag i push

```bash
docker tag node-app:1.0.0 <REJESTR>/node-app:1.0.0
docker push <REJESTR>/node-app:1.0.0
```

**Mac z procesorem M:** węzły klastra mają procesory amd64, a Twój Docker buduje domyślnie arm64. Buduj i wypychaj od razu dla amd64:

```bash
docker buildx build --platform linux/amd64 -t <REJESTR>/node-app:1.0.0 --push node
docker buildx imagetools inspect <REJESTR>/node-app:1.0.0 --format '{{.Image.Architecture}}'     # amd64
```

Obraz arm64 na węźle amd64 kończy się w Kubernetesie błędem `exec format error` albo `no match for platform in manifest`.

**Tag zawsze z wersją** (`1.0.0`, `1.0.1`, `a1b2c3d` = skrót commita), nigdy `latest`. Z `latest` nie wiesz, która wersja działa w klastrze, a rollback „do poprzedniego latest” nie istnieje. Każda zmiana obrazu = nowy tag.

## Gdy coś nie działa

| Objaw | Co zrobić |
|---|---|
| `denied: requested access to the resource is denied` | Nazwa obrazu nie zaczyna się od Twojej przestrzeni (`docker.io/<Twój-login>/…`) albo nie jesteś zalogowany. `docker login …` jeszcze raz |
| `unauthorized: authentication required` | Wygasłe logowanie albo token bez prawa zapisu (GHCR: `write:packages`, Docker Hub: Read & Write) |
| `An image does not exist locally with the tag` | Najpierw `docker tag`, potem `docker push`, ta sama nazwa w obu |
| `invalid reference format: repository name must be lowercase` | W nazwie są wielkie litery (częste przy loginie GitHub). Wszystko małymi literami |
| `az: command not found` | Brak Azure CLI: <https://learn.microsoft.com/cli/azure/install-azure-cli> albo poproś prowadzącego o login i token do `docker login` |
| `x509: certificate signed by unknown authority` | Proxy firmowe z inspekcją TLS, patrz [`docker-desktop.md`](docker-desktop.md#proxy) |
| Klaster: `ImagePullBackOff`, w `kubectl describe pod` `401 Unauthorized` / `not found` | Obraz prywatny (GHCR: zmień na Public) albo literówka w nazwie lub tagu |
