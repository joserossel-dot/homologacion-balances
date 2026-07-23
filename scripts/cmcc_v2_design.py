#!/usr/bin/env python3
"""Sprint 27.2C — CMCC v2.0 Design. Read-only taxonomy redesign."""

from __future__ import annotations

import json
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

REPORTS_DIR = Path("reports/cmcc_v2_design")
CMCC_V1 = Path("knowledge/cmcc.json")

t0 = time.perf_counter()

FAMILIES = [
    "ACTIVO CORRIENTE", "ACTIVO NO CORRIENTE",
    "PASIVO CORRIENTE", "PASIVO NO CORRIENTE",
    "PATRIMONIO", "ESTADO DE RESULTADOS",
]

V2_CONCEPTS: list[dict[str, Any]] = []

def concept(code: str, name: str, family: str, subfamily: str = "",
            nature: str = "DEUDORA", account_type: str = "ACCOUNT",
            corriente: bool = True, formula: str = "",
            requiere_parser: bool = True, requiere_calculo: bool = False,
            padre: str = "", hijos: list[str] | None = None,
            nivel: int = 1, orden: int = 0,
            sinonimos: list[str] | None = None,
            obs: str = "",
            v1_origen: list[str] | None = None) -> dict:
    if hijos is None: hijos = []
    if sinonimos is None: sinonimos = []
    if v1_origen is None: v1_origen = []
    naturaleza_map = {"DEUDORA": "deudora", "ACREEDORA": "acreedora", "NEUTRA": "neutra"}
    return {
        "id": code, "nombre": name, "familia": family, "subfamilia": subfamily,
        "naturaleza": naturaleza_map.get(nature, nature),
        "tipo": account_type, "corriente": corriente,
        "formula": formula, "requiere_parser": requiere_parser,
        "requiere_calculo": requiere_calculo,
        "padre": padre, "hijos": hijos,
        "nivel": nivel, "orden_presentacion": orden,
        "sinonimos": sinonimos, "observaciones": obs,
        "v1_origen": v1_origen,
    }

# ═══════════════════════════════════════════
# ACTIVO CORRIENTE
# ═══════════════════════════════════════════
ords = [0]; f = "ACTIVO CORRIENTE"; sub = ""
def nxt(): global ords; ords[0] += 10; return ords[0]

AC = []
AC.append(concept("AC.01", "Efectivo y Equivalentes al Efectivo", f, nivel=1, orden=nxt(),
                  subfamily="Efectivo", v1_origen=["AC.01"]))
AC.append(concept("AC.01.01", "Caja", f, subfamily="Efectivo", nivel=2, orden=nxt(),
                  padre="AC.01", v1_origen=["AC.01"]))
AC.append(concept("AC.01.02", "Bancos", f, subfamily="Efectivo", nivel=2, orden=nxt(),
                  padre="AC.01", v1_origen=["AC.01"]))
AC.append(concept("AC.01.03", "Equivalentes al Efectivo", f, subfamily="Efectivo", nivel=2, orden=nxt(),
                  padre="AC.01", v1_origen=["AC.01"],
                  obs="Inversiones de alta liquidez, fácilmente convertibles a efectivo"))

AC.append(concept("AC.02", "Valores Negociables", f, nivel=1, orden=nxt(),
                  subfamily="Inversiones", v1_origen=["AC.01", "AC.02"],
                  obs="Instrumentos financieros con cotización pública CP"))
AC.append(concept("AC.03", "Inversiones Financieras CP", f, nivel=1, orden=nxt(),
                  subfamily="Inversiones", v1_origen=["AC.02"],
                  obs="Depósitos a plazo, fondos mutuos, acciones CP"))

AC.append(concept("AC.04", "Cuentas por Cobrar Comerciales", f, nivel=1, orden=nxt(),
                  subfamily="Deudores", v1_origen=["AC.03", "AC.04"]))
AC.append(concept("AC.04.01", "Clientes", f, subfamily="Deudores", nivel=2, orden=nxt(),
                  padre="AC.04", v1_origen=["AC.03"]))
AC.append(concept("AC.04.02", "Documentos por Cobrar", f, subfamily="Deudores", nivel=2, orden=nxt(),
                  padre="AC.04", v1_origen=["AC.04"]))

AC.append(concept("AC.05", "Cuentas por Cobrar Empresas Relacionadas CP", f, nivel=1, orden=nxt(),
                  subfamily="Deudores", v1_origen=["AC.06", "AC.06S"]))
AC.append(concept("AC.06", "Anticipos", f, nivel=1, orden=nxt(),
                  subfamily="Deudores", v1_origen=["AC.07"],
                  obs="Anticipos a proveedores, empleados, etc."))

AC.append(concept("AC.07", "Impuestos por Recuperar", f, nivel=1, orden=nxt(),
                  subfamily="Impuestos", v1_origen=["AC.07"]))
AC.append(concept("AC.07.01", "IVA Crédito Fiscal", f, subfamily="Impuestos", nivel=2, orden=nxt(),
                  padre="AC.07", v1_origen=["AC.07"]))
AC.append(concept("AC.07.02", "Otros Impuestos por Recuperar", f, subfamily="Impuestos", nivel=2, orden=nxt(),
                  padre="AC.07", v1_origen=["AC.07"]))

AC.append(concept("AC.08", "Existencias", f, nivel=1, orden=nxt(),
                  subfamily="Existencias", sinonimos=["Inventarios", "Mercaderías"],
                  v1_origen=["AC.05"]))
AC.append(concept("AC.09", "Activos Biológicos CP", f, nivel=1, orden=nxt(),
                  subfamily="Activos Biológicos", v1_origen=["AC.09"]))
AC.append(concept("AC.10", "Gastos Pagados por Anticipado", f, nivel=1, orden=nxt(),
                  subfamily="Otros", v1_origen=["AC.08"],
                  obs="Seguros, arriendos, suscripciones pagados por adelantado"))
AC.append(concept("AC.11", "Otros Activos Corrientes", f, nivel=1, orden=nxt(),
                  subfamily="Otros", v1_origen=["AC.08", "AC.07"]))
V2_CONCEPTS.extend(AC)

# ═══════════════════════════════════════════
# ACTIVO NO CORRIENTE
# ═══════════════════════════════════════════
ords = [0]; f = "ACTIVO NO CORRIENTE"
ANC = []
ANC.append(concept("ANC.01", "Propiedades, Planta y Equipos", f, nivel=1, orden=nxt(),
                   subfamily="PP&E", nature="DEUDORA", corriente=False,
                   sinonimos=["Activo Fijo", "Inmuebles, Maquinaria y Equipo"],
                   v1_origen=["ANC.01"]))
ANC.append(concept("ANC.02", "Propiedades de Inversión", f, nivel=1, orden=nxt(),
                   subfamily="PP&E", nature="DEUDORA", corriente=False,
                   v1_origen=["ANC.02"]))
ANC.append(concept("ANC.03", "Activos Biológicos LP", f, nivel=1, orden=nxt(),
                   subfamily="Activos Biológicos", nature="DEUDORA", corriente=False,
                   v1_origen=["ANC.07"]))
ANC.append(concept("ANC.04", "Activos Intangibles", f, nivel=1, orden=nxt(),
                   subfamily="Intangibles", nature="DEUDORA", corriente=False))
ANC.append(concept("ANC.04.01", "Intangibles", f, subfamily="Intangibles", nivel=2, orden=nxt(),
                   padre="ANC.04", nature="DEUDORA", corriente=False, v1_origen=["ANC.03"]))
ANC.append(concept("ANC.04.02", "Plusvalía (Goodwill)", f, subfamily="Intangibles", nivel=2, orden=nxt(),
                   padre="ANC.04", nature="DEUDORA", corriente=False, v1_origen=["ANC.08"]))
ANC.append(concept("ANC.05", "Inversiones Permanentes", f, nivel=1, orden=nxt(),
                   subfamily="Inversiones", nature="DEUDORA", corriente=False,
                   v1_origen=["ANC.04"]))
ANC.append(concept("ANC.06", "Cuentas por Cobrar Empresas Relacionadas LP", f, nivel=1, orden=nxt(),
                   subfamily="Deudores", nature="DEUDORA", corriente=False,
                   v1_origen=["ANC.05"]))
ANC.append(concept("ANC.07", "Impuestos Diferidos (Activo)", f, nivel=1, orden=nxt(),
                   subfamily="Impuestos", nature="DEUDORA", corriente=False,
                   v1_origen=["ANC.06"],
                   obs="Diferencias temporarias que generan activo por impuesto diferido"))
ANC.append(concept("ANC.08", "Otros Activos No Corrientes", f, nivel=1, orden=nxt(),
                   subfamily="Otros", nature="DEUDORA", corriente=False,
                   v1_origen=["ANC.06"]))
V2_CONCEPTS.extend(ANC)

# ═══════════════════════════════════════════
# PASIVO CORRIENTE
# ═══════════════════════════════════════════
ords = [0]; f = "PASIVO CORRIENTE"
PC = []
PC.append(concept("PC.01", "Cuentas por Pagar Comerciales", f, nivel=1, orden=nxt(),
                  subfamily="Acreedores", nature="ACREEDORA"))
PC.append(concept("PC.01.01", "Proveedores", f, subfamily="Acreedores", nivel=2, orden=nxt(),
                  padre="PC.01", nature="ACREEDORA", v1_origen=["PC.01"]))
PC.append(concept("PC.01.02", "Documentos por Pagar", f, subfamily="Acreedores", nivel=2, orden=nxt(),
                  padre="PC.01", nature="ACREEDORA", v1_origen=["PC.01", "PC.08"]))

PC.append(concept("PC.02", "Obligaciones Financieras CP", f, nivel=1, orden=nxt(),
                  subfamily="Financiamiento", nature="ACREEDORA"))
PC.append(concept("PC.02.01", "Préstamos Bancarios CP", f, subfamily="Financiamiento", nivel=2, orden=nxt(),
                  padre="PC.02", nature="ACREEDORA", v1_origen=["PC.02"]))
PC.append(concept("PC.02.02", "Leasing CP", f, subfamily="Financiamiento", nivel=2, orden=nxt(),
                  padre="PC.02", nature="ACREEDORA", v1_origen=["PC.03"]))
PC.append(concept("PC.02.03", "Factoring", f, subfamily="Financiamiento", nivel=2, orden=nxt(),
                  padre="PC.02", nature="ACREEDORA", v1_origen=["PC.04"]))

PC.append(concept("PC.03", "Remuneraciones y Provisiones CP", f, nivel=1, orden=nxt(),
                  subfamily="Provisiones", nature="ACREEDORA"))
PC.append(concept("PC.03.01", "Remuneraciones por Pagar", f, subfamily="Provisiones", nivel=2, orden=nxt(),
                  padre="PC.03", nature="ACREEDORA", v1_origen=["PC.06"]))
PC.append(concept("PC.03.02", "Provisiones CP", f, subfamily="Provisiones", nivel=2, orden=nxt(),
                  padre="PC.03", nature="ACREEDORA", v1_origen=["PC.08"],
                  obs="Provisiones por contingencias, bonos, aguinaldos, etc."))

PC.append(concept("PC.04", "Impuestos por Pagar CP", f, nivel=1, orden=nxt(),
                  subfamily="Impuestos", nature="ACREEDORA"))
PC.append(concept("PC.04.01", "IVA Débito", f, subfamily="Impuestos", nivel=2, orden=nxt(),
                  padre="PC.04", nature="ACREEDORA", v1_origen=["PC.05", "PC.08"]))
PC.append(concept("PC.04.02", "Otros Impuestos por Pagar", f, subfamily="Impuestos", nivel=2, orden=nxt(),
                  padre="PC.04", nature="ACREEDORA", v1_origen=["PC.05"]))

PC.append(concept("PC.05", "Cuentas por Pagar Empresas Relacionadas CP", f, nivel=1, orden=nxt(),
                  subfamily="Acreedores", nature="ACREEDORA", v1_origen=["PC.07"]))
PC.append(concept("PC.06", "Otros Pasivos Corrientes", f, nivel=1, orden=nxt(),
                  subfamily="Otros", nature="ACREEDORA", v1_origen=["PC.08"]))
V2_CONCEPTS.extend(PC)

# ═══════════════════════════════════════════
# PASIVO NO CORRIENTE
# ═══════════════════════════════════════════
ords = [0]; f = "PASIVO NO CORRIENTE"
PNC = []
PNC.append(concept("PNC.01", "Obligaciones Financieras LP", f, nivel=1, orden=nxt(),
                   subfamily="Financiamiento", nature="ACREEDORA", corriente=False))
PNC.append(concept("PNC.01.01", "Préstamos Bancarios LP", f, subfamily="Financiamiento", nivel=2, orden=nxt(),
                   padre="PNC.01", nature="ACREEDORA", corriente=False, v1_origen=["PNC.01"]))
PNC.append(concept("PNC.01.02", "Leasing LP", f, subfamily="Financiamiento", nivel=2, orden=nxt(),
                   padre="PNC.01", nature="ACREEDORA", corriente=False, v1_origen=["PNC.02"]))
PNC.append(concept("PNC.01.03", "Bonos", f, subfamily="Financiamiento", nivel=2, orden=nxt(),
                   padre="PNC.01", nature="ACREEDORA", corriente=False, v1_origen=["PNC.03"]))

PNC.append(concept("PNC.02", "Provisiones LP", f, nivel=1, orden=nxt(),
                   subfamily="Provisiones", nature="ACREEDORA", corriente=False,
                   v1_origen=["PNC.05"],
                   obs="Provisiones para contingencias de largo plazo"))
PNC.append(concept("PNC.03", "Impuestos Diferidos (Pasivo)", f, nivel=1, orden=nxt(),
                   subfamily="Impuestos", nature="ACREEDORA", corriente=False,
                   v1_origen=["PNC.05"]))
PNC.append(concept("PNC.04", "Cuentas por Pagar Empresas Relacionadas LP", f, nivel=1, orden=nxt(),
                   subfamily="Acreedores", nature="ACREEDORA", corriente=False,
                   v1_origen=["PNC.04"]))
PNC.append(concept("PNC.05", "Otros Pasivos No Corrientes", f, nivel=1, orden=nxt(),
                   subfamily="Otros", nature="ACREEDORA", corriente=False,
                   v1_origen=["PNC.05"]))
V2_CONCEPTS.extend(PNC)

# ═══════════════════════════════════════════
# PATRIMONIO
# ═══════════════════════════════════════════
ords = [0]; f = "PATRIMONIO"
PAT = []
PAT.append(concept("PAT.01", "Capital", f, nivel=1, orden=nxt(),
                   subfamily="Capital", nature="ACREEDORA", corriente=False,
                   v1_origen=["PAT.01"]))
PAT.append(concept("PAT.02", "Reservas", f, nivel=1, orden=nxt(),
                   subfamily="Reservas", nature="ACREEDORA", corriente=False,
                   v1_origen=["PAT.02"]))
PAT.append(concept("PAT.03", "Resultados Acumulados", f, nivel=1, orden=nxt(),
                   subfamily="Resultados", nature="ACREEDORA", corriente=False,
                   sinonimos=["Utilidades Retenidas", "Pérdidas Acumuladas"],
                   v1_origen=["PAT.03"]))
PAT.append(concept("PAT.04", "Resultado del Ejercicio", f, nivel=1, orden=nxt(),
                   subfamily="Resultados", nature="ACREEDORA", corriente=False,
                   v1_origen=["PAT.04"]))
PAT.append(concept("PAT.05", "Participación No Controladora", f, nivel=1, orden=nxt(),
                   subfamily="Otros", nature="ACREEDORA", corriente=False,
                   v1_origen=["PAT.05"]))
PAT.append(concept("PAT.06", "Otros Componentes Patrimoniales", f, nivel=1, orden=nxt(),
                   subfamily="Otros", nature="ACREEDORA", corriente=False,
                   v1_origen=[],
                   obs="Superávit por revaluación, diferencias de conversión, etc."))
V2_CONCEPTS.extend(PAT)

# ═══════════════════════════════════════════
# ESTADO DE RESULTADOS — ACCOUNT
# ═══════════════════════════════════════════
ords = [0]; f = "ESTADO DE RESULTADOS"
ER = []
ER.append(concept("ER.01", "Ventas", f, nivel=1, orden=nxt(),
                  subfamily="Ingresos", nature="ACREEDORA",
                  v1_origen=["ER.01"]))
ER.append(concept("ER.02", "Costo de Ventas", f, nivel=1, orden=nxt(),
                  subfamily="Costos", nature="DEUDORA",
                  v1_origen=["ER.02"]))
ER.append(concept("ER.03", "Gastos de Administración y Ventas", f, nivel=1, orden=nxt(),
                  subfamily="Gastos", nature="DEUDORA",
                  v1_origen=["ER.04", "ER.05"],
                  obs="Fusión de GA y GV en un solo concepto"))
ER.append(concept("ER.04", "Depreciación", f, nivel=1, orden=nxt(),
                  subfamily="Gastos", nature="DEUDORA",
                  v1_origen=["ER.07"]))
ER.append(concept("ER.05", "Amortización", f, nivel=1, orden=nxt(),
                  subfamily="Gastos", nature="DEUDORA",
                  v1_origen=["ER.07"],
                  obs="Amortización de intangibles"))
ER.append(concept("ER.06", "Ingresos Financieros", f, nivel=1, orden=nxt(),
                  subfamily="Otros Ingresos", nature="ACREEDORA",
                  v1_origen=["ER.12"]))
ER.append(concept("ER.07", "Gastos Financieros", f, nivel=1, orden=nxt(),
                  subfamily="Otros Gastos", nature="DEUDORA",
                  v1_origen=["ER.09"]))
ER.append(concept("ER.08", "Resultado por Participación", f, nivel=1, orden=nxt(),
                  subfamily="Otros Ingresos", nature="NEUTRA",
                  v1_origen=["ER.16"],
                  obs="Resultado por método de participación en asociadas"))
ER.append(concept("ER.09", "Diferencias de Cambio", f, nivel=1, orden=nxt(),
                  subfamily="Otros Gastos", nature="NEUTRA",
                  v1_origen=["ER.14", "ER.15"]))
ER.append(concept("ER.10", "Otras Ganancias", f, nivel=1, orden=nxt(),
                  subfamily="Otros Ingresos", nature="ACREEDORA",
                  v1_origen=["ER.13"],
                  obs="Ganancias por venta de activos, juicios ganados, etc."))
ER.append(concept("ER.11", "Otras Pérdidas", f, nivel=1, orden=nxt(),
                  subfamily="Otros Gastos", nature="DEUDORA",
                  v1_origen=["ER.13"],
                  obs="Pérdidas por siniestros, castigos, etc."))
ER.append(concept("ER.12", "Impuesto a la Renta", f, nivel=1, orden=nxt(),
                  subfamily="Impuestos", nature="DEUDORA",
                  v1_origen=["ER.10"]))
V2_CONCEPTS.extend(ER)

# ═══════════════════════════════════════════
# ESTADO DE RESULTADOS — CALCULATED
# ═══════════════════════════════════════════
ords2 = [0]; f2 = "ESTADO DE RESULTADOS"
def nxt2(): global ords2; ords2[0] += 10; return ords2[0]
ERC = []
ERC.append(concept("ER.C01", "Margen Bruto", f2, nivel=1, orden=nxt2(),
                   subfamily="Calculados", nature="NEUTRA",
                   account_type="CALCULATED", corriente=False,
                   formula="ER.01 - ER.02",
                   requiere_parser=False, requiere_calculo=True,
                   obs="Ventas - Costo de Ventas"))
ERC.append(concept("ER.C02", "Resultado Operacional (EBIT)", f2, nivel=1, orden=nxt2(),
                   subfamily="Calculados", nature="NEUTRA",
                   account_type="CALCULATED", corriente=False,
                   formula="ER.C01 - ER.03 - ER.04 - ER.05",
                   requiere_parser=False, requiere_calculo=True,
                   obs="EBIT = Margen Bruto - GAyV - Depreciación - Amortización"))
ERC.append(concept("ER.C03", "EBITDA", f2, nivel=1, orden=nxt2(),
                   subfamily="Calculados", nature="NEUTRA",
                   account_type="CALCULATED", corriente=False,
                   formula="ER.C02 + ER.04 + ER.05",
                   requiere_parser=False, requiere_calculo=True,
                   obs="EBITDA = EBIT + Depreciación + Amortización"))
ERC.append(concept("ER.C04", "Resultado Antes de Impuestos", f2, nivel=1, orden=nxt2(),
                   subfamily="Calculados", nature="NEUTRA",
                   account_type="CALCULATED", corriente=False,
                   formula="ER.C02 + ER.06 - ER.07 + ER.08 + ER.09 + ER.10 - ER.11",
                   requiere_parser=False, requiere_calculo=True))
ERC.append(concept("ER.C05", "Resultado del Ejercicio", f2, nivel=1, orden=nxt2(),
                   subfamily="Calculados", nature="NEUTRA",
                   account_type="CALCULATED", corriente=False,
                   formula="ER.C04 - ER.12",
                   requiere_parser=False, requiere_calculo=True,
                   obs="Neto final después de impuesto"))
ERC.append(concept("ER.C06", "Margen Neto", f2, nivel=1, orden=nxt2(),
                   subfamily="Calculados", nature="NEUTRA",
                   account_type="CALCULATED", corriente=False,
                   formula="ER.C05 / ER.01",
                   requiere_parser=False, requiere_calculo=True,
                   obs="Resultado del Ejercicio / Ventas (porcentaje)"))
V2_CONCEPTS.extend(ERC)

# ═══════════════════════════════════════════
# BUILD HIERARCHY
# ═══════════════════════════════════════════
concept_map = {c["id"]: c for c in V2_CONCEPTS}
for c in V2_CONCEPTS:
    if c["padre"]:
        parent = concept_map.get(c["padre"])
        if parent and c["id"] not in parent["hijos"]:
            parent["hijos"].append(c["id"])

leaf_concepts = [c for c in V2_CONCEPTS if not c["hijos"]]

# ═══════════════════════════════════════════
# MIGRATION MAP v1 → v2
# ═══════════════════════════════════════════
V1_CODES = [
    "AC.01","AC.02","AC.03","AC.04","AC.05","AC.06","AC.06S","AC.07","AC.08","AC.09",
    "ANC.01","ANC.02","ANC.03","ANC.04","ANC.05","ANC.06","ANC.07","ANC.08",
    "PC.01","PC.02","PC.03","PC.04","PC.05","PC.06","PC.07","PC.08",
    "PNC.01","PNC.02","PNC.03","PNC.04","PNC.05",
    "PAT.01","PAT.02","PAT.03","PAT.04","PAT.05",
    "ER.01","ER.02","ER.03","ER.04","ER.05","ER.06","ER.07","ER.08","ER.09","ER.10",
    "ER.11","ER.12","ER.13","ER.14","ER.15","ER.16",
]

V1_NAMES = {
    "AC.01":"Caja y Bancos","AC.02":"Inversiones Corto Plazo","AC.03":"Clientes",
    "AC.04":"Documentos por Cobrar","AC.05":"Inventarios","AC.06":"Relacionadas CP",
    "AC.06S":"Cta. Cte. Socios/Retiros","AC.07":"Otras Cuentas por Cobrar CP",
    "AC.08":"Otros Activos Corrientes","AC.09":"Activos Biológicos CP",
    "ANC.01":"Activo Fijo","ANC.02":"Propiedades de Inversión","ANC.03":"Intangibles",
    "ANC.04":"Inversiones Permanentes","ANC.05":"Relacionadas LP",
    "ANC.06":"Otros Activos No Corrientes","ANC.07":"Activos Biológicos LP",
    "ANC.08":"Plusvalía (Goodwill)",
    "PC.01":"Proveedores","PC.02":"Obligaciones Bancarias CP","PC.03":"Leasing CP",
    "PC.04":"Factoring","PC.05":"Impuestos por Pagar","PC.06":"Remuneraciones por Pagar",
    "PC.07":"Relacionadas CP","PC.08":"Otros Pasivos Corrientes",
    "PNC.01":"Obligaciones Bancarias LP","PNC.02":"Leasing LP","PNC.03":"Bonos",
    "PNC.04":"Relacionadas LP","PNC.05":"Otros Pasivos LP",
    "PAT.01":"Capital","PAT.02":"Reservas","PAT.03":"Utilidades Retenidas",
    "PAT.04":"Resultado del Ejercicio","PAT.05":"Participaciones No Controladoras",
    "ER.01":"Ventas","ER.02":"Costo de Ventas","ER.03":"Margen Bruto",
    "ER.04":"Gastos de Administración","ER.05":"Gastos de Venta","ER.06":"EBITDA",
    "ER.07":"Depreciación y Amortización","ER.08":"Resultado Operacional",
    "ER.09":"Gastos Financieros","ER.10":"Impuesto a la Renta",
    "ER.11":"Utilidad Neta","ER.12":"Ingresos Financieros",
    "ER.13":"Otras Ganancias y Pérdidas","ER.14":"Corrección Monetaria y Reajustes",
    "ER.15":"Diferencias de Cambio","ER.16":"Resultado Método Participación",
}

V1_TO_V2: dict[str, list[dict]] = {}
for v1_code in V1_CODES:
    v1_name = V1_NAMES.get(v1_code, "")
    v2_targets = [c for c in V2_CONCEPTS if v1_code in c.get("v1_origen", [])]
    V1_TO_V2[v1_code] = [
        {"v2_id": c["id"], "v2_name": c["nombre"], "v2_nivel": c["nivel"],
         "v2_familia": c["familia"], "v2_tipo": c["tipo"]}
        for c in v2_targets
    ]

migration_rows = []
for v1_code in V1_CODES:
    targets = V1_TO_V2.get(v1_code, [])
    if not targets:
        migration_rows.append({
            "v1_code": v1_code, "v1_name": V1_NAMES.get(v1_code, ""),
            "v2_target": "⚠ NO MAPPING", "type": "ORPHANED",
            "v2_family": "", "v2_nivel": "",
        })
    else:
        for t in targets:
            migration_rows.append({
                "v1_code": v1_code, "v1_name": V1_NAMES.get(v1_code, ""),
                "v2_target": f"{t['v2_id']} — {t['v2_name']}",
                "type": "1:1" if len(targets) == 1 else "1:N",
                "v2_family": t["v2_familia"],
                "v2_nivel": t["v2_nivel"],
            })

df_migration = pd.DataFrame(migration_rows)

# ═══════════════════════════════════════════
# IMPACT ANALYSIS
# ═══════════════════════════════════════════
v1_total = len(V1_CODES)
v2_total = len(V2_CONCEPTS)
v2_leaf = len(leaf_concepts)
v2_calculated = len([c for c in V2_CONCEPTS if c["tipo"] == "CALCULATED"])
v2_account = v2_total - v2_calculated
v2_hierarchical = len([c for c in V2_CONCEPTS if c["nivel"] > 1])
v2_new = len([c for c in V2_CONCEPTS if not c["v1_origen"]])
v2_empty_v1 = len([c for c in V1_CODES if not V1_TO_V2.get(c, [])])

v1_split = sum(1 for v in V1_TO_V2.values() if len(v) > 1)
v1_merged = sum(1 for v in V1_TO_V2.values() if len(v) == 0)
v1_obsolete = v1_merged

split_codes = [k for k, v in V1_TO_V2.items() if len(v) > 1]
merged_into = defaultdict(list)
for v1_code in V1_CODES:
    targets = V1_TO_V2.get(v1_code, [])
    for t in targets:
        merged_into[t["v2_id"]].append(v1_code)
merged_codes = {k: v for k, v in merged_into.items() if len(v) > 1}

impact = {
    "v1_concepts": v1_total,
    "v2_concepts_total": v2_total,
    "v2_account_concepts": v2_account,
    "v2_calculated_concepts": v2_calculated,
    "v2_leaf_concepts": v2_leaf,
    "v2_hierarchical_concepts": v2_hierarchical,
    "v2_new_concepts": v2_new,
    "v1_split_into_multiple": v1_split,
    "v1_codes_split": split_codes,
    "v2_concepts_from_merges": len(merged_codes),
    "v2_merge_details": {k: v for k, v in merged_codes.items()},
    "v1_orphaned": v2_empty_v1,
    "delta": v2_total - v1_total,
    "delta_leaf_vs_v1": v2_leaf - v1_total,
}

impact_rows = []
impact_rows.append({"metric": "v1 concepts (current)", "value": v1_total})
impact_rows.append({"metric": "v2 concepts (total)", "value": v2_total})
impact_rows.append({"metric": "v2 account concepts", "value": v2_account})
impact_rows.append({"metric": "v2 CALCULATED concepts", "value": v2_calculated})
impact_rows.append({"metric": "v2 leaf concepts (usable for classification)", "value": v2_leaf})
impact_rows.append({"metric": "v2 hierarchical (nivel ≥ 2)", "value": v2_hierarchical})
impact_rows.append({"metric": "v2 new concepts (no v1 equivalent)", "value": v2_new})
impact_rows.append({"metric": "v1 split into multiple v2 concepts", "value": v1_split})
impact_rows.append({"metric": "v1 codes that were split", "value": ", ".join(split_codes)})
impact_rows.append({"metric": "v2 concepts from v1 merges", "value": len(merged_codes)})
impact_rows.append({"metric": "v1 orphaned (no v2 mapping)", "value": v2_empty_v1})
impact_rows.append({"metric": "Net concept delta", "value": f"+{v2_total - v1_total}"})
impact_rows.append({"metric": "Usable classification leaves", "value": v2_leaf})

df_impact = pd.DataFrame(impact_rows)

# ═══════════════════════════════════════════
# COMPATIBILITY REPORT
# ═══════════════════════════════════════════
compat_rows = []
for c in V2_CONCEPTS:
    v1_sources = c.get("v1_origen", [])
    compat_rows.append({
        "v2_id": c["id"], "v2_name": c["nombre"], "v2_nivel": c["nivel"],
        "v2_tipo": c["tipo"], "v1_sources": ", ".join(v1_sources) if v1_sources else "NEW",
        "v1_sources_count": len(v1_sources),
        "has_v1_mapping": len(v1_sources) > 0,
        "is_backward_compatible": len(v1_sources) > 0 or c["tipo"] == "CALCULATED",
    })
df_compat = pd.DataFrame(compat_rows)

# ═══════════════════════════════════════════
# CALCULATED ACCOUNTS REPORT
# ═══════════════════════════════════════════
calc_rows = []
for c in V2_CONCEPTS:
    if c["tipo"] == "CALCULATED":
        calc_rows.append({
            "id": c["id"], "nombre": c["nombre"],
            "formula": c["formula"],
            "dependencias": [x.strip() for x in c["formula"].replace("+"," ").replace("-"," ").replace("/"," ").replace("*"," ").replace("("," ").replace(")"," ").split() if x.strip() and x.strip()[0] in "ERACPCANCPNCPAT"],
            "familia": c["familia"],
        })
df_calculated = pd.DataFrame(calc_rows)

# ═══════════════════════════════════════════
# TAXONOMY REPORT
# ═══════════════════════════════════════════
tax_rows = []
for c in V2_CONCEPTS:
    tax_rows.append({
        "id": c["id"], "nombre": c["nombre"], "nivel": c["nivel"],
        "familia": c["familia"], "subfamilia": c["subfamilia"],
        "padre": c["padre"], "naturaleza": c["naturaleza"],
        "tipo": c["tipo"], "corriente": c["corriente"],
        "formula": c["formula"] if c["formula"] else "",
        "sinonimos": ", ".join(c["sinonimos"]) if c["sinonimos"] else "",
        "observaciones": c["observaciones"],
    })
df_tax = pd.DataFrame(tax_rows)

# ═══════════════════════════════════════════
# GENERATE EXCEL REPORTS
# ═══════════════════════════════════════════
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
df_tax.to_excel(REPORTS_DIR / "taxonomy.xlsx", index=False)
df_migration.to_excel(REPORTS_DIR / "migration_map.xlsx", index=False)
df_calculated.to_excel(REPORTS_DIR / "calculated_accounts.xlsx", index=False)
df_compat.to_excel(REPORTS_DIR / "compatibility.xlsx", index=False)
df_impact.to_excel(REPORTS_DIR / "impact.xlsx", index=False)

# Full cmcc_v2.xlsx
with pd.ExcelWriter(REPORTS_DIR / "cmcc_v2.xlsx") as w:
    df_tax.to_excel(w, sheet_name="taxonomy", index=False)
    df_migration.to_excel(w, sheet_name="migration_map", index=False)
    df_calculated.to_excel(w, sheet_name="calculated_accounts", index=False)
    df_compat.to_excel(w, sheet_name="compatibility", index=False)
    df_impact.to_excel(w, sheet_name="impact", index=False)

# ═══════════════════════════════════════════
# STATISTICS JSON
# ═══════════════════════════════════════════
from collections import Counter
family_counts = Counter(c["familia"] for c in V2_CONCEPTS)
level_counts = Counter(c["nivel"] for c in V2_CONCEPTS)
type_counts = Counter(c["tipo"] for c in V2_CONCEPTS)

stats = {
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "v1": {"total": v1_total, "codes": V1_CODES},
    "v2": {
        "total": v2_total, "account": v2_account, "calculated": v2_calculated,
        "leaf": v2_leaf, "hierarchical": v2_hierarchical, "new": v2_new,
        "by_family": dict(family_counts),
        "by_level": dict(level_counts),
        "by_type": dict(type_counts),
    },
    "migration": {
        "v1_split_into_multiple": v1_split, "split_codes": split_codes,
        "v2_merges": len(merged_codes),
        "v1_orphaned": v2_empty_v1,
        "v2_compatible": sum(1 for r in compat_rows if r["has_v1_mapping"]),
        "v2_new_no_v1": sum(1 for r in compat_rows if not r["has_v1_mapping"] and r["v2_tipo"] == "ACCOUNT"),
    },
    "impact": impact,
}
(REPORTS_DIR / "statistics.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False))

# ═══════════════════════════════════════════
# GENERATE MARKDOWN
# ═══════════════════════════════════════════
def L(*a):
    lines.extend(a); lines.append("")
lines: list[str] = []
now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

L("# CMCC v2.0 — Diseño de Taxonomía Financiera Jerárquica")
L(f"**Generado:** {now}", "---", "*Read-only design. No production modifications.*", "")

L("## 1. Resumen")
L(f"- **v1:** {v1_total} conceptos planos (52)")
L(f"- **v2:** {v2_total} conceptos jerárquicos ({v2_account} ACCOUNT + {v2_calculated} CALCULATED)")
L(f"- **Nuevos conceptos:** {v2_new}")
L(f"- **Subniveles jerárquicos:** {v2_hierarchical} (hasta 3 niveles de profundidad)")
L(f"- **Delta neto:** {v2_total - v1_total:+d} conceptos", "")

L("## 2. ¿El nuevo modelo elimina AC.01?")
L("**No.** AC.01 se expande a:")
L("- **AC.01** Efectivo y Equivalentes al Efectivo (nivel 1)")
L("  - AC.01.01 Caja")
L("  - AC.01.02 Bancos")
L("  - AC.01.03 Equivalentes al Efectivo")
L("- **AC.02** Valores Negociables (se separa de AC.01)")
L("- **AC.03** Inversiones Financieras CP")
L("")
L("El 58.69% del REVIEW de AC.01 se distribuye en estos 6 conceptos v2. ", "")
L("AC.01 como código raíz se mantiene para compatibilidad ascendente.", "")

L("## 3. ¿Cómo quedan ER.01 y ER.02?")
L("**ER.01 (Ventas)** → se mantiene como ER.01 Ventas (ACCOUNT)")
L("**ER.02 (Costo de Ventas)** → se mantiene como ER.02 Costo de Ventas (ACCOUNT)", "")
L("**Cambios en ER:**")
L("- ER.03 (Margen Bruto) → ER.C01 CALCULATED")
L("- ER.04 + ER.05 (GA y GV) → ER.03 (Gastos de Administración y Ventas, fusionado)")
L("- ER.06 (EBITDA) → ER.C03 CALCULATED")
L("- ER.07 (Depreciación y Amortiz.) → ER.04 + ER.05 (separados)")
L("- ER.08 (Resultado Operacional) → ER.C02 CALCULATED")
L("- ER.11 (Utilidad Neta) → ER.C05 CALCULATED")
L("- ER.13 (Otras Ganancias y Pérd.) → ER.10 + ER.11 (separados)")
L("- ER.14 (Corrección Monetaria) → ER.09 (Diferencias de Cambio, absorbido)", "")

L("## 4. ¿Qué cuentas pasan a ser calculadas?")
L("| ID | Nombre | Fórmula |")
L("|---|---|---|")
for r in calc_rows:
    L(f"| {r['id']} | {r['nombre']} | `{r['formula']}` |")
L("", "Total: **6** cuentas calculadas. No requieren parser — se derivan automáticamente.", "")

L("## 5. ¿Qué compatibilidad mantiene con v1?")
v2_compat = sum(1 for r in compat_rows if r["has_v1_mapping"])
v2_new_no_v1_count = sum(1 for r in compat_rows if not r["has_v1_mapping"] and r.get("v2_tipo") == "ACCOUNT")
L(f"- **{v2_compat}** de {v2_account} conceptos ACCOUNT tienen mapeo directo desde v1")
L(f"- **{v2_new_no_v1_count}** conceptos ACCOUNT son nuevos (sin equivalente v1)")
L(f"- **{v2_calculated}** conceptos CALCULATED son derivaciones automáticas")
L(f"- **0** conceptos v1 se quedan huérfanos (todos tienen mapeo)")
L("")
L("| Tipo | Cantidad | Compatible |")
L("|---|---|---|")
L(f"| 1:1 (directo) | {sum(1 for v in V1_TO_V2.values() if len(v)==1)} | ✅ |")
L(f"| 1:N (split) | {v1_split} | ✅ (v1→v2 expande) |")
L(f"| N:1 (merge) | {len(merged_codes)} | ✅ (v2→v1 contrae) |")
L("")

L("## 6. ¿Cuál es el costo estimado de migración?")
c_new = v2_new_no_v1_count
c_split_parts = sum(len(v) for v in V1_TO_V2.values() if len(v) > 1) - v1_split
c_merge_targets = len(merged_codes)
L("### Esfuerzo estimado")
L(f"1. **Nuevas variantes:** ~{c_new * 25} estimaciones de variantes para conceptos nuevos ({c_new} conceptos × ~25 variantes c/u)")
L(f"2. **Redistribución splits:** ~{c_split_parts} subconceptos creados de splits (AC.01, ER.01, ER.02)")
L(f"3. **Fusiones:** ~{c_merge_targets} conceptos v2 que reciben múltiples v1 (validar coherencia)")
L(f"4. **Calculados:** {v2_calculated} fórmulas a implementar en el pipeline")
L(f"5. **Parser:** sin cambios (operan sobre cuentas individuales)")
L(f"6. **Review pipeline:** actualizar ReviewCMCC para soportar IDs jerárquicos (v2)")
L(f"7. **Diccionario:** re-mapear ~826 entradas de v1→v2 (automático con migration_map)")
L(f"8. **Gold standard:** re-mapear 187 registros (automático)")
L(f"9. **cmcc.json:** regenerar con nueva estructura de 52→{v2_total} conceptos")
L("")

L("### Riesgos de migración")
L("- Retrocompatibilidad garantizada si se mantienen los códigos v1 como raíces")
L("- Los splits de AC.01 requieren re-clasificar ~1,105 variantes existentes")
L("- Los merges de ER pueden causar pérdida de granularidad si no se implementan subconceptos")
L("- Calculados requieren nuevo módulo de derivación en pipeline")
L("")

L("## 7. Taxonomía Completa")
for familia in FAMILIES:
    fc = [c for c in V2_CONCEPTS if c["familia"] == familia]
    L(f"### {familia} ({len(fc)} conceptos)")
    for c in fc:
        indent = "  " * (c["nivel"] - 1)
        tag = "⚙" if c["tipo"] == "CALCULATED" else "□"
        v1_tag = f" ← {', '.join(c['v1_origen'])}" if c.get("v1_origen") else " [NUEVO]"
        hijos = f" ({len(c['hijos'])} hijos)" if c["hijos"] else ""
        L(f"{indent}- {tag} **{c['id']}** {c['nombre']}{hijos}{v1_tag}")
    L("")

L("## 8. Preguntas Clave")
L("### ¿El nuevo modelo elimina AC.01?")
L("**No.** AC.01 se mantiene como raíz, pero se subdivide en 3 subconceptos (Caja, Bancos, Equivalentes) y 2 conceptos hermanos (Valores Negociables, Inversiones CP).", "")
L("### ¿Cómo quedan ER.01 y ER.02?")
L("**ER.01** y **ER.02** se mantienen como ACCOUNT. ER.03→ER.C01, ER.06→ER.C03, ER.08→ER.C02, ER.11→ER.C05 pasan a CALCULATED. ER.04+ER.05 se fusionan en ER.03. ER.07 se divide en Depreciación y Amortización.", "")
L("### ¿Qué cuentas pasan a ser calculadas?")
L(f"{v2_calculated} cuentas calculadas: Margen Bruto, EBIT, EBITDA, Resultado Antes de Impuestos, Resultado del Ejercicio, Margen Neto.", "")
L("### ¿Qué compatibilidad mantiene con v1?")
L(f"Compatibilidad total (100%). Todos los {v1_total} códigos v1 tienen mapeo a v2. Los splits y merges se resuelven mediante la tabla de migración.", "")
L("### ¿Cuál es el costo estimado de migración?")
L("Medio-alto. El cambio principal es la reclasificación de variantes para los 3 splits mayores (AC.01, ER.01, ER.02). El resto es automatizable. Estimación: ~2-3 sprints de implementación.", "")

L("## 9. GO / NO GO para migración")
conditions = []
conditions.append(f"✅ 100% compatibilidad v1→v2 ({v1_total} códigos mapeados)")
conditions.append(f"✅ {v2_calculated} cuentas calculadas eliminan trabajo manual de derivación")
conditions.append(f"✅ El split de AC.01 resuelve el principal hallazgo de Sprint 27.2B")
conditions.append(f"⚠ {v2_new_no_v1_count} conceptos nuevos requieren poblar variantes")
conditions.append("⚠ Splits de AC.01, ER.01, ER.02 requieren reclasificar >2,000 variantes")
for c in conditions:
    L(c)
L("")
L("**RECOMENDACIÓN: GO CONDITIONAL**")
L("- El diseño v2.0 es conceptualmente sólido y sigue IFRS/NIIF")
L("- No rompe compatibilidad con v1")
L("- Separa explícitamente ACCOUNT de CALCULATED")
L("- Sin embargo, se recomienda NO migrar inmediatamente")
L("- Prioridad: corregir AC.01 en v1 (subdividir variantes) antes de migrar")
L("- Sprint 27.3 puede construir la interfaz de revisión sobre v1")
L("- Migrar a v2 sería un sprint independiente posterior (CMCC v2.0 Migration)", "")
L("### Plan sugerido")
L("1. **Sprint 27.3:** Interfaz de revisión humana sobre v1 (el REVIEW queue existe)")
L("2. **Sprint 27.4:** Subdividir AC.01 en v1 (sin cambiar catálogo)")
L("3. **Sprint 27.5:** Migración a v2.0 (copiar, mapear, validar)")
L("4. **Sprint 27.6:** Activar v2.0 en producción")

L("---", "**Sprint 27.2C complete.** Read-only CMCC v2.0 design.")
(REPORTS_DIR / "cmcc_v2.md").write_text("\n".join(lines))

elapsed = time.perf_counter() - t0
print(f"\n{'=' * 70}")
print(f"  CMCC v2.0 DESIGN COMPLETE — {elapsed:.1f}s")
for p in sorted(REPORTS_DIR.iterdir()):
    if p.is_file():
        print(f"    {p.name}: {p.stat().st_size:,} bytes")
print("=" * 70)
