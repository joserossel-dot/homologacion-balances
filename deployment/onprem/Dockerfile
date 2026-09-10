# Desarrollo admite la etiqueta multi-arquitectura. Un build de release debe
# sobrescribir PYTHON_BUILD_IMAGE con `python:...@sha256:<digest verificado>`.
ARG PYTHON_BUILD_IMAGE=python:3.12-slim-bookworm
ARG TESSERACT_OCR_VERSION=5.3.0-2
ARG TESSERACT_SPA_VERSION=1:4.1.0-2
FROM ${PYTHON_BUILD_IMAGE} AS builder

ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:${PATH}" \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && python -m venv "${VIRTUAL_ENV}" \
    && pip install --no-cache-dir poetry==2.4.1

WORKDIR /build
COPY pyproject.toml poetry.lock README.md ./
RUN poetry config virtualenvs.create false \
    && poetry install --only main --no-root --no-interaction --no-ansi


FROM ${PYTHON_BUILD_IMAGE} AS runtime

ARG APP_UID=10001
ARG APP_GID=10001
ARG TESSERACT_OCR_VERSION
ARG TESSERACT_SPA_VERSION

ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:${PATH}" \
    PYTHONPATH="/app:/app/src" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/var/lib/homologacion \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        libgl1 \
        poppler-utils \
        "tesseract-ocr=${TESSERACT_OCR_VERSION}" \
        "tesseract-ocr-spa=${TESSERACT_SPA_VERSION}" \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid "${APP_GID}" homologacion \
    && useradd --uid "${APP_UID}" --gid "${APP_GID}" \
        --home-dir /var/lib/homologacion --no-create-home --shell /usr/sbin/nologin \
        homologacion \
    && install -d -o homologacion -g homologacion \
        /app /var/lib/homologacion /var/lib/homologacion/runtime

COPY --from=builder /opt/venv /opt/venv
WORKDIR /app
COPY --chown=homologacion:homologacion . .
COPY --chown=homologacion:homologacion deployment/onprem/run-app.sh /usr/local/bin/run-app
COPY --chown=homologacion:homologacion deployment/onprem/run-bootstrap.sh /usr/local/bin/run-bootstrap
COPY --chown=homologacion:homologacion scripts/onprem_ocr_entrypoint.sh /usr/local/bin/onprem-ocr-entrypoint
RUN chmod 0555 /usr/local/bin/run-app /usr/local/bin/run-bootstrap /usr/local/bin/onprem-ocr-entrypoint \
    && date -u +%Y-%m-%dT%H:%M:%SZ > /app/.build_date \
    && python scripts/ocr_preflight.py --require-spa --output /app/.ocr_runtime.json

USER homologacion:homologacion

EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=5 \
    CMD curl --fail --silent http://127.0.0.1:8501/_stcore/health || exit 1

ENTRYPOINT ["/usr/local/bin/onprem-ocr-entrypoint"]
