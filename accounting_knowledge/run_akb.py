#!/usr/bin/env python3
"""Runner for the Accounting Knowledge Base analyzer.

Usage:
    python -m accounting_knowledge.run_akb
"""

import sys
from pathlib import Path

# Ensure project root is in path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from accounting_knowledge import AccountingKnowledgeBase


def main():
    import time
    start = time.time()

    akb = AccountingKnowledgeBase("datasets/")
    stats = akb.run_all()

    elapsed = time.time() - start
    print(f"\n{'='*60}")
    print(f"AKB COMPLETADO en {elapsed/60:.2f} min")
    print(f"Archivos procesados: {stats['archivos_procesados']}")
    print(f"Cuentas extraidas: {stats['total_cuentas_extraidas']}")
    print(f"Tokens unicos: {stats['total_tokens_unicos']}")
    print(f"Abreviaturas: {stats['total_abreviaturas_detectadas']}")
    print(f"Sinonimos: {stats['total_sinonimos_encontrados']}")
    print(f"Familias: {stats['total_familias_descubiertas']}")
    print(f"Nombres normalizables: {stats['total_nombres_normalizables']}")
    print(f"Cobertura actual: {stats['cobertura_actual_pct']}%")
    print(f"Cobertura potencial: {stats['cobertura_potencial_pct']}%")
    print(f"Incremento potencial: {stats['incremento_potencial_cobertura_pct']}%")
    print(f"Top 50 oportunidades generadas")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
