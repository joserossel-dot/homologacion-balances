# Usamos Python 3.12 como requiere tu pyproject.toml
FROM python:3.12-slim

# Instalar librerías del sistema (Poppler, Tesseract y herramientas esenciales)
RUN apt-get update && apt-get install -y \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-spa \
    curl \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Instalar Poetry
RUN pip install --no-cache-dir poetry

# Configurar el directorio de trabajo
WORKDIR /app

# Instalar dependencias antes de copiar el código para aprovechar la caché.
COPY pyproject.toml poetry.lock README.md ./
RUN poetry config virtualenvs.create false \
    && poetry install --only main --no-root --no-interaction --no-ansi

# Copiar el código y registrar la fecha UTC del artefacto desplegado.
COPY . .
RUN date -u +%Y-%m-%dT%H:%M:%SZ > /app/.build_date

# Forzamos a Python a mirar tanto en la raíz como en la carpeta src
ENV PYTHONPATH="/app:/app/src"

# CAMBIO CRUCIAL: Arrancamos con 'streamlit run', asignando el puerto 10000 de Render
CMD ["sh", "-c", "streamlit run app_validacion.py --server.port=${PORT:-10000} --server.address=0.0.0.0"]
