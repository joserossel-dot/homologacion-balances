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

# Desactivar el entorno virtual e instalar las dependencias
RUN poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi

# SOLUCIÓN: Le enseñamos a Python dónde encontrar 'db_repository' y el resto de tus módulos
ENV PYTHONPATH=/app:/app/src

# Comando de inicio
CMD ["poetry", "run", "python", "app_validacion.py"]
