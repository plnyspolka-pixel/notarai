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

# In the real pilot a custodian must provide an independently verified
# trusted-origin-root.json and bind its SHA-256 into the image build.
# The CI smoke image intentionally lacks it; the worker then refuses all
# SQS jobs BEFORE decryption (fail closed). The optional hash is only a
# build-consistency check; actual trust requires custodian approval of the
# measured Nitro image/PCR and independently controlled KMS policy.
ARG NOTARAI_TRUSTED_ORIGIN_ROOT_SHA256=""
RUN if [ -n "$NOTARAI_TRUSTED_ORIGIN_ROOT_SHA256" ]; then \
      test -s /opt/notarai/confidential/trusted-origin-root.json && \
      printf '%s  %s\\n' "$NOTARAI_TRUSTED_ORIGIN_ROOT_SHA256" \
        /opt/notarai/confidential/trusted-origin-root.json | sha256sum -c -; \
    else \
      echo 'SEC-03: custody trust root not provided; guest must reject all decrypts'; \
    fi

# The guest doesn't need the root account to run browser and KMS clients.
RUN useradd --uid 10001 --no-create-home --home-dir /tmp --shell /usr/sbin/nologin notarai \
    && chmod -R a+rX /opt/notarai \
    && chmod -R a+rX /ms-playwright
USER 10001:10001

CMD ["python", "-m", "confidential.worker"]
