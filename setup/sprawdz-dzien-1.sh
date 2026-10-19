#!/usr/bin/env bash
# Sprawdza stanowisko przed dniem 1 (Docker). Niczego nie instaluje i nie zmienia.
# Uruchom z katalogu głównego repo (macOS / Linux / WSL / Git Bash):
#   bash setup/sprawdz-dzien-1.sh           # sprawdzenie, ok. 1 min
#   bash setup/sprawdz-dzien-1.sh --pull    # to samo + pobranie obrazów z labów dnia 1 (ok. 4 GB)

BLEDY=0; UWAGI=0
ok()    { printf '  ✅ %s\n' "$1"; }
uwaga() { printf '  ⚠️  %s\n' "$1"; UWAGI=$((UWAGI + 1)); }
blad()  { printf '  ❌ %s\n' "$1"; BLEDY=$((BLEDY + 1)); }
# wersja „x.y…” → liczba x*1000+y, do porównań
num()   { awk -F. '{ printf "%d", $1 * 1000 + $2 }' <<<"$1"; }

OBRAZY="nginx:1.29 nginx:1.29-alpine ubuntu:24.04 busybox:1.37 alpine:3.22 postgres:18 redis:8.2-alpine
nicolaka/netshoot:v0.14 node:22-alpine python:3.13-slim golang:1.25 gcr.io/distroless/static-debian12:nonroot
nginxinc/nginx-unprivileged:1.29-alpine mcr.microsoft.com/dotnet/sdk:10.0 mcr.microsoft.com/dotnet/aspnet:10.0
mongo:7.0 mongo-express:1.0.2-20-alpine3.19"

echo "Docker"
if ! command -v docker >/dev/null 2>&1; then
  blad "brak komendy docker — zainstaluj Docker Desktop (setup/docker-desktop.md)"
  echo; echo "❌ Bez Dockera dalsze sprawdzenie nie ma sensu."; exit 1
fi
SERWER=$(docker version --format '{{.Server.Version}}' 2>/dev/null)
if [[ -z $SERWER ]]; then
  blad "Docker nie odpowiada — uruchom Docker Desktop i poczekaj na zielony status (Linux: sudo systemctl start docker)"
  echo; echo "❌ Bez działającego Dockera dalsze sprawdzenie nie ma sensu."; exit 1
fi
if (( $(num "$SERWER") >= 28000 )); then ok "Docker $SERWER"; else uwaga "Docker $SERWER — zaktualizuj do 28 lub nowszego"; fi

if V=$(docker compose version --short 2>/dev/null); then
  (( $(num "${V#v}") >= 2000 )) && ok "Docker Compose $V" || uwaga "Docker Compose $V — zaktualizuj Docker Desktop (potrzebne v2 lub nowsze)"
else
  blad "brak docker compose (v2) — Linux: sudo apt-get install docker-compose-plugin"
fi
if V=$(docker buildx version 2>/dev/null); then ok "buildx: ${V%% *} $(awk '{print $2}' <<<"$V")"
else blad "brak docker buildx — Linux: sudo apt-get install docker-buildx-plugin"; fi

CPU=$(docker info --format '{{.NCPU}}' 2>/dev/null)
RAM=$(( $(docker info --format '{{.MemTotal}}' 2>/dev/null || echo 0) / 1024 / 1024 / 1024 ))
if (( CPU >= 4 && RAM >= 6 )); then ok "zasoby Dockera: $CPU CPU, ok. $RAM GB RAM"
else uwaga "zasoby Dockera: $CPU CPU, ok. $RAM GB RAM — daj co najmniej 4 CPU i 6 GB (Settings → Resources)"; fi

if docker run --rm busybox:1.37 echo ok >/dev/null 2>&1; then ok "kontener uruchamia się (busybox:1.37)"
else blad "docker run busybox:1.37 nie działa — sprawdź sieć/proxy (setup/docker-desktop.md, „Proxy”)"; fi

ARCH=$(docker info --format '{{.Architecture}}' 2>/dev/null)
case $ARCH in
  aarch64|arm64) ok "architektura $ARCH — obrazy do rejestru budujesz z --platform linux/amd64 (lab03)" ;;
  *) ok "architektura ${ARCH:-?}" ;;
esac

KONF="${DOCKER_CONFIG:-$HOME/.docker}/config.json"
if grep -q 'index.docker.io' "$KONF" 2>/dev/null; then ok "zalogowany do Docker Hub"
else uwaga "brak logowania do Docker Hub — załóż darmowe konto i zrób docker login (limit pobrań na szkoleniu)"; fi

echo; echo "Narzędzia"
if command -v git >/dev/null 2>&1; then ok "$(git --version)"
else blad "brak git — macOS: xcode-select --install · WSL/Linux: sudo apt install git"; fi
if [[ -d labs && -d setup ]]; then ok "jesteś w katalogu repo szkolenia"
else uwaga "uruchom skrypt z katalogu głównego sklonowanego repo (tam, gdzie są labs/ i setup/)"; fi
if command -v aws >/dev/null 2>&1; then
  V=$(aws --version 2>&1 | sed -E 's#^aws-cli/([0-9.]+).*#\1#')
  if (( $(num "$V") >= 2032 )); then ok "AWS CLI $V"; else uwaga "AWS CLI $V — do lab03 potrzebne 2.32 lub nowsze (setup/rejestr.md)"; fi
else
  uwaga "brak AWS CLI — potrzebne w dniu 1 przed lab03 (karta dostępowa, punkt 2; setup/rejestr.md)"
fi

echo; echo "Porty używane w labach dnia 1"
for p in 8080 8081 8082 8090 3000 5001; do
  if (exec 3<>"/dev/tcp/127.0.0.1/$p") 2>/dev/null; then
    uwaga "port $p zajęty — zamknij program albo kontener, który go używa (docker ps)"
  else
    ok "port $p wolny"
  fi
done

if [[ ${1:-} == --pull ]]; then
  echo; echo "Pobieranie obrazów z labów dnia 1"
  for i in $OBRAZY; do
    if docker pull -q "$i" >/dev/null 2>&1; then ok "$i"; else blad "$i — nie udało się pobrać"; fi
  done
fi

echo
if (( BLEDY > 0 )); then
  echo "❌ Błędy: $BLEDY, uwagi: $UWAGI. Popraw błędy przed szkoleniem; jeśli utkniesz, napisz do prowadzącego z wynikiem tego skryptu."
  exit 1
elif (( UWAGI > 0 )); then
  echo "🟡 Gotowe do dnia 1, uwagi: $UWAGI (przejrzyj ⚠️ powyżej)."
else
  echo "✅ SUKCES: stanowisko gotowe do dnia 1."
fi
[[ ${1:-} == --pull ]] || echo "Opcjonalnie, żeby na szkoleniu nie czekać na sieć: bash setup/sprawdz-dzien-1.sh --pull"
