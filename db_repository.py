import json
import os
import ssl
from pathlib import Path

try:
    import asyncpg
except ImportError:
    asyncpg = None


class RepositorioDiccionario:
    def __init__(self) -> None:
        self._pool = None
        self._database_url = os.environ.get("DATABASE_URL")
        self._catalogo: list[dict] = []
        self._diccionario: list[dict] = []

    async def inicializar(self) -> None:
        if self._database_url:
            await self._inicializar_postgres()
        else:
            self._inicializar_json()

    async def _inicializar_postgres(self) -> None:
        if asyncpg is None:
            raise RuntimeError(
                "asyncpg no está instalado. Ejecuta: pip install asyncpg"
            )
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        self._pool = await asyncpg.create_pool(
            self._database_url,
            ssl=ctx,
            min_size=1,
            max_size=5,
        )
        async with self._pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS catalogo_maestro (
                    codigo TEXT PRIMARY KEY,
                    descripcion TEXT NOT NULL,
                    giro TEXT,
                    categoria TEXT,
                    activo BOOLEAN DEFAULT TRUE
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS diccionario_homologacion (
                    id SERIAL PRIMARY KEY,
                    codigo_f29 TEXT NOT NULL,
                    glosa_f29 TEXT,
                    codigo_balance TEXT,
                    glosa_balance TEXT,
                    factor REAL DEFAULT 1.0,
                    activo BOOLEAN DEFAULT TRUE
                )
            """)
            rows_catalogo = await conn.fetch("SELECT * FROM catalogo_maestro")
            rows_diccionario = await conn.fetch(
                "SELECT * FROM diccionario_homologacion"
            )
            self._catalogo = [dict(r) for r in rows_catalogo]
            self._diccionario = [dict(r) for r in rows_diccionario]

    def _inicializar_json(self) -> None:
        base = Path(__file__).resolve().parent.parent
        catalogo_path = base / "catalogo_maestro.json"
        diccionario_path = base / "diccionario_optimizado.json"

        if catalogo_path.exists():
            with open(catalogo_path, encoding="utf-8") as f:
                self._catalogo = json.load(f)

        if diccionario_path.exists():
            with open(diccionario_path, encoding="utf-8") as f:
                self._diccionario = json.load(f)

    async def cerrar(self) -> None:
        if self._pool:
            await self._pool.close()
            self._pool = None

    @property
    def catalogo(self) -> list[dict]:
        return list(self._catalogo)

    @property
    def diccionario(self) -> list[dict]:
        return list(self._diccionario)

    async def buscar_homologacion(
        self, codigo_f29: str
    ) -> dict | None:
        for entry in self._diccionario:
            if entry.get("codigo_f29") == codigo_f29:
                return entry
        if self._pool:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM diccionario_homologacion WHERE codigo_f29 = $1",
                    codigo_f29,
                )
                if row:
                    return dict(row)
        return None

    async def buscar_en_catalogo(
        self, codigo: str
    ) -> dict | None:
        for entry in self._catalogo:
            if entry.get("codigo") == codigo:
                return entry
        if self._pool:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM catalogo_maestro WHERE codigo = $1",
                    codigo,
                )
                if row:
                    return dict(row)
        return None
