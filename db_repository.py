"""
db_repository.py — Capa de persistencia compartida para el diccionario
de homologación.

Reemplaza el almacenamiento efímero en st.session_state por escrituras
y lecturas directas a PostgreSQL, de modo que las correcciones de un
analista sean visibles inmediatamente para todos los demás.

Si la base de datos no está disponible, RepositorioDiccionario cae a
modo "solo lectura" sobre el JSON local y registra una advertencia —
la app sigue funcionando pero sin persistencia compartida.
"""

import json
import re
import logging
from pathlib import Path
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)

DB_CONFIG = dict(
    host='localhost', port=5432, dbname='homologacion',
    user='postgres', password='claude123'
)

BASE_DIR = Path(__file__).parent


def normalizar_nombre(s: str) -> str:
    n = s.lower().strip()
    n = re.sub(r"[^\w\sñáéíóú]", " ", n)
    n = re.sub(r"\s+", " ", n)
    return n.strip()


class RepositorioDiccionario:
    """
    Acceso a catalogo_maestro y diccionario_homologacion en PostgreSQL,
    con fallback a JSON local de solo lectura si la BD no está disponible.
    """

    def __init__(self):
        self.modo_db = False
        self.conn = None
        try:
            self.conn = psycopg2.connect(**DB_CONFIG, connect_timeout=3)
            self.conn.autocommit = False
            self.modo_db = True
            logger.info("RepositorioDiccionario: conectado a PostgreSQL")
        except Exception as e:
            logger.warning(f"RepositorioDiccionario: sin conexión a BD ({e}). "
                            f"Modo solo-lectura desde JSON local.")
            self._cargar_fallback_json()

    def _cargar_fallback_json(self):
        with open(BASE_DIR / 'catalogo_maestro.json', encoding='utf-8') as f:
            self._catalogo_fallback = json.load(f)
        with open(BASE_DIR / 'diccionario_optimizado.json', encoding='utf-8') as f:
            self._diccionario_fallback = json.load(f)

    # ─────────────────────────────────────────────────────────────────────────
    # CATÁLOGO MAESTRO
    # ─────────────────────────────────────────────────────────────────────────

    def obtener_catalogo(self) -> dict:
        """Retorna {codigo_estandar: {...}} para todos los códigos activos."""
        if not self.modo_db:
            return self._catalogo_fallback

        with self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT codigo_estandar, nombre_estandar, categoria, tipo_estado,
                       naturaleza, signo_normal, es_deuda_financiera,
                       es_activo_liquido, afecta_ebitda
                FROM catalogo_maestro WHERE activo = TRUE
            """)
            rows = cur.fetchall()

        return {r['codigo_estandar']: dict(r) for r in rows}

    # ─────────────────────────────────────────────────────────────────────────
    # DICCIONARIO DE HOMOLOGACIÓN
    # ─────────────────────────────────────────────────────────────────────────

    def obtener_diccionario(self) -> list[dict]:
        """Retorna todas las entradas activas del diccionario."""
        if not self.modo_db:
            return self._diccionario_fallback

        with self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT cuenta_original, cuenta_normalizada, codigo_estandar,
                       fuente, validado_humano, frecuencia_uso
                FROM diccionario_homologacion WHERE activo = TRUE
            """)
            rows = cur.fetchall()

        return [dict(r) for r in rows]

    def buscar_exacto(self, nombre_normalizado: str) -> dict | None:
        """Búsqueda exacta por cuenta_normalizada. Más rápido que cargar todo."""
        if not self.modo_db:
            for d in self._diccionario_fallback:
                if normalizar_nombre(d['cuenta_original']) == nombre_normalizado:
                    return d
            return None

        with self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT cuenta_original, cuenta_normalizada, codigo_estandar,
                       fuente, validado_humano
                FROM diccionario_homologacion
                WHERE cuenta_normalizada = %s AND activo = TRUE
            """, (nombre_normalizado,))
            row = cur.fetchone()

        return dict(row) if row else None

    def buscar_similares_trgm(self, nombre_normalizado: str, limite: int = 5) -> list[dict]:
        """
        Búsqueda por similitud trigrama (pg_trgm) — sustituto liviano de
        embeddings para la Etapa 1b mientras no hay pgvector poblado.
        """
        if not self.modo_db:
            return []  # sin trgm en modo fallback

        with self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT cuenta_original, codigo_estandar,
                       similarity(cuenta_normalizada, %s) AS score
                FROM diccionario_homologacion
                WHERE activo = TRUE
                  AND cuenta_normalizada %% %s
                ORDER BY score DESC
                LIMIT %s
            """, (nombre_normalizado, nombre_normalizado, limite))
            rows = cur.fetchall()

        return [dict(r) for r in rows]

    # ─────────────────────────────────────────────────────────────────────────
    # ESCRITURA — FEEDBACK LOOP COMPARTIDO
    # ─────────────────────────────────────────────────────────────────────────

    def guardar_validacion(
        self,
        cuenta_original: str,
        codigo_estandar: str,
        validado_por: str = 'analista',
        codigo_sugerido: str | None = None,
        metodo_sugerido: str | None = None,
        confianza_sugerida: float | None = None,
        archivo_origen: str | None = None,
    ) -> bool:
        """
        Inserta/actualiza una entrada del diccionario validada por un humano
        y registra el evento en log_validaciones. Visible inmediatamente
        para todos los analistas (no requiere descargar/recargar JSON).

        Retorna True si se persistió en BD, False si quedó solo en memoria
        (modo fallback).
        """
        nombre_norm = normalizar_nombre(cuenta_original)
        fue_correccion = (
            codigo_sugerido is not None and codigo_sugerido != codigo_estandar
        )

        if not self.modo_db:
            # Modo fallback: agregar en memoria para esta sesión únicamente
            self._diccionario_fallback.append({
                'cuenta_original': cuenta_original,
                'cuenta_normalizada': nombre_norm,
                'codigo_estandar': codigo_estandar,
                'fuente': 'validacion_humana_sesion_local',
                'validado_humano': True,
                'frecuencia_uso': 1,
            })
            logger.warning(
                "Validación guardada SOLO en memoria de esta sesión "
                "(sin conexión a BD) — no será visible para otros analistas."
            )
            return False

        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO diccionario_homologacion
                    (cuenta_original, cuenta_normalizada, codigo_estandar,
                     fuente, validado_humano, validado_por, validado_en)
                VALUES (%s,%s,%s,'validacion_humana',TRUE,%s,%s)
                ON CONFLICT (cuenta_normalizada) DO UPDATE SET
                    codigo_estandar = EXCLUDED.codigo_estandar,
                    validado_humano = TRUE,
                    validado_por = EXCLUDED.validado_por,
                    validado_en = EXCLUDED.validado_en,
                    frecuencia_uso = diccionario_homologacion.frecuencia_uso + 1,
                    actualizado_en = NOW()
            """, (cuenta_original, nombre_norm, codigo_estandar,
                  validado_por, datetime.now(timezone.utc)))

            cur.execute("""
                INSERT INTO log_validaciones
                    (cuenta_original, codigo_sugerido, codigo_validado,
                     metodo_sugerido, confianza_sugerida, fue_correccion,
                     validado_por, archivo_origen)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """, (cuenta_original, codigo_sugerido, codigo_estandar,
                  metodo_sugerido, confianza_sugerida, fue_correccion,
                  validado_por, archivo_origen))

        self.conn.commit()
        return True

    # ─────────────────────────────────────────────────────────────────────────

    def estadisticas(self) -> dict:
        if not self.modo_db:
            return {
                'modo': 'fallback_json',
                'total_diccionario': len(self._diccionario_fallback),
                'total_catalogo': len(self._catalogo_fallback),
                'validaciones_pendientes_persistir': 0,
            }

        with self.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM diccionario_homologacion WHERE activo")
            total_dic = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM catalogo_maestro WHERE activo")
            total_cat = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM log_validaciones")
            total_log = cur.fetchone()[0]
            cur.execute("""
                SELECT COUNT(*) FROM log_validaciones
                WHERE creado_en > NOW() - INTERVAL '24 hours'
            """)
            validaciones_24h = cur.fetchone()[0]

        return {
            'modo': 'postgresql',
            'total_diccionario': total_dic,
            'total_catalogo': total_cat,
            'total_validaciones_historicas': total_log,
            'validaciones_ultimas_24h': validaciones_24h,
        }

    def close(self):
        if self.conn:
            self.conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# TEST
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    repo = RepositorioDiccionario()

    print("Estadísticas:", repo.estadisticas())

    cat = repo.obtener_catalogo()
    print(f"\nCatálogo: {len(cat)} códigos")
    print("  AC.01:", cat.get('AC.01'))

    # Test búsqueda exacta
    r = repo.buscar_exacto(normalizar_nombre("Banco Bci"))
    print(f"\nBúsqueda exacta 'Banco Bci': {r}")

    # Test búsqueda trgm (similar a 'fondo por rendir' con typo)
    similares = repo.buscar_similares_trgm(normalizar_nombre("Fondo x Rendirr"))
    print(f"\nSimilares trgm a 'Fondo x Rendirr':")
    for s in similares:
        print(f"   {s['cuenta_original']:35s} -> {s['codigo_estandar']}  (score={s['score']:.3f})")

    # Test escritura + verificación inmediata desde "otra sesión"
    print("\n--- Test feedback loop compartido ---")
    ok = repo.guardar_validacion(
        cuenta_original="Cuenta de Prueba Sesión A",
        codigo_estandar="AC.07",
        validado_por="analista_A",
        codigo_sugerido="AC.08",
        metodo_sugerido="regla_regex",
        confianza_sugerida=0.6,
        archivo_origen="test.pdf"
    )
    print(f"Persistido en BD: {ok}")

    # Nueva conexión simulando "otra sesión" (otro analista)
    repo2 = RepositorioDiccionario()
    r2 = repo2.buscar_exacto(normalizar_nombre("Cuenta de Prueba Sesión A"))
    print(f"Visible desde otra sesión (analista_B): {r2}")
    print(f"Estadísticas tras la validación: {repo2.estadisticas()}")

    repo.close()
    repo2.close()
