# Criterio de aceptación comercial por documento

## Propósito

Este criterio traduce el objetivo operativo del piloto a una señal medible por
documento. Mide cuánto trabajo de clasificación llega al analista sin una
decisión humana por cuenta. No autoriza integración, no sustituye la revisión
del analista y no reemplaza los estados técnicos del protocolo interno.

La salida se entrega en
`delivery_readiness.aceptacion_comercial` y, para el informe de corpus, también
en `commercial_acceptance` de cada documento.

## Métrica que se usa para el umbral

El denominador es el número de cuentas relevantes: filas que no son totales,
tienen importe finito y distinto de cero. El numerador es:

```text
automaticas_estrictas + sugeridas_automatizadas
```

El umbral inicial es 60% y queda serializado como `umbral_cobertura`. Puede
configurarse al invocar `evaluar_entregabilidad` con
`umbral_cobertura_comercial`. El reporte conserva por separado el porcentaje
por importe absoluto; ese porcentaje no sustituye el umbral por cantidad de
cuentas.

### Automática estricta

Una cuenta entra en `automaticas_estrictas` sólo si tiene código compatible,
no exige revisión y su método no representa una decisión humana ni una
propagación.

### Sugerida automatizada

Una cuenta entra en `sugeridas_automatizadas` sólo si tiene código compatible,
exige revisión, no proviene de una decisión humana o propagación y alcanza la
confianza mínima configurada. Además, para fallar de forma cerrada, debe
cumplir simultáneamente estas condiciones:

1. Su método pertenece a la allowlist auditada:
   `contextual_accounting_suggestion`,
   `contextual_credit_balance_depreciation`, `current_result_year`,
   `dictionary_exact_contra_pasivo`, `dictionary_fuzzy` o
   `regex_contextual`.
2. Tiene una evidencia o regla legible no vacía en uno de estos campos:
   `evidencia`, `evidence`, `regla`, `rule`, `razon`, `reason` o
   `special_rule`.
3. Su confianza es finita y alcanza el umbral configurado.

La confianza mínima inicial es 0,80 y se serializa como
`umbral_confianza_sugerencia`. Un método desconocido, una traza vacía o una
confianza no finita queda fuera del numerador y se informa por separado para
revisión.

La sugerencia cuenta para dimensionar un paquete de revisión, pero sigue
requiriendo confirmación contable antes de una salida revisada.

## Elementos excluidos del numerador

Los siguientes grupos permanecen visibles en el reporte, pero no aumentan la
cobertura comercial:

- `decisiones_humanas_individuales`: una persona eligió la cuenta.
- `decisiones_humanas_lote`: una persona eligió una categoría para un lote.
- `asistencia_derivada_humano_lote`: propagación con documento de origen del
  mismo lote.
- `asistencia_derivada_humano_historial_confirmado`: propagación con una
  bandera explícita de confirmación histórica. Es evidencia útil, no
  automatización del documento actual.
- `propagacion_sin_traza_confirmada`: propagación sin evidencia suficiente
  para atribuirla a historial confirmado.
- `origin_fallback_en_revision`: categoría residual por columna de origen.
  Siempre se informa para revisión y no se transforma en sugerencia comercial.
- `sugerencias_metodo_no_admitido`: método no incluido en la allowlist
  comercial.
- `sugerencias_sin_evidencia_trazable`: falta una regla o evidencia legible
  asociada a una sugerencia.
- `sugerencias_confianza_insuficiente`: confianza ausente, no finita o bajo el
  umbral configurado.
- `sin_clasificar`, `incompatibles`, `excluidas` y `otras_en_revision`.

Una propagación histórica sólo se marca como tal cuando la fila incluye una de
estas banderas verdaderas: `propagacion_confirmada_historial`,
`propagated_from_confirmed_history` o
`historical_propagation_confirmed`. La ausencia de esa evidencia no permite
contarla como automática ni sugerida.

## Gates que conservan prioridad

Una cobertura de 60% no compensa un problema técnico. Para quedar
`CUMPLE_CRITERIO_COMERCIAL_PARA_REVISION`, el documento debe cumplir todos
estos puntos:

1. La extracción está apta para revisión asistida.
2. El formato tiene estado `SOPORTADO` para ese documento.
3. La cuadratura homologada cuadra.
4. No hay bloqueos finales.
5. La cobertura comercial alcanza el umbral configurado.

`CUMPLE_CRITERIO_COMERCIAL_FINAL` agrega el estado técnico
`LISTO_PARA_INTEGRAR` y cuadratura certificada. Dentro del piloto interno la
salida sigue sujeta a la revisión y al protocolo vigente; este estado no cambia
el alcance no mutativo ni autoriza una integración automática.

Los estados `NO_APTO_POR_GATES_TECNICOS` y
`NO_APTO_POR_COBERTURA_COMERCIAL` incluyen `motivos` y `siguiente_accion`. El
primero se resuelve antes de intentar mejorar clasificación. El segundo se
resuelve sólo incorporando evidencia auditable, por ejemplo una regla exacta,
un código fuente verificable o una entrada de diccionario revisada. No se
resuelve reclasificando decisiones humanas como automáticas.

## Uso en el cierre del piloto

Para cada documento el informe de cierre debe conservar, junto al estado
técnico, los siguientes campos agregados:

- cuentas elegibles;
- automáticas estrictas;
- sugeridas automatizadas;
- cobertura y brecha contra el umbral;
- decisiones humanas y propagaciones, por categoría;
- estado de aceptación comercial, motivos y siguiente acción;
- resultado de los gates de extracción, formato y cuadratura.

El informe no debe usar esta métrica para ocultar revisión pendiente ni para
modificar el diccionario original.
