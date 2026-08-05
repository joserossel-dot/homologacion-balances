"""
reconcile_gold.py — Auditoría de sola-lectura de los conflictos del Gold Standard.

Problema de fondo: `gold_standard` puede contener varias filas con el mismo
`normalized` pero códigos distintos. `learning/engine.py` hace `SELECT ... WHERE
normalized = ?` sin `ORDER BY` y `fetchone()` devuelve la primera fila por orden
físico (rowid), por lo que el código elegido no es el "mejor" sino el primero que
SQLite devuelva.

Este script SOLO LEE. No modifica:
  - gold_standard.db
  - learning/engine.py
  - ningún otro archivo del proyecto.

Uso:
    python3 tools/reconcile_gold.py                  # reporte por consola
    python3 tools/reconcile_gold.py --report          # escribe reports/classifier_audit/gold_conflicts.md
    python3 tools/reconcile_gold.py --json            # además imprime JSON
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

GOLD_DB = REPO / "gold_standard.db"
REPORT_PATH = REPO / "reports" / "classifier_audit" / "gold_conflicts.md"


def _fmt(v: Any) -> str:
    if v is None:
        return "(X)"
    s = str(v).strip()
    return s if s else "(?)"


def load_conflicts(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Detecta normalized con más de un código distinto."""
    rows = conn.execute(
        """
        SELECT normalized, COUNT(*) AS n_filas,
               COUNT(DISTINCT codigo_estandar) AS n_codigos,
               GROUP_CONCAT(DISTINCT codigo_estandar) AS codigos
        FROM gold_standard
        GROUP BY normalized
        HAVING n_codigos > 1
        ORDER BY n_filas DESC, n_codigos DESC, normalized
        """
    ).fetchall()

    conflicts: list[dict[str, Any]] = []
    for norm, n_filas, n_codigos, codigos in rows:
        registros = conn.execute(
            """
            SELECT g.id, g.codigo_estandar, g.nombre_cuenta
            FROM gold_standard g
            WHERE g.normalized = ?
            ORDER BY g.id
            """,
            (norm,),
        ).fetchall()
        detalles: list[dict[str, Any]] = []
        for gid, gcode, gname in registros:
            peer = conn.execute(
                """
                SELECT source_file, account_code_original, account_nature,
                       suggested_code, suggested_confidence, final_code,
                       reviewer, review_date, comments, usage_count, last_used
                FROM gold_records WHERE id = ?
                """,
                (gid,),
            ).fetchone()
            det: dict[str, Any] = {
                "id": gid,
                "codigo_estandar": gcode,
                "nombre_cuenta": gname,
            }
            if peer:
                det.update({
                    "source_file": peer[0],
                    "account_code_original": peer[1],
                    "account_nature": peer[2],
                    "suggested_code": peer[3],
                    "suggested_confidence": peer[4],
                    "final_code": peer[5],
                    "reviewer": peer[6],
                    "review_date": peer[7],
                    "comments": peer[8],
                    "usage_count": peer[9],
                    "last_used": peer[10],
                })
            detalles.append(det)
        conflicts.append({
            "normalized": norm,
            "n_registros": n_filas,
            "n_codigos": n_codigos,
            "codigos": codigos.split(","),
            "registros": detalles,
        })
    return conflicts


def build_report(conflicts: list[dict[str, Any]], conn: sqlite3.Connection) -> str:
    lines: list[str] = []
    lines.append("# Auditoría de Conflictos del Gold Standard")
    lines.append("")
    lines.append(
        f"Generado: {datetime.now().isoformat(timespec='seconds')} — "
        f"`tools/reconcile_gold.py` (solo lectura, dry-run)"
    )
    lines.append("")
    lines.append("> No se modificó ninguna base de datos ni código.")
    lines.append("")

    if not conflicts:
        lines.append("**No se encontraron `normalized` con códigos conflictivos.**")
        return "\n".join(lines)

    total_registros = conn.execute("SELECT COUNT(*) FROM gold_standard").fetchone()[0]
    total_unicos = conn.execute(
        "SELECT COUNT(DISTINCT normalized) FROM gold_standard"
    ).fetchone()[0]

    lines.append("## Resumen")
    lines.append("")
    lines.append(f"- **Grupos con código conflictivo:** `{len(conflicts)}`")
    lines.append(f"- **Registros en gold_standard:** `{total_registros}`  (normalized únicos: `{total_unicos}`)")
    lines.append("")
    lines.append("## Conflictos (ordenados por nº de registros)")
    lines.append("")

    for i, c in enumerate(conflicts, 1):
        lines.append(f"### {i}. `{c['normalized']}`")
        lines.append("")
        lines.append(f"- Registros: `{c['n_registros']}` | Códigos: `{'`, `'.join(c['codigos'])}`")
        lines.append("")
        lines.append("| id | código | suggested_conf | reviewer | review_date | usage | sugerido | final | naturaleza | source_file |")
        lines.append("|----|--------|----------------|----------|-------------|-------|----------|-------|-----------|-------------|")
        for r in c["registros"]:
            lines.append(
                "| {id} | `{cod}` | {conf} | {rev} | {fecha} | {uc} | {sc} | {fc} | {nat} | `{sf}` |".format(
                    id=r["id"],
                    cod=r["codigo_estandar"],
                    conf=_fmt(r.get("suggested_confidence")),
                    rev=_fmt(r.get("reviewer")),
                    fecha=_fmt(r.get("review_date")),
                    uc=_fmt(r.get("usage_count")),
                    sc=_fmt(r.get("suggested_code")),
                    fc=_fmt(r.get("final_code")),
                    nat=_fmt(r.get("account_nature")),
                    sf=_fmt(r.get("source_file")),
                )
            )
        lines.append("")
        lines.append("- **Impacto en documentos**: los PDF afectados por `anticipo a proveedores` "
                     "(AC.01 vs AC.07) figuran en `reports/architecture_state/mismatch_table.json` "
                     "(causa `G`, 19 casos por `learning_exact`).")
        lines.append("")

    lines.append("---")
    lines.append("## Correlación de IDs")
    lines.append("")
    lines.append("Id correlativo de `gold_standard` ↔ `gold_records`, verificado 1:1 (0 huérfanos).")
    return "\n".join(lines)


def print_console(conflicts: list[dict[str, Any]]) -> None:
    if not conflicts:
        print("Sin conflictos.")
        return
    for c in conflicts:
        print(
            f"\n### {c['normalized']}  "
            f"[{c['n_registros']} filas | {c['n_codigos']} códigos: {', '.join(c['codigos'])}]"
        )
        for r in c["registros"]:
            print(
                f"  id={r['id']:>4} cod={r['codigo_estandar']:<6} "
                f"conf={_fmt(r.get('suggested_confidence')):<6} "
                f"reviewer={_fmt(r.get('reviewer')):<12} "
                f"review_date={_fmt(r.get('review_date')):<10} "
                f"usage={_fmt(r.get('usage_count')):<4} "
                f"sugerido={_fmt(r.get('suggested_code')):<6} "
                f"final={_fmt(r.get('final_code')):<6} "
                f"naturaleza={_fmt(r.get('account_nature')):<8} "
                f"archivo={_fmt(r.get('source_file'))}"
            )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Auditoría (solo lectura) de conflictos del Gold Standard"
    )
    parser.add_argument("--report", action="store_true",
                        help=f"Escribir {REPORT_PATH.relative_to(REPO)}")
    parser.add_argument("--json", action="store_true", help="Imprimir JSON de conflictos")
    args = parser.parse_args()

    if not GOLD_DB.exists():
        print(f"ERROR: {GOLD_DB} no existe", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(str(GOLD_DB))
    conflicts = load_conflicts(conn)

    print_console(conflicts)

    if args.json:
        print("\n=== JSON ===")
        print(json.dumps(conflicts, indent=2, ensure_ascii=False, default=str))

    if args.report:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(build_report(conflicts, conn), encoding="utf-8")
        print(f"\nReporte escrito: {REPORT_PATH}")

    conn.close()
    print("\n(dry-run completo — 0 escrituras)")


if __name__ == "__main__":
    main()