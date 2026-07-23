# Propuestas de Mejora — Knowledge Generator

Generado: 2026-07-07 16:09:49 UTC

## Resumen

| Métrica | Valor |
|---|---|
| Propuestas de reglas | 533 |
| Entradas de diccionario | 2598 |
| Entradas Gold Standard | 185 |
| Líneas de tests generados | 29622 |
| Líneas de código de reglas | 1073 |

## Reglas Semánticas Propuestas

### 1. `suelo_preparacion`
- **Tipo**: revenue
- **Keywords**: suelo, preparacion, camellones
- **Prioridad sugerida**: 60
- **Confianza**: 0.4
- **Cuentas afectadas**: ~192
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="suelo_preparacion",
        priority=60,
        required_keywords=[['sueló', 'súelo', 'suélo', 'suelos', 'suelo'], ['préparacion', 'preparacion', 'preparacions', 'prepárácion', 'preparación', 'preparacíon'], ['camellone', 'cámellones', 'camellones', 'caméllonés', 'camellónes']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: suelo, preparacion, camellones",
    ),
```

### 2. `administracion_gastos`
- **Tipo**: revenue
- **Keywords**: administracion, gastos, generales
- **Prioridad sugerida**: 70
- **Confianza**: 0.4
- **Cuentas afectadas**: ~162
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="administracion_gastos",
        priority=70,
        required_keywords=[['administracion', 'ádministrácion', 'admínístracíon', 'administración', 'administracions'], ['gasto', 'gastos', 'gastós', 'gástos'], ['generales', 'generáles', 'généralés', 'generale']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: administracion, gastos, generales",
    ),
```

### 3. `administracion_sueldos`
- **Tipo**: revenue
- **Keywords**: administracion, sueldos
- **Prioridad sugerida**: 80
- **Confianza**: 0.4
- **Cuentas afectadas**: ~152
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="administracion_sueldos",
        priority=80,
        required_keywords=[['administracion', 'ádministrácion', 'admínístracíon', 'administración', 'administracions'], ['sueldos', 'sueldo', 'sueldós', 'súeldos', 'suéldos']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: administracion, sueldos",
    ),
```

### 4. `habilitacion_proyecto`
- **Tipo**: revenue
- **Keywords**: habilitacion, proyecto, pre
- **Prioridad sugerida**: 90
- **Confianza**: 0.4
- **Cuentas afectadas**: ~130
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="habilitacion_proyecto",
        priority=90,
        required_keywords=[['hábilitácion', 'habilitacion', 'habilitación', 'habilitacions', 'habílítacíon'], ['proyectos', 'proyécto', 'proyecto', 'próyectó'], ['pre', 'pres', 'pré']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: habilitacion, proyecto, pre",
    ),
```

### 5. `equipos_acum`
- **Tipo**: revenue
- **Keywords**: equipos, acum, impulsiones
- **Prioridad sugerida**: 100
- **Confianza**: 0.4
- **Cuentas afectadas**: ~125
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="equipos_acum",
        priority=100,
        required_keywords=[['equipos', 'equipós', 'equipo', 'eqúipos', 'equípos', 'équipos'], ['acums', 'ácum', 'acúm', 'acum'], ['impulsionés', 'impulsiones', 'impulsione', 'ímpulsíones', 'impúlsiones', 'impulsiónes']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: equipos, acum, impulsiones",
    ),
```

### 6. `diciembre_enero`
- **Tipo**: revenue
- **Keywords**: diciembre, enero
- **Prioridad sugerida**: 110
- **Confianza**: 0.4
- **Cuentas afectadas**: ~124
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="diciembre_enero",
        priority=110,
        required_keywords=[['diciembres', 'diciémbré', 'diciembre', 'dícíembre'], ['eneros', 'eneró', 'enero', 'énéro']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: diciembre, enero",
    ),
```

### 7. `corrientes_otros`
- **Tipo**: revenue
- **Keywords**: corrientes, otros, activos, financieros
- **Prioridad sugerida**: 120
- **Confianza**: 0.4
- **Cuentas afectadas**: ~109
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="corrientes_otros",
        priority=120,
        required_keywords=[['corríentes', 'corriente', 'corriéntés', 'corrientes', 'córrientes'], ['ótrós', 'otros', 'otro'], ['actívos', 'áctivos', 'activo', 'activós', 'activos'], ['fináncieros', 'fínancíeros', 'financiéros', 'financiero', 'financieros', 'financierós']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: corrientes, otros, activos, financieros",
    ),
```

### 8. `documentos_pagar`
- **Tipo**: revenue
- **Keywords**: documentos, pagar, cobrar
- **Prioridad sugerida**: 130
- **Confianza**: 0.4
- **Cuentas afectadas**: ~91
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="documentos_pagar",
        priority=130,
        required_keywords=[['dócumentós', 'documentos', 'docúmentos', 'documéntos', 'documento'], ['pagar', 'págár', 'pagars'], ['cóbrar', 'cobrár', 'cobrars', 'cobrar']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: documentos, pagar, cobrar",
    ),
```

### 9. `materiales_oficina`
- **Tipo**: revenue
- **Keywords**: materiales, oficina, aseo, gastos
- **Prioridad sugerida**: 140
- **Confianza**: 0.4
- **Cuentas afectadas**: ~90
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="materiales_oficina",
        priority=140,
        required_keywords=[['materiale', 'máteriáles', 'materíales', 'materiales', 'matérialés'], ['oficina', 'oficinas', 'óficina', 'ofícína', 'oficiná'], ['áseo', 'aséo', 'aseó', 'aseo', 'aseos'], ['gasto', 'gastos', 'gastós', 'gástos']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: materiales, oficina, aseo, gastos",
    ),
```

### 10. `explotacion_margen`
- **Tipo**: revenue
- **Keywords**: explotacion, margen, ingresos
- **Prioridad sugerida**: 150
- **Confianza**: 0.4
- **Cuentas afectadas**: ~65
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="explotacion_margen",
        priority=150,
        required_keywords=[['explotacion', 'explotacions', 'explotacíon', 'explotácion', 'explótación', 'éxplotacion'], ['margén', 'margens', 'margen', 'márgen'], ['ingreso', 'ingrésos', 'ingresos', 'íngresos', 'ingresós']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: explotacion, margen, ingresos",
    ),
```

### 11. `cuentas_comerciales`
- **Tipo**: revenue
- **Keywords**: cuentas, comerciales, otras
- **Prioridad sugerida**: 160
- **Confianza**: 0.4
- **Cuentas afectadas**: ~65
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="cuentas_comerciales",
        priority=160,
        required_keywords=[['cuentás', 'cuenta', 'cuéntas', 'cuentas', 'cúentas'], ['comércialés', 'comerciales', 'comercíales', 'comerciáles', 'comerciale', 'cómerciales'], ['otras', 'ótras', 'otra', 'otrás']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: cuentas, comerciales, otras",
    ),
```

### 12. `ganancia_bruta`
- **Tipo**: revenue
- **Keywords**: ganancia, bruta, antes
- **Prioridad sugerida**: 170
- **Confianza**: 0.4
- **Cuentas afectadas**: ~61
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="ganancia_bruta",
        priority=170,
        required_keywords=[['ganancía', 'ganancias', 'gánánciá', 'ganancia'], ['brutas', 'brúta', 'brutá', 'bruta'], ['ante', 'antés', 'antes', 'ántes']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: ganancia, bruta, antes",
    ),
```

### 13. `servicio_correo`
- **Tipo**: revenue
- **Keywords**: servicio, correo, seguridad, productos
- **Prioridad sugerida**: 180
- **Confianza**: 0.4
- **Cuentas afectadas**: ~56
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="servicio_correo",
        priority=180,
        required_keywords=[['servicio', 'servicios', 'servícío', 'servició', 'sérvicio'], ['corréo', 'correo', 'correos', 'córreó'], ['seguridád', 'seguridads', 'séguridad', 'segúridad', 'segurídad', 'seguridad'], ['prodúctos', 'productos', 'producto', 'próductós']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: servicio, correo, seguridad, productos",
    ),
```

### 14. `utilidad_perdida`
- **Tipo**: expense
- **Keywords**: utilidad, perdida, venta
- **Prioridad sugerida**: 190
- **Confianza**: 0.4
- **Cuentas afectadas**: ~55
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="utilidad_perdida",
        priority=190,
        required_keywords=[['utilidads', 'utílídad', 'utilidad', 'utilidád', 'útilidad'], ['perdída', 'perdidá', 'perdida', 'pérdida', 'perdidas'], ['ventas', 'vénta', 'ventá', 'venta']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: utilidad, perdida, venta",
    ),
```

### 15. `cuentas_relacionadas`
- **Tipo**: revenue
- **Keywords**: cuentas, relacionadas, entidades
- **Prioridad sugerida**: 200
- **Confianza**: 0.4
- **Cuentas afectadas**: ~47
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="cuentas_relacionadas",
        priority=200,
        required_keywords=[['cuentás', 'cuenta', 'cuéntas', 'cuentas', 'cúentas'], ['rélacionadas', 'relacíonadas', 'relacionadas', 'relácionádás', 'relacionada', 'relaciónadas'], ['entidade', 'éntidadés', 'entidádes', 'entídades', 'entidades']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: cuentas, relacionadas, entidades",
    ),
```

### 16. `otros_gastos`
- **Tipo**: expense
- **Keywords**: otros, gastos, personal, generales
- **Prioridad sugerida**: 210
- **Confianza**: 0.4
- **Cuentas afectadas**: ~45
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="otros_gastos",
        priority=210,
        required_keywords=[['ótrós', 'otros', 'otro'], ['gasto', 'gastos', 'gastós', 'gástos'], ['pérsonal', 'personal', 'persónal', 'personál', 'personals'], ['generales', 'generáles', 'généralés', 'generale']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: otros, gastos, personal, generales",
    ),
```

### 17. `remuneraciones_total`
- **Tipo**: expense
- **Keywords**: remuneraciones, total, anticipo, pasivo
- **Prioridad sugerida**: 220
- **Confianza**: 0.4
- **Cuentas afectadas**: ~38
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="remuneraciones_total",
        priority=220,
        required_keywords=[['remuneracione', 'rémunéracionés', 'remuneraciones', 'remuneracíones', 'remúneraciones', 'remuneraciónes', 'remuneráciones'], ['tótal', 'totál', 'totals', 'total'], ['antícípo', 'anticipó', 'ánticipo', 'anticipos', 'anticipo'], ['pasivó', 'pasivos', 'pásivo', 'pasívo', 'pasivo']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: remuneraciones, total, anticipo, pasivo",
    ),
```

### 18. `efectivo_equivalentes`
- **Tipo**: revenue
- **Keywords**: efectivo, equivalentes, capital
- **Prioridad sugerida**: 230
- **Confianza**: 0.4
- **Cuentas afectadas**: ~36
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="efectivo_equivalentes",
        priority=230,
        required_keywords=[['efectivos', 'éféctivo', 'efectivo', 'efectivó', 'efectívo'], ['equivalente', 'equiválentes', 'equivalentes', 'équivaléntés', 'eqúivalentes', 'equívalentes'], ['capitals', 'capítal', 'cápitál', 'capital']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: efectivo, equivalentes, capital",
    ),
```

### 19. `nivel_anivel`
- **Tipo**: revenue
- **Keywords**: nivel, anivel
- **Prioridad sugerida**: 240
- **Confianza**: 0.4
- **Cuentas afectadas**: ~34
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="nivel_anivel",
        priority=240,
        required_keywords=[['nivels', 'nível', 'nivél', 'nivel'], ['ánivel', 'anivel', 'anível', 'anivels', 'anivél']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: nivel, anivel",
    ),
```

### 20. `indemnizacion_cta`
- **Tipo**: revenue
- **Keywords**: indemnizacion, cta, pablo
- **Prioridad sugerida**: 250
- **Confianza**: 0.4
- **Cuentas afectadas**: ~33
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="indemnizacion_cta",
        priority=250,
        required_keywords=[['indemnización', 'indemnizacions', 'indémnizacion', 'indemnizacion', 'indemnizácion', 'índemnízacíon'], ['ctá', 'ctas', 'cta'], ['páblo', 'pablo', 'pabló', 'pablos']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: indemnizacion, cta, pablo",
    ),
```

### 21. `moneda_pagina`
- **Tipo**: revenue
- **Keywords**: moneda, pagina, peso, chileno
- **Prioridad sugerida**: 260
- **Confianza**: 0.4
- **Cuentas afectadas**: ~33
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="moneda_pagina",
        priority=260,
        required_keywords=[['monéda', 'monedas', 'moneda', 'móneda', 'monedá'], ['pagina', 'paginas', 'pagína', 'páginá'], ['pesos', 'péso', 'peso', 'pesó'], ['chilenos', 'chiléno', 'chilenó', 'chileno', 'chíleno']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: moneda, pagina, peso, chileno",
    ),
```

### 22. `agua_administracion`
- **Tipo**: revenue
- **Keywords**: agua, administracion, gastos
- **Prioridad sugerida**: 270
- **Confianza**: 0.4
- **Cuentas afectadas**: ~31
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="agua_administracion",
        priority=270,
        required_keywords=[['agúa', 'aguas', 'agua', 'águá'], ['administracion', 'ádministrácion', 'admínístracíon', 'administración', 'administracions'], ['gasto', 'gastos', 'gastós', 'gástos']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: agua, administracion, gastos",
    ),
```

### 23. `pagar_cuentas`
- **Tipo**: revenue
- **Keywords**: pagar, cuentas, empresa, caja
- **Prioridad sugerida**: 280
- **Confianza**: 0.4
- **Cuentas afectadas**: ~29
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="pagar_cuentas",
        priority=280,
        required_keywords=[['pagar', 'págár', 'pagars'], ['cuentás', 'cuenta', 'cuéntas', 'cuentas', 'cúentas'], ['empresa', 'empresas', 'empresá', 'émprésa'], ['cájá', 'cajas', 'caja']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: pagar, cuentas, empresa, caja",
    ),
```

### 24. `capital_emitido`
- **Tipo**: revenue
- **Keywords**: capital, emitido, jose
- **Prioridad sugerida**: 290
- **Confianza**: 0.4
- **Cuentas afectadas**: ~28
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="capital_emitido",
        priority=290,
        required_keywords=[['capitals', 'capítal', 'cápitál', 'capital'], ['emítído', 'emitidó', 'emitidos', 'émitido', 'emitido'], ['jóse', 'jose', 'joses', 'josé']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: capital, emitido, jose",
    ),
```

### 25. `pagina_asesorias`
- **Tipo**: revenue
- **Keywords**: pagina, asesorias, inversiones
- **Prioridad sugerida**: 300
- **Confianza**: 0.4
- **Cuentas afectadas**: ~28
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="pagina_asesorias",
        priority=300,
        required_keywords=[['pagina', 'paginas', 'pagína', 'páginá'], ['asesórias', 'asesoria', 'asesorías', 'asésorias', 'asesorias', 'ásesoriás'], ['inversiones', 'inversiónes', 'ínversíones', 'inversione', 'invérsionés']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: pagina, asesorias, inversiones",
    ),
```

### 26. `ingresos_actividades`
- **Tipo**: revenue
- **Keywords**: ingresos, actividades, ordinarias, buses
- **Prioridad sugerida**: 310
- **Confianza**: 0.4
- **Cuentas afectadas**: ~27
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="ingresos_actividades",
        priority=310,
        required_keywords=[['ingreso', 'ingrésos', 'ingresos', 'íngresos', 'ingresós'], ['actividade', 'áctividádes', 'actividadés', 'actívídades', 'actividades'], ['ordináriás', 'órdinarias', 'ordinaria', 'ordinarias', 'ordínarías'], ['búses', 'buses', 'busés', 'buse']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: ingresos, actividades, ordinarias, buses",
    ),
```

### 27. `diferidos_impuestos`
- **Tipo**: revenue
- **Keywords**: diferidos, impuestos, diferido, impuesto
- **Prioridad sugerida**: 320
- **Confianza**: 0.4
- **Cuentas afectadas**: ~27
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="diferidos_impuestos",
        priority=320,
        required_keywords=[['diferidos', 'díferídos', 'diferidós', 'diferido', 'diféridos'], ['ímpuestos', 'impuestós', 'impuéstos', 'impuesto', 'impuestos', 'impúestos'], ['diferidos', 'diférido', 'diferidó', 'diferido', 'díferído'], ['impuésto', 'impuesto', 'impuestos', 'impuestó', 'impúesto', 'ímpuesto']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: diferidos, impuestos, diferido, impuesto",
    ),
```

### 28. `total_activo`
- **Tipo**: expense
- **Keywords**: total, activo, fijo, patrimonio, neto
- **Prioridad sugerida**: 330
- **Confianza**: 0.4
- **Cuentas afectadas**: ~26
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="total_activo",
        priority=330,
        required_keywords=[['tótal', 'totál', 'totals', 'total'], ['áctivo', 'activó', 'actívo', 'activo', 'activos'], ['fijó', 'fijos', 'fíjo', 'fijo'], ['patrímonío', 'pátrimonio', 'patrimónió', 'patrimonios', 'patrimonio'], ['netó', 'netos', 'néto', 'neto']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: total, activo, fijo, patrimonio, neto",
    ),
```

### 29. `ppm_reajuste`
- **Tipo**: revenue
- **Keywords**: ppm, reajuste, iva, ppmava
- **Prioridad sugerida**: 340
- **Confianza**: 0.4
- **Cuentas afectadas**: ~26
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="ppm_reajuste",
        priority=340,
        required_keywords=[['ppm', 'ppms'], ['reajúste', 'reajuste', 'réajusté', 'reájuste', 'reajustes'], ['ivá', 'íva', 'iva', 'ivas'], ['ppmavas', 'ppmává', 'ppmava']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: ppm, reajuste, iva, ppmava",
    ),
```

### 30. `computacion_equipos`
- **Tipo**: revenue
- **Keywords**: computacion, equipos, colacion, total
- **Prioridad sugerida**: 350
- **Confianza**: 0.4
- **Cuentas afectadas**: ~26
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="computacion_equipos",
        priority=350,
        required_keywords=[['computácion', 'computacions', 'cómputación', 'computacion', 'compútacion', 'computacíon'], ['equipos', 'equipós', 'equipo', 'eqúipos', 'equípos', 'équipos'], ['colácion', 'colacion', 'colacíon', 'colacions', 'cólación'], ['tótal', 'totál', 'totals', 'total']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: computacion, equipos, colacion, total",
    ),
```

### 31. `riego_equipo`
- **Tipo**: revenue
- **Keywords**: riego, equipo, olivos, spa
- **Prioridad sugerida**: 360
- **Confianza**: 0.4
- **Cuentas afectadas**: ~26
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="riego_equipo",
        priority=360,
        required_keywords=[['riégo', 'riego', 'riegos', 'ríego', 'riegó'], ['equipos', 'equipó', 'equípo', 'equipo', 'eqúipo', 'équipo'], ['olivo', 'ólivós', 'olívos', 'olivos'], ['spa', 'spas', 'spá']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: riego, equipo, olivos, spa",
    ),
```

### 32. `comisiones_percibidas`
- **Tipo**: revenue
- **Keywords**: comisiones, percibidas
- **Prioridad sugerida**: 370
- **Confianza**: 0.4
- **Cuentas afectadas**: ~25
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="comisiones_percibidas",
        priority=370,
        required_keywords=[['comisiones', 'comísíones', 'comisionés', 'cómisiónes', 'comisione'], ['percibidas', 'percíbídas', 'pércibidas', 'percibida', 'percibidás']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: comisiones, percibidas",
    ),
```

### 33. `folio_dias`
- **Tipo**: revenue
- **Keywords**: folio, dias, 2014
- **Prioridad sugerida**: 380
- **Confianza**: 0.4
- **Cuentas afectadas**: ~25
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="folio_dias",
        priority=380,
        required_keywords=[['fólió', 'folio', 'folío', 'folios'], ['días', 'dia', 'diás', 'dias'], ['2014s', '2014']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: folio, dias, 2014",
    ),
```

### 34. `rengo_338`
- **Tipo**: revenue
- **Keywords**: rengo, 338, piso
- **Prioridad sugerida**: 390
- **Confianza**: 0.4
- **Cuentas afectadas**: ~24
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="rengo_338",
        priority=390,
        required_keywords=[['rengos', 'rengó', 'réngo', 'rengo'], ['338s', '338'], ['piso', 'pisos', 'pisó', 'píso']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: rengo, 338, piso",
    ),
```

### 35. `imprenta_gastos`
- **Tipo**: revenue
- **Keywords**: imprenta, gastos, reproduccion
- **Prioridad sugerida**: 400
- **Confianza**: 0.4
- **Cuentas afectadas**: ~24
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="imprenta_gastos",
        priority=400,
        required_keywords=[['ímprenta', 'imprénta', 'imprenta', 'imprentá', 'imprentas'], ['gasto', 'gastos', 'gastós', 'gástos'], ['reproduccíon', 'reproduccion', 'repróducción', 'reproduccions', 'reprodúccion', 'réproduccion']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: imprenta, gastos, reproduccion",
    ),
```

### 36. `obligaciones_bancos`
- **Tipo**: expense
- **Keywords**: obligaciones, bancos, financieras
- **Prioridad sugerida**: 410
- **Confianza**: 0.4
- **Cuentas afectadas**: ~24
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="obligaciones_bancos",
        priority=410,
        required_keywords=[['obligaciones', 'oblígacíones', 'obligacione', 'obligacionés', 'obligáciones', 'óbligaciónes'], ['banco', 'bancós', 'báncos', 'bancos'], ['fínancíeras', 'financieras', 'financiéras', 'fináncierás', 'financiera']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: obligaciones, bancos, financieras",
    ),
```

### 37. `tributario_republica`
- **Tipo**: revenue
- **Keywords**: tributario, republica
- **Prioridad sugerida**: 420
- **Confianza**: 0.4
- **Cuentas afectadas**: ~23
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="tributario_republica",
        priority=420,
        required_keywords=[['tributário', 'tríbutarío', 'tribútario', 'tributario', 'tributarios', 'tributarió'], ['republica', 'república', 'republíca', 'republicá', 'républica', 'republicas']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: tributario, republica",
    ),
```

### 38. `intereses_multas`
- **Tipo**: revenue
- **Keywords**: intereses, multas, mas
- **Prioridad sugerida**: 430
- **Confianza**: 0.4
- **Cuentas afectadas**: ~23
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="intereses_multas",
        priority=430,
        required_keywords=[['íntereses', 'intérésés', 'intereses', 'interese'], ['multas', 'multa', 'multás', 'múltas'], ['ma', 'más', 'mas']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: intereses, multas, mas",
    ),
```

### 39. `corte_soporte`
- **Tipo**: revenue
- **Keywords**: corte, soporte, gastos
- **Prioridad sugerida**: 440
- **Confianza**: 0.4
- **Cuentas afectadas**: ~23
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="corte_soporte",
        priority=440,
        required_keywords=[['cortes', 'córte', 'corte', 'corté'], ['soporté', 'soportes', 'soporte', 'sópórte'], ['gasto', 'gastos', 'gastós', 'gástos']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: corte, soporte, gastos",
    ),
```

### 40. `vehiculos_comercial`
- **Tipo**: revenue
- **Keywords**: vehiculos, comercial, patente, gastos
- **Prioridad sugerida**: 450
- **Confianza**: 0.4
- **Cuentas afectadas**: ~22
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="vehiculos_comercial",
        priority=450,
        required_keywords=[['vehiculos', 'vehiculo', 'véhiculos', 'vehiculós', 'vehículos', 'vehicúlos'], ['comerciál', 'comercíal', 'comercial', 'comercials', 'cómercial', 'comércial'], ['patentes', 'pátente', 'paténté', 'patente'], ['gasto', 'gastos', 'gastós', 'gástos']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: vehiculos, comercial, patente, gastos",
    ),
```

### 41. `comunicaciones_bonificaciones`
- **Tipo**: revenue
- **Keywords**: comunicaciones, bonificaciones, telefonos
- **Prioridad sugerida**: 460
- **Confianza**: 0.4
- **Cuentas afectadas**: ~22
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="comunicaciones_bonificaciones",
        priority=460,
        required_keywords=[['comunícacíones', 'comunicacionés', 'comúnicaciones', 'cómunicaciónes', 'comunicaciones', 'comunicáciones', 'comunicacione'], ['bonífícacíones', 'bonificacionés', 'bónificaciónes', 'bonificaciones', 'bonificacione', 'bonificáciones'], ['telefono', 'téléfonos', 'telefonos', 'telefónós']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: comunicaciones, bonificaciones, telefonos",
    ),
```

### 42. `credito_linea`
- **Tipo**: revenue
- **Keywords**: credito, linea, cta, especial
- **Prioridad sugerida**: 470
- **Confianza**: 0.4
- **Cuentas afectadas**: ~22
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="credito_linea",
        priority=470,
        required_keywords=[['crédito', 'creditó', 'credito', 'creditos', 'credíto'], ['lineas', 'linéa', 'línea', 'lineá', 'linea'], ['ctá', 'ctas', 'cta'], ['especíal', 'especiál', 'especials', 'especial', 'éspécial']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: credito, linea, cta, especial",
    ),
```

### 43. `octubre_consumo`
- **Tipo**: revenue
- **Keywords**: octubre, consumo
- **Prioridad sugerida**: 480
- **Confianza**: 0.4
- **Cuentas afectadas**: ~22
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="octubre_consumo",
        priority=480,
        required_keywords=[['óctubre', 'octubres', 'octúbre', 'octubré', 'octubre'], ['consúmo', 'consumos', 'consumo', 'cónsumó']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: octubre, consumo",
    ),
```

### 44. `plantacion_personal`
- **Tipo**: expense
- **Keywords**: plantacion, personal, manuel, torres, eirl
- **Prioridad sugerida**: 490
- **Confianza**: 0.4
- **Cuentas afectadas**: ~22
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="plantacion_personal",
        priority=490,
        required_keywords=[['plantacíon', 'plantacion', 'plantacions', 'plántácion', 'plantación'], ['pérsonal', 'personal', 'persónal', 'personál', 'personals'], ['manúel', 'manuels', 'mánuel', 'manuel', 'manuél'], ['torre', 'torres', 'tórres', 'torrés'], ['eirls', 'eírl', 'éirl', 'eirl']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: plantacion, personal, manuel, torres, eirl",
    ),
```

### 45. `plantacion_contratista`
- **Tipo**: revenue
- **Keywords**: plantacion, contratista, angelica, vasquez, cabezas
- **Prioridad sugerida**: 500
- **Confianza**: 0.4
- **Cuentas afectadas**: ~22
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="plantacion_contratista",
        priority=500,
        required_keywords=[['plantacíon', 'plantacion', 'plantacions', 'plántácion', 'plantación'], ['contratistas', 'contrátistá', 'contratista', 'contratísta', 'cóntratista'], ['ángelicá', 'angelíca', 'angélica', 'angelica', 'angelicas'], ['vasquez', 'vásquez', 'vasqúez', 'vasquéz', 'vasquezs'], ['cabeza', 'cábezás', 'cabezas', 'cabézas']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: plantacion, contratista, angelica, vasquez, cabezas",
    ),
```

### 46. `obras_ejecucion`
- **Tipo**: expense
- **Keywords**: obras, ejecucion, arica, antofagasta
- **Prioridad sugerida**: 510
- **Confianza**: 0.4
- **Cuentas afectadas**: ~22
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="obras_ejecucion",
        priority=510,
        required_keywords=[['óbras', 'obrás', 'obra', 'obras'], ['ejecucíon', 'ejecúcion', 'ejecucion', 'ejecucions', 'ejecución', 'éjécucion'], ['áricá', 'aríca', 'arica', 'aricas'], ['antofagastas', 'ántofágástá', 'antófagasta', 'antofagasta']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: obras, ejecucion, arica, antofagasta",
    ),
```

### 47. `disponible_bancos`
- **Tipo**: expense
- **Keywords**: disponible, bancos, 463, instituciones
- **Prioridad sugerida**: 520
- **Confianza**: 0.4
- **Cuentas afectadas**: ~20
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="disponible_bancos",
        priority=520,
        required_keywords=[['dispónible', 'disponible', 'disponibles', 'disponiblé', 'dísponíble'], ['banco', 'bancós', 'báncos', 'bancos'], ['463', '463s'], ['instituciones', 'institucione', 'institúciones', 'institucionés', 'ínstítucíones', 'instituciónes']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: disponible, bancos, 463, instituciones",
    ),
```

### 48. `amortizacion_depreciacion`
- **Tipo**: expense
- **Keywords**: amortizacion, depreciacion, costo, acumulada
- **Prioridad sugerida**: 530
- **Confianza**: 0.4
- **Cuentas afectadas**: ~20
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="amortizacion_depreciacion",
        priority=530,
        required_keywords=[['amortizacion', 'amortízacíon', 'amórtización', 'amortizacions', 'ámortizácion'], ['dépréciacion', 'deprecíacíon', 'depreciacions', 'depreciácion', 'depreciacion', 'depreciación'], ['cóstó', 'costo', 'costos'], ['acumuladas', 'acumulada', 'acúmúlada', 'ácumuládá']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: amortizacion, depreciacion, costo, acumulada",
    ),
```

### 49. `impuesto_saldo`
- **Tipo**: revenue
- **Keywords**: impuesto, saldo, favor
- **Prioridad sugerida**: 540
- **Confianza**: 0.4
- **Cuentas afectadas**: ~19
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="impuesto_saldo",
        priority=540,
        required_keywords=[['impuésto', 'impuesto', 'impuestos', 'impuestó', 'impúesto', 'ímpuesto'], ['saldos', 'sáldo', 'saldó', 'saldo'], ['favór', 'fávor', 'favor', 'favors']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: impuesto, saldo, favor",
    ),
```

### 50. `perdidas_ganancias`
- **Tipo**: expense
- **Keywords**: perdidas, ganancias, acumuladas, ganancia
- **Prioridad sugerida**: 550
- **Confianza**: 0.4
- **Cuentas afectadas**: ~19
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="perdidas_ganancias",
        priority=550,
        required_keywords=[['perdídas', 'perdidás', 'pérdidas', 'perdida', 'perdidas'], ['gánánciás', 'ganancías', 'ganancias', 'ganancia'], ['acumuladas', 'acumulada', 'acúmúladas', 'ácumuládás'], ['ganancía', 'ganancias', 'gánánciá', 'ganancia']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: perdidas, ganancias, acumuladas, ganancia",
    ),
```

### 51. `movilizacion_sueldos`
- **Tipo**: revenue
- **Keywords**: movilizacion, sueldos, acentralizacion
- **Prioridad sugerida**: 560
- **Confianza**: 0.4
- **Cuentas afectadas**: ~19
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="movilizacion_sueldos",
        priority=560,
        required_keywords=[['movílízacíon', 'movilizacion', 'móvilización', 'movilizacions', 'movilizácion'], ['sueldos', 'sueldo', 'sueldós', 'súeldos', 'suéldos'], ['acentralización', 'ácentrálizácion', 'acéntralizacion', 'acentralízacíon', 'acentralizacion', 'acentralizacions']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: movilizacion, sueldos, acentralizacion",
    ),
```

### 52. `inventarios_corrientes`
- **Tipo**: revenue
- **Keywords**: inventarios, corrientes, inversiones, provisiones
- **Prioridad sugerida**: 570
- **Confianza**: 0.4
- **Cuentas afectadas**: ~19
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="inventarios_corrientes",
        priority=570,
        required_keywords=[['invéntarios', 'ínventaríos', 'inventario', 'inventarios', 'inventários', 'inventariós'], ['corríentes', 'corriente', 'corriéntés', 'corrientes', 'córrientes'], ['inversiones', 'inversiónes', 'ínversíones', 'inversione', 'invérsionés'], ['provisiones', 'provisione', 'provisionés', 'próvisiónes', 'provísíones']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: inventarios, corrientes, inversiones, provisiones",
    ),
```

### 53. `pasivos_corrientes`
- **Tipo**: expense
- **Keywords**: pasivos, corrientes, impuestos, arrendamiento
- **Prioridad sugerida**: 580
- **Confianza**: 0.4
- **Cuentas afectadas**: ~19
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="pasivos_corrientes",
        priority=580,
        required_keywords=[['pasivos', 'pasivós', 'pásivos', 'pasívos', 'pasivo'], ['corríentes', 'corriente', 'corriéntés', 'corrientes', 'córrientes'], ['ímpuestos', 'impuestós', 'impuéstos', 'impuesto', 'impuestos', 'impúestos'], ['arréndamiénto', 'árrendámiento', 'arrendamientos', 'arrendamíento', 'arrendamientó', 'arrendamiento']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: pasivos, corrientes, impuestos, arrendamiento",
    ),
```

### 54. `muebles_utiles`
- **Tipo**: revenue
- **Keywords**: muebles, utiles, 12351
- **Prioridad sugerida**: 590
- **Confianza**: 0.4
- **Cuentas afectadas**: ~19
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="muebles_utiles",
        priority=590,
        required_keywords=[['muéblés', 'muebles', 'mueble', 'múebles'], ['utíles', 'utile', 'utiles', 'útiles', 'utilés'], ['12351s', '12351']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: muebles, utiles, 12351",
    ),
```

### 55. `plantacion_fertilizante`
- **Tipo**: revenue
- **Keywords**: plantacion, fertilizante
- **Prioridad sugerida**: 600
- **Confianza**: 0.4
- **Cuentas afectadas**: ~19
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="plantacion_fertilizante",
        priority=600,
        required_keywords=[['plantacíon', 'plantacion', 'plantacions', 'plántácion', 'plantación'], ['fertilizante', 'fertílízante', 'fertilizánte', 'fértilizanté', 'fertilizantes']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: plantacion, fertilizante",
    ),
```

### 56. `electricidad_gastos`
- **Tipo**: revenue
- **Keywords**: electricidad, gastos, 1353750
- **Prioridad sugerida**: 610
- **Confianza**: 0.4
- **Cuentas afectadas**: ~18
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="electricidad_gastos",
        priority=610,
        required_keywords=[['electricidad', 'electricidads', 'electricidád', 'electrícídad', 'éléctricidad'], ['gasto', 'gastos', 'gastós', 'gástos'], ['1353750', '1353750s']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: electricidad, gastos, 1353750",
    ),
```

### 57. `fletes_fletespruta`
- **Tipo**: revenue
- **Keywords**: fletes, fletespruta
- **Prioridad sugerida**: 620
- **Confianza**: 0.4
- **Cuentas afectadas**: ~18
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="fletes_fletespruta",
        priority=620,
        required_keywords=[['fletes', 'flete', 'flétés'], ['fletesprúta', 'flétéspruta', 'fletespruta', 'fletesprutá', 'fletesprutas']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: fletes, fletespruta",
    ),
```

### 58. `comuna_bulnes`
- **Tipo**: revenue
- **Keywords**: comuna, bulnes, pagina
- **Prioridad sugerida**: 630
- **Confianza**: 0.4
- **Cuentas afectadas**: ~18
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="comuna_bulnes",
        priority=630,
        required_keywords=[['comúna', 'comuna', 'cómuna', 'comunas', 'comuná'], ['búlnes', 'bulnes', 'bulnés', 'bulne'], ['pagina', 'paginas', 'pagína', 'páginá']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: comuna, bulnes, pagina",
    ),
```

### 59. `pagar_total`
- **Tipo**: revenue
- **Keywords**: pagar, total, lineas, disposicion
- **Prioridad sugerida**: 640
- **Confianza**: 0.4
- **Cuentas afectadas**: ~17
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="pagar_total",
        priority=640,
        required_keywords=[['pagar', 'págár', 'pagars'], ['tótal', 'totál', 'totals', 'total'], ['lineás', 'lineas', 'líneas', 'linéas', 'linea'], ['dispósición', 'disposicion', 'disposicions', 'dísposícíon']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: pagar, total, lineas, disposicion",
    ),
```

### 60. `acumuladas_ganancias`
- **Tipo**: revenue
- **Keywords**: acumuladas, ganancias, perdida, ganacias
- **Prioridad sugerida**: 650
- **Confianza**: 0.4
- **Cuentas afectadas**: ~17
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="acumuladas_ganancias",
        priority=650,
        required_keywords=[['acumuladas', 'acumulada', 'acúmúladas', 'ácumuládás'], ['gánánciás', 'ganancías', 'ganancias', 'ganancia'], ['perdída', 'perdidá', 'perdida', 'pérdida', 'perdidas'], ['ganacias', 'ganacia', 'gánáciás', 'ganacías']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: acumuladas, ganancias, perdida, ganacias",
    ),
```

### 61. `plantacion_fertilizante`
- **Tipo**: expense
- **Keywords**: plantacion, fertilizante, copeval
- **Prioridad sugerida**: 660
- **Confianza**: 0.4
- **Cuentas afectadas**: ~17
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="plantacion_fertilizante",
        priority=660,
        required_keywords=[['plantacíon', 'plantacion', 'plantacions', 'plántácion', 'plantación'], ['fertilizante', 'fertílízante', 'fertilizánte', 'fértilizanté', 'fertilizantes'], ['copeval', 'copevals', 'copéval', 'copevál', 'cópeval']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: plantacion, fertilizante, copeval",
    ),
```

### 62. `instalaciones_acum`
- **Tipo**: revenue
- **Keywords**: instalaciones, acum, dep, roble
- **Prioridad sugerida**: 670
- **Confianza**: 0.4
- **Cuentas afectadas**: ~17
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="instalaciones_acum",
        priority=670,
        required_keywords=[['instalaciónes', 'instalacionés', 'instáláciones', 'instalacione', 'ínstalacíones', 'instalaciones'], ['acums', 'ácum', 'acúm', 'acum'], ['deps', 'dép', 'dep'], ['roblé', 'róble', 'robles', 'roble']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: instalaciones, acum, dep, roble",
    ),
```

### 63. `ingresos_otros`
- **Tipo**: revenue
- **Keywords**: ingresos, otros, funcion, fletes
- **Prioridad sugerida**: 680
- **Confianza**: 0.4
- **Cuentas afectadas**: ~16
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="ingresos_otros",
        priority=680,
        required_keywords=[['ingreso', 'ingrésos', 'ingresos', 'íngresos', 'ingresós'], ['ótrós', 'otros', 'otro'], ['funcion', 'funcíon', 'funcions', 'fúncion', 'función'], ['fletes', 'flete', 'flétés']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: ingresos, otros, funcion, fletes",
    ),
```

### 64. `impulsiones_tranques`
- **Tipo**: revenue
- **Keywords**: impulsiones, tranques, orellana, fuentes
- **Prioridad sugerida**: 690
- **Confianza**: 0.4
- **Cuentas afectadas**: ~16
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="impulsiones_tranques",
        priority=690,
        required_keywords=[['impulsionés', 'impulsiones', 'impulsione', 'ímpulsíones', 'impúlsiones', 'impulsiónes'], ['tránques', 'tranque', 'tranques', 'tranqués', 'tranqúes'], ['orellana', 'oréllana', 'orelláná', 'orellanas', 'órellana'], ['fuéntés', 'fuente', 'fuentes', 'fúentes']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: impulsiones, tranques, orellana, fuentes",
    ),
```

### 65. `agricola_lechera`
- **Tipo**: revenue
- **Keywords**: agricola, lechera, stgo, plantacion, fertilizante
- **Prioridad sugerida**: 700
- **Confianza**: 0.4
- **Cuentas afectadas**: ~16
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="agricola_lechera",
        priority=700,
        required_keywords=[['agrícola', 'agricola', 'agricóla', 'agricolas', 'ágricolá'], ['léchéra', 'lecheras', 'lecherá', 'lechera'], ['stgó', 'stgo', 'stgos'], ['plantacíon', 'plantacion', 'plantacions', 'plántácion', 'plantación'], ['fertilizante', 'fertílízante', 'fertilizánte', 'fértilizanté', 'fertilizantes']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: agricola, lechera, stgo, plantacion, fertilizante",
    ),
```

### 66. `inmob_spa`
- **Tipo**: expense
- **Keywords**: inmob, spa, don, cta
- **Prioridad sugerida**: 710
- **Confianza**: 0.4
- **Cuentas afectadas**: ~16
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="inmob_spa",
        priority=710,
        required_keywords=[['inmób', 'ínmob', 'inmob', 'inmobs'], ['spa', 'spas', 'spá'], ['dons', 'dón', 'don'], ['ctá', 'ctas', 'cta']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: inmob, spa, don, cta",
    ),
```

### 67. `varios_dificil`
- **Tipo**: revenue
- **Keywords**: varios, dificil, clasificacion, clasificados
- **Prioridad sugerida**: 720
- **Confianza**: 0.4
- **Cuentas afectadas**: ~15
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="varios_dificil",
        priority=720,
        required_keywords=[['vários', 'varios', 'vario', 'variós', 'varíos'], ['dificil', 'dífícíl', 'dificils'], ['clásificácion', 'clasificacions', 'clasífícacíon', 'clasificación', 'clasificacion'], ['clasificados', 'clasificado', 'clasificadós', 'clasífícados', 'clásificádos']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: varios, dificil, clasificacion, clasificados",
    ),
```

### 68. `capacitacion_gastos`
- **Tipo**: revenue
- **Keywords**: capacitacion, gastos, credito
- **Prioridad sugerida**: 730
- **Confianza**: 0.4
- **Cuentas afectadas**: ~15
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="capacitacion_gastos",
        priority=730,
        required_keywords=[['cápácitácion', 'capacitación', 'capacitacion', 'capacítacíon', 'capacitacions'], ['gasto', 'gastos', 'gastós', 'gástos'], ['crédito', 'creditó', 'credito', 'creditos', 'credíto']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: capacitacion, gastos, credito",
    ),
```

### 69. `radio_2011`
- **Tipo**: revenue
- **Keywords**: radio, 2011, sony, auto
- **Prioridad sugerida**: 740
- **Confianza**: 0.4
- **Cuentas afectadas**: ~15
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="radio_2011",
        priority=740,
        required_keywords=[['radió', 'radío', 'radios', 'radio', 'rádio'], ['2011', '2011s'], ['sony', 'sonys', 'sóny'], ['autó', 'aúto', 'auto', 'autos', 'áuto']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: radio, 2011, sony, auto",
    ),
```

### 70. `deudores_venta`
- **Tipo**: expense
- **Keywords**: deudores, venta, neto, usd
- **Prioridad sugerida**: 750
- **Confianza**: 0.4
- **Cuentas afectadas**: ~14
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="deudores_venta",
        priority=750,
        required_keywords=[['deudore', 'deudóres', 'deúdores', 'deudores', 'déudorés'], ['ventas', 'vénta', 'ventá', 'venta'], ['netó', 'netos', 'néto', 'neto'], ['úsd', 'usds', 'usd']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: deudores, venta, neto, usd",
    ),
```

### 71. `vacaciones_proporcionales`
- **Tipo**: revenue
- **Keywords**: vacaciones, proporcionales, provision, provisione
- **Prioridad sugerida**: 760
- **Confianza**: 0.4
- **Cuentas afectadas**: ~14
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="vacaciones_proporcionales",
        priority=760,
        required_keywords=[['vacaciones', 'vacacionés', 'vacacíones', 'vacaciónes', 'vacacione', 'vácáciones'], ['proporcionáles', 'proporcionale', 'proporcíonales', 'própórciónales', 'proporcionalés', 'proporcionales'], ['provísíon', 'provisions', 'provision', 'próvisión'], ['provisione', 'provísíone', 'próvisióne', 'provisiones', 'provisioné']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: vacaciones, proporcionales, provision, provisione",
    ),
```

### 72. `hidrocivil`
- **Tipo**: revenue
- **Keywords**: hidrocivil
- **Prioridad sugerida**: 770
- **Confianza**: 0.4
- **Cuentas afectadas**: ~14
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="hidrocivil",
        priority=770,
        required_keywords=[['hídrocívíl', 'hidrocivil', 'hidrocivils', 'hidrócivil']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: hidrocivil",
    ),
```

### 73. `proyecto_electrico`
- **Tipo**: expense
- **Keywords**: proyecto, electrico, electrica, nuevo
- **Prioridad sugerida**: 780
- **Confianza**: 0.4
- **Cuentas afectadas**: ~14
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="proyecto_electrico",
        priority=780,
        required_keywords=[['proyectos', 'proyécto', 'proyecto', 'próyectó'], ['electricó', 'electricos', 'electrico', 'éléctrico', 'electríco'], ['electricas', 'electrica', 'éléctrica', 'electríca', 'electricá'], ['nuévo', 'nuevos', 'nuevó', 'núevo', 'nuevo']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: proyecto, electrico, electrica, nuevo",
    ),
```

### 74. `rio_claro`
- **Tipo**: revenue
- **Keywords**: rio, claro, ltda, plantacion, tutores
- **Prioridad sugerida**: 790
- **Confianza**: 0.4
- **Cuentas afectadas**: ~14
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="rio_claro",
        priority=790,
        required_keywords=[['rio', 'rios', 'rió', 'río'], ['claro', 'claró', 'claros', 'cláro'], ['ltda', 'ltdas', 'ltdá'], ['plantacíon', 'plantacion', 'plantacions', 'plántácion', 'plantación'], ['tutores', 'tutóres', 'tútores', 'tutorés', 'tutore']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: rio, claro, ltda, plantacion, tutores",
    ),
```

### 75. `montevideo`
- **Tipo**: revenue
- **Keywords**: montevideo
- **Prioridad sugerida**: 800
- **Confianza**: 0.4
- **Cuentas afectadas**: ~14
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="montevideo",
        priority=800,
        required_keywords=[['montévidéo', 'móntevideó', 'montevideo', 'montevídeo', 'montevideos']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: montevideo",
    ),
```

### 76. `banco_pagar`
- **Tipo**: revenue
- **Keywords**: banco, pagar, corpbanca, cuentas
- **Prioridad sugerida**: 810
- **Confianza**: 0.4
- **Cuentas afectadas**: ~13
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="banco_pagar",
        priority=810,
        required_keywords=[['banco', 'bánco', 'bancos', 'bancó'], ['pagar', 'págár', 'pagars'], ['corpbanca', 'córpbanca', 'corpbancas', 'corpbáncá'], ['cuentás', 'cuenta', 'cuéntas', 'cuentas', 'cúentas']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: banco, pagar, corpbanca, cuentas",
    ),
```

### 77. `profesionales_retencion`
- **Tipo**: revenue
- **Keywords**: profesionales, retencion, cat, tarjeta
- **Prioridad sugerida**: 820
- **Confianza**: 0.4
- **Cuentas afectadas**: ~13
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="profesionales_retencion",
        priority=820,
        required_keywords=[['profesíonales', 'prófesiónales', 'profésionalés', 'profesionales', 'profesionale', 'profesionáles'], ['retencíon', 'retención', 'retencion', 'réténcion', 'retencions'], ['cat', 'cát', 'cats'], ['tárjetá', 'tarjetas', 'tarjéta', 'tarjeta']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: profesionales, retencion, cat, tarjeta",
    ),
```

### 78. `letreros_publicitarios`
- **Tipo**: revenue
- **Keywords**: letreros, publicitarios, aporte
- **Prioridad sugerida**: 830
- **Confianza**: 0.4
- **Cuentas afectadas**: ~13
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="letreros_publicitarios",
        priority=830,
        required_keywords=[['letrero', 'letreros', 'letrerós', 'létréros'], ['publicitarios', 'públicitarios', 'publicitários', 'publicitario', 'publícítaríos', 'publicitariós'], ['aporte', 'áporte', 'aporté', 'apórte', 'aportes']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: letreros, publicitarios, aporte",
    ),
```

### 79. `correspondencia_tramites`
- **Tipo**: expense
- **Keywords**: correspondencia, tramites, franqueo, encomienda
- **Prioridad sugerida**: 840
- **Confianza**: 0.4
- **Cuentas afectadas**: ~13
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="correspondencia_tramites",
        priority=840,
        required_keywords=[['correspondencias', 'córrespóndencia', 'correspondenciá', 'correspondencia', 'correspondencía', 'corréspondéncia'], ['tramites', 'tramités', 'tramítes', 'trámites', 'tramite'], ['franqúeo', 'franquéo', 'franqueo', 'fránqueo', 'franqueos', 'franqueó'], ['encomiendas', 'encomienda', 'encómienda', 'encomiendá', 'éncomiénda', 'encomíenda']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: correspondencia, tramites, franqueo, encomienda",
    ),
```

### 80. `ebitda_ebida`
- **Tipo**: revenue
- **Keywords**: ebitda, ebida
- **Prioridad sugerida**: 850
- **Confianza**: 0.4
- **Cuentas afectadas**: ~13
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="ebitda_ebida",
        priority=850,
        required_keywords=[['ebítda', 'ébitda', 'ebitdas', 'ebitda', 'ebitdá'], ['ebidas', 'ebída', 'ébida', 'ebidá', 'ebida']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: ebitda, ebida",
    ),
```

### 81. `provisiones_cobrar`
- **Tipo**: revenue
- **Keywords**: provisiones, cobrar, fisco, documetos
- **Prioridad sugerida**: 860
- **Confianza**: 0.4
- **Cuentas afectadas**: ~13
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="provisiones_cobrar",
        priority=860,
        required_keywords=[['provisiones', 'provisione', 'provisionés', 'próvisiónes', 'provísíones'], ['cóbrar', 'cobrár', 'cobrars', 'cobrar'], ['fiscos', 'fisco', 'fiscó', 'físco'], ['documétos', 'dócumetós', 'documeto', 'documetos', 'docúmetos']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: provisiones, cobrar, fisco, documetos",
    ),
```

### 82. `prevision_instituciones`
- **Tipo**: revenue
- **Keywords**: prevision, instituciones, clientes, cuentas
- **Prioridad sugerida**: 870
- **Confianza**: 0.4
- **Cuentas afectadas**: ~13
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="prevision_instituciones",
        priority=870,
        required_keywords=[['prevísíon', 'previsions', 'prévision', 'prevision', 'previsión'], ['instituciones', 'institucione', 'institúciones', 'institucionés', 'ínstítucíones', 'instituciónes'], ['cliente', 'clíentes', 'cliéntés', 'clientes'], ['cuentás', 'cuenta', 'cuéntas', 'cuentas', 'cúentas']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: prevision, instituciones, clientes, cuentas",
    ),
```

### 83. `mantencion_vehiculos`
- **Tipo**: revenue
- **Keywords**: mantencion, vehiculos, edificio
- **Prioridad sugerida**: 880
- **Confianza**: 0.4
- **Cuentas afectadas**: ~13
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="mantencion_vehiculos",
        priority=880,
        required_keywords=[['mantencíon', 'manténcion', 'mántencion', 'mantención', 'mantencions', 'mantencion'], ['vehiculos', 'vehiculo', 'véhiculos', 'vehiculós', 'vehículos', 'vehicúlos'], ['edificio', 'edifició', 'edífícío', 'édificio', 'edificios']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: mantencion, vehiculos, edificio",
    ),
```

### 84. `plantacion_desinfeccion`
- **Tipo**: expense
- **Keywords**: plantacion, desinfeccion
- **Prioridad sugerida**: 890
- **Confianza**: 0.4
- **Cuentas afectadas**: ~13
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="plantacion_desinfeccion",
        priority=890,
        required_keywords=[['plantacíon', 'plantacion', 'plantacions', 'plántácion', 'plantación'], ['desinfeccions', 'désinféccion', 'desinfeccion', 'desínfeccíon', 'desinfección']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: plantacion, desinfeccion",
    ),
```

### 85. `contribuciones`
- **Tipo**: expense
- **Keywords**: contribuciones
- **Prioridad sugerida**: 900
- **Confianza**: 0.4
- **Cuentas afectadas**: ~13
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="contribuciones",
        priority=900,
        required_keywords=[['contribucionés', 'contribúciones', 'contríbucíones', 'cóntribuciónes', 'contribuciones', 'contribucione']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: contribuciones",
    ),
```

### 86. `gastos_oficina`
- **Tipo**: expense
- **Keywords**: gastos, oficina, publicidad, comision
- **Prioridad sugerida**: 910
- **Confianza**: 0.4
- **Cuentas afectadas**: ~13
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="gastos_oficina",
        priority=910,
        required_keywords=[['gasto', 'gastos', 'gastós', 'gástos'], ['oficina', 'oficinas', 'óficina', 'ofícína', 'oficiná'], ['publicidád', 'públicidad', 'publícídad', 'publicidad', 'publicidads'], ['cómisión', 'comision', 'comísíon', 'comisions']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: gastos, oficina, publicidad, comision",
    ),
```

### 87. `papel_regalo`
- **Tipo**: revenue
- **Keywords**: papel, regalo, bolsas
- **Prioridad sugerida**: 920
- **Confianza**: 0.4
- **Cuentas afectadas**: ~12
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="papel_regalo",
        priority=920,
        required_keywords=[['papel', 'papels', 'pápel', 'papél'], ['regalos', 'regalo', 'regaló', 'regálo', 'régalo'], ['bolsa', 'bolsás', 'bolsas', 'bólsas']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: papel, regalo, bolsas",
    ),
```

### 88. `materiales_electricos`
- **Tipo**: revenue
- **Keywords**: materiales, electricos, ulectricos
- **Prioridad sugerida**: 930
- **Confianza**: 0.4
- **Cuentas afectadas**: ~12
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="materiales_electricos",
        priority=930,
        required_keywords=[['materiale', 'máteriáles', 'materíales', 'materiales', 'matérialés'], ['electricos', 'electricós', 'electrico', 'electrícos', 'éléctricos'], ['ulectricós', 'ulectricos', 'uléctricos', 'ulectrico', 'úlectricos', 'ulectrícos']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: materiales, electricos, ulectricos",
    ),
```

### 89. `sueldos_viaticos`
- **Tipo**: revenue
- **Keywords**: sueldos, viaticos
- **Prioridad sugerida**: 940
- **Confianza**: 0.4
- **Cuentas afectadas**: ~12
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="sueldos_viaticos",
        priority=940,
        required_keywords=[['sueldos', 'sueldo', 'sueldós', 'súeldos', 'suéldos'], ['viaticos', 'viaticós', 'viáticos', 'víatícos', 'viatico']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: sueldos, viaticos",
    ),
```

### 90. `ventas_otras`
- **Tipo**: revenue
- **Keywords**: ventas, otras, extranjeras, mercado, fuera
- **Prioridad sugerida**: 950
- **Confianza**: 0.4
- **Cuentas afectadas**: ~12
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="ventas_otras",
        priority=950,
        required_keywords=[['ventas', 'venta', 'véntas', 'ventás'], ['otras', 'ótras', 'otra', 'otrás'], ['éxtranjéras', 'extranjeras', 'extránjerás', 'extranjera'], ['mercadó', 'mercádo', 'mercado', 'mércado', 'mercados'], ['fuéra', 'fueras', 'fuera', 'fúera', 'fuerá']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: ventas, otras, extranjeras, mercado, fuera",
    ),
```

### 91. `retenciones_deudores`
- **Tipo**: revenue
- **Keywords**: retenciones, deudores, varios, neto
- **Prioridad sugerida**: 960
- **Confianza**: 0.4
- **Cuentas afectadas**: ~12
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="retenciones_deudores",
        priority=960,
        required_keywords=[['retencione', 'retenciones', 'retenciónes', 'retencíones', 'réténcionés'], ['deudore', 'deudóres', 'deúdores', 'deudores', 'déudorés'], ['vários', 'varios', 'vario', 'variós', 'varíos'], ['netó', 'netos', 'néto', 'neto']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: retenciones, deudores, varios, neto",
    ),
```

### 92. `diciembre`
- **Tipo**: revenue
- **Keywords**: diciembre
- **Prioridad sugerida**: 970
- **Confianza**: 0.4
- **Cuentas afectadas**: ~12
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="diciembre",
        priority=970,
        required_keywords=[['diciembres', 'diciémbré', 'diciembre', 'dícíembre']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: diciembre",
    ),
```

### 93. `seguridad_accesorios`
- **Tipo**: revenue
- **Keywords**: seguridad, accesorios, elem, merc
- **Prioridad sugerida**: 980
- **Confianza**: 0.4
- **Cuentas afectadas**: ~12
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="seguridad_accesorios",
        priority=980,
        required_keywords=[['seguridád', 'seguridads', 'séguridad', 'segúridad', 'segurídad', 'seguridad'], ['accesorio', 'accesoríos', 'accesorios', 'áccesorios', 'accésorios', 'accesóriós'], ['elem', 'élém', 'elems'], ['merc', 'mercs', 'mérc']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: seguridad, accesorios, elem, merc",
    ),
```

### 94. `reserva_rev`
- **Tipo**: expense
- **Keywords**: reserva, rev, capital, spa
- **Prioridad sugerida**: 990
- **Confianza**: 0.4
- **Cuentas afectadas**: ~12
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="reserva_rev",
        priority=990,
        required_keywords=[['reserva', 'reservas', 'résérva', 'reservá'], ['rév', 'revs', 'rev'], ['capitals', 'capítal', 'cápitál', 'capital'], ['spa', 'spas', 'spá']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: reserva, rev, capital, spa",
    ),
```

### 95. `plantas_plantacion`
- **Tipo**: expense
- **Keywords**: plantas, plantacion, paz, correa, pizarro
- **Prioridad sugerida**: 1000
- **Confianza**: 0.4
- **Cuentas afectadas**: ~12
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="plantas_plantacion",
        priority=1000,
        required_keywords=[['plántás', 'planta', 'plantas'], ['plantacíon', 'plantacion', 'plantacions', 'plántácion', 'plantación'], ['pazs', 'paz', 'páz'], ['correá', 'correa', 'córrea', 'correas', 'corréa'], ['pizárro', 'pizarros', 'pízarro', 'pizarro', 'pizarró']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: plantas, plantacion, paz, correa, pizarro",
    ),
```

### 96. `traspaso_cta`
- **Tipo**: revenue
- **Keywords**: traspaso, cta, cte, entre, bancos
- **Prioridad sugerida**: 1010
- **Confianza**: 0.4
- **Cuentas afectadas**: ~12
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="traspaso_cta",
        priority=1010,
        required_keywords=[['traspaso', 'traspasó', 'tráspáso', 'traspasos'], ['ctá', 'ctas', 'cta'], ['cte', 'ctes', 'cté'], ['entre', 'éntré', 'entres'], ['banco', 'bancós', 'báncos', 'bancos']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: traspaso, cta, cte, entre, bancos",
    ),
```

### 97. `inmob_spa`
- **Tipo**: expense
- **Keywords**: inmob, spa, tab, latorre
- **Prioridad sugerida**: 1020
- **Confianza**: 0.4
- **Cuentas afectadas**: ~12
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="inmob_spa",
        priority=1020,
        required_keywords=[['inmób', 'ínmob', 'inmob', 'inmobs'], ['spa', 'spas', 'spá'], ['táb', 'tabs', 'tab'], ['látorre', 'latorres', 'latorre', 'latorré', 'latórre']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: inmob, spa, tab, latorre",
    ),
```

### 98. `existencias_provisiones`
- **Tipo**: expense
- **Keywords**: existencias, provisiones, materiales, insumos
- **Prioridad sugerida**: 1030
- **Confianza**: 0.4
- **Cuentas afectadas**: ~12
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="existencias_provisiones",
        priority=1030,
        required_keywords=[['existenciás', 'existencia', 'exístencías', 'existencias', 'éxisténcias'], ['provisiones', 'provisione', 'provisionés', 'próvisiónes', 'provísíones'], ['materiale', 'máteriáles', 'materíales', 'materiales', 'matérialés'], ['insumo', 'insumos', 'ínsumos', 'insúmos', 'insumós']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: existencias, provisiones, materiales, insumos",
    ),
```

### 99. `unico_impto`
- **Tipo**: revenue
- **Keywords**: unico, impto, tarjeta
- **Prioridad sugerida**: 1040
- **Confianza**: 0.4
- **Cuentas afectadas**: ~11
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="unico_impto",
        priority=1040,
        required_keywords=[['único', 'unicó', 'uníco', 'unicos', 'unico'], ['imptos', 'imptó', 'ímpto', 'impto'], ['tárjetá', 'tarjetas', 'tarjéta', 'tarjeta']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: unico, impto, tarjeta",
    ),
```

### 100. `leasing_obligaciones`
- **Tipo**: revenue
- **Keywords**: leasing, obligaciones, largo
- **Prioridad sugerida**: 1050
- **Confianza**: 0.4
- **Cuentas afectadas**: ~11
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="leasing_obligaciones",
        priority=1050,
        required_keywords=[['leasíng', 'léasing', 'leasing', 'leasings', 'leásing'], ['obligaciones', 'oblígacíones', 'obligacione', 'obligacionés', 'obligáciones', 'óbligaciónes'], ['largos', 'lárgo', 'largó', 'largo']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: leasing, obligaciones, largo",
    ),
```

### 101. `ejercicio_utilidad`
- **Tipo**: expense
- **Keywords**: ejercicio, utilidad
- **Prioridad sugerida**: 1060
- **Confianza**: 0.4
- **Cuentas afectadas**: ~11
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="ejercicio_utilidad",
        priority=1060,
        required_keywords=[['éjércicio', 'ejercicios', 'ejercició', 'ejercícío', 'ejercicio'], ['utilidads', 'utílídad', 'utilidad', 'utilidád', 'útilidad']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: ejercicio, utilidad",
    ),
```

### 102. `seguros_edificios`
- **Tipo**: revenue
- **Keywords**: seguros, edificios, otros
- **Prioridad sugerida**: 1070
- **Confianza**: 0.4
- **Cuentas afectadas**: ~11
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="seguros_edificios",
        priority=1070,
        required_keywords=[['seguro', 'segúros', 'segurós', 'seguros', 'séguros'], ['edificiós', 'edificio', 'édificios', 'edificios', 'edífícíos'], ['ótrós', 'otros', 'otro']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: seguros, edificios, otros",
    ),
```

### 103. `riego_maldonado`
- **Tipo**: revenue
- **Keywords**: riego, maldonado
- **Prioridad sugerida**: 1080
- **Confianza**: 0.4
- **Cuentas afectadas**: ~11
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="riego_maldonado",
        priority=1080,
        required_keywords=[['riégo', 'riego', 'riegos', 'ríego', 'riegó'], ['maldonados', 'maldonado', 'maldónadó', 'máldonádo']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: riego, maldonado",
    ),
```

### 104. `plantacion_tutores`
- **Tipo**: expense
- **Keywords**: plantacion, tutores
- **Prioridad sugerida**: 1090
- **Confianza**: 0.4
- **Cuentas afectadas**: ~11
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="plantacion_tutores",
        priority=1090,
        required_keywords=[['plantacíon', 'plantacion', 'plantacions', 'plántácion', 'plantación'], ['tutores', 'tutóres', 'tútores', 'tutorés', 'tutore']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: plantacion, tutores",
    ),
```

### 105. `pagar_honorarios`
- **Tipo**: revenue
- **Keywords**: pagar, honorarios, tarjeta, din
- **Prioridad sugerida**: 1100
- **Confianza**: 0.4
- **Cuentas afectadas**: ~10
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="pagar_honorarios",
        priority=1100,
        required_keywords=[['pagar', 'págár', 'pagars'], ['honorários', 'honoraríos', 'honorario', 'hónórariós', 'honorarios'], ['tárjetá', 'tarjetas', 'tarjéta', 'tarjeta'], ['din', 'dins', 'dín']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: pagar, honorarios, tarjeta, din",
    ),
```

### 106. `mat_prepar`
- **Tipo**: revenue
- **Keywords**: mat, prepar, vitrinas, visual
- **Prioridad sugerida**: 1110
- **Confianza**: 0.4
- **Cuentas afectadas**: ~10
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="mat_prepar",
        priority=1110,
        required_keywords=[['mát', 'mat', 'mats'], ['prepars', 'prépar', 'prepár', 'prepar'], ['vitrina', 'vitrinás', 'vitrinas', 'vítrínas'], ['visuals', 'visual', 'visúal', 'vísual', 'visuál']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: mat, prepar, vitrinas, visual",
    ),
```

### 107. `aporte_empresa`
- **Tipo**: expense
- **Keywords**: aporte, empresa, afc
- **Prioridad sugerida**: 1120
- **Confianza**: 0.4
- **Cuentas afectadas**: ~10
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="aporte_empresa",
        priority=1120,
        required_keywords=[['aporte', 'áporte', 'aporté', 'apórte', 'aportes'], ['empresa', 'empresas', 'empresá', 'émprésa'], ['afcs', 'áfc', 'afc']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: aporte, empresa, afc",
    ),
```

### 108. `inmob_coronel`
- **Tipo**: expense
- **Keywords**: inmob, coronel, alvarado, spa
- **Prioridad sugerida**: 1130
- **Confianza**: 0.4
- **Cuentas afectadas**: ~10
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="inmob_coronel",
        priority=1130,
        required_keywords=[['inmób', 'ínmob', 'inmob', 'inmobs'], ['coronél', 'córónel', 'coronels', 'coronel'], ['alvarado', 'alvaradó', 'álvárádo', 'alvarados'], ['spa', 'spas', 'spá']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: inmob, coronel, alvarado, spa",
    ),
```

### 109. `monetaria_correc`
- **Tipo**: revenue
- **Keywords**: monetaria, correc, orreccion, rechazados, art
- **Prioridad sugerida**: 1140
- **Confianza**: 0.4
- **Cuentas afectadas**: ~10
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="monetaria_correc",
        priority=1140,
        required_keywords=[['monetaría', 'mónetaria', 'monetarias', 'monetáriá', 'monetaria', 'monétaria'], ['corréc', 'correcs', 'córrec', 'correc'], ['orreccion', 'orréccion', 'órrección', 'orreccíon', 'orreccions'], ['rechazados', 'rechazado', 'rechazadós', 'réchazados', 'recházádos'], ['árt', 'arts', 'art']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: monetaria, correc, orreccion, rechazados, art",
    ),
```

### 110. `computacionales_gastos`
- **Tipo**: expense
- **Keywords**: computacionales, gastos, insumos
- **Prioridad sugerida**: 1150
- **Confianza**: 0.4
- **Cuentas afectadas**: ~10
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="computacionales_gastos",
        priority=1150,
        required_keywords=[['computácionáles', 'computacionale', 'computacionalés', 'computacíonales', 'compútacionales', 'computacionales', 'cómputaciónales'], ['gasto', 'gastos', 'gastós', 'gástos'], ['insumo', 'insumos', 'ínsumos', 'insúmos', 'insumós']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: computacionales, gastos, insumos",
    ),
```

### 111. `agricola_jardin`
- **Tipo**: revenue
- **Keywords**: agricola, jardin
- **Prioridad sugerida**: 1160
- **Confianza**: 0.4
- **Cuentas afectadas**: ~10
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="agricola_jardin",
        priority=1160,
        required_keywords=[['agrícola', 'agricola', 'agricóla', 'agricolas', 'ágricolá'], ['jardín', 'jardin', 'jardins', 'járdin']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: agricola, jardin",
    ),
```

### 112. `pagina`
- **Tipo**: revenue
- **Keywords**: pagina
- **Prioridad sugerida**: 1170
- **Confianza**: 0.4
- **Cuentas afectadas**: ~10
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="pagina",
        priority=1170,
        required_keywords=[['pagina', 'paginas', 'pagína', 'páginá']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: pagina",
    ),
```

### 113. `form`
- **Tipo**: revenue
- **Keywords**: form
- **Prioridad sugerida**: 1180
- **Confianza**: 0.3
- **Cuentas afectadas**: ~9
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="form",
        priority=1180,
        required_keywords=[['fórm', 'form', 'forms']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: form",
    ),
```

### 114. `reajuste_art`
- **Tipo**: revenue
- **Keywords**: reajuste, art, menos
- **Prioridad sugerida**: 1190
- **Confianza**: 0.3
- **Cuentas afectadas**: ~9
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="reajuste_art",
        priority=1190,
        required_keywords=[['reajúste', 'reajuste', 'réajusté', 'reájuste', 'reajustes'], ['árt', 'arts', 'art'], ['ménos', 'menos', 'meno', 'menós']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: reajuste, art, menos",
    ),
```

### 115. `provision_intereses`
- **Tipo**: expense
- **Keywords**: provision, intereses, wages, seguro
- **Prioridad sugerida**: 1200
- **Confianza**: 0.3
- **Cuentas afectadas**: ~9
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="provision_intereses",
        priority=1200,
        required_keywords=[['provísíon', 'provisions', 'provision', 'próvisión'], ['íntereses', 'intérésés', 'intereses', 'interese'], ['wage', 'wages', 'wáges', 'wagés'], ['seguro', 'seguró', 'segúro', 'séguro', 'seguros']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: provision, intereses, wages, seguro",
    ),
```

### 116. `inversiones_cuanta`
- **Tipo**: revenue
- **Keywords**: inversiones, cuanta, pagar
- **Prioridad sugerida**: 1210
- **Confianza**: 0.3
- **Cuentas afectadas**: ~9
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="inversiones_cuanta",
        priority=1210,
        required_keywords=[['inversiones', 'inversiónes', 'ínversíones', 'inversione', 'invérsionés'], ['cuántá', 'cúanta', 'cuantas', 'cuanta'], ['pagar', 'págár', 'pagars']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: inversiones, cuanta, pagar",
    ),
```

### 117. `plantaciones_cia`
- **Tipo**: expense
- **Keywords**: plantaciones, cia, forestales, garcia
- **Prioridad sugerida**: 1220
- **Confianza**: 0.3
- **Cuentas afectadas**: ~9
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="plantaciones_cia",
        priority=1220,
        required_keywords=[['plantaciónes', 'plantacionés', 'plántáciones', 'plantacione', 'plantacíones', 'plantaciones'], ['ciá', 'cias', 'cia', 'cía'], ['foréstalés', 'forestale', 'forestales', 'forestáles', 'fórestales'], ['garcía', 'gárciá', 'garcia', 'garcias']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: plantaciones, cia, forestales, garcia",
    ),
```

### 118. `valor_fondos`
- **Tipo**: revenue
- **Keywords**: valor, fondos, mutuos, mayor, financiero
- **Prioridad sugerida**: 1230
- **Confianza**: 0.3
- **Cuentas afectadas**: ~9
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="valor_fondos",
        priority=1230,
        required_keywords=[['valór', 'valor', 'valors', 'válor'], ['fondos', 'fóndós', 'fondo'], ['mútúos', 'mutuós', 'mutuo', 'mutuos'], ['máyor', 'mayors', 'mayor', 'mayór'], ['financieró', 'financiero', 'financiéro', 'financieros', 'fínancíero', 'finánciero']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: valor, fondos, mutuos, mayor, financiero",
    ),
```

### 119. `periodo_renta`
- **Tipo**: revenue
- **Keywords**: periodo, renta, liquida, compras
- **Prioridad sugerida**: 1240
- **Confianza**: 0.3
- **Cuentas afectadas**: ~9
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="periodo_renta",
        priority=1240,
        required_keywords=[['período', 'periodo', 'périodo', 'periodos', 'periódó'], ['rentá', 'rentas', 'rénta', 'renta'], ['liquida', 'liqúida', 'liquidas', 'líquída', 'liquidá'], ['comprás', 'compras', 'cómpras', 'compra']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: periodo, renta, liquida, compras",
    ),
```

### 120. `saldo_segun`
- **Tipo**: revenue
- **Keywords**: saldo, segun, libro
- **Prioridad sugerida**: 1250
- **Confianza**: 0.3
- **Cuentas afectadas**: ~9
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="saldo_segun",
        priority=1250,
        required_keywords=[['saldos', 'sáldo', 'saldó', 'saldo'], ['seguns', 'segun', 'según', 'ségun'], ['libro', 'libró', 'libros', 'líbro']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: saldo, segun, libro",
    ),
```

### 121. `bonificacion_ant`
- **Tipo**: revenue
- **Keywords**: bonificacion, ant, marzo, sept
- **Prioridad sugerida**: 1260
- **Confianza**: 0.3
- **Cuentas afectadas**: ~9
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="bonificacion_ant",
        priority=1260,
        required_keywords=[['bónificación', 'bonífícacíon', 'bonificacion', 'bonificacions', 'bonificácion'], ['ánt', 'ant', 'ants'], ['marzos', 'márzo', 'marzo', 'marzó'], ['septs', 'sépt', 'sept']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: bonificacion, ant, marzo, sept",
    ),
```

### 122. `caseta_obras`
- **Tipo**: revenue
- **Keywords**: caseta, obras, civiles, orellana
- **Prioridad sugerida**: 1270
- **Confianza**: 0.3
- **Cuentas afectadas**: ~9
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="caseta_obras",
        priority=1270,
        required_keywords=[['casetas', 'caseta', 'caséta', 'cásetá'], ['óbras', 'obrás', 'obra', 'obras'], ['civilés', 'civile', 'cívíles', 'civiles'], ['orellana', 'oréllana', 'orelláná', 'orellanas', 'órellana']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: caseta, obras, civiles, orellana",
    ),
```

### 123. `2019`
- **Tipo**: revenue
- **Keywords**: 2019
- **Prioridad sugerida**: 1280
- **Confianza**: 0.3
- **Cuentas afectadas**: ~9
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="2019",
        priority=1280,
        required_keywords=[['2019', '2019s']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: 2019",
    ),
```

### 124. `ambientacion_audio`
- **Tipo**: expense
- **Keywords**: ambientacion, audio
- **Prioridad sugerida**: 1290
- **Confianza**: 0.3
- **Cuentas afectadas**: ~9
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="ambientacion_audio",
        priority=1290,
        required_keywords=[['ambientacion', 'ámbientácion', 'ambientacions', 'ambiéntacion', 'ambíentacíon', 'ambientación'], ['audio', 'audío', 'audios', 'aúdio', 'audió', 'áudio']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: ambientacion, audio",
    ),
```

### 125. `leasing_diferido`
- **Tipo**: expense
- **Keywords**: leasing, diferido, interes, intereses
- **Prioridad sugerida**: 1300
- **Confianza**: 0.3
- **Cuentas afectadas**: ~9
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="leasing_diferido",
        priority=1300,
        required_keywords=[['leasíng', 'léasing', 'leasing', 'leasings', 'leásing'], ['diferidos', 'diférido', 'diferidó', 'diferido', 'díferído'], ['intere', 'intérés', 'interes', 'ínteres'], ['íntereses', 'intérésés', 'intereses', 'interese']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: leasing, diferido, interes, intereses",
    ),
```

### 126. `acreedores_scotiabank`
- **Tipo**: revenue
- **Keywords**: acreedores, scotiabank, varios, 754
- **Prioridad sugerida**: 1310
- **Confianza**: 0.3
- **Cuentas afectadas**: ~8
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="acreedores_scotiabank",
        priority=1310,
        required_keywords=[['acréédorés', 'acreedóres', 'acreedore', 'acreedores', 'ácreedores'], ['scotiabank', 'scótiabank', 'scotiábánk', 'scotíabank', 'scotiabanks'], ['vários', 'varios', 'vario', 'variós', 'varíos'], ['754', '754s']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: acreedores, scotiabank, varios, 754",
    ),
```

### 127. `activos_pasivos`
- **Tipo**: revenue
- **Keywords**: activos, pasivos, intangibles, distintos
- **Prioridad sugerida**: 1320
- **Confianza**: 0.3
- **Cuentas afectadas**: ~8
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="activos_pasivos",
        priority=1320,
        required_keywords=[['actívos', 'áctivos', 'activo', 'activós', 'activos'], ['pasivos', 'pasivós', 'pásivos', 'pasívos', 'pasivo'], ['intangibles', 'intángibles', 'intangiblés', 'íntangíbles', 'intangible'], ['dístíntos', 'distinto', 'distintós', 'distintos']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: activos, pasivos, intangibles, distintos",
    ),
```

### 128. `empleados_provisiones`
- **Tipo**: expense
- **Keywords**: empleados, provisiones, corrientes
- **Prioridad sugerida**: 1330
- **Confianza**: 0.3
- **Cuentas afectadas**: ~8
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="empleados_provisiones",
        priority=1330,
        required_keywords=[['empleados', 'empleadós', 'empleado', 'émpléados', 'empleádos'], ['provisiones', 'provisione', 'provisionés', 'próvisiónes', 'provísíones'], ['corríentes', 'corriente', 'corriéntés', 'corrientes', 'córrientes']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: empleados, provisiones, corrientes",
    ),
```

### 129. `intangibles_activos`
- **Tipo**: expense
- **Keywords**: intangibles, activos, distintos
- **Prioridad sugerida**: 1340
- **Confianza**: 0.3
- **Cuentas afectadas**: ~8
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="intangibles_activos",
        priority=1340,
        required_keywords=[['intangibles', 'intángibles', 'intangiblés', 'íntangíbles', 'intangible'], ['actívos', 'áctivos', 'activo', 'activós', 'activos'], ['dístíntos', 'distinto', 'distintós', 'distintos']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: intangibles, activos, distintos",
    ),
```

### 130. `colon_proyecto`
- **Tipo**: revenue
- **Keywords**: colon, proyecto
- **Prioridad sugerida**: 1350
- **Confianza**: 0.3
- **Cuentas afectadas**: ~8
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="colon_proyecto",
        priority=1350,
        required_keywords=[['colon', 'colons', 'cólón'], ['proyectos', 'proyécto', 'proyecto', 'próyectó']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: colon, proyecto",
    ),
```

### 131. `cuentas_cobrar`
- **Tipo**: revenue
- **Keywords**: cuentas, cobrar, pagar, relac
- **Prioridad sugerida**: 1360
- **Confianza**: 0.3
- **Cuentas afectadas**: ~8
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="cuentas_cobrar",
        priority=1360,
        required_keywords=[['cuentás', 'cuenta', 'cuéntas', 'cuentas', 'cúentas'], ['cóbrar', 'cobrár', 'cobrars', 'cobrar'], ['pagar', 'págár', 'pagars'], ['relacs', 'rélac', 'relac', 'relác']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: cuentas, cobrar, pagar, relac",
    ),
```

### 132. `arriendos_devengados`
- **Tipo**: revenue
- **Keywords**: arriendos, devengados, anticipado, arriendo
- **Prioridad sugerida**: 1370
- **Confianza**: 0.3
- **Cuentas afectadas**: ~8
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="arriendos_devengados",
        priority=1370,
        required_keywords=[['árriendos', 'arriendos', 'arriendós', 'arriéndos', 'arriendo', 'arríendos'], ['devengado', 'devengados', 'devengadós', 'devengádos', 'dévéngados'], ['anticipados', 'anticipadó', 'antícípado', 'ánticipádo', 'anticipado'], ['arriéndo', 'árriendo', 'arriendó', 'arriendos', 'arriendo', 'arríendo']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: arriendos, devengados, anticipado, arriendo",
    ),
```

### 133. `gastos_vehiculo`
- **Tipo**: expense
- **Keywords**: gastos, vehiculo, rendiciones, telefonicos
- **Prioridad sugerida**: 1380
- **Confianza**: 0.3
- **Cuentas afectadas**: ~8
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="gastos_vehiculo",
        priority=1380,
        required_keywords=[['gasto', 'gastos', 'gastós', 'gástos'], ['vehiculos', 'vehiculo', 'véhiculo', 'vehiculó', 'vehicúlo', 'vehículo'], ['rendiciónes', 'réndicionés', 'rendícíones', 'rendicione', 'rendiciones'], ['telefonícos', 'telefonico', 'telefónicós', 'téléfonicos', 'telefonicos']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: gastos, vehiculo, rendiciones, telefonicos",
    ),
```

### 134. `capital_propio`
- **Tipo**: revenue
- **Keywords**: capital, propio, revaloriz
- **Prioridad sugerida**: 1390
- **Confianza**: 0.3
- **Cuentas afectadas**: ~8
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="capital_propio",
        priority=1390,
        required_keywords=[['capitals', 'capítal', 'cápitál', 'capital'], ['propio', 'propío', 'própió', 'propios'], ['revalóriz', 'révaloriz', 'revaloriz', 'revaloríz', 'reváloriz', 'revalorizs']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: capital, propio, revaloriz",
    ),
```

### 135. `perdida_ejercicio`
- **Tipo**: expense
- **Keywords**: perdida, ejercicio, 21050utilidad, 2005, ajuste
- **Prioridad sugerida**: 1400
- **Confianza**: 0.3
- **Cuentas afectadas**: ~8
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="perdida_ejercicio",
        priority=1400,
        required_keywords=[['perdída', 'perdidá', 'perdida', 'pérdida', 'perdidas'], ['éjércicio', 'ejercicios', 'ejercició', 'ejercícío', 'ejercicio'], ['21050utilidád', '21050utílídad', '21050utilidad', '21050utilidads', '21050útilidad'], ['2005s', '2005'], ['ájuste', 'ajustes', 'ajuste', 'ajusté', 'ajúste']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: perdida, ejercicio, 21050utilidad, 2005, ajuste",
    ),
```

### 136. `empresas_inversiones`
- **Tipo**: expense
- **Keywords**: empresas, inversiones, relacionadas, relacionada
- **Prioridad sugerida**: 1410
- **Confianza**: 0.3
- **Cuentas afectadas**: ~8
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="empresas_inversiones",
        priority=1410,
        required_keywords=[['empresás', 'empresa', 'émprésas', 'empresas'], ['inversiones', 'inversiónes', 'ínversíones', 'inversione', 'invérsionés'], ['rélacionadas', 'relacíonadas', 'relacionadas', 'relácionádás', 'relacionada', 'relaciónadas'], ['relácionádá', 'relaciónada', 'relacionadas', 'relacíonada', 'rélacionada', 'relacionada']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: empresas, inversiones, relacionadas, relacionada",
    ),
```

### 137. `doctos_pagar`
- **Tipo**: revenue
- **Keywords**: doctos, pagar, ctas
- **Prioridad sugerida**: 1420
- **Confianza**: 0.3
- **Cuentas afectadas**: ~8
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="doctos_pagar",
        priority=1420,
        required_keywords=[['dóctós', 'doctos', 'docto'], ['pagar', 'págár', 'pagars'], ['ctás', 'ctas', 'cta']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: doctos, pagar, ctas",
    ),
```

### 138. `cta_inmob`
- **Tipo**: expense
- **Keywords**: cta, inmob, don, part
- **Prioridad sugerida**: 1430
- **Confianza**: 0.3
- **Cuentas afectadas**: ~8
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="cta_inmob",
        priority=1430,
        required_keywords=[['ctá', 'ctas', 'cta'], ['inmób', 'ínmob', 'inmob', 'inmobs'], ['dons', 'dón', 'don'], ['part', 'párt', 'parts']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: cta, inmob, don, part",
    ),
```

### 139. `otras_provisiones`
- **Tipo**: revenue
- **Keywords**: otras, provisiones, corto, plazo
- **Prioridad sugerida**: 1440
- **Confianza**: 0.3
- **Cuentas afectadas**: ~8
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="otras_provisiones",
        priority=1440,
        required_keywords=[['otras', 'ótras', 'otra', 'otrás'], ['provisiones', 'provisione', 'provisionés', 'próvisiónes', 'provísíones'], ['corto', 'cortos', 'córtó'], ['plazos', 'plazo', 'plazó', 'plázo']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: otras, provisiones, corto, plazo",
    ),
```

### 140. `notas_adjuntas`
- **Tipo**: revenue
- **Keywords**: notas, adjuntas, numeros
- **Prioridad sugerida**: 1450
- **Confianza**: 0.3
- **Cuentas afectadas**: ~8
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="notas_adjuntas",
        priority=1450,
        required_keywords=[['notas', 'nótas', 'nota', 'notás'], ['adjuntas', 'adjunta', 'ádjuntás', 'adjúntas'], ['numéros', 'numerós', 'numeros', 'numero', 'números']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: notas, adjuntas, numeros",
    ),
```

### 141. `estados_financieros`
- **Tipo**: revenue
- **Keywords**: estados, financieros, forman, parte
- **Prioridad sugerida**: 1460
- **Confianza**: 0.3
- **Cuentas afectadas**: ~8
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="estados_financieros",
        priority=1460,
        required_keywords=[['estádos', 'estadós', 'estados', 'éstados', 'estado'], ['fináncieros', 'fínancíeros', 'financiéros', 'financiero', 'financieros', 'financierós'], ['formán', 'fórman', 'forman', 'formans'], ['parté', 'párte', 'partes', 'parte']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: estados, financieros, forman, parte",
    ),
```

### 142. `materias_primas`
- **Tipo**: revenue
- **Keywords**: materias, primas, existencias, retenciones, 30270venta
- **Prioridad sugerida**: 1470
- **Confianza**: 0.3
- **Cuentas afectadas**: ~8
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="materias_primas",
        priority=1470,
        required_keywords=[['materias', 'matérias', 'máteriás', 'materia', 'materías'], ['primas', 'primás', 'prímas', 'prima'], ['existenciás', 'existencia', 'exístencías', 'existencias', 'éxisténcias'], ['retencione', 'retenciones', 'retenciónes', 'retencíones', 'réténcionés'], ['30270vénta', '30270venta', '30270ventas', '30270ventá']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: materias, primas, existencias, retenciones, 30270venta",
    ),
```

### 143. `banco_santander`
- **Tipo**: expense
- **Keywords**: banco, santander, prestamo, credito, linea
- **Prioridad sugerida**: 1480
- **Confianza**: 0.3
- **Cuentas afectadas**: ~8
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="banco_santander",
        priority=1480,
        required_keywords=[['banco', 'bánco', 'bancos', 'bancó'], ['santanders', 'santander', 'sántánder', 'santandér'], ['prestamos', 'préstamo', 'prestamo', 'prestamó', 'prestámo'], ['crédito', 'creditó', 'credito', 'creditos', 'credíto'], ['lineas', 'linéa', 'línea', 'lineá', 'linea']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: banco, santander, prestamo, credito, linea",
    ),
```

### 144. `direccion_avenida`
- **Tipo**: revenue
- **Keywords**: direccion, avenida, torres
- **Prioridad sugerida**: 1490
- **Confianza**: 0.3
- **Cuentas afectadas**: ~8
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="direccion_avenida",
        priority=1490,
        required_keywords=[['direccion', 'dirección', 'diréccion', 'direccions', 'díreccíon'], ['avenidas', 'avenida', 'avenída', 'ávenidá', 'avénida'], ['torre', 'torres', 'tórres', 'torrés']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: direccion, avenida, torres",
    ),
```

### 145. `giro_comercial`
- **Tipo**: revenue
- **Keywords**: giro, comercial, codigo, agricola
- **Prioridad sugerida**: 1500
- **Confianza**: 0.3
- **Cuentas afectadas**: ~8
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="giro_comercial",
        priority=1500,
        required_keywords=[['giros', 'gíro', 'giró', 'giro'], ['comerciál', 'comercíal', 'comercial', 'comercials', 'cómercial', 'comércial'], ['codígo', 'códigó', 'codigos', 'codigo'], ['agrícola', 'agricola', 'agricóla', 'agricolas', 'ágricolá']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: giro, comercial, codigo, agricola",
    ),
```

### 146. `publicidad_gastos`
- **Tipo**: expense
- **Keywords**: publicidad, gastos, 10125, 49225
- **Prioridad sugerida**: 1510
- **Confianza**: 0.3
- **Cuentas afectadas**: ~8
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="publicidad_gastos",
        priority=1510,
        required_keywords=[['publicidád', 'públicidad', 'publícídad', 'publicidad', 'publicidads'], ['gasto', 'gastos', 'gastós', 'gástos'], ['10125s', '10125'], ['49225s', '49225']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: publicidad, gastos, 10125, 49225",
    ),
```

### 147. `credito_intereses`
- **Tipo**: expense
- **Keywords**: credito, intereses, 40250intereses, pag
- **Prioridad sugerida**: 1520
- **Confianza**: 0.3
- **Cuentas afectadas**: ~8
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="credito_intereses",
        priority=1520,
        required_keywords=[['crédito', 'creditó', 'credito', 'creditos', 'credíto'], ['íntereses', 'intérésés', 'intereses', 'interese'], ['40250intérésés', '40250interese', '40250íntereses', '40250intereses'], ['pags', 'pag', 'pág']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: credito, intereses, 40250intereses, pag",
    ),
```

### 148. `declaracion_mas`
- **Tipo**: revenue
- **Keywords**: declaracion, mas, reajustes, fuera
- **Prioridad sugerida**: 1530
- **Confianza**: 0.3
- **Cuentas afectadas**: ~7
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="declaracion_mas",
        priority=1530,
        required_keywords=[['declaracíon', 'déclaracion', 'declaracion', 'declaracions', 'declaración', 'declárácion'], ['ma', 'más', 'mas'], ['reajuste', 'reájustes', 'réajustés', 'reajústes', 'reajustes'], ['fuéra', 'fueras', 'fuera', 'fúera', 'fuerá']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: declaracion, mas, reajustes, fuera",
    ),
```

### 149. `terceros_servicios`
- **Tipo**: revenue
- **Keywords**: terceros, servicios, honorarios
- **Prioridad sugerida**: 1540
- **Confianza**: 0.3
- **Cuentas afectadas**: ~7
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="terceros_servicios",
        priority=1540,
        required_keywords=[['tercerós', 'tércéros', 'tercero', 'terceros'], ['serviciós', 'servicio', 'sérvicios', 'servícíos', 'servicios'], ['honorários', 'honoraríos', 'honorario', 'hónórariós', 'honorarios']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: terceros, servicios, honorarios",
    ),
```

### 150. `seguros_porpagar`
- **Tipo**: expense
- **Keywords**: seguros, porpagar, had
- **Prioridad sugerida**: 1550
- **Confianza**: 0.3
- **Cuentas afectadas**: ~7
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="seguros_porpagar",
        priority=1550,
        required_keywords=[['seguro', 'segúros', 'segurós', 'seguros', 'séguros'], ['porpágár', 'porpagar', 'porpagars', 'pórpagar'], ['hads', 'hád', 'had']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: seguros, porpagar, had",
    ),
```

### 151. `impuestos_gasto`
- **Tipo**: expense
- **Keywords**: impuestos, gasto
- **Prioridad sugerida**: 1560
- **Confianza**: 0.3
- **Cuentas afectadas**: ~7
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="impuestos_gasto",
        priority=1560,
        required_keywords=[['ímpuestos', 'impuestós', 'impuéstos', 'impuesto', 'impuestos', 'impúestos'], ['gastó', 'gasto', 'gásto', 'gastos']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: impuestos, gasto",
    ),
```

### 152. `asesorias_profesionales`
- **Tipo**: expense
- **Keywords**: asesorias, profesionales, honorarios, 52202
- **Prioridad sugerida**: 1570
- **Confianza**: 0.3
- **Cuentas afectadas**: ~7
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="asesorias_profesionales",
        priority=1570,
        required_keywords=[['asesórias', 'asesoria', 'asesorías', 'asésorias', 'asesorias', 'ásesoriás'], ['profesíonales', 'prófesiónales', 'profésionalés', 'profesionales', 'profesionale', 'profesionáles'], ['honorários', 'honoraríos', 'honorario', 'hónórariós', 'honorarios'], ['52202s', '52202']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: asesorias, profesionales, honorarios, 52202",
    ),
```

### 153. `derechos_usufructo`
- **Tipo**: revenue
- **Keywords**: derechos, usufructo, saldo, 13401
- **Prioridad sugerida**: 1580
- **Confianza**: 0.3
- **Cuentas afectadas**: ~7
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="derechos_usufructo",
        priority=1580,
        required_keywords=[['déréchos', 'derechós', 'derecho', 'derechos'], ['usufructos', 'usufructó', 'úsúfrúcto', 'usufructo'], ['saldos', 'sáldo', 'saldó', 'saldo'], ['13401s', '13401']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: derechos, usufructo, saldo, 13401",
    ),
```

### 154. `ajuste_remanente`
- **Tipo**: revenue
- **Keywords**: ajuste, remanente, credito, fiscal
- **Prioridad sugerida**: 1590
- **Confianza**: 0.3
- **Cuentas afectadas**: ~7
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="ajuste_remanente",
        priority=1590,
        required_keywords=[['ájuste', 'ajustes', 'ajuste', 'ajusté', 'ajúste'], ['remanente', 'remánente', 'rémanénté', 'remanentes'], ['crédito', 'creditó', 'credito', 'creditos', 'credíto'], ['fiscál', 'físcal', 'fiscals', 'fiscal']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: ajuste, remanente, credito, fiscal",
    ),
```

### 155. `mahuidanche_lote`
- **Tipo**: expense
- **Keywords**: mahuidanche, lote
- **Prioridad sugerida**: 1600
- **Confianza**: 0.3
- **Cuentas afectadas**: ~7
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="mahuidanche_lote",
        priority=1600,
        required_keywords=[['máhuidánche', 'mahuídanche', 'mahuidanche', 'mahuidanches', 'mahuidanché', 'mahúidanche'], ['lóte', 'lote', 'loté', 'lotes']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: mahuidanche, lote",
    ),
```

### 156. `plantas_plantacion`
- **Tipo**: revenue
- **Keywords**: plantas, plantacion, natividad, ltda, nogal
- **Prioridad sugerida**: 1610
- **Confianza**: 0.3
- **Cuentas afectadas**: ~7
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="plantas_plantacion",
        priority=1610,
        required_keywords=[['plántás', 'planta', 'plantas'], ['plantacíon', 'plantacion', 'plantacions', 'plántácion', 'plantación'], ['nátividád', 'natividad', 'natividads', 'natívídad'], ['ltda', 'ltdas', 'ltdá'], ['nogál', 'nógal', 'nogal', 'nogals']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: plantas, plantacion, natividad, ltda, nogal",
    ),
```

### 157. `2020`
- **Tipo**: revenue
- **Keywords**: 2020
- **Prioridad sugerida**: 1620
- **Confianza**: 0.3
- **Cuentas afectadas**: ~7
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="2020",
        priority=1620,
        required_keywords=[['2020s', '2020']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: 2020",
    ),
```

### 158. `bonificacion_conaf`
- **Tipo**: revenue
- **Keywords**: bonificacion, conaf, constancia, puyaral
- **Prioridad sugerida**: 1630
- **Confianza**: 0.3
- **Cuentas afectadas**: ~7
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="bonificacion_conaf",
        priority=1630,
        required_keywords=[['bónificación', 'bonífícacíon', 'bonificacion', 'bonificacions', 'bonificácion'], ['cónaf', 'conáf', 'conafs', 'conaf'], ['constancias', 'cónstancia', 'constancia', 'constancía', 'constánciá'], ['púyaral', 'puyarals', 'puyárál', 'puyaral']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: bonificacion, conaf, constancia, puyaral",
    ),
```

### 159. `bonificacion_ramon`
- **Tipo**: revenue
- **Keywords**: bonificacion, ramon, pedro, ipa
- **Prioridad sugerida**: 1640
- **Confianza**: 0.3
- **Cuentas afectadas**: ~7
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="bonificacion_ramon",
        priority=1640,
        required_keywords=[['bónificación', 'bonífícacíon', 'bonificacion', 'bonificacions', 'bonificácion'], ['ramon', 'rámon', 'ramón', 'ramons'], ['pedro', 'pedró', 'pedros', 'pédro'], ['ipa', 'ipas', 'ípa', 'ipá']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: bonificacion, ramon, pedro, ipa",
    ),
```

### 160. `arauco_arsuco`
- **Tipo**: revenue
- **Keywords**: arauco, arsuco, coger
- **Prioridad sugerida**: 1650
- **Confianza**: 0.3
- **Cuentas afectadas**: ~7
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="arauco_arsuco",
        priority=1650,
        required_keywords=[['araucos', 'araúco', 'araucó', 'áráuco', 'arauco'], ['arsuco', 'arsucó', 'ársuco', 'arsúco', 'arsucos'], ['cóger', 'cogér', 'cogers', 'coger']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: arauco, arsuco, coger",
    ),
```

### 161. `189_pag`
- **Tipo**: revenue
- **Keywords**: 189, pag, 230
- **Prioridad sugerida**: 1660
- **Confianza**: 0.3
- **Cuentas afectadas**: ~7
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="189_pag",
        priority=1660,
        required_keywords=[['189', '189s'], ['pags', 'pag', 'pág'], ['230', '230s']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: 189, pag, 230",
    ),
```

### 162. `intereses_pagados`
- **Tipo**: revenue
- **Keywords**: intereses, pagados, adeudados
- **Prioridad sugerida**: 1670
- **Confianza**: 0.3
- **Cuentas afectadas**: ~7
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="intereses_pagados",
        priority=1670,
        required_keywords=[['íntereses', 'intérésés', 'intereses', 'interese'], ['pagados', 'pagadós', 'pagado', 'págádos'], ['adéudados', 'adeúdados', 'adeudados', 'ádeudádos', 'adeudadós', 'adeudado']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: intereses, pagados, adeudados",
    ),
```

### 163. `asesorias_servicios`
- **Tipo**: expense
- **Keywords**: asesorias, servicios, negocios, cta
- **Prioridad sugerida**: 1680
- **Confianza**: 0.3
- **Cuentas afectadas**: ~7
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="asesorias_servicios",
        priority=1680,
        required_keywords=[['asesórias', 'asesoria', 'asesorías', 'asésorias', 'asesorias', 'ásesoriás'], ['serviciós', 'servicio', 'sérvicios', 'servícíos', 'servicios'], ['negocios', 'négocios', 'negóciós', 'negocíos', 'negocio'], ['ctá', 'ctas', 'cta']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: asesorias, servicios, negocios, cta",
    ),
```

### 164. `suscripciones_inscripciones`
- **Tipo**: expense
- **Keywords**: suscripciones, inscripciones, 49233
- **Prioridad sugerida**: 1690
- **Confianza**: 0.3
- **Cuentas afectadas**: ~7
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="suscripciones_inscripciones",
        priority=1690,
        required_keywords=[['suscripciónes', 'suscripciones', 'suscripcionés', 'súscripciones', 'suscrípcíones', 'suscripcione'], ['ínscrípcíones', 'inscripciones', 'inscripciónes', 'inscripcione', 'inscripcionés'], ['49233s', '49233']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: suscripciones, inscripciones, 49233",
    ),
```

### 165. `gastos_legales`
- **Tipo**: expense
- **Keywords**: gastos, legales, leasing, 40228
- **Prioridad sugerida**: 1700
- **Confianza**: 0.3
- **Cuentas afectadas**: ~7
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="gastos_legales",
        priority=1700,
        required_keywords=[['gasto', 'gastos', 'gastós', 'gástos'], ['legale', 'légalés', 'legáles', 'legales'], ['leasíng', 'léasing', 'leasing', 'leasings', 'leásing'], ['40228s', '40228']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: gastos, legales, leasing, 40228",
    ),
```

### 166. `asesoria_legal`
- **Tipo**: expense
- **Keywords**: asesoria, legal, agricola, contable
- **Prioridad sugerida**: 1710
- **Confianza**: 0.3
- **Cuentas afectadas**: ~7
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="asesoria_legal",
        priority=1710,
        required_keywords=[['asesoria', 'asesoría', 'asesorias', 'ásesoriá', 'asesória', 'asésoria'], ['legal', 'légal', 'legals', 'legál'], ['agrícola', 'agricola', 'agricóla', 'agricolas', 'ágricolá'], ['contáble', 'cóntable', 'contable', 'contables', 'contablé']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: asesoria, legal, agricola, contable",
    ),
```

### 167. `nacionales_capital`
- **Tipo**: revenue
- **Keywords**: nacionales, capital, ventas
- **Prioridad sugerida**: 1720
- **Confianza**: 0.3
- **Cuentas afectadas**: ~6
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="nacionales_capital",
        priority=1720,
        required_keywords=[['nacionale', 'nacionales', 'naciónales', 'nacionalés', 'nácionáles', 'nacíonales'], ['capitals', 'capítal', 'cápitál', 'capital'], ['ventas', 'venta', 'véntas', 'ventás']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: nacionales, capital, ventas",
    ),
```

### 168. `capital_pagado`
- **Tipo**: revenue
- **Keywords**: capital, pagado, 23101, deudores
- **Prioridad sugerida**: 1730
- **Confianza**: 0.3
- **Cuentas afectadas**: ~6
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="capital_pagado",
        priority=1730,
        required_keywords=[['capitals', 'capítal', 'cápitál', 'capital'], ['pagado', 'pagados', 'pagadó', 'págádo'], ['23101s', '23101'], ['deudore', 'deudóres', 'deúdores', 'deudores', 'déudorés']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: capital, pagado, 23101, deudores",
    ),
```

### 169. `dec_2017`
- **Tipo**: expense
- **Keywords**: dec, 2017, assets, 2015
- **Prioridad sugerida**: 1740
- **Confianza**: 0.3
- **Cuentas afectadas**: ~6
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="dec_2017",
        priority=1740,
        required_keywords=[['déc', 'decs', 'dec'], ['2017', '2017s'], ['asséts', 'assets', 'asset', 'ássets'], ['2015', '2015s']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: dec, 2017, assets, 2015",
    ),
```

### 170. `impuesto_timbres`
- **Tipo**: revenue
- **Keywords**: impuesto, timbres, primera, categoria
- **Prioridad sugerida**: 1750
- **Confianza**: 0.3
- **Cuentas afectadas**: ~6
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="impuesto_timbres",
        priority=1750,
        required_keywords=[['impuésto', 'impuesto', 'impuestos', 'impuestó', 'impúesto', 'ímpuesto'], ['timbres', 'timbrés', 'tímbres', 'timbre'], ['prímera', 'primeras', 'priméra', 'primerá', 'primera'], ['categoría', 'catégoria', 'categoria', 'cátegoriá', 'categorias', 'categória']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: impuesto, timbres, primera, categoria",
    ),
```

### 171. `mercaderias_impto`
- **Tipo**: revenue
- **Keywords**: mercaderias, impto, unico, categ
- **Prioridad sugerida**: 1760
- **Confianza**: 0.3
- **Cuentas afectadas**: ~6
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="mercaderias_impto",
        priority=1760,
        required_keywords=[['mercaderias', 'mercaderia', 'mercáderiás', 'mercaderías', 'mércadérias'], ['imptos', 'imptó', 'ímpto', 'impto'], ['único', 'unicó', 'uníco', 'unicos', 'unico'], ['cáteg', 'catég', 'categ', 'categs']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: mercaderias, impto, unico, categ",
    ),
```

### 172. `cta_part`
- **Tipo**: revenue
- **Keywords**: cta, part, rafael, abad, garcia
- **Prioridad sugerida**: 1770
- **Confianza**: 0.3
- **Cuentas afectadas**: ~6
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="cta_part",
        priority=1770,
        required_keywords=[['ctá', 'ctas', 'cta'], ['part', 'párt', 'parts'], ['rafaels', 'rafael', 'rafaél', 'ráfáel'], ['ábád', 'abad', 'abads'], ['garcía', 'gárciá', 'garcia', 'garcias']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: cta, part, rafael, abad, garcia",
    ),
```

### 173. `plazo_deposito`
- **Tipo**: revenue
- **Keywords**: plazo, deposito
- **Prioridad sugerida**: 1780
- **Confianza**: 0.3
- **Cuentas afectadas**: ~6
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="plazo_deposito",
        priority=1780,
        required_keywords=[['plazos', 'plazo', 'plazó', 'plázo'], ['depósitó', 'deposito', 'depositos', 'déposito', 'deposíto']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: plazo, deposito",
    ),
```

### 174. `sondajes`
- **Tipo**: revenue
- **Keywords**: sondajes
- **Prioridad sugerida**: 1790
- **Confianza**: 0.3
- **Cuentas afectadas**: ~6
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="sondajes",
        priority=1790,
        required_keywords=[['sondájes', 'sondaje', 'sondajés', 'sóndajes', 'sondajes']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: sondajes",
    ),
```

### 175. `plantacion_desinfeccion`
- **Tipo**: revenue
- **Keywords**: plantacion, desinfeccion, raices, futuro
- **Prioridad sugerida**: 1800
- **Confianza**: 0.3
- **Cuentas afectadas**: ~6
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="plantacion_desinfeccion",
        priority=1800,
        required_keywords=[['plantacíon', 'plantacion', 'plantacions', 'plántácion', 'plantación'], ['desinfeccions', 'désinféccion', 'desinfeccion', 'desínfeccíon', 'desinfección'], ['raice', 'raicés', 'raices', 'ráices', 'raíces'], ['fútúro', 'futuros', 'futuró', 'futuro']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: plantacion, desinfeccion, raices, futuro",
    ),
```

### 176. `maderera_alto`
- **Tipo**: revenue
- **Keywords**: maderera, alto, lonquen, ltda, plantacion
- **Prioridad sugerida**: 1810
- **Confianza**: 0.3
- **Cuentas afectadas**: ~6
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="maderera_alto",
        priority=1810,
        required_keywords=[['madéréra', 'mádererá', 'madereras', 'maderera'], ['altó', 'álto', 'altos', 'alto'], ['lónquen', 'lonqúen', 'lonquén', 'lonquens', 'lonquen'], ['ltda', 'ltdas', 'ltdá'], ['plantacíon', 'plantacion', 'plantacions', 'plántácion', 'plantación']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: maderera, alto, lonquen, ltda, plantacion",
    ),
```

### 177. `plantacion_eliecer`
- **Tipo**: expense
- **Keywords**: plantacion, eliecer, carmen, perez
- **Prioridad sugerida**: 1820
- **Confianza**: 0.3
- **Cuentas afectadas**: ~6
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="plantacion_eliecer",
        priority=1820,
        required_keywords=[['plantacíon', 'plantacion', 'plantacions', 'plántácion', 'plantación'], ['eliecers', 'éliécér', 'elíecer', 'eliecer'], ['carmen', 'carmens', 'carmén', 'cármen'], ['perez', 'péréz', 'perezs']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: plantacion, eliecer, carmen, perez",
    ),
```

### 178. `capital_social`
- **Tipo**: revenue
- **Keywords**: capital, social, terrenos, 359, 764
- **Prioridad sugerida**: 1830
- **Confianza**: 0.3
- **Cuentas afectadas**: ~6
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="capital_social",
        priority=1830,
        required_keywords=[['capitals', 'capítal', 'cápitál', 'capital'], ['sócial', 'socials', 'sociál', 'social', 'socíal'], ['terreno', 'terrenos', 'térrénos', 'terrenós'], ['359', '359s'], ['764s', '764']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: capital, social, terrenos, 359, 764",
    ),
```

### 179. `agregados_arados`
- **Tipo**: revenue
- **Keywords**: agregados, arados, into, oonononannoroso, 65242484
- **Prioridad sugerida**: 1840
- **Confianza**: 0.3
- **Cuentas afectadas**: ~6
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="agregados_arados",
        priority=1840,
        required_keywords=[['agrégados', 'agregadós', 'agregados', 'ágregádos', 'agregado'], ['árádos', 'arados', 'arado', 'aradós'], ['intó', 'intos', 'into', 'ínto'], ['oonononánnoroso', 'oonononannorosos', 'oonononannoroso', 'óónónónannórósó'], ['65242484s', '65242484']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: agregados, arados, into, oonononannoroso, 65242484",
    ),
```

### 180. `jahuel_aguas`
- **Tipo**: revenue
- **Keywords**: jahuel, aguas
- **Prioridad sugerida**: 1850
- **Confianza**: 0.3
- **Cuentas afectadas**: ~6
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="jahuel_aguas",
        priority=1850,
        required_keywords=[['jahuels', 'jahuel', 'jahúel', 'jáhuel', 'jahuél'], ['agúas', 'águás', 'aguas', 'agua']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: jahuel, aguas",
    ),
```

### 181. `diciembre_2018`
- **Tipo**: revenue
- **Keywords**: diciembre, 2018, a131
- **Prioridad sugerida**: 1860
- **Confianza**: 0.3
- **Cuentas afectadas**: ~6
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="diciembre_2018",
        priority=1860,
        required_keywords=[['diciembres', 'diciémbré', 'diciembre', 'dícíembre'], ['2018', '2018s'], ['a131s', 'a131', 'á131']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: diciembre, 2018, a131",
    ),
```

### 182. `prestamos_terceros`
- **Tipo**: revenue
- **Keywords**: prestamos, terceros, caja, compensacion
- **Prioridad sugerida**: 1870
- **Confianza**: 0.3
- **Cuentas afectadas**: ~6
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="prestamos_terceros",
        priority=1870,
        required_keywords=[['prestamós', 'prestamos', 'prestámos', 'prestamo', 'préstamos'], ['tercerós', 'tércéros', 'tercero', 'terceros'], ['cájá', 'cajas', 'caja'], ['compensácion', 'compensacion', 'compensacíon', 'compensacions', 'cómpensación', 'compénsacion']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: prestamos, terceros, caja, compensacion",
    ),
```

### 183. `dep_acum`
- **Tipo**: expense
- **Keywords**: dep, acum, thompson, crimson, thompsom
- **Prioridad sugerida**: 1880
- **Confianza**: 0.3
- **Cuentas afectadas**: ~6
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="dep_acum",
        priority=1880,
        required_keywords=[['deps', 'dép', 'dep'], ['acums', 'ácum', 'acúm', 'acum'], ['thompson', 'thompsons', 'thómpsón'], ['crímson', 'crimsons', 'crimson', 'crimsón'], ['thómpsóm', 'thompsom', 'thompsoms']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: dep, acum, thompson, crimson, thompsom",
    ),
```

### 184. `dep_acum`
- **Tipo**: expense
- **Keywords**: dep, acum, red, globe
- **Prioridad sugerida**: 1890
- **Confianza**: 0.3
- **Cuentas afectadas**: ~6
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="dep_acum",
        priority=1890,
        required_keywords=[['deps', 'dép', 'dep'], ['acums', 'ácum', 'acúm', 'acum'], ['réd', 'reds', 'red'], ['globé', 'globe', 'globes', 'glóbe']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: dep, acum, red, globe",
    ),
```

### 185. `resultados_ejercicios`
- **Tipo**: expense
- **Keywords**: resultados, ejercicios, resultado
- **Prioridad sugerida**: 1900
- **Confianza**: 0.3
- **Cuentas afectadas**: ~6
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="resultados_ejercicios",
        priority=1900,
        required_keywords=[['resultadós', 'résultados', 'resultado', 'resultados', 'resultádos', 'resúltados'], ['ejercícíos', 'ejercicios', 'éjércicios', 'ejerciciós', 'ejercicio'], ['resultádo', 'resultadó', 'résultado', 'resultado', 'resultados', 'resúltado']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: resultados, ejercicios, resultado",
    ),
```

### 186. `ejercicio_anterior`
- **Tipo**: revenue
- **Keywords**: ejercicio, anterior, negativo
- **Prioridad sugerida**: 1910
- **Confianza**: 0.3
- **Cuentas afectadas**: ~6
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="ejercicio_anterior",
        priority=1910,
        required_keywords=[['éjércicio', 'ejercicios', 'ejercició', 'ejercícío', 'ejercicio'], ['ánterior', 'antérior', 'anterior', 'anteríor', 'anteriór', 'anteriors'], ['negátivo', 'négativo', 'negativo', 'negativó', 'negativos', 'negatívo']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: ejercicio, anterior, negativo",
    ),
```

### 187. `anticipo_sueldos`
- **Tipo**: expense
- **Keywords**: anticipo, sueldos, exceso, sulldos
- **Prioridad sugerida**: 1920
- **Confianza**: 0.3
- **Cuentas afectadas**: ~6
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="anticipo_sueldos",
        priority=1920,
        required_keywords=[['antícípo', 'anticipó', 'ánticipo', 'anticipos', 'anticipo'], ['sueldos', 'sueldo', 'sueldós', 'súeldos', 'suéldos'], ['excesó', 'exceso', 'excesos', 'éxcéso'], ['súlldos', 'sulldós', 'sulldos', 'sulldo']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: anticipo, sueldos, exceso, sulldos",
    ),
```

### 188. `actualizacion_unidad`
- **Tipo**: revenue
- **Keywords**: actualizacion, unidad
- **Prioridad sugerida**: 1930
- **Confianza**: 0.3
- **Cuentas afectadas**: ~6
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="actualizacion_unidad",
        priority=1930,
        required_keywords=[['actualízacíon', 'actualización', 'áctuálizácion', 'actualizacion', 'actúalizacion', 'actualizacions'], ['unidads', 'unidád', 'unidad', 'únidad', 'unídad']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: actualizacion, unidad",
    ),
```

### 189. `oscar_prohens`
- **Tipo**: revenue
- **Keywords**: oscar, prohens, espinosa, pagina
- **Prioridad sugerida**: 1940
- **Confianza**: 0.3
- **Cuentas afectadas**: ~6
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="oscar_prohens",
        priority=1940,
        required_keywords=[['oscar', 'oscars', 'óscar', 'oscár'], ['prohen', 'prohens', 'prohéns', 'próhens'], ['espínosa', 'espinosá', 'éspinosa', 'espinosas', 'espinósa', 'espinosa'], ['pagina', 'paginas', 'pagína', 'páginá']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: oscar, prohens, espinosa, pagina",
    ),
```

### 190. `suministros_colacion`
- **Tipo**: expense
- **Keywords**: suministros, colacion, otros, ali
- **Prioridad sugerida**: 1950
- **Confianza**: 0.3
- **Cuentas afectadas**: ~6
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="suministros_colacion",
        priority=1950,
        required_keywords=[['sumínístros', 'suministrós', 'suministros', 'suministro', 'súministros'], ['colácion', 'colacion', 'colacíon', 'colacions', 'cólación'], ['ótrós', 'otros', 'otro'], ['ali', 'áli', 'alí', 'alis']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: suministros, colacion, otros, ali",
    ),
```

### 191. `herbicidas_fungicidas`
- **Tipo**: expense
- **Keywords**: herbicidas, fungicidas, pesticida
- **Prioridad sugerida**: 1960
- **Confianza**: 0.3
- **Cuentas afectadas**: ~6
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="herbicidas_fungicidas",
        priority=1960,
        required_keywords=[['herbicida', 'herbícídas', 'herbicidás', 'hérbicidas', 'herbicidas'], ['fungicida', 'fúngicidas', 'fungicidás', 'fungicidas', 'fungícídas'], ['pestícída', 'pésticida', 'pesticida', 'pesticidas', 'pesticidá']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: herbicidas, fungicidas, pesticida",
    ),
```

### 192. `electrica_energia`
- **Tipo**: expense
- **Keywords**: electrica, energia, unurgia
- **Prioridad sugerida**: 1970
- **Confianza**: 0.3
- **Cuentas afectadas**: ~6
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="electrica_energia",
        priority=1970,
        required_keywords=[['electricas', 'electrica', 'éléctrica', 'electríca', 'electricá'], ['energiá', 'énérgia', 'energia', 'energias', 'energía'], ['unurgiá', 'únúrgia', 'unurgias', 'unurgia', 'unurgía']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: electrica, energia, unurgia",
    ),
```

### 193. `escritorio_utiles`
- **Tipo**: expense
- **Keywords**: escritorio, utiles, gtos
- **Prioridad sugerida**: 1980
- **Confianza**: 0.3
- **Cuentas afectadas**: ~6
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="escritorio_utiles",
        priority=1980,
        required_keywords=[['escritórió', 'escrítorío', 'éscritorio', 'escritorios', 'escritorio'], ['utíles', 'utile', 'utiles', 'útiles', 'utilés'], ['gto', 'gtos', 'gtós']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: escritorio, utiles, gtos",
    ),
```

### 194. `horas_extras`
- **Tipo**: revenue
- **Keywords**: horas, extras
- **Prioridad sugerida**: 1990
- **Confianza**: 0.3
- **Cuentas afectadas**: ~6
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="horas_extras",
        priority=1990,
        required_keywords=[['hora', 'hóras', 'horás', 'horas'], ['éxtras', 'extra', 'extras', 'extrás']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: horas, extras",
    ),
```

### 195. `pagare_ltda`
- **Tipo**: expense
- **Keywords**: pagare, ltda, maravilla, inv, inversiones
- **Prioridad sugerida**: 2000
- **Confianza**: 0.3
- **Cuentas afectadas**: ~6
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="pagare_ltda",
        priority=2000,
        required_keywords=[['pagares', 'pagaré', 'págáre', 'pagare'], ['ltda', 'ltdas', 'ltdá'], ['márávillá', 'maravillas', 'maravílla', 'maravilla'], ['invs', 'inv', 'ínv'], ['inversiones', 'inversiónes', 'ínversíones', 'inversione', 'invérsionés']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: pagare, ltda, maravilla, inv, inversiones",
    ),
```

### 196. `gastos_cosecha`
- **Tipo**: revenue
- **Keywords**: gastos, cosecha, 50830reasignacion, vendimia
- **Prioridad sugerida**: 2010
- **Confianza**: 0.3
- **Cuentas afectadas**: ~6
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="gastos_cosecha",
        priority=2010,
        required_keywords=[['gasto', 'gastos', 'gastós', 'gástos'], ['cosechas', 'cosecha', 'cósecha', 'cosechá', 'cosécha'], ['50830reásignácion', '50830reasígnacíon', '50830reasignacions', '50830reasignacion', '50830réasignacion', '50830reasignación'], ['véndimia', 'vendimias', 'vendímía', 'vendimiá', 'vendimia']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: gastos, cosecha, 50830reasignacion, vendimia",
    ),
```

### 197. `deudas_recuperadas`
- **Tipo**: revenue
- **Keywords**: deudas, recuperadas
- **Prioridad sugerida**: 2020
- **Confianza**: 0.3
- **Cuentas afectadas**: ~5
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="deudas_recuperadas",
        priority=2020,
        required_keywords=[['déudas', 'deúdas', 'deuda', 'deudas', 'deudás'], ['recuperádás', 'recuperada', 'recuperadas', 'récupéradas', 'recúperadas']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: deudas, recuperadas",
    ),
```

### 198. `legales_gastos`
- **Tipo**: expense
- **Keywords**: legales, gastos, resery, reservas
- **Prioridad sugerida**: 2030
- **Confianza**: 0.3
- **Cuentas afectadas**: ~5
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="legales_gastos",
        priority=2030,
        required_keywords=[['legale', 'légalés', 'legáles', 'legales'], ['gasto', 'gastos', 'gastós', 'gástos'], ['resery', 'réséry', 'reserys'], ['reservas', 'résérvas', 'reservás', 'reserva']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: legales, gastos, resery, reservas",
    ),
```

### 199. `publicidad_difusion`
- **Tipo**: revenue
- **Keywords**: publicidad, difusion, 279, 997
- **Prioridad sugerida**: 2040
- **Confianza**: 0.3
- **Cuentas afectadas**: ~5
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="publicidad_difusion",
        priority=2040,
        required_keywords=[['publicidád', 'públicidad', 'publícídad', 'publicidad', 'publicidads'], ['difusion', 'dífusíon', 'difúsion', 'difusions', 'difusión'], ['279s', '279'], ['997s', '997']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: publicidad, difusion, 279, 997",
    ),
```

### 200. `ingresos_ordinarios`
- **Tipo**: revenue
- **Keywords**: ingresos, ordinarios, intereses, moratorios
- **Prioridad sugerida**: 2050
- **Confianza**: 0.3
- **Cuentas afectadas**: ~5
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="ingresos_ordinarios",
        priority=2050,
        required_keywords=[['ingreso', 'ingrésos', 'ingresos', 'íngresos', 'ingresós'], ['ordinario', 'ordinarios', 'ordínaríos', 'ordinários', 'órdinariós'], ['íntereses', 'intérésés', 'intereses', 'interese'], ['moratorios', 'móratóriós', 'moratoríos', 'moratorio', 'morátorios']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: ingresos, ordinarios, intereses, moratorios",
    ),
```

### 201. `provision_impto`
- **Tipo**: revenue
- **Keywords**: provision, impto, gasto, importacion
- **Prioridad sugerida**: 2060
- **Confianza**: 0.3
- **Cuentas afectadas**: ~5
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="provision_impto",
        priority=2060,
        required_keywords=[['provísíon', 'provisions', 'provision', 'próvisión'], ['imptos', 'imptó', 'ímpto', 'impto'], ['gastó', 'gasto', 'gásto', 'gastos'], ['importacions', 'impórtación', 'importácion', 'ímportacíon', 'importacion']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: provision, impto, gasto, importacion",
    ),
```

### 202. `activo_inmovilizado`
- **Tipo**: expense
- **Keywords**: activo, inmovilizado, depreciacion, 50901, 2000
- **Prioridad sugerida**: 2070
- **Confianza**: 0.3
- **Cuentas afectadas**: ~5
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="activo_inmovilizado",
        priority=2070,
        required_keywords=[['áctivo', 'activó', 'actívo', 'activo', 'activos'], ['inmóvilizadó', 'inmovilizado', 'inmovilizádo', 'inmovilizados', 'ínmovílízado'], ['dépréciacion', 'deprecíacíon', 'depreciacions', 'depreciácion', 'depreciacion', 'depreciación'], ['50901s', '50901'], ['2000s', '2000']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: activo, inmovilizado, depreciacion, 50901, 2000",
    ),
```

### 203. `252_700`
- **Tipo**: revenue
- **Keywords**: 252, 700, pag
- **Prioridad sugerida**: 2080
- **Confianza**: 0.3
- **Cuentas afectadas**: ~5
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="252_700",
        priority=2080,
        required_keywords=[['252', '252s'], ['700', '700s'], ['pags', 'pag', 'pág']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: 252, 700, pag",
    ),
```

### 204. `resultados_acumulados`
- **Tipo**: expense
- **Keywords**: resultados, acumulados, 218, 029
- **Prioridad sugerida**: 2090
- **Confianza**: 0.3
- **Cuentas afectadas**: ~5
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="resultados_acumulados",
        priority=2090,
        required_keywords=[['resultadós', 'résultados', 'resultado', 'resultados', 'resultádos', 'resúltados'], ['ácumuládos', 'acúmúlados', 'acumulado', 'acumulados', 'acumuladós'], ['218s', '218'], ['029', '029s']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: resultados, acumulados, 218, 029",
    ),
```

### 205. `spa_plantacion`
- **Tipo**: revenue
- **Keywords**: spa, plantacion, fertilizante, futuro, agro
- **Prioridad sugerida**: 2100
- **Confianza**: 0.3
- **Cuentas afectadas**: ~5
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="spa_plantacion",
        priority=2100,
        required_keywords=[['spa', 'spas', 'spá'], ['plantacíon', 'plantacion', 'plantacions', 'plántácion', 'plantación'], ['fertilizante', 'fertílízante', 'fertilizánte', 'fértilizanté', 'fertilizantes'], ['fútúro', 'futuros', 'futuró', 'futuro'], ['agros', 'agró', 'agro', 'ágro']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: spa, plantacion, fertilizante, futuro, agro",
    ),
```

### 206. `tractores_maldonado`
- **Tipo**: revenue
- **Keywords**: tractores, maldonado, plantacion
- **Prioridad sugerida**: 2110
- **Confianza**: 0.3
- **Cuentas afectadas**: ~5
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="tractores_maldonado",
        priority=2110,
        required_keywords=[['tráctores', 'tractore', 'tractores', 'tractóres', 'tractorés'], ['maldonados', 'maldonado', 'maldónadó', 'máldonádo'], ['plantacíon', 'plantacion', 'plantacions', 'plántácion', 'plantación']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: tractores, maldonado, plantacion",
    ),
```

### 207. `cta_cte`
- **Tipo**: revenue
- **Keywords**: cta, cte, garcia
- **Prioridad sugerida**: 2120
- **Confianza**: 0.3
- **Cuentas afectadas**: ~5
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="cta_cte",
        priority=2120,
        required_keywords=[['ctá', 'ctas', 'cta'], ['cte', 'ctes', 'cté'], ['garcía', 'gárciá', 'garcia', 'garcias']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: cta, cte, garcia",
    ),
```

### 208. `arriendos_pagados`
- **Tipo**: revenue
- **Keywords**: arriendos, pagados, leasing, anticipa
- **Prioridad sugerida**: 2130
- **Confianza**: 0.3
- **Cuentas afectadas**: ~5
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="arriendos_pagados",
        priority=2130,
        required_keywords=[['árriendos', 'arriendos', 'arriendós', 'arriéndos', 'arriendo', 'arríendos'], ['pagados', 'pagadós', 'pagado', 'págádos'], ['leasíng', 'léasing', 'leasing', 'leasings', 'leásing'], ['anticipa', 'ánticipá', 'antícípa', 'anticipas']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: arriendos, pagados, leasing, anticipa",
    ),
```

### 209. `desahucio_50090indemnizacion`
- **Tipo**: expense
- **Keywords**: desahucio, 50090indemnizacion, otros, honorarios, insumos
- **Prioridad sugerida**: 2140
- **Confianza**: 0.3
- **Cuentas afectadas**: ~5
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="desahucio_50090indemnizacion",
        priority=2140,
        required_keywords=[['desahucio', 'desahució', 'désahucio', 'desahucío', 'desáhucio', 'desahúcio', 'desahucios'], ['50090indemnización', '50090índemnízacíon', '50090indemnizacion', '50090indémnizacion', '50090indemnizácion', '50090indemnizacions'], ['ótrós', 'otros', 'otro'], ['honorários', 'honoraríos', 'honorario', 'hónórariós', 'honorarios'], ['insumo', 'insumos', 'ínsumos', 'insúmos', 'insumós']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: desahucio, 50090indemnizacion, otros, honorarios, insumos",
    ),
```

### 210. `oficinas_subcontratacion`
- **Tipo**: expense
- **Keywords**: oficinas, subcontratacion, externas, 10112
- **Prioridad sugerida**: 2150
- **Confianza**: 0.3
- **Cuentas afectadas**: ~5
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="oficinas_subcontratacion",
        priority=2150,
        required_keywords=[['oficina', 'oficinas', 'ofícínas', 'oficinás', 'óficinas'], ['subcontratacion', 'subcontrátácion', 'subcontratacions', 'súbcontratacion', 'subcóntratación', 'subcontratacíon'], ['externas', 'éxtérnas', 'externa', 'externás'], ['10112', '10112s']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: oficinas, subcontratacion, externas, 10112",
    ),
```

### 211. `categoria_imuesto`
- **Tipo**: expense
- **Keywords**: categoria, imuesto
- **Prioridad sugerida**: 2160
- **Confianza**: 0.3
- **Cuentas afectadas**: ~5
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="categoria_imuesto",
        priority=2160,
        required_keywords=[['categoría', 'catégoria', 'categoria', 'cátegoriá', 'categorias', 'categória'], ['imuesto', 'imuestos', 'imuésto', 'ímuesto', 'imúesto', 'imuestó']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: categoria, imuesto",
    ),
```

### 212. `siembras_siembra`
- **Tipo**: expense
- **Keywords**: siembras, siembra, maiz, semillas
- **Prioridad sugerida**: 2170
- **Confianza**: 0.3
- **Cuentas afectadas**: ~5
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="siembras_siembra",
        priority=2170,
        required_keywords=[['siémbras', 'síembras', 'siembrás', 'siembras', 'siembra'], ['siembrá', 'siembras', 'siembra', 'síembra', 'siémbra'], ['maíz', 'maizs', 'maiz', 'máiz'], ['semillas', 'semillás', 'sémillas', 'semíllas', 'semilla']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: siembras, siembra, maiz, semillas",
    ),
```

### 213. `pagina_altosa`
- **Tipo**: revenue
- **Keywords**: pagina, altosa, lotal
- **Prioridad sugerida**: 2180
- **Confianza**: 0.3
- **Cuentas afectadas**: ~5
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="pagina_altosa",
        priority=2180,
        required_keywords=[['pagina', 'paginas', 'pagína', 'páginá'], ['áltosá', 'altósa', 'altosa', 'altosas'], ['lotals', 'lótal', 'lotál', 'lotal']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: pagina, altosa, lotal",
    ),
```

### 214. `114_959`
- **Tipo**: revenue
- **Keywords**: 114, 959, pagina
- **Prioridad sugerida**: 2190
- **Confianza**: 0.3
- **Cuentas afectadas**: ~5
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="114_959",
        priority=2190,
        required_keywords=[['114', '114s'], ['959s', '959'], ['pagina', 'paginas', 'pagína', 'páginá']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: 114, 959, pagina",
    ),
```

### 215. `gas_licuado`
- **Tipo**: expense
- **Keywords**: gas, licuado
- **Prioridad sugerida**: 2200
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="gas_licuado",
        priority=2200,
        required_keywords=[['ga', 'gas', 'gás'], ['licuádo', 'lícuado', 'licuado', 'licúado', 'licuadó', 'licuados']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: gas, licuado",
    ),
```

### 216. `peajes_127`
- **Tipo**: expense
- **Keywords**: peajes, 127, 329
- **Prioridad sugerida**: 2210
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="peajes_127",
        priority=2210,
        required_keywords=[['péajés', 'peajes', 'peaje', 'peájes'], ['127', '127s'], ['329s', '329']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: peajes, 127, 329",
    ),
```

### 217. `tipo_cambio`
- **Tipo**: revenue
- **Keywords**: tipo, cambio, 30490difererencia
- **Prioridad sugerida**: 2220
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="tipo_cambio",
        priority=2220,
        required_keywords=[['típo', 'tipo', 'tipó', 'tipos'], ['cambió', 'cambio', 'cambios', 'cámbio', 'cambío'], ['30490difererencias', '30490difererencia', '30490difererenciá', '30490diféréréncia', '30490dífererencía']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: tipo, cambio, 30490difererencia",
    ),
```

### 218. `deferred_taxes`
- **Tipo**: expense
- **Keywords**: deferred, taxes, reserves, 461
- **Prioridad sugerida**: 2230
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="deferred_taxes",
        priority=2230,
        required_keywords=[['déférréd', 'deferreds', 'deferred'], ['taxés', 'taxes', 'táxes', 'taxe'], ['reserves', 'résérvés', 'reserve'], ['461s', '461']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: deferred, taxes, reserves, 461",
    ),
```

### 219. `cash_term`
- **Tipo**: expense
- **Keywords**: cash, term, debt, and
- **Prioridad sugerida**: 2240
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="cash_term",
        priority=2240,
        required_keywords=[['cash', 'cashs', 'cásh'], ['térm', 'terms', 'term'], ['débt', 'debts', 'debt'], ['and', 'ands', 'ánd']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: cash, term, debt, and",
    ),
```

### 220. `comisiones_pagar`
- **Tipo**: revenue
- **Keywords**: comisiones, pagar, cuentas, cobrar
- **Prioridad sugerida**: 2250
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="comisiones_pagar",
        priority=2250,
        required_keywords=[['comisiones', 'comísíones', 'comisionés', 'cómisiónes', 'comisione'], ['pagar', 'págár', 'pagars'], ['cuentás', 'cuenta', 'cuéntas', 'cuentas', 'cúentas'], ['cóbrar', 'cobrár', 'cobrars', 'cobrar']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: comisiones, pagar, cuentas, cobrar",
    ),
```

### 221. `otras_retenciones`
- **Tipo**: expense
- **Keywords**: otras, retenciones, personal, acciones
- **Prioridad sugerida**: 2260
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="otras_retenciones",
        priority=2260,
        required_keywords=[['otras', 'ótras', 'otra', 'otrás'], ['retencione', 'retenciones', 'retenciónes', 'retencíones', 'réténcionés'], ['pérsonal', 'personal', 'persónal', 'personál', 'personals'], ['ácciones', 'acciónes', 'accione', 'accíones', 'acciones', 'accionés']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: otras, retenciones, personal, acciones",
    ),
```

### 222. `gastos_informatica`
- **Tipo**: expense
- **Keywords**: gastos, informatica, fotocopia
- **Prioridad sugerida**: 2270
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="gastos_informatica",
        priority=2270,
        required_keywords=[['gasto', 'gastos', 'gastós', 'gástos'], ['informatica', 'informáticá', 'infórmatica', 'ínformatíca', 'informaticas'], ['fotocopias', 'fotocopía', 'fótócópia', 'fotocopia', 'fotocopiá']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: gastos, informatica, fotocopia",
    ),
```

### 223. `corp_banca`
- **Tipo**: revenue
- **Keywords**: corp, banca, angeles, cuentas
- **Prioridad sugerida**: 2280
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="corp_banca",
        priority=2280,
        required_keywords=[['córp', 'corp', 'corps'], ['báncá', 'bancas', 'banca'], ['angélés', 'angele', 'ángeles', 'angeles'], ['cuentás', 'cuenta', 'cuéntas', 'cuentas', 'cúentas']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: corp, banca, angeles, cuentas",
    ),
```

### 224. `plantaciones_agricolas`
- **Tipo**: expense
- **Keywords**: plantaciones, agricolas, com
- **Prioridad sugerida**: 2290
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="plantaciones_agricolas",
        priority=2290,
        required_keywords=[['plantaciónes', 'plantacionés', 'plántáciones', 'plantacione', 'plantacíones', 'plantaciones'], ['ágricolás', 'agricólas', 'agricola', 'agrícolas', 'agricolas'], ['com', 'cóm', 'coms']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: plantaciones, agricolas, com",
    ),
```

### 225. `vehiculos_motorizados`
- **Tipo**: expense
- **Keywords**: vehiculos, motorizados, 12301, 12503
- **Prioridad sugerida**: 2300
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="vehiculos_motorizados",
        priority=2300,
        required_keywords=[['vehiculos', 'vehiculo', 'véhiculos', 'vehiculós', 'vehículos', 'vehicúlos'], ['motorizado', 'motorízados', 'mótórizadós', 'motorizádos', 'motorizados'], ['12301s', '12301'], ['12503s', '12503']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: vehiculos, motorizados, 12301, 12503",
    ),
```

### 226. `tributaria_inversiones`
- **Tipo**: revenue
- **Keywords**: tributaria, inversiones
- **Prioridad sugerida**: 2310
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="tributaria_inversiones",
        priority=2310,
        required_keywords=[['tríbutaría', 'tributáriá', 'tributaria', 'tributarias', 'tribútaria'], ['inversiones', 'inversiónes', 'ínversíones', 'inversione', 'invérsionés']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: tributaria, inversiones",
    ),
```

### 227. `20901_imptos`
- **Tipo**: revenue
- **Keywords**: 20901, imptos, diferidos, pasivo
- **Prioridad sugerida**: 2320
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="20901_imptos",
        priority=2320,
        required_keywords=[['20901', '20901s'], ['imptos', 'imptós', 'ímptos', 'impto'], ['diferidos', 'díferídos', 'diferidós', 'diferido', 'diféridos'], ['pasivó', 'pasivos', 'pásivo', 'pasívo', 'pasivo']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: 20901, imptos, diferidos, pasivo",
    ),
```

### 228. `alto_lote`
- **Tipo**: expense
- **Keywords**: alto, lote, nupangue
- **Prioridad sugerida**: 2330
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="alto_lote",
        priority=2330,
        required_keywords=[['altó', 'álto', 'altos', 'alto'], ['lóte', 'lote', 'loté', 'lotes'], ['nupangue', 'nupangué', 'nupángue', 'nupangues', 'núpangúe']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: alto, lote, nupangue",
    ),
```

### 229. `saldo_inicial`
- **Tipo**: revenue
- **Keywords**: saldo, inicial
- **Prioridad sugerida**: 2340
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="saldo_inicial",
        priority=2340,
        required_keywords=[['saldos', 'sáldo', 'saldó', 'saldo'], ['ínícíal', 'iniciál', 'inicial', 'inicials']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: saldo, inicial",
    ),
```

### 230. `2020_activo`
- **Tipo**: revenue
- **Keywords**: 2020, activo, fijo, ifrs
- **Prioridad sugerida**: 2350
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="2020_activo",
        priority=2350,
        required_keywords=[['2020s', '2020'], ['áctivo', 'activó', 'actívo', 'activo', 'activos'], ['fijó', 'fijos', 'fíjo', 'fijo'], ['ífrs', 'ifr', 'ifrs']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: 2020, activo, fijo, ifrs",
    ),
```

### 231. `magdalena_diaz`
- **Tipo**: revenue
- **Keywords**: magdalena, diaz, ramirez, plantacion
- **Prioridad sugerida**: 2360
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="magdalena_diaz",
        priority=2360,
        required_keywords=[['mágdálená', 'magdaléna', 'magdalena', 'magdalenas'], ['díaz', 'diazs', 'diáz', 'diaz'], ['rámirez', 'ramirez', 'ramiréz', 'ramírez', 'ramirezs'], ['plantacíon', 'plantacion', 'plantacions', 'plántácion', 'plantación']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: magdalena, diaz, ramirez, plantacion",
    ),
```

### 232. `agroinsumos_plantacion`
- **Tipo**: revenue
- **Keywords**: agroinsumos, plantacion, fertilizante
- **Prioridad sugerida**: 2370
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="agroinsumos_plantacion",
        priority=2370,
        required_keywords=[['agroinsúmos', 'agroinsumos', 'ágroinsumos', 'agróinsumós', 'agroínsumos', 'agroinsumo'], ['plantacíon', 'plantacion', 'plantacions', 'plántácion', 'plantación'], ['fertilizante', 'fertílízante', 'fertilizánte', 'fértilizanté', 'fertilizantes']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: agroinsumos, plantacion, fertilizante",
    ),
```

### 233. `valdivieso`
- **Tipo**: revenue
- **Keywords**: valdivieso
- **Prioridad sugerida**: 2380
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="valdivieso",
        priority=2380,
        required_keywords=[['valdivieso', 'valdívíeso', 'valdiviesó', 'valdiviesos', 'valdiviéso', 'váldivieso']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: valdivieso",
    ),
```

### 234. `mendoza_2020`
- **Tipo**: revenue
- **Keywords**: mendoza, 2020
- **Prioridad sugerida**: 2390
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="mendoza_2020",
        priority=2390,
        required_keywords=[['mendozas', 'mendoza', 'méndoza', 'mendozá', 'mendóza'], ['2020s', '2020']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: mendoza, 2020",
    ),
```

### 235. `2020`
- **Tipo**: revenue
- **Keywords**: 2020
- **Prioridad sugerida**: 2400
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="2020",
        priority=2400,
        required_keywords=[['2020s', '2020']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: 2020",
    ),
```

### 236. `tarjeta_instituciones`
- **Tipo**: revenue
- **Keywords**: tarjeta, instituciones, prevision
- **Prioridad sugerida**: 2410
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="tarjeta_instituciones",
        priority=2410,
        required_keywords=[['tárjetá', 'tarjetas', 'tarjéta', 'tarjeta'], ['instituciones', 'institucione', 'institúciones', 'institucionés', 'ínstítucíones', 'instituciónes'], ['prevísíon', 'previsions', 'prévision', 'prevision', 'previsión']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: tarjeta, instituciones, prevision",
    ),
```

### 237. `aporte_soc`
- **Tipo**: revenue
- **Keywords**: aporte, soc, transp, libardom
- **Prioridad sugerida**: 2420
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="aporte_soc",
        priority=2420,
        required_keywords=[['aporte', 'áporte', 'aporté', 'apórte', 'aportes'], ['sóc', 'soc', 'socs'], ['transp', 'tránsp', 'transps'], ['libardóm', 'libárdom', 'líbardom', 'libardoms', 'libardom']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: aporte, soc, transp, libardom",
    ),
```

### 238. `sanidad_ambiental`
- **Tipo**: revenue
- **Keywords**: sanidad, ambiental, servicio, serv
- **Prioridad sugerida**: 2430
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="sanidad_ambiental",
        priority=2430,
        required_keywords=[['sanidads', 'sanídad', 'sánidád', 'sanidad'], ['ambiéntal', 'ambientals', 'ámbientál', 'ambiental', 'ambíental'], ['servicio', 'servicios', 'servícío', 'servició', 'sérvicio'], ['servs', 'sérv', 'serv']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: sanidad, ambiental, servicio, serv",
    ),
```

### 239. `cuentas_cobrar`
- **Tipo**: revenue
- **Keywords**: cuentas, cobrar, pasivo, circulante
- **Prioridad sugerida**: 2440
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="cuentas_cobrar",
        priority=2440,
        required_keywords=[['cuentás', 'cuenta', 'cuéntas', 'cuentas', 'cúentas'], ['cóbrar', 'cobrár', 'cobrars', 'cobrar'], ['pasivó', 'pasivos', 'pásivo', 'pasívo', 'pasivo'], ['círculante', 'circulanté', 'circulantes', 'circúlante', 'circulánte', 'circulante']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: cuentas, cobrar, pasivo, circulante",
    ),
```

### 240. `imponible_capital`
- **Tipo**: revenue
- **Keywords**: imponible, capital, propio, renta, liquida
- **Prioridad sugerida**: 2450
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="imponible_capital",
        priority=2450,
        required_keywords=[['ímponíble', 'imponible', 'imponibles', 'impónible', 'imponiblé'], ['capitals', 'capítal', 'cápitál', 'capital'], ['propio', 'propío', 'própió', 'propios'], ['rentá', 'rentas', 'rénta', 'renta'], ['liquida', 'liqúida', 'liquidas', 'líquída', 'liquidá']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: imponible, capital, propio, renta, liquida",
    ),
```

### 241. `138_pagar`
- **Tipo**: revenue
- **Keywords**: 138, pagar, impuestos, tarjeta
- **Prioridad sugerida**: 2460
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="138_pagar",
        priority=2460,
        required_keywords=[['138s', '138'], ['pagar', 'págár', 'pagars'], ['ímpuestos', 'impuestós', 'impuéstos', 'impuesto', 'impuestos', 'impúestos'], ['tárjetá', 'tarjetas', 'tarjéta', 'tarjeta']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: 138, pagar, impuestos, tarjeta",
    ),
```

### 242. `crecimiento_reguladores`
- **Tipo**: expense
- **Keywords**: crecimiento, reguladores, parrones
- **Prioridad sugerida**: 2470
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="crecimiento_reguladores",
        priority=2470,
        required_keywords=[['crecimiento', 'crecimientos', 'crécimiénto', 'crecimientó', 'crecímíento'], ['regúladores', 'réguladorés', 'reguladóres', 'reguladore', 'reguládores', 'reguladores'], ['parrónes', 'parronés', 'parrones', 'parrone', 'párrones']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: crecimiento, reguladores, parrones",
    ),
```

### 243. `patrimonio_financiero`
- **Tipo**: revenue
- **Keywords**: patrimonio, financiero, capital, enterado, total
- **Prioridad sugerida**: 2480
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="patrimonio_financiero",
        priority=2480,
        required_keywords=[['patrímonío', 'pátrimonio', 'patrimónió', 'patrimonios', 'patrimonio'], ['financieró', 'financiero', 'financiéro', 'financieros', 'fínancíero', 'finánciero'], ['capitals', 'capítal', 'cápitál', 'capital'], ['enterados', 'enterado', 'enterádo', 'enteradó', 'éntérado'], ['tótal', 'totál', 'totals', 'total']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: patrimonio, financiero, capital, enterado, total",
    ),
```

### 244. `rentas_efectivas`
- **Tipo**: revenue
- **Keywords**: rentas, efectivas, obre, fecha, vencimiento
- **Prioridad sugerida**: 2490
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="rentas_efectivas",
        priority=2490,
        required_keywords=[['rentas', 'rentás', 'renta', 'réntas'], ['efectivás', 'efectívas', 'efectivas', 'éféctivas', 'efectiva'], ['obré', 'obre', 'óbre', 'obres'], ['fechá', 'fechas', 'fécha', 'fecha'], ['vencimientó', 'véncimiénto', 'vencimiento', 'vencimientos', 'vencímíento']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: rentas, efectivas, obre, fecha, vencimiento",
    ),
```

### 245. `estados_intermedios`
- **Tipo**: revenue
- **Keywords**: estados, intermedios, financieros
- **Prioridad sugerida**: 2500
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="estados_intermedios",
        priority=2500,
        required_keywords=[['estádos', 'estadós', 'estados', 'éstados', 'estado'], ['intermediós', 'intermedios', 'intermedio', 'íntermedíos', 'intérmédios'], ['fináncieros', 'fínancíeros', 'financiéros', 'financiero', 'financieros', 'financierós']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: estados, intermedios, financieros",
    ),
```

### 246. `asesorias_contables`
- **Tipo**: expense
- **Keywords**: asesorias, contables, 900, 4103
- **Prioridad sugerida**: 2510
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="asesorias_contables",
        priority=2510,
        required_keywords=[['asesórias', 'asesoria', 'asesorías', 'asésorias', 'asesorias', 'ásesoriás'], ['contábles', 'contable', 'contablés', 'cóntables', 'contables'], ['900', '900s'], ['4103', '4103s']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: asesorias, contables, 900, 4103",
    ),
```

### 247. `direccion_183`
- **Tipo**: revenue
- **Keywords**: direccion, 183, avtajamar
- **Prioridad sugerida**: 2520
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="direccion_183",
        priority=2520,
        required_keywords=[['direccion', 'dirección', 'diréccion', 'direccions', 'díreccíon'], ['183', '183s'], ['ávtájámár', 'avtajamars', 'avtajamar']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: direccion, 183, avtajamar",
    ),
```

### 248. `construcciones_reparac`
- **Tipo**: expense
- **Keywords**: construcciones, reparac, deprec, gener, habitac
- **Prioridad sugerida**: 2530
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="construcciones_reparac",
        priority=2530,
        required_keywords=[['constrúcciones', 'construccíones', 'construccionés', 'construcciones', 'cónstrucciónes', 'construccione'], ['repárác', 'reparac', 'reparacs', 'réparac'], ['deprec', 'deprecs', 'dépréc'], ['génér', 'gener', 'geners'], ['hábitác', 'habítac', 'habitacs', 'habitac']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: construcciones, reparac, deprec, gener, habitac",
    ),
```

### 249. `vehiculos_carga`
- **Tipo**: expense
- **Keywords**: vehiculos, carga, reparac
- **Prioridad sugerida**: 2540
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="vehiculos_carga",
        priority=2540,
        required_keywords=[['vehiculos', 'vehiculo', 'véhiculos', 'vehiculós', 'vehículos', 'vehicúlos'], ['carga', 'cárgá', 'cargas'], ['repárác', 'reparac', 'reparacs', 'réparac']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: vehiculos, carga, reparac",
    ),
```

### 250. `fluctuaciones_cambio`
- **Tipo**: expense
- **Keywords**: fluctuaciones, cambio, desfar, favore
- **Prioridad sugerida**: 2550
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="fluctuaciones_cambio",
        priority=2550,
        required_keywords=[['fluctuaciones', 'fluctuacione', 'fluctuacionés', 'fluctuacíones', 'flúctúaciones', 'fluctuaciónes', 'fluctuáciones'], ['cambió', 'cambio', 'cambios', 'cámbio', 'cambío'], ['desfars', 'désfar', 'desfar', 'desfár'], ['favóre', 'favores', 'favore', 'fávore', 'favoré']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: fluctuaciones, cambio, desfar, favore",
    ),
```

### 251. `aduanas_gastos`
- **Tipo**: revenue
- **Keywords**: aduanas, gastos, agencias, 20084agencia
- **Prioridad sugerida**: 2560
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="aduanas_gastos",
        priority=2560,
        required_keywords=[['aduanas', 'áduánás', 'adúanas', 'aduana'], ['gasto', 'gastos', 'gastós', 'gástos'], ['agencia', 'ágenciás', 'agencías', 'agéncias', 'agencias'], ['20084agencía', '20084ágenciá', '20084agencias', '20084agencia', '20084agéncia']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: aduanas, gastos, agencias, 20084agencia",
    ),
```

### 252. `depositos_plazo`
- **Tipo**: expense
- **Keywords**: depositos, plazo, bco, santander
- **Prioridad sugerida**: 2570
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="depositos_plazo",
        priority=2570,
        required_keywords=[['dépositos', 'depósitós', 'deposito', 'depositos', 'deposítos'], ['plazos', 'plazo', 'plazó', 'plázo'], ['bco', 'bcó', 'bcos'], ['santanders', 'santander', 'sántánder', 'santandér']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: depositos, plazo, bco, santander",
    ),
```

### 253. `iva_credito`
- **Tipo**: expense
- **Keywords**: iva, credito, incluido
- **Prioridad sugerida**: 2580
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="iva_credito",
        priority=2580,
        required_keywords=[['ivá', 'íva', 'iva', 'ivas'], ['crédito', 'creditó', 'credito', 'creditos', 'credíto'], ['incluidos', 'incluido', 'íncluído', 'inclúido', 'incluidó']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: iva, credito, incluido",
    ),
```

### 254. `agricolas_servicio`
- **Tipo**: expense
- **Keywords**: agricolas, servicio, cosecha, prestacion
- **Prioridad sugerida**: 2590
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="agricolas_servicio",
        priority=2590,
        required_keywords=[['ágricolás', 'agricólas', 'agricola', 'agrícolas', 'agricolas'], ['servicio', 'servicios', 'servícío', 'servició', 'sérvicio'], ['cosechas', 'cosecha', 'cósecha', 'cosechá', 'cosécha'], ['prestación', 'prestácion', 'prestacíon', 'prestacions', 'prestacion', 'préstacion']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: agricolas, servicio, cosecha, prestacion",
    ),
```

### 255. `emitir_factura`
- **Tipo**: expense
- **Keywords**: emitir, factura, facturas
- **Prioridad sugerida**: 2600
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="emitir_factura",
        priority=2600,
        required_keywords=[['emitirs', 'émitir', 'emítír', 'emitir'], ['fácturá', 'facturas', 'factura', 'factúra'], ['facturas', 'factura', 'factúras', 'fácturás']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: emitir, factura, facturas",
    ),
```

### 256. `cta_cte`
- **Tipo**: expense
- **Keywords**: cta, cte, mival, arica, camila
- **Prioridad sugerida**: 2610
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="cta_cte",
        priority=2610,
        required_keywords=[['ctá', 'ctas', 'cta'], ['cte', 'ctes', 'cté'], ['míval', 'mivál', 'mivals', 'mival'], ['áricá', 'aríca', 'arica', 'aricas'], ['camila', 'cámilá', 'camíla', 'camilas']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: cta, cte, mival, arica, camila",
    ),
```

### 257. `merchandising_30080venta`
- **Tipo**: revenue
- **Keywords**: merchandising, 30080venta, 40090costo, venta
- **Prioridad sugerida**: 2620
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="merchandising_30080venta",
        priority=2620,
        required_keywords=[['merchándising', 'merchandisings', 'merchandísíng', 'merchandising', 'mérchandising'], ['30080ventas', '30080venta', '30080ventá', '30080vénta'], ['40090costos', '40090cóstó', '40090costo'], ['ventas', 'vénta', 'ventá', 'venta']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: merchandising, 30080venta, 40090costo, venta",
    ),
```

### 258. `embotellado_30100venta`
- **Tipo**: revenue
- **Keywords**: embotellado, 30100venta, 40110costo, vta
- **Prioridad sugerida**: 2630
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="embotellado_30100venta",
        priority=2630,
        required_keywords=[['émbotéllado', 'embotellados', 'embótelladó', 'embotelládo', 'embotellado'], ['30100ventá', '30100ventas', '30100venta', '30100vénta'], ['40110costos', '40110cóstó', '40110costo'], ['vta', 'vtas', 'vtá']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: embotellado, 30100venta, 40110costo, vta",
    ),
```

### 259. `muestras_30120venta`
- **Tipo**: revenue
- **Keywords**: muestras, 30120venta, 40130costo, venta
- **Prioridad sugerida**: 2640
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="muestras_30120venta",
        priority=2640,
        required_keywords=[['muestrás', 'muestras', 'muestra', 'múestras', 'muéstras'], ['30120vénta', '30120ventá', '30120ventas', '30120venta'], ['40130costo', '40130costos', '40130cóstó'], ['ventas', 'vénta', 'ventá', 'venta']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: muestras, 30120venta, 40130costo, venta",
    ),
```

### 260. `produccion_eerr`
- **Tipo**: revenue
- **Keywords**: produccion, eerr, 30271venta, insumos, 40371costo
- **Prioridad sugerida**: 2650
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="produccion_eerr",
        priority=2650,
        required_keywords=[['prodúccion', 'produccíon', 'produccion', 'próducción', 'produccions'], ['éérr', 'eerr', 'eerrs'], ['30271ventas', '30271vénta', '30271venta', '30271ventá'], ['insumo', 'insumos', 'ínsumos', 'insúmos', 'insumós'], ['40371costos', '40371costo', '40371cóstó']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: produccion, eerr, 30271venta, insumos, 40371costo",
    ),
```

### 261. `venta_40060costo`
- **Tipo**: expense
- **Keywords**: venta, 40060costo, tour, 40120costo
- **Prioridad sugerida**: 2660
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="venta_40060costo",
        priority=2660,
        required_keywords=[['ventas', 'vénta', 'ventá', 'venta'], ['40060cóstó', '40060costos', '40060costo'], ['toúr', 'tours', 'tour', 'tóur'], ['40120costos', '40120cóstó', '40120costo']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: venta, 40060costo, tour, 40120costo",
    ),
```

### 262. `banco_pagados`
- **Tipo**: expense
- **Keywords**: banco, pagados, 40191interes
- **Prioridad sugerida**: 2670
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="banco_pagados",
        priority=2670,
        required_keywords=[['banco', 'bánco', 'bancos', 'bancó'], ['pagados', 'pagadós', 'pagado', 'págádos'], ['40191ínteres', '40191intere', '40191intérés', '40191interes']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: banco, pagados, 40191interes",
    ),
```

### 263. `imponibles_pers`
- **Tipo**: expense
- **Keywords**: imponibles, pers, 50070otros, 50080otros
- **Prioridad sugerida**: 2680
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="imponibles_pers",
        priority=2680,
        required_keywords=[['ímponíbles', 'impónibles', 'imponible', 'imponibles', 'imponiblés'], ['pérs', 'per', 'pers'], ['50070ótrós', '50070otros', '50070otro'], ['50080ótrós', '50080otros', '50080otro']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: imponibles, pers, 50070otros, 50080otros",
    ),
```

### 264. `viajes_50370gastos`
- **Tipo**: expense
- **Keywords**: viajes, 50370gastos, 42129, gastos
- **Prioridad sugerida**: 2690
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="viajes_50370gastos",
        priority=2690,
        required_keywords=[['viajés', 'víajes', 'viaje', 'viájes', 'viajes'], ['50370gastós', '50370gasto', '50370gastos', '50370gástos'], ['42129s', '42129'], ['gasto', 'gastos', 'gastós', 'gástos']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: viajes, 50370gastos, 42129, gastos",
    ),
```

### 265. `gastos_telefonos`
- **Tipo**: revenue
- **Keywords**: gastos, telefonos, 10127, 9227
- **Prioridad sugerida**: 2700
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="gastos_telefonos",
        priority=2700,
        required_keywords=[['gasto', 'gastos', 'gastós', 'gástos'], ['telefono', 'téléfonos', 'telefonos', 'telefónós'], ['10127s', '10127'], ['9227s', '9227']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: gastos, telefonos, 10127, 9227",
    ),
```

### 266. `pag`
- **Tipo**: revenue
- **Keywords**: pag
- **Prioridad sugerida**: 2710
- **Confianza**: 0.2
- **Cuentas afectadas**: ~4
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="pag",
        priority=2710,
        required_keywords=[['pags', 'pag', 'pág']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: pag",
    ),
```

### 267. `compra_prov`
- **Tipo**: revenue
- **Keywords**: compra, prov, fruta
- **Prioridad sugerida**: 2720
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="compra_prov",
        priority=2720,
        required_keywords=[['cómpra', 'comprá', 'compras', 'compra'], ['próv', 'provs', 'prov'], ['fruta', 'frutas', 'frutá', 'frúta']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: compra, prov, fruta",
    ),
```

### 268. `patentes_2301974`
- **Tipo**: expense
- **Keywords**: patentes, 2301974
- **Prioridad sugerida**: 2730
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="patentes_2301974",
        priority=2730,
        required_keywords=[['paténtés', 'patentes', 'pátentes', 'patente'], ['2301974s', '2301974']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: patentes, 2301974",
    ),
```

### 269. `utilidad_perdida`
- **Tipo**: revenue
- **Keywords**: utilidad, perdida, ingresos, explotac
- **Prioridad sugerida**: 2740
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="utilidad_perdida",
        priority=2740,
        required_keywords=[['utilidads', 'utílídad', 'utilidad', 'utilidád', 'útilidad'], ['perdída', 'perdidá', 'perdida', 'pérdida', 'perdidas'], ['ingreso', 'ingrésos', 'ingresos', 'íngresos', 'ingresós'], ['éxplotac', 'explotác', 'explotacs', 'explótac', 'explotac']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: utilidad, perdida, ingresos, explotac",
    ),
```

### 270. `valores_negociables`
- **Tipo**: revenue
- **Keywords**: valores, negociables, cuentas, pagar
- **Prioridad sugerida**: 2750
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="valores_negociables",
        priority=2750,
        required_keywords=[['valorés', 'valore', 'valóres', 'válores', 'valores'], ['négociablés', 'negociables', 'negocíables', 'negóciables', 'negociable', 'negociábles'], ['cuentás', 'cuenta', 'cuéntas', 'cuentas', 'cúentas'], ['pagar', 'págár', 'pagars']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: valores, negociables, cuentas, pagar",
    ),
```

### 271. `otros_activos`
- **Tipo**: revenue
- **Keywords**: otros, activos, circulantes, corr, mon
- **Prioridad sugerida**: 2760
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="otros_activos",
        priority=2760,
        required_keywords=[['ótrós', 'otros', 'otro'], ['actívos', 'áctivos', 'activo', 'activós', 'activos'], ['circulantés', 'circúlantes', 'circulante', 'círculantes', 'circulantes', 'circulántes'], ['córr', 'corr', 'corrs'], ['mon', 'món', 'mons']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: otros, activos, circulantes, corr, mon",
    ),
```

### 272. `rut`
- **Tipo**: revenue
- **Keywords**: rut
- **Prioridad sugerida**: 2770
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="rut",
        priority=2770,
        required_keywords=[['ruts', 'rut', 'rút']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: rut",
    ),
```

### 273. `patrimonio_atribuible`
- **Tipo**: expense
- **Keywords**: patrimonio, atribuible, propietarios
- **Prioridad sugerida**: 2780
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="patrimonio_atribuible",
        priority=2780,
        required_keywords=[['patrímonío', 'pátrimonio', 'patrimónió', 'patrimonios', 'patrimonio'], ['atríbuíble', 'atribuiblé', 'atribuible', 'atribúible', 'átribuible', 'atribuibles'], ['propíetaríos', 'propietario', 'propietarios', 'propiétarios', 'propietários', 'própietariós']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: patrimonio, atribuible, propietarios",
    ),
```

### 274. `pagar_clientes`
- **Tipo**: revenue
- **Keywords**: pagar, clientes, campomanes, cuentas
- **Prioridad sugerida**: 2790
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="pagar_clientes",
        priority=2790,
        required_keywords=[['pagar', 'págár', 'pagars'], ['cliente', 'clíentes', 'cliéntés', 'clientes'], ['campomanés', 'campómanes', 'cámpománes', 'campomanes', 'campomane'], ['cuentás', 'cuenta', 'cuéntas', 'cuentas', 'cúentas']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: pagar, clientes, campomanes, cuentas",
    ),
```

### 275. `clientes_acreedores`
- **Tipo**: revenue
- **Keywords**: clientes, acreedores, varios, casa, garcia
- **Prioridad sugerida**: 2800
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="clientes_acreedores",
        priority=2800,
        required_keywords=[['cliente', 'clíentes', 'cliéntés', 'clientes'], ['acréédorés', 'acreedóres', 'acreedore', 'acreedores', 'ácreedores'], ['vários', 'varios', 'vario', 'variós', 'varíos'], ['casa', 'casas', 'cásá'], ['garcía', 'gárciá', 'garcia', 'garcias']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: clientes, acreedores, varios, casa, garcia",
    ),
```

### 276. `sueldos_clientes`
- **Tipo**: revenue
- **Keywords**: sueldos, clientes, pagar, asturias
- **Prioridad sugerida**: 2810
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="sueldos_clientes",
        priority=2810,
        required_keywords=[['sueldos', 'sueldo', 'sueldós', 'súeldos', 'suéldos'], ['cliente', 'clíentes', 'cliéntés', 'clientes'], ['pagar', 'págár', 'pagars'], ['astúrias', 'asturias', 'asturia', 'asturías', 'ásturiás']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: sueldos, clientes, pagar, asturias",
    ),
```

### 277. `proveedores_regularizar`
- **Tipo**: revenue
- **Keywords**: proveedores, regularizar, 161, cta
- **Prioridad sugerida**: 2820
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="proveedores_regularizar",
        priority=2820,
        required_keywords=[['proveedores', 'proveedore', 'próveedóres', 'provéédorés'], ['regúlarizar', 'régularizar', 'regularizars', 'regularízar', 'regularizar', 'regulárizár'], ['161', '161s'], ['ctá', 'ctas', 'cta']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: proveedores, regularizar, 161, cta",
    ),
```

### 278. `cuentas_pagar`
- **Tipo**: revenue
- **Keywords**: cuentas, pagar, tarjeta
- **Prioridad sugerida**: 2830
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="cuentas_pagar",
        priority=2830,
        required_keywords=[['cuentás', 'cuenta', 'cuéntas', 'cuentas', 'cúentas'], ['pagar', 'págár', 'pagars'], ['tárjetá', 'tarjetas', 'tarjéta', 'tarjeta']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: cuentas, pagar, tarjeta",
    ),
```

### 279. `pons_garcia`
- **Tipo**: revenue
- **Keywords**: pons, garcia, part, maria, dol
- **Prioridad sugerida**: 2840
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="pons_garcia",
        priority=2840,
        required_keywords=[['póns', 'pon', 'pons'], ['garcía', 'gárciá', 'garcia', 'garcias'], ['part', 'párt', 'parts'], ['maria', 'marias', 'maría', 'máriá'], ['dol', 'dols', 'dól']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: pons, garcia, part, maria, dol",
    ),
```

### 280. `depreciacion_financiera`
- **Tipo**: revenue
- **Keywords**: depreciacion, financiera
- **Prioridad sugerida**: 2850
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="depreciacion_financiera",
        priority=2850,
        required_keywords=[['dépréciacion', 'deprecíacíon', 'depreciacions', 'depreciácion', 'depreciacion', 'depreciación'], ['financieras', 'fináncierá', 'financiera', 'financiéra', 'fínancíera']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: depreciacion, financiera",
    ),
```

### 281. `usufructo`
- **Tipo**: revenue
- **Keywords**: usufructo
- **Prioridad sugerida**: 2860
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="usufructo",
        priority=2860,
        required_keywords=[['usufructos', 'usufructó', 'úsúfrúcto', 'usufructo']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: usufructo",
    ),
```

### 282. `cta_cte`
- **Tipo**: revenue
- **Keywords**: cta, cte, personal, 11305
- **Prioridad sugerida**: 2870
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="cta_cte",
        priority=2870,
        required_keywords=[['ctá', 'ctas', 'cta'], ['cte', 'ctes', 'cté'], ['pérsonal', 'personal', 'persónal', 'personál', 'personals'], ['11305s', '11305']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: cta, cte, personal, 11305",
    ),
```

### 283. `gastos_operacion`
- **Tipo**: expense
- **Keywords**: gastos, operacion, factoring, 50701, 9999
- **Prioridad sugerida**: 2880
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="gastos_operacion",
        priority=2880,
        required_keywords=[['gasto', 'gastos', 'gastós', 'gástos'], ['opéracion', 'operacions', 'operácion', 'operacíon', 'óperación', 'operacion'], ['factorings', 'fáctoring', 'factoríng', 'factoring', 'factóring'], ['50701', '50701s'], ['9999s', '9999']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: gastos, operacion, factoring, 50701, 9999",
    ),
```

### 284. `contabilidad_saldo`
- **Tipo**: revenue
- **Keywords**: contabilidad, saldo, segun
- **Prioridad sugerida**: 2890
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="contabilidad_saldo",
        priority=2890,
        required_keywords=[['contabílídad', 'contabilidad', 'cóntabilidad', 'contábilidád', 'contabilidads'], ['saldos', 'sáldo', 'saldó', 'saldo'], ['seguns', 'segun', 'según', 'ségun']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: contabilidad, saldo, segun",
    ),
```

### 285. `pablo`
- **Tipo**: revenue
- **Keywords**: pablo
- **Prioridad sugerida**: 2900
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="pablo",
        priority=2900,
        required_keywords=[['páblo', 'pablo', 'pabló', 'pablos']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: pablo",
    ),
```

### 286. `mauricio_ramirez`
- **Tipo**: revenue
- **Keywords**: mauricio, ramirez, rendir
- **Prioridad sugerida**: 2910
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="mauricio_ramirez",
        priority=2910,
        required_keywords=[['mauricios', 'maurícío', 'maúricio', 'maurició', 'mauricio', 'máuricio'], ['rámirez', 'ramirez', 'ramiréz', 'ramírez', 'ramirezs'], ['réndir', 'rendirs', 'rendir', 'rendír']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: mauricio, ramirez, rendir",
    ),
```

### 287. `san_12103`
- **Tipo**: revenue
- **Keywords**: san, 12103, ramon, pencahue
- **Prioridad sugerida**: 2920
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="san_12103",
        priority=2920,
        required_keywords=[['sán', 'sans', 'san'], ['12103s', '12103'], ['ramon', 'rámon', 'ramón', 'ramons'], ['pencahues', 'pencahue', 'péncahué', 'pencáhue', 'pencahúe']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: san, 12103, ramon, pencahue",
    ),
```

### 288. `12108_san`
- **Tipo**: revenue
- **Keywords**: 12108, san, luis
- **Prioridad sugerida**: 2930
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="12108_san",
        priority=2930,
        required_keywords=[['12108s', '12108'], ['sán', 'sans', 'san'], ['lui', 'luís', 'luis', 'lúis']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: 12108, san, luis",
    ),
```

### 289. `cipres_12139`
- **Tipo**: revenue
- **Keywords**: cipres, 12139
- **Prioridad sugerida**: 2940
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="cipres_12139",
        priority=2940,
        required_keywords=[['cipre', 'cipres', 'cípres', 'ciprés'], ['12139s', '12139']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: cipres, 12139",
    ),
```

### 290. `compras_activadas`
- **Tipo**: revenue
- **Keywords**: compras, activadas, compra, activo
- **Prioridad sugerida**: 2950
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="compras_activadas",
        priority=2950,
        required_keywords=[['comprás', 'compras', 'cómpras', 'compra'], ['activadas', 'activada', 'actívadas', 'áctivádás'], ['cómpra', 'comprá', 'compras', 'compra'], ['áctivo', 'activó', 'actívo', 'activo', 'activos']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: compras, activadas, compra, activo",
    ),
```

### 291. `plantacion_tutores`
- **Tipo**: revenue
- **Keywords**: plantacion, tutores, alambre
- **Prioridad sugerida**: 2960
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="plantacion_tutores",
        priority=2960,
        required_keywords=[['plantacíon', 'plantacion', 'plantacions', 'plántácion', 'plantación'], ['tutores', 'tutóres', 'tútores', 'tutorés', 'tutore'], ['alambres', 'alambre', 'alambré', 'álámbre']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: plantacion, tutores, alambre",
    ),
```

### 292. `ltda_plantacion`
- **Tipo**: revenue
- **Keywords**: ltda, plantacion, tutores, torres, miranda
- **Prioridad sugerida**: 2970
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="ltda_plantacion",
        priority=2970,
        required_keywords=[['ltda', 'ltdas', 'ltdá'], ['plantacíon', 'plantacion', 'plantacions', 'plántácion', 'plantación'], ['tutores', 'tutóres', 'tútores', 'tutorés', 'tutore'], ['torre', 'torres', 'tórres', 'torrés'], ['míranda', 'miranda', 'mirándá', 'mirandas']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: ltda, plantacion, tutores, torres, miranda",
    ),
```

### 293. `meses_amortizar`
- **Tipo**: revenue
- **Keywords**: meses, amortizar, contar, fecha
- **Prioridad sugerida**: 2980
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="meses_amortizar",
        priority=2980,
        required_keywords=[['mese', 'mésés', 'meses'], ['amortizar', 'amortízar', 'ámortizár', 'amórtizar', 'amortizars'], ['contar', 'contár', 'contars', 'cóntar'], ['fechá', 'fechas', 'fécha', 'fecha']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: meses, amortizar, contar, fecha",
    ),
```

### 294. `2020`
- **Tipo**: revenue
- **Keywords**: 2020
- **Prioridad sugerida**: 2990
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="2020",
        priority=2990,
        required_keywords=[['2020s', '2020']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: 2020",
    ),
```

### 295. `utilidades_acumuladas`
- **Tipo**: revenue
- **Keywords**: utilidades, acumuladas, 23302, saldo
- **Prioridad sugerida**: 3000
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="utilidades_acumuladas",
        priority=3000,
        required_keywords=[['utílídades', 'utilidádes', 'utilidade', 'utilidades', 'útilidades', 'utilidadés'], ['acumuladas', 'acumulada', 'acúmúladas', 'ácumuládás'], ['23302', '23302s'], ['saldos', 'sáldo', 'saldó', 'saldo']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: utilidades, acumuladas, 23302, saldo",
    ),
```

### 296. `retiro_utilidades`
- **Tipo**: revenue
- **Keywords**: retiro, utilidades, inmob, lobarnechea
- **Prioridad sugerida**: 3010
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="retiro_utilidades",
        priority=3010,
        required_keywords=[['retiro', 'retiró', 'retiros', 'retíro', 'rétiro'], ['utílídades', 'utilidádes', 'utilidade', 'utilidades', 'útilidades', 'utilidadés'], ['inmób', 'ínmob', 'inmob', 'inmobs'], ['lobárnecheá', 'lobarnechea', 'lobarnecheas', 'lóbarnechea', 'lobarnéchéa']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: retiro, utilidades, inmob, lobarnechea",
    ),
```

### 297. `ppua_ajuste`
- **Tipo**: expense
- **Keywords**: ppua, ajuste, at2014
- **Prioridad sugerida**: 3020
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="ppua_ajuste",
        priority=3020,
        required_keywords=[['ppua', 'ppuá', 'ppuas', 'ppúa'], ['ájuste', 'ajustes', 'ajuste', 'ajusté', 'ajúste'], ['at2014s', 'at2014', 'át2014']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: ppua, ajuste, at2014",
    ),
```

### 298. `2006_juan`
- **Tipo**: expense
- **Keywords**: 2006, juan, maria
- **Prioridad sugerida**: 3030
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="2006_juan",
        priority=3030,
        required_keywords=[['2006s', '2006'], ['juán', 'júan', 'juans', 'juan'], ['maria', 'marias', 'maría', 'máriá']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: 2006, juan, maria",
    ),
```

### 299. `mercaderias_pasivo`
- **Tipo**: revenue
- **Keywords**: mercaderias, pasivo, circulante, 327, 082
- **Prioridad sugerida**: 3040
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="mercaderias_pasivo",
        priority=3040,
        required_keywords=[['mercaderias', 'mercaderia', 'mercáderiás', 'mercaderías', 'mércadérias'], ['pasivó', 'pasivos', 'pásivo', 'pasívo', 'pasivo'], ['círculante', 'circulanté', 'circulantes', 'circúlante', 'circulánte', 'circulante'], ['327s', '327'], ['082s', '082']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: mercaderias, pasivo, circulante, 327, 082",
    ),
```

### 300. `impto_renta`
- **Tipo**: revenue
- **Keywords**: impto, renta, art, at2019
- **Prioridad sugerida**: 3050
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="impto_renta",
        priority=3050,
        required_keywords=[['imptos', 'imptó', 'ímpto', 'impto'], ['rentá', 'rentas', 'rénta', 'renta'], ['árt', 'arts', 'art'], ['at2019s', 'át2019', 'at2019']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: impto, renta, art, at2019",
    ),
```

### 301. `renta_impto`
- **Tipo**: revenue
- **Keywords**: renta, impto
- **Prioridad sugerida**: 3060
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="renta_impto",
        priority=3060,
        required_keywords=[['rentá', 'rentas', 'rénta', 'renta'], ['imptos', 'imptó', 'ímpto', 'impto']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: renta, impto",
    ),
```

### 302. `eventos_especiales`
- **Tipo**: revenue
- **Keywords**: eventos, especiales
- **Prioridad sugerida**: 3070
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="eventos_especiales",
        priority=3070,
        required_keywords=[['événtos', 'eventós', 'eventos', 'evento'], ['éspécialés', 'especiale', 'especíales', 'especiáles', 'especiales']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: eventos, especiales",
    ),
```

### 303. `productos_quimicos`
- **Tipo**: expense
- **Keywords**: productos, quimicos, otros, costo, 206
- **Prioridad sugerida**: 3080
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="productos_quimicos",
        priority=3080,
        required_keywords=[['prodúctos', 'productos', 'producto', 'próductós'], ['quimicos', 'químícos', 'qúimicos', 'quimicós', 'quimico'], ['ótrós', 'otros', 'otro'], ['cóstó', 'costo', 'costos'], ['206', '206s']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: productos, quimicos, otros, costo, 206",
    ),
```

### 304. `frigorifico_obras`
- **Tipo**: revenue
- **Keywords**: frigorifico, obras
- **Prioridad sugerida**: 3090
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="frigorifico_obras",
        priority=3090,
        required_keywords=[['frigórificó', 'frigorificos', 'frigorifico', 'frígorífíco'], ['óbras', 'obrás', 'obra', 'obras']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: frigorifico, obras",
    ),
```

### 305. `dep_acum`
- **Tipo**: expense
- **Keywords**: dep, acum, superior, software
- **Prioridad sugerida**: 3100
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="dep_acum",
        priority=3100,
        required_keywords=[['deps', 'dép', 'dep'], ['acums', 'ácum', 'acúm', 'acum'], ['superior', 'súperior', 'superiors', 'supérior', 'superíor', 'superiór'], ['softwaré', 'software', 'sóftware', 'softwáre', 'softwares']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: dep, acum, superior, software",
    ),
```

### 306. `uvas_usas`
- **Tipo**: revenue
- **Keywords**: uvas, usas
- **Prioridad sugerida**: 3110
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="uvas_usas",
        priority=3110,
        required_keywords=[['uva', 'uvas', 'úvas', 'uvás'], ['usas', 'usa', 'úsas', 'usás']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: uvas, usas",
    ),
```

### 307. `recuperar_impuestos`
- **Tipo**: revenue
- **Keywords**: recuperar, impuestos
- **Prioridad sugerida**: 3120
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="recuperar_impuestos",
        priority=3120,
        required_keywords=[['recuperár', 'recúperar', 'recuperar', 'récupérar', 'recuperars'], ['ímpuestos', 'impuestós', 'impuéstos', 'impuesto', 'impuestos', 'impúestos']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: recuperar, impuestos",
    ),
```

### 308. `otros_activos`
- **Tipo**: revenue
- **Keywords**: otros, activos, largo, plazo, mon
- **Prioridad sugerida**: 3130
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="otros_activos",
        priority=3130,
        required_keywords=[['ótrós', 'otros', 'otro'], ['actívos', 'áctivos', 'activo', 'activós', 'activos'], ['largos', 'lárgo', 'largó', 'largo'], ['plazos', 'plazo', 'plazó', 'plázo'], ['mon', 'món', 'mons']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: otros, activos, largo, plazo, mon",
    ),
```

### 309. `vencimiento_provisionales`
- **Tipo**: revenue
- **Keywords**: vencimiento, provisionales, art, fecha
- **Prioridad sugerida**: 3140
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="vencimiento_provisionales",
        priority=3140,
        required_keywords=[['vencimientó', 'véncimiénto', 'vencimiento', 'vencimientos', 'vencímíento'], ['próvisiónales', 'provisionalés', 'provisionales', 'provísíonales', 'provisionale', 'provisionáles'], ['árt', 'arts', 'art'], ['fechá', 'fechas', 'fécha', 'fecha']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: vencimiento, provisionales, art, fecha",
    ),
```

### 310. `art_renta`
- **Tipo**: expense
- **Keywords**: art, renta, liquida, perdida
- **Prioridad sugerida**: 3150
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="art_renta",
        priority=3150,
        required_keywords=[['árt', 'arts', 'art'], ['rentá', 'rentas', 'rénta', 'renta'], ['liquida', 'liqúida', 'liquidas', 'líquída', 'liquidá'], ['perdída', 'perdidá', 'perdida', 'pérdida', 'perdidas']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: art, renta, liquida, perdida",
    ),
```

### 311. `mercaderias_importadas`
- **Tipo**: expense
- **Keywords**: mercaderias, importadas, 173, 670, 519
- **Prioridad sugerida**: 3160
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="mercaderias_importadas",
        priority=3160,
        required_keywords=[['mercaderias', 'mercaderia', 'mercáderiás', 'mercaderías', 'mércadérias'], ['impórtadas', 'ímportadas', 'importádás', 'importada', 'importadas'], ['173s', '173'], ['670', '670s'], ['519s', '519']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: mercaderias, importadas, 173, 670, 519",
    ),
```

### 312. `cuentas_largo`
- **Tipo**: revenue
- **Keywords**: cuentas, largo, plazo, pago
- **Prioridad sugerida**: 3170
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="cuentas_largo",
        priority=3170,
        required_keywords=[['cuentás', 'cuenta', 'cuéntas', 'cuentas', 'cúentas'], ['largos', 'lárgo', 'largó', 'largo'], ['plazos', 'plazo', 'plazó', 'plázo'], ['págo', 'pagó', 'pagos', 'pago']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: cuentas, largo, plazo, pago",
    ),
```

### 313. `tarjeta_sueldos`
- **Tipo**: revenue
- **Keywords**: tarjeta, sueldos, pagar
- **Prioridad sugerida**: 3180
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="tarjeta_sueldos",
        priority=3180,
        required_keywords=[['tárjetá', 'tarjetas', 'tarjéta', 'tarjeta'], ['sueldos', 'sueldo', 'sueldós', 'súeldos', 'suéldos'], ['pagar', 'págár', 'pagars']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: tarjeta, sueldos, pagar",
    ),
```

### 314. `cuentas_cobrar`
- **Tipo**: revenue
- **Keywords**: cuentas, cobrar, empresa, relac
- **Prioridad sugerida**: 3190
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="cuentas_cobrar",
        priority=3190,
        required_keywords=[['cuentás', 'cuenta', 'cuéntas', 'cuentas', 'cúentas'], ['cóbrar', 'cobrár', 'cobrars', 'cobrar'], ['empresa', 'empresas', 'empresá', 'émprésa'], ['relacs', 'rélac', 'relac', 'relác']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: cuentas, cobrar, empresa, relac",
    ),
```

### 315. `tipo_perdida`
- **Tipo**: revenue
- **Keywords**: tipo, perdida, camblo
- **Prioridad sugerida**: 3200
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="tipo_perdida",
        priority=3200,
        required_keywords=[['típo', 'tipo', 'tipó', 'tipos'], ['perdída', 'perdidá', 'perdida', 'pérdida', 'perdidas'], ['camblos', 'cámblo', 'camblo', 'cambló']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: tipo, perdida, camblo",
    ),
```

### 316. `derechos_concesiones`
- **Tipo**: expense
- **Keywords**: derechos, concesiones, suscripciones
- **Prioridad sugerida**: 3210
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="derechos_concesiones",
        priority=3210,
        required_keywords=[['déréchos', 'derechós', 'derecho', 'derechos'], ['concesiones', 'concesíones', 'cóncesiónes', 'concesione', 'concésionés'], ['suscripciónes', 'suscripciones', 'suscripcionés', 'súscripciones', 'suscrípcíones', 'suscripcione']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: derechos, concesiones, suscripciones",
    ),
```

### 317. `activo_impuestos`
- **Tipo**: revenue
- **Keywords**: activo, impuestos, corrientes, total
- **Prioridad sugerida**: 3220
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="activo_impuestos",
        priority=3220,
        required_keywords=[['áctivo', 'activó', 'actívo', 'activo', 'activos'], ['ímpuestos', 'impuestós', 'impuéstos', 'impuesto', 'impuestos', 'impúestos'], ['corríentes', 'corriente', 'corriéntés', 'corrientes', 'córrientes'], ['tótal', 'totál', 'totals', 'total']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: activo, impuestos, corrientes, total",
    ),
```

### 318. `margen_bruto`
- **Tipo**: revenue
- **Keywords**: margen, bruto
- **Prioridad sugerida**: 3230
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="margen_bruto",
        priority=3230,
        required_keywords=[['margén', 'margens', 'margen', 'márgen'], ['brutó', 'brúto', 'bruto', 'brutos']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: margen, bruto",
    ),
```

### 319. `inversiones_philadelphia`
- **Tipo**: expense
- **Keywords**: inversiones, philadelphia, spa, ibiza
- **Prioridad sugerida**: 3240
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="inversiones_philadelphia",
        priority=3240,
        required_keywords=[['inversiones', 'inversiónes', 'ínversíones', 'inversione', 'invérsionés'], ['phíladelphía', 'philádelphiá', 'philadelphias', 'philadelphia', 'philadélphia'], ['spa', 'spas', 'spá'], ['ibiza', 'ibizá', 'íbíza', 'ibizas']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: inversiones, philadelphia, spa, ibiza",
    ),
```

### 320. `provisional_cat`
- **Tipo**: revenue
- **Keywords**: provisional, cat, impto, 11199994
- **Prioridad sugerida**: 3250
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="provisional_cat",
        priority=3250,
        required_keywords=[['provisionals', 'próvisiónal', 'provisional', 'provisionál', 'provísíonal'], ['cat', 'cát', 'cats'], ['imptos', 'imptó', 'ímpto', 'impto'], ['11199994s', '11199994']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: provisional, cat, impto, 11199994",
    ),
```

### 321. `riego_mecanizado`
- **Tipo**: expense
- **Keywords**: riego, mecanizado, 3715414, 412824, 3302598
- **Prioridad sugerida**: 3260
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="riego_mecanizado",
        priority=3260,
        required_keywords=[['riégo', 'riego', 'riegos', 'ríego', 'riegó'], ['mecanízado', 'mécanizado', 'mecanizadó', 'mecanizados', 'mecánizádo', 'mecanizado'], ['3715414', '3715414s'], ['412824', '412824s'], ['3302598', '3302598s']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: riego, mecanizado, 3715414, 412824, 3302598",
    ),
```

### 322. `familiar_asig`
- **Tipo**: expense
- **Keywords**: familiar, asig, asignacion, 200141
- **Prioridad sugerida**: 3270
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="familiar_asig",
        priority=3270,
        required_keywords=[['familiars', 'famílíar', 'fámiliár', 'familiar'], ['asigs', 'asig', 'asíg', 'ásig'], ['asígnacíon', 'asignación', 'asignacions', 'asignacion', 'ásignácion'], ['200141s', '200141']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: familiar, asig, asignacion, 200141",
    ),
```

### 323. `chile_spa`
- **Tipo**: revenue
- **Keywords**: chile, spa, pagina, capiro, captro
- **Prioridad sugerida**: 3280
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="chile_spa",
        priority=3280,
        required_keywords=[['chilé', 'chiles', 'chile', 'chíle'], ['spa', 'spas', 'spá'], ['pagina', 'paginas', 'pagína', 'páginá'], ['capíro', 'capiros', 'capiró', 'capiro', 'cápiro'], ['captró', 'captros', 'cáptro', 'captro']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: chile, spa, pagina, capiro, captro",
    ),
```

### 324. `costos_4101`
- **Tipo**: expense
- **Keywords**: costos, 4101
- **Prioridad sugerida**: 3290
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="costos_4101",
        priority=3290,
        required_keywords=[['cóstós', 'costo', 'costos'], ['4101', '4101s']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: costos, 4101",
    ),
```

### 325. `ajuste_centratizacion`
- **Tipo**: revenue
- **Keywords**: ajuste, centratizacion, centralizacion
- **Prioridad sugerida**: 3300
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="ajuste_centratizacion",
        priority=3300,
        required_keywords=[['ájuste', 'ajustes', 'ajuste', 'ajusté', 'ajúste'], ['centrátizácion', 'céntratizacion', 'centratizacion', 'centratizacions', 'centratízacíon', 'centratización'], ['centralizacions', 'centralízacíon', 'centralización', 'centrálizácion', 'centralizacion', 'céntralizacion']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: ajuste, centratizacion, centralizacion",
    ),
```

### 326. `fabrica_dest`
- **Tipo**: revenue
- **Keywords**: fabrica, dest, etilico, comercial, agroindustrial
- **Prioridad sugerida**: 3310
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="fabrica_dest",
        priority=3310,
        required_keywords=[['fabrica', 'fabricas', 'fabríca', 'fábricá'], ['dest', 'dést', 'dests'], ['etílíco', 'etilico', 'etilicó', 'étilico', 'etilicos'], ['comerciál', 'comercíal', 'comercial', 'comercials', 'cómercial', 'comércial'], ['agroindustrials', 'agroindústrial', 'agroindustrial', 'agróindustrial', 'ágroindustriál', 'agroíndustríal']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: fabrica, dest, etilico, comercial, agroindustrial",
    ),
```

### 327. `arriendo_maq`
- **Tipo**: expense
- **Keywords**: arriendo, maq, vehiculos, vehiculo
- **Prioridad sugerida**: 3320
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="arriendo_maq",
        priority=3320,
        required_keywords=[['arriéndo', 'árriendo', 'arriendó', 'arriendos', 'arriendo', 'arríendo'], ['máq', 'maq', 'maqs'], ['vehiculos', 'vehiculo', 'véhiculos', 'vehiculós', 'vehículos', 'vehicúlos'], ['vehiculos', 'vehiculo', 'véhiculo', 'vehiculó', 'vehicúlo', 'vehículo']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: arriendo, maq, vehiculos, vehiculo",
    ),
```

### 328. `desdeenero_2018`
- **Tipo**: revenue
- **Keywords**: desdeenero, 2018, hastadiciembre
- **Prioridad sugerida**: 3330
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="desdeenero_2018",
        priority=3330,
        required_keywords=[['desdeeneró', 'desdeeneros', 'desdeenero', 'désdéénéro'], ['2018', '2018s'], ['hastadiciémbré', 'hastadiciembres', 'hastadícíembre', 'hástádiciembre', 'hastadiciembre']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: desdeenero, 2018, hastadiciembre",
    ),
```

### 329. `produccion_gastos`
- **Tipo**: expense
- **Keywords**: produccion, gastos, general, costo
- **Prioridad sugerida**: 3340
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="produccion_gastos",
        priority=3340,
        required_keywords=[['prodúccion', 'produccíon', 'produccion', 'próducción', 'produccions'], ['gasto', 'gastos', 'gastós', 'gástos'], ['general', 'generals', 'général', 'generál'], ['cóstó', 'costo', 'costos']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: produccion, gastos, general, costo",
    ),
```

### 330. `venta_uva`
- **Tipo**: revenue
- **Keywords**: venta, uva, mesa, pais
- **Prioridad sugerida**: 3350
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="venta_uva",
        priority=3350,
        required_keywords=[['ventas', 'vénta', 'ventá', 'venta'], ['uva', 'uvas', 'úva', 'uvá'], ['mesá', 'mésa', 'mesas', 'mesa'], ['país', 'pai', 'páis', 'pais']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: venta, uva, mesa, pais",
    ),
```

### 331. `gtos_vtas`
- **Tipo**: revenue
- **Keywords**: gtos, vtas, comision, sodexo
- **Prioridad sugerida**: 3360
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="gtos_vtas",
        priority=3360,
        required_keywords=[['gto', 'gtos', 'gtós'], ['vta', 'vtás', 'vtas'], ['cómisión', 'comision', 'comísíon', 'comisions'], ['sodéxo', 'sódexó', 'sodexo', 'sodexos']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: gtos, vtas, comision, sodexo",
    ),
```

### 332. `asesorias_externas`
- **Tipo**: revenue
- **Keywords**: asesorias, externas, operacion
- **Prioridad sugerida**: 3370
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="asesorias_externas",
        priority=3370,
        required_keywords=[['asesórias', 'asesoria', 'asesorías', 'asésorias', 'asesorias', 'ásesoriás'], ['externas', 'éxtérnas', 'externa', 'externás'], ['opéracion', 'operacions', 'operácion', 'operacíon', 'óperación', 'operacion']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: asesorias, externas, operacion",
    ),
```

### 333. `uniformes_implementos`
- **Tipo**: revenue
- **Keywords**: uniformes, implementos, tra
- **Prioridad sugerida**: 3380
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="uniformes_implementos",
        priority=3380,
        required_keywords=[['uniforme', 'uniformes', 'unifórmes', 'úniformes', 'uníformes', 'uniformés'], ['implementos', 'implementós', 'implemento', 'impléméntos', 'ímplementos'], ['tras', 'trá', 'tra']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: uniformes, implementos, tra",
    ),
```

### 334. `indemnizaciones_desahucios`
- **Tipo**: expense
- **Keywords**: indemnizaciones, desahucios
- **Prioridad sugerida**: 3390
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="indemnizaciones_desahucios",
        priority=3390,
        required_keywords=[['indemnizacione', 'indemnizaciones', 'indémnizacionés', 'índemnízacíones', 'indemnizáciones', 'indemnizaciónes'], ['desáhucios', 'desahucio', 'desahucíos', 'desahuciós', 'desahúcios', 'desahucios', 'désahucios']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: indemnizaciones, desahucios",
    ),
```

### 335. `fletes_reparto`
- **Tipo**: expense
- **Keywords**: fletes, reparto
- **Prioridad sugerida**: 3400
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="fletes_reparto",
        priority=3400,
        required_keywords=[['fletes', 'flete', 'flétés'], ['repárto', 'repartó', 'repartos', 'reparto', 'réparto']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: fletes, reparto",
    ),
```

### 336. `gastos_seguridad`
- **Tipo**: revenue
- **Keywords**: gastos, seguridad, alarmas
- **Prioridad sugerida**: 3410
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="gastos_seguridad",
        priority=3410,
        required_keywords=[['gasto', 'gastos', 'gastós', 'gástos'], ['seguridád', 'seguridads', 'séguridad', 'segúridad', 'segurídad', 'seguridad'], ['álármás', 'alarma', 'alarmas']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: gastos, seguridad, alarmas",
    ),
```

### 337. `registro_gastos`
- **Tipo**: revenue
- **Keywords**: registro, gastos, notaria, publicacion
- **Prioridad sugerida**: 3420
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="registro_gastos",
        priority=3420,
        required_keywords=[['régistro', 'regístro', 'registró', 'registro', 'registros'], ['gasto', 'gastos', 'gastós', 'gástos'], ['notáriá', 'notaria', 'nótaria', 'notarias', 'notaría'], ['públicacion', 'publicacions', 'publicación', 'publicacion', 'publícacíon', 'publicácion']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: registro, gastos, notaria, publicacion",
    ),
```

### 338. `avena_siembra`
- **Tipo**: expense
- **Keywords**: avena, siembra
- **Prioridad sugerida**: 3430
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="avena_siembra",
        priority=3430,
        required_keywords=[['avena', 'avéna', 'avenas', 'ávená'], ['siembrá', 'siembras', 'siembra', 'síembra', 'siémbra']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: avena, siembra",
    ),
```

### 339. `almuerzos_40080costo`
- **Tipo**: expense
- **Keywords**: almuerzos, 40080costo, venta, 30070venta
- **Prioridad sugerida**: 3440
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="almuerzos_40080costo",
        priority=3440,
        required_keywords=[['álmuerzos', 'almuerzo', 'almúerzos', 'almuerzós', 'almuérzos', 'almuerzos'], ['40080costo', '40080costos', '40080cóstó'], ['ventas', 'vénta', 'ventá', 'venta'], ['30070vénta', '30070ventá', '30070ventas', '30070venta']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: almuerzos, 40080costo, venta, 30070venta",
    ),
```

### 340. `renta_40480impuesto`
- **Tipo**: expense
- **Keywords**: renta, 40480impuesto, 40490impuesto
- **Prioridad sugerida**: 3450
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="renta_40480impuesto",
        priority=3450,
        required_keywords=[['rentá', 'rentas', 'rénta', 'renta'], ['40480impúesto', '40480impuestó', '40480impuestos', '40480ímpuesto', '40480impuesto', '40480impuésto'], ['40490impuestó', '40490impuésto', '40490ímpuesto', '40490impúesto', '40490impuestos', '40490impuesto']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: renta, 40480impuesto, 40490impuesto",
    ),
```

### 341. `50610depreciaciones_50611depreciaciones`
- **Tipo**: expense
- **Keywords**: 50610depreciaciones, 50611depreciaciones, mvrt
- **Prioridad sugerida**: 3460
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="50610depreciaciones_50611depreciaciones",
        priority=3460,
        required_keywords=[['50610depreciacione', '50610depreciaciones', '50610depreciaciónes', '50610dépréciacionés', '50610deprecíacíones', '50610depreciáciones'], ['50611deprecíacíones', '50611depreciacione', '50611depreciáciones', '50611depreciaciónes', '50611depreciaciones', '50611dépréciacionés'], ['mvrts', 'mvrt']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: 50610depreciaciones, 50611depreciaciones, mvrt",
    ),
```

### 342. `serbmit_otseupmi`
- **Tipo**: revenue
- **Keywords**: serbmit, otseupmi
- **Prioridad sugerida**: 3470
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="serbmit_otseupmi",
        priority=3470,
        required_keywords=[['serbmits', 'sérbmit', 'serbmit', 'serbmít'], ['otseupmí', 'otseupmis', 'otseúpmi', 'ótseupmi', 'otseupmi', 'otséupmi']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: serbmit, otseupmi",
    ),
```

### 343. `retencion_impuestos`
- **Tipo**: revenue
- **Keywords**: retencion, impuestos, 192428, 207983
- **Prioridad sugerida**: 3480
- **Confianza**: 0.2
- **Cuentas afectadas**: ~3
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="retencion_impuestos",
        priority=3480,
        required_keywords=[['retencíon', 'retención', 'retencion', 'réténcion', 'retencions'], ['ímpuestos', 'impuestós', 'impuéstos', 'impuesto', 'impuestos', 'impúestos'], ['192428s', '192428'], ['207983', '207983s']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: retencion, impuestos, 192428, 207983",
    ),
```

### 344. `2211_doom`
- **Tipo**: revenue
- **Keywords**: 2211, doom
- **Prioridad sugerida**: 3490
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="2211_doom",
        priority=3490,
        required_keywords=[['2211', '2211s'], ['doom', 'dooms', 'dóóm']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: 2211, doom",
    ),
```

### 345. `anticipo_proveedores`
- **Tipo**: expense
- **Keywords**: anticipo, proveedores, 348
- **Prioridad sugerida**: 3500
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="anticipo_proveedores",
        priority=3500,
        required_keywords=[['antícípo', 'anticipó', 'ánticipo', 'anticipos', 'anticipo'], ['proveedores', 'proveedore', 'próveedóres', 'provéédorés'], ['348', '348s']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: anticipo, proveedores, 348",
    ),
```

### 346. `obras_inmueble`
- **Tipo**: expense
- **Keywords**: obras, inmueble
- **Prioridad sugerida**: 3510
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="obras_inmueble",
        priority=3510,
        required_keywords=[['óbras', 'obrás', 'obra', 'obras'], ['inmúeble', 'inmuebles', 'ínmueble', 'inmueble', 'inmuéblé']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: obras, inmueble",
    ),
```

### 347. `maquinaria_211376247`
- **Tipo**: expense
- **Keywords**: maquinaria, 211376247, 379, 018
- **Prioridad sugerida**: 3520
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="maquinaria_211376247",
        priority=3520,
        required_keywords=[['maquinarias', 'máquináriá', 'maquinaria', 'maqúinaria', 'maquínaría'], ['211376247s', '211376247'], ['379', '379s'], ['018s', '018']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: maquinaria, 211376247, 379, 018",
    ),
```

### 348. `contratista_339`
- **Tipo**: revenue
- **Keywords**: contratista, 339, 294, 130
- **Prioridad sugerida**: 3530
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="contratista_339",
        priority=3530,
        required_keywords=[['contratistas', 'contrátistá', 'contratista', 'contratísta', 'cóntratista'], ['339', '339s'], ['294s', '294'], ['130', '130s']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: contratista, 339, 294, 130",
    ),
```

### 349. `fumigaciones_8321`
- **Tipo**: expense
- **Keywords**: fumigaciones, 8321
- **Prioridad sugerida**: 3540
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="fumigaciones_8321",
        priority=3540,
        required_keywords=[['fúmigaciones', 'fumigáciones', 'fumigacionés', 'fumigaciones', 'fumigaciónes', 'fumígacíones', 'fumigacione'], ['8321', '8321s']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: fumigaciones, 8321",
    ),
```

### 350. `remuneraciones_122`
- **Tipo**: revenue
- **Keywords**: remuneraciones, 122, 043
- **Prioridad sugerida**: 3550
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="remuneraciones_122",
        priority=3550,
        required_keywords=[['remuneracione', 'rémunéracionés', 'remuneraciones', 'remuneracíones', 'remúneraciones', 'remuneraciónes', 'remuneráciones'], ['122', '122s'], ['043', '043s']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: remuneraciones, 122, 043",
    ),
```

### 351. `gastos_adm`
- **Tipo**: revenue
- **Keywords**: gastos, adm, vtas
- **Prioridad sugerida**: 3560
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="gastos_adm",
        priority=3560,
        required_keywords=[['gasto', 'gastos', 'gastós', 'gástos'], ['ádm', 'adms', 'adm'], ['vta', 'vtás', 'vtas']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: gastos, adm, vtas",
    ),
```

### 352. `predio_tranque`
- **Tipo**: expense
- **Keywords**: predio, tranque
- **Prioridad sugerida**: 3570
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="predio_tranque",
        priority=3570,
        required_keywords=[['predio', 'predió', 'predío', 'predios', 'prédio'], ['tranqúe', 'tránque', 'tranque', 'tranqué', 'tranques']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: predio, tranque",
    ),
```

### 353. `total_pasivos`
- **Tipo**: expense
- **Keywords**: total, pasivos, puerto
- **Prioridad sugerida**: 3580
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="total_pasivos",
        priority=3580,
        required_keywords=[['tótal', 'totál', 'totals', 'total'], ['pasivos', 'pasivós', 'pásivos', 'pasívos', 'pasivo'], ['puérto', 'púerto', 'puertó', 'puerto', 'puertos']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: total, pasivos, puerto",
    ),
```

### 354. `vessels_and`
- **Tipo**: expense
- **Keywords**: vessels, and, machineries, paid, capital
- **Prioridad sugerida**: 3590
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="vessels_and",
        priority=3590,
        required_keywords=[['vessels', 'vésséls', 'vessel'], ['and', 'ands', 'ánd'], ['machinerie', 'machinériés', 'machíneríes', 'máchineries', 'machineries'], ['paid', 'páid', 'paids', 'paíd'], ['capitals', 'capítal', 'cápitál', 'capital']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: vessels, and, machineries, paid, capital",
    ),
```

### 355. `austral_law`
- **Tipo**: expense
- **Keywords**: austral, law, retained, earnings
- **Prioridad sugerida**: 3600
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="austral_law",
        priority=3600,
        required_keywords=[['aústral', 'austral', 'áustrál', 'australs'], ['láw', 'law', 'laws'], ['rétainéd', 'retaíned', 'retáined', 'retained', 'retaineds'], ['earning', 'earníngs', 'éarnings', 'earnings', 'eárnings']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: austral, law, retained, earnings",
    ),
```

### 356. `net_income`
- **Tipo**: expense
- **Keywords**: net, income, for, the, period
- **Prioridad sugerida**: 3610
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="net_income",
        priority=3610,
        required_keywords=[['nets', 'nét', 'net'], ['incomes', 'incóme', 'incomé', 'income', 'íncome'], ['fors', 'fór', 'for'], ['thé', 'the', 'thes'], ['periods', 'period', 'períod', 'périod', 'periód']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: net, income, for, the, period",
    ),
```

### 357. `long_term`
- **Tipo**: expense
- **Keywords**: long, term, inventory, 356, 733
- **Prioridad sugerida**: 3620
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="long_term",
        priority=3620,
        required_keywords=[['long', 'longs', 'lóng'], ['térm', 'terms', 'term'], ['inventóry', 'invéntory', 'ínventory', 'inventory', 'inventorys'], ['356', '356s'], ['733s', '733']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: long, term, inventory, 356, 733",
    ),
```

### 358. `leasing_payables`
- **Tipo**: expense
- **Keywords**: leasing, payables, tax, assets, current
- **Prioridad sugerida**: 3630
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="leasing_payables",
        priority=3630,
        required_keywords=[['leasíng', 'léasing', 'leasing', 'leasings', 'leásing'], ['payablés', 'payable', 'payables', 'páyábles'], ['taxs', 'tax', 'táx'], ['asséts', 'assets', 'asset', 'ássets'], ['current', 'currents', 'currént', 'cúrrent']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: leasing, payables, tax, assets, current",
    ),
```

### 359. `accounts_related`
- **Tipo**: revenue
- **Keywords**: accounts, related, companies, insurance
- **Prioridad sugerida**: 3640
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="accounts_related",
        priority=3640,
        required_keywords=[['accoúnts', 'accóunts', 'accounts', 'account', 'áccounts'], ['relateds', 'rélatéd', 'related', 'reláted'], ['companies', 'companíes', 'companie', 'companiés', 'compánies', 'cómpanies'], ['insúrance', 'insurance', 'insurancé', 'ínsurance', 'insuránce', 'insurances']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: accounts, related, companies, insurance",
    ),
```

### 360. `payable_tax`
- **Tipo**: expense
- **Keywords**: payable, tax
- **Prioridad sugerida**: 3650
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="payable_tax",
        priority=3650,
        required_keywords=[['páyáble', 'payable', 'payablé', 'payables'], ['taxs', 'tax', 'táx']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: payable, tax",
    ),
```

### 361. `witholdings`
- **Tipo**: expense
- **Keywords**: witholdings
- **Prioridad sugerida**: 3660
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="witholdings",
        priority=3660,
        required_keywords=[['witholding', 'withóldings', 'wítholdíngs', 'witholdings']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: witholdings",
    ),
```

### 362. `clientes_santina`
- **Tipo**: revenue
- **Keywords**: clientes, santina, 570, honorarios
- **Prioridad sugerida**: 3670
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="clientes_santina",
        priority=3670,
        required_keywords=[['cliente', 'clíentes', 'cliéntés', 'clientes'], ['sántiná', 'santína', 'santina', 'santinas'], ['570s', '570'], ['honorários', 'honoraríos', 'honorario', 'hónórariós', 'honorarios']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: clientes, santina, 570, honorarios",
    ),
```

### 363. `tarjeta_acreedores`
- **Tipo**: revenue
- **Keywords**: tarjeta, acreedores, varios, credito
- **Prioridad sugerida**: 3680
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="tarjeta_acreedores",
        priority=3680,
        required_keywords=[['tárjetá', 'tarjetas', 'tarjéta', 'tarjeta'], ['acréédorés', 'acreedóres', 'acreedore', 'acreedores', 'ácreedores'], ['vários', 'varios', 'vario', 'variós', 'varíos'], ['crédito', 'creditó', 'credito', 'creditos', 'credíto']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: tarjeta, acreedores, varios, credito",
    ),
```

### 364. `anticipo_remuneraciones`
- **Tipo**: revenue
- **Keywords**: anticipo, remuneraciones, 544, 288, iva
- **Prioridad sugerida**: 3690
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="anticipo_remuneraciones",
        priority=3690,
        required_keywords=[['antícípo', 'anticipó', 'ánticipo', 'anticipos', 'anticipo'], ['remuneracione', 'rémunéracionés', 'remuneraciones', 'remuneracíones', 'remúneraciones', 'remuneraciónes', 'remuneráciones'], ['544s', '544'], ['288s', '288'], ['ivá', 'íva', 'iva', 'ivas']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: anticipo, remuneraciones, 544, 288, iva",
    ),
```

### 365. `saldo_segun`
- **Tipo**: revenue
- **Keywords**: saldo, segun, cartola
- **Prioridad sugerida**: 3700
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="saldo_segun",
        priority=3700,
        required_keywords=[['saldos', 'sáldo', 'saldó', 'saldo'], ['seguns', 'segun', 'según', 'ségun'], ['cartóla', 'cártolá', 'cartola', 'cartolas']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: saldo, segun, cartola",
    ),
```

### 366. `mensual_intereses`
- **Tipo**: revenue
- **Keywords**: mensual, intereses, 505, 425
- **Prioridad sugerida**: 3710
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="mensual_intereses",
        priority=3710,
        required_keywords=[['mensual', 'mensúal', 'mensuál', 'mensuals', 'ménsual'], ['íntereses', 'intérésés', 'intereses', 'interese'], ['505s', '505'], ['425', '425s']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: mensual, intereses, 505, 425",
    ),
```

### 367. `victor_padilla`
- **Tipo**: revenue
- **Keywords**: victor, padilla
- **Prioridad sugerida**: 3720
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="victor_padilla",
        priority=3720,
        required_keywords=[['victór', 'víctor', 'victors', 'victor'], ['pádillá', 'padílla', 'padilla', 'padillas']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: victor, padilla",
    ),
```

### 368. `francisco_750`
- **Tipo**: revenue
- **Keywords**: francisco, 750
- **Prioridad sugerida**: 3730
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="francisco_750",
        priority=3730,
        required_keywords=[['franciscó', 'fráncisco', 'francisco', 'franciscos', 'francísco'], ['750', '750s']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: francisco, 750",
    ),
```

### 369. `56301_9999`
- **Tipo**: revenue
- **Keywords**: 56301, 9999, 2020, contabiliza, impto
- **Prioridad sugerida**: 3740
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="56301_9999",
        priority=3740,
        required_keywords=[['56301s', '56301'], ['9999s', '9999'], ['2020s', '2020'], ['cóntabiliza', 'contabiliza', 'contábilizá', 'contabilizas', 'contabílíza'], ['imptos', 'imptó', 'ímpto', 'impto']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: 56301, 9999, 2020, contabiliza, impto",
    ),
```

### 370. `monta_12106`
- **Tipo**: revenue
- **Keywords**: monta, 12106, mal
- **Prioridad sugerida**: 3750
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="monta_12106",
        priority=3750,
        required_keywords=[['mónta', 'montas', 'montá', 'monta'], ['12106s', '12106'], ['mál', 'mal', 'mals']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: monta, 12106, mal",
    ),
```

### 371. `san_12109`
- **Tipo**: revenue
- **Keywords**: san, 12109, pedro
- **Prioridad sugerida**: 3760
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="san_12109",
        priority=3760,
        required_keywords=[['sán', 'sans', 'san'], ['12109s', '12109'], ['pedro', 'pedró', 'pedros', 'pédro']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: san, 12109, pedro",
    ),
```

### 372. `reclasificaciones_depresicaiones`
- **Tipo**: revenue
- **Keywords**: reclasificaciones, depresicaiones
- **Prioridad sugerida**: 3770
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="reclasificaciones_depresicaiones",
        priority=3770,
        required_keywords=[['réclasificacionés', 'reclasificaciones', 'reclasificacione', 'reclasífícacíones', 'reclasificaciónes', 'reclásificáciones'], ['depresicaione', 'depresicaiones', 'depresicáiones', 'depresicaiónes', 'déprésicaionés', 'depresícaíones']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: reclasificaciones, depresicaiones",
    ),
```

### 373. `434`
- **Tipo**: revenue
- **Keywords**: 434
- **Prioridad sugerida**: 3780
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="434",
        priority=3780,
        required_keywords=[['434', '434s']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: 434",
    ),
```

### 374. `protector_prados`
- **Tipo**: revenue
- **Keywords**: protector, prados, ltda, plantacion
- **Prioridad sugerida**: 3790
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="protector_prados",
        priority=3790,
        required_keywords=[['protectors', 'protector', 'protéctor', 'prótectór'], ['pradós', 'prado', 'prádos', 'prados'], ['ltda', 'ltdas', 'ltdá'], ['plantacíon', 'plantacion', 'plantacions', 'plántácion', 'plantación']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: protector, prados, ltda, plantacion",
    ),
```

### 375. `plantas_gallardo`
- **Tipo**: revenue
- **Keywords**: plantas, gallardo, salgado, plantacion, 79hector
- **Prioridad sugerida**: 3800
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="plantas_gallardo",
        priority=3800,
        required_keywords=[['plántás', 'planta', 'plantas'], ['gállárdo', 'gallardo', 'gallardos', 'gallardó'], ['salgadó', 'salgados', 'salgado', 'sálgádo'], ['plantacíon', 'plantacion', 'plantacions', 'plántácion', 'plantación'], ['79hectors', '79hector', '79héctor', '79hectór']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: plantas, gallardo, salgado, plantacion, 79hector",
    ),
```

### 376. `augusto_maturana`
- **Tipo**: revenue
- **Keywords**: augusto, maturana, plantacion
- **Prioridad sugerida**: 3810
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="augusto_maturana",
        priority=3810,
        required_keywords=[['áugusto', 'aúgústo', 'augustó', 'augustos', 'augusto'], ['máturáná', 'maturana', 'matúrana', 'maturanas'], ['plantacíon', 'plantacion', 'plantacions', 'plántácion', 'plantación']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: augusto, maturana, plantacion",
    ),
```

### 377. `pacta_spa`
- **Tipo**: revenue
- **Keywords**: pacta, spa, plantacion, tutores
- **Prioridad sugerida**: 3820
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="pacta_spa",
        priority=3820,
        required_keywords=[['pacta', 'pactas', 'páctá'], ['spa', 'spas', 'spá'], ['plantacíon', 'plantacion', 'plantacions', 'plántácion', 'plantación'], ['tutores', 'tutóres', 'tútores', 'tutorés', 'tutore']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: pacta, spa, plantacion, tutores",
    ),
```

### 378. `plantacion_plantas`
- **Tipo**: revenue
- **Keywords**: plantacion, plantas, 4200593copeval
- **Prioridad sugerida**: 3830
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="plantacion_plantas",
        priority=3830,
        required_keywords=[['plantacíon', 'plantacion', 'plantacions', 'plántácion', 'plantación'], ['plántás', 'planta', 'plantas'], ['4200593copeval', '4200593copéval', '4200593copevals', '4200593copevál', '4200593cópeval']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: plantacion, plantas, 4200593copeval",
    ),
```

### 379. `plantacion_tutores`
- **Tipo**: revenue
- **Keywords**: plantacion, tutores, 4201196copeval
- **Prioridad sugerida**: 3840
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="plantacion_tutores",
        priority=3840,
        required_keywords=[['plantacíon', 'plantacion', 'plantacions', 'plántácion', 'plantación'], ['tutores', 'tutóres', 'tútores', 'tutorés', 'tutore'], ['4201196copéval', '4201196cópeval', '4201196copevals', '4201196copevál', '4201196copeval']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: plantacion, tutores, 4201196copeval",
    ),
```

### 380. `usufructo_roberto`
- **Tipo**: expense
- **Keywords**: usufructo, roberto, tra
- **Prioridad sugerida**: 3850
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="usufructo_roberto",
        priority=3850,
        required_keywords=[['usufructos', 'usufructó', 'úsúfrúcto', 'usufructo'], ['roberto', 'robertos', 'robérto', 'róbertó'], ['tras', 'trá', 'tra']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: usufructo, roberto, tra",
    ),
```

### 381. `cuotas_anuales`
- **Tipo**: revenue
- **Keywords**: cuotas, anuales
- **Prioridad sugerida**: 3860
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="cuotas_anuales",
        priority=3860,
        required_keywords=[['cuotas', 'cuota', 'cuotás', 'cúotas', 'cuótas'], ['ánuáles', 'anuale', 'anuales', 'anualés', 'anúales']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: cuotas, anuales",
    ),
```

### 382. `amortizacion_2020`
- **Tipo**: revenue
- **Keywords**: amortizacion, 2020
- **Prioridad sugerida**: 3870
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="amortizacion_2020",
        priority=3870,
        required_keywords=[['amortizacion', 'amortízacíon', 'amórtización', 'amortizacions', 'ámortizácion'], ['2020s', '2020']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: amortizacion, 2020",
    ),
```

### 383. `2020_sur`
- **Tipo**: revenue
- **Keywords**: 2020, sur
- **Prioridad sugerida**: 3880
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="2020_sur",
        priority=3880,
        required_keywords=[['2020s', '2020'], ['sur', 'surs', 'súr']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: 2020, sur",
    ),
```

### 384. `fernandez_boris`
- **Tipo**: revenue
- **Keywords**: fernandez, boris
- **Prioridad sugerida**: 3890
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="fernandez_boris",
        priority=3890,
        required_keywords=[['fernandezs', 'fernández', 'fernandez', 'férnandéz'], ['bori', 'bóris', 'borís', 'boris']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: fernandez, boris",
    ),
```

### 385. `karina_garrido`
- **Tipo**: revenue
- **Keywords**: karina, garrido
- **Prioridad sugerida**: 3900
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="karina_garrido",
        priority=3900,
        required_keywords=[['karína', 'karinas', 'karina', 'káriná'], ['garridos', 'garrído', 'gárrido', 'garrido', 'garridó']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: karina, garrido",
    ),
```

### 386. `jose_palavecino`
- **Tipo**: revenue
- **Keywords**: jose, palavecino
- **Prioridad sugerida**: 3910
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="jose_palavecino",
        priority=3910,
        required_keywords=[['jóse', 'jose', 'joses', 'josé'], ['palavecinos', 'palavécino', 'palavecino', 'palavecíno', 'palavecinó', 'pálávecino']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: jose, palavecino",
    ),
```

### 387. `carlos_chandia`
- **Tipo**: revenue
- **Keywords**: carlos, chandia
- **Prioridad sugerida**: 3920
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="carlos_chandia",
        priority=3920,
        required_keywords=[['carlós', 'carlo', 'cárlos', 'carlos'], ['chandias', 'chándiá', 'chandia', 'chandía']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: carlos, chandia",
    ),
```

### 388. `resultados_asignado`
- **Tipo**: revenue
- **Keywords**: resultados, asignado, ajuste, estado
- **Prioridad sugerida**: 3930
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="resultados_asignado",
        priority=3930,
        required_keywords=[['resultadós', 'résultados', 'resultado', 'resultados', 'resultádos', 'resúltados'], ['asignados', 'asignadó', 'ásignádo', 'asígnado', 'asignado'], ['ájuste', 'ajustes', 'ajuste', 'ajusté', 'ajúste'], ['estados', 'éstado', 'estadó', 'estádo', 'estado']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: resultados, asignado, ajuste, estado",
    ),
```

### 389. `reclasificacion_gastos`
- **Tipo**: expense
- **Keywords**: reclasificacion, gastos, 2009, 2010
- **Prioridad sugerida**: 3940
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="reclasificacion_gastos",
        priority=3940,
        required_keywords=[['reclásificácion', 'reclasificacions', 'réclasificacion', 'reclasificacion', 'reclasífícacíon', 'reclasificación'], ['gasto', 'gastos', 'gastós', 'gástos'], ['2009', '2009s'], ['2010', '2010s']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: reclasificacion, gastos, 2009, 2010",
    ),
```

### 390. `dif_impto`
- **Tipo**: revenue
- **Keywords**: dif, impto, 1era, cat, at2012
- **Prioridad sugerida**: 3950
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="dif_impto",
        priority=3950,
        required_keywords=[['díf', 'difs', 'dif'], ['imptos', 'imptó', 'ímpto', 'impto'], ['1era', '1erá', '1eras', '1éra'], ['cat', 'cát', 'cats'], ['at2012', 'át2012', 'at2012s']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: dif, impto, 1era, cat, at2012",
    ),
```

### 391. `anticipos_ajuste`
- **Tipo**: revenue
- **Keywords**: anticipos, ajuste, reclasificacion, proveedores
- **Prioridad sugerida**: 3960
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="anticipos_ajuste",
        priority=3960,
        required_keywords=[['antícípos', 'anticipós', 'ánticipos', 'anticipo', 'anticipos'], ['ájuste', 'ajustes', 'ajuste', 'ajusté', 'ajúste'], ['reclásificácion', 'reclasificacions', 'réclasificacion', 'reclasificacion', 'reclasífícacíon', 'reclasificación'], ['proveedores', 'proveedore', 'próveedóres', 'provéédorés']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: anticipos, ajuste, reclasificacion, proveedores",
    ),
```

### 392. `determinado_capital`
- **Tipo**: expense
- **Keywords**: determinado, capital, propio, inicial
- **Prioridad sugerida**: 3970
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="determinado_capital",
        priority=3970,
        required_keywords=[['determínado', 'determinado', 'determinadó', 'determinados', 'determinádo', 'détérminado'], ['capitals', 'capítal', 'cápitál', 'capital'], ['propio', 'propío', 'própió', 'propios'], ['ínícíal', 'iniciál', 'inicial', 'inicials']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: determinado, capital, propio, inicial",
    ),
```

### 393. `pretenciosa_12112`
- **Tipo**: expense
- **Keywords**: pretenciosa, 12112
- **Prioridad sugerida**: 3980
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="pretenciosa_12112",
        priority=3980,
        required_keywords=[['pretenciosas', 'pretencíosa', 'pretenciosa', 'préténciosa', 'pretenciósa', 'pretenciosá'], ['12112', '12112s']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: pretenciosa, 12112",
    ),
```

### 394. `doberman_12116`
- **Tipo**: expense
- **Keywords**: doberman, 12116
- **Prioridad sugerida**: 3990
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="doberman_12116",
        priority=3990,
        required_keywords=[['dóberman', 'dobermans', 'doberman', 'dobérman', 'dobermán'], ['12116', '12116s']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: doberman, 12116",
    ),
```

### 395. `12117`
- **Tipo**: expense
- **Keywords**: 12117
- **Prioridad sugerida**: 4000
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="12117",
        priority=4000,
        required_keywords=[['12117s', '12117']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: 12117",
    ),
```

### 396. `queule_12122`
- **Tipo**: expense
- **Keywords**: queule, 12122
- **Prioridad sugerida**: 4010
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="queule_12122",
        priority=4010,
        required_keywords=[['queules', 'qúeúle', 'queule', 'quéulé'], ['12122s', '12122']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: queule, 12122",
    ),
```

### 397. `12123`
- **Tipo**: expense
- **Keywords**: 12123
- **Prioridad sugerida**: 4020
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="12123",
        priority=4020,
        required_keywords=[['12123', '12123s']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: 12123",
    ),
```

### 398. `luis_silva`
- **Tipo**: expense
- **Keywords**: luis, silva, plantacion, plantas
- **Prioridad sugerida**: 4030
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="luis_silva",
        priority=4030,
        required_keywords=[['lui', 'luís', 'luis', 'lúis'], ['silva', 'silvas', 'silvá', 'sílva'], ['plantacíon', 'plantacion', 'plantacions', 'plántácion', 'plantación'], ['plántás', 'planta', 'plantas']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: luis, silva, plantacion, plantas",
    ),
```

### 399. `135_comisiones`
- **Tipo**: revenue
- **Keywords**: 135, comisiones, pagar, tarjeta
- **Prioridad sugerida**: 4040
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="135_comisiones",
        priority=4040,
        required_keywords=[['135', '135s'], ['comisiones', 'comísíones', 'comisionés', 'cómisiónes', 'comisione'], ['pagar', 'págár', 'pagars'], ['tárjetá', 'tarjetas', 'tarjéta', 'tarjeta']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: 135, comisiones, pagar, tarjeta",
    ),
```

### 400. `pasivos_oxros`
- **Tipo**: revenue
- **Keywords**: pasivos, oxros, iealantes, otros
- **Prioridad sugerida**: 4050
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="pasivos_oxros",
        priority=4050,
        required_keywords=[['pasivos', 'pasivós', 'pásivos', 'pasívos', 'pasivo'], ['oxros', 'óxrós', 'oxro'], ['iéalantés', 'iealante', 'íealantes', 'iealantes', 'ieálántes'], ['ótrós', 'otros', 'otro']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: pasivos, oxros, iealantes, otros",
    ),
```

### 401. `inversiones_alternativas`
- **Tipo**: expense
- **Keywords**: inversiones, alternativas
- **Prioridad sugerida**: 4060
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="inversiones_alternativas",
        priority=4060,
        required_keywords=[['inversiones', 'inversiónes', 'ínversíones', 'inversione', 'invérsionés'], ['álternátivás', 'altérnativas', 'alternativas', 'alternatívas', 'alternativa']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: inversiones, alternativas",
    ),
```

### 402. `part_cia`
- **Tipo**: expense
- **Keywords**: part, cia, cta
- **Prioridad sugerida**: 4070
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="part_cia",
        priority=4070,
        required_keywords=[['part', 'párt', 'parts'], ['ciá', 'cias', 'cia', 'cía'], ['ctá', 'ctas', 'cta']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: part, cia, cta",
    ),
```

### 403. `bosques_csm`
- **Tipo**: expense
- **Keywords**: bosques, csm, ltda
- **Prioridad sugerida**: 4080
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="bosques_csm",
        priority=4080,
        required_keywords=[['bosqués', 'bosques', 'bósques', 'bosqúes', 'bosque'], ['csms', 'csm'], ['ltda', 'ltdas', 'ltdá']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: bosques, csm, ltda",
    ),
```

### 404. `utilidad_perdida`
- **Tipo**: revenue
- **Keywords**: utilidad, perdida, segun, balance
- **Prioridad sugerida**: 4090
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="utilidad_perdida",
        priority=4090,
        required_keywords=[['utilidads', 'utílídad', 'utilidad', 'utilidád', 'útilidad'], ['perdída', 'perdidá', 'perdida', 'pérdida', 'perdidas'], ['seguns', 'segun', 'según', 'ségun'], ['bálánce', 'balancé', 'balance', 'balances']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: utilidad, perdida, segun, balance",
    ),
```

### 405. `goldman_sachs`
- **Tipo**: revenue
- **Keywords**: goldman, sachs, comisiones, pagadas, gasto
- **Prioridad sugerida**: 4100
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="goldman_sachs",
        priority=4100,
        required_keywords=[['goldmans', 'goldmán', 'goldman', 'góldman'], ['sachs', 'sach', 'sáchs'], ['comisiones', 'comísíones', 'comisionés', 'cómisiónes', 'comisione'], ['págádás', 'pagada', 'pagadas'], ['gastó', 'gasto', 'gásto', 'gastos']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: goldman, sachs, comisiones, pagadas, gasto",
    ),
```

### 406. `seguros_generales`
- **Tipo**: expense
- **Keywords**: seguros, generales
- **Prioridad sugerida**: 4110
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="seguros_generales",
        priority=4110,
        required_keywords=[['seguro', 'segúros', 'segurós', 'seguros', 'séguros'], ['generales', 'generáles', 'généralés', 'generale']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: seguros, generales",
    ),
```

### 407. `mercaderias_437`
- **Tipo**: revenue
- **Keywords**: mercaderias, 437, 101, 434, capital
- **Prioridad sugerida**: 4120
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="mercaderias_437",
        priority=4120,
        required_keywords=[['mercaderias', 'mercaderia', 'mercáderiás', 'mercaderías', 'mércadérias'], ['437s', '437'], ['101', '101s'], ['434', '434s'], ['capitals', 'capítal', 'cápitál', 'capital']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: mercaderias, 437, 101, 434, capital",
    ),
```

### 408. `subtotal_hectareas`
- **Tipo**: revenue
- **Keywords**: subtotal, hectareas, productivas
- **Prioridad sugerida**: 4130
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="subtotal_hectareas",
        priority=4130,
        required_keywords=[['súbtotal', 'subtotal', 'subtotál', 'subtótal', 'subtotals'], ['hectarea', 'héctaréas', 'hectareas', 'hectáreás'], ['productívas', 'productivás', 'prodúctivas', 'próductivas', 'productivas', 'productiva']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: subtotal, hectareas, productivas",
    ),
```

### 409. `construccion_parron`
- **Tipo**: revenue
- **Keywords**: construccion, parron, nuevo, materiales
- **Prioridad sugerida**: 4140
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="construccion_parron",
        priority=4140,
        required_keywords=[['construccíon', 'constrúccion', 'construccions', 'cónstrucción', 'construccion'], ['parron', 'párron', 'parrón', 'parrons'], ['nuévo', 'nuevos', 'nuevó', 'núevo', 'nuevo'], ['materiale', 'máteriáles', 'materíales', 'materiales', 'matérialés']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: construccion, parron, nuevo, materiales",
    ),
```

### 410. `licencias_programas`
- **Tipo**: revenue
- **Keywords**: licencias, programas, comput, computacionales
- **Prioridad sugerida**: 4150
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="licencias_programas",
        priority=4150,
        required_keywords=[['licenciás', 'licencia', 'lícencías', 'licencias', 'licéncias'], ['prográmás', 'programas', 'prógramas', 'programa'], ['compút', 'computs', 'comput', 'cómput'], ['computácionáles', 'computacionale', 'computacionalés', 'computacíonales', 'compútacionales', 'computacionales', 'cómputaciónales']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: licencias, programas, comput, computacionales",
    ),
```

### 411. `operacional_resultado`
- **Tipo**: revenue
- **Keywords**: operacional, resultado, totales, margen
- **Prioridad sugerida**: 4160
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="operacional_resultado",
        priority=4160,
        required_keywords=[['operacíonal', 'opéracional', 'óperaciónal', 'operacionals', 'operacional', 'operácionál'], ['resultádo', 'resultadó', 'résultado', 'resultado', 'resultados', 'resúltado'], ['tótales', 'totales', 'totale', 'totáles', 'totalés'], ['margén', 'margens', 'margen', 'márgen']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: operacional, resultado, totales, margen",
    ),
```

### 412. `patrimonio_neto`
- **Tipo**: expense
- **Keywords**: patrimonio, neto, atibas
- **Prioridad sugerida**: 4170
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="patrimonio_neto",
        priority=4170,
        required_keywords=[['patrímonío', 'pátrimonio', 'patrimónió', 'patrimonios', 'patrimonio'], ['netó', 'netos', 'néto', 'neto'], ['atiba', 'atibas', 'átibás', 'atíbas']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: patrimonio, neto, atibas",
    ),
```

### 413. `remuneraciones_631`
- **Tipo**: revenue
- **Keywords**: remuneraciones, 631, 1ssea36oplesa, eridas
- **Prioridad sugerida**: 4180
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="remuneraciones_631",
        priority=4180,
        required_keywords=[['remuneracione', 'rémunéracionés', 'remuneraciones', 'remuneracíones', 'remúneraciones', 'remuneraciónes', 'remuneráciones'], ['631', '631s'], ['1ssea36oplesa', '1ssea36óplesa', '1sséa36oplésa', '1ssea36oplesas', '1sseá36oplesá'], ['erídas', 'eridás', 'erida', 'eridas', 'éridas']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: remuneraciones, 631, 1ssea36oplesa, eridas",
    ),
```

### 414. `aldo_corriente`
- **Tipo**: revenue
- **Keywords**: aldo, corriente, bancaria, rez
- **Prioridad sugerida**: 4190
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="aldo_corriente",
        priority=4190,
        required_keywords=[['aldo', 'áldo', 'aldos', 'aldó'], ['corríente', 'corriente', 'córriente', 'corrientes', 'corriénté'], ['báncáriá', 'bancaria', 'bancaría', 'bancarias'], ['rez', 'rezs', 'réz']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: aldo, corriente, bancaria, rez",
    ),
```

### 415. `123_total`
- **Tipo**: revenue
- **Keywords**: 123, total, pasivo, final, iaass7agtoli29
- **Prioridad sugerida**: 4200
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="123_total",
        priority=4200,
        required_keywords=[['123s', '123'], ['tótal', 'totál', 'totals', 'total'], ['pasivó', 'pasivos', 'pásivo', 'pasívo', 'pasivo'], ['finál', 'finals', 'fínal', 'final'], ['iaass7agtóli29', 'iááss7ágtoli29', 'íaass7agtolí29', 'iaass7agtoli29', 'iaass7agtoli29s']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: 123, total, pasivo, final, iaass7agtoli29",
    ),
```

### 416. `resultado_negativo`
- **Tipo**: revenue
- **Keywords**: resultado, negativo
- **Prioridad sugerida**: 4210
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="resultado_negativo",
        priority=4210,
        required_keywords=[['resultádo', 'resultadó', 'résultado', 'resultado', 'resultados', 'resúltado'], ['negátivo', 'négativo', 'negativo', 'negativó', 'negativos', 'negatívo']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: resultado, negativo",
    ),
```

### 417. `otal_capital`
- **Tipo**: revenue
- **Keywords**: otal, capital, enterado, rebaja, credito
- **Prioridad sugerida**: 4220
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="otal_capital",
        priority=4220,
        required_keywords=[['otals', 'otal', 'ótal', 'otál'], ['capitals', 'capítal', 'cápitál', 'capital'], ['enterados', 'enterado', 'enterádo', 'enteradó', 'éntérado'], ['rebajas', 'rébaja', 'rebaja', 'rebájá'], ['crédito', 'creditó', 'credito', 'creditos', 'credíto']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: otal, capital, enterado, rebaja, credito",
    ),
```

### 418. `gastos_977`
- **Tipo**: revenue
- **Keywords**: gastos, 977, cobrar
- **Prioridad sugerida**: 4230
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="gastos_977",
        priority=4230,
        required_keywords=[['gasto', 'gastos', 'gastós', 'gástos'], ['977', '977s'], ['cóbrar', 'cobrár', 'cobrars', 'cobrar']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: gastos, 977, cobrar",
    ),
```

### 419. `caja_392`
- **Tipo**: revenue
- **Keywords**: caja, 392, cartas
- **Prioridad sugerida**: 4240
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="caja_392",
        priority=4240,
        required_keywords=[['cájá', 'cajas', 'caja'], ['392s', '392'], ['cartas', 'carta', 'cártás']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: caja, 392, cartas",
    ),
```

### 420. `mercaderias_retencion`
- **Tipo**: revenue
- **Keywords**: mercaderias, retencion, categoria, 10120633916
- **Prioridad sugerida**: 4250
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="mercaderias_retencion",
        priority=4250,
        required_keywords=[['mercaderias', 'mercaderia', 'mercáderiás', 'mercaderías', 'mércadérias'], ['retencíon', 'retención', 'retencion', 'réténcion', 'retencions'], ['categoría', 'catégoria', 'categoria', 'cátegoriá', 'categorias', 'categória'], ['10120633916', '10120633916s']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: mercaderias, retencion, categoria, 10120633916",
    ),
```

### 421. `importacion_transito`
- **Tipo**: expense
- **Keywords**: importacion, transito, 245, 807
- **Prioridad sugerida**: 4260
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="importacion_transito",
        priority=4260,
        required_keywords=[['importacions', 'impórtación', 'importácion', 'ímportacíon', 'importacion'], ['transito', 'tránsito', 'transíto', 'transitó', 'transitos'], ['245s', '245'], ['807', '807s']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: importacion, transito, 245, 807",
    ),
```

### 422. `edificios_capital`
- **Tipo**: revenue
- **Keywords**: edificios, capital, propio, 1433522318, rey
- **Prioridad sugerida**: 4270
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="edificios_capital",
        priority=4270,
        required_keywords=[['edificiós', 'edificio', 'édificios', 'edificios', 'edífícíos'], ['capitals', 'capítal', 'cápitál', 'capital'], ['propio', 'propío', 'própió', 'propios'], ['1433522318s', '1433522318'], ['réy', 'rey', 'reys']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: edificios, capital, propio, 1433522318, rey",
    ),
```

### 423. `supermercados_rebajar`
- **Tipo**: revenue
- **Keywords**: supermercados, rebajar
- **Prioridad sugerida**: 4280
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="supermercados_rebajar",
        priority=4280,
        required_keywords=[['supermercadós', 'súpermercados', 'supérmércados', 'supermercado', 'supermercádos', 'supermercados'], ['rebájár', 'rebajars', 'rébajar', 'rebajar']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: supermercados, rebajar",
    ),
```

### 424. `aldo_corriente`
- **Tipo**: revenue
- **Keywords**: aldo, corriente
- **Prioridad sugerida**: 4290
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="aldo_corriente",
        priority=4290,
        required_keywords=[['aldo', 'áldo', 'aldos', 'aldó'], ['corríente', 'corriente', 'córriente', 'corrientes', 'corriénté']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: aldo, corriente",
    ),
```

### 425. `pagos_provisionales`
- **Tipo**: revenue
- **Keywords**: pagos, provisionales, mensuales, 448, 100
- **Prioridad sugerida**: 4300
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="pagos_provisionales",
        priority=4300,
        required_keywords=[['págos', 'pagós', 'pagos', 'pago'], ['próvisiónales', 'provisionalés', 'provisionales', 'provísíonales', 'provisionale', 'provisionáles'], ['ménsualés', 'mensúales', 'mensuale', 'mensuales', 'mensuáles'], ['448s', '448'], ['100s', '100']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: pagos, provisionales, mensuales, 448, 100",
    ),
```

### 426. `activo_fijo`
- **Tipo**: revenue
- **Keywords**: activo, fijo, prestamo, banco, securidy
- **Prioridad sugerida**: 4310
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="activo_fijo",
        priority=4310,
        required_keywords=[['áctivo', 'activó', 'actívo', 'activo', 'activos'], ['fijó', 'fijos', 'fíjo', 'fijo'], ['prestamos', 'préstamo', 'prestamo', 'prestamó', 'prestámo'], ['banco', 'bánco', 'bancos', 'bancó'], ['secúridy', 'sécuridy', 'securidy', 'securídy', 'securidys']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: activo, fijo, prestamo, banco, securidy",
    ),
```

### 427. `vehiculos_190`
- **Tipo**: revenue
- **Keywords**: vehiculos, 190, pasivo, largo
- **Prioridad sugerida**: 4320
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="vehiculos_190",
        priority=4320,
        required_keywords=[['vehiculos', 'vehiculo', 'véhiculos', 'vehiculós', 'vehículos', 'vehicúlos'], ['190', '190s'], ['pasivó', 'pasivos', 'pásivo', 'pasívo', 'pasivo'], ['largos', 'lárgo', 'largó', 'largo']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: vehiculos, 190, pasivo, largo",
    ),
```

### 428. `servicios_bas`
- **Tipo**: revenue
- **Keywords**: servicios, bas, pgresos
- **Prioridad sugerida**: 4330
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="servicios_bas",
        priority=4330,
        required_keywords=[['serviciós', 'servicio', 'sérvicios', 'servícíos', 'servicios'], ['bás', 'bas', 'ba'], ['pgrésos', 'pgresós', 'pgresos', 'pgreso']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: servicios, bas, pgresos",
    ),
```

### 429. `edificios_inmuebles`
- **Tipo**: expense
- **Keywords**: edificios, inmuebles
- **Prioridad sugerida**: 4340
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="edificios_inmuebles",
        priority=4340,
        required_keywords=[['edificiós', 'edificio', 'édificios', 'edificios', 'edífícíos'], ['inmuebles', 'inmúebles', 'inmueble', 'inmuéblés', 'ínmuebles']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: edificios, inmuebles",
    ),
```

### 430. `polo_spa`
- **Tipo**: expense
- **Keywords**: polo, spa, 13104
- **Prioridad sugerida**: 4350
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="polo_spa",
        priority=4350,
        required_keywords=[['póló', 'polos', 'polo'], ['spa', 'spas', 'spá'], ['13104s', '13104']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: polo, spa, 13104",
    ),
```

### 431. `resultados_2017`
- **Tipo**: revenue
- **Keywords**: resultados, 2017, total, estados
- **Prioridad sugerida**: 4360
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="resultados_2017",
        priority=4360,
        required_keywords=[['resultadós', 'résultados', 'resultado', 'resultados', 'resultádos', 'resúltados'], ['2017', '2017s'], ['tótal', 'totál', 'totals', 'total'], ['estádos', 'estadós', 'estados', 'éstados', 'estado']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: resultados, 2017, total, estados",
    ),
```

### 432. `santa_maria`
- **Tipo**: revenue
- **Keywords**: santa, maria, direccion, rendicion, super
- **Prioridad sugerida**: 4370
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="santa_maria",
        priority=4370,
        required_keywords=[['sántá', 'santa', 'santas'], ['maria', 'marias', 'maría', 'máriá'], ['direccion', 'dirección', 'diréccion', 'direccions', 'díreccíon'], ['rendición', 'réndicion', 'rendícíon', 'rendicion', 'rendicions'], ['supers', 'super', 'supér', 'súper']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: santa, maria, direccion, rendicion, super",
    ),
```

### 433. `bancos_prestamos`
- **Tipo**: expense
- **Keywords**: bancos, prestamos, 934
- **Prioridad sugerida**: 4380
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="bancos_prestamos",
        priority=4380,
        required_keywords=[['banco', 'bancós', 'báncos', 'bancos'], ['prestamós', 'prestamos', 'prestámos', 'prestamo', 'préstamos'], ['934', '934s']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: bancos, prestamos, 934",
    ),
```

### 434. `dolares_menor`
- **Tipo**: expense
- **Keywords**: dolares, menor, mayor, valor
- **Prioridad sugerida**: 4390
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="dolares_menor",
        priority=4390,
        required_keywords=[['dolarés', 'dolares', 'dolare', 'dólares', 'doláres'], ['menors', 'ménor', 'menór', 'menor'], ['máyor', 'mayors', 'mayor', 'mayór'], ['valór', 'valor', 'valors', 'válor']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: dolares, menor, mayor, valor",
    ),
```

### 435. `fdo_util`
- **Tipo**: revenue
- **Keywords**: fdo, util, trib, acumuladas
- **Prioridad sugerida**: 4400
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="fdo_util",
        priority=4400,
        required_keywords=[['fdo', 'fdó', 'fdos'], ['útil', 'util', 'utíl', 'utils'], ['tríb', 'trib', 'tribs'], ['acumuladas', 'acumulada', 'acúmúladas', 'ácumuládás']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: fdo, util, trib, acumuladas",
    ),
```

### 436. `prestano_bci`
- **Tipo**: revenue
- **Keywords**: prestano, bci, 123696, c66pabna
- **Prioridad sugerida**: 4410
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="prestano_bci",
        priority=4410,
        required_keywords=[['préstano', 'prestáno', 'prestanó', 'prestano', 'prestanos'], ['bcí', 'bci', 'bcis'], ['123696s', '123696'], ['c66pabnas', 'c66pábná', 'c66pabna']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: prestano, bci, 123696, c66pabna",
    ),
```

### 437. `gastos_generales`
- **Tipo**: revenue
- **Keywords**: gastos, generales, 19315181
- **Prioridad sugerida**: 4420
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="gastos_generales",
        priority=4420,
        required_keywords=[['gasto', 'gastos', 'gastós', 'gástos'], ['generales', 'generáles', 'généralés', 'generale'], ['19315181s', '19315181']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: gastos, generales, 19315181",
    ),
```

### 438. `subtotale_2575499743`
- **Tipo**: revenue
- **Keywords**: subtotale, 2575499743, 2390901598, 1829628222
- **Prioridad sugerida**: 4430
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="subtotale_2575499743",
        priority=4430,
        required_keywords=[['subtótale', 'subtotále', 'súbtotale', 'subtotale', 'subtotales', 'subtotalé'], ['2575499743s', '2575499743'], ['2390901598', '2390901598s'], ['1829628222', '1829628222s']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: subtotale, 2575499743, 2390901598, 1829628222",
    ),
```

### 439. `inpto_renta`
- **Tipo**: expense
- **Keywords**: inpto, renta, 4334333, 10cat6
- **Prioridad sugerida**: 4440
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="inpto_renta",
        priority=4440,
        required_keywords=[['inptó', 'inpto', 'ínpto', 'inptos'], ['rentá', 'rentas', 'rénta', 'renta'], ['4334333s', '4334333'], ['10cat6', '10cat6s', '10cát6']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: inpto, renta, 4334333, 10cat6",
    ),
```

### 440. `4101_fletes`
- **Tipo**: expense
- **Keywords**: 4101, fletes
- **Prioridad sugerida**: 4450
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="4101_fletes",
        priority=4450,
        required_keywords=[['4101', '4101s'], ['fletes', 'flete', 'flétés']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: 4101, fletes",
    ),
```

### 441. `seguro_accidentes`
- **Tipo**: expense
- **Keywords**: seguro, accidentes, 4202, 4102
- **Prioridad sugerida**: 4460
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="seguro_accidentes",
        priority=4460,
        required_keywords=[['seguro', 'seguró', 'segúro', 'séguro', 'seguros'], ['áccidentes', 'accidentes', 'accidente', 'accidéntés', 'accídentes'], ['4202s', '4202'], ['4102', '4102s']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: seguro, accidentes, 4202, 4102",
    ),
```

### 442. `4103_seguros`
- **Tipo**: expense
- **Keywords**: 4103, seguros
- **Prioridad sugerida**: 4470
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="4103_seguros",
        priority=4470,
        required_keywords=[['4103', '4103s'], ['seguro', 'segúros', 'segurós', 'seguros', 'séguros']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: 4103, seguros",
    ),
```

### 443. `4103_gastos`
- **Tipo**: expense
- **Keywords**: 4103, gastos, 341
- **Prioridad sugerida**: 4480
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="4103_gastos",
        priority=4480,
        required_keywords=[['4103', '4103s'], ['gasto', 'gastos', 'gastós', 'gástos'], ['341', '341s']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: 4103, gastos, 341",
    ),
```

### 444. `2109`
- **Tipo**: revenue
- **Keywords**: 2109
- **Prioridad sugerida**: 4490
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="2109",
        priority=4490,
        required_keywords=[['2109s', '2109']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: 2109",
    ),
```

### 445. `servicios_asesorias`
- **Tipo**: expense
- **Keywords**: servicios, asesorias, basicos
- **Prioridad sugerida**: 4500
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="servicios_asesorias",
        priority=4500,
        required_keywords=[['serviciós', 'servicio', 'sérvicios', 'servícíos', 'servicios'], ['asesórias', 'asesoria', 'asesorías', 'asésorias', 'asesorias', 'ásesoriás'], ['basícos', 'basico', 'básicos', 'basicos', 'basicós']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: servicios, asesorias, basicos",
    ),
```

### 446. `embotellacion_gasto`
- **Tipo**: revenue
- **Keywords**: embotellacion, gasto, gastos
- **Prioridad sugerida**: 4510
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="embotellacion_gasto",
        priority=4510,
        required_keywords=[['émbotéllacion', 'embótellación', 'embotellacíon', 'embotellacion', 'embotellácion', 'embotellacions'], ['gastó', 'gasto', 'gásto', 'gastos'], ['gasto', 'gastos', 'gastós', 'gástos']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: embotellacion, gasto, gastos",
    ),
```

### 447. `gasto_mant`
- **Tipo**: revenue
- **Keywords**: gasto, mant, destilatorio, 1117312
- **Prioridad sugerida**: 4520
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="gasto_mant",
        priority=4520,
        required_keywords=[['gastó', 'gasto', 'gásto', 'gastos'], ['mánt', 'mants', 'mant'], ['destilátorio', 'déstilatorio', 'destílatorío', 'destilatorios', 'destilatórió', 'destilatorio'], ['1117312s', '1117312']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: gasto, mant, destilatorio, 1117312",
    ),
```

### 448. `materia_prima`
- **Tipo**: expense
- **Keywords**: materia, prima, 66137878
- **Prioridad sugerida**: 4530
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="materia_prima",
        priority=4530,
        required_keywords=[['máteriá', 'matéria', 'matería', 'materias', 'materia'], ['primas', 'príma', 'primá', 'prima'], ['66137878', '66137878s']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: materia, prima, 66137878",
    ),
```

### 449. `remuneracion_personal`
- **Tipo**: expense
- **Keywords**: remuneracion, personal, perman, permanente101, 002
- **Prioridad sugerida**: 4540
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="remuneracion_personal",
        priority=4540,
        required_keywords=[['remuneracion', 'rémunéracion', 'remuneracíon', 'remuneración', 'remunerácion', 'remúneracion', 'remuneracions'], ['pérsonal', 'personal', 'persónal', 'personál', 'personals'], ['pérman', 'perman', 'permán', 'permans'], ['permánente101', 'permanente101', 'pérmanénté101', 'permanente101s'], ['002s', '002']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: remuneracion, personal, perman, permanente101, 002",
    ),
```

### 450. `remunerac_temporeros`
- **Tipo**: expense
- **Keywords**: remunerac, temporeros
- **Prioridad sugerida**: 4550
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="remunerac_temporeros",
        priority=4550,
        required_keywords=[['remunerác', 'remunerac', 'rémunérac', 'remúnerac', 'remuneracs'], ['témporéros', 'temporeros', 'temporero', 'tempórerós']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: remunerac, temporeros",
    ),
```

### 451. `foliares`
- **Tipo**: expense
- **Keywords**: foliares
- **Prioridad sugerida**: 4560
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="foliares",
        priority=4560,
        required_keywords=[['foliare', 'folíares', 'fóliares', 'foliarés', 'foliares', 'foliáres']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: foliares",
    ),
```

### 452. `costos_contratista`
- **Tipo**: expense
- **Keywords**: costos, contratista
- **Prioridad sugerida**: 4570
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="costos_contratista",
        priority=4570,
        required_keywords=[['cóstós', 'costo', 'costos'], ['contratistas', 'contrátistá', 'contratista', 'contratísta', 'cóntratista']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: costos, contratista",
    ),
```

### 453. `reparaciones_plantaciones`
- **Tipo**: expense
- **Keywords**: reparaciones, plantaciones
- **Prioridad sugerida**: 4580
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="reparaciones_plantaciones",
        priority=4580,
        required_keywords=[['réparacionés', 'repáráciones', 'reparacíones', 'reparaciónes', 'reparaciones', 'reparacione'], ['plantaciónes', 'plantacionés', 'plántáciones', 'plantacione', 'plantacíones', 'plantaciones']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: reparaciones, plantaciones",
    ),
```

### 454. `rep_const`
- **Tipo**: expense
- **Keywords**: rep, const, habitacionales
- **Prioridad sugerida**: 4590
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="rep_const",
        priority=4590,
        required_keywords=[['rép', 'rep', 'reps'], ['cónst', 'consts', 'const'], ['habitacionalés', 'habitacionales', 'habitacionale', 'habitaciónales', 'habítacíonales', 'hábitácionáles']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: rep, const, habitacionales",
    ),
```

### 455. `transporte_carga`
- **Tipo**: expense
- **Keywords**: transporte, carga, corresp
- **Prioridad sugerida**: 4600
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="transporte_carga",
        priority=4600,
        required_keywords=[['tránsporte', 'transportes', 'transporte', 'transpórte', 'transporté'], ['carga', 'cárgá', 'cargas'], ['corresps', 'corresp', 'córresp', 'corrésp']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: transporte, carga, corresp",
    ),
```

### 456. `arriendo_bienes`
- **Tipo**: expense
- **Keywords**: arriendo, bienes, ministeric
- **Prioridad sugerida**: 4610
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="arriendo_bienes",
        priority=4610,
        required_keywords=[['arriéndo', 'árriendo', 'arriendó', 'arriendos', 'arriendo', 'arríendo'], ['bíenes', 'biene', 'biénés', 'bienes'], ['ministerics', 'ministéric', 'ministeric', 'mínísteríc']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: arriendo, bienes, ministeric",
    ),
```

### 457. `sueldos_empresarial`
- **Tipo**: expense
- **Keywords**: sueldos, empresarial
- **Prioridad sugerida**: 4620
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="sueldos_empresarial",
        priority=4620,
        required_keywords=[['sueldos', 'sueldo', 'sueldós', 'súeldos', 'suéldos'], ['émprésarial', 'empresarial', 'empresaríal', 'empresarials', 'empresáriál']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: sueldos, empresarial",
    ),
```

### 458. `ajustes_varios`
- **Tipo**: expense
- **Keywords**: ajustes, varios
- **Prioridad sugerida**: 4630
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="ajustes_varios",
        priority=4630,
        required_keywords=[['ajústes', 'ajustes', 'ajustés', 'ajuste', 'ájustes'], ['vários', 'varios', 'vario', 'variós', 'varíos']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: ajustes, varios",
    ),
```

### 459. `impto_territorial`
- **Tipo**: expense
- **Keywords**: impto, territorial
- **Prioridad sugerida**: 4640
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="impto_territorial",
        priority=4640,
        required_keywords=[['imptos', 'imptó', 'ímpto', 'impto'], ['terrítoríal', 'territorial', 'territórial', 'territorials', 'territoriál', 'térritorial']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: impto, territorial",
    ),
```

### 460. `corr_mon`
- **Tipo**: expense
- **Keywords**: corr, mon, patrimonio
- **Prioridad sugerida**: 4650
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="corr_mon",
        priority=4650,
        required_keywords=[['córr', 'corr', 'corrs'], ['mon', 'món', 'mons'], ['patrímonío', 'pátrimonio', 'patrimónió', 'patrimonios', 'patrimonio']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: corr, mon, patrimonio",
    ),
```

### 461. `reajustes_favorables`
- **Tipo**: revenue
- **Keywords**: reajustes, favorables, desfavorables
- **Prioridad sugerida**: 4660
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="reajustes_favorables",
        priority=4660,
        required_keywords=[['reajuste', 'reájustes', 'réajustés', 'reajústes', 'reajustes'], ['favorable', 'fávorábles', 'favorables', 'favorablés', 'favórables'], ['désfavorablés', 'desfávorábles', 'desfavorable', 'desfavorables', 'desfavórables']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: reajustes, favorables, desfavorables",
    ),
```

### 462. `otros_ing`
- **Tipo**: revenue
- **Keywords**: otros, ing, mercad, bonificad
- **Prioridad sugerida**: 4670
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="otros_ing",
        priority=4670,
        required_keywords=[['ótrós', 'otros', 'otro'], ['ings', 'íng', 'ing'], ['mércad', 'mercád', 'mercads', 'mercad'], ['bonificad', 'bonificads', 'bonífícad', 'bonificád', 'bónificad']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: otros, ing, mercad, bonificad",
    ),
```

### 463. `costo_polla`
- **Tipo**: revenue
- **Keywords**: costo, polla, chilena
- **Prioridad sugerida**: 4680
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="costo_polla",
        priority=4680,
        required_keywords=[['cóstó', 'costo', 'costos'], ['pollas', 'pollá', 'pólla', 'polla'], ['chilená', 'chílena', 'chiléna', 'chilenas', 'chilena']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: costo, polla, chilena",
    ),
```

### 464. `costo_recarga`
- **Tipo**: revenue
- **Keywords**: costo, recarga, telefonica
- **Prioridad sugerida**: 4690
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="costo_recarga",
        priority=4690,
        required_keywords=[['cóstó', 'costo', 'costos'], ['recargas', 'recárgá', 'recarga', 'récarga'], ['téléfonica', 'telefonica', 'telefónica', 'telefonicas', 'telefoníca', 'telefonicá']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: costo, recarga, telefonica",
    ),
```

### 465. `comision_comercio`
- **Tipo**: revenue
- **Keywords**: comision, comercio, asociado
- **Prioridad sugerida**: 4700
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="comision_comercio",
        priority=4700,
        required_keywords=[['cómisión', 'comision', 'comísíon', 'comisions'], ['comércio', 'comercio', 'cómerció', 'comercios', 'comercío'], ['asocíado', 'asociado', 'ásociádo', 'asociados', 'asóciadó']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: comision, comercio, asociado",
    ),
```

### 466. `gastos_repr`
- **Tipo**: revenue
- **Keywords**: gastos, repr, gerencia, pasajes
- **Prioridad sugerida**: 4710
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="gastos_repr",
        priority=4710,
        required_keywords=[['gasto', 'gastos', 'gastós', 'gástos'], ['répr', 'repr', 'reprs'], ['gerencia', 'gerencias', 'gerencía', 'géréncia', 'gerenciá'], ['pasajés', 'pásájes', 'pasaje', 'pasajes']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: gastos, repr, gerencia, pasajes",
    ),
```

### 467. `gastos_hospedaje`
- **Tipo**: revenue
- **Keywords**: gastos, hospedaje, colaciones
- **Prioridad sugerida**: 4720
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="gastos_hospedaje",
        priority=4720,
        required_keywords=[['gasto', 'gastos', 'gastós', 'gástos'], ['hóspedaje', 'hospedaje', 'hospedajes', 'hospedáje', 'hospédajé'], ['colacionés', 'colacione', 'colaciones', 'colacíones', 'cólaciónes', 'coláciones']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: gastos, hospedaje, colaciones",
    ),
```

### 468. `servicios_traslado`
- **Tipo**: revenue
- **Keywords**: servicios, traslado, valores
- **Prioridad sugerida**: 4730
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="servicios_traslado",
        priority=4730,
        required_keywords=[['serviciós', 'servicio', 'sérvicios', 'servícíos', 'servicios'], ['traslado', 'trasladó', 'traslados', 'trásládo'], ['valorés', 'valore', 'valóres', 'válores', 'valores']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: servicios, traslado, valores",
    ),
```

### 469. `recoleccion_residuos`
- **Tipo**: revenue
- **Keywords**: recoleccion, residuos
- **Prioridad sugerida**: 4740
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="recoleccion_residuos",
        priority=4740,
        required_keywords=[['recólección', 'recoleccions', 'récoléccion', 'recoleccíon', 'recoleccion'], ['residuo', 'residúos', 'resíduos', 'residuos', 'residuós', 'résiduos']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: recoleccion, residuos",
    ),
```

### 470. `santander_obligaciones`
- **Tipo**: expense
- **Keywords**: santander, obligaciones, banco, comision
- **Prioridad sugerida**: 4750
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="santander_obligaciones",
        priority=4750,
        required_keywords=[['santanders', 'santander', 'sántánder', 'santandér'], ['obligaciones', 'oblígacíones', 'obligacione', 'obligacionés', 'obligáciones', 'óbligaciónes'], ['banco', 'bánco', 'bancos', 'bancó'], ['cómisión', 'comision', 'comísíon', 'comisions']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: santander, obligaciones, banco, comision",
    ),
```

### 471. `impuesto_primera`
- **Tipo**: revenue
- **Keywords**: impuesto, primera, provisional, categora, aero
- **Prioridad sugerida**: 4760
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="impuesto_primera",
        priority=4760,
        required_keywords=[['impuésto', 'impuesto', 'impuestos', 'impuestó', 'impúesto', 'ímpuesto'], ['prímera', 'primeras', 'priméra', 'primerá', 'primera'], ['provisionals', 'próvisiónal', 'provisional', 'provisionál', 'provísíonal'], ['categoras', 'categora', 'categóra', 'cátegorá', 'catégora'], ['aeros', 'aeró', 'áero', 'aéro', 'aero']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: impuesto, primera, provisional, categora, aero",
    ),
```

### 472. `bbva_scotiabank`
- **Tipo**: expense
- **Keywords**: bbva, scotiabank, banco, linea
- **Prioridad sugerida**: 4770
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="bbva_scotiabank",
        priority=4770,
        required_keywords=[['bbva', 'bbvá', 'bbvas'], ['scotiabank', 'scótiabank', 'scotiábánk', 'scotíabank', 'scotiabanks'], ['banco', 'bánco', 'bancos', 'bancó'], ['lineas', 'linéa', 'línea', 'lineá', 'linea']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: bbva, scotiabank, banco, linea",
    ),
```

### 473. `raps`
- **Tipo**: expense
- **Keywords**: raps
- **Prioridad sugerida**: 4780
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="raps",
        priority=4780,
        required_keywords=[['ráps', 'raps', 'rap']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: raps",
    ),
```

### 474. `maiz_semilla`
- **Tipo**: expense
- **Keywords**: maiz, semilla
- **Prioridad sugerida**: 4790
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="maiz_semilla",
        priority=4790,
        required_keywords=[['maíz', 'maizs', 'maiz', 'máiz'], ['semillas', 'sémilla', 'semillá', 'semílla', 'semilla']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: maiz, semilla",
    ),
```

### 475. `esparragos_esparraguera`
- **Tipo**: expense
- **Keywords**: esparragos, esparraguera
- **Prioridad sugerida**: 4800
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="esparragos_esparraguera",
        priority=4800,
        required_keywords=[['esparrago', 'ésparragos', 'espárrágos', 'esparragós', 'esparragos'], ['ésparraguéra', 'espárráguerá', 'esparraguera', 'esparragueras', 'esparragúera']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: esparragos, esparraguera",
    ),
```

### 476. `iva_retenido`
- **Tipo**: expense
- **Keywords**: iva, retenido, parcial
- **Prioridad sugerida**: 4810
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="iva_retenido",
        priority=4810,
        required_keywords=[['ivá', 'íva', 'iva', 'ivas'], ['retenído', 'retenido', 'réténido', 'retenidos', 'retenidó'], ['parcial', 'párciál', 'parcíal', 'parcials']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: iva, retenido, parcial",
    ),
```

### 477. `retenciones_2da`
- **Tipo**: expense
- **Keywords**: retenciones, 2da, categoria
- **Prioridad sugerida**: 4820
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="retenciones_2da",
        priority=4820,
        required_keywords=[['retencione', 'retenciones', 'retenciónes', 'retencíones', 'réténcionés'], ['2da', '2das', '2dá'], ['categoría', 'catégoria', 'categoria', 'cátegoriá', 'categorias', 'categória']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: retenciones, 2da, categoria",
    ),
```

### 478. `cta_particular`
- **Tipo**: expense
- **Keywords**: cta, particular, edgardo, meynet
- **Prioridad sugerida**: 4830
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="cta_particular",
        priority=4830,
        required_keywords=[['ctá', 'ctas', 'cta'], ['particular', 'párticulár', 'particulars', 'particúlar', 'partícular'], ['edgárdo', 'edgardó', 'edgardo', 'édgardo', 'edgardos'], ['méynét', 'meynet', 'meynets']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: cta, particular, edgardo, meynet",
    ),
```

### 479. `arriendo_quimicos`
- **Tipo**: expense
- **Keywords**: arriendo, quimicos
- **Prioridad sugerida**: 4840
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="arriendo_quimicos",
        priority=4840,
        required_keywords=[['arriéndo', 'árriendo', 'arriendó', 'arriendos', 'arriendo', 'arríendo'], ['quimicos', 'químícos', 'qúimicos', 'quimicós', 'quimico']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: arriendo, quimicos",
    ),
```

### 480. `antimalezas`
- **Tipo**: expense
- **Keywords**: antimalezas
- **Prioridad sugerida**: 4850
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="antimalezas",
        priority=4850,
        required_keywords=[['antímalezas', 'antimaleza', 'ántimálezás', 'antimalezas', 'antimalézas']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: antimalezas",
    ),
```

### 481. `pesa_aaa`
- **Tipo**: revenue
- **Keywords**: pesa, aaa
- **Prioridad sugerida**: 4860
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="pesa_aaa",
        priority=4860,
        required_keywords=[['pésa', 'pesa', 'pesas', 'pesá'], ['aaa', 'aaas', 'ááá']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: pesa, aaa",
    ),
```

### 482. `operacion_pendiente`
- **Tipo**: expense
- **Keywords**: operacion, pendiente
- **Prioridad sugerida**: 4870
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="operacion_pendiente",
        priority=4870,
        required_keywords=[['opéracion', 'operacions', 'operácion', 'operacíon', 'óperación', 'operacion'], ['péndiénté', 'pendientes', 'pendiente', 'pendíente']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: operacion, pendiente",
    ),
```

### 483. `cta_cte`
- **Tipo**: expense
- **Keywords**: cta, cte, trabajadores, auxiliar
- **Prioridad sugerida**: 4880
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="cta_cte",
        priority=4880,
        required_keywords=[['ctá', 'ctas', 'cta'], ['cte', 'ctes', 'cté'], ['trábájádores', 'trabajadore', 'trabajadóres', 'trabajadores', 'trabajadorés'], ['auxiliars', 'aúxiliar', 'auxiliar', 'áuxiliár', 'auxílíar']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: cta, cte, trabajadores, auxiliar",
    ),
```

### 484. `bonificaciones_recuperar`
- **Tipo**: expense
- **Keywords**: bonificaciones, recuperar
- **Prioridad sugerida**: 4890
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="bonificaciones_recuperar",
        priority=4890,
        required_keywords=[['bonífícacíones', 'bonificacionés', 'bónificaciónes', 'bonificaciones', 'bonificacione', 'bonificáciones'], ['recuperár', 'recúperar', 'recuperar', 'récupérar', 'recuperars']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: bonificaciones, recuperar",
    ),
```

### 485. `facturas_reclasificar`
- **Tipo**: expense
- **Keywords**: facturas, reclasificar
- **Prioridad sugerida**: 4900
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="facturas_reclasificar",
        priority=4900,
        required_keywords=[['facturas', 'factura', 'factúras', 'fácturás'], ['reclasificars', 'reclasificar', 'réclasificar', 'reclásificár', 'reclasífícar']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: facturas, reclasificar",
    ),
```

### 486. `general_borgo`
- **Tipo**: revenue
- **Keywords**: general, borgo, 934
- **Prioridad sugerida**: 4910
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="general_borgo",
        priority=4910,
        required_keywords=[['general', 'generals', 'général', 'generál'], ['borgo', 'borgos', 'bórgó'], ['934', '934s']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: general, borgo, 934",
    ),
```

### 487. `asociacion_chilena`
- **Tipo**: revenue
- **Keywords**: asociacion, chilena, 2222, seg, azos6si
- **Prioridad sugerida**: 4920
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="asociacion_chilena",
        priority=4920,
        required_keywords=[['asociacions', 'asociacion', 'asocíacíon', 'asóciación', 'ásociácion'], ['chilená', 'chílena', 'chiléna', 'chilenas', 'chilena'], ['2222', '2222s'], ['segs', 'ség', 'seg'], ['ázos6si', 'azós6si', 'azos6sis', 'azos6sí', 'azos6si']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: asociacion, chilena, 2222, seg, azos6si",
    ),
```

### 488. `30110venta_granel`
- **Tipo**: revenue
- **Keywords**: 30110venta, granel
- **Prioridad sugerida**: 4930
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="30110venta_granel",
        priority=4930,
        required_keywords=[['30110ventas', '30110vénta', '30110venta', '30110ventá'], ['granels', 'gránel', 'granel', 'granél']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: 30110venta, granel",
    ),
```

### 489. `30150intereses_bancos`
- **Tipo**: revenue
- **Keywords**: 30150intereses, bancos
- **Prioridad sugerida**: 4940
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="30150intereses_bancos",
        priority=4940,
        required_keywords=[['30150íntereses', '30150intereses', '30150intérésés', '30150interese'], ['banco', 'bancós', 'báncos', 'bancos']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: 30150intereses, bancos",
    ),
```

### 490. `30290venta_material`
- **Tipo**: revenue
- **Keywords**: 30290venta, material, desecho
- **Prioridad sugerida**: 4950
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="30290venta_material",
        priority=4950,
        required_keywords=[['30290ventas', '30290vénta', '30290ventá', '30290venta'], ['materials', 'máteriál', 'materíal', 'matérial', 'material'], ['désécho', 'desecho', 'desechos', 'desechó']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: 30290venta, material, desecho",
    ),
```

### 491. `30360servicio_vinificacion`
- **Tipo**: revenue
- **Keywords**: 30360servicio, vinificacion
- **Prioridad sugerida**: 4960
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="30360servicio_vinificacion",
        priority=4960,
        required_keywords=[['30360servicios', '30360servicio', '30360servició', '30360servícío', '30360sérvicio'], ['vinificácion', 'vinificación', 'vinificacion', 'vínífícacíon', 'vinificacions']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: 30360servicio, vinificacion",
    ),
```

### 492. `30370ventas_estacas`
- **Tipo**: revenue
- **Keywords**: 30370ventas, estacas, pasto, otros
- **Prioridad sugerida**: 4970
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="30370ventas_estacas",
        priority=4970,
        required_keywords=[['30370venta', '30370véntas', '30370ventas', '30370ventás'], ['estaca', 'éstacas', 'estacas', 'estácás'], ['pastó', 'pásto', 'pastos', 'pasto'], ['ótrós', 'otros', 'otro']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: 30370ventas, estacas, pasto, otros",
    ),
```

### 493. `30491diferencia_precios`
- **Tipo**: expense
- **Keywords**: 30491diferencia, precios, vta
- **Prioridad sugerida**: 4980
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="30491diferencia_precios",
        priority=4980,
        required_keywords=[['30491diferencias', '30491diféréncia', '30491diferenciá', '30491diferencia', '30491díferencía'], ['precio', 'précios', 'preciós', 'precíos', 'precios'], ['vta', 'vtas', 'vtá']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: 30491diferencia, precios, vta",
    ),
```

### 494. `40141merma_proceso`
- **Tipo**: expense
- **Keywords**: 40141merma, proceso, productivo
- **Prioridad sugerida**: 4990
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="40141merma_proceso",
        priority=4990,
        required_keywords=[['40141merma', '40141mérma', '40141mermas', '40141mermá'], ['procesos', 'prócesó', 'proceso', 'procéso'], ['productivos', 'próductivó', 'prodúctivo', 'productívo', 'productivo']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: 40141merma, proceso, productivo",
    ),
```

### 495. `40160gastos_variables`
- **Tipo**: expense
- **Keywords**: 40160gastos, variables, venta
- **Prioridad sugerida**: 5000
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="40160gastos_variables",
        priority=5000,
        required_keywords=[['40160gasto', '40160gastos', '40160gástos', '40160gastós'], ['variables', 'váriábles', 'variable', 'varíables', 'variablés'], ['ventas', 'vénta', 'ventá', 'venta']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: 40160gastos, variables, venta",
    ),
```

### 496. `40165gastos_variables`
- **Tipo**: expense
- **Keywords**: 40165gastos, variables, reproceso, vino
- **Prioridad sugerida**: 5010
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="40165gastos_variables",
        priority=5010,
        required_keywords=[['40165gastós', '40165gástos', '40165gastos', '40165gasto'], ['variables', 'váriábles', 'variable', 'varíables', 'variablés'], ['reprócesó', 'reproceso', 'réprocéso', 'reprocesos'], ['víno', 'vinó', 'vinos', 'vino']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: 40165gastos, variables, reproceso, vino",
    ),
```

### 497. `40166comision_vta`
- **Tipo**: expense
- **Keywords**: 40166comision, vta, uva, vino
- **Prioridad sugerida**: 5020
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="40166comision_vta",
        priority=5020,
        required_keywords=[['40166cómisión', '40166comisions', '40166comísíon', '40166comision'], ['vta', 'vtas', 'vtá'], ['uva', 'uvas', 'úva', 'uvá'], ['víno', 'vinó', 'vinos', 'vino']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: 40166comision, vta, uva, vino",
    ),
```

### 498. `40310diferencias_inventario`
- **Tipo**: expense
- **Keywords**: 40310diferencias, inventario
- **Prioridad sugerida**: 5030
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="40310diferencias_inventario",
        priority=5030,
        required_keywords=[['40310diferencia', '40310diféréncias', '40310diferenciás', '40310diferencias', '40310díferencías'], ['ínventarío', 'invéntario', 'inventario', 'inventarios', 'inventarió', 'inventário']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: 40310diferencias, inventario",
    ),
```

### 499. `40311diferencia_cubicacion`
- **Tipo**: expense
- **Keywords**: 40311diferencia, cubicacion, huinchas
- **Prioridad sugerida**: 5040
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="40311diferencia_cubicacion",
        priority=5040,
        required_keywords=[['40311diféréncia', '40311díferencía', '40311diferencia', '40311diferencias', '40311diferenciá'], ['cubicacion', 'cubicácion', 'cubícacíon', 'cubicacions', 'cúbicacion', 'cubicación'], ['huinchas', 'huinchás', 'húinchas', 'huínchas', 'huincha']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: 40311diferencia, cubicacion, huinchas",
    ),
```

### 500. `40360costo_vta`
- **Tipo**: expense
- **Keywords**: 40360costo, vta, insumo, mat
- **Prioridad sugerida**: 5050
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="40360costo_vta",
        priority=5050,
        required_keywords=[['40360costo', '40360costos', '40360cóstó'], ['vta', 'vtas', 'vtá'], ['insumo', 'ínsumo', 'insumos', 'insúmo', 'insumó'], ['mát', 'mat', 'mats']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: 40360costo, vta, insumo, mat",
    ),
```

### 501. `40410cto_vta`
- **Tipo**: expense
- **Keywords**: 40410cto, vta, agroquim
- **Prioridad sugerida**: 5060
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="40410cto_vta",
        priority=5060,
        required_keywords=[['40410cto', '40410ctos', '40410ctó'], ['vta', 'vtas', 'vtá'], ['agroquim', 'agróquim', 'agroqúim', 'agroquims', 'ágroquim', 'agroquím']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: 40410cto, vta, agroquim",
    ),
```

### 502. `40430otros_egresos`
- **Tipo**: expense
- **Keywords**: 40430otros, egresos
- **Prioridad sugerida**: 5070
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="40430otros_egresos",
        priority=5070,
        required_keywords=[['40430otro', '40430ótrós', '40430otros'], ['egresós', 'égrésos', 'egreso', 'egresos']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: 40430otros, egresos",
    ),
```

### 503. `40431multas`
- **Tipo**: expense
- **Keywords**: 40431multas
- **Prioridad sugerida**: 5080
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="40431multas",
        priority=5080,
        required_keywords=[['40431multa', '40431multas', '40431multás', '40431múltas']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: 40431multas",
    ),
```

### 504. `40460deudores_incobrables`
- **Tipo**: revenue
- **Keywords**: 40460deudores, incobrables
- **Prioridad sugerida**: 5090
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="40460deudores_incobrables",
        priority=5090,
        required_keywords=[['40460deudores', '40460deudore', '40460deudóres', '40460deúdores', '40460déudorés'], ['incobrables', 'íncobrables', 'incobrable', 'incobrablés', 'incóbrables', 'incobrábles']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: 40460deudores, incobrables",
    ),
```

### 505. `40500impuesto_diferido`
- **Tipo**: revenue
- **Keywords**: 40500impuesto, diferido
- **Prioridad sugerida**: 5100
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="40500impuesto_diferido",
        priority=5100,
        required_keywords=[['40500impuesto', '40500impuésto', '40500impúesto', '40500impuestó', '40500ímpuesto', '40500impuestos'], ['diferidos', 'diférido', 'diferidó', 'diferido', 'díferído']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: 40500impuesto, diferido",
    ),
```

### 506. `50040remun_base`
- **Tipo**: expense
- **Keywords**: 50040remun, base, personal
- **Prioridad sugerida**: 5110
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="50040remun_base",
        priority=5110,
        required_keywords=[['50040remuns', '50040remun', '50040rémun', '50040remún'], ['base', 'báse', 'basé', 'bases'], ['pérsonal', 'personal', 'persónal', 'personál', 'personals']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: 50040remun, base, personal",
    ),
```

### 507. `50050sobretiempo_personal`
- **Tipo**: expense
- **Keywords**: 50050sobretiempo, personal
- **Prioridad sugerida**: 5120
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="50050sobretiempo_personal",
        priority=5120,
        required_keywords=[['50050sobretíempo', '50050sobrétiémpo', '50050sobretiempo', '50050sóbretiempó', '50050sobretiempos'], ['pérsonal', 'personal', 'persónal', 'personál', 'personals']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: 50050sobretiempo, personal",
    ),
```

### 508. `50060gratificacion_personal`
- **Tipo**: expense
- **Keywords**: 50060gratificacion, personal
- **Prioridad sugerida**: 5130
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="50060gratificacion_personal",
        priority=5130,
        required_keywords=[['50060grátificácion', '50060gratífícacíon', '50060gratificación', '50060gratificacion', '50060gratificacions'], ['pérsonal', 'personal', 'persónal', 'personál', 'personals']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: 50060gratificacion, personal",
    ),
```

### 509. `50120seguro_acciden`
- **Tipo**: expense
- **Keywords**: 50120seguro, acciden, trabajo
- **Prioridad sugerida**: 5140
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="50120seguro_acciden",
        priority=5140,
        required_keywords=[['50120seguró', '50120segúro', '50120séguro', '50120seguros', '50120seguro'], ['accíden', 'accidén', 'accidens', 'acciden', 'ácciden'], ['trábájo', 'trabajó', 'trabajos', 'trabajo']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: 50120seguro, acciden, trabajo",
    ),
```

### 510. `50130feriado_benef`
- **Tipo**: expense
- **Keywords**: 50130feriado, benef, garantizado
- **Prioridad sugerida**: 5150
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="50130feriado_benef",
        priority=5150,
        required_keywords=[['50130feriádo', '50130feríado', '50130feriado', '50130feriados', '50130fériado', '50130feriadó'], ['benefs', 'benef', 'bénéf'], ['garantizado', 'garantizados', 'garantizadó', 'garantízado', 'gárántizádo']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: 50130feriado, benef, garantizado",
    ),
```

### 511. `50150seguro_salud`
- **Tipo**: expense
- **Keywords**: 50150seguro, salud, complementario
- **Prioridad sugerida**: 5160
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="50150seguro_salud",
        priority=5160,
        required_keywords=[['50150séguro', '50150segúro', '50150seguró', '50150seguro', '50150seguros'], ['salúd', 'sálud', 'saluds', 'salud'], ['complementário', 'complementarios', 'complementario', 'complementarío', 'cómplementarió', 'compléméntario']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: 50150seguro, salud, complementario",
    ),
```

### 512. `50160alimentac_alojam`
- **Tipo**: expense
- **Keywords**: 50160alimentac, alojam, trabajador
- **Prioridad sugerida**: 5170
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="50160alimentac_alojam",
        priority=5170,
        required_keywords=[['50160alimentac', '50160alímentac', '50160aliméntac', '50160alimentacs', '50160álimentác'], ['alójam', 'alojam', 'alojams', 'álojám'], ['trabajadór', 'trabajador', 'trabajadors', 'trábájádor']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: 50160alimentac, alojam, trabajador",
    ),
```

### 513. `50170movilizac_trabajadores`
- **Tipo**: expense
- **Keywords**: 50170movilizac, trabajadores
- **Prioridad sugerida**: 5180
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="50170movilizac_trabajadores",
        priority=5180,
        required_keywords=[['50170movilizác', '50170móvilizac', '50170movilizac', '50170movilizacs', '50170movílízac'], ['trábájádores', 'trabajadore', 'trabajadóres', 'trabajadores', 'trabajadorés']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: 50170movilizac, trabajadores",
    ),
```

### 514. `50190elementos_seguridad`
- **Tipo**: expense
- **Keywords**: 50190elementos, seguridad, prote
- **Prioridad sugerida**: 5190
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="50190elementos_seguridad",
        priority=5190,
        required_keywords=[['50190elemento', '50190éléméntos', '50190elementos', '50190elementós'], ['seguridád', 'seguridads', 'séguridad', 'segúridad', 'segurídad', 'seguridad'], ['protes', 'próte', 'prote', 'proté']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: 50190elementos, seguridad, prote",
    ),
```

### 515. `50200otros_benef`
- **Tipo**: expense
- **Keywords**: 50200otros, benef, trabajadores
- **Prioridad sugerida**: 5200
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="50200otros_benef",
        priority=5200,
        required_keywords=[['50200otros', '50200otro', '50200ótrós'], ['benefs', 'benef', 'bénéf'], ['trábájádores', 'trabajadore', 'trabajadóres', 'trabajadores', 'trabajadorés']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: 50200otros, benef, trabajadores",
    ),
```

### 516. `50351honorarios_serv`
- **Tipo**: revenue
- **Keywords**: 50351honorarios, serv, adm, agricola
- **Prioridad sugerida**: 5210
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="50351honorarios_serv",
        priority=5210,
        required_keywords=[['50351honoraríos', '50351honorários', '50351honorario', '50351hónórariós', '50351honorarios'], ['servs', 'sérv', 'serv'], ['ádm', 'adms', 'adm'], ['agrícola', 'agricola', 'agricóla', 'agricolas', 'ágricolá']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: 50351honorarios, serv, adm, agricola",
    ),
```

### 517. `50390servicios`
- **Tipo**: expense
- **Keywords**: 50390servicios
- **Prioridad sugerida**: 5220
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="50390servicios",
        priority=5220,
        required_keywords=[['50390sérvicios', '50390servicio', '50390serviciós', '50390servicios', '50390servícíos']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: 50390servicios",
    ),
```

### 518. `50410desarrollo_promocion`
- **Tipo**: expense
- **Keywords**: 50410desarrollo, promocion
- **Prioridad sugerida**: 5230
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="50410desarrollo_promocion",
        priority=5230,
        required_keywords=[['50410desárrollo', '50410desarrollos', '50410desarrólló', '50410desarrollo', '50410désarrollo'], ['promocions', 'promocíon', 'prómóción', 'promocion']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: 50410desarrollo, promocion",
    ),
```

### 519. `50490seguros`
- **Tipo**: expense
- **Keywords**: 50490seguros
- **Prioridad sugerida**: 5240
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="50490seguros",
        priority=5240,
        required_keywords=[['50490segurós', '50490seguro', '50490séguros', '50490seguros', '50490segúros']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: 50490seguros",
    ),
```

### 520. `50510arriendos`
- **Tipo**: expense
- **Keywords**: 50510arriendos
- **Prioridad sugerida**: 5250
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="50510arriendos",
        priority=5250,
        required_keywords=[['50510arriendós', '50510arríendos', '50510árriendos', '50510arriendo', '50510arriendos', '50510arriéndos']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: 50510arriendos",
    ),
```

### 521. `50590suministros`
- **Tipo**: expense
- **Keywords**: 50590suministros
- **Prioridad sugerida**: 5260
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="50590suministros",
        priority=5260,
        required_keywords=[['50590suministros', '50590sumínístros', '50590súministros', '50590suministro', '50590suministrós']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: 50590suministros",
    ),
```

### 522. `50630insumos_agricolas`
- **Tipo**: expense
- **Keywords**: 50630insumos, agricolas
- **Prioridad sugerida**: 5270
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="50630insumos_agricolas",
        priority=5270,
        required_keywords=[['50630insumós', '50630ínsumos', '50630insumos', '50630insumo', '50630insúmos'], ['ágricolás', 'agricólas', 'agricola', 'agrícolas', 'agricolas']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: 50630insumos, agricolas",
    ),
```

### 523. `50670amortizacion_intangibles`
- **Tipo**: expense
- **Keywords**: 50670amortizacion, intangibles
- **Prioridad sugerida**: 5280
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="50670amortizacion_intangibles",
        priority=5280,
        required_keywords=[['50670amortizacion', '50670amortizacions', '50670ámortizácion', '50670amortízacíon', '50670amórtización'], ['intangibles', 'intángibles', 'intangiblés', 'íntangíbles', 'intangible']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: 50670amortizacion, intangibles",
    ),
```

### 524. `50691gastos_aceptados`
- **Tipo**: expense
- **Keywords**: 50691gastos, aceptados
- **Prioridad sugerida**: 5290
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="50691gastos_aceptados",
        priority=5290,
        required_keywords=[['50691gastos', '50691gastós', '50691gástos', '50691gasto'], ['aceptado', 'áceptádos', 'aceptadós', 'aceptados', 'acéptados']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: 50691gastos, aceptados",
    ),
```

### 525. `50710provision_gastos`
- **Tipo**: revenue
- **Keywords**: 50710provision, gastos
- **Prioridad sugerida**: 5300
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="50710provision_gastos",
        priority=5300,
        required_keywords=[['50710provision', '50710provísíon', '50710provisions', '50710próvisión'], ['gasto', 'gastos', 'gastós', 'gástos']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: 50710provision, gastos",
    ),
```

### 526. `balance_general`
- **Tipo**: revenue
- **Keywords**: balance, general
- **Prioridad sugerida**: 5310
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="balance_general",
        priority=5310,
        required_keywords=[['bálánce', 'balancé', 'balance', 'balances'], ['general', 'generals', 'général', 'generál']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: balance, general",
    ),
```

### 527. `aporte`
- **Tipo**: revenue
- **Keywords**: aporte
- **Prioridad sugerida**: 5320
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="aporte",
        priority=5320,
        required_keywords=[['aporte', 'áporte', 'aporté', 'apórte', 'aportes']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: aporte",
    ),
```

### 528. `0223_servicios`
- **Tipo**: revenue
- **Keywords**: 0223, servicios, basicos
- **Prioridad sugerida**: 5330
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="0223_servicios",
        priority=5330,
        required_keywords=[['0223', '0223s'], ['serviciós', 'servicio', 'sérvicios', 'servícíos', 'servicios'], ['basícos', 'basico', 'básicos', 'basicos', 'basicós']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: 0223, servicios, basicos",
    ),
```

### 529. `oooooooooooooooooooooo_o1n`
- **Tipo**: revenue
- **Keywords**: oooooooooooooooooooooo, o1n
- **Prioridad sugerida**: 5340
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="oooooooooooooooooooooo_o1n",
        priority=5340,
        required_keywords=[['oooooooooooooooooooooos', 'óóóóóóóóóóóóóóóóóóóóóó', 'oooooooooooooooooooooo'], ['o1n', 'ó1n', 'o1ns']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: oooooooooooooooooooooo, o1n",
    ),
```

### 530. `servicios_contabilidad`
- **Tipo**: expense
- **Keywords**: servicios, contabilidad, contables
- **Prioridad sugerida**: 5350
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="servicios_contabilidad",
        priority=5350,
        required_keywords=[['serviciós', 'servicio', 'sérvicios', 'servícíos', 'servicios'], ['contabílídad', 'contabilidad', 'cóntabilidad', 'contábilidád', 'contabilidads'], ['contábles', 'contable', 'contablés', 'cóntables', 'contables']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: servicios, contabilidad, contables",
    ),
```

### 531. `gasto_instalacion`
- **Tipo**: revenue
- **Keywords**: gasto, instalacion
- **Prioridad sugerida**: 5360
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: ganancia

```python
    _context_rule(
        name="gasto_instalacion",
        priority=5360,
        required_keywords=[['gastó', 'gasto', 'gásto', 'gastos'], ['ínstalacíon', 'instálácion', 'instalacion', 'instalación', 'instalacions']],
        acceptable_columns=["ganancia"],
        semantic_type="revenue",
        financial_statement="income_statement",
        economic_nature="credit",
        presentation="operating",
        expected_side="credit",
        parent_category="ingresos_operacionales",
        base_confidence=0.9,
        observations="Ingreso detectado por palabras clave: gasto, instalacion",
    ),
```

### 532. `proyecto_luminaria`
- **Tipo**: expense
- **Keywords**: proyecto, luminaria, rainier
- **Prioridad sugerida**: 5370
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="proyecto_luminaria",
        priority=5370,
        required_keywords=[['proyectos', 'proyécto', 'proyecto', 'próyectó'], ['lumináriá', 'luminarias', 'lúminaria', 'lumínaría', 'luminaria'], ['rainier', 'raíníer', 'rainiers', 'ráinier', 'rainiér']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: proyecto, luminaria, rainier",
    ),
```

### 533. `productos_agricolas`
- **Tipo**: expense
- **Keywords**: productos, agricolas, 404, 864
- **Prioridad sugerida**: 5380
- **Confianza**: 0.1
- **Cuentas afectadas**: ~2
- **Columna aceptable**: perdida

```python
    _context_rule(
        name="productos_agricolas",
        priority=5380,
        required_keywords=[['prodúctos', 'productos', 'producto', 'próductós'], ['ágricolás', 'agricólas', 'agricola', 'agrícolas', 'agricolas'], ['404', '404s'], ['864s', '864']],
        acceptable_columns=["perdida"],
        semantic_type="expense",
        financial_statement="income_statement",
        economic_nature="debit",
        presentation="operating",
        expected_side="debit",
        parent_category="gastos_operacionales",
        base_confidence=0.9,
        observations="Gasto detectado por palabras clave: productos, agricolas, 404, 864",
    ),
```

## Entradas de Diccionario Propuestas

Total: 2598 entradas

| # | Cuenta Original | Código Estándar | Fuente | Confianza |
|---|---|---|---|---|
| 1 | suelo | ER.01 | knowledge_generator | 0.4 |
| 2 | preparacion | ER.01 | knowledge_generator | 0.4 |
| 3 | camellones | ER.01 | knowledge_generator | 0.4 |
| 4 | administracion | ER.01 | knowledge_generator | 0.4 |
| 5 | gastos | ER.01 | knowledge_generator | 0.4 |
| 6 | generales | ER.01 | knowledge_generator | 0.4 |
| 7 | sueldos | ER.01 | knowledge_generator | 0.4 |
| 8 | habilitacion | ER.01 | knowledge_generator | 0.4 |
| 9 | proyecto | ER.01 | knowledge_generator | 0.4 |
| 10 | pre | ER.01 | knowledge_generator | 0.4 |
| 11 | equipos | ER.01 | knowledge_generator | 0.4 |
| 12 | acum | ER.01 | knowledge_generator | 0.4 |
| 13 | impulsiones | ER.01 | knowledge_generator | 0.4 |
| 14 | diciembre | ER.01 | knowledge_generator | 0.4 |
| 15 | enero | ER.01 | knowledge_generator | 0.4 |
| 16 | corrientes | ER.01 | knowledge_generator | 0.4 |
| 17 | otros | ER.01 | knowledge_generator | 0.4 |
| 18 | activos | ER.01 | knowledge_generator | 0.4 |
| 19 | financieros | ER.01 | knowledge_generator | 0.4 |
| 20 | documentos | ER.01 | knowledge_generator | 0.4 |
| 21 | pagar | ER.01 | knowledge_generator | 0.4 |
| 22 | cobrar | ER.01 | knowledge_generator | 0.4 |
| 23 | materiales | ER.01 | knowledge_generator | 0.4 |
| 24 | oficina | ER.01 | knowledge_generator | 0.4 |
| 25 | aseo | ER.01 | knowledge_generator | 0.4 |
| 26 | explotacion | ER.01 | knowledge_generator | 0.4 |
| 27 | margen | ER.01 | knowledge_generator | 0.4 |
| 28 | ingresos | ER.01 | knowledge_generator | 0.4 |
| 29 | cuentas | ER.01 | knowledge_generator | 0.4 |
| 30 | comerciales | ER.01 | knowledge_generator | 0.4 |
| ... | (2568 más) | ... | ... | ... |

## Entradas Gold Standard Propuestas

Total: 185 entradas

| # | Account Name | Suggested Code | Confidence | Comments |
|---|---|---|---|---|
| 1 |  | ER.01 | 0.4 | Sugerido por Knowledge Generator. Cluster: suelo_preparacion. Tipo: revenue. |
| 2 |  | ER.01 | 0.4 | Sugerido por Knowledge Generator. Cluster: suelo_preparacion. Tipo: revenue. |
| 3 |  | ER.01 | 0.4 | Sugerido por Knowledge Generator. Cluster: administracion_gastos. Tipo: revenue. |
| 4 |  | ER.01 | 0.4 | Sugerido por Knowledge Generator. Cluster: administracion_gastos. Tipo: revenue. |
| 5 |  | ER.01 | 0.4 | Sugerido por Knowledge Generator. Cluster: habilitacion_proyecto. Tipo: revenue. |
| 6 |  | ER.01 | 0.4 | Sugerido por Knowledge Generator. Cluster: habilitacion_proyecto. Tipo: revenue. |
| 7 |  | ER.01 | 0.4 | Sugerido por Knowledge Generator. Cluster: equipos_acum. Tipo: revenue. |
| 8 |  | ER.01 | 0.4 | Sugerido por Knowledge Generator. Cluster: equipos_acum. Tipo: revenue. |
| 9 |  | ER.01 | 0.4 | Sugerido por Knowledge Generator. Cluster: equipos_acum. Tipo: revenue. |
| 10 |  | ER.01 | 0.4 | Sugerido por Knowledge Generator. Cluster: diciembre_enero. Tipo: revenue. |
| 11 |  | ER.01 | 0.4 | Sugerido por Knowledge Generator. Cluster: diciembre_enero. Tipo: revenue. |
| 12 |  | ER.01 | 0.4 | Sugerido por Knowledge Generator. Cluster: diciembre_enero. Tipo: revenue. |
| 13 |  | ER.01 | 0.4 | Sugerido por Knowledge Generator. Cluster: corrientes_otros. Tipo: revenue. |
| 14 |  | ER.01 | 0.4 | Sugerido por Knowledge Generator. Cluster: documentos_pagar. Tipo: revenue. |
| 15 |  | ER.01 | 0.4 | Sugerido por Knowledge Generator. Cluster: materiales_oficina. Tipo: revenue. |
| 16 |  | ER.01 | 0.4 | Sugerido por Knowledge Generator. Cluster: servicio_correo. Tipo: revenue. |
| 17 |  | ER.02 | 0.4 | Sugerido por Knowledge Generator. Cluster: utilidad_perdida. Tipo: expense. |
| 18 |  | ER.02 | 0.4 | Sugerido por Knowledge Generator. Cluster: utilidad_perdida. Tipo: expense. |
| 19 |  | ER.02 | 0.4 | Sugerido por Knowledge Generator. Cluster: utilidad_perdida. Tipo: expense. |
| 20 |  | ER.02 | 0.4 | Sugerido por Knowledge Generator. Cluster: otros_gastos. Tipo: expense. |
| ... | (165 más) | ... | ... | ... |

## Archivos Generados

| Archivo | Contenido |
|---|---|
| `generated_rules.py` | Código Python sugerido para nuevas reglas semánticas |
| `generated_tests.py` | Tests unitarios sugeridos para nuevas reglas y entradas |
| `generated_dictionary_entries.json` | Entradas de diccionario sugeridas |
| `generated_gold_standard.json` | Entradas Gold Standard sugeridas |

---

*Reporte generado automáticamente por Knowledge Generator. Ninguna propuesta ha sido incorporada al proyecto.*
