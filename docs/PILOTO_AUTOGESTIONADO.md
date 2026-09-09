# Piloto autogestionado de instalación on-premise

Este procedimiento reproduce la experiencia inicial de una empresa sin usar
Neon ni datos productivos. No constituye aprobación de producción.

## 1. Registrar el candidato

Antes de copiar o instalar el paquete, registre:

| Campo | Valor |
|---|---|
| Commit completo | |
| Fecha y hora | |
| Equipo y sistema operativo | |
| Operador | |
| Carpeta privada de evidencias | |

El repositorio debe estar limpio y el commit debe coincidir con el candidato
aprobado. Detenga la prueba si existen cambios locales inesperados.

## 2. Prueba técnica aislada

Desde la raíz del repositorio:

```bash
docker info
deployment/onprem/scripts/verify-package.sh
deployment/onprem/scripts/smoke-test.sh
```

El resultado esperado es `SMOKE ON-PREMISE (evaluation): APROBADO`. El smoke
construye un proyecto aislado, comprueba HTTPS, persistencia local, reinicio,
respaldo cifrado, restauración y recuperación de salud. Sus volúmenes se
eliminan al finalizar.

## 3. Instalación manual como empresa piloto

No utilice documentos reales de clientes en esta etapa.

```bash
cd deployment/onprem
cp .env.example .env
docker compose -f docker-compose.yml -f docker-compose.evaluation.yml config --quiet
docker compose -f docker-compose.yml -f docker-compose.evaluation.yml up --build -d
docker compose -f docker-compose.yml -f docker-compose.evaluation.yml ps
```

Abra `https://localhost`. La evaluación usa una CA local de Caddy y no incluye
autenticación corporativa. Registre la advertencia del navegador, pero no
desactive controles TLS del paquete.

## 4. Prueba funcional

Ejecute `U01` a `U10` de `docs/UAT_PREPRODUCTIVO_20260908.md` con documentos
públicos, sintéticos o expresamente autorizados. Para cada caso conserve fuera
del repositorio:

- documento y páginas utilizadas;
- período, moneda y escala;
- valores impresos y extraídos;
- clasificación esperada y observada;
- capturas necesarias;
- reporte generado;
- resultado `APROBADO`, `RECHAZADO` o `NO EJECUTADO`;
- incidente, gravedad y responsable.

Una prueba no ejecutada no cuenta como aprobada. Un indicador verde no sustituye
la comparación de cuentas y totales contra el documento.

## 5. Reinicio y recuperación manual

Compruebe que las decisiones de prueba siguen disponibles después de reiniciar:

```bash
docker compose -f docker-compose.yml -f docker-compose.evaluation.yml restart app
docker compose -f docker-compose.yml -f docker-compose.evaluation.yml ps
```

Ejecute después el respaldo y restauración documentados en
`deployment/onprem/README.md`. En evaluación puede usarse una clave temporal;
en producción la clave debe mantenerse fuera del paquete.

## 6. Cierre seguro

```bash
docker compose -f docker-compose.yml -f docker-compose.evaluation.yml down
```

No agregue `.env`, respaldos, documentos, capturas ni reportes privados a Git.
Antes de borrar evidencias, aplique la política de conservación acordada.

## 7. Decisión

El piloto queda `RECHAZADO` si ocurre cualquiera de estos eventos:

- monto, período, moneda o columna incorrectos en el entregable;
- doble contabilización de subtotales;
- reporte definitivo emitido sin certificación;
- pérdida de decisiones o auditoría después de reiniciar;
- restauración que no recupera el estado esperado;
- exposición de datos o acceso no autorizado;
- un caso obligatorio no ejecutado.

El piloto puede quedar `ACEPTADO CON INCIDENCIAS` sólo cuando las incidencias no
afectan cifras, seguridad, trazabilidad, persistencia ni recuperación, y cada
una tiene responsable y plazo. Producción requiere además Gold exacto,
identidad corporativa, controles de red, custodia de claves y aprobación formal.
