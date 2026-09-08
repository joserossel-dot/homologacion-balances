# Controles de seguridad para publicación

## Alcance

Estos controles protegen el repositorio y la ruta de publicación. No reemplazan
la seguridad del nodo on-premise ni autorizan el uso de datos reales.

## Línea base auditada el 29 de agosto de 2026

Se verificó mediante Git y la API pública de GitHub:

- el repositorio remoto es público;
- `main` apunta a `ab7b81d` y no contiene workflows bajo `.github`;
- `codex/mejoras-pendientes-20260826` apunta a `c70e60e` y contiene únicamente
  `release-gate.yml`;
- por lo tanto, los controles descritos aquí todavía no están activos mientras
  estos cambios no sean revisados, publicados e integrados en la rama usada.

No se pudo verificar la protección de ramas con la API pública porque ese
endpoint exige autenticación. La consulta pública de ejecuciones de Actions
respondió con error 502 durante la auditoría. Ambos puntos deben comprobarse en
la interfaz administrativa antes de aprobar el lanzamiento.

## Controles versionados

El flujo `Security checks` ejecuta cuatro verificaciones independientes:

1. Gitleaks revisa el historial completo en pushes, pull requests y semanalmente.
2. `pip-audit` contrasta las versiones de `poetry.lock` con vulnerabilidades
   conocidas.
3. Dependency Review bloquea pull requests que introduzcan vulnerabilidades de
   severidad alta o crítica.
4. CodeQL analiza Python con las consultas `security-extended`.

Las acciones de terceros están fijadas a un SHA concreto y los workflows parten
con permiso `contents: read`. CodeQL recibe adicionalmente sólo
`security-events: write`, necesario para publicar sus resultados.

Dependabot revisa semanalmente dependencias Python y acciones de GitHub. Las
actualizaciones mayores quedan separadas para revisión humana.

## Configuración administrativa pendiente en GitHub

La configuración dentro del repositorio no puede activar por sí sola estos
controles administrativos. Antes de producción se debe verificar en GitHub:

- autenticación de dos factores para toda cuenta con acceso de escritura;
- Dependency Graph y Dependabot alerts habilitados;
- secret scanning y push protection habilitados;
- code scanning habilitado y con resultados visibles;
- rama `main` protegida;
- rama de lanzamiento protegida mientras sea fuente de despliegue;
- pull request obligatorio y al menos una aprobación;
- checks `Security checks` y `Release gate` obligatorios;
- prohibición de force push y eliminación de ramas protegidas;
- aprobación manual del environment de producción;
- revisión de que el repositorio pueda permanecer público sin exponer datos
  derivados de balances reales.

## Gate privado

El release gate exige que `PRIVATE_RELEASE_CERTIFIED_COMMIT` coincida exactamente
con el SHA que se intenta desplegar. El valor sólo debe actualizarse después de
ejecutar fuera de GitHub la matriz privada y los Gold aprobados. Los documentos
privados no se suben al repositorio ni como artefactos de Actions.

## Operación ante hallazgos

Un hallazgo de secreto exige rotar la credencial antes de limpiar el historial.
Eliminar el texto del commit no invalida una credencial ya expuesta.

Una vulnerabilidad sin versión corregida debe registrarse con responsable,
impacto, mitigación y fecha de revisión. No se debe omitir desde el workflow sin
una excepción documentada y acotada al identificador exacto.

## Verificación por lanzamiento

Antes de aprobar un despliegue:

1. Confirmar que el commit certificado es la cabeza remota de la rama.
2. Confirmar que la suite completa terminó sin fallas.
3. Confirmar que los cuatro jobs de seguridad terminaron correctamente.
4. Confirmar la recertificación privada para el mismo SHA.
5. Confirmar que no existen alertas críticas o altas abiertas sin aceptación.
6. Registrar el SHA desplegado y conservar el rollback anterior.
