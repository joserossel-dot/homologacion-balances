"""Tests de la Document Knowledge Base (Sprint 32).

Cubre: Fingerprint, Matcher, Ranking, Repository, Clustering,
Catalog Builder, Report, UI y Backward compatibility.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from document_intelligence.knowledge import (
    DocumentFingerprint,
    DocumentKnowledgeBase,
    DocumentProfile,
    MatchResult,
    Matcher,
    cluster_fingerprints,
    compute_similarity,
    compute_statistics,
)
from document_intelligence.signature import (
    CodePattern,
    DocumentType,
    Family,
    FormatSignature,
    LayoutType,
    NumericPattern,
)

BASE_DIR = Path(__file__).resolve().parent.parent
BALANCE_2016 = BASE_DIR / "datasets" / "validacion" / "BALANCE 2016.pdf"


def _pdf_path() -> Path:
    if not BALANCE_2016.exists():
        pytest.skip(f"PDF no encontrado: {BALANCE_2016}")
    return BALANCE_2016


def _sig_estandar(conf=0.9):
    return FormatSignature(
        document_type=DocumentType.BALANCE,
        family=Family.PDF_ESTANDAR,
        layout=LayoutType.VERTICAL,
        orientation="portrait",
        code_pattern=CodePattern.GUION,
        numeric_pattern=NumericPattern.CHILENO,
        confidence=conf,
    )


def _fp_estandar(company_token="", conf=0.9):
    sig = _sig_estandar(conf)
    lines = f"""Código Cuenta Monto
1-01-01 Caja 1.500.000
1-01-02 Bancos 5.200.000
Total Activo 6.700.000""".split("\n")
    return DocumentFingerprint.build(sig, lines)


def _fp_libre():
    sig = FormatSignature(
        document_type=DocumentType.BALANCE,
        family=Family.BALANCE_SIMPLE,
        layout=LayoutType.LIBRE,
        code_pattern=CodePattern.SIN_CODIGO,
        numeric_pattern=NumericPattern.ENTERO,
        confidence=0.6,
    )
    lines = """Reporte
Caja 1500000
Bancos 5200000""".split("\n")
    return DocumentFingerprint.build(sig, lines)


# ═══════════════════════════════════════════════════════════════════
# Fingerprint
# ═══════════════════════════════════════════════════════════════════

class TestDocumentFingerprint:
    def test_build(self):
        fp = _fp_estandar()
        assert fp.layout == "VERTICAL"
        assert fp.code_pattern == "GUION"
        assert fp.document_type == "BALANCE"
        assert fp.signature_hash
        assert fp.total_patterns >= 2
        assert fp.summary_position == "BOTTOM"

    def test_determinismo(self):
        a = _fp_estandar()
        b = _fp_estandar()
        assert a.signature_hash == b.signature_hash
        assert a.canonical_string() == b.canonical_string()

    def test_serializacion_round_trip(self):
        fp = _fp_estandar()
        restored = DocumentFingerprint.from_dict(fp.to_dict())
        assert restored.to_dict() == fp.to_dict()

    def test_densidades(self):
        fp = _fp_estandar()
        assert 0.0 <= fp.text_density <= 1.0
        assert 0.0 <= fp.numeric_density <= 1.0
        assert 0.0 <= fp.table_density <= 1.0

    def test_fingerprint_from_file(self):
        from document_intelligence.knowledge.fingerprint import fingerprint_from_file
        fp = fingerprint_from_file(_pdf_path())
        assert isinstance(fp, DocumentFingerprint)
        assert fp.document_type in ("BALANCE", "OTRO")
        assert fp.page_count >= 1


# ═══════════════════════════════════════════════════════════════════
# Matcher
# ═══════════════════════════════════════════════════════════════════

class TestMatcher:
    def _profiles(self):
        p1 = DocumentProfile.new(
            name="Bal A", company="Empresa A", family="PDF_ESTANDAR",
            fingerprint=_fp_estandar(),
        )
        p2 = DocumentProfile.new(
            name="Bal B", company="Empresa B", family="PDF_ESTANDAR",
            fingerprint=_fp_estandar(),
        )
        p3 = DocumentProfile.new(
            name="ER Libre", company="Empresa C", family="BALANCE_SIMPLE",
            fingerprint=_fp_libre(),
        )
        return [p1, p2, p3]

    def test_similarity_identico(self):
        fp = _fp_estandar()
        p = DocumentProfile.new(name="X", company="", family="PDF_ESTANDAR", fingerprint=fp)
        info = compute_similarity(fp, p)
        assert info["similarity"] == 100.0
        assert "partial_hash" in info["matched_fields"]

    def test_similarity_diferente(self):
        info = compute_similarity(_fp_estandar(), DocumentProfile.new(
            name="Y", company="", family="BALANCE_SIMPLE", fingerprint=_fp_libre(),
        ))
        assert info["similarity"] < 60.0
        assert len(info["differences"]) > 0

    def test_match_mejor_perfil(self):
        result = Matcher().match(_fp_estandar(), self._profiles(), company="Empresa A")
        assert isinstance(result, MatchResult)
        assert result.matched_profile is not None
        assert result.matched_profile.name in ("Bal A", "Bal B")
        assert result.similarity >= 90.0

    def test_ranking_top5(self):
        profiles = self._profiles() * 3
        result = Matcher().match(_fp_estandar(), profiles, company="Empresa A")
        assert len(result.ranking) == 5
        scores = [s for _, s in result.ranking]
        assert scores == sorted(scores, reverse=True)

    def test_sin_coincidencias(self):
        profiles = [DocumentProfile.new(
            name="Z", company="", family="DESCONOCIDO", fingerprint=_fp_libre(),
        )]
        result = Matcher().match(_fp_libre(), profiles)
        assert result.matched_profile is not None or result.similarity > 0

    def test_missing_fields(self):
        sig = FormatSignature()
        fp = DocumentFingerprint.build(sig, [])
        p = DocumentProfile.new(name="X", company="", family="PDF_ESTANDAR",
                                fingerprint=_fp_estandar())
        info = compute_similarity(fp, p)
        assert "layout" in info["missing_fields"] or "code" in info["missing_fields"]


# ═══════════════════════════════════════════════════════════════════
# Clustering
# ═══════════════════════════════════════════════════════════════════

class TestClustering:
    def test_identicos_un_solo_cluster(self):
        clusters = cluster_fingerprints([_fp_estandar(), _fp_estandar()], threshold=70)
        assert len(clusters) == 1
        assert len(clusters[0].members) == 2
        assert clusters[0].confidence >= 90.0

    def test_distintos_varios_clusters(self):
        clusters = cluster_fingerprints(
            [_fp_estandar(), _fp_libre(), _fp_estandar()], threshold=70
        )
        assert len(clusters) == 2

    def test_centroid_y_common_features(self):
        clusters = cluster_fingerprints([_fp_estandar(), _fp_estandar()], threshold=70)
        c = clusters[0]
        assert c.centroid.code_pattern == "GUION"
        assert c.centroid.layout == "VERTICAL"
        assert c.common_features["layout"] == "VERTICAL"
        assert c.common_features["code_pattern"] == "GUION"

    def test_serializacion_cluster(self):
        clusters = cluster_fingerprints([_fp_estandar()], threshold=70)
        data = clusters[0].to_dict()
        from document_intelligence.knowledge import Cluster
        restored = Cluster.from_dict(data)
        assert restored.id == clusters[0].id
        assert len(restored.members) == 1


# ═══════════════════════════════════════════════════════════════════
# Repository
# ═══════════════════════════════════════════════════════════════════

class TestRepository:
    def _kb(self):
        kb = DocumentKnowledgeBase()
        kb.add(DocumentProfile.new(
            name="Bal A", company="Empresa A", family="PDF_ESTANDAR",
            fingerprint=_fp_estandar(), recommended_extractor="STANDARD_PARSER",
        ))
        kb.add(DocumentProfile.new(
            name="ER Libre", company="Empresa B", family="BALANCE_SIMPLE",
            fingerprint=_fp_libre(), recommended_extractor="UNKNOWN",
        ))
        return kb

    def test_save_load_round_trip(self, tmp_path):
        path = tmp_path / "kb.json"
        self._kb().save(path)
        loaded = DocumentKnowledgeBase().load(path)
        assert len(loaded.profiles) == 2
        assert loaded.get(loaded.profiles[0].id) is not None
        assert loaded.statistics()["total_profiles"] == 2

    def test_update(self):
        kb = self._kb()
        p = kb.profiles[0]
        p.times_seen = 99
        assert kb.update(p) is True
        assert kb.get(p.id).times_seen == 99
        assert kb.update(DocumentProfile.new(name="N", company="", family="", fingerprint=_fp_libre())) is False

    def test_merge(self):
        # Mismos perfiles (mismos ids) → merge actualiza, no duplica.
        p1 = DocumentProfile.new(
            name="Bal A", company="Empresa A", family="PDF_ESTANDAR",
            fingerprint=_fp_estandar(),
        )
        p2 = DocumentProfile.new(
            name="ER Libre", company="Empresa B", family="BALANCE_SIMPLE",
            fingerprint=_fp_libre(),
        )
        a = DocumentKnowledgeBase()
        b = DocumentKnowledgeBase()
        a.add(p1)
        a.add(p2)
        b.add(p1)  # mismo objeto/id
        b.add(p2)
        b.profiles[0].times_seen = 5
        n = a.merge(b)
        assert n == 0  # ambos ya existían → solo actualiza
        assert a.get(p1.id).times_seen == 5

    def test_merge_con_nuevos(self):
        kb = self._kb()
        nuevo = DocumentProfile.new(
            name="Nuevo", company="X", family="DESCONOCIDO", fingerprint=_fp_libre(),
        )
        other = DocumentKnowledgeBase()
        other.add(nuevo)
        assert kb.merge(other) == 1
        assert kb.get(nuevo.id) is not None

    def test_find_by_company(self):
        kb = self._kb()
        assert len(kb.find_by_company("Empresa A")) == 1
        assert kb.find_by_company("") == []

    def test_find_by_family(self):
        kb = self._kb()
        assert len(kb.find_by_family("PDF_ESTANDAR")) == 1
        assert len(kb.find_by_family("DESCONOCIDO")) == 0

    def test_find_similar(self):
        kb = self._kb()
        ranking = kb.find_similar(_fp_estandar(), company="Empresa A", top_n=5)
        assert len(ranking) <= 5
        assert ranking[0][0].name == "Bal A"
        assert ranking[0][1] >= 90.0

    def test_statistics(self):
        stats = self._kb().statistics()
        assert stats["total_profiles"] == 2
        assert stats["unique_formats"] == 2
        assert stats["total_variants"] >= 0
        assert "top_families" in stats


# ═══════════════════════════════════════════════════════════════════
# Catalog Builder + Report
# ═══════════════════════════════════════════════════════════════════

class TestCatalogBuilder:
    def _make_xlsx(self, path: Path, rows: list[list]):
        df = pd.DataFrame(rows)
        df.to_excel(path, index=False, header=False)

    def _setup_dataset(self, tmp_path: Path) -> Path:
        ds = tmp_path / "datasets"
        (ds / "a").mkdir(parents=True)
        self._make_xlsx(ds / "a" / "balance1.xlsx", [
            ["Código", "Cuenta", "Monto"],
            ["1-01-01", "Caja", 1500000],
            ["1-01-02", "Bancos", 5200000],
            ["Total Activo", "", 6700000],
        ])
        self._make_xlsx(ds / "a" / "balance2.xlsx", [
            ["Código", "Cuenta", "Monto"],
            ["1-01-01", "Caja", 999999],
            ["Total Activo", "", 999999],
        ])
        self._make_xlsx(ds / "a" / "libre1.xlsx", [
            ["Caja", 1500000],
            ["Bancos", 5200000],
        ])
        self._make_xlsx(ds / "a" / "er1.xlsx", [
            ["Ingresos", 50000000],
            ["Costo", -30000000],
        ])
        return ds

    def test_build_kb(self, tmp_path):
        ds = self._setup_dataset(tmp_path)
        out = tmp_path / "kb.json"
        report = tmp_path / "report.md"

        from tools.build_document_kb import build_kb
        kb, rep = build_kb(
            datasets_dir=ds, out_path=out, report_path=report, quiet=True,
        )
        assert out.exists()
        assert report.exists()
        assert rep["clusters"] >= 2
        assert rep["files_processed"] == 4
        assert rep["errors"] == 0
        assert len(kb.profiles) == rep["clusters"]

    def test_report_contenido(self, tmp_path):
        ds = self._setup_dataset(tmp_path)
        report = tmp_path / "report.md"
        from tools.build_document_kb import build_kb
        build_kb(datasets_dir=ds, out_path=tmp_path / "kb.json",
                 report_path=report, quiet=True)
        texto = report.read_text()
        assert "# Document Knowledge Base" in texto
        assert "## Resumen" in texto
        assert "## Top Empresas" in texto
        assert "## Top Familias" in texto
        assert "## Distribución de Layouts" in texto
        assert "## Distribución de Patrones" in texto
        assert "## Top Fingerprints Repetidos" in texto
        assert "## Formatos Desconocidos" in texto
        assert "## Catálogo de Perfiles" in texto

    def test_guess_company(self):
        from tools.build_document_kb import guess_company
        assert guess_company("BALANCE 2016 EMPRESA EJEMPLO.pdf") == "EMPRESA EJEMPLO"
        assert guess_company("BALANCE CLASIFICADO.pdf") == "DESCONOCIDO"
        assert guess_company("Balance 2017 - Naviera Orca.pdf") == "Naviera Orca"


# ═══════════════════════════════════════════════════════════════════
# UI
# ═══════════════════════════════════════════════════════════════════

class TestUiConocimiento:
    def test_tab_conocimiento_sin_dkb(self, monkeypatch):
        import app_validacion

        monkeypatch.setattr(app_validacion, "_cargar_document_kb", lambda: None)
        rendered = []
        monkeypatch.setattr(app_validacion.st, "info", lambda m: rendered.append(m))
        monkeypatch.setattr(app_validacion.st, "warning", lambda m: rendered.append(m))
        monkeypatch.setattr(app_validacion.st, "markdown", lambda m: rendered.append(m))

        class FakeArchivo:
            name = "x.pdf"

        app_validacion._tab_conocimiento(FakeArchivo(), object(), None)
        assert any("Document Knowledge Base" in r for r in rendered)

    def test_tab_conocimiento_sin_archivo(self, monkeypatch):
        import app_validacion
        rendered = []
        monkeypatch.setattr(app_validacion.st, "info", lambda m: rendered.append(m))
        app_validacion._tab_conocimiento(None, None, None)
        assert any("no está disponible" in r for r in rendered)

    def test_tab_conocimiento_muestra_perfil(self, monkeypatch):
        import app_validacion

        fp = _fp_estandar()
        profile = DocumentProfile.new(
            name="Bal A", company="Empresa A", family="PDF_ESTANDAR",
            fingerprint=fp, recommended_extractor="STANDARD_PARSER",
        )
        kb = DocumentKnowledgeBase()
        kb.add(profile)
        monkeypatch.setattr(app_validacion, "_cargar_document_kb", lambda: kb)
        monkeypatch.setattr(app_validacion, "_build_fingerprint_archivo", lambda a, c: fp)

        metrics = []
        rendered = []
        monkeypatch.setattr(app_validacion.st, "markdown", lambda m: rendered.append(m))
        monkeypatch.setattr(app_validacion.st, "dataframe", lambda *a, **k: None)
        monkeypatch.setattr(app_validacion.st, "write", lambda m: None)
        monkeypatch.setattr(app_validacion.st, "caption", lambda m: None)

        class _FakeCol:
            def metric(self, *a, **k):
                metrics.append(a)

        class _FakeCols(list):
            def __init__(self, *args, **kwargs):
                super().__init__()

        def fake_columns(n):
            return [_FakeCol() for _ in range(n)]

        monkeypatch.setattr(app_validacion.st, "columns", fake_columns)

        class FakeArchivo:
            name = "x.pdf"

        app_validacion._tab_conocimiento(FakeArchivo(), object(), None)
        assert any("Conocimiento Documental" in r for r in rendered)
        labels = [m[0] for m in metrics]
        assert "Perfil detectado" in labels
        assert "Empresa" in labels
        assert "Familia" in labels
        assert "Extractor recomendado" in labels
        assert "Similitud" in labels
        assert "Frecuencia (documentos)" in labels

    def test_tab_conocimiento_matcher_falla(self, monkeypatch):
        import app_validacion

        kb = DocumentKnowledgeBase()
        kb.add(DocumentProfile.new(name="X", company="", family="PDF_ESTANDAR",
                                   fingerprint=_fp_estandar()))
        monkeypatch.setattr(app_validacion, "_cargar_document_kb", lambda: kb)
        monkeypatch.setattr(app_validacion, "_build_fingerprint_archivo", lambda a, c: _fp_estandar())

        import document_intelligence.knowledge.matcher as matcher_mod

        def boom(self, *a, **k):
            raise RuntimeError("matcher caído")

        monkeypatch.setattr(matcher_mod.Matcher, "match", boom)

        warnings = []
        monkeypatch.setattr(app_validacion.st, "warning", lambda m: warnings.append(m))

        class FakeArchivo:
            name = "x.pdf"

        app_validacion._tab_conocimiento(FakeArchivo(), object(), None)
        assert any("matcher" in w for w in warnings)


# ═══════════════════════════════════════════════════════════════════
# Backward compatibility
# ═══════════════════════════════════════════════════════════════════

class TestBackwardCompat:
    def test_parser_idem_sin_coincidencias_dkb(self):
        """Cuando la DKB no encuentra coincidencias, el parser no cambia."""
        from parser_universal import ParserPDF

        path = _pdf_path()
        base = ParserPDF().parsear(path)

        # KB cargada con un perfil totalmente distinto (no debe coincidir).
        kb = DocumentKnowledgeBase()
        kb.add(DocumentProfile.new(
            name="Libre", company="X", family="BALANCE_SIMPLE", fingerprint=_fp_libre(),
        ))
        fp = DocumentFingerprint.build(base.document_context.signature, [])
        result = Matcher().match(fp, kb.profiles)
        assert result.similarity < 60.0

        # El parser produce exactamente el mismo resultado.
        again = ParserPDF().parsear(path)
        assert len(again.cuentas) == len(base.cuentas)
        for c1, c2 in zip(base.cuentas, again.cuentas):
            assert c1.nombre == c2.nombre
            assert c1.monto == c2.monto
            assert c1.codigo == c2.codigo

    def test_parser_no_depende_del_matcher(self, monkeypatch):
        """ParserPDF no importa ni usa el Matcher (desacoplado)."""
        from parser_universal import ParserPDF
        import document_intelligence.knowledge.matcher as matcher_mod

        def boom(*a, **k):
            raise RuntimeError("boom")

        monkeypatch.setattr(matcher_mod.Matcher, "match", boom)
        monkeypatch.setattr(matcher_mod, "compute_similarity", boom)

        resultado = ParserPDF().parsear(_pdf_path())
        assert len(resultado.cuentas) > 0
