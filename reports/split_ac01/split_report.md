# Informe de División — AC.01 Caja y Bancos

**Fecha:** 2026-07-10 16:50:16

## Resumen

- Variantes totales AC.01: **1105**
- Clasificadas automáticamente: **152** (13.76%)
- Requieren revisión humana: **953** (86.2%)

## Distribución por Sub-Concepto

| Sub-Concepto | Variantes | % |
|---|---|---|
| AC.01.01 Caja | 20 | 1.8% |
| AC.01.02 Bancos | 109 | 9.9% |
| AC.01.03 Equivalentes al Efectivo | 23 | 2.1% |
| Sin clasificar | 953 | 86.2% |

## Mejora de Cobertura

- Antes: 1 concepto (AC.01) cubriendo **1105** variantes
- Después: **3** sub-conceptos
  - 20 → AC.01.01 Caja
  - 109 → AC.01.02 Bancos
  - 23 → AC.01.03 Equivalentes
  - 953 → Sin clasificar

## Riesgos

1. **Precisión de reglas léxicas:** Las reglas pueden generar falsos positivos en variantes que contengan palabras clave en contextos no financieros (ej. 'Caja de Compensación').
2. **Ruido OCR:** 953 variantes (86.2%) no pudieron clasificarse automáticamente, probablemente debido a ruido OCR o datos mal clasificados en AC.01 original.
3. **Ambigüedad semántica:** Variantes con palabras clave de múltiples sub-conceptos (ej. 'Dep. a Plazo Bancos' tiene tanto 'plazo' como 'banco').
4. **Compatibilidad v1:** AC.01 sigue existiendo como padre. No se modificaron IDs ni datos existentes. Los pipelines que referencian AC.01 continúan funcionando.
