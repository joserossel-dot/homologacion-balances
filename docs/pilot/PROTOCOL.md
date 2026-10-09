# Protocolo de piloto interno no mutativo

## Alcance autorizado

- Un solo cliente, identificado solo por un seudónimo en la evidencia.
- Hasta diez documentos PDF o Excel autorizados por el cliente.
- Revisor responsable: José Alfonso Rossel.
- Todo resultado se entrega como borrador revisado por humano.

El piloto no publica clasificaciones, no integra resultados a contabilidad y no
modifica Neon, el diccionario, el catálogo, Gold Standard ni el runtime.

## Preparación de documentos

1. Mantener los originales en una ubicación restringida y fuera del repositorio.
2. No copiar PDF, XLS ni XLSX a Git, `datasets/` o reportes compartidos.
3. Crear un manifiesto desde `manifest.example.json` fuera del repositorio.
4. Asignar un identificador opaco por documento y registrar el SHA-256, sin RUT
   ni razón social cuando no sean indispensables para la revisión.
5. Incluir documentos legibles, autorizados y representativos de las columnas
   ACTIVO, PASIVO, PÉRDIDA y GANANCIA; incluir al menos dos importes negativos y
   dos estructuras de documento distintas.

## Ejecución

Arrancar la aplicación con el guard de piloto activo:

```sh
PILOT_MODE=1 DATABASE_URL= poetry run streamlit run app_validacion.py
```

Con `PILOT_MODE=1`, las decisiones viven solo en la sesión. La interfaz usa el
catálogo y diccionario locales, no instancia Neon, no ejecuta el modo shadow y
no guarda validaciones en Neon o JSON, agrega categorías, aprende en Gold
Standard, promueve runtime o gestiona conocimiento. Mantener `DATABASE_URL=`
evita que el proceso herede una conexión configurada fuera del piloto.

La descarga queda deshabilitada hasta que el revisor confirme en la interfaz
que revisó las cuentas pendientes. El archivo descargado queda nombrado y
marcado como `BORRADOR_PILOTO`; esa marca no sustituye la evidencia de revisión
humana exigida en este protocolo.

Con la aplicación detenida, capturar una línea base de los artefactos protegidos
en una ubicación restringida y externa al repositorio:

```sh
poetry run python scripts/pilot_integrity.py snapshot > /ruta/restringida/piloto-before.json
```

Después de cerrar el piloto, verificar la misma línea base:

```sh
poetry run python scripts/pilot_integrity.py verify /ruta/restringida/piloto-before.json
```

El comando solo emite hashes, tamaños y estados de los artefactos protegidos,
incluidos los archivos auxiliares de SQLite; no incluye contenido de documentos
del cliente. Un resultado distinto de `PASS` obliga a detener el cierre y
revisar la diferencia antes de continuar.

No usar durante el piloto:

- `dataset_manager.py` o `register_existing_files()`, porque escriben el
  registro SQLite de datasets.
- La importación Gold, promoción de runtime o sus comandos con `--apply`.
- El runner de validación o backend que crea reportes o artefactos automáticos.

## Revisión humana y evidencia

José Alfonso Rossel debe revisar el 100% de los entregables y toda cuenta
UNKNOWN, conflicto, reasignación, contra-cuenta o validación fallida. Guardar
fuera del repositorio:

- manifiesto de entradas y hashes;
- salida marcada como borrador;
- decisiones, razones y fecha de revisión;
- SHA del candidato, configuración `PILOT_MODE=1` y resultado de la puerta CI;
- incidencias, exclusiones y decisión de cierre.

## Cierre y detención

Detener el piloto de inmediato si se detecta una escritura no autorizada, una
salida entregada sin revisión humana, una exposición de documentos o un error
contable material sin explicación. Antes y después de cada ejecución, comprobar
que no cambiaron `diccionario.json`, `catalogo_maestro.json`,
`gold_standard.db`, `gold_standard_runtime.db`, `learning_queue.json` ni
`datasets/dataset_registry.db`.

No promover correcciones del piloto a conocimiento persistente sin una revisión
separada y autorización explícita. Adjuntar al cierre el snapshot inicial y el
resultado de verificación final fuera del repositorio.
