# pieczapp - kontener produkcyjny (App Runner / ECS, Linux)
#
# Budowa:   docker build -t pieczapp .
# Test:     docker run -p 8000:8000 -e PIECZAPP_HOST=0.0.0.0 pieczapp
#
# W chmurze ustaw:
#   PIECZAPP_HOST=0.0.0.0          (kontener slucha dla load balancera)
#   PIECZAPP_MAGAZYN=s3
#   PIECZAPP_S3_BUCKET=...
#   PIECZAPP_MULTI=true
#   PIECZAPP_ADMIN_TOKEN=...       (openssl rand -hex 32)
#   AWS_REGION=eu-central-1
# Poswiadczenia AWS: rola IAM instancji/uslugi (NIE klucze w env).
FROM python:3.12-slim

WORKDIR /app

# faster-whisper i playwright sa opcjonalne lokalnie; w chmurze pomijamy
# (transkrypcja i asysta formularzy to funkcje stanowiska notariusza).
COPY requirements.txt .
RUN grep -vE "^(faster-whisper|playwright)" requirements.txt > /tmp/req.txt \
    && pip install --no-cache-dir -r /tmp/req.txt

COPY . .

# Kontener nie trzyma danych na stale - dysk to cache, prawda jest w S3.
ENV PIECZAPP_HOST=0.0.0.0 \
    PIECZAPP_PORT=8000 \
    PYTHONUNBUFFERED=1

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/zdrowie')" || exit 1

CMD ["python", "app.py"]
