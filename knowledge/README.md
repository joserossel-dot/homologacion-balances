# Catálogo Maestro de Conceptos Contables (CMCC)

## ¿Qué es un Concepto?

Un **Concepto** representa una categoría contable estándar dentro del catálogo maestro.
Cada concepto corresponde a un código estándar del plan de cuentas (ej: `AC.01` = Caja y Bancos).

Un concepto contiene:
- **nombre**: Nombre estándar (ej: "Caja y Bancos")
- **código**: Código estándar (ej: "AC.01")
- **sinónimos**: Nombres alternativos equivalentes (ej: "Efectivo", "Disponible")
- **abreviaturas**: Formas abreviadas (ej: "cta cte", "cxc")
- **variantes**: Variantes observadas en datos reales (ej: "Banco Bci USD", "Caja $")
- **palabras clave**: Términos clave para matching
- **patrones**: Expresiones regulares para detectar el concepto
- **ejemplos**: Nombres de cuentas reales que corresponden a este concepto

## ¿Qué es una Variante?

Una **variante** es una forma específica de un nombre de cuenta observada en datos reales.
Por ejemplo, para el concepto "Caja y Bancos" (`AC.01`), las variantes incluyen:
- "Banco Bci $ Egresos DSI"
- "Banco Santander USD"
- "Caja General"

Las variantes se extraen automáticamente del archivo `diccionario.json`.

## ¿Qué es un Sinónimo?

Un **sinónimo** es un nombre alternativo equivalente al nombre estándar.
Por ejemplo, "Efectivo" es sinónimo de "Caja y Bancos".

Los sinónimos permiten matching semántico: si una cuenta dice "Efectivo General",
el sistema puede asociarlo al concepto "Caja y Bancos".

## ¿Cómo crece el CMCC?

1. **Inicialización**: Se construye desde `catalogo_maestro.json` (52 códigos estándar)
   y `diccionario.json` (826 cuentas reales mapeadas a códigos).
2. **Extracción**: `Builder` procesa cuentas no clasificadas y genera propuestas.
3. **Revisión**: Un contador revisa las propuestas y confirma/rechaza cada una.
4. **Actualización**: Las propuestas confirmadas se incorporan como variantes,
   sinónimos, o nuevos conceptos.
5. **Iteración**: El ciclo se repite, aumentando la cobertura en cada iteración.

## ¿Cómo interactuará con el pipeline?

El CMCC reemplazará el matching basado en `diccionario.json` por un matching
semántico multicapa:

1. **Normalización**: El texto pasa por `Normalizer` (acentos, puntuación,
   abreviaturas, mayúsculas, singularización).
2. **Matching**: `Matcher` busca los 10 mejores conceptos candidatos usando
   tokens compartidos, sinónimos, abreviaturas, patrones y ejemplos.
3. **Propuestas**: `Builder` genera propuestas para cuentas no clasificadas.
4. **Integración**: El pipeline usará `CMCC.match()` en lugar de la comparación
   directa contra `diccionario.json`.

## API Pública

```python
from knowledge.cmcc import CMCC

cmcc = CMCC()
cmcc.load()

# Normalizar texto
result = cmcc.normalize("GASTOS ADM Y VTAS")
print(result.text)  # "gasto administracion venta"

# Buscar conceptos candidatos
matches = cmcc.match("Caja General")
for m in matches:
    print(f"{m.concept.codigo} - {m.concept.nombre}: score {m.score}")

# Agregar variante
cmcc.add_variant("AC.01", "Caja Chica USD")

# Agregar sinónimo
cmcc.add_synonym("AC.01", "Disponible")

# Crear nuevo concepto
from knowledge.concept import Concept
nuevo = Concept(
    id="CUSTOM.01",
    codigo="CUSTOM.01",
    nombre="Mi Concepto",
    categoria="activo_corriente",
    tipo_estado_financiero="balance",
    confidence=0.8,
    version="1.0.0",
    ultima_revision="2026-07-08"
)
cmcc.create_concept(nuevo)
cmcc.save()
```

## Estructura de Archivos

```
knowledge/
├── __init__.py
├── cmcc.py          # API de alto nivel
├── concept.py       # Clase Concept
├── normalizer.py    # Normalizador de texto
├── matcher.py       # Matcher de conceptos
├── repository.py    # Repositorio JSON
├── builder.py       # Generador de propuestas
├── metrics.py       # Métricas
├── cmcc.json        # Datos del catálogo
├── schema.json      # Esquema oficial
├── README.md
└── proposals/       # Propuestas generadas
    ├── proposals.json
    └── proposals.xlsx
```
