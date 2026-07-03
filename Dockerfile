# Pasamos a Python 3.11 que es más compatible con las últimas versiones de Poetry y librerías
FROM python:3.11-slim

# Instalar librerías del sistema (Añadimos 'git' por si alguna librería se descarga desde GitHub)
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

# SOLUCIÓN: Copiamos TODO el proyecto primero para que Poetry encuentre la carpeta 'src', 
# el 'README.md' y cualquier archivo que necesite para validar la instalación.
COPY . .

# Desactivamos el entorno virtual e instalamos TODO (incluyendo el proyecto de forma segura)
RUN poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi

# Comando de inicio
CMD ["poetry", "run", "python", "src/app.py"]
