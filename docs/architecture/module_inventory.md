# Inventario verificable de arquitectura Python

Fecha de corte: 2026-08-30. Rama observada:
`codex/mejoras-pendientes-20260826`.

## Método

El inventario cuenta archivos `*.py` y líneas físicas con `Path.read_text()`.
Excluye `.git`, `.venv`, `__pycache__` y `tests` de los totales de código de
ejecución. La clasificación se contrastó con:

1. entrypoint desplegado en `Dockerfile` y `render.yaml`;
2. imports desde `app_validacion.py`, `parser_universal.py`, `pipeline/`,
   `scripts/` y `tools/`;
3. banderas en `pipeline/features.py`;
4. imports exclusivos desde pruebas;
5. búsqueda global de consumidores del nombre de módulo.

Las líneas son una medición, no una métrica de calidad. Cambiarán cuando cambie
el código y deben recalcularse antes de una poda posterior.

El control reproducible está en `scripts/audit_module_usage.py`. Para generar
un artefacto JSON determinista:

```bash
python3 scripts/audit_module_usage.py \
  --root . \
  --pretty \
  --output module-usage-audit.json
```

Para usarlo como control de seguridad, sin convertir huérfanos en un fallo
automático:

```bash
python3 scripts/audit_module_usage.py --root . --fail-on-security > module-usage-audit.json
```

El código de salida es `2` sólo si aparece `CERT_NONE` o
`check_hostname = False` en Python de ejecución. Un entrypoint inexistente,
módulo huérfano o módulo sólo usado por pruebas se informa en JSON, pero no
autoriza su borrado ni falla el comando.

## Contrato del JSON

- `entrypoints`: scripts Poetry, comandos Streamlit de Render/Docker y archivos
  con guardia `__main__`, indicando si el módulo existe;
- `modules`: ruta, líneas, imports internos, consumidores runtime/tests,
  entrypoint y estado calculado;
- `findings.nonexistent_entrypoints`: destinos declarados que no existen;
- `findings.tls_bypasses`: bypass TLS prohibidos con archivo, línea y regla;
- `findings.modules_without_consumers`: módulos sin inbound estático;
- `findings.tests_only_modules`: módulos alcanzables desde pruebas, no desde el
  entrypoint productivo;
- `findings.orphan_modules`: módulos fuera de entrypoints productivos, offline,
  shadow y pruebas.

El resultado fija `root` como `.` y ordena claves y listas, por lo que dos
ejecuciones sobre el mismo árbol producen el mismo contenido. No incluye fecha,
ruta absoluta ni estado Git.

### Reglas automáticas de estado

1. `shadow`: ruta superior `shadow/`;
2. `productive`: alcanzable por imports desde un comando Streamlit declarado en
   Render o Docker;
3. `offline`: ruta superior `scripts/`, `tools/` o `deployment/`, o guardia
   `__main__` no productiva;
4. `tests_only`: alcanzable desde imports de pruebas y no productivo;
5. `orphan`: ninguno de los anteriores.

La precedencia está incluida en el JSON. Los imports dinámicos no se resuelven y
el inventario no interpreta si una bandera habilita una función. Esos límites
impiden usar el resultado como poda automática.

## Estados usados

- **productivo**: alcanzable desde Streamlit o un script de operación vigente;
- **shadow**: se ejecuta para observar o medir, sin decidir el resultado final;
- **feature-gated**: importado por el flujo, pero su efecto depende de una
  bandera desactivada por defecto;
- **offline**: herramienta, pipeline alternativo o preparación manual;
- **tests-only**: alcanzable sólo desde pruebas;
- **huérfano**: sin entrypoint ni consumidor encontrado.
- **mixto**: el directorio contiene más de un estado y requiere poda por archivo.

## Totales por familia

| Familia | Archivos | Líneas | Estado comprobado | Evidencia principal |
|---|---:|---:|---|---|
| raíz | 12 | 12.539 | productivo/mixto | Streamlit importa clasificación, reportes, metadatos y reglas; `cargar_datos.py` es offline |
| `adapters` | 9 | 639 | productivo/mixto | `account_adapter` está en pipeline; los demás alimentan Pipeline V2 |
| `config` | 3 | 100 | productivo/huérfano | `regex_rules` es productivo; `config.features` no tiene consumidor de ejecución encontrado |
| `coverage_engine` | 10 | 1.820 | productivo | `pipeline.operational_quality` lo importa |
| `decision` | 3 | 248 | feature-gated | importado por `homologation_pipeline`; bandera desactivada por defecto |
| `decision_engine` | 9 | 703 | tests-only/offline | consumido por adaptador de Pipeline V2 y pruebas |
| `deployment` | 2 | 92 | offline/operación | bootstrap y preflight on-premise |
| `document_context` | 9 | 1.679 | productivo/mixto | calidad operativa y Pipeline V2 |
| `document_intelligence` | 43 | 7.898 | productivo/offline | parser y UI importan extractores y base documental; minería/entrenamiento son offline |
| `gold_standard` | 8 | 1.781 | productivo | importado por Streamlit |
| `interpreters` | 1 | 53 | productivo | pipeline principal y certificador |
| `knowledge` | 1 | 188 | feature-gated | normalizador consumido por clasificador CMCC |
| `knowledge_base` | 15 | 1.971 | huérfano candidato | no se encontró import externo del paquete Python; no confundir con datos JSON del directorio |
| `learning` | 6 | 510 | productivo | importado por pipeline principal |
| `models` | 4 | 287 | productivo | modelos usados por pipeline y adaptadores |
| `orchestrator` | 2 | 74 | tests-only | `HomologationPipelineV2` sólo aparece en pruebas |
| `parsers` | 16 | 2.584 | productivo | importado por parser, UI y pipeline |
| `persistence` | 18 | 1.943 | productivo/en adopción | Neon es productivo; contratos/local/factoría aún no integrados por UI |
| `pipeline` | 6 | 1.419 | productivo/huérfano | homologación y calidad son productivos; `new_pipeline.py` no tiene consumidor encontrado |
| `review` | 8 | 1.550 | productivo/feature-gated | revisión CMCC y presentación de revisión |
| `scripts` | 9 | 2.519 | offline/operación | certificación, auditoría, preflight, attestation, deploy y smoke manual |
| `self_qa_engine` | 11 | 2.126 | productivo | calidad operativa lo importa |
| `semantic` | 11 | 1.290 | feature-gated | pipeline lo importa, matcher desactivado por defecto |
| `shadow` | 1 | 60 | shadow | UI lo ejecuta con `SHADOW_MODE=True` para PDF |
| `src` | 1 | 0 | paquete vacío | sólo permanece `src/api/__init__.py`; ruta insegura retirada |
| `structure_engine` | 9 | 897 | productivo | calidad operativa y extractores lo importan |
| `tools` | 2 | 593 | offline | construcción y minería documental manual |
| `validation` | 17 | 2.182 | productivo | pipeline, UI y certificación |

El código de pruebas medido por separado contiene 39 archivos y 14.612 líneas
en este corte. Los totales anteriores pueden incluir cambios concurrentes de
otros frentes presentes en el mismo worktree.

## Retiro ejecutado

Se retiraron 278 líneas inequívocamente huérfanas:

| Archivo | Líneas retiradas | Motivo verificable |
|---|---:|---|
| `src/api/main.py` | 118 | no era entrypoint; llamaba un método inexistente del orquestador |
| `src/core/orquestador.py` | 32 | sólo lo importaba la API retirada; no coordinaba el pipeline operativo |
| `src/db_repository.py` | 128 | sólo lo importaban los dos anteriores; esquema paralelo y `CERT_NONE` |

La búsqueda global no encontró otros consumidores de `RepositorioDiccionario`
o `PipelineOrquestador`. `scripts/smoke_pipeline.py` sólo los menciona en su
explicación histórica y usa el pipeline vigente.

## Poda propuesta, no ejecutada

1. Evaluar juntos `orchestrator/`, los adaptadores exclusivos de Pipeline V2,
   `decision_engine/` y porciones exclusivas de `document_context/`. No deben
   borrarse por separado mientras las pruebas de la arquitectura V2 sigan
   declarando el comportamiento esperado.
2. Revisar `knowledge_base/*.py` sin borrar los JSON del mismo directorio. No se
   encontró consumidor de ejecución, pero falta una decisión humana sobre CMCC
   y herramientas futuras.
3. Retirar o promover `pipeline/new_pipeline.py`; actualmente no tiene
   consumidor ni prueba específica encontrada.
4. Retirar `config/features.py` si se confirma que la configuración genérica no
   forma parte de una versión futura. Las banderas operativas actuales viven en
   `pipeline/features.py`.
5. El script Poetry inexistente `src.cli:main` fue retirado de `pyproject.toml`;
   una prueba impide volver a publicar ese entrypoint roto.

Estas familias no se eliminaron porque ausencia de import estático no
prueba por sí sola que no exista uso externo o una ruta planificada.
