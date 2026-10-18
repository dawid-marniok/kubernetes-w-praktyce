# Oficjalny obraz nginx z przypiętą wersją (nigdy :latest)
FROM nginx:1.29

# Narzędzia do zaglądania do kontenera (docker exec -it ... bash)
# Jedna instrukcja RUN = jedna warstwa; czyścimy listy apt w tej samej warstwie
RUN apt-get update \
    && apt-get install -y --no-install-recommends vim curl \
    && rm -rf /var/lib/apt/lists/*

# Pliki statyczne naszej strony
COPY index.html /usr/share/nginx/html/index.html

# Zmienna środowiskowa (składnia KLUCZ=wartość)
ENV NGINX_HOST=localhost

# Dokumentacja: kontener słucha na 80 (publikujesz i tak przez -p)
EXPOSE 80

# Katalog logów jako wolumen
VOLUME /var/log/nginx

# nginx na pierwszym planie — proces główny kontenera (PID 1)
CMD ["nginx", "-g", "daemon off;"]
