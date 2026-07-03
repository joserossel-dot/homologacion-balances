# Usamos una imagen oficial de Python
FROM python:3.10-slim

# Instalar las librerías del sistema (Poppler, Tesseract y herramientas básicas)
RUN apt-get update && apt-get install -y \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-spa \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalar Poetry dentro del contenedor
RUN pip install poetry

# Configurar el directorio de trabajo
WORKDIR /app

# Copiar los archivos de configuración de Poetry
COPY pyproject.toml poetry.lock* ./

# Configurar Poetry para que instale los paquetes globalmente en el contenedor
RUN poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi

# Copiar el resto del código del proyecto
COPY . .

# Comando de inicio con la sintaxis JSON correcta (revisa si tu archivo principal es app.py o main.py)
CMD ["poetry", "run", "python", "src/app.py"]
