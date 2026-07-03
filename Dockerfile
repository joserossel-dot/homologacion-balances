# Usamos una imagen oficial de Python
FROM python:3.10-slim

# Instalar las librerías del sistema (Añadimos build-essential por seguridad)
RUN apt-get update && apt-get install -y \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-spa \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Instalar Poetry dentro del contenedor
RUN pip install poetry

# Configurar el directorio de trabajo
WORKDIR /app

# Copiar los archivos de configuración de Poetry
COPY pyproject.toml poetry.lock* ./

# CAMBIO CLAVE: Añadimos --no-root para que no falle al no encontrar el código aún
RUN poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi --no-root

# Ahora sí, copiamos todo el código del proyecto
COPY . .

# Comando de inicio
CMD ["poetry", "run", "python", "src/app.py"]
