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

# Etap 1: wersja przegladarkowa aplikacji klienta (mobilna/, Expo) pod
# /aplikacja. Do obrazu trafia tylko statyczny dist/ - node_modules i Node
# zostaja w tym etapie. Adres API domyslny (https://app.notarai.pl), czyli ta
# sama domena, z ktorej strona jest serwowana.
FROM public.ecr.aws/docker/library/node:22-slim AS aplikacja-web
WORKDIR /mobilna
COPY mobilna/package.json mobilna/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY mobilna/ ./
ENV NODE_OPTIONS=--max-old-space-size=1536 \
    EXPO_NO_TELEMETRY=1
RUN npx expo export --platform web --output-dir dist --max-workers 1 \
    && test -f dist/index.html

# Etap 2: aplikacja. Oficjalny obraz Pythona z lustra ECR Public - bez limitow
# pobran Docker Hub, ktore trafiaja wspoldzielone adresy CodeBuild.
FROM public.ecr.aws/docker/library/python:3.12-slim

WORKDIR /app

# faster-whisper i playwright sa opcjonalne lokalnie; w chmurze pomijamy
# (transkrypcja i asysta formularzy to funkcje stanowiska notariusza).
COPY requirements.txt .
RUN grep -vE "^(faster-whisper|playwright)" requirements.txt > /tmp/req.txt \
    && pip install --no-cache-dir -r /tmp/req.txt

COPY . .
COPY --from=aplikacja-web /mobilna/dist /app/mobilna/dist

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
