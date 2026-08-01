from __future__ import annotations

import re
from abc import ABC, abstractmethod

from .signature import (
    CodePattern,
    ColumnType,
    DocumentType,
    LayoutType,
    NumericPattern,
)


class BaseDetector(ABC):
    @abstractmethod
    def detect(self, lines: list[str]) -> dict:
        ...


class HeaderDetector(BaseDetector):
    RUT_PATTERN = re.compile(
        r'\b(\d{1,2}\.\d{3}\.\d{3}[-][\dkK]|\d{7,9}[-][\dkK])\b'
    )
    PERIOD_PATTERN = re.compile(
        r'\b(31/12|01/01|31\-12|01\-01|per[ií]odo|ejercicio|a[ñn]o)\b',
        re.IGNORECASE,
    )
    COMPANY_INDICATORS = [
        'raz.n social', 'razon social', 'r.u.t', 'rut',
        'empresa', 'sociedad', 'compa.ía', 'compaña',
        'giro', 'direcci.n', 'domicilio',
    ]

    def detect(self, lines: list[str]) -> dict:
        result = {
            'has_headers': False,
            'company_name': '',
            'confidence': 0.0,
        }
        if not lines:
            return result

        header_zone = lines[:min(20, len(lines))]
        text_block = ' '.join(header_zone).lower()

        rut_match = self.RUT_PATTERN.search(text_block)
        period_match = self.PERIOD_PATTERN.search(text_block)
        company_indicators_found = sum(
            1 for ind in self.COMPANY_INDICATORS if ind in text_block
        )

        result['has_headers'] = (
            bool(rut_match) or bool(period_match) or company_indicators_found >= 2
        )

        if company_indicators_found >= 1:
            for line in header_zone:
                for ind in self.COMPANY_INDICATORS:
                    if ind in line.lower():
                        result['company_name'] = line.strip()
                        break
                if result['company_name']:
                    break

        if result['has_headers'] and company_indicators_found >= 2 and bool(rut_match):
            result['confidence'] = 0.95
        elif result['has_headers']:
            result['confidence'] = 0.70
        elif company_indicators_found >= 1:
            result['confidence'] = 0.30

        return result


class LayoutDetector(BaseDetector):
    HORIZONTAL_KEYWORDS = ['activo', 'pasivo', 'patrimonio']
    SEPARATOR_PATTERN = re.compile(r'\t|\s{3,}')

    def detect(self, lines: list[str]) -> dict:
        result = {
            'layout': LayoutType.DESCONOCIDO,
            'orientation': 'portrait',
            'confidence': 0.0,
        }
        if not lines:
            return result

        data_lines = [
            l.strip() for l in lines
            if l.strip() and not self._is_header_line(l)
        ]

        if not data_lines:
            return result

        double_column_candidates = 0
        for line in data_lines[:50]:
            parts = self.SEPARATOR_PATTERN.split(line)
            numeric_parts = sum(1 for p in parts if self._looks_like_number(p))
            if len(parts) >= 3 and numeric_parts >= 2:
                double_column_candidates += 1

        tabular_keywords = sum(
            1 for l in data_lines[:30]
            if any(kw in l.lower() for kw in self.HORIZONTAL_KEYWORDS)
        )

        text_block = ' '.join(data_lines[:30]).lower()
        has_active_section = 'activo' in text_block
        has_passive_section = 'pasivo' in text_block
        has_income_section = 'ganancia' in text_block or 'ingreso' in text_block
        has_loss_section = 'perdida' in text_block or 'p.rdida' in text_block or 'gasto' in text_block

        tabular_ratio = double_column_candidates / max(len(data_lines[:50]), 1)
        has_vertical_markers = tabular_keywords >= 3

        if has_active_section and has_passive_section:
            if tabular_ratio >= 0.15:
                result['layout'] = LayoutType.HORIZONTAL
                result['orientation'] = 'landscape'
                result['confidence'] = 0.85
            else:
                result['layout'] = LayoutType.VERTICAL
                result['orientation'] = 'portrait'
                result['confidence'] = 0.80
        elif has_active_section or has_passive_section:
            if tabular_ratio >= 0.20:
                result['layout'] = LayoutType.TABULAR
                result['orientation'] = 'landscape'
                result['confidence'] = 0.75
            else:
                result['layout'] = LayoutType.VERTICAL
                result['confidence'] = 0.65
        elif has_income_section or has_loss_section:
            result['layout'] = LayoutType.VERTICAL
            result['confidence'] = 0.60
        elif tabular_ratio >= 0.30:
            result['layout'] = LayoutType.TABULAR
            result['orientation'] = 'landscape'
            result['confidence'] = 0.70
        else:
            result['layout'] = LayoutType.LIBRE
            result['confidence'] = 0.40

        return result

    def _looks_like_number(self, s: str) -> bool:
        s = s.strip()
        if not s:
            return False
        s_clean = s.replace('.', '').replace(',', '').replace('-', '').replace('(', '').replace(')', '')
        return s_clean.isdigit() and len(s_clean) >= 2

    def _is_header_line(self, line: str) -> bool:
        header_kw = ['rut', 'p.gina', 'hoja', 'fecha', 'folio', 'página']
        return any(kw in line.lower() for kw in header_kw)


class ColumnDetector(BaseDetector):
    CODE_MARKERS = re.compile(
        r'^(c.digo|c.d|c.digo|cod|cod\.?|cta\.?|nro\.?|n°|número)',
        re.IGNORECASE,
    )
    NAME_MARKERS = re.compile(
        r'^(nombre|cuenta|detalle|descripci.n|concepto|glosa|rubro)',
        re.IGNORECASE,
    )
    AMOUNT_MARKERS = re.compile(
        r'^(monto|importe|saldo|valor|total|debe|haber|activo|pasivo)',
        re.IGNORECASE,
    )

    def detect(self, lines: list[str]) -> dict:
        result = {
            'columns': [],
            'confidence': 0.0,
        }
        if not lines:
            return result

        first_data_lines = [l for l in lines[:30] if l.strip()]
        header_candidates = []
        for line in first_data_lines:
            words = [w.strip() for w in re.split(r'\t|\s{2,}', line) if w.strip()]
            if len(words) >= 2:
                header_candidates.append(words)

        detected = set()
        for words in header_candidates[:5]:
            for w in words:
                w_lower = w.lower().strip('.:;,')
                if self.CODE_MARKERS.match(w_lower):
                    detected.add(ColumnType.CODIGO)
                elif self.NAME_MARKERS.match(w_lower):
                    detected.add(ColumnType.NOMBRE)
                elif self.AMOUNT_MARKERS.match(w_lower):
                    if 'activo' in w_lower:
                        detected.add(ColumnType.ACTIVO)
                    elif 'pasivo' in w_lower:
                        detected.add(ColumnType.PASIVO)
                    elif 'debe' in w_lower:
                        detected.add(ColumnType.DEBE)
                    elif 'haber' in w_lower:
                        detected.add(ColumnType.HABER)
                    else:
                        detected.add(ColumnType.MONTO)

        if not detected:
            result['columns'] = [ColumnType.NOMBRE, ColumnType.MONTO]
            result['confidence'] = 0.40
        else:
            ordered = [ColumnType.CODIGO, ColumnType.NOMBRE, ColumnType.MONTO]
            result['columns'] = [c for c in ordered if c in detected]
            remaining = [c for c in [ColumnType.ACTIVO, ColumnType.PASIVO, ColumnType.DEBE, ColumnType.HABER] if c in detected]
            result['columns'].extend(remaining)
            result['confidence'] = min(0.95, 0.5 + 0.1 * len(result['columns']))

        return result


class CodePatternDetector(BaseDetector):
    PATTERNS: list[tuple[re.Pattern, CodePattern, float]] = [
        (re.compile(r'\b\d{1,2}\.\d{2}\.\d{2}\b'), CodePattern.PUNTO, 0.95),
        (re.compile(r'\b\d{1,2}\.\d{2}\.\d{2}\.\d{2}\b'), CodePattern.PUNTO, 0.95),
        (re.compile(r'\b\d{1,2}\-\d{2}\b'), CodePattern.GUION, 0.90),
        (re.compile(r'\b\d{1,2}\-\d{2}\-\d{2}\b'), CodePattern.GUION, 0.95),
        (re.compile(r'\b\d{1,2}\-\d{2}\-\d{2}\-\d{2}\b'), CodePattern.GUION, 0.95),
        (re.compile(r'\b\d{4,6}\b(?![.,]\d)'), CodePattern.COMPACTO, 0.70),
        (re.compile(r'\b\d{2}\.\d{2}\b'), CodePattern.PUNTO, 0.75),
    ]

    def detect(self, lines: list[str]) -> dict:
        result = {
            'code_pattern': CodePattern.DESCONOCIDO,
            'confidence': 0.0,
        }
        if not lines:
            return result

        text = ' '.join(lines[:100])
        best_match = CodePattern.DESCONOCIDO
        best_conf = 0.0

        for pattern, code_type, conf in self.PATTERNS:
            matches = pattern.findall(text)
            if matches:
                count = len(matches)
                adjusted_conf = conf * min(1.0, count / 3)
                if adjusted_conf > best_conf:
                    best_conf = adjusted_conf
                    best_match = code_type

        if best_match == CodePattern.DESCONOCIDO:
            numeric_tokens = sum(
                1 for t in text.split()
                if t.strip().replace('.', '').replace('-', '').isdigit()
            )
            total_tokens = len(text.split())
            if total_tokens > 0 and numeric_tokens / total_tokens > 0.15:
                best_match = CodePattern.NUMERICO
                best_conf = 0.40

        result['code_pattern'] = best_match
        result['confidence'] = best_conf
        return result


class NumericPatternDetector(BaseDetector):
    CHILEAN_PATTERN = re.compile(r'\b\d{1,3}(?:\.\d{3})+(?:,\d{2})?\b')
    DECIMAL_PATTERN = re.compile(r'\b\d+(?:\.\d{2})\b')
    INTEGER_PATTERN = re.compile(r'\b\d{3,}\b')
    PARENTHESIS_PATTERN = re.compile(r'\(\s*\d[\d.,]*\s*\)')
    SIGN_PATTERN = re.compile(r'[+-]\s*\d{3,}[\d.,]*')

    def detect(self, lines: list[str]) -> dict:
        result = {
            'numeric_pattern': NumericPattern.DESCONOCIDO,
            'confidence': 0.0,
        }
        if not lines:
            return result

        text = ' '.join(lines[:100])

        chilean = len(self.CHILEAN_PATTERN.findall(text))
        decimal = len(self.DECIMAL_PATTERN.findall(text))
        integer = len(self.INTEGER_PATTERN.findall(text))
        paren = len(self.PARENTHESIS_PATTERN.findall(text))
        signed = len(self.SIGN_PATTERN.findall(text))
        total = chilean + decimal + integer + paren + signed

        if total == 0:
            return result

        chilean_ratio = chilean / total
        paren_ratio = paren / total
        signed_ratio = signed / total

        if chilean_ratio >= 0.3:
            result['numeric_pattern'] = NumericPattern.CHILENO
            result['confidence'] = 0.90
        elif paren_ratio >= 0.2:
            result['numeric_pattern'] = NumericPattern.PARENTESIS
            result['confidence'] = 0.85
        elif signed_ratio >= 0.2:
            result['numeric_pattern'] = NumericPattern.SIGNO
            result['confidence'] = 0.80
        elif decimal / max(total, 1) >= 0.3:
            result['numeric_pattern'] = NumericPattern.DECIMAL
            result['confidence'] = 0.75
        elif integer / max(total, 1) >= 0.5:
            result['numeric_pattern'] = NumericPattern.ENTERO
            result['confidence'] = 0.70

        return result


class DocumentTypeDetector(BaseDetector):
    def detect(self, lines: list[str]) -> dict:
        result = {
            'document_type': DocumentType.OTRO,
            'confidence': 0.0,
        }
        if not lines:
            return result

        text = ' '.join(lines[:60]).lower()

        balance_weight = 0.0
        er_weight = 0.0
        patrimonio_weight = 0.0
        flujo_weight = 0.0

        balance_keywords = ['activo', 'pasivo', 'patrimonio', 'balance']
        er_keywords = ['resultado', 'ganancia', 'p.rdida', 'ingreso', 'costo', 'gasto', 'estado de resultado']
        patrimonio_keywords = ['patrimonio', 'capital', 'reserva', 'utilidad', 'resultado del ejercicio']
        flujo_keywords = ['flujo', 'efectivo', 'flujo de efectivo', 'flujo de caja']

        for kw in balance_keywords:
            if kw in text:
                balance_weight += 1
        for kw in er_keywords:
            if kw in text:
                er_weight += 1.5
        for kw in patrimonio_keywords:
            if kw in text:
                patrimonio_weight += 1
        for kw in flujo_keywords:
            if kw in text:
                flujo_weight += 2

        has_activo = 'activo' in text
        has_pasivo = 'pasivo' in text
        has_patrimonio = 'patrimonio' in text
        has_total = 'total' in text

        if balance_weight >= er_weight and balance_weight >= patrimonio_weight and balance_weight >= flujo_weight:
            threshold = 2 if has_activo and has_pasivo else 3
            if balance_weight >= threshold:
                result['document_type'] = DocumentType.BALANCE
                result['confidence'] = min(0.95, 0.5 + 0.1 * balance_weight)
        elif er_weight >= balance_weight and er_weight >= patrimonio_weight and er_weight >= flujo_weight:
            if er_weight >= 2:
                result['document_type'] = DocumentType.ESTADO_RESULTADOS
                result['confidence'] = min(0.95, 0.5 + 0.1 * er_weight)
        elif patrimonio_weight >= 2:
            result['document_type'] = DocumentType.ESTADO_PATRIMONIO
            result['confidence'] = min(0.90, 0.4 + 0.1 * patrimonio_weight)
        elif flujo_weight >= 1:
            result['document_type'] = DocumentType.ESTADO_FLUJO
            result['confidence'] = 0.70

        if result['document_type'] == DocumentType.OTRO:
            if has_activo or has_pasivo:
                result['document_type'] = DocumentType.BALANCE
                result['confidence'] = 0.40

        return result
