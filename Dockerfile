# notarai - kontener produkcyjny (ECS Fargate, Linux x86_64)
#
# Obraz buduje CodeBuild w AWS (infra/notarai-budowanie.yaml), Docker na
# stanowisku nie jest potrzebny. Lokalnie, jesli Docker jest:
#   docker build -t notarai .
#   docker run -p 8000:8000 notarai
#
# Konfiguracja w chmurze pochodzi z definicji zadania ECS
# (infra/notarai-aplikacja.yaml): tryb S3, wiele kancelarii, token admina
# wstrzykiwany z Secrets Manager. Poswiadczenia AWS: rola zadania, NIGDY
# klucze w zmiennych srodowiskowych.

# Oficjalny obraz Pythona z lustra ECR Public - bez limitow pobran Docker Hub,
# ktore trafiaja wspoldzielone adresy CodeBuild.
FROM public.ecr.aws/docker/library/python:3.12-slim

WORKDIR /app

# Lokalny OCR w trybie chronionym; polski model bez pobierania podczas żądania.
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-pol \
    && rm -rf /var/lib/apt/lists/*

# faster-whisper i playwright sa opcjonalne lokalnie; w chmurze pomijamy
# (transkrypcja i asysta formularzy to funkcje stanowiska notariusza).
COPY requirements.txt .
RUN grep -vE "^(faster-whisper|playwright)" requirements.txt > /tmp/req.txt \
    && pip install --no-cache-dir -r /tmp/req.txt

COPY requirements-pii.txt .
COPY scripts/pobierz_model_pii.py /tmp/pobierz_model_pii.py
# Osobny profil obrazu beta; nie aktywuje flagi chronionej ani produkcji.
ARG NOTARAI_PII=0
RUN if [ "$NOTARAI_PII" = "1" ]; then \
      pip install --no-cache-dir torch==2.9.1 --index-url https://download.pytorch.org/whl/cpu \
      && pip install --no-cache-dir -r requirements-pii.txt \
      && python /tmp/pobierz_model_pii.py /opt/notarai/pii-pl \
      && chmod -R a-w /opt/notarai/pii-pl; \
    fi
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1

COPY . .

# Aplikacja nie dziala jako root. Zapisuje tylko do dane/ (cache spraw),
# prawda jest w S3.
RUN useradd --system --uid 10001 --home-dir /app notarai \
    && mkdir -p /app/dane \
    && chown -R notarai /app/dane
USER notarai

ENV PIECZAPP_HOST=0.0.0.0 \
    PIECZAPP_PORT=8000 \
    PYTHONUNBUFFERED=1

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/zdrowie')" || exit 1

CMD ["python", "app.py"]
