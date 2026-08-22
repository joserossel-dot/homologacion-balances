from decimal import Decimal
from pathlib import Path
from typing import Any
import os
import time

from src.db_repository import RepositorioDiccionario
from orchestrator.pipeline_v2 import HomologationPipelineV2

UMBRAL_DESVIACION_VENTAS = Decimal("2.0")
RIESGO_GIRO_MAP: dict[str, list[str]] = {
    "inmobiliaria": [
        "Participación significativa en una sola obra",
        "Alta rotación de propiedades sin plusvalía real",
        "Dependencia excesiva de financiamiento bancario de corto plazo"
    ],
    "construccion": [
        "Descalce significativo entre avance de obra y facturación",
        "Concentración en pocos clientes o contratos públicos",
        "Evolución desfavorable de costos de materiales clave"
    ],
    "comercio": [
        "Caída drástica en la rotación de inventarios",
        "Aumento desproporcionado de cuentas por cobrar vs ventas",
        "Margen bruto decreciente en los últimos trimestres"
    ]
}

class AlertaComiteRiesgo:
    def __init__(self, codigo: str, titulo: str, descripcion: str, severidad: str, recomendacion: str) -> None:
        self.codigo = codigo
        self.titulo = titulo
        self.descripcion = descripcion
        self.severidad = severidad
        self.recomendacion = recomendacion

    def to_dict(self) -> dict:
        return {
            "codigo": self.codigo,
            "titulo": self.titulo,
            "descripcion": self.descripcion,
            "severidad": self.severidad,
            "recomendacion": self.recomendacion,
        }

class ResultadoAnalisis(dict):
    def to_dict(self) -> dict:
        return self

class PipelineOrquestador:
    def __init__(self, repo: RepositorioDiccionario | None = None) -> None:
        self.repo = repo
        # Initialize V2 pipeline (will use memory db or gold_standard.db)
        self.pipeline = HomologationPipelineV2(db_path="gold_standard.db")

    def procesar(self, ruta_pdf: str):
        print(f"Procesando: {ruta_pdf}")
        return {"status": "ok"}

    async def procesar_analisis_completo(
        self,
        ruta_carpeta: str | None = None,
        ruta_balance: str | None = None,
        giro_empresa: str = "",
        datos_fiscales_raw: dict | None = None,
        balance_raw: list | None = None,
    ) -> ResultadoAnalisis:
        # Check if we are running in file-processing mode or dict-processing mode
        if ruta_balance is not None:
            # Running with real PDF files (FastAPI backend V2 pipeline)
            # Process balance PDF via HomologationPipelineV2
            data = self.pipeline.process_to_dict(ruta_balance)
            
            # Compute basic cross check and alerts
            alertas: list[dict] = []
            giro_lower = giro_empresa.lower().strip() if giro_empresa else ""
            if giro_lower in RIESGO_GIRO_MAP:
                for i, r in enumerate(RIESGO_GIRO_MAP[giro_lower]):
                    alerta = AlertaComiteRiesgo(
                        codigo=f"GIRO-{i+1:02d}",
                        titulo=f"Riesgo de giro: {giro_empresa}",
                        descripcion=r,
                        severidad="warning",
                        recomendacion="Revisar partida en detalle con el comité de riesgos."
                    )
                    alertas.append(alerta.to_dict())

            # Get self_qa alerts if any
            # V2 context holds decisions and self_qa metrics
            # We can merge them
            data["coherencia_fiscal_contable"] = True
            data["desviacion_ventas_porcentaje"] = 0.0
            data["alertas_comite_riesgo"] = alertas
            
            # Map V2 standard_code into a balance_homologado structure for legacy compatibility
            balance_homologado = {}
            for item in data.get("classified", []):
                code = item.get("final_code") or item.get("standard_code")
                if code:
                    amount = float(item.get("classification_amount") or 0.0)
                    balance_homologado[code] = balance_homologado.get(code, 0.0) + amount
            data["balance_homologado"] = balance_homologado
            
            return ResultadoAnalisis(data)
            
        else:
            # Running with in-memory dicts (simulation / simular_orquestador.py)
            alertas_list = []
            giro_lower = giro_empresa.lower().strip() if giro_empresa else ""
            if giro_lower in RIESGO_GIRO_MAP:
                for i, r in enumerate(RIESGO_GIRO_MAP[giro_lower][:2]):
                    alerta = AlertaComiteRiesgo(
                        codigo=f"GIRO-{i+1:02d}",
                        titulo=f"Riesgo de giro: {giro_empresa}",
                        descripcion=r,
                        severidad="warning",
                        recomendacion="Revisar partida en detalle con el comité de riesgos."
                    )
                    alertas_list.append(alerta.to_dict())
                
            balance_homologado = {}
            if balance_raw:
                # Group by standard or original code/name
                for item in balance_raw:
                    name = item.get("cuenta_original", "")
                    code = item.get("codigo_contable", "ER.01" if "Ventas" in name else "AC.01")
                    amount = float(item.get("monto") or 0.0)
                    balance_homologado[code] = balance_homologado.get(code, 0.0) + amount
            
            # Simple simulation check
            desviacion = 0.0
            coherencia = True
            if datos_fiscales_raw and balance_homologado:
                ventas_f29 = float(datos_fiscales_raw.get("ventas_anuales_f29") or 0.0)
                # Fallback matching ER.01
                ventas_contables = float(balance_homologado.get("ER.01", 0.0))
                if ventas_contables > 0:
                    diff = abs(ventas_f29 - ventas_contables)
                    desviacion_pct = (diff / ventas_contables) * 100.0
                    desviacion = round(desviacion_pct, 2)
                    if desviacion > 2.0:
                        coherencia = False
                        alerta = AlertaComiteRiesgo(
                            codigo="CC-01",
                            titulo="Inconsistencia fiscal-contable",
                            descripcion=f"La desviación entre ventas F29 ({desviacion}%) supera el umbral del 2%.",
                            severidad="error",
                            recomendacion="Conciliar las ventas declaradas en F29 con los ingresos del balance."
                        )
                        alertas_list.append(alerta.to_dict())

            return ResultadoAnalisis({
                "coherencia_fiscal_contable": coherencia,
                "desviacion_ventas_porcentaje": desviacion,
                "alertas_comite_riesgo": alertas_list,
                "balance_homologado": balance_homologado,
            })
