FROM python:3.13-slim

# Logi Pythona od razu na stdout (docker logs), bez plików .pyc
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Użytkownik bez uprawnień roota
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 5000

CMD ["python", "app.py"]
