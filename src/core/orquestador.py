from decimal import Decimal
from pathlib import Path

from ..db_repository import RepositorioDiccionario
from extractor_metadata import PDFExtractor
from app_validacion import TaxFolder

UMBRAL_DESVIACION_VENTAS = Decimal("2.0")
RIESGO_GIRO_MAP: dict[str, list[str]] = {
    "inmobiliaria": [
        "Participación significativa en una sola obra",
        "Alta rotación de propiedades sin plusvalía real",
# Force cache bust
