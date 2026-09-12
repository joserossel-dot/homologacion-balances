# Revalidación de sugerencias del benchmark

Base publicada: `bea81e42ebe2015236f042589195b662c8e7ad44`.
Medición local realizada el 12 de septiembre de 2026, con conexiones de red bloqueadas
por el contexto del benchmark y almacenamiento temporal. No se modificó el catálogo,
el diccionario ni las etiquetas esperadas de los casos.

## Cambio comprobado

El décimo acierto Top-1 es `SYN02`, «Deudores por Ventas Comerciales», cuyo código
esperado preexistente es `AC.03`, «Clientes». El catálogo identifica AC.03 como
activo corriente y el diccionario contiene «Deudores Por Ventas» con ese código.
El informe histórico B2 mostraba `AC.07`, `ANC.05`, `AC.10` como alternativas;
la medición actual muestra `AC.03`, `AC.07`, `ANC.05`.

La cuenta continúa requiriendo revisión: mejorar una sugerencia no equivale a
confirmarla automáticamente. Las pruebas ahora identifican los casos que aportan
cada acierto, además de comprobar los totales y sus denominadores.

## Resultados B2 operativos, 22 casos

| Métrica | Resultado |
| --- | --- |
| Clasificables | 14 |
| Ambiguas, desconocidas y conflicto | 6 |
| Controles aritméticos | 2 |
| Automáticas correctas | 7/14 |
| Automáticas incorrectas o indebidas | 0 |
| Top-1 | 10/14, 71,43 % |
| Top-3 | 12/14, 85,71 % |

Top-1: EX01, EX02, EX03, EX04, EX05, SYN01, SYN02, CA02, TAX02 y PAT01.
Top-3 agrega CA01 y TAX01. SYN03 y UNC01 siguen sin el código esperado en Top-3.
Se conservan los requisitos de abstención y de cero automatizaciones indebidas.

## Límite del experimento A5

El ejecutor `benchmark_classifier_isolated.py` contiene una muestra diferente de
18 casos, usa un umbral experimental de 0,85 e incluye la sugerencia PC.09 para
«Provisión General» en su denominador de 14. No debe presentarse como la misma
muestra ni como una medida de automatización productiva. Sus sugerencias también
dan Top-1 10/14 y Top-3 13/14; ahora devuelve el detalle por caso para permitir
recalcular ambos resultados. No se cambiaron silenciosamente su población ni
sus requisitos históricos para obtener una prueba aprobada.

Estos resultados describen cuentas sintéticas del benchmark y no certifican
documentos reales ni la preparación para producción del proyecto completo.

## Verificación ejecutada

`poetry run pytest tests/experiments/pilot_coverage/test_confidence_benchmark.py tests/experiments/pilot_coverage/test_benchmark_isolated.py -q`

Resultado: **20 pruebas aprobadas en 13,69 segundos**. Incluye aislamiento de
red/entorno, restauración de sockets, taxonomía negativa y las métricas detalladas.
La comprobación de espacios y formato del diff de los tres archivos Python
intervenidos terminó con código 0.
