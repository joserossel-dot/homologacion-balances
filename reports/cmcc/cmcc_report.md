# CMCC — Catálogo Maestro de Conceptos Contables

## Reporte de Infraestructura

## Arquitectura

El CMCC sigue una arquitectura en capas:

```
┌──────────────────────────────────────────────┐
│                  cmcc.py                      │  ← API de alto nivel
│         CMCC() — Punto de entrada único       │
├──────────────────────────────────────────────┤
│  concept.py  │  matcher.py  │  normalizer.py  │  ← Lógica de negocio
├──────────────────────────────────────────────┤
│  repository.py  │  metrics.py  │  builder.py  │  ← Infraestructura
├──────────────────────────────────────────────┤
│              cmcc.json / schema.json          │  ← Almacenamiento
└──────────────────────────────────────────────┘
```

## Clases Creadas

### `Concept` (`knowledge/concept.py`)
- Dataclass con 16 campos: id, codigo, nombre, categoria, tipo_estado_financiero,
  sinonimos, abreviaturas, variantes, palabras_clave, patrones, ejemplos,
  empresas, confidence, version, ultima_revision, metadata
- Métodos: `to_dict()`, `from_dict()`, `add_variant()`, `add_synonym()`,
  `add_abbreviation()`, `add_example()`, `add_empresa()`, `all_tokens`,
  `coverage_score`

### `Normalizer` (`knowledge/normalizer.py`)
- Pipeline de 8 transformaciones: lowercase → sin acentos → sin puntuación →
  expandir abreviaturas → normalizar romanos → espacios → singularizar →
  stopwords
- Retorna `NormalizerResult(text, [transformaciones_aplicadas])`
- 46 abreviaturas configuradas (adm, depr, prov, cta, cxc, cxp, etc.)
- Stopwords configurables (19 por defecto)
- Singularización heurística: ~50 reglas de plural a singular

### `Matcher` (`knowledge/matcher.py`)
- Entrada: texto crudo → Normalizer → tokenización → `find_candidates()`
- Scoring multicapa: tokens compartidos, coincidencia exacta, sinónimos,
  patrones regex, ejemplos, abreviaturas, variantes
- Retorna `MatchResult(concept, score, [reasons])`
- Top N configurable (10 por defecto)

### `Repository` (`knowledge/repository.py`)
- Carga/guarda `knowledge/cmcc.json`
- Índices: por id, por código
- Búsqueda: `find_by_id()`, `find_by_codigo()`, `find_by_name()`,
  `find_candidates(tokens)` con scoring Jaccard + overlap

### `Builder` (`knowledge/builder.py`)
- Lee `unclassified.xlsx`
- Para cada cuenta: normaliza → matchea → genera propuesta
- Guarda `knowledge/proposals/proposals.xlsx` y `.json`
- Cada propuesta: texto_observado, texto_normalizado, concepto_sugerido,
  código_sugerido, score, razón, empresa, frecuencia

### `Metrics` (`knowledge/metrics.py`)
- Métricas: cantidad de conceptos, variantes, sinónimos, abreviaturas, ejemplos
- Distribuciones: confianza, categoría, estado financiero
- Cobertura potencial: qué % de conceptos tienen variantes/sinónimos/abreviaturas

### `CMCC` (`knowledge/cmcc.py`)
- API unificada: `normalize()`, `match()`, `add_variant()`, `add_synonym()`,
  `create_concept()`, `load()`, `save()`, `metrics`, `concepts`, `count`

## Dependencias

| Módulo | Dependencias externas |
|--------|----------------------|
| concept.py | Ninguna (stdlib) |
| normalizer.py | Ninguna (stdlib) |
| repository.py | json, pathlib |
| matcher.py | knowledge.normalizer, knowledge.repository |
| builder.py | pandas, openpyxl |
| metrics.py | collections |
| cmcc.py | Todos los anteriores |

No se requieren dependencias externas nuevas. pandas/openpyxl ya están
en el proyecto.

## API Pública

```python
from knowledge.cmcc import CMCC

cmcc = CMCC()
cmcc.load()

# Normalizar
result = cmcc.normalize("Gastos de Adm. y Vtas")
# → NormalizerResult(text='gastos administracion venta', transforms=[...])

# Matchear
matches = cmcc.match("Caja General", top_n=5)
# → [MatchResult(concept, score, reasons), ...]

# Administrar
cmcc.add_variant("AC.01", "Caja Chica USD")
cmcc.add_synonym("PC.01", "Acreedores Comerciales")
cmcc.add_abbreviation("AC.01", "cj")

# Crear concepto
from knowledge.concept import Concept
nuevo = Concept(id="CUSTOM.01", codigo="CUSTOM.01", nombre="...", ...)
cmcc.create_concept(nuevo)
cmcc.save()

# Consultar
print(cmcc.count)              # → 52
print(cmcc.metrics.report())   # → dict con métricas
```

## Tests

| Archivo | Tests | Cobertura del módulo |
|---------|-------|---------------------|
| tests/test_concept.py | 11 | concept.py: 100% |
| tests/test_normalizer.py | 21 | normalizer.py: 100% |
| tests/test_repository.py | 15 | repository.py: 99% |
| tests/test_matcher.py | 13 | matcher.py: 92% |
| tests/test_cmcc.py | 16 | cmcc.py: 97% |
| tests/test_metrics.py | 12 | metrics.py: 99% |
| tests/test_builder.py | 3 | builder.py: 100% |
| **Total** | **91** | **promedio: ~98%** |

## Estado del Catálogo

| Indicador | Valor |
|-----------|-------|
| Conceptos en cmcc.json | 0 (inicial) |
| Códigos disponibles en `catalogo_maestro.json` | 52 |
| Entradas en `diccionario.json` | 826 |
| Abreviaturas configuradas en normalizer | 46 |
| Reglas de singularización | ~50 |
| Stopwords por defecto | 19 |

## Próximos Pasos

1. **Poblar CMCC desde `catalogo_maestro.json`**: Convertir los 52 códigos
   estándar en objetos Concept con sus categorías y nombres estándar.

2. **Poblar desde `diccionario.json`**: Agregar las 826 cuentas reales como
   variantes de los conceptos correspondientes.

3. **Ejecutar Builder**: Procesar `unclassified.xlsx` para generar propuestas
   de nuevos conceptos, variantes y sinónimos.

4. **Revisión contable**: Un contador revisa las propuestas y confirma o
   rechaza cada una.

5. **Integrar con el pipeline**: Reemplazar la comparación directa contra
   `diccionario.json` por `CMCC.match()` en el clasificador.

6. **Ciclo iterativo**: Builder → Revisión → Actualización → Re-ejecución.

## Nota

Esta fase NO modifica el clasificador, el parser, el pipeline, ni los
resultados actuales. Solo crea la infraestructura para la siguiente fase.
