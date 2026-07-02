"""Repositorio de datos para la plataforma de análisis financiero.

Esta versión está alineada con la estructura real de la base de datos:

* Tablas PostgreSQL
  - catalogo_maestro
  - diccionario_homologacion
* Campos de fallback JSON
  - catálogo → cualquier campo (se devuelven todas las filas)
  - diccionario → usa la clave *cuenta_original* como identificador principal
"""

import os
import json
import logging
from typing import Any, List, Dict, Optional

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()  # Solo en desarrollo

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL no configurada. Por favor, define la variable de entorno o crea un archivo .env local"
    )

class RepositorioDiccionario:
    """Acceso a catálogos y diccionarios con fallback JSON."""

    def __init__(self) -> None:
        self._conn: Optional[psycopg2.extensions.connection] = None
        self._catalogo_fallback: Optional[List[Dict[str, Any]]] = None
        self._diccionario_fallback: Optional[List[Dict[str, Any]]] = None

        try:
            self._conn = psycopg2.connect(DATABASE_URL, connect_timeout=3)
            self._conn.autocommit = True
        except Exception as e:
            logging.error(
                "Error al conectar con PostgreSQL: %s — usando fallback JSON.", e
            )
            self._load_fallback_json()

    def _load_fallback_json(self) -> None:
        base_path = os.path.abspath(os.path.dirname(__file__))
        try:
            with open(os.path.join(base_path, "catalogo_maestro.json"), "r", encoding="utf-8") as f:
                self._catalogo_fallback = json.load(f)
        except FileNotFoundError:
            self._catalogo_fallback = []

        try:
            with open(os.path.join(base_path, "diccionario_optimizado.json"), "r", encoding="utf-8") as f:
                self._diccionario_fallback = json.load(f)
        except FileNotFoundError:
            self._diccionario_fallback = []

    def obtener_catalogo(self) -> List[Dict[str, Any]]:
        if self._conn:
            with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM catalogo_maestro;")
                return cur.fetchall()
        return self._catalogo_fallback or []

    def obtener_diccionario(self) -> List[Dict[str, Any]]:
        if self._conn:
            with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM diccionario_homologacion;")
                return cur.fetchall()
        return self._diccionario_fallback or []

    def buscar_exacto(self, termino: str) -> List[Dict[str, Any]]:
        if not self._conn:
            return [row for row in (self._diccionario_fallback or []) if row.get("cuenta_original") == termino]
        with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM diccionario_homologacion WHERE cuenta_original = %s;", (termino,))
            return cur.fetchall()

    def buscar_similares_trgm(self, termino: str, limite: int = 10) -> List[Dict[str, Any]]:
        if not self._conn:
            return [row for row in (self._diccionario_fallback or []) if termino.lower() in row.get("cuenta_original", "").lower()][:limite]
        with self._conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM diccionario_homologacion
                WHERE cuenta_original %s
                ORDER BY similarity(cuenta_original, %s) DESC LIMIT %s;
            """, (termino, termino, limite))
            return cur.fetchall()

    def guardar_validacion(self, cuenta_original: str, es_correcto: bool, comentario: Optional[str] = None) -> None:
        if not self._conn:
            logging.info("Validación (fallback) – cuenta: %s", cuenta_original)
            return
        with self._conn.cursor() as cur:
            cur.execute("""
                INSERT INTO log_validaciones (cuenta_original, es_correcto, comentario, fecha)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (cuenta_original) DO UPDATE
                SET es_correcto = EXCLUDED.es_correcto, comentario = EXCLUDED.comentario, fecha = NOW();
            """, (cuenta_original, es_correcto, comentario))

    def cerrar(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
