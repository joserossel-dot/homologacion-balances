# Classification Gap Report — Análisis de Cuentas No Clasificadas

## Resumen Ejecutivo

Se analizaron **5,992 cuentas distintas** no clasificadas (de 8,720 registros totales).

| Métrica | Valor |
|---------|-------|
| Total registros sin clasificar | 8,720 |
| Cuentas distintas sin clasificar | 5,992 |
| Cuentas válidas (no son ruido) | 5,476 |
| Cuentas inválidas (parser/OCR) | 516 |
| Monto total no clasificado | $2,293,171,865,200 |
| Entradas en diccionario actual | 826 |
| Códigos estándar disponibles | 49 |

## 1. ¿Cuántas cuentas distintas siguen sin clasificar?

**5,992 cuentas distintas** están sin clasificar.

De ellas, **5,476 (91.4%)** son cuentas válidas que debieran clasificarse.
Las restantes **516 (8.6%)** son artefactos del parser o ruido de OCR.

## 2. Top 100 cuentas más frecuentes (válidas)

Las 100 cuentas válidas más frecuentes representan **953 ocurrencias** (10.9% del total de registros).

| # | Cuenta | Frecuencia | Empresas | Monto total |
|---|--------|-----------|----------|-------------|
| 1 | Capital emitido | 22 | 0 | $14,262,084 |
| 2 | Ingresos de actividades ordinarias | 20 | 0 | $23,415,074 |
| 3 | Cuentas por pagar a entidades relacionadas, corrientes | 19 | 0 | $10,698,277 |
| 4 | CAJA | 18 | 0 | $38,931,370,512 |
| 5 | Activos por impuestos corrientes | 18 | 0 | $974,204 |
| 6 | Otros activos no financieros, corrientes | 17 | 0 | $520,092 |
| 7 | Acumulado hasta diciembre | 16 | 0 | $32,280 |
| 8 | Ganancias acumuladas | 16 | 0 | $7,404,350 |
| 9 | Deudores comerciales y otras cuentas por cobrar | 16 | 0 | $42,176,929 |
| 10 | Cuentas comerciales y otras cuentas por pagar | 15 | 0 | $3,525,918 |
| 11 | Propiedades, plantas y equipos, neto | 15 | 0 | $23,714,844 |
| 12 | Efectivo y equivalentes al efectivo | 15 | 0 | $249,568 |
| 13 | Servicio de Seguridad | 15 | 0 | $14,984,396 |
| 14 | MONTEVIDEO | 14 | 0 | $30,016 |
| 15 | Otros pasivos financieros, no corrientes | 14 | 0 | $7,652,255 |
| 16 | Gastos de Viaje y Representación | 14 | 0 | $44,826,961 |
| 17 | Rengo | 14 | 0 | $4,732 |
| 18 | Ganancia bruta | 14 | 0 | $9,723,831 |
| 19 | Materiales de Aseo | 13 | 0 | $13,406,298 |
| 20 | Patente Comercial y Vehículos | 13 | 0 | $11,582,562 |
| 21 | Otros pasivos financieros, corrientes | 13 | 0 | $7,523,331 |
| 22 | BANCO CORPBANCA | 13 | 0 | $4,580,919,920 |
| 23 | Nivel | 13 | 0 | $65 |
| 24 | Desde Enero a Diciembre | 13 | 0 | $26,216 |
| 25 | Electricidad | 12 | 0 | $326,439,200 |
| 26 | Agua | 12 | 0 | $8,792,011 |
| 27 | Fletes | 12 | 0 | $296,726,403 |
| 28 | Materiales de Computacion | 12 | 0 | $6,780,456 |
| 29 | Corte a: | 12 | 0 | $24,233 |
| 30 | A NIVEL | 12 | 0 | $45 |

[Las 100 cuentas completas están en top_accounts.xlsx]

## 3. Match contra diccionario

| Tipo de match | Cuentas | % del total | Interpretación |
|--------------|---------|------------|----------------|
| NEW_ACCOUNT | 4998 | 83.4% | Cuentas válidas no presentes en el diccionario |
| OCR_NOISE | 466 | 7.8% | Ruido de OCR (montos embebidos, caracteres extraños) |
| ABBREVIATION | 394 | 6.6% | Contienen abreviaturas expandibles |
| FUZZY_MATCH | 89 | 1.5% | Coinciden con fuzzy matching (≥88% similitud) |
| PARSER_ARTIFACT | 43 | 0.7% | Artefactos del parser (fechas, encabezados) |
| NORMALIZED_MATCH | 2 | 0.0% | Coinciden al normalizar mayúsculas/tildes |

## 4. Análisis detallado por categoría

### 4.1 Normalización (91 cuentas, 1.5%)

- **NORMALIZED_MATCH**: 2 cuentas — solo requieren quitar tildes y mayúsculas
- **FUZZY_MATCH**: 89 cuentas — requieren fuzzy matching (>88%)
- **Total recuperable**: 91 cuentas

Estas cuentas ya existen en el diccionario pero con diferencias menores (tildes, espacios, puntuación).

### 4.2 Sinónimos (934 cuentas, 15.6%)

Se detectaron **376 grupos de sinónimos** con un total de **934 cuentas** involucradas.

Principales grupos:
- Grupo 100 (frecuencia 34): "Otros pasivos financieros, corrientes" → Otros pasivos financieros corrientes | Otros pasivos financieros no corrientes |
- Grupo 11 (frecuencia 26): "CAJA" → Caja
- Grupo 296 (frecuencia 25): "Nivel" → A NIVEL
- Grupo 30 (frecuencia 25): "(=) MARGEN DE LA EXPLOTACION" → Margen de Explotación | Margen de explotación | (E) MARGEN DE LA EXPLOTACION | M
- Grupo 181 (frecuencia 25): "Capital emitido" → Capital Emitido
- Grupo 99 (frecuencia 24): "Otros activos no financieros, corrientes" → Otros activos financieros no corrientes | Otros activos no financieros, no corri
- Grupo 171 (frecuencia 23): "Activos por impuestos corrientes" → Activos por impuestos, corrientes | Activos por Impuestos Corrientes
- Grupo 167 (frecuencia 23): "Deudores comerciales y otras cuentas por cobrar" → Deudores comerciales y otras cuentas por cobrar corrientes | Deudores comerciale
- Grupo 173 (frecuencia 22): "Cuentas comerciales y otras cuentas por pagar" → Cuentas por pagar comerciales y otras cuentas por pagar | Cuentas comerciales y 
- Grupo 240 (frecuencia 22): "Acumulado hasta diciembre" → Acumulado hasta Diciembre

### 4.3 Abreviaturas (394 cuentas, 6.6%)

Se detectaron **25 abreviaturas distintas** en **394 cuentas**.

| Abreviatura | Expansión sugerida | Frecuencia | Cuentas | Confianza |
|------------|-------------------|-----------|---------|-----------|
| cta | cuenta | 211 | 144 | alta |
| dep | depósito | 78 | 49 | alta |
| mat | materiales | 45 | 37 | alta |
| rev | revisión | 39 | 25 | alta |
| inv | inventario | 37 | 26 | alta |
| soc | sociedad | 36 | 29 | alta |
| ctas | cuentas | 29 | 22 | alta |
| vta | venta | 15 | 8 | alta |
| fdo | fondo | 13 | 13 | alta |
| adm | administración | 12 | 9 | alta |
| dif | diferencia | 11 | 10 | alta |
| prov | provisión | 11 | 11 | alta |
| rem | remuneración | 10 | 10 | alta |
| util | utilidad | 6 | 6 | alta |
| eq | equipo | 6 | 5 | alta |

### 4.4 Nuevas entradas en diccionario (4998 cuentas, 83.4%)

**4998 cuentas** válidas no existen en el diccionario.
Representan **91.3%** de las cuentas válidas sin clasificar.

Estas cuentas requieren:
1. Revisión manual para determinar su código estándar
2. Inserción en el diccionario
3. Re-ejecución del pipeline

### 4.5 Patrones detectables (1295 cuentas, 21.6%)

| Patrón | Frecuencia | Cuentas |
|--------|-----------|---------|
| Gastos * | 486 | 345 |
| Cuentas * | 227 | 119 |
| Banco * | 225 | 145 |
| Venta * | 133 | 90 |
| Capital * | 118 | 74 |
| Ingresos * | 98 | 50 |
| Caja * | 86 | 48 |
| Impuesto * | 67 | 46 |
| Activo * | 58 | 43 |
| Servicio * | 55 | 18 |
| Clientes * | 55 | 43 |
| Arriendo * | 54 | 40 |
| Anticipo * | 47 | 39 |
| IVA * | 46 | 26 |
| Provision * | 42 | 35 |

### 4.6 Problemas del parser (43 cuentas, 0.7%)

**43 cuentas** identificadas como artefactos del parser:
- Fechas ("Al 31 de Diciembre de", "Enero a Diciembre")
- Encabezados de página ("Comuna : Bulnes PAGINA :")
- Nombres de empresa ("Rengo", "MONTEVIDEO")
- Títulos de sección

Estas cuentas NO deben clasificarse; deben filtrarse en el parser.

### 4.7 Problemas de OCR (466 cuentas, 7.8%)

**466 cuentas** con probable ruido de OCR:
- Montos numéricos embebidos en el nombre de cuenta
- Caracteres extraños (|, _, /, corchetes)
- Texto irreconocible

Ejemplos:
- "oz [PontalEfacivo | sb60s857O"
- "— | [23 frobicerrasvo "| ress2g0543 zo Fsstanafinal"
- "[o Portestueintarea——" [GORPRANCAÍSOS Pesatodo guasón Iplo a]"
- "717857|699 [fevos ques dañe agora RU gin TRA"
- "[as [resatinaro anio (o Paro vio) | 7o9goneloas Fania Pro rouaro Peso]"
- "ao [fencecimo Polea poco incas"
- "pao [ooo rosso 0) / Mora celo AFP | 17o54azolazo Percesación Pinedo arado"
- "A E"
- "A _ — — á+>=>=+=—=2211 aa ed DOOM ANP FOdio"
- "] DOCUMENTOS"

Ejemplos de artefactos del parser:
- "Enero a Diciembre"
- "Dela Página Anterior"
- ": De la Página Anterior"
- "Dela Página Anterior —"
- "De la Página Anterior —"
- "o Total Página"
- "l De la Página Anterior"
- "AL 31 DE DICIEMBRE"
- "AL 31 DE DICIEMBRE DE"
- "Al 31 de Diciembre de"

## 5. Estimación de impacto

| Prioridad | Acción | Cuentas | % cobertura | Esfuerzo | Retorno esperado |
|-----------|--------|---------|------------|----------|-----------------|
| 1 (Alta) | Normalización (fuzzy + normalized) | 91 | 1.5% | Bajo | Alto — implementación simple, impacto inmediato |
| 1 (Alta) | Sinónimos | 934 | 15.6% | Bajo | Medio — mejora consistencia |
| 2 (Media) | Abreviaturas | 394 | 6.6% | Medio | Medio — expandir antes de matching |
| 2 (Media) | Reglas (patrones) | 1295 | 21.6% | Medio | Medio — cubre familias completas |
| 3 (Baja) | Nuevas entradas diccionario | 4998 | 83.4% | Alto | Alto pero requiere revisión manual |
| — | Filtrar artefactos parser | 43 | 0.7% | Bajo | Mejora métricas, no cobertura |
| — | Limpiar ruido OCR | 466 | 7.8% | Alto | Depende del origen |

## 6. Respuestas a preguntas clave

### ¿Por qué las cuentas no se clasifican?

| Causa raíz | % de cuentas afectadas |
|-----------|----------------------|
| No existen en el diccionario | 83.4% |
| Ruido de OCR | 7.8% |
| Abreviaturas no expandidas | 6.6% |
| Diferencias menores (normalización) | 1.5% |
| Artefactos del parser | 0.7% |

### ¿Qué porcentaje puede resolverse con normalización?

**1.7%** de las cuentas válidas (91 cuentas).

### ¿Qué porcentaje puede resolverse con sinónimos?

**17.1%** de las cuentas válidas (934 cuentas).

### ¿Qué porcentaje requiere ampliar el diccionario?

**91.3%** de las cuentas válidas (4998 cuentas) — es la causa principal.

### ¿Qué porcentaje corresponde a problemas del parser?

**0.7%** del total (43 cuentas).

### ¿Qué porcentaje corresponde a OCR?

**7.8%** del total (466 cuentas).

## 7. Recomendaciones priorizadas

### Sprint 1 (Alta prioridad — máximo retorno con mínimo esfuerzo)

1. **Implementar normalización de texto en el pipeline de matching**:
   - Quitar tildes antes de comparar contra el diccionario
   - Ignorar mayúsculas/minúsculas
   - Eliminar puntuación y espacios múltiples
   - Impacto estimado: **+2 cuentas clasificadas**

2. **Agregar fuzzy matching con threshold ≥88%**:
   - Capturar variantes ortográficas menores
   - Impacto estimado: **+89 cuentas clasificadas**

### Sprint 2 (Prioridad media)

3. **Expandir abreviaturas antes del matching**:
   - Crear tabla de expansión (25 abreviaturas identificadas)
   - Impacto estimado: **+394 cuentas clasificadas**

4. **Crear reglas por patrón**:
   - 30 patrones identificados (Gastos *, Banco *, etc.)
   - Impacto estimado: **+1295 cuentas clasificadas**

### Sprint 3 (Prioridad baja — esfuerzo alto)

5. **Ampliar el diccionario con 4998 nuevas entradas**:
   - Requiere revisión manual de cada cuenta
   - Es la acción de mayor impacto individual (91.3% de cuentas válidas)

6. **Filtrar artefactos del parser**:
   - Ignorar fechas, encabezados, nombres de empresa
   - 43 cuentas dejarían de aparecer como "no clasificadas"

### Acción con mayor retorno esperado

**Normalización + Fuzzy matching**: implementación simple (días), sin revisión manual, recupera **91 cuentas (1.5%)**.

## 8. Conclusión

La causa principal de cuentas no clasificadas es la **ausencia en el diccionario** (83.4%).
Sin embargo, la acción con **mayor retorno inmediato** es la **normalización de texto** (bajo esfuerzo, impacto del 1.5%).

Combinando normalización + sinónimos + abreviaturas + reglas se podría recuperar hasta **~2714 cuentas** (45.3% del total), sin modificar el diccionario.

Para superar el **91.3%** restante de cuentas válidas, se requiere ampliar el diccionario con revisión manual.
