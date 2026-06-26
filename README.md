# Plataforma de Homologación de Balances Tributarios Chilenos

Transforma balances tributarios chilenos (PDF y Excel) en estados financieros normalizados orientados al análisis de riesgo crediticio bancario.

## Funcionalidades

- Parser universal de PDFs (texto nativo y escaneados con OCR) y Excel
- Clasificación híbrida automática: código de cuenta → diccionario → reglas regex
- 52 categorías estándar orientadas al análisis crediticio bancario chileno
- Reglas especiales crediticias (criterio conservador BCI/Santander)
- Validación de cuadre utilidad ER vs Patrimonio
- Cola de revisión humana con selección en lote
- Visor de documento integrado con zoom, rotación y navegación por páginas
- Feedback loop: correcciones persistidas en PostgreSQL
- Exportación Excel con balance homologado + apertura de cuentas

## Requisitos

- Python 3.12+
- PostgreSQL 16
- Tesseract OCR (con idioma español)
- Poppler (pdftoppm)

## Instalación (Mac Intel)

```bash
brew install python@3.12 postgresql@16 tesseract tesseract-lang poppler
brew services start postgresql@16
pip3 install -r requirements.txt
```

## Configuración base de datos

```bash
psql postgres -c "CREATE USER postgres WITH PASSWORD 'claude123' SUPERUSER;"
psql postgres -c "CREATE DATABASE homologacion;"
psql -U postgres -d homologacion -f schema_minimo.sql
python3 cargar_datos.py
```

## Ejecución

```bash
streamlit run app_validacion.py
```

## Estructura del proyecto

```
├── app_validacion.py           # Interfaz principal Streamlit
├── parser_universal.py         # Parser PDF (nativo + OCR) y Excel
├── clasificador_codigo_cuenta.py  # Clasificación por código numérico
├── reglas_especiales.py        # Reglas crediticias especiales D1-D5
├── extractor_metadata.py       # Detección automática RUT/razón social/período
├── db_repository.py            # Capa de persistencia PostgreSQL
├── cargar_datos.py             # Carga inicial de datos
├── schema_minimo.sql           # Esquema de base de datos
├── catalogo_maestro.json       # 52 códigos estándar
├── diccionario.json            # 710+ cuentas homologadas
└── requirements.txt
```

## Catálogo maestro

52 códigos estándar organizados en:
- Activo Corriente (AC.01 – AC.09)
- Activo No Corriente (ANC.01 – ANC.08)
- Pasivo Corriente (PC.01 – PC.08)
- Pasivo No Corriente (PNC.01 – PNC.05)
- Patrimonio (PAT.01 – PAT.05)
- Estado de Resultados (ER.01 – ER.16)

## Notas

- Los archivos de balance (PDF/Excel) **no se incluyen** en el repositorio por confidencialidad.
- La contraseña de PostgreSQL por defecto es `claude123`. Cámbiala en producción.
