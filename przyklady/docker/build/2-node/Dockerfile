# Oficjalny obraz Node.js, wersja LTS na Alpine (mały)
FROM node:22-alpine

ENV NODE_ENV=production
WORKDIR /usr/src/app

# Najpierw manifesty zależności: ta warstwa i npm ci idą z cache,
# dopóki nie zmienisz package.json / package-lock.json
COPY package.json package-lock.json ./
RUN npm ci --omit=dev

# Potem kod aplikacji (zmienia się najczęściej)
COPY . .

# Nie uruchamiamy aplikacji jako root
USER node

EXPOSE 3000

# Forma exec: node jest PID 1 i dostaje SIGTERM przy docker stop
CMD ["node", "app.js"]
