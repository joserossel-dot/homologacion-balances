# Usamos una imagen oficial de Python
FROM python:3.10-slim

# Instalar las librerías del sistema que te faltan (Poppler y Tesseract con idioma español)
RUN apt-get update && apt-get install -y \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-spa \
    && rm -rf /var/lib/apt/lists/*

# Establecer el directorio de trabajo
WORKDIR /app

# Copiar e instalar las dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo el código del proyecto
COPY . .

# Comando de inicio (Copia aquí exactamente el "Start Command" que tienes configurado en Render)
# Por ejemplo, si usas Gunicorn, Uvicorn o directamente Python:
CMD [poetry run streamlit run app_validacion.py --server.port $PORT --server.address 0.0.0.0]
