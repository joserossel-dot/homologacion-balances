"""Script de carga inicial de datos."""

import os
import json
import logging
from typing import List, Dict, Any
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL no configurada.")

def obtener_conexion() -> psycopg2.extensions.connection:
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=3)
    conn.autocommit = True
    return conn

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

def cargar_json(nombre: str) -> List[Dict[str, Any]]:
    ruta = os.path.join(BASE_DIR, nombre)
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)

def upsert_catalogo(conn: psycopg2.extensions.connection, filas: List[Dict[str, Any]]) -> None:
    if not filas: return
    columnas = list(filas[0].keys())
    set_clause = ", ".join([f"{col}=EXCLUDED.{col}" for col in columnas if col != "codigo_estandar"])
    query = f"INSERT INTO catalogo_maestro ({', '.join(columnas)}) VALUES %s ON CONFLICT (codigo_estandar) DO UPDATE SET {set_clause};"
    valores = [[fila[col] for col in columnas] for fila in filas]
    with conn.cursor() as cur: execute_values(cur, query, valores)

def upsert_diccionario(conn: psycopg2.extensions.connection, filas: List[Dict[str, Any]]) -> None:
    if not filas: return
    columnas = list(filas[0].keys())
    set_clause = ", ".join([f"{col}=EXCLUDED.{col}" for col in columnas if col != "cuenta_original"])
    query = f"INSERT INTO diccionario_homologacion ({', '.join(columnas)}) VALUES %s ON CONFLICT (cuenta_original) DO UPDATE SET {set_clause};"
    valores = [[fila[col] for col in columnas] for fila in filas]
    with conn.cursor() as cur: execute_values(cur, query, valores)

def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    conn = None
    try:
        conn = obtener_conexion()
        catalogo = cargar_json("catalogo_maestro.json")
        diccionario = cargar_json("diccionario_optimizado.json")
        upsert_catalogo(conn, catalogo)
        upsert_diccionario(conn, diccionario)
        logging.info("¡Carga inicial ejecutada con éxito!")
    except Exception as e:
        logging.error("Fallo: %s", e)
        raise
    finally:
        if conn: conn.close()

if __name__ == "__main__":
    main()
