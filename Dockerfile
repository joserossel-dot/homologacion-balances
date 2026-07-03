# Cambiamos a Python 3.12 para cumplir con el requisito de tu pyproject.toml (^3.12)
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

# Copiamos todo el proyecto primero
COPY . .

# Desactivamos el entorno virtual e instalamos las dependencias con la versión de Python correcta
RUN poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi

# Comando de inicio
CMD ["poetry", "run", "python", "src/app.py"]
