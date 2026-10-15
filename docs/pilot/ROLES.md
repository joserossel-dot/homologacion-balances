# Roles y límites de acceso

Este documento define cuatro roles. Aunque la solicitud inicial enumera tres,
incluye cuatro responsabilidades distintas: ingreso de datos, análisis,
jefatura y administración.

## Principio de aplicación

La política se implementa en `access_control.py` y falla cerrada. Una interfaz
que oculte botones no constituye control de acceso. La aplicación debe recibir
una identidad autenticada y un `team_id` confiables antes de invocar la
política.

| Rol | Alcance | Puede | No puede |
| --- | --- | --- | --- |
| Ingreso de datos | Sus propios registros de su equipo | Cargar, ver, editar y enviar sus datos | Clasificar, revisar, aprobar entregas o cambiar el diccionario |
| Analista | Cuentas y paquetes de revisión de su equipo | Clasificar, revisar, proponer asignaciones para el diccionario de su equipo y exportar el paquete de revisión | Editar ingresos de otras personas, activar o revocar una asignación, aprobar entregas o cambiar el diccionario original |
| Jefatura | Todo el equipo | Ver y modificar todos los ingresos del equipo, revisar, aprobar la entrega, activar o revocar asignaciones del equipo y enviarlas a revisión administrativa | Cruzar a otro equipo, cambiar el diccionario original o administrar roles |
| Administrador | Todos los equipos y la configuración | Gestionar roles, equipos, configuración y revisar propuestas de incorporación al diccionario original, además de todas las capacidades operativas | Borrar el historial de auditoría o incorporar automáticamente una propuesta al diccionario original |

## Diccionario y trazabilidad

Cada equipo opera una superposición privada sobre el diccionario base. El
ciclo es: Analista propone, Jefatura activa o revoca dentro de su equipo,
Jefatura envía una asignación activa a revisión y el Administrador la aprueba
o rechaza para una incorporación posterior. La aprobación administrativa no
escribe Neon, `diccionario.json` ni cambia el diccionario original.

Una revocación no es borrado físico. Se conserva con actor, equipo, fecha,
motivo y el estado previo en un historial append-only. La jefatura sólo puede
actuar sobre filas con su propio `team_id`; el Administrador puede inspeccionar
todos los equipos. La incorporación efectiva al diccionario original debe ser
un proceso separado, explícito y auditado.

## Cuentas locales

La aplicación incorpora una capa local de solicitudes, aprobación, rol y
equipo cuando se inicia con `LOCAL_ACCESS_MODE=1`. El administrador inicial se
crea una sola vez con `scripts/bootstrap_local_admin.py`; no se solicita ni se
guarda una contraseña en el repositorio. Las solicitudes no eligen rol: el
administrador asigna Ingreso de datos, Analista o Jefatura junto con un equipo.

La capa de cuentas y las asignaciones privadas de equipo se guardan fuera del
repositorio. No almacenan PDFs, balances ni resultados extraídos. Las
asignaciones de equipo son configuración local explícitamente aprobada, no
aprendizaje automático: nunca actualizan el diccionario original durante el
piloto.

## Límite actual de colaboración

Los balances del piloto viven únicamente en la sesión temporal del navegador.
Por eso aún no existe un caso compartido que una jefatura pueda editar desde
otra cuenta. Esa capacidad se mantiene bloqueada hasta contar con un almacén
de trabajo por equipo, con `team_id`, propietario y auditoría de cada cambio.
