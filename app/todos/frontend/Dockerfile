# --- Etap 1: build aplikacji React (Vite) ---
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# --- Etap 2: tylko statyczne pliki + nginx ---
# nginx-unprivileged: oficjalny wariant od twórców nginx, działa jako UID 101 (nie root)
# i słucha na porcie 8080 (porty <1024 wymagałyby roota).
FROM nginxinc/nginx-unprivileged:1.29-alpine

# Domyślny adres backendu — w compose to usługa "api", w Kubernetesie Service "api"
ENV API_HOST=api \
    API_PORT=3001

COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080
