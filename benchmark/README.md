# Benchmark de Certificación

Benchmark independiente sobre balances NO utilizados para entrenamiento.

## Dataset

`datasets/HOLDOUT/` — 20 balances tributarios chilenos en PDF.

Seleccionados explícitamente como conjunto de validación no visto durante desarrollo. No pueden usarse para entrenar reglas, descubrir variantes, ampliar diccionario ni modificar CMCC.

## Composición del dataset

- 20 archivos PDF
- 18 empresas distintas
- Años: 2011–2020
- Cuentas totales: 2.717
- Documentos OCR: 0

## Requisitos

```bash
cd homologacion-balances
pip install -r requirements.txt  # o poetry install
```

## Ejecución

```bash
python3 benchmark/benchmark_runner.py
```

Salida:
- `benchmark/benchmark_results.csv` — métricas por archivo
- `benchmark/dataset_manifest.csv` — inventario del dataset
- `benchmark/benchmark_summary.md` — reporte consolidado

## Qué mide

| Métrica | Descripción |
|---|---|
| archivo | Nombre del archivo procesado |
| tiempo_procesamiento_s | Segundos totales |
| cuentas_detectadas | Cuentas extraídas por el parser |
| cuentas_homologadas | Cuentas con código asignado |
| cuentas_ignoradas | Cuentas sin movimiento (monto 0/Nones) |
| cuentas_desconocidas | Cuentas sin clasificación posible |
| errores | Excepciones durante el procesamiento |
| warnings | Advertencias del pipeline |
| precision_extraccion | Proporción de cuentas con confianza >= 0.7 |
| precision_homologacion | Proporción de clasificadas sobre total extraído |
| metodos_usados | Distribución de métodos de clasificación |
| learning_hits | Cuentas clasificadas vía Gold Standard |

## Notas

- No se requiere gold standard etiquetado para HOLDOUT.
- No se modifica ningún archivo del pipeline ni del parser.
- Los resultados son reproducibles ejecutando nuevamente el runner.
