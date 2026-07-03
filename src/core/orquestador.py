from decimal import Decimal
from pathlib import Path

from src.db_repository import RepositorioDiccionario
from app_validacion import TaxFolder

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

class PipelineOrquestador:
    def __init__(self):
        pass

    def procesar(self, ruta_pdf: str):
        print(f"Procesando: {ruta_pdf}")
        return {"status": "ok"}
