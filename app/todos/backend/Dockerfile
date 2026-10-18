FROM node:22-alpine

ENV NODE_ENV=production
WORKDIR /usr/src/app

# Najpierw tylko manifesty zależności — ta warstwa (i npm ci) idzie z cache,
# dopóki nie zmienisz package.json / package-lock.json
COPY package.json package-lock.json ./
RUN npm ci --omit=dev && npm cache clean --force

COPY . .

# Proces nie działa jako root (użytkownik node jest w obrazie bazowym)
USER node

EXPOSE 3001
CMD ["node", "server.js"]
