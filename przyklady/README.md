# Przykłady z zajęć

Gotowe, działające pliki do tematów ze slajdów: pełne wersje YAML-i i Dockerfile, które na slajdzie są skrócone. Każdy katalog ma własny `README.md` (co jest w środku i jak uruchomić).

Jak z nich korzystać:
- **Na zajęciach:** prowadzący odsyła do pliku, kiedy na slajdzie jest tylko fragment.
- **W labie:** gdy nie wiesz, jak zacząć YAML, otwórz przykład z tego samego tematu, skopiuj i przerób. Lab każe zwykle napisać coś trochę innego niż przykład.
- **Po szkoleniu:** wzorce do własnych projektów.

Manifesty Kubernetesa nie mają `namespace:` (trafiają do Twojego domyślnego) i mają `resources` (w namespace jest quota). Uruchamiasz je z katalogu repo: `kubectl apply -f przyklady/k8s/<katalog>/<plik>.yaml`. Katalogi dochodzą razem z labami danego dnia (`git pull`).

| Katalog | Dzień | Temat | Lab | Co jest w środku |
|---|---|---|---|---|
| [`docker/build/`](docker/build/) | 1 | Obrazy i Dockerfile | lab03 | Dockerfile: nginx, Node z cache zależności, .NET multi-stage |
| [`docker/compose/`](docker/compose/) | 1 | Bezpieczeństwo i Compose | lab04 | Compose: nginx, shoppinglist (Flask + PostgreSQL), skalowanie za nginx |
