"""Document Intelligence Engine (DIE).

Módulo de inteligencia documental que analiza un PDF/Excel ANTES de ejecutar
el parser y produce recomendaciones sobre cómo procesarlo.

Uso básico:

    from document_intelligence import DocumentIntelligence

    engine = DocumentIntelligence()
    report = engine.analyze("ruta/al/documento.pdf")
    print(report.summary())

Sprint 30 — Nueva capa de detección de formato:

    from document_intelligence import FormatAnalyzer

    analyzer = FormatAnalyzer()
    sig = analyzer.analyze_text(text)
    print(sig.summary())
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .analyzer import FormatAnalyzer
from .context import DocumentProcessingContext, analyze_document_preview
from .detector import (
    BaseDetector,
    CodePatternDetector,
    ColumnDetector,
    DocumentTypeDetector,
    HeaderDetector,
    LayoutDetector,
    NumericPatternDetector,
)
from .factory import ExtractorFactory, ExtractorType
from .metrics import DetectionMetrics, MetricsCollector
from .knowledge import (
    Cluster,
    DocumentFingerprint,
    DocumentKnowledgeBase,
    MatchResult,
    Matcher,
    build_centroid,
    cluster_fingerprints,
    compute_similarity,
    compute_statistics,
)
from .mining import (
    DocumentFamily,
    DocumentRecord,
    Representative,
    SimilarityMatrix,
    build_similarity_matrix,
    coverage_by_top_families,
    detect_families,
    detect_quality_issues,
    fingerprint_similarity,
    recommend_extractors,
    run_mining_analysis,
    select_representatives,
    write_csvs,
    write_dashboard_report,
)
from .extractors import (
    ExtractorResult,
    SpecializedExtractor,
    SpecializedExtractorFactory,
    UniversalExtractor,
    get_extractor,
    get_extractor_for_family,
    instantiate,
    list_extractors,
    register_extractor,
    register_extractor_class,
)
from .models import (
    DocumentType,
    Family,
    Complexity,
    Recommendation,
    ParserName,
    DocumentProfile,
    DocumentClassification,
    FamilyClassification,
    TemplatePrediction,
    ParserRecommendation,
    ValidationRecommendation,
    ConfidencePrediction,
    CoveragePrediction,
    ProcessingRecommendation,
    IntelligenceReport,
)
from .document_classifier import DocumentClassifier
from .family_classifier import FamilyClassifier
from .template_classifier import TemplateClassifier
from .parser_selector import ParserSelector
from .validation_selector import ValidationSelector
from .confidence_predictor import ConfidencePredictor
from .recommendation_engine import RecommendationEngine
from .repository import FormatRepository
from .signature import (
    CodePattern,
    ColumnType,
    FormatSignature,
    LayoutType,
    NumericPattern,
)
from .statistics import DocumentIntelligenceStats

__all__ = [
    "DocumentIntelligence",
    "DocumentIntelligenceStats",
    # Sprint 30
    "FormatAnalyzer",
    "FormatSignature",
    "FormatRepository",
    "ExtractorFactory",
    "ExtractorType",
    "DetectionMetrics",
    "MetricsCollector",
    # Sprint 31
    "DocumentProcessingContext",
    "analyze_document_preview",
    # Sprint 32 — Document Knowledge Base
    "DocumentFingerprint",
    "Matcher",
    "MatchResult",
    "compute_similarity",
    "Cluster",
    "build_centroid",
    "cluster_fingerprints",
    "DocumentKnowledgeBase",
    "compute_statistics",
    # Sprint 33 — Data Mining del DKB
    "DocumentRecord",
    "DocumentFamily",
    "Representative",
    "SimilarityMatrix",
    "fingerprint_similarity",
    "build_similarity_matrix",
    "detect_families",
    "select_representatives",
    "coverage_by_top_families",
    "detect_quality_issues",
    "recommend_extractors",
    "run_mining_analysis",
    "write_csvs",
    "write_dashboard_report",
    # Sprint 34 — Extractores especializados (arquitectura)
    "ExtractorResult",
    "SpecializedExtractor",
    "SpecializedExtractorFactory",
    "UniversalExtractor",
    "register_extractor",
    "register_extractor_class",
    "get_extractor",
    "get_extractor_for_family",
    "list_extractors",
    "instantiate",
    "BaseDetector",
    "HeaderDetector",
    "LayoutDetector",
    "ColumnDetector",
    "CodePatternDetector",
    "NumericPatternDetector",
    "DocumentTypeDetector",
    "CodePattern",
    "ColumnType",
    "LayoutType",
    "NumericPattern",
    # Legacy models
    "DocumentType",
    "Family",
    "Complexity",
    "Recommendation",
    "ParserName",
    "DocumentProfile",
    "DocumentClassification",
    "FamilyClassification",
    "TemplatePrediction",
    "ParserRecommendation",
    "ValidationRecommendation",
    "ConfidencePrediction",
    "CoveragePrediction",
    "ProcessingRecommendation",
    "IntelligenceReport",
]


class DocumentIntelligence:
    """Motor central de inteligencia documental.

    Analiza archivos antes de parsearlos y produce un IntelligenceReport
    con predicciones sobre tipo, familia, template, parser, validaciones,
    confianza, cobertura y recomendación de procesamiento.
    """

    def __init__(
        self,
        template_repo_path: str = "structure_repository.json",
        kb_path: str = "knowledge_base/cmcc_knowledge.json",
    ):
        self.classifier = DocumentClassifier()
        self.family_classifier = FamilyClassifier()
        self.template_classifier = TemplateClassifier(repo_path=template_repo_path)
        self.parser_selector = ParserSelector()
        self.validation_selector = ValidationSelector()
        self.confidence_predictor = ConfidencePredictor()
        self.recommendation_engine = RecommendationEngine()
        self.kb_path = kb_path

    def analyze(self, file_path: str | Path) -> IntelligenceReport:
        path = Path(file_path)

        raw_lines = self._extract_preview(path)
        file_ext = path.suffix.lower()

        pages = self._estimate_pages(raw_lines=raw_lines)
        ocr_prob = self._estimate_ocr_probability(raw_lines, pages)
        is_pdf_text = ocr_prob < 0.5

        classification = self.classifier.classify(raw_lines)

        account_lines = self._build_quick_accounts(raw_lines)
        code_format = self._detect_code_format(account_lines)
        column_layout = self._detect_column_layout(account_lines)
        layout = column_layout

        total_accounts = len(account_lines)
        total_sections = self._estimate_sections(raw_lines)
        total_subtotals = self._estimate_subtotals(raw_lines)

        family = self.family_classifier.classify(
            raw_lines=raw_lines,
            section_count=total_sections,
            subtotal_count=total_subtotals,
            total_lines=len(raw_lines),
            code_format=code_format,
        )

        template = self.template_classifier.predict(
            code_format=code_format,
            column_layout=layout,
            total_lines=len(raw_lines),
            account_lines=account_lines,
        )

        parser = self.parser_selector.recommend(
            file_path=str(path),
            ocr_probability=ocr_prob,
            pages=max(pages, 1),
            is_pdf_text=is_pdf_text,
            document_type=classification.document_type.value if classification.document_type else None,
        )

        validation = self.validation_selector.recommend(
            document_type=classification.document_type,
            family=family.family,
            estimated_accounts=total_accounts,
            estimated_sections=total_sections,
        )

        kb_coverage = self._estimate_kb_coverage(code_format, total_accounts)

        confidence = self.confidence_predictor.predict(
            document_type=classification.document_type,
            family=family.family,
            template_id=template.template_id if template else "",
            ocr_probability=ocr_prob,
            parser_name=parser.parser_name.value,
            kb_coverage_pct=kb_coverage,
            estimated_accounts=total_accounts,
            estimated_sections=total_sections,
            has_signature=template is not None,
        )

        coverage = CoveragePrediction(
            global_pct=kb_coverage,
            estimated_covered=int(total_accounts * kb_coverage) if total_accounts else 0,
            estimated_total=total_accounts,
            kb_size=self._get_kb_size(),
            signals=[f"kb_coverage:{kb_coverage:.2f}"],
        )

        profile = DocumentProfile(
            document_type=classification.document_type,
            family=family.family,
            template=template.template_name if template else None,
            template_id=template.template_id if template else "",
            pages=pages,
            layout=layout,
            ocr_probability=ocr_prob,
            estimated_accounts=total_accounts,
            estimated_sections=total_sections,
            estimated_subtotals=total_subtotals,
            estimated_complexity=self._estimate_profile_complexity(
                pages, total_accounts, ocr_prob,
            ),
            column_count=self._estimate_column_count(column_layout),
        )

        recommendation = self.recommendation_engine.evaluate(
            profile=profile,
            classification=classification,
            family=family,
            template=template,
            parser_rec=parser,
            validation=validation,
            confidence=confidence,
            coverage=coverage,
        )

        return IntelligenceReport(
            profile=profile,
            classification=classification,
            family=family,
            template=template,
            parser=parser,
            validation=validation,
            confidence=confidence,
            coverage=coverage,
            recommendation=recommendation,
        )

    def analyze_batch(self, file_paths: list[str | Path]) -> list[IntelligenceReport]:
        return [self.analyze(fp) for fp in file_paths]

    def _extract_preview(self, path: Path) -> list[str]:
        if not path.exists():
            return []

        ext = path.suffix.lower()
        raw_text = ""

        try:
            if ext == ".pdf":
                raw_text = self._extract_pdf_text(path)
            elif ext in (".xls", ".xlsx", ".xlsm"):
                raw_text = self._extract_excel_text(path)
            elif ext in (".txt", ".csv"):
                raw_text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            raw_text = ""

        if not raw_text:
            raw_text = path.read_text(encoding="utf-8", errors="replace")

        lines = raw_text.split("\n")
        return [l for l in lines if l.strip()][:200]

    def _extract_pdf_text(self, path: Path) -> str:
        try:
            import fitz
            doc = fitz.open(str(path))
            text = "\n".join(page.get_text() for page in doc)
            doc.close()
            return text
        except ImportError:
            pass
        try:
            import pdfplumber
            with pdfplumber.open(str(path)) as pdf:
                return "\n".join(page.extract_text() or "" for page in pdf.pages)
        except ImportError:
            pass
        try:
            import PyPDF2
            reader = PyPDF2.PdfReader(str(path))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except ImportError:
            pass
        return ""

    def _extract_excel_text(self, path: Path) -> str:
        try:
            import openpyxl
            wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
            lines = []
            for sheet in wb.worksheets:
                for row in sheet.iter_rows(values_only=True):
                    cells = [str(c) for c in row if c is not None]
                    if cells:
                        lines.append(" ".join(cells))
            wb.close()
            return "\n".join(lines)
        except ImportError:
            pass
        try:
            import pandas as pd
            dfs = pd.read_excel(str(path), sheet_name=None)
            lines = []
            for df in dfs.values():
                for _, row in df.iterrows():
                    cells = [str(v) for v in row if pd.notna(v)]
                    if cells:
                        lines.append(" ".join(cells))
            return "\n".join(lines)
        except ImportError:
            pass
        return ""

    def _estimate_pages(
        self,
        path: Path | None = None,
        raw_lines: list[str] | None = None,
    ) -> int:
        if path and path.suffix.lower() == ".pdf":
            try:
                import fitz
                doc = fitz.open(str(path))
                pages = doc.page_count
                doc.close()
                return pages
            except ImportError:
                pass
            try:
                import PyPDF2
                reader = PyPDF2.PdfReader(str(path))
                return len(reader.pages)
            except ImportError:
                pass
        lines = raw_lines or []
        if not lines:
            return 1
        return max(1, len(lines) // 30 + 1)

    def _estimate_ocr_probability(
        self,
        raw_lines: list[str],
        pages: int,
    ) -> float:
        if not raw_lines or pages == 0:
            return 0.5
        total_chars = sum(len(l) for l in raw_lines)
        chars_per_page = total_chars / max(pages, 1)
        if chars_per_page < 20:
            return 0.95
        elif chars_per_page < 100:
            return 0.7
        elif chars_per_page < 500:
            return 0.3
        return 0.05

    def _estimate_sections(self, raw_lines: list[str]) -> int:
        section_keywords = [
            "activo", "pasivo", "patrimonio", "resultado",
            "ingreso", "costo", "gasto", "capital",
        ]
        count = 0
        text_lower = "\n".join(raw_lines[:80]).lower()
        for kw in section_keywords:
            if kw in text_lower:
                count += 1
        return max(1, count)

    def _estimate_subtotals(self, raw_lines: list[str]) -> int:
        import re
        pattern = re.compile(r"^(total|subtotal|suma)", re.IGNORECASE)
        count = 0
        for line in raw_lines[:200]:
            if pattern.match(line.strip()):
                count += 1
        return count

    def _build_quick_accounts(self, raw_lines: list[str]) -> list[dict]:
        accounts = []
        for i, line in enumerate(raw_lines):
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            code = ""
            name = line
            if parts and (parts[0].isdigit() or "." in parts[0] or "-" in parts[0]):
                code = parts[0]
                name = " ".join(parts[1:]) if len(parts) > 1 else ""
            accounts.append({
                "nombre": name,
                "monto": 0,
                "codigo": code,
                "origen_columna": "",
                "es_total": False,
                "linea": i,
            })
        return accounts

    def _detect_code_format(self, accounts: list[dict]) -> str:
        from structure_engine.structure_detector import StructureDetector
        return StructureDetector.detect_code_format(accounts)

    def _detect_column_layout(self, accounts: list[dict]) -> str:
        from structure_engine.structure_detector import StructureDetector
        return StructureDetector.detect_column_layout(accounts)

    def _estimate_column_count(self, layout: str) -> int:
        mapping = {
            "SINGLE_COLUMN": 1,
            "DOUBLE_COLUMN": 2,
            "MULTI_COLUMN": 3,
            "INCOME_COLUMNS": 2,
            "DEBIT_CREDIT": 2,
        }
        return mapping.get(layout, 1)

    def _estimate_kb_coverage(self, code_format: str, total_accounts: int) -> float:
        kb_size = self._get_kb_size()
        if kb_size == 0:
            return 0.1
        if code_format == "PUNTO":
            return min(0.95, 0.5 + kb_size / 2000)
        elif code_format == "COMPACTO":
            return min(0.85, 0.4 + kb_size / 3000)
        elif code_format == "GUION":
            return min(0.80, 0.3 + kb_size / 4000)
        else:
            return 0.3

    def _get_kb_size(self) -> int:
        try:
            import json
            path = Path(self.kb_path)
            if path.exists():
                data = json.loads(path.read_text())
                codes = data.get("codes", {}) if isinstance(data, dict) else {}
                return len(codes) if isinstance(codes, dict) else 0
        except Exception:
            pass
        return 0

    def _estimate_profile_complexity(
        self,
        pages: int,
        accounts: int,
        ocr_prob: float,
    ) -> Complexity:
        if ocr_prob > 0.7:
            return Complexity.ALTA
        if pages > 15 or accounts > 100:
            return Complexity.ALTA
        if pages > 8 or accounts > 50:
            return Complexity.MEDIA
        return Complexity.BAJA
