FROM python:3.13-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .

# bez roota: numeryczny UID, żeby runAsNonRoot w Kubernetesie dało się sprawdzić
USER 10001
EXPOSE 8080
CMD ["python", "app.py"]
