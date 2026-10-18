# Budowanie obrazów: przykłady Dockerfile

| Katalog | Co pokazuje | Obraz bazowy | Port |
|---|---|---|---|
| `1-nginx/` | własna strona w obrazie nginx: `RUN`, `COPY`, `ENV`, `EXPOSE`, `VOLUME`, `CMD` | `nginx:1.29` | 80 |
| `2-node/` | aplikacja Node.js: kolejność warstw pod cache, `npm ci`, `.dockerignore`, `USER` | `node:22-alpine` | 3000 |
| `3-dotnet-multistage/` | multi-stage build (.NET 10) i porównanie z jednym etapem | `mcr.microsoft.com/dotnet/sdk:10.0` → `aspnet:10.0` | 8080 |

Polecenia wydajesz w katalogu danego przykładu (`.` na końcu `docker build` to **kontekst budowania**, czyli katalog, którego zawartość trafia do buildera).

## 1-nginx

```bash
cd 1-nginx
docker build -t moj-nginx:1.0 .
docker run -d --name moj-nginx -p 8080:80 moj-nginx:1.0
curl localhost:8080                      # nasza strona z index.html
docker exec -it moj-nginx bash           # w środku są vim i curl z RUN apt-get
docker rm -f -v moj-nginx               # -v usuwa też anonimowy wolumen utworzony przez VOLUME

# wariant bez własnej strony, z innym plikiem Dockerfile
docker build -f Dockerfile.simple -t moj-nginx:simple .
```

Zmień `index.html`, zbuduj `moj-nginx:1.1` i porównaj `docker history moj-nginx:1.0` z `moj-nginx:1.1`: warstwa z `apt-get` jest ta sama (z cache), zmieniła się tylko warstwa `COPY`.

## 2-node

```bash
cd 2-node
docker build -t node-app:1.0 .
docker run -d --name node-app -p 3000:3000 node-app:1.0
curl localhost:3000
docker exec node-app whoami              # node, nie root
docker stop node-app                     # kończy się od razu, bo aplikacja obsługuje SIGTERM
docker rm node-app
```

Co warto zauważyć w `Dockerfile`:
- najpierw `COPY package.json package-lock.json`, potem `RUN npm ci`, a dopiero na końcu `COPY . .`. Zmiana kodu nie unieważnia warstwy z zależnościami;
- `npm ci --omit=dev` instaluje dokładnie wersje z `package-lock.json`, bez zależności deweloperskich;
- `.dockerignore` nie wpuszcza do kontekstu `node_modules`, `.git` ani `.env`;
- `CMD ["node", "app.js"]` w formie exec: `node` jest procesem nr 1 i dostaje sygnały (w formie shell sygnały dostałby `sh`).

## 3-dotnet-multistage

Minimalne API w ASP.NET Core (.NET 10). `Dockerfile` ma dwa etapy: `build` na pełnym SDK i `final` na samym runtime ASP.NET. `Dockerfile.single` robi to samo w jednym etapie, na SDK.

```bash
cd 3-dotnet-multistage
docker build -t sample:multi .
docker build -f Dockerfile.single -t sample:single .
docker images sample                     # porównaj rozmiary

docker run --rm -d --name sample -p 8080:8080 sample:multi
curl localhost:8080                      # Hello World from .NET!
docker rm -f sample
```

Rozmiary zmierzone przy przygotowaniu przykładu (Docker Desktop, arm64):

| Obraz | Rozmiar (`docker images`) |
|---|---|
| `sample:multi` | 262 MB (runtime `aspnet:10.0` + opublikowana aplikacja) |
| `sample:single` | 975 MB (całe SDK + źródła + pliki pośrednie) |

**Cache warstw.** Zmień napis w `Program.cs` i zbuduj ponownie (`docker build -t sample:multi .`). Kroki `COPY *.csproj` i `RUN dotnet restore` są oznaczone jako `CACHED`, wykonują się tylko `COPY . .`, `dotnet publish` i `COPY --from=build`. Gdyby w Dockerfile od razu było `COPY . .`, każda zmiana kodu pobierałaby pakiety NuGet od nowa.

Wynik z przygotowania przykładu (fragment `docker build --progress=plain`, po zmianie napisu, całość ok. 3,5 s):

```
#9  [build 3/6] COPY *.csproj ./                       CACHED
#10 [build 4/6] RUN dotnet restore                     CACHED
#11 [build 5/6] COPY . .                               DONE 0.0s
#12 [build 6/6] RUN dotnet publish -c Release ...      DONE 2.9s
#13 [final 2/3] WORKDIR /app                           CACHED
#14 [final 3/3] COPY --from=build /app/publish .       DONE 0.0s
```

Projekt nie ma pakietów NuGet, więc sam `restore` trwa tu krótko (ok. 1,6 s). W prawdziwej aplikacji z kilkudziesięcioma pakietami ten krok zajmuje minuty i wtedy cache naprawdę oszczędza czas.

Obrazy .NET od wersji 8 słuchają domyślnie na porcie **8080** i mają wbudowanego użytkownika bez uprawnień (`USER $APP_UID`).

## Dockerfile: najważniejsze instrukcje

| Instrukcja | Do czego | Przykład |
|---|---|---|
| `FROM` | obraz bazowy (zawsze z konkretnym tagiem) | `FROM node:22-alpine` |
| `RUN` | polecenie przy budowaniu, wynik to nowa warstwa | `RUN apt-get update && apt-get install -y curl` |
| `COPY` | pliki z kontekstu do obrazu | `COPY . /app` |
| `ADD` | jak `COPY`, ale rozpakowuje archiwa i pobiera z URL (zwykle wystarcza `COPY`) | `ADD app.tar.gz /opt/` |
| `WORKDIR` | katalog roboczy dla kolejnych instrukcji i kontenera | `WORKDIR /app` |
| `ENV` | zmienna środowiskowa (w obrazie i kontenerze) | `ENV NODE_ENV=production` |
| `ARG` | zmienna tylko na czas budowania (`--build-arg`) | `ARG VERSION=1.0.0` |
| `EXPOSE` | dokumentuje port, na którym słucha aplikacja (nie publikuje go) | `EXPOSE 8080` |
| `USER` | użytkownik, jako który działa proces | `USER node` |
| `VOLUME` | punkt montowania wolumenu | `VOLUME /var/log/nginx` |
| `LABEL` | metadane obrazu | `LABEL org.opencontainers.image.version="1.0"` |
| `HEALTHCHECK` | jak sprawdzać, czy kontener jest zdrowy | `HEALTHCHECK CMD curl -f http://localhost/ \|\| exit 1` |
| `CMD` | domyślne polecenie albo domyślne argumenty dla `ENTRYPOINT` | `CMD ["nginx", "-g", "daemon off;"]` |
| `ENTRYPOINT` | stały program, który uruchamia kontener | `ENTRYPOINT ["dotnet", "sample.dll"]` |
| `SHELL` | powłoka dla `RUN` w formie shell | `SHELL ["/bin/bash", "-c"]` |

## CMD a ENTRYPOINT

- `CMD` to domyślne polecenie. Wszystko, co podasz po nazwie obrazu w `docker run`, **zastępuje** całe `CMD`.
- `ENTRYPOINT` to program, który uruchamia się zawsze. Argumenty z `docker run` (albo z `CMD`) są do niego **dopisywane**. Zmienisz go tylko flagą `--entrypoint`.
- Razem: `ENTRYPOINT` mówi *co* uruchomić, a `CMD` podaje *domyślne argumenty*.

Kontener jako narzędzie, `ping` z domyślnym celem:

```dockerfile
FROM busybox:1.37
ENTRYPOINT ["ping", "-c", "3"]
CMD ["localhost"]
```

```bash
docker build -t pinger:1.0 -f- . <<'EOF'
FROM busybox:1.37
ENTRYPOINT ["ping", "-c", "3"]
CMD ["localhost"]
EOF
docker run --rm pinger:1.0               # ping -c 3 localhost
docker run --rm pinger:1.0 8.8.8.8       # ping -c 3 8.8.8.8 (CMD zastąpione)
docker run --rm --entrypoint echo pinger:1.0 hej   # inny program zamiast ping
```

Zapisuj obie instrukcje w **formie exec** (`["program", "arg"]`). Forma shell (`CMD node app.js`) uruchamia `/bin/sh -c`, więc to powłoka jest procesem nr 1 i aplikacja nie dostaje `SIGTERM` przy `docker stop`.

## docker build: przydatne flagi

| Flaga | Do czego | Przykład |
|---|---|---|
| `-t` | nazwa i tag obrazu | `docker build -t moja-aplikacja:1.0 .` |
| `-f` | inny plik niż `Dockerfile` | `docker build -f Dockerfile.single -t sample:single .` |
| `--build-arg` | wartość dla `ARG` | `docker build --build-arg VERSION=1.2.3 -t app:1.2.3 .` |
| `--no-cache` | budowanie bez cache warstw | `docker build --no-cache -t app:1.0 .` |
| `--platform` | budowanie na inną architekturę (np. amd64 na Macu z Apple Silicon) | `docker build --platform linux/amd64 -t app:1.0-amd64 .` |
| `--progress=plain` | pełny log kroków (widać `CACHED`) | `docker build --progress=plain -t app:1.0 .` |
| `--target` | budowanie tylko do wskazanego etapu multi-stage | `docker build --target build -t sample:build .` |
