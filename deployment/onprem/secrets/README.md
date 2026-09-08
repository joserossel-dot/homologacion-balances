# Secretos locales

Antes de iniciar, cree `postgres_password.txt` en este directorio con una
contraseña aleatoria y permisos sólo para el propietario:

```bash
openssl rand -base64 36 > secrets/postgres_password.txt
chmod 600 secrets/postgres_password.txt
```

El `.gitignore` impide versionar el secreto. En una instalación corporativa,
reemplace este archivo por Docker Secrets o el gestor de secretos aprobado por
el cliente.
