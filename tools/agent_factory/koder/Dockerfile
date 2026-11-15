# Obraz robotnika: zależności testów NotarAI + mini-swe-agent. Bez sekretów, bez kodu repo.
FROM public.ecr.aws/docker/library/python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /tmp/requirements.txt
RUN grep -vE '^(faster-whisper|playwright)' /tmp/requirements.txt > /tmp/req.txt \
    && pip install --no-cache-dir -r /tmp/req.txt mini-swe-agent==2.4.6
ENV MSWEA_CONFIGURED=true MSWEA_COST_TRACKING=ignore_errors HOSTED_VLLM_API_KEY=local-only \
    HOME=/tmp PYTHONDONTWRITEBYTECODE=1
WORKDIR /repo
