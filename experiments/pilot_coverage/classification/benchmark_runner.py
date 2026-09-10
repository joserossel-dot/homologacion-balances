"""
experiments/pilot_coverage/classification/benchmark_runner.py

Ejecutor determinista y estrictamente aislado del benchmark de clasificación y revisión (B2/B3).
Aislamiento real:
- Utiliza isolated_benchmark_environment() para no contaminar el proceso global.
- Almacenamiento temporal SQLite para el motor Gold / LearningEngine.
- Sin lectura ni mutación de datos aprendidos del usuario.
- Evaluación contra contratos reales de motor (HomologationPipeline) y sugerencias UI (MotorHibridoLocal).
"""

from __future__ import annotations

import json
import pathlib
import sys
import tempfile
from typing import Any, Dict, List, Optional

from experiments.pilot_coverage.classification.benchmark_classifier_isolated import (
    isolated_benchmark_environment,
)

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_BENCHMARK_CASES = [
    {"id": "EX01", "nombre": "Caja", "tipo": "ACTIVO", "monto": 100000, "codigo_esperado": "AC.01", "categoria": "Exacta", "debe_clasificar_auto": True},
    {"id": "EX02", "nombre": "Banco de Chile", "tipo": "ACTIVO", "monto": 5000000, "codigo_esperado": "AC.01", "categoria": "Exacta", "debe_clasificar_auto": True},
    {"id": "EX03", "nombre": "Clientes", "tipo": "ACTIVO", "monto": 2500000, "codigo_esperado": "AC.03", "categoria": "Exacta", "debe_clasificar_auto": True},
    {"id": "EX04", "nombre": "Proveedores Nacionales", "tipo": "PASIVO", "monto": 1200000, "codigo_esperado": "PC.01", "categoria": "Exacta", "debe_clasificar_auto": True},
    {"id": "EX05", "nombre": "Capital Pagado", "tipo": "PATRIMONIO", "monto": 10000000, "codigo_esperado": "PAT.01", "categoria": "Exacta", "debe_clasificar_auto": True},
    {"id": "SYN01", "nombre": "Caja Chica Sucursal Centro", "tipo": "ACTIVO", "monto": 50000, "codigo_esperado": "AC.01", "categoria": "Sinónimo", "debe_clasificar_auto": False},
    {"id": "SYN02", "nombre": "Deudores por Ventas Comerciales", "tipo": "ACTIVO", "monto": 800000, "codigo_esperado": "AC.03", "categoria": "Sinónimo", "debe_clasificar_auto": False},
    {"id": "SYN03", "nombre": "Acreedores Comerciales Varios", "tipo": "PASIVO", "monto": 450000, "codigo_esperado": "PC.01", "categoria": "Sinónimo", "debe_clasificar_auto": False},
    {"id": "AMB01", "nombre": "Otras Cuentas", "tipo": "DESCONOCIDO", "monto": 10000, "codigo_esperado": None, "categoria": "Ambiguo", "debe_clasificar_auto": False},
    {"id": "AMB02", "nombre": "Varios y Ajustes", "tipo": "DESCONOCIDO", "monto": 25000, "codigo_esperado": None, "categoria": "Ambiguo", "debe_clasificar_auto": False},
    {"id": "AMB03", "nombre": "Provisión General", "tipo": "PASIVO", "monto": 300000, "codigo_esperado": None, "categoria": "Ambiguo", "debe_clasificar_auto": False},
    {"id": "CA01", "nombre": "Depreciación Acumulada Maquinarias", "tipo": "PASIVO", "monto": -500000, "codigo_esperado": "ANC.01.01", "categoria": "Contra-cuenta", "debe_clasificar_auto": False},
    {"id": "CA02", "nombre": "Amortización Acumulada Intangibles", "tipo": "PASIVO", "monto": -200000, "codigo_esperado": "ANC.03", "categoria": "Contra-cuenta", "debe_clasificar_auto": False},
    {"id": "TAX01", "nombre": "Activos por impuestos diferidos", "tipo": "ACTIVO", "monto": 150000, "codigo_esperado": "ANC.09", "categoria": "Imp. Diferidos", "debe_clasificar_auto": True},
    {"id": "TAX02", "nombre": "Pasivos por impuestos diferidos", "tipo": "PASIVO", "monto": 180000, "codigo_esperado": "PNC.06", "categoria": "Imp. Diferidos", "debe_clasificar_auto": True},
    {"id": "PAT01", "nombre": "Pérdidas Acumuladas Años Anteriores", "tipo": "ACTIVO", "monto": -1200000, "codigo_esperado": "PAT.03", "categoria": "Patr. Negativo", "debe_clasificar_auto": False},
    {"id": "TOT01", "nombre": "Total Activo Circulante", "tipo": "ACTIVO", "monto": 15000000, "codigo_esperado": None, "es_total": True, "categoria": "Total", "debe_clasificar_auto": False},
    {"id": "TOT02", "nombre": "Total Pasivo y Patrimonio", "tipo": "PASIVO", "monto": 15000000, "codigo_esperado": None, "es_total": True, "categoria": "Total", "debe_clasificar_auto": False},
    {"id": "UNK01", "nombre": "Fondo Extraordinario Proyecto Alfa", "tipo": "DESCONOCIDO", "monto": 750000, "codigo_esperado": None, "categoria": "Desconocido", "debe_clasificar_auto": False},
    {"id": "UNK02", "nombre": "Depósito Transitorio Sin Aplicar", "tipo": "DESCONOCIDO", "monto": 120000, "codigo_esperado": None, "categoria": "Desconocido", "debe_clasificar_auto": False},
    {"id": "CONF01", "nombre": "Ingresos por Ventas de Servicios", "tipo": "PASIVO", "monto": 500000, "codigo_esperado": None, "categoria": "Conflicto", "debe_clasificar_auto": False},
    {"id": "UNC01", "nombre": "Cuenta Corriente Mercantil Histórica", "tipo": "ACTIVO", "monto": 0, "codigo_esperado": "AC.08", "categoria": "Saldo Cero", "debe_clasificar_auto": False},
]


def run_benchmark(
    cases_path: Optional[pathlib.Path] = None,
    catalog_path: Optional[pathlib.Path] = None,
    dictionary_path: Optional[pathlib.Path] = None,
) -> Dict[str, Any]:
    """Ejecuta la medición unificada del clasificador y sugerencias UI en aislamiento."""
    if catalog_path is None:
        catalog_path = PROJECT_ROOT / "catalogo_maestro.json"
    if dictionary_path is None:
        dictionary_path = PROJECT_ROOT / "diccionario.json"

    if cases_path is not None and cases_path.exists():
        with open(cases_path, "r", encoding="utf-8") as f:
            cases: List[Dict[str, Any]] = json.load(f)
    else:
        cases = DEFAULT_BENCHMARK_CASES

    with open(catalog_path, "r", encoding="utf-8") as f:
        catalogo: Dict[str, Any] = json.load(f)

    with open(dictionary_path, "r", encoding="utf-8") as f:
        diccionario: List[Dict[str, Any]] = json.load(f)

    with isolated_benchmark_environment():
        from pipeline.homologation_pipeline import HomologationPipeline
        from app_validacion import (
            MotorHibridoLocal,
            _alternativas_revision,
            UMBRAL_REVISION,
        )

        motor_ui = MotorHibridoLocal(diccionario)

        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_db = pathlib.Path(tmp_dir) / "isolated_gold.db"
            pipeline = HomologationPipeline(db_path=temp_db)

            results_detail = []

            auto_correctas = 0
            auto_incorrectas = 0
            automatizaciones_indebidas = 0
            revisiones_justificadas = 0
            revisiones_evitables = 0
            controles_correctamente_separados = 0
            controles_tratados_como_cuenta = 0

            casos_evaluables_clasificacion = 0
            casos_sin_codigo_verificable = 0
            casos_totales_control = 0

            top1_hits = 0
            top3_hits = 0
            total_eval_top = 0

            for c in cases:
                cid = c["id"]
                nombre = c["nombre"]
                tipo = c["tipo"]
                monto = c["monto"]
                esperado = c["codigo_esperado"]
                es_total = c.get("es_total", False)
                debe_auto = c.get("debe_clasificar_auto", False)

                # A. Evaluación del Clasificador Operativo
                res = pipeline._classify_account(
                    account_code=c.get("codigo_cuenta", ""),
                    account_name=nombre,
                    account_tipo=tipo,
                    store_cmcc_shadow=False,
                )
                std_code = res.get("standard_code")
                conf_clasif = float(res.get("confidence") or 0.0)

                ajuste = pipeline._rule_processor.aplicar(
                    nombre_cuenta=nombre,
                    codigo_clasificado=std_code or "",
                    monto=monto,
                    origen_columna=tipo.lower(),
                )
                codigo_final = ajuste.codigo_final if ajuste.aplica else std_code

                # Decisión operativa del pipeline sobre revisión requerida
                requiere_revision_operativa = (
                    es_total
                    or (conf_clasif < UMBRAL_REVISION)
                    or (ajuste.aplica and ajuste.requiere_revision)
                    or (codigo_final is None)
                )

                es_automatica = (
                    not es_total
                    and codigo_final is not None
                    and not requiere_revision_operativa
                )

                # B. Evaluación de Alternativas de Revisión en UI
                alts = _alternativas_revision(
                    nombre=nombre,
                    sugerido=codigo_final or "",
                    confianza=conf_clasif,
                    origen_columna=tipo.lower(),
                    monto=monto,
                    catalogo=catalogo,
                    motor=motor_ui,
                    limite=3,
                )
                codigos_alts = [a["codigo"] for a in alts]

                top1_ok = False
                top3_ok = False
                if esperado is not None and not es_total:
                    total_eval_top += 1
                    if codigos_alts and codigos_alts[0] == esperado:
                        top1_hits += 1
                        top1_ok = True
                    if esperado in codigos_alts:
                        top3_hits += 1
                        top3_ok = True

                # C. Categorización Rigurosa del Comportamiento
                if es_total:
                    casos_totales_control += 1
                    if es_automatica or codigo_final is not None:
                        if not requiere_revision_operativa:
                            controles_tratados_como_cuenta += 1
                            decision_categoria = "CONTROL_TRATADO_COMO_CUENTA"
                        else:
                            controles_correctamente_separados += 1
                            decision_categoria = "CONTROL_ARITMETICO_SEPARADO"
                    else:
                        controles_correctamente_separados += 1
                        decision_categoria = "CONTROL_ARITMETICO_SEPARADO"

                elif esperado is not None:
                    casos_evaluables_clasificacion += 1
                    if es_automatica:
                        if codigo_final == esperado:
                            auto_correctas += 1
                            decision_categoria = "AUTOMATICA_CORRECTA"
                        else:
                            auto_incorrectas += 1
                            decision_categoria = "AUTOMATICA_INCORRECTA"
                    else:
                        if debe_auto:
                            revisiones_evitables += 1
                            decision_categoria = "REVISION_EVITABLE"
                        else:
                            revisiones_justificadas += 1
                            decision_categoria = "REVISION_JUSTIFICADA"

                else:
                    casos_sin_codigo_verificable += 1
                    if es_automatica:
                        automatizaciones_indebidas += 1
                        decision_categoria = "AUTOMATIZACION_INDEBIDA"
                    else:
                        revisiones_justificadas += 1
                        decision_categoria = "REVISION_JUSTIFICADA"

                results_detail.append({
                    "id": cid,
                    "nombre": nombre,
                    "tipo": tipo,
                    "monto": monto,
                    "codigo_esperado": esperado,
                    "codigo_obtenido": codigo_final,
                    "confianza_clasificacion": conf_clasif,
                    "es_automatica": es_automatica,
                    "requiere_revision": requiere_revision_operativa,
                    "decision_categoria": decision_categoria,
                    "alts_sugeridas": codigos_alts,
                    "top1_ok": top1_ok,
                    "top3_ok": top3_ok,
                })

            total_casos = len(cases)
            denominador_cobertura = casos_evaluables_clasificacion
            cobertura_auto = (auto_correctas / denominador_cobertura) if denominador_cobertura > 0 else 0.0
            total_auto = auto_correctas + auto_incorrectas + automatizaciones_indebidas
            precision_auto = (auto_correctas / total_auto) if total_auto > 0 else 1.0

            tasa_top1 = (top1_hits / total_eval_top) if total_eval_top > 0 else 0.0
            tasa_top3 = (top3_hits / total_eval_top) if total_eval_top > 0 else 0.0

            return {
                "total_casos": total_casos,
                "desglose_casos": {
                    "casos_evaluables_con_codigo": casos_evaluables_clasificacion,
                    "casos_sin_codigo_verificable_ambiguos_desconocidos": casos_sin_codigo_verificable,
                    "casos_controles_totales": casos_totales_control,
                },
                "metricas_clasificacion": {
                    "auto_correctas": auto_correctas,
                    "auto_incorrectas": auto_incorrectas,
                    "automatizaciones_indebidas": automatizaciones_indebidas,
                    "revision_justificada": revisiones_justificadas,
                    "revision_evitable": revisiones_evitables,
                    "controles_correctamente_separados": controles_correctamente_separados,
                    "controles_tratados_como_cuenta": controles_tratados_como_cuenta,
                    "denominador_cobertura": denominador_cobertura,
                    "cobertura_automatica": cobertura_auto,
                    "precision_automatica": precision_auto,
                },
                "metricas_sugerencias_ui": {
                    "denominador_sugerencias": total_eval_top,
                    "top1_hits": top1_hits,
                    "top3_hits": top3_hits,
                    "tasa_top1": tasa_top1,
                    "tasa_top3": tasa_top3,
                },
                "detalle_casos": results_detail,
            }
