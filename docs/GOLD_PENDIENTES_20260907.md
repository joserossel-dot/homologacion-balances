# Recertificación Gold: pendientes comprobados

Fecha: 2026-09-07. Worktree candidato: `homologacion-balances-pendientes-20260826`.
Esta medición corresponde a cambios locales sobre el candidato, no a un release publicado.

## Resultado integrado posterior a la política global

El usuario aprobó que las tres decisiones contables rijan para balances futuros.
La política está implementada localmente y documentada en
`POLITICA_GLOBAL_CLASIFICACION_20260907.md`; no se ha sincronizado Neon.

La ejecución `/tmp/onprem-gold-final-20260907.json` separa ahora:

| Caso | Certificación técnica de detalle y controles | Comparación Gold exacta |
| --- | --- | --- |
| ABS | parcial | rechazada |
| Cosemar | certificada | rechazada |
| Purefruit | certificada | rechazada |

Gold completo sigue **0/3**, mientras la certificación técnica por secciones,
períodos y resultados alcanza **2/3**. No equivale a autorización de producción.
Permanecen 97 filas con diferencias: 83 diferencias de método, 37 de confianza
y una de código (campos superpuestos). El único código diferente es Purefruit,
fila 27: la nueva política global produce PNC.05 donde el Gold histórico decía
PNC.01. Las tres divergencias originalmente consultadas al usuario están resueltas.
No se modificaron los libros históricos ni sus métodos/confianzas para aprobarlos.

El certificador comprueba resultados bruto, antes de impuestos y neto por año,
impuestos con su signo, controles de operaciones continuadas y discontinuadas
en orden y sin doble conteo. Operaciones discontinuadas no nulas sin detalle,
atribuciones y otros controles sin respaldo suficiente conservan estado parcial.
ABS sigue bloqueado por confianza 0,75 y controles de resultado integral aún
fuera del alcance acreditado. La interfaz utiliza la fuente completa y vincula
la certificación final a códigos, estado de revisión e importes.

La comparación Gold de métodos/confianzas requiere una revisión de procedencia
y una nueva versión trazable de la referencia; no son reclasificaciones contables.
Schema 1 no certifica jerarquía. Falta también aceptación con documentos reales
en la interfaz y el entorno productivo.

## Resultado anterior a la política global (histórico)

Ejecución real de `scripts/certify_local_corpus.py` con el manifiesto
`tests/fixtures/private_gold_candidate_matrix.json` y los libros privados revisados.
Resultado: **0/3**, salida del proceso **1**. Los tres documentos terminan
`parcial`; ninguno cumple la expectativa `certificada`.

| Caso | Filas extraídas | Filas distintas de Gold | Código distinto | Método distinto | Confianza distinta |
| --- | ---: | ---: | ---: | ---: | ---: |
| ABS | 37 | 37 | 1 | 23 | 37 |
| Cosemar | 42 | 32 | 1 | 32 | 0 |
| Purefruit | 41 | 28 | 1 | 28 | 0 |

Son 97 filas distintas. Las columnas de diferencias se superponen y no deben
sumarse como si fueran filas independientes. No se detectaron filas faltantes
ni adicionales, ni diferencias de monto, períodos, origen, columnas contables,
marca de total o revisión dentro del contrato schema 1 de estos libros.
Schema 1 no compara la jerarquía contable; esta ejecución no acredita ese campo.

## Tres decisiones contables concretas

| Caso | Cuenta | Línea fuente | Código runtime | Código aprobado en Gold |
| --- | --- | ---: | --- | --- |
| ABS | Otros activos financieros | 7 | AC.02 | AC.08 |
| Cosemar | Otros pasivos financieros no corrientes | 38 | PNC.01 | PNC.05 |
| Purefruit | Costos de distribución | 48 | ER.05 | ER.04 |

La revisión humana ya existe en los libros. No corresponde sustituirla por
la decisión automática. Falta determinar si cada selección es una excepción
del documento o una política global. Con esa definición se puede representar
su alcance y reproducirla en el runtime sin modificar otras empresas.

## Diferencias de procedencia y un bloqueo independiente

Los 83 cambios de método corresponden al uso actual de
`audited_statement_label` frente a métodos históricos del Gold, incluidos
`origin_fallback`, `regex_contextual` y valores vacíos. ABS presenta además
37 cambios de confianza de extracción de `1.0` a `0.75`, coherentes con la
advertencia actual de reconstrucción de texto nativo fragmentado.

El comparador exige método y confianza expresamente. Las pruebas actuales
también verifican este contrato. Quitarlos o copiar los valores actuales al
Gold sin revisión rebajaría el control. Se necesita una revisión trazable de
procedencia, o una decisión explícita y versionada sobre qué contrato se desea
certificar; no hay autorización implícita para aprobar cambios históricos.

Existe un bloqueo adicional a las diferencias de Gold: la ruta
`classified_totals` del parser conserva el estado `parcial` aun cuando la
ecuación final impresa cuadra. `certify()` toma ese estado de extracción y
después ejecuta la clasificación. En esta medición la clasificación reporta
23/32/28 cuentas automáticas y cero pendientes, pero el estado de extracción
sigue siendo parcial. Resolver los tres códigos no basta para obtener 3/3.

El siguiente trabajo técnico debe integrar la recertificación completa con
la clasificación final y sus controles, con pruebas que rechacen totales
correctos acompañados de detalle incorrecto. No debe promoverse `parcial`
únicamente porque la clasificación no tenga pendientes.

## Evidencia y reproducción

Reporte privado de esta ejecución: `/tmp/gold-pending-20260907.json`.
Es un artefacto temporal que debe archivarse en el repositorio privado de
evidencias antes de usarlo en una aprobación de release.

```sh
python3 scripts/certify_local_corpus.py \
  /Users/josealfonsorossel/Downloads/homologacion-balances/recertificacion_gold_20260827/documents \
  --manifest tests/fixtures/private_gold_candidate_matrix.json \
  --gold-root /Users/josealfonsorossel/Downloads/homologacion-balances/recertificacion_gold_20260827/gold \
  --output /tmp/gold-pending-20260907.json \
  --document-timeout-seconds 90

python3 -m pytest tests/test_corpus_certification.py -q
```

Pruebas del certificador: **34 aprobadas en 3,17 segundos**. No se modificaron
el comparador, las decisiones humanas, el catálogo, el parser ni los libros
Gold durante esta revisión. La suite verde no cambia el resultado Gold 0/3.

## Avance técnico posterior de esta jornada

Se agregó `certificar_clasificado_final` al parser y su llamada posterior a
clasificación en el certificador del corpus. Su alcance certificado es detalle
de balance por secciones: exige moneda única, años explícitos, importes finitos
por cada período, controles impresos, cobertura completa y clasificación
compatible ligada a la fila fuente. La evidencia insuficiente conserva estado
parcial; no se compara una suma incompleta como si fuese un descuadre probado.

Los controles del estado de resultados aún no están cubiertos por esta función.
Por ello no se promocionan documentos que los incluyan. La función se integró
posteriormente en la interfaz antes del control de emisión: conserva fuente
completa ligada al hash documental, páginas y períodos; rechaza detalle
filtrado, excluido, duplicado o sin fuente. Los certificados finales vinculan
además códigos y revisión, conservando el contrato previo para ocho columnas.
Cambiar una clasificación exige evaluar nuevamente el detalle, no sólo renovar
su digest. Falta verificar este flujo con los documentos reales mediante UI.
No se declara cerrada la recertificación integral.

El control final acredita compatibilidad de sección y existencia del código
en el catálogo, no exactitud semántica entre dos códigos de la misma sección.
Esa exactitud sigue dependiendo de Gold y de las decisiones humanas aprobadas.

Prueba posterior: 43 aprobadas (9 nuevas y 34 existentes). Reproducción privada
en `/tmp/gold-final-detail-20260907.json`: 0/3, los tres parciales. ABS conserva
revisión de extracción por confianza 0,75; Cosemar y Purefruit incluyen
controles/resultados fuera del alcance certificado. Permanecen las diferencias
Gold de código y procedencia anteriores, sin alterar los libros esperados.
