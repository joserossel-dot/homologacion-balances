# Desarrollo admite la etiqueta multi-arquitectura. Un build de release debe
# sobrescribir PYTHON_BUILD_IMAGE con `python:...@sha256:<digest verificado>`.
ARG PYTHON_BUILD_IMAGE=python:3.12-slim-bookworm
FROM ${PYTHON_BUILD_IMAGE}

ARG TESSERACT_OCR_VERSION=5.3.0-2
ARG TESSERACT_SPA_VERSION=1:4.1.0-2

# Instalar librerías del sistema (Poppler, Tesseract y herramientas esenciales)
RUN apt-get update && apt-get install -y \
    poppler-utils \
    "tesseract-ocr=${TESSERACT_OCR_VERSION}" \
    "tesseract-ocr-spa=${TESSERACT_SPA_VERSION}" \
    curl \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Instalar una versión reproducible de Poetry.
RUN pip install --no-cache-dir poetry==2.4.1

# Configurar el directorio de trabajo
WORKDIR /app

# Instalar dependencias antes de copiar el código para aprovechar la caché.
COPY pyproject.toml poetry.lock README.md ./
RUN poetry config virtualenvs.create false \
    && poetry install --only main --no-root --no-interaction --no-ansi

# Copiar el código y registrar la fecha UTC del artefacto desplegado.
COPY . .
RUN date -u +%Y-%m-%dT%H:%M:%SZ > /app/.build_date \
    && python scripts/ocr_preflight.py --require-spa --output /app/.ocr_runtime.json

# Forzamos a Python a mirar tanto en la raíz como en la carpeta src
ENV PYTHONPATH="/app:/app/src"

# CAMBIO CRUCIAL: Arrancamos con 'streamlit run', asignando el puerto 10000 de Render
CMD ["sh", "-c", "python scripts/ocr_preflight.py --require-spa --compare /app/.ocr_runtime.json && streamlit run app_validacion.py --server.port=${PORT:-10000} --server.address=0.0.0.0"]
