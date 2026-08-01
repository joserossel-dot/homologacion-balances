# Arquitectura de Extractores Especializados — Sprint 34

Infraestructura definitiva para construir extractores especializados por
familia documental (Nogales, AICSA, Wilug, Gonzagri, ...) **sin romper la
compatibilidad con el Parser Universal**.

Este sprint NO implementa lógica especializada: todos los extractores
delegan 1:1 al Parser Universal. El comportamiento del sistema es
exactamente igual al anterior; solo se agrega una **anotación**
(`resultado.extractor_info`).

---

## 1. Diagrama de arquitectura

```
                     ┌──────────────────────────────────────────────┐
                     │              ParserPDF.parsear()             │
                     └──────────────────────────────────────────────┘
                                      │
                                      ▼
                     ┌──────────────────────────────────────────────┐
                     │    1. _analizar_documento(path)  (Sprint 31) │
                     │   → DocumentProcessingContext (signature)    │
                     └──────────────────────────────────────────────┘
                                      │
                                      ▼   (solo anotación, NO cambia la extracción)
                     ┌──────────────────────────────────────────────┐
                     │   2. _anotar_extractor(resultado) (Sprint 34)│
                     │   → SpecializedExtractorFactory().detect()   │
                     └──────────────────────────────────────────────┘
                                      │
                                      ▼
                     ┌──────────────────────────────────────────────┐
                     │       3. SpecializedExtractorFactory          │
                     │  ┌────────────────────────────────────────┐  │
                     │  │ a. DocumentFingerprint.build(sig,preview)│ │
                     │  │ b. fingerprint_similarity vs centroides  │ │
                     │  │    (familias de document_mining.json)    │ │
                     │  │ c. similitud >= umbral (70)  ?           │ │
                     │  │ d. ¿extractor registrado para la familia?│ │
                     │  └────────────────────────────────────────┘  │
                     └──────────────────────────────────────────────┘
                                      │
                     ┌────────────────┴────────────────┐
                     ▼                                 ▼
        ┌─────────────────────────┐      ┌─────────────────────────┐
        │  Extractores de familia │      │   UniversalExtractor    │
        │  (Nogales, AICSA, ...)  │      │   (default y fallback)  │
        └─────────────────────────┘      └─────────────────────────┘
                     │                                 │
                     └───────────────┬─────────────────┘
                                     ▼
                     ┌──────────────────────────────────────────────┐
                     │           ParserPDF.parsear()  (sin cambios)  │
                     │  → ResultadoParseo + resultado.extractor_info │
                     └──────────────────────────────────────────────┘
```

**Regla de oro:** la extracción siempre la hace `ParserPDF`. El framework de
extractores solo decide *qué* extractor está seleccionado y (en el futuro)
podrá ajustar cómo se parsea cada familia — siempre con el universal como
base.

---

## 2. Componentes

### Paquete `document_intelligence/extractors/`

| Archivo      | Responsabilidad |
|--------------|-----------------|
| `base.py`    | `ExtractorResult` (resultado uniforme) y `SpecializedExtractor` (ABC) |
| `registry.py`| Registro automático (`@register_extractor`) + índice familia→extractor |
| `universal.py`| `UniversalExtractor`: delega 1:1 a `ParserPDF.parsear()`, es el fallback obligatorio |
| `specialized.py` | Scaffolds registrados: `NogalesExtractor`, `AicsaExtractor`, `WilugExtractor`, `GonzagriExtractor` (delegan al universal) |
| `factory.py` | `SpecializedExtractorFactory`: decisión familia→extractor con fallback universal |

### `ExtractorResult`

```python
ExtractorResult(
    extractor_id,      # id del extractor seleccionado
    display_name,      # nombre legible
    result,            # ResultadoParseo real (del Parser Universal)
    family_id,         # familia detectada (cluster_... del mining)
    confidence,        # 0-1 (similitud fingerprint vs centroide)
    elapsed_ms,        # tiempo de extracción
    fallback_used,     # True si se delegó al universal
)
```

### `SpecializedExtractor` (ABC)

```python
class SpecializedExtractor(ABC):
    id: str                 # identificador único (se registra)
    display_name: str       # nombre legible
    supported_families: list[str]  # familias del mining que sabe procesar
    @abstractmethod
    def extract(self, path, context=None) -> ExtractorResult: ...
```

---

## 3. Factory (`SpecializedExtractorFactory`)

Proceso de decisión:

1. **Fingerprint del documento**: reutiliza `signature` del
   `DocumentProcessingContext` + `extract_preview_lines()` → mismo
   `DocumentFingerprint.build` que usa el mining (misma similitud).
2. **Comparación**: `fingerprint_similarity(query, centroid)` contra los
   centroides de las familias de `knowledge_base/document_mining.json`
   (misma función del clustering).
3. **Decisión**:
   - mejor similitud `>= umbral (70)` **y** existe extractor registrado
     para esa familia → se instancia y devuelve ese extractor;
   - en cualquier otro caso → `UniversalExtractor`.

Garantías:

- **Nunca lanza excepción**: cualquier error (contexto roto, JSON faltante,
  PDF ilegible) termina en `UniversalExtractor`.
- `build(path, context)` → devuelve el extractor concreto.
- `detect(path, context)` → dict con `extractor_id`, `display_name`,
  `family_id`, `confidence`, `fallback_used`, `reason`, `elapsed_ms`
  (lo que se guarda en `resultado.extractor_info`).

---

## 4. Registry

```python
from document_intelligence.extractors import (
    register_extractor, get_extractor, list_extractors,
    get_extractor_for_family, instantiate,
)
```

- `@register_extractor()` → registra la clase usando sus atributos `id` y
  `supported_families` (kwargs opcionales: `id=`, `display_name=`,
  `families=`).
- Diccionario interno `{id → clase}` + índice `{family_id → [extractor_ids]}`.
- `get_extractor_for_family(family_id)` devuelve el **primer** extractor
  registrado para la familia (orden de registro da precedencia).
- Registrar dos veces la misma clase es idempotente.

---

## 5. Fallback (garantías de reversibilidad)

- `UniversalExtractor` es el **extractor por defecto y el fallback
  obligatorio**.
- `SpecializedExtractorFactory` nunca lanza; cualquier fallo → universal.
- `ParserPDF.parsear()` envuelve la anotación en try/except: si la factory
  falla, `extractor_info` queda `None` y la salida es idéntica.
- Todos los extractores delegan hoy al universal (`fallback_used=True`);
  revertir el sprint = eliminar `_anotar_extractor` y el campo
  `extractor_info` (nada más depende de ello).

---

## 6. Cómo agregar un extractor nuevo

1. Crear la clase en `document_intelligence/extractors/specialized.py`
   (o en un módulo nuevo dentro del paquete):

   ```python
   @register_extractor()
   class MiEmpresaExtractor(SpecializedExtractor):
       id = "miempresa"
       display_name = "Mi Empresa"
       supported_families = ["cluster_ab12cd34ef"]

       def extract(self, path, context=None) -> ExtractorResult:
           return self.delegate_to_universal(path, context)
   ```

2. Si se creó un módulo nuevo, importarlo desde `extractors/__init__.py`
   (necesario para que el decorator se ejecute al importar el paquete).
3. Listo: el factory lo seleccionará automáticamente cuando detecte la
   familia registrada. (El scaffold delega al universal hasta que se
   implemente su lógica.)

> En el Sprint siguiente, `extract()` reemplazará
> `delegate_to_universal(...)` por la lógica específica y ajustará
> `fallback_used=False` cuando la use.

---

## 7. Cómo registrar una nueva familia

1. La familia ya debe existir en `knowledge_base/document_mining.json`
   (se genera con `python -m tools.run_document_mining`).
2. Asociar la familia al extractor: añadir el id de la familia a
   `supported_families` del extractor correspondiente (o crearlo nuevo,
   ver sección 6).
3. Opcional: subir el umbral por extractor pasándolo a la factory
   (`SpecializedExtractorFactory(threshold=75.0)`) si se quiere ser más
   exigente.

> **Familia DESCONOCIDA / sin extractor**: la factory nunca registra
> familias sin extractor; la búsqueda es por centroide y cualquier familia
> sin extractor registrado cae en el universal.

---

## 8. Implementar la lógica específica (Sprint siguiente)

En el Sprint siguiente, cada extractor implementará su `extract()` real:

1. Usar la familia (por `context.signature` + `family_id` detectado) para
   aplicar reglas específicas de la empresa (p. ej. columnas propias de
   Nogales: códigos COMPACTO, layout VERTICAL, columnas específicas).
2. Todo debe pasar SIEMPRE por `ParserPDF.parsear()` como base (el
   universal sigue siendo el piso; la especialización lo afina, no lo
   reemplaza por completo).
3. Marcar `fallback_used=False` solo cuando el extractor procesó el
   documento con su lógica; en cualquier incertidumbre, delegar con
   `delegate_to_universal(...)` (fallback).
4. Añadir métricas (tiempo, nº de cuentas, flag de fallback, familia
   detectada, confianza) — la estructura ya está en `ExtractorResult`.

---

## 9. Impacto en el comportamiento

| Qué | Antes | Después |
|-----|-------|---------|
| Extracción de cuentas | ParserPDF | ParserPDF (idéntico) |
| `ResultadoParseo.cuentas` | igual | **igual** (mismo orden, nombre, monto, código, tipo) |
| Parser seleccionado | implícito | anotado en `resultado.extractor_info` |
| Excepciones | las mismas | ninguna nueva (todo con fallback) |
| Módulos tocados | — | `document_intelligence/extractors/*` (nuevo), `parser_universal.py` (campo + anotación), `__init__.py` (exports) |
