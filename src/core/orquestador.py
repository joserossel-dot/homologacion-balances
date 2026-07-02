from decimal import Decimal
from pathlib import Path

from src.core.tax_folder_engine import TaxFolderEngine
from src.db_repository import RepositorioDiccionario
from src.extractors.pdf_extractor import PDFExtractor
from src.models.tax_folder import TaxFolder

UMBRAL_DESVIACION_VENTAS = Decimal("2.0")
RIESGO_GIRO_MAP: dict[str, list[str]] = {
    "inmobiliaria": [
        "Participación significativa en una sola obra",
        "Alta rotación de propiedades sin plusvalía real",
        "Desfase entre IVA declarado e ingresos por venta",
    ],
    "tecnologia": [
        "Ingresos por licencias sin correlato en activos intangibles",
        "Gastos en I+D sin activación contable",
        "Margen bruto muy superior al promedio del rubro",
    ],
    "comercio": [
        "Inventario declarado no consistente con compras",
        "Rotación de stocks muy por debajo del promedio",
    ],
    "transporte": [
        "Activos fijos (flota) desproporcionados respecto a ventas",
        "Gastos en combustible sin registro de viajes",
    ],
}


class BalanceHomologado:
    def __init__(
        self,
        ingresos: Decimal | None = None,
        costo_ventas: Decimal | None = None,
        margen_bruto: Decimal | None = None,
        resultado_ejercicio: Decimal | None = None,
        total_activos: Decimal | None = None,
        total_pasivos: Decimal | None = None,
        patrimonio: Decimal | None = None,
    ) -> None:
        self.ingresos = ingresos
        self.costo_ventas = costo_ventas
        self.margen_bruto = margen_bruto
        self.resultado_ejercicio = resultado_ejercicio
        self.total_activos = total_activos
        self.total_pasivos = total_pasivos
        self.patrimonio = patrimonio

    def to_dict(self) -> dict:
        def _fmt(v: Decimal | None) -> float | None:
            return float(v) if v is not None else None
        return {
            "ingresos": _fmt(self.ingresos),
            "costo_ventas": _fmt(self.costo_ventas),
            "margen_bruto": _fmt(self.margen_bruto),
            "resultado_ejercicio": _fmt(self.resultado_ejercicio),
            "total_activos": _fmt(self.total_activos),
            "total_pasivos": _fmt(self.total_pasivos),
            "patrimonio": _fmt(self.patrimonio),
        }


class AlertaComiteRiesgo:
    def __init__(
        self, codigo: str, titulo: str, descripcion: str, severidad: str, recomendacion: str = ""
    ) -> None:
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


class ResultadoAnalisis:
    def __init__(self) -> None:
        self.coherencia_fiscal_contable: bool = True
        self.desviacion_ventas_porcentaje: float | None = None
        self.alertas_comite_riesgo: list[dict] = []
        self.balance_homologado: dict | None = None

    def to_dict(self) -> dict:
        return {
            "coherencia_fiscal_contable": self.coherencia_fiscal_contable,
            "desviacion_ventas_porcentaje": self.desviacion_ventas_porcentaje,
            "alertas_comite_riesgo": self.alertas_comite_riesgo,
            "balance_homologado": self.balance_homologado,
        }


class PipelineOrquestador:
    def __init__(self, repositorio: RepositorioDiccionario) -> None:
        self._repositorio = repositorio

    async def procesar_analisis_completo(
        self,
        ruta_carpeta: str,
        ruta_balance: str,
        giro_empresa: str,
    ) -> ResultadoAnalisis:
        resultado = ResultadoAnalisis()

        tax_folder = await self._fase1_carpeta_tributaria(ruta_carpeta)
        balance = self._fase2_balance(ruta_balance)
        self._fase3_cross_check(tax_folder, balance, resultado)
        await self._fase4_alertas_giro(tax_folder, balance, giro_empresa, resultado)
        resultado.balance_homologado = balance.to_dict() if balance else None

        return resultado

    async def _fase1_carpeta_tributaria(self, ruta: str) -> TaxFolder:
        engine = TaxFolderEngine(ruta)
        return engine.parse()

    def _fase2_balance(self, ruta: str) -> BalanceHomologado:
        path = Path(ruta)
        if not path.exists():
            return BalanceHomologado()

        extractor = PDFExtractor()
        extract_result = extractor.extract(ruta)
        text = "\n".join(p.text for p in extract_result.pages)

        ingresos = self._sum_balance_column(text, r"INGRESOS\s", 7)
        costo = self._sum_balance_column(text, r"COSTO\s+DE\s+VENTAS?", 6)
        resultado_ej = self._extract_decimal(
            text, r"RESULTADO\s+ACUMULADO.*?([\d.,]+)(?:\s|$)"
        )
        activos = self._extract_total_general(text, column=4)
        pasivos = self._extract_total_general(text, column=5)
        activo_total = activos
        pasivo_total = pasivos
        patrimonio = (activo_total - pasivo_total) if (activo_total and pasivo_total) else None

        margen = None
        if ingresos and costo:
            margen = ingresos - costo

        return BalanceHomologado(
            ingresos=ingresos,
            costo_ventas=costo,
            margen_bruto=margen,
            resultado_ejercicio=resultado_ej,
            total_activos=activos,
            total_pasivos=pasivos,
            patrimonio=patrimonio,
        )

    @staticmethod
    def _parse_chilean_number(raw: str) -> Decimal | None:
        raw = raw.strip()
        raw = raw.replace("$", "").replace(" ", "")
        if not raw or raw in ("0",):
            return None
        try:
            clean = raw.replace(".", "").replace(",", "")
            return Decimal(clean)
        except Exception:
            return None

    @staticmethod
    def _parse_tokens(line: str) -> list[str]:
        import re
        parts = line.strip().split()
        if not parts:
            return []
        tokens: list[str] = []
        for p in parts:
            if re.match(r"^\d+-\d+-\d+-\d+$", p):
                continue
            val = p.replace(",", "")
            if val.replace(".", "").replace("-", "").isdigit() or val == "###########":
                tokens.append(p)
        return tokens

    @staticmethod
    def _sum_balance_column(text: str, section_pattern: str, col_idx: int) -> Decimal | None:
        import re
        total = Decimal("0")
        found = False
        in_section = False
        for line in text.split("\n"):
            if re.search(section_pattern, line, re.IGNORECASE):
                in_section = True
            if re.search(r"^(?:Sub[\-\s]*Totales?|Total\s+General)", line, re.IGNORECASE):
                in_section = False
            if not in_section:
                continue
            tokens = PipelineOrquestador._parse_tokens(line)
            if len(tokens) > col_idx:
                val = PipelineOrquestador._parse_chilean_number(tokens[col_idx])
                if val is not None:
                    total += val
                    found = True
        return total if found else None

    @staticmethod
    def _extract_total_general(text: str, column: int) -> Decimal | None:
        import re
        for line in text.split("\n"):
            if re.search(r"^(?:Sub[\-\s]*Totales?|Total\s+General)", line, re.IGNORECASE):
                tokens = PipelineOrquestador._parse_tokens(line)
                if len(tokens) > column:
                    return PipelineOrquestador._parse_chilean_number(tokens[column])
        return None

    @staticmethod
    def _extract_decimal(text: str, pattern: str) -> Decimal | None:
        import re
        m = re.search(pattern, text, re.IGNORECASE)
        if not m:
            return None
        return PipelineOrquestador._parse_chilean_number(m.group(1))

    @staticmethod
    def _fase3_cross_check(
        tax_folder: TaxFolder,
        balance: BalanceHomologado,
        resultado: ResultadoAnalisis,
    ) -> None:
        ventas_f29_total = Decimal("0")
        for mt in tax_folder.monthly_taxes:
            if mt.total_ventas is not None:
                ventas_f29_total += mt.total_ventas

        ingresos_balance = balance.ingresos

        if ventas_f29_total and ingresos_balance and ingresos_balance > 0:
            diff = abs(ventas_f29_total - ingresos_balance)
            desviacion = (diff / ingresos_balance) * Decimal("100")
            resultado.desviacion_ventas_porcentaje = float(
                desviacion.quantize(Decimal("0.01"))
            )
            resultado.coherencia_fiscal_contable = (
                desviacion <= UMBRAL_DESVIACION_VENTAS
            )
        elif ventas_f29_total and not ingresos_balance:
            resultado.desviacion_ventas_porcentaje = 100.0
            resultado.coherencia_fiscal_contable = False

    async def _fase4_alertas_giro(
        self,
        tax_folder: TaxFolder,
        balance: BalanceHomologado,
        giro_empresa: str,
        resultado: ResultadoAnalisis,
    ) -> None:
        giro_lower = giro_empresa.lower().strip()
        riesgos = RIESGO_GIRO_MAP.get(giro_lower, [])

        alertas: list[AlertaComiteRiesgo] = []

        for i, riesgo in enumerate(riesgos):
            alertas.append(
                AlertaComiteRiesgo(
                    codigo=f"GIRO-{i+1:02d}",
                    titulo=f"Riesgo de giro: {giro_empresa}",
                    descripcion=riesgo,
                    severidad="warning",
                    recomendacion="Revisar partida en detalle con el comité de riesgos.",
                )
            )

        if not resultado.coherencia_fiscal_contable:
            alertas.append(
                AlertaComiteRiesgo(
                    codigo="CC-01",
                    titulo="Inconsistencia fiscal-contable",
                    descripcion=(
                        f"La desviación entre ventas F29 ({resultado.desviacion_ventas_porcentaje}%) "
                        f"supera el umbral del 2%."
                    ),
                    severidad="error",
                    recomendacion="Conciliar las ventas declaradas en F29 con los ingresos del balance.",
                )
            )

        for v in tax_folder.validation:
            alertas.append(
                AlertaComiteRiesgo(
                    codigo=f"REGLA-{v.code}",
                    titulo=v.title,
                    descripcion=v.description,
                    severidad=v.severity.value if hasattr(v.severity, "value") else v.severity,
                    recomendacion=v.recommendation,
                )
            )

        resultado.alertas_comite_riesgo = [a.to_dict() for a in alertas]
