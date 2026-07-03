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

# Copiar todo el proyecto
COPY . .

# Desactivar el entorno virtual e instalar las dependencias de forma global
RUN poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi

# Forzamos a Python a mirar tanto en la raíz como en la carpeta src
ENV PYTHONPATH="/app:/app/src"

# CAMBIO CLAVE: Ejecutamos directamente con python (sin 'poetry run') para asegurar las rutas
CMD ["python", "app_validacion.py"]
