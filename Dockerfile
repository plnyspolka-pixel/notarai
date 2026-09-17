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

# faster-whisper i playwright sa opcjonalne lokalnie; w chmurze pomijamy
# (transkrypcja i asysta formularzy to funkcje stanowiska notariusza).
COPY requirements.txt .
RUN grep -vE "^(faster-whisper|playwright)" requirements.txt > /tmp/req.txt \
    && pip install --no-cache-dir -r /tmp/req.txt

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
