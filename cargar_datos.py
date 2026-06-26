"""
cargar_datos.py — Carga inicial de catalogo_maestro y diccionario_homologacion
desde los JSON locales hacia PostgreSQL.

Uso:
    python3 cargar_datos.py
"""

import json
import re
from pathlib import Path

import psycopg2
import psycopg2.extras

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


def main():
    with open(BASE_DIR / 'catalogo_maestro.json', encoding='utf-8') as f:
        catalogo = json.load(f)
    with open(BASE_DIR / 'diccionario_optimizado.json', encoding='utf-8') as f:
        diccionario = json.load(f)

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    # ── Catálogo maestro ────────────────────────────────────────────────────
    n_cat = 0
    for cod, c in catalogo.items():
        cur.execute("""
            INSERT INTO catalogo_maestro
                (codigo_estandar, nombre_estandar, categoria, tipo_estado,
                 naturaleza, signo_normal, es_deuda_financiera,
                 es_activo_liquido, afecta_ebitda)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (codigo_estandar) DO UPDATE SET
                nombre_estandar = EXCLUDED.nombre_estandar,
                categoria = EXCLUDED.categoria,
                tipo_estado = EXCLUDED.tipo_estado,
                naturaleza = EXCLUDED.naturaleza,
                signo_normal = EXCLUDED.signo_normal,
                es_deuda_financiera = EXCLUDED.es_deuda_financiera,
                es_activo_liquido = EXCLUDED.es_activo_liquido,
                afecta_ebitda = EXCLUDED.afecta_ebitda
        """, (
            c['codigo_estandar'], c['nombre_estandar'], c['categoria'],
            c['tipo_estado'], c['naturaleza'], c['signo_normal'],
            c['es_deuda_financiera'], c['es_activo_liquido'], c['afecta_ebitda']
        ))
        n_cat += 1

    # ── Diccionario de homologación ─────────────────────────────────────────
    n_dic = 0
    n_skip = 0
    for d in diccionario:
        cuenta_original = d['cuenta_original']
        cuenta_norm = normalizar_nombre(cuenta_original)
        codigo = d['codigo_estandar']
        fuente = d['fuente']
        validado = 'validacion_humana' in fuente or 'validado' in fuente

        try:
            cur.execute("""
                INSERT INTO diccionario_homologacion
                    (cuenta_original, cuenta_normalizada, codigo_estandar,
                     fuente, validado_humano)
                VALUES (%s,%s,%s,%s,%s)
                ON CONFLICT (cuenta_normalizada) DO UPDATE SET
                    codigo_estandar = EXCLUDED.codigo_estandar,
                    fuente = EXCLUDED.fuente,
                    actualizado_en = NOW()
            """, (cuenta_original, cuenta_norm, codigo, fuente, validado))
            n_dic += 1
        except psycopg2.errors.ForeignKeyViolation:
            conn.rollback()
            print(f"  SKIP (código no existe en catálogo): {cuenta_original!r} -> {codigo}")
            n_skip += 1
            continue

    conn.commit()

    cur.execute("SELECT COUNT(*) FROM catalogo_maestro")
    total_cat = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM diccionario_homologacion")
    total_dic = cur.fetchone()[0]

    print(f"\nCatálogo maestro:      {n_cat} procesados -> {total_cat} en BD")
    print(f"Diccionario:           {n_dic} procesados, {n_skip} omitidos -> {total_dic} en BD")

    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
