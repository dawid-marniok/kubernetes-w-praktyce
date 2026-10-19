# Rejestr obrazów

W lab03 wypychasz własny obraz do rejestru, a w dniach 2–5 klaster pobiera go stamtąd. Na szkoleniu rejestrem jest **Amazon ECR**. W labach adres rejestru razem z Twoją przestrzenią to **`<REJESTR>`**, a pełna nazwa obrazu:

```text
<REJESTR>/<nazwa-obrazu>:<wersja>        np. <REJESTR>/node-app:1.0.0
```

`<REJESTR>` masz w punkcie 1 swojej karty dostępowej (`<login>.html`, dostajesz ją od prowadzącego prywatnie), np. `123456789012.dkr.ecr.eu-central-1.amazonaws.com/jkowalski`.

## Logowanie (Amazon ECR)

Wszystko jest opisane na karcie (punkty 2 i 3). W skrócie:

1. AWS CLI v2 w wersji 2.32 lub nowszej: `aws --version`.
2. Logowanie do AWS (rano każdego dnia):
   ```bash
   aws login --profile szkolenie                 # bez przeglądarki (WSL, SSH): dodaj --remote
   ```
3. Logowanie Dockera do rejestru (hasło jest ważne 12 h, więc też każdego dnia rano). Adres to `<REJESTR>` bez końcówki `/<login>`:
   ```bash
   aws ecr get-login-password --profile szkolenie --region eu-central-1 | docker login --username AWS --password-stdin <konto>.dkr.ecr.eu-central-1.amazonaws.com
   ```
   ✅ `Login Succeeded`.

Repozytorium (np. `<login>/node-app`) tworzy się samo przy pierwszym `docker push`. Wysyłać i pobierać możesz tylko w swojej przestrzeni `<login>/…`. W konsoli AWS (Elastic Container Registry, region Frankfurt) zobaczysz swoje obrazy i wynik skanu podatności.

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

## Docker Hub: tylko logowanie na limit pobrań

Obrazy bazowe (`nginx`, `node`, `postgres`…) pobierasz z Docker Hub. Anonimowo jest limit pobrań, który na szkoleniu (wiele osób z jednego adresu IP) potrafi się skończyć (`429 Too Many Requests`). Darmowe konto go podnosi: <https://hub.docker.com/signup>, potem `docker login` (zamiast hasła lepiej token: Account settings → Personal access tokens). Logowanie do Docker Hub i do ECR działają obok siebie.

Po szkoleniu, na własnym koncie, ten sam schemat działa z Docker Hub (`<REJESTR>` = `docker.io/<login>`, repozytorium publiczne) albo z GitHub Container Registry (`ghcr.io/<login-github>`, `docker login ghcr.io`, token z `write:packages`).

## Gdy coś nie działa

| Objaw | Co zrobić |
|---|---|
| `Unable to locate credentials` / `expired` przy `aws ecr …` | Brak `--profile szkolenie` w poleceniu albo sesja wygasła: `aws login --profile szkolenie` |
| `no basic auth credentials` / `authorization token has expired` przy `docker push` | Hasło Dockera wygasło (12 h): powtórz `aws ecr get-login-password … \| docker login …` |
| `denied` / `not authorized to perform: ecr:…` | Nazwa obrazu nie zaczyna się od Twojego `<REJESTR>` (cudza przestrzeń albo brak `/<login>`). Sprawdź nazwę z kartą |
| `An image does not exist locally with the tag` | Najpierw `docker tag`, potem `docker push`, ta sama nazwa w obu |
| `invalid reference format: repository name must be lowercase` | W nazwie są wielkie litery. Wszystko małymi literami |
| `aws: unknown command 'login'` | Za stare AWS CLI: zaktualizuj do 2.32+ (karta, punkt 2) |
| `x509: certificate signed by unknown authority` | Proxy firmowe z inspekcją TLS, patrz [`docker-desktop.md`](docker-desktop.md#proxy) |
| Klaster: `ImagePullBackOff`, w `kubectl describe pod` `not found` | Literówka w nazwie lub tagu, albo obraz zbudowany dla złej architektury (Mac M bez `--platform linux/amd64`) |
