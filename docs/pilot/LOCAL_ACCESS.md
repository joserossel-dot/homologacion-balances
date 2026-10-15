# Cuentas locales y aprobación de accesos

Este flujo usa una base SQLite privada fuera del repositorio. Guarda hashes de
contraseña, solicitudes, roles, equipos, auditoría y las asignaciones explícitas
del diccionario privado de cada equipo. No guarda PDFs, balances, resultados
extraídos ni datos de clientes.

## Preparación inicial

En el equipo que ejecuta la aplicación, crear una única cuenta administradora:

```bash
poetry run python scripts/bootstrap_local_admin.py
```

El comando solicita el usuario, nombre visible y contraseña en la terminal. La
contraseña no se muestra ni se escribe en Git. La base se crea por defecto en
`~/Library/Application Support/HomologacionBalances/local_accounts.sqlite3`,
con permisos privados.

## Inicio protegido

Iniciar Streamlit con `LOCAL_ACCESS_MODE=1`, conservando las variables del
piloto que ya correspondan a la ejecución:

```bash
LOCAL_ACCESS_MODE=1 poetry run streamlit run app_validacion.py
```

Sin una cuenta administradora, la aplicación no procesa balances y muestra el
comando de preparación inicial.

## Flujo de trabajo

1. La persona crea una solicitud con usuario, nombre, contraseña y equipo
   solicitado opcional.
2. La solicitud queda en estado pendiente y no permite iniciar sesión.
3. El administrador crea o selecciona un equipo y aprueba o rechaza la
   solicitud.
4. Al aprobar, el administrador asigna uno de estos roles: Ingreso de datos,
   Analista o Jefatura.
5. La base registra la solicitud, aprobación, reasignación, deshabilitación y
   creación de equipos en una auditoría append-only.

El administrador inicial es la única cuenta administradora creada por este
flujo. Las aprobaciones ordinarias no pueden crear otro administrador.

La interfaz aplica el rol al cargar balances y a las vistas disponibles. En
particular, Ingreso de datos puede cargar su propia sesión, Analista y
Jefatura solo reciben vistas de revisión compatibles y el administrador
mantiene las vistas de configuración global.

## Diccionario privado por equipo

El diccionario base se conserva como referencia común y se lee en modo de solo
lectura. Cada equipo puede tener una superposición privada, guardada en la
misma base local protegida:

1. Analista registra una propuesta de cuenta y código estándar para su equipo.
2. Jefatura activa o revoca la propuesta. Sólo las asignaciones activas se
   usan al clasificar balances de ese mismo equipo.
3. Jefatura puede enviarla a revisión administrativa.
4. El Administrador aprueba o rechaza la incorporación futura después de su
   análisis.

La aprobación no modifica Neon, `diccionario.json` ni el diccionario base. La
incorporación al original debe ejecutarse después mediante un proceso separado,
explícito y auditado. Durante el piloto no hay propagación automática ni
aprendizaje desde estas asignaciones.

## Límite de este piloto

Las cuentas controlan el acceso a la aplicación y a la administración de
identidades. Los balances todavía son temporales por sesión, por lo que no se
habilita aún la edición de una carga hecha por otra persona. Los roles que no
pueden cargar no reciben una carga ajena como sustituto. Esa funcionalidad
requiere un almacén compartido de trabajo aprobado separadamente.
