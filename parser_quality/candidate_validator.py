import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

from parser_quality.rejection_reasons import RejectionReason


# ─────────────────────────────────────────────────────────────────────────────
# PATRONES DE DETECCIÓN
# ─────────────────────────────────────────────────────────────────────────────

PAT_PAGE = re.compile(
    r'\b(p[áa]gina|hoja\s*n[°]?|folio|page)\s*\d*\b', re.IGNORECASE)
PAT_RUT = re.compile(r'\b\d{1,2}\.\d{3}\.\d{3}[-][\dkK]\b')
PAT_DATE = re.compile(
    r'\b(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}[-/]\d{2}[-/]\d{2})\b')
PAT_FECHA_TEXTO = re.compile(
    r'\b(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|'
    r'octubre|noviembre|diciembre|'
    r'ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)\s+\d{2,4}\b',
    re.IGNORECASE)
PAT_ADDRESS = re.compile(
    r'\b(calle|av\.?|avenida|pasaje|km\s?\d+|n[°]\s?\d+|'
    r's/n|comuna|ciudad|provincia|regi[óo]n|piso|depto|oficina)\b',
    re.IGNORECASE)
PAT_PHONE = re.compile(
    r'(?:\+56\s*9\s*\d{4}\s*\d{4}|'
    r'\+\d{1,3}\s*\d{2,4}\s*\d{4}\s*\d{4}|'
    r'\b9\s*\d{4}\s*\d{4}\b|'
    r'\b2\s*\d{4}\s*\d{4}\b)'
)
PAT_EMAIL = re.compile(
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')
PAT_WEB = re.compile(
    r'\b(www\.|https?://)[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')
PAT_COMUNA = re.compile(r'\b(comuna|comunas)\b', re.IGNORECASE)
PAT_CIUDAD = re.compile(
    r'\b(ciudad|santiago|valpara[íi]so|concepci[óo]n|vi[ñn]a|'
    r'providencia|las condes|vitacura)\b', re.IGNORECASE)
PAT_REGION = re.compile(
    r'\b(regi[óo]n|rm|metropolitana|v\s*regi[óo]n)\b', re.IGNORECASE)
PAT_MONEDA = re.compile(
    r'\b(moneda|d[oó]lar|d[oó]lares|uf|utm|euro|peso|usd|clp)\b',
    re.IGNORECASE)
PAT_FIRMA = re.compile(
    r'\b(firma|firmado|firmante|representante|suscribe|'
    r'certifico|declaro|autorizo)\b', re.IGNORECASE)
PAT_NOTAS = re.compile(
    r'\b(notas?\s*(a\s*los)?\s*e\.?f\.?|anexo|anexos|'
    r'[íi]ndice|contenido|glosario)\b', re.IGNORECASE)
PAT_BALANCE_GENERAL = re.compile(
    r'\b(balance\s*general|estado\s*(de\s*)?(situaci[óo]n|resultados?|'
    r'financiero)|ee\.?ff\.?)\b', re.IGNORECASE)
PAT_PERIODO = re.compile(
    r'\b(desde\s+\w|al\s+\d+\s+de|ejercicio\s+\d{4}|'
    r'a[ñn]o\s+\d{4}|per[ií]odo\s+\d{4})\b', re.IGNORECASE)
PAT_HEADER_FOOTER = re.compile(
    r'^(pre[-\s]?balance|balance\s+(tributario|general|clasificado)|'
    r'compan[ií]a|sociedad|r\.?u\.?t\.?|pre[-\s]?balance\s+)',
    re.IGNORECASE)
PAT_HTML = re.compile(r'(&[a-z]+;|<[^>]+>|&#\d+;)')
PAT_NOISE_LINE = re.compile(r'^[\d\s\-_.,;:/()|\[\]{}]+$')
PAT_ONLY_SYMBOLS = re.compile(r'^[^a-zA-ZáéíóúñüÁÉÍÓÚÑÜ\s]{2,}$')

# Palabras clave de cuentas contables
ACCOUNT_KEYWOR = {
    "caja", "banco", "cuenta", "corriente", "cliente", "deudor",
    "acreedor", "proveedor", "inventario", "existencia", "mercaderia",
    "capital", "reserva", "utilidad", "perdida", "ganancia",
    "ingreso", "gasto", "costo", "venta", "remuneracion", "sueldo",
    "honorario", "impuesto", "iva", "credito", "prestamo",
    "obligacion", "depreciacion", "amortizacion", "provision",
    "activo", "pasivo", "patrimonio", "resultado",
    "inversion", "accion", "participacion",
    "documento", "por cobrar", "por pagar",
    "leasing", "arriendo", "seguro",
    "electricidad", "agua", "telefono", "comunicacion",
    "mantencion", "reparacion", "asesoria",
    "interes", "comision", "multa",
    "donacion", "patente", "contribucion",
    "diferencia de cambio", "correccion monetaria",
}

ACCOUNT_KEYWOR_COMPILED = re.compile(
    r'\b(' + '|'.join(re.escape(kw) for kw in sorted(
        ACCOUNT_KEYWOR, key=len, reverse=True
    )) + r')\b', re.IGNORECASE)

STANDARD_CODES = re.compile(
    r'\b(AC\.\d{2}|PC\.\d{2}|PAT\.\d{2}|ER\.\d{2}|'
    r'ANC\.\d{2}|PNC\.\d{2}|PAS\.\d{2})\b')


# ─────────────────────────────────────────────────────────────────────────────
# UTILIDADES
# ─────────────────────────────────────────────────────────────────────────────

def strip_accents(s: str) -> str:
    nfkd = unicodedata.normalize('NFKD', s)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


def name_has_account_keywords(name: str) -> bool:
    return bool(ACCOUNT_KEYWOR_COMPILED.search(strip_accents(name)))


def count_symbols(s: str) -> float:
    if not s:
        return 0.0
    symbols = sum(1 for c in s if not c.isalnum() and not c.isspace())
    return symbols / len(s)


def count_digits(s: str) -> float:
    if not s:
        return 0.0
    digits = sum(1 for c in s if c.isdigit())
    return digits / len(s)


# ─────────────────────────────────────────────────────────────────────────────
# SEÑALES POSITIVAS
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_positive_signals(
    name: str,
    code: Optional[str],
    monto: Optional[float],
    is_total: bool,
) -> dict[RejectionReason, float]:
    signals: dict[RejectionReason, float] = {}

    if monto is not None:
        signals[RejectionReason.HAS_MONTO] = 0.15
    if code is not None and len(code) >= 3:
        signals[RejectionReason.HAS_CODE] = 0.10
    if name and 5 <= len(name) <= 80:
        signals[RejectionReason.REASONABLE_LENGTH] = 0.05
    if name and name_has_account_keywords(name):
        signals[RejectionReason.ACCOUNT_PATTERN] = 0.10
    if STANDARD_CODES.search(name or ""):
        signals[RejectionReason.ACCOUNT_PATTERN] = 0.10
    if is_total:
        signals[RejectionReason.ACCOUNT_PATTERN] = 0.05

    n_tokens = len(name.split()) if name else 0
    if 2 <= n_tokens <= 15:
        signals[RejectionReason.KNOWN_ACCOUNT] = 0.05

    return signals


# ─────────────────────────────────────────────────────────────────────────────
# SEÑALES NEGATIVAS
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_negative_signals(
    line: str,
    name: str,
    requirio_ocr: bool,
) -> dict[RejectionReason, float]:
    signals: dict[RejectionReason, float] = {}

    if not line and not name:
        return signals

    name_lower = name.lower().strip() if name else ""
    line_lower = line.lower()

    # --- Escanear el NOMBRE (no la línea completa que incluye montos) ---
    if name_lower:
        if PAT_PAGE.search(name_lower):
            signals[RejectionReason.CONTAINS_PAGE] = -0.25
        if PAT_RUT.search(name):
            signals[RejectionReason.CONTAINS_RUT] = -0.30
        if PAT_DATE.search(name) or PAT_FECHA_TEXTO.search(name):
            signals[RejectionReason.CONTAINS_DATE] = -0.20
        if PAT_ADDRESS.search(name_lower):
            signals[RejectionReason.CONTAINS_ADDRESS] = -0.30
        if PAT_PHONE.search(name):
            signals[RejectionReason.CONTAINS_PHONE] = -0.30
        if PAT_EMAIL.search(name):
            signals[RejectionReason.CONTAINS_EMAIL] = -0.30
        if PAT_WEB.search(name):
            signals[RejectionReason.CONTAINS_WEB] = -0.30
        if PAT_COMUNA.search(name_lower):
            signals[RejectionReason.CONTAINS_COMUNA] = -0.25
        if PAT_CIUDAD.search(name_lower):
            signals[RejectionReason.CONTAINS_CIUDAD] = -0.20
        if PAT_REGION.search(name_lower):
            signals[RejectionReason.CONTAINS_REGION] = -0.20
        if PAT_MONEDA.search(name_lower):
            signals[RejectionReason.CONTAINS_MONEDA] = -0.15
        if PAT_FIRMA.search(name_lower):
            signals[RejectionReason.CONTAINS_FIRMA] = -0.25
        if PAT_NOTAS.search(name_lower):
            signals[RejectionReason.CONTAINS_NOTAS] = -0.25
        if PAT_BALANCE_GENERAL.search(name_lower):
            signals[RejectionReason.CONTAINS_BALANCE_GENERAL] = -0.20
        if PAT_PERIODO.search(name_lower):
            signals[RejectionReason.CONTAINS_PERIODO] = -0.15
        if PAT_HEADER_FOOTER.match(name_lower):
            signals[RejectionReason.CONTAINS_HEADER] = -0.20
        if PAT_ONLY_SYMBOLS.fullmatch(name.strip()):
            signals[RejectionReason.NAME_ONLY_SYMBOLS] = -0.25

        # Nombre: métricas de calidad
        nm_len = len(name.strip())
        if nm_len < 4:
            signals[RejectionReason.NAME_TOO_SHORT] = -0.20
        elif nm_len > 120:
            signals[RejectionReason.NAME_TOO_LONG] = -0.15

        sym_pct = count_symbols(name)
        if sym_pct > 0.30:
            signals[RejectionReason.NAME_TOO_MANY_SYMBOLS] = -0.20

        dig_pct = count_digits(name)
        if dig_pct > 0.40:
            signals[RejectionReason.NAME_TOO_MANY_DIGITS] = -0.20

    # --- Escanear la LÍNEA COMPLETA (para patrones estructurales) ---
    if PAT_HTML.search(line):
        signals[RejectionReason.HTML_ARTIFACT] = -0.30
    if PAT_NOISE_LINE.fullmatch(line.strip()):
        signals[RejectionReason.NAME_ONLY_SYMBOLS] = -0.30

    if requirio_ocr:
        signals[RejectionReason.OCR_LOW_CONFIDENCE] = -0.10

    return signals


# ─────────────────────────────────────────────────────────────────────────────
# EVIDENCE RESULT
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class EvidenceResult:
    confidence: float
    reasons: list[RejectionReason]
    positive_signals: dict[RejectionReason, float] = field(default_factory=dict)
    negative_signals: dict[RejectionReason, float] = field(default_factory=dict)

    def top_reasons(self, n: int = 5) -> list[RejectionReason]:
        combined = dict(self.positive_signals)
        combined.update(self.negative_signals)
        sorted_by_impact = sorted(
            combined,
            key=lambda r: abs(combined[r]),
            reverse=True,
        )
        return [r for r in sorted_by_impact if r in self.reasons][:n]


# ─────────────────────────────────────────────────────────────────────────────
# VALIDATOR
# ─────────────────────────────────────────────────────────────────────────────

class CandidateValidator:
    """Evalúa cada línea candidata usando evidencia determinística."""

    BASE_CONFIDENCE = 0.50

    def evaluate(
        self,
        line: str,
        name: str,
        code: Optional[str] = None,
        monto: Optional[float] = None,
        is_total: bool = False,
        requirio_ocr: bool = False,
    ) -> EvidenceResult:
        pos_signals = evaluate_positive_signals(name, code, monto, is_total)
        neg_signals = evaluate_negative_signals(line, name, requirio_ocr)

        all_signals = dict(pos_signals)
        all_signals.update(neg_signals)

        confidence = self.BASE_CONFIDENCE
        for delta in all_signals.values():
            confidence += delta
        confidence = max(0.0, min(1.0, confidence))

        reasons: list[RejectionReason] = []
        for reason, delta in all_signals.items():
            if delta > 0:
                continue
            reasons.append(reason)

        if not reasons and confidence < 0.85:
            if not code and monto is None:
                reasons.append(RejectionReason.OUTSIDE_TABLE)
            elif monto is None:
                reasons.append(RejectionReason.NO_MONTO)

        return EvidenceResult(
            confidence=round(confidence, 4),
            reasons=reasons,
            positive_signals=pos_signals,
            negative_signals=neg_signals,
        )
