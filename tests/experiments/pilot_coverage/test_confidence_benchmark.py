"""
tests/experiments/pilot_coverage/test_confidence_benchmark.py

Benchmark determinista para evaluar la línea base del clasificador y sugerencias en UI.
Aislamiento obligatorio y ejecución unificada:
- Red y Neon bloqueados preventivamente.
- Almacenamiento temporal SQLite para el motor Gold / LearningEngine.
- Misma entrada y cálculo entre test y benchmark_runner.
- Taxonomía validada formalmente contra catalogo_maestro.json.
- Verificación del contrato productivo de sugerencias UI (MotorHibridoLocal).
"""

from __future__ import annotations

from typing import Any, Dict
import pytest

from experiments.pilot_coverage.classification.benchmark_runner import run_benchmark


@pytest.fixture(scope="module")
def benchmark_results() -> Dict[str, Any]:
    """Ejecuta la medición unificada y determinista del benchmark."""
    return run_benchmark()


def test_baseline_clasificador_linea_base(benchmark_results):
    """Evalúa las decisiones del clasificador productivo con métricas formales y sin umbrales locales ad-hoc."""
    total = benchmark_results["total_casos"]
    desglose = benchmark_results["desglose_casos"]
    metricas = benchmark_results["metricas_clasificacion"]

    print(f"\n--- REPORTE DE MEDICIÓN OPERATIVA (Total: {total}) ---")
    print(f"Cuentas Evaluables con Código: {desglose['casos_evaluables_con_codigo']}")
    print(f"Ambiguas / Desconocidas / Conflictos: {desglose['casos_sin_codigo_verificable_ambiguos_desconocidos']}")
    print(f"Controles / Totales: {desglose['casos_controles_totales']}")
    print(f"Auto Correctas: {metricas['auto_correctas']}/{metricas['denominador_cobertura']} ({metricas['cobertura_automatica']:.1%})")
    print(f"Auto Incorrectas: {metricas['auto_incorrectas']}")
    print(f"Automatizaciones Indebidas: {metricas['automatizaciones_indebidas']}")
    print(f"Precisión Automática: {metricas['precision_automatica']:.1%}")
    print(f"Revisiones Justificadas: {metricas['revision_justificada']}")
    print(f"Revisiones Evitables: {metricas['revision_evitable']}")
    print(f"Controles Correctamente Separados: {metricas['controles_correctamente_separados']}")

    # Comprobaciones deterministas
    assert total == 22
    assert desglose["casos_evaluables_con_codigo"] == 14
    assert desglose["casos_sin_codigo_verificable_ambiguos_desconocidos"] == 6
    assert desglose["casos_controles_totales"] == 2

    assert metricas["auto_correctas"] == 7, "Esperadas 7 automáticas correctas (5 exactas + 2 impuestos diferidos auditados)"
    assert metricas["auto_incorrectas"] == 0, "No debe haber clasificaciones automáticas incorrectas"
    assert metricas["automatizaciones_indebidas"] == 0, "No debe haber confirmaciones automáticas sobre casos ambiguos/desconocidos"
    assert metricas["precision_automatica"] == 1.0, "La precisión sobre automáticas debe ser 100%"
    assert metricas["cobertura_automatica"] == 0.5, "La cobertura sobre clasificables debe ser 50.0% (7/14)"
    assert metricas["revision_justificada"] == 13, "Esperadas 13 revisiones justificadas"
    assert metricas["revision_evitable"] == 0, "No debe haber revisiones evitables"
    assert metricas["controles_correctamente_separados"] == 2, "Los 2 controles deben separarse correctamente de las cuentas de detalle"
    assert metricas["controles_tratados_como_cuenta"] == 0


def test_alternativas_revision_presencia_top1_top3(benchmark_results):
    """Evalúa la presencia del código estándar en Top-1 y Top-3 usando el contrato productivo (MotorHibridoLocal)."""
    sug = benchmark_results["metricas_sugerencias_ui"]

    print(f"\n--- EVALUACIÓN ALTERNATIVAS REVISIÓN (Total Evaluables: {sug['denominador_sugerencias']}) ---")
    print(f"Top-1 Hits: {sug['top1_hits']}/{sug['denominador_sugerencias']} ({sug['tasa_top1']:.1%})")
    print(f"Top-3 Hits: {sug['top3_hits']}/{sug['denominador_sugerencias']} ({sug['tasa_top3']:.1%})")

    # Mediciones verificadas con el contrato real
    assert sug["denominador_sugerencias"] == 14
    detalle = benchmark_results["detalle_casos"]
    top1_ids = {c["id"] for c in detalle if c["top1_ok"]}
    assert top1_ids == {
        "EX01", "EX02", "EX03", "EX04", "EX05", "SYN01", "SYN02",
        "CA02", "TAX02", "PAT01",
    }
    assert {c["id"] for c in detalle if c["top3_ok"]} == top1_ids | {"CA01", "TAX01"}
    assert sug["top1_hits"] == 10
    assert sug["top3_hits"] == 12
    assert sug["tasa_top1"] == pytest.approx(10 / 14)
    assert sug["tasa_top3"] == pytest.approx(12 / 14)

    # El nuevo acierto es una cuenta comercial de activo, no una promoción automática.
    deudores = next(c for c in detalle if c["id"] == "SYN02")
    assert deudores["codigo_esperado"] == "AC.03"
    assert deudores["alts_sugeridas"][0] == "AC.03"
    assert deudores["requiere_revision"] is True
    assert deudores["es_automatica"] is False
