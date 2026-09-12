"""
experiments/pilot_coverage/classification/benchmark_classifier_isolated.py

Benchmark del clasificador aislado y evaluación honesta de sugerencias (Encargo A5).
Garantiza:
1. No modificar el entorno ni socket.socket en tiempo de importación.
2. Context manager 'isolated_benchmark_environment' que guarda y restaura exactamente
   socket.socket, DATABASE_URL, NEON_DATABASE_URL y variables de entorno modificadas.
3. Bloqueo fail-closed de conexiones de red (connect, connect_ex) sin romper bind ni ssl.
4. Validación contable exhaustiva de la taxonomía (familias, contra-cuentas, signos y origen).
5. Limpieza garantizada de almacenamiento temporal (tempfile.TemporaryDirectory).
6. Contrato de interfaz legítimo con MotorHibridoLocal(diccionario) para _alternativas_revision.
7. Métricas honestas y trazables con denominadores explícitos.
"""

from __future__ import annotations

import contextlib
import json
import os
import pathlib
import socket
import sys
import tempfile
from typing import Any, Dict, List, Optional

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

@contextlib.contextmanager
def isolated_benchmark_environment():
    """
    Context manager que garantiza aislamiento estricto durante la ejecución del benchmark:
    - Salva y restaura el estado exacto de variables de entorno (DATABASE_URL, NEON_DATABASE_URL, etc.).
    - Bloquea conexiones de red salientes (connect, connect_ex) en fail-closed sin bloquear bind.
    - Restaura socket.socket original garantizadamente mediante try...finally.
    """
    old_env = os.environ.copy()
    old_socket_cls = socket.socket

    # 1. Configurar variables de entorno aisladas
    os.environ.pop("DATABASE_URL", None)
    os.environ.pop("NEON_DATABASE_URL", None)
    os.environ["STREAMLIT_SERVER_HEADLESS"] = "true"

    # 2. Subclase de socket que bloquea llamadas de conexión externa
    class _IsolatedSocket(old_socket_cls):
        def connect(self, *args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("Acceso a red bloqueado: el benchmark debe ejecutarse en aislamiento estricto")

        def connect_ex(self, *args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("Acceso a red bloqueado: el benchmark debe ejecutarse en aislamiento estricto")

    socket.socket = _IsolatedSocket
    try:
        yield
    finally:
        socket.socket = old_socket_cls
        os.environ.clear()
        os.environ.update(old_env)


# Casos de prueba deterministas con tipología y origen contable explícito
CASOS_BENCHMARK = [
    # Inequívocos exactos (deben clasificar automáticamente bajo umbral experimental >= 0.85)
    {"id": "EX01", "nombre": "Caja", "tipo": "ACTIVO", "monto": 100000, "esperado": "AC.01", "categoria": "inequivoco"},
    {"id": "EX02", "nombre": "Banco de Chile", "tipo": "ACTIVO", "monto": 5000000, "esperado": "AC.01", "categoria": "inequivoco"},
    {"id": "EX03", "nombre": "Clientes", "tipo": "ACTIVO", "monto": 2500000, "esperado": "AC.03", "categoria": "inequivoco"},
    {"id": "EX04", "nombre": "Proveedores Nacionales", "tipo": "PASIVO", "monto": 1200000, "esperado": "PC.01", "categoria": "inequivoco"},
    {"id": "EX05", "nombre": "Capital Pagado", "tipo": "PATRIMONIO", "monto": 10000000, "esperado": "PAT.01", "categoria": "inequivoco"},
    {"id": "EX06", "nombre": "Activos por impuestos diferidos", "tipo": "ACTIVO", "monto": 150000, "esperado": "ANC.09", "categoria": "inequivoco"},
    {"id": "EX07", "nombre": "Pasivos por impuestos diferidos", "tipo": "PASIVO", "monto": 180000, "esperado": "PNC.06", "categoria": "inequivoco"},

    # Casos clasificables que deliberadamente deben abstenerse / requerir revisión humana
    {"id": "SYN01", "nombre": "Caja Chica Sucursal Centro", "tipo": "ACTIVO", "monto": 50000, "esperado": "AC.01", "categoria": "abstencion"},
    {"id": "SYN02", "nombre": "Deudores por Ventas Comerciales", "tipo": "ACTIVO", "monto": 800000, "esperado": "AC.03", "categoria": "abstencion"},
    {"id": "SYN03", "nombre": "Acreedores Comerciales Varios", "tipo": "PASIVO", "monto": 450000, "esperado": "PC.01", "categoria": "abstencion"},
    {"id": "CA01", "nombre": "Depreciación Acumulada Maquinarias", "tipo": "PASIVO", "monto": -500000, "esperado": "ANC.01.01", "categoria": "abstencion"},
    {"id": "CA02", "nombre": "Amortización Acumulada Intangibles", "tipo": "PASIVO", "monto": -200000, "esperado": "ANC.03", "categoria": "abstencion"},
    {"id": "PAT01", "nombre": "Pérdidas Acumuladas Años Anteriores", "tipo": "ACTIVO", "monto": -1200000, "esperado": "PAT.03", "categoria": "abstencion"},

    # Casos ambiguos / sin correspondencia unívoca en catálogo
    {"id": "AMB01", "nombre": "Otras Cuentas", "tipo": "DESCONOCIDO", "monto": 10000, "esperado": None, "categoria": "ambiguo"},
    {"id": "AMB02", "nombre": "Varios y Ajustes", "tipo": "DESCONOCIDO", "monto": 25000, "esperado": None, "categoria": "ambiguo"},
    {"id": "AMB03", "nombre": "Provisión General", "tipo": "PASIVO", "monto": 300000, "esperado": "PC.09", "categoria": "ambiguo"},

    # Desconocidos / partidas extraordinarias sin estándar
    {"id": "UNK01", "nombre": "Fondo Extraordinario Proyecto Alfa", "tipo": "DESCONOCIDO", "monto": 750000, "esperado": None, "categoria": "desconocido"},
    {"id": "UNK02", "nombre": "Depósito Transitorio Sin Aplicar", "tipo": "DESCONOCIDO", "monto": 120000, "esperado": None, "categoria": "desconocido"},
]


def validar_taxonomia_catalogo(catalogo: Dict[str, Any], casos: Optional[List[Dict[str, Any]]] = None) -> None:
    """
    Valida exhaustivamente la consistencia contable y taxonómica de los casos esperados:
    1. Existencia en catalogo_maestro.json.
    2. Estado clasificable (clasificable == True).
    3. Compatibilidad de familia contable (AC/ANC -> Activos/Contra-activos, PC/PNC -> Pasivos, PAT -> Patrimonio, ER -> Resultados).
    4. Compatibilidad con el origen contable y tratamiento de contra-cuentas:
       - Depreciación Acumulada -> ANC.01.01 (contra-activo con naturaleza acreedora y signo -1).
       - Amortización Acumulada Intangibles -> ANC.03 (intangibles, NO ANC.02 propiedades de inversión).
       - Pérdidas Acumuladas -> PAT.03 (resultados acumulados, compatible con patrimonio aún si viene en columna activo con signo -).
       - Activos por impuestos diferidos -> ANC.09.
       - Pasivos por impuestos diferidos -> PNC.06.
    5. Coherencia semántica: rechazo estricto de cruces espurios (ej. resultado como activo, o pasivo como activo corriente).
    """
    eval_casos = casos if casos is not None else CASOS_BENCHMARK

    for c in eval_casos:
        esp_val = c.get("esperado")
        esp = str(esp_val) if esp_val is not None else None
        nombre = str(c.get("nombre") or "")
        tipo = str(c.get("tipo") or "DESCONOCIDO").upper()

        if esp is None:
            continue

        # 1. Existencia en catálogo
        if esp not in catalogo:
            raise ValueError(f"Código esperado '{esp}' para '{nombre}' no existe en catalogo_maestro.json")

        item = catalogo[esp]

        # 2. Estado clasificable
        if not item.get("clasificable", True):
            raise ValueError(f"Código esperado '{esp}' para '{nombre}' está marcado como NO clasificable en catalogo_maestro.json")

        cat = str(item.get("categoria") or "")
        nat = str(item.get("naturaleza") or "")
        sig = int(item.get("signo_normal", 1))

        # 3. Alineamiento de Familia / Prefijo
        if esp.startswith("AC."):
            if cat != "activo_corriente":
                raise ValueError(f"Código {esp} tiene prefijo AC pero categoría '{cat}' incompatible")
        elif esp.startswith("ANC."):
            if cat != "activo_no_corriente":
                raise ValueError(f"Código {esp} tiene prefijo ANC pero categoría '{cat}' incompatible")
        elif esp.startswith("PC."):
            if cat != "pasivo_corriente":
                raise ValueError(f"Código {esp} tiene prefijo PC pero categoría '{cat}' incompatible")
        elif esp.startswith("PNC."):
            if cat != "pasivo_no_corriente":
                raise ValueError(f"Código {esp} tiene prefijo PNC pero categoría '{cat}' incompatible")
        elif esp.startswith("PAT."):
            if cat != "patrimonio":
                raise ValueError(f"Código {esp} tiene prefijo PAT pero categoría '{cat}' incompatible")
        elif esp.startswith("ER."):
            if cat not in ("ingresos_operacionales", "costos_operacionales", "gastos_administracion_ventas", "otros_ingresos_gastos", "impuestos"):
                raise ValueError(f"Código {esp} tiene prefijo ER pero categoría '{cat}' no es de resultado")

        # 4. Validaciones contables específicas de casos obligatorios
        nombre_lower = nombre.lower()

        # Depreciación acumulada -> debe ser contra-activo (ANC.01.01, naturaleza acreedora, signo -1)
        if "depreciacion acumulada" in nombre_lower or "depreciación acumulada" in nombre_lower:
            if esp != "ANC.01.01":
                raise ValueError(f"Cuenta de depreciación acumulada '{nombre}' debe mapear a ANC.01.01, recibido '{esp}'")
            if nat != "acreedora" or sig != -1:
                raise ValueError(f"Contra-activo ANC.01.01 debe tener naturaleza acreedora y signo -1 (nat={nat}, sig={sig})")

        # Amortización acumulada intangibles -> debe ser ANC.03 (Intangibles), NO ANC.02 (Propiedades de inversión)
        if "amortizacion acumulada intangibles" in nombre_lower or "amortización acumulada intangibles" in nombre_lower:
            if esp != "ANC.03":
                raise ValueError(f"Amortización acumulada intangibles debe ser ANC.03, recibido '{esp}'")
            if esp == "ANC.02":
                raise ValueError("Error contable: ANC.02 (Propiedades de Inversión) no corresponde a intangibles")

        # Pérdidas acumuladas -> debe ser PAT.03 (Resultados Acumulados)
        if "perdidas acumuladas" in nombre_lower or "pérdidas acumuladas" in nombre_lower:
            if esp != "PAT.03":
                raise ValueError(f"Pérdidas acumuladas debe mapear a PAT.03 (patrimonio), recibido '{esp}'")
            if cat != "patrimonio":
                raise ValueError(f"Pérdidas acumuladas debe ser categoría patrimonio, recibido '{cat}'")

        # Activos por impuestos diferidos -> ANC.09
        if "activos por impuestos diferidos" in nombre_lower:
            if esp != "ANC.09":
                raise ValueError(f"Activos por impuestos diferidos debe ser ANC.09, recibido '{esp}'")

        # Pasivos por impuestos diferidos -> PNC.06
        if "pasivos por impuestos diferidos" in nombre_lower:
            if esp != "PNC.06":
                raise ValueError(f"Pasivos por impuestos diferidos debe ser PNC.06, recibido '{esp}'")

        # 5. Compatibilidad de tipo/origen
        if tipo == "RESULTADOS" and not esp.startswith("ER."):
            raise ValueError(f"Cuenta de resultados '{nombre}' asignada erróneamente a código de balance '{esp}'")
        if tipo == "ACTIVO" and (esp.startswith("PC.") or esp.startswith("PNC.")):
            raise ValueError(f"Cuenta de activo '{nombre}' asignada erróneamente a pasivo '{esp}'")
        if tipo == "PASIVO" and esp.startswith("AC."):
            raise ValueError(f"Cuenta de pasivo '{nombre}' asignada erróneamente a activo corriente '{esp}'")


def ejecutar_benchmark_clasificador_aislado() -> Dict[str, Any]:
    """
    Ejecuta el benchmark determinista en un entorno totalmente aislado.
    Garantiza que no queden rastros en base de datos ni contaminación de sockets.
    """
    with isolated_benchmark_environment():
        from pipeline.homologation_pipeline import HomologationPipeline
        from app_validacion import MotorHibridoLocal, _alternativas_revision

        catalogo = json.loads((PROJECT_ROOT / "catalogo_maestro.json").read_text())
        diccionario = json.loads((PROJECT_ROOT / "diccionario.json").read_text())
        validar_taxonomia_catalogo(catalogo)

        with tempfile.TemporaryDirectory(prefix="isolated_bench_") as tmp_dir:
            tmp_db = pathlib.Path(tmp_dir) / "isolated_bench.db"
            pipeline = HomologationPipeline(db_path=tmp_db)
            motor_ui = MotorHibridoLocal(diccionario)

            total_muestra = len(CASOS_BENCHMARK)
            total_inequivocos = sum(1 for c in CASOS_BENCHMARK if c["categoria"] == "inequivoco")
            total_abstencion = sum(1 for c in CASOS_BENCHMARK if c["categoria"] != "inequivoco")

            auto_correctas = 0
            auto_incorrectas = 0
            auto_indebidas_abstencion = 0
            revisiones_justificadas = 0
            revisiones_evitables = 0

            top1_hits = 0
            top3_hits = 0
            detalle_sugerencias = []
            casos_con_esperado = [c for c in CASOS_BENCHMARK if c["esperado"] is not None]

            for c in CASOS_BENCHMARK:
                c_nombre = str(c.get("nombre") or "")
                c_tipo_raw = c.get("tipo")
                c_tipo = str(c_tipo_raw) if c_tipo_raw is not None else None
                c_monto_raw = c.get("monto")
                c_monto = float(c_monto_raw) if isinstance(c_monto_raw, (int, float, str)) else 0.0
                c_origen_col = (c_tipo or "desconocido").lower()
                c_esperado = str(c["esperado"]) if c.get("esperado") is not None else None

                # 1. Inferencia con el pipeline
                res = pipeline._classify_account(
                    account_code="",
                    account_name=c_nombre,
                    account_tipo=c_tipo,
                    store_cmcc_shadow=False,
                )
                std_code = res.get("standard_code")
                conf = float(res.get("confidence") or 0.0)
                es_auto = (std_code is not None and conf >= 0.85)

                if c["categoria"] == "inequivoco":
                    if es_auto:
                        if std_code == c_esperado:
                            auto_correctas += 1
                        else:
                            auto_incorrectas += 1
                    else:
                        revisiones_evitables += 1
                else:
                    if es_auto:
                        auto_indebidas_abstencion += 1
                    else:
                        revisiones_justificadas += 1

                # 2. Evaluación de alternativas de revisión para UI
                if c_esperado is not None:
                    alts = _alternativas_revision(
                        nombre=c_nombre,
                        sugerido="",
                        confianza=0.0,
                        origen_columna=c_origen_col,
                        monto=c_monto,
                        catalogo=catalogo,
                        motor=motor_ui,
                        limite=3,
                    )
                    cods = [a["codigo"] for a in alts]
                    detalle_sugerencias.append({
                        "id": c["id"],
                        "codigo_esperado": c_esperado,
                        "codigos_sugeridos": cods,
                    })
                    if cods:
                        if cods[0] == c_esperado:
                            top1_hits += 1
                        if c_esperado in cods:
                            top3_hits += 1

            total_decisiones_auto = auto_correctas + auto_incorrectas + auto_indebidas_abstencion
            precision_auto = (auto_correctas / total_decisiones_auto) if total_decisiones_auto > 0 else 1.0

            metrics = {
                "total_muestra": total_muestra,
                "total_inequivocos": total_inequivocos,
                "total_abstencion": total_abstencion,
                "auto_correctas": auto_correctas,
                "auto_incorrectas": auto_incorrectas,
                "auto_indebidas_abstencion": auto_indebidas_abstencion,
                "revisiones_justificadas": revisiones_justificadas,
                "revisiones_evitables": revisiones_evitables,
                "precision_automatica": precision_auto,
                "cobertura_automatica_inequivocos": auto_correctas / total_inequivocos,
                "cobertura_muestra_completa": auto_correctas / total_muestra,
                "denominador_alternativas_catalogo": len(casos_con_esperado),
                "top1_hits": top1_hits,
                "top3_hits": top3_hits,
                "tasa_top1": top1_hits / len(casos_con_esperado),
                "tasa_top3": top3_hits / len(casos_con_esperado),
                "detalle_sugerencias": detalle_sugerencias,
            }
            return metrics


if __name__ == "__main__":
    m = ejecutar_benchmark_clasificador_aislado()
    print("Métricas del Clasificador Aislado (Encargo A5):")
    for k, v in m.items():
        print(f"  {k}: {v}")
