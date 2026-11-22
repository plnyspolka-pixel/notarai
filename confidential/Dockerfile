# Build only for the separate Nitro guest; not used by existing Fargate app.
# Pin by immutable digest in the AWS task definition after an audited build.
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    HOME=/tmp \
    XDG_CACHE_HOME=/tmp \
    TMPDIR=/tmp

WORKDIR /opt/notarai

# Playwright's bundled Node binary needs libatomic even before install --with-deps.
RUN apt-get update && apt-get install -y --no-install-recommends libatomic1 \
    && rm -rf /var/lib/apt/lists/*

COPY confidential/requirements.txt /opt/notarai/confidential/requirements.txt
RUN pip install --no-cache-dir -r confidential/requirements.txt \
    && python -m playwright install --with-deps chromium

COPY confidential/ /opt/notarai/confidential/

# Public key only. No defaults: image build fails without the pinned notary
# origin anchor. This file is covered by the final audited image/PCR digest.
ARG TRUSTED_ORIGIN_ISSUER_ID
ARG TRUSTED_ORIGIN_PUBLIC_B64
RUN python -m confidential.bake_trust

# The guest doesn't need the root account to run browser and KMS clients.
RUN useradd --uid 10001 --no-create-home --home-dir /tmp --shell /usr/sbin/nologin notarai \
    && chmod -R a+rX /opt/notarai \
    && chmod -R a+rX /ms-playwright
USER 10001:10001

CMD ["python", "-m", "confidential.customer_v3_worker"]
