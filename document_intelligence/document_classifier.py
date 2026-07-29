from __future__ import annotations

import re
from .models import DocumentType, DocumentClassification


HEADER_PATTERNS: list[tuple[re.Pattern, DocumentType, str]] = [
    (re.compile(r"balance\s+tributario", re.IGNORECASE), DocumentType.BALANCE_TRIBUTARIO, "header:balance_tributario"),
    (re.compile(r"balance\s+general", re.IGNORECASE), DocumentType.BALANCE_GENERAL, "header:balance_general"),
    (re.compile(r"balance\s+clasificado", re.IGNORECASE), DocumentType.BALANCE_GENERAL, "header:balance_clasificado"),
    (re.compile(r"estado\s+de\s+resultado", re.IGNORECASE), DocumentType.ESTADO_RESULTADOS, "header:estado_resultados"),
    (re.compile(r"estado\s+de\s+patrimonio", re.IGNORECASE), DocumentType.ESTADO_PATRIMONIO, "header:estado_patrimonio"),
    (re.compile(r"estado\s+de\s+flujo", re.IGNORECASE), DocumentType.ESTADO_FLUJO, "header:estado_flujo"),
    (re.compile(r"patrimonio\s+neto", re.IGNORECASE), DocumentType.ESTADO_PATRIMONIO, "section:patrimonio_neto"),
    (re.compile(r"resultado\s+del\s+ejercicio", re.IGNORECASE), DocumentType.ESTADO_RESULTADOS, "section:resultado"),
]

SECTION_HEURISTICS: dict[DocumentType, list[re.Pattern]] = {
    DocumentType.BALANCE_TRIBUTARIO: [
        re.compile(r"^(activo|pasivo|patrimonio)", re.IGNORECASE),
    ],
    DocumentType.BALANCE_GENERAL: [
        re.compile(r"^(activo|pasivo|patrimonio)", re.IGNORECASE),
    ],
    DocumentType.ESTADO_RESULTADOS: [
        re.compile(r"^(ingreso|venta|costo|gasto)", re.IGNORECASE),
    ],
    DocumentType.ESTADO_PATRIMONIO: [
        re.compile(r"^(capital|reserva|resultado|patrimonio)", re.IGNORECASE),
    ],
    DocumentType.ESTADO_FLUJO: [
        re.compile(r"^(flujo|operacion|inversion|financiamiento)", re.IGNORECASE),
    ],
}

DOCUMENT_KEYWORDS: dict[DocumentType, list[str]] = {
    DocumentType.BALANCE_TRIBUTARIO: ["balance", "tributario", "activo", "pasivo"],
    DocumentType.BALANCE_GENERAL: ["balance", "general", "activo", "pasivo"],
    DocumentType.ESTADO_RESULTADOS: ["resultado", "ganancia", "perdida", "ingreso", "gasto"],
    DocumentType.ESTADO_PATRIMONIO: ["patrimonio", "capital", "reserva"],
    DocumentType.ESTADO_FLUJO: ["flujo", "efectivo", "cash flow"],
}


class DocumentClassifier:

    def classify(self, raw_lines: list[str]) -> DocumentClassification:
        if not raw_lines:
            return DocumentClassification(
                document_type=DocumentType.OTRO,
                confidence=0.0,
                signals=["no_lines"],
            )

        text = "\n".join(raw_lines[:60])
        lower_text = text.lower()

        header_hits: dict[DocumentType, list[str]] = {}
        for pattern, dtype, signal in HEADER_PATTERNS:
            if pattern.search(text) or pattern.search(lower_text):
                header_hits.setdefault(dtype, []).append(signal)

        keyword_scores: dict[DocumentType, float] = {}
        for dtype, keywords in DOCUMENT_KEYWORDS.items():
            score = 0.0
            for kw in keywords:
                count = lower_text.count(kw)
                if count > 0:
                    score += min(count / 3.0, 2.0)
            if score > 0:
                keyword_scores[dtype] = score

        section_checks: dict[DocumentType, int] = {}
        for dtype, patterns in SECTION_HEURISTICS.items():
            for pattern in patterns:
                matches = pattern.findall(lower_text)
                section_checks[dtype] = section_checks.get(dtype, 0) + len(matches)

        doc_votes: dict[DocumentType, float] = {}
        for dtype in DocumentType:
            if dtype == DocumentType.OTRO:
                continue
            score = 0.0
            signals_list: list[str] = []
            hs = header_hits.get(dtype, [])
            score += len(hs) * 3.0
            signals_list.extend(hs)
            ks = keyword_scores.get(dtype, 0.0)
            score += ks
            if ks > 0:
                signals_list.append(f"keywords:score={ks:.1f}")
            sc = section_checks.get(dtype, 0)
            score += sc * 1.0
            if sc > 0:
                signals_list.append(f"sections:count={sc}")
            if score > 0:
                doc_votes[dtype] = score

        if not doc_votes:
            return DocumentClassification(
                document_type=DocumentType.OTRO,
                confidence=0.2,
                signals=["no_headers_detected"],
            )

        winner = max(doc_votes, key=doc_votes.get)
        winner_score = doc_votes[winner]
        total_score = sum(doc_votes.values())
        second_score = sorted(doc_votes.values())[-2] if len(doc_votes) > 1 else 0

        if winner_score == 0:
            return DocumentClassification(
                document_type=DocumentType.OTRO,
                confidence=0.0,
                signals=["no_match"],
            )

        margin = (winner_score - second_score) / max(winner_score, 1)
        confidence = min(0.5 + (winner_score / max(total_score, 1)) * 0.3 + margin * 0.2, 1.0)

        all_signals = header_hits.get(winner, [])
        if winner in keyword_scores:
            all_signals.append(f"keyword_score={keyword_scores[winner]:.1f}")

        raw_headers = list(dict.fromkeys(
            line.strip() for line in raw_lines[:40]
            if any(kw in line.lower() for kw in DOCUMENT_KEYWORDS.get(winner, []))
        ))

        return DocumentClassification(
            document_type=winner,
            confidence=round(confidence, 4),
            signals=all_signals,
            raw_detected_headers=raw_headers[:10],
        )
