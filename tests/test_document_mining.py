"""Tests del Data Mining del DKB (Sprint 33).

Cubre: Similarity Matrix, Family Detector, Representative Selector,
Coverage, Quality Analyzer, Reportes, CSVs, Dashboard, Tool y
Backward compatibility (el pipeline no cambia).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from document_intelligence.knowledge import DocumentFingerprint
from document_intelligence.mining import (
    CoverageResult,
    DocumentFamily,
    DocumentRecord,
    Representative,
    SimilarityMatrix,
    build_similarity_matrix,
    coverage_by_top_families,
    detect_families,
    detect_quality_issues,
    fingerprint_similarity,
    load_analysis_result,
    recommend_extractors,
    run_mining_analysis,
    save_analysis_result,
    select_representatives,
    write_csvs,
    write_dashboard_report,
)
from document_intelligence.signature import (
    CodePattern,
    ColumnType,
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


def _fp_estandar(conf=0.9):
    sig = FormatSignature(
        document_type=DocumentType.BALANCE,
        family=Family.PDF_ESTANDAR,
        layout=LayoutType.VERTICAL,
        orientation="portrait",
        code_pattern=CodePattern.GUION,
        numeric_pattern=NumericPattern.CHILENO,
        columns=[
            ColumnType.CODIGO, ColumnType.NOMBRE, ColumnType.MONTO,
        ],
        confidence=conf,
    )
    lines = """Código Cuenta Monto
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
        columns=[ColumnType.NOMBRE, ColumnType.MONTO],
        confidence=0.6,
    )
    lines = """Reporte
Caja 1500000
Bancos 5200000""".split("\n")
    return DocumentFingerprint.build(sig, lines)


def _fp_compacto():
    sig = FormatSignature(
        document_type=DocumentType.BALANCE,
        family=Family.PDF_ESTANDAR,
        layout=LayoutType.VERTICAL,
        orientation="portrait",
        code_pattern=CodePattern.COMPACTO,
        numeric_pattern=NumericPattern.ENTERO,
        columns=[ColumnType.CODIGO, ColumnType.NOMBRE, ColumnType.MONTO],
        confidence=0.8,
    )
    lines = """Cuenta Monto
101 Caja 1500000
102 Bancos 5200000
Total Activo 6700000""".split("\n")
    return DocumentFingerprint.build(sig, lines)


def _rec(id_, fp, company="", document_type="BALANCE"):
    return DocumentRecord(
        id=id_, file=id_, company=company or id_,
        family="PDF_ESTANDAR", extractor="STANDARD_PARSER",
        document_type=document_type, fingerprint=fp,
    )


def _records(n_std=3, n_libre=1, n_comp=0):
    recs = [_rec(f"std{i}.pdf", _fp_estandar(), company="ACME")
            for i in range(n_std)]
    recs += [_rec(f"libre{i}.pdf", _fp_libre(), company="OTRA")
             for i in range(n_libre)]
    recs += [_rec(f"comp{i}.pdf", _fp_compacto(), company="ZETA")
             for i in range(n_comp)]
    return recs


# ═══════════════════════════════════════════════════════════════════
# Similarity Matrix
# ═══════════════════════════════════════════════════════════════════

class TestSimilarityMatrix:
    def test_identicos_similitud_100(self):
        assert fingerprint_similarity(_fp_estandar(), _fp_estandar()) == 100.0

    def test_distintos_similitud_baja(self):
        assert fingerprint_similarity(_fp_estandar(), _fp_libre()) < 60.0

    def test_pesos_normalizados(self):
        from document_intelligence.mining.similarity_matrix import FINGERPRINT_WEIGHTS
        assert abs(sum(FINGERPRINT_WEIGHTS.values()) - 1.0) < 1e-9
        assert "company" not in FINGERPRINT_WEIGHTS

    def test_matriz_pares_y_topk(self):
        recs = _records(n_std=4, n_libre=2)
        m = build_similarity_matrix(recs, top_k=3)
        assert m.pairs_computed == 15  # 6*5/2
        assert len(m.neighbors) == 6
        for nbrs in m.neighbors.values():
            assert len(nbrs) <= 3
        # simétrico: si B está en topk de A con sim s, A está en topk de B con s
        for i, r in enumerate(recs):
            for other, s in m.neighbors[r.id]:
                back = m.pair_similarity(other, r.id)
                if back is not None:
                    assert abs(back - s) < 1e-6

    def test_media_global(self):
        m = build_similarity_matrix(_records(n_std=2, n_libre=0))
        assert m.mean_similarity == 100.0

    def test_round_trip(self):
        m = build_similarity_matrix(_records(n_std=2, n_libre=1), top_k=2)
        restored = SimilarityMatrix.from_dict(m.to_dict())
        assert restored.top_k == m.top_k
        assert restored.pairs_computed == m.pairs_computed
        assert restored.mean_similarity == m.mean_similarity
        assert set(restored.neighbors) == set(m.neighbors)

    def test_summary_rows(self):
        m = build_similarity_matrix(_records(n_std=2, n_libre=0), top_k=2)
        rows = m.to_summary_rows()
        assert len(rows) == 2
        assert rows[0]["top1_similarity"] == 100.0
        assert "doc_id" in rows[0] and "file" in rows[0]

    def test_registro_serializacion(self):
        r = _rec("a.pdf", _fp_estandar(), company="X")
        data = r.to_dict()
        restored = DocumentRecord.from_dict(data)
        assert restored.id == "a.pdf"
        assert restored.fingerprint.signature_hash == r.fingerprint.signature_hash


# ═══════════════════════════════════════════════════════════════════
# Family Detector
# ═══════════════════════════════════════════════════════════════════

class TestFamilyDetector:
    def test_no_usa_empresa_ni_nombre(self):
        """Mismo fingerprint + distintas empresas/archivos → 1 familia."""
        fp = _fp_estandar()
        recs = [
            _rec("balance de la empresa X 2016.pdf", fp, company="EMPRESA X"),
            _rec("ALGO 2020.pdf", fp, company="OTRA EMPRESA"),
            _rec("docs/varios.pdf", fp, company=""),
        ]
        familias = detect_families(recs, threshold=70)
        assert len(familias) == 1
        assert familias[0].count == 3

    def test_familias_por_fingerprint(self):
        familias = detect_families(_records(n_std=3, n_libre=1), threshold=70)
        assert len(familias) == 2
        counts = {f.count for f in familias}
        assert counts == {3, 1}

    def test_sin_duplicados_entre_familias(self):
        """Copias idénticas en distintos directorios no se cuentan 2 veces."""
        fp = _fp_estandar()
        recs = [
            _rec("ARCHIVE/Balance SA JAHUEL 2020 V3.pdf", fp, company="JAHUEL"),
            _rec("HOLDOUT/Balance SA JAHUEL 2020 V3.pdf", fp, company="JAHUEL"),
            _rec("edge_cases/Balance SA JAHUEL 2020 V3.pdf", fp, company="JAHUEL"),
        ]
        familias = detect_families(recs, threshold=70)
        todos = [d.id for f in familias for d in f.documents]
        assert len(todos) == len(set(todos)) == 3
        assert sum(f.count for f in familias) == 3
        assert familias[0].count == 3

    def test_campos_de_familia(self):
        familias = detect_families(_records(n_std=2, n_libre=1), threshold=70)
        f = max(familias, key=lambda x: x.count)
        assert f.count == 2
        assert f.avg_similarity == 100.0
        assert f.dominant_layout == "VERTICAL"
        assert f.dominant_code_pattern == "GUION"
        assert f.dominant_document_type == "BALANCE"
        assert f.centroid is not None
        assert "MONTO" in f.dominant_columns
        assert f.confidence == 1.0
        assert f.id.startswith("cluster_")

    def test_serializacion_familia(self):
        familias = detect_families(_records(n_std=2), threshold=70)
        data = familias[0].to_dict()
        restored = DocumentFamily.from_dict(data)
        assert restored.id == familias[0].id
        assert restored.count == familias[0].count
        assert restored.dominant_layout == familias[0].dominant_layout


# ═══════════════════════════════════════════════════════════════════
# Representative Selector
# ═══════════════════════════════════════════════════════════════════

class TestRepresentativeSelector:
    def test_un_representante_por_familia(self):
        familias = detect_families(_records(n_std=3, n_libre=1), threshold=70)
        reps = select_representatives(familias)
        assert len(reps) == 2
        for r in reps:
            assert isinstance(r, Representative)
            assert r.file
            assert r.n_documents > 0

    def test_representante_mayor_similitud(self):
        """El representante debe tener la mayor similitud promedio interna."""
        familias = detect_families(_records(n_std=3), threshold=70)
        f = familias[0]
        reps = select_representatives([f])
        assert reps[0].file in {d.id for d in f.documents}
        assert reps[0].avg_similarity == 100.0  # todos idénticos

    def test_familia_singleton(self):
        f = detect_families(_records(n_std=0, n_libre=1), threshold=70)[0]
        reps = select_representatives([f])
        assert len(reps) == 1
        assert reps[0].file == "libre0.pdf"
        assert reps[0].n_documents == 1

    def test_serializacion_representante(self):
        r = Representative(family_id="c1", document_id="x.pdf", file="x.pdf",
                           avg_similarity=95.0, n_documents=3, company="ACME")
        restored = Representative.from_dict(r.to_dict())
        assert restored.family_id == "c1"
        assert restored.file == "x.pdf"


# ═══════════════════════════════════════════════════════════════════
# Coverage
# ═══════════════════════════════════════════════════════════════════

class TestCoverage:
    def test_cobertura_top5(self):
        familias = [
            DocumentFamily(id=f"c{i}", documents=[_rec(f"d{j}.pdf", _fp_estandar()) for j in range(n)], count=n)
            for i, n in enumerate([50, 30, 10, 5, 3, 2])
        ]
        cov = coverage_by_top_families(familias)
        assert cov.total_documents == 100
        tiers = {t["top_n"]: t for t in cov.tiers}
        assert tiers[5]["cumulative_pct"] == 98.0   # 50+30+10+5+3
        assert tiers[10]["cumulative_pct"] == 100.0
        assert tiers[20]["cumulative_pct"] == 100.0
        assert tiers[30]["cumulative_pct"] == 100.0

    def test_coverage_ordenado(self):
        familias = [DocumentFamily(id=f"c{i}", documents=[], count=n)
                    for i, n in enumerate([3, 9, 6])]
        cov = coverage_by_top_families(familias)
        assert cov.tiers[0]["top_families"][0]["id"] == "c1"  # 9 primero

    def test_serializacion_coverage(self):
        familias = [DocumentFamily(id="c1", documents=[], count=4)]
        cov = coverage_by_top_families(familias)
        restored = CoverageResult.from_dict(cov.to_dict())
        assert restored.total_documents == 4
        assert len(restored.tiers) == 4


# ═══════════════════════════════════════════════════════════════════
# Quality Analyzer
# ═══════════════════════════════════════════════════════════════════

class TestQualityAnalyzer:
    def test_singleton_detectado(self):
        familias = detect_families(_records(n_std=3, n_libre=1), threshold=70)
        issues = detect_quality_issues(familias)
        kinds = {i["kind"] for i in issues}
        assert "singleton" in kinds

    def test_heterogeneo_detectado(self):
        """Familia con similitud interna baja → cluster heterogéneo."""
        fp_guion = _fp_estandar()
        fp_compacto = _fp_compacto()
        familia = DocumentFamily(
            id="c_hetero",
            documents=[_rec("a.pdf", fp_guion), _rec("b.pdf", fp_compacto)],
            count=2,
            avg_similarity=55.0,
            centroid=fp_guion,
            dominant_layout="VERTICAL",
        )
        issues = detect_quality_issues([familia])
        assert any(i["kind"] == "heterogeneous" for i in issues)

    def test_layout_inconsistente(self):
        familia = DocumentFamily(
            id="c_lay",
            documents=[
                _rec("a.pdf", _fp_estandar()),
                _rec("b.pdf", _fp_libre()),
            ],
            count=2,
            avg_similarity=80.0,
            centroid=_fp_estandar(),
            dominant_layout="VERTICAL",
        )
        issues = detect_quality_issues([familia])
        assert any(i["kind"] == "inconsistent_layout" for i in issues)


# ═══════════════════════════════════════════════════════════════════
# Reports / Dashboard / CSVs
# ═══════════════════════════════════════════════════════════════════

class TestReports:
    def test_run_mining_analysis_completo(self):
        res = run_mining_analysis(_records(n_std=6, n_libre=1))
        assert res["n_documents"] == 7
        assert res["n_families"] == 2
        assert res["matrix"]["pairs_computed"] == 21
        assert len(res["representatives"]) == 2
        assert len(res["coverage"]["tiers"]) == 4
        assert "quality_issues" in res
        assert "recommendations" in res
        assert "statistics" in res
        assert len(res["similarity_summary"]) == 7

    def test_recomendaciones_por_volumen(self):
        """Familia con ≥5 docs coherentes → recomendada; singleton no."""
        recs = [DocumentRecord(
            id=f"s{i}.pdf", file=f"s{i}.pdf", company="ACME",
            family="PDF_ESTANDAR", extractor="STANDARD_PARSER",
            document_type="BALANCE", fingerprint=_fp_estandar(),
        ) for i in range(6)]
        res = run_mining_analysis(recs)
        assert len(res["recommendations"]) == 1
        assert res["recommendations"][0]["count"] == 6
        assert res["recommendations"][0]["pct_dataset"] == 100.0

    def test_recomendacion_excluye_desconocidos(self):
        """Layout DESCONOCIDO o volumen < 5 → NO recomendado."""
        sig = FormatSignature()
        fp = DocumentFingerprint.build(sig, [])
        recs = [_rec(f"u{i}.pdf", fp, company="") for i in range(10)]
        res = run_mining_analysis(recs)
        assert res["recommendations"] == []

    def test_recomendacion_directa(self):
        familias = detect_families(_records(n_std=6, n_libre=1), threshold=70)
        cov = coverage_by_top_families(familias)
        recs = recommend_extractors(familias, cov)
        assert recs and recs[0]["count"] == 6

    def test_dashboard_markdown(self, tmp_path):
        res = run_mining_analysis(_records(n_std=6, n_libre=1))
        p = tmp_path / "document_mining_report.md"
        write_dashboard_report(res, p)
        texto = p.read_text()
        for section in [
            "Resumen Ejecutivo", "Distribución", "Top Familias",
            "Top Empresas", "Top Variantes", "Cobertura Esperada",
            "Representantes por Familia", "Familias Candidatas",
            "Problemas Detectados", "Recomendación Automática",
        ]:
            assert section in texto

    def test_csvs_escritos(self, tmp_path):
        res = run_mining_analysis(_records(n_std=6, n_libre=1))
        out = tmp_path / "reports"
        paths = write_csvs(res, out)
        for name in ["families", "coverage", "clusters", "representatives", "similarity_summary"]:
            p = paths[name]
            assert p.exists()
            raw = p.read_bytes()
            assert raw.startswith(b"\xef\xbb\xbf")  # BOM → Excel
            assert raw.decode("utf-8-sig").strip()

    def test_csv_familias_contenido(self, tmp_path):
        res = run_mining_analysis(_records(n_std=3, n_libre=1))
        p = write_csvs(res, tmp_path)["families"]
        content = p.read_text(encoding="utf-8-sig")
        assert "family_id" in content
        assert "VERTICAL" in content

    def test_save_load_resultado(self, tmp_path):
        res = run_mining_analysis(_records(n_std=3, n_libre=1))
        p = tmp_path / "mining.json"
        save_analysis_result(res, p)
        loaded = load_analysis_result(p)
        assert loaded["n_families"] == res["n_families"]
        assert loaded["n_documents"] == res["n_documents"]
        assert len(loaded["similarity_summary"]) == 4


# ═══════════════════════════════════════════════════════════════════
# Tool (collect_records + caché)
# ═══════════════════════════════════════════════════════════════════

class TestTool:
    def _make_xlsx(self, path: Path, rows: list[list]):
        import pandas as pd
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
        self._make_xlsx(ds / "a" / "libre1.xlsx", [
            ["Caja", 1500000],
            ["Bancos", 5200000],
        ])
        return ds

    def test_collect_records_y_cache(self, tmp_path):
        from tools.run_document_mining import collect_records
        ds = self._setup_dataset(tmp_path)
        cache = tmp_path / "fingerprints.json"
        records, errores = collect_records(ds, cache_path=cache, quiet=True)
        assert errores == 0
        assert len(records) == 2
        assert cache.exists()

        # Segunda llamada → carga de caché (misma cantidad, sin rescanear).
        records2, _ = collect_records(ds, cache_path=cache, quiet=True)
        assert len(records2) == 2

    def test_run_mining_tool(self, tmp_path):
        from tools.run_document_mining import run_mining
        ds = self._setup_dataset(tmp_path)
        res = run_mining(
            datasets_dir=ds,
            cache_path=tmp_path / "fp.json",
            result_path=tmp_path / "mining.json",
            report_path=tmp_path / "report.md",
            csvs_dir=tmp_path / "csv",
            quiet=True,
        )
        assert res["n_documents"] == 2
        assert res["n_families"] >= 1
        assert (tmp_path / "mining.json").exists()
        assert (tmp_path / "report.md").exists()
        assert (tmp_path / "csv" / "families.csv").exists()


# ═══════════════════════════════════════════════════════════════════
# UI — Inteligencia del Dataset
# ═══════════════════════════════════════════════════════════════════

class TestUiInteligencia:
    def test_tab_sin_resultado(self, monkeypatch):
        import app_validacion
        monkeypatch.setattr(app_validacion, "_cargar_mining_result", lambda: None)
        rendered = []
        monkeypatch.setattr(app_validacion.st, "info", lambda m: rendered.append(m))
        app_validacion._tab_inteligencia()
        assert any("minería" in r for r in rendered)

    def test_tab_muestra_metricas(self, monkeypatch):
        import app_validacion
        res = run_mining_analysis(_records(n_std=6, n_libre=1))
        monkeypatch.setattr(app_validacion, "_cargar_mining_result", lambda: res)

        metrics = []
        rendered = []
        monkeypatch.setattr(app_validacion.st, "markdown", lambda m: rendered.append(m))
        monkeypatch.setattr(app_validacion.st, "caption", lambda m: rendered.append(m))
        monkeypatch.setattr(app_validacion.st, "dataframe", lambda *a, **k: None)
        monkeypatch.setattr(app_validacion.st, "write", lambda m: rendered.append(m))

        class _FakeCol:
            def metric(self, *a, **k):
                metrics.append(a)

        def fake_columns(n):
            return [_FakeCol() for _ in range(n)]

        monkeypatch.setattr(app_validacion.st, "columns", fake_columns)

        app_validacion._tab_inteligencia()
        assert any("Inteligencia del Dataset" in r for r in rendered)
        labels = [m[0] for m in metrics]
        assert "Familias detectadas" in labels
        assert "Documentos analizados" in labels
        assert "Similitud media global" in labels
        assert "Pares comparados" in labels


# ═══════════════════════════════════════════════════════════════════
# Backward compatibility
# ═══════════════════════════════════════════════════════════════════

class TestBackwardCompat:
    def test_parser_idem_con_mining_importado(self):
        """El mining NO altera el resultado del Parser Universal."""
        from parser_universal import ParserPDF
        from document_intelligence.mining import run_mining_analysis  # noqa: F401

        path = _pdf_path()
        base = ParserPDF().parsear(path)
        again = ParserPDF().parsear(path)
        assert len(again.cuentas) == len(base.cuentas)
        for c1, c2 in zip(base.cuentas, again.cuentas):
            assert c1.nombre == c2.nombre
            assert c1.monto == c2.monto
            assert c1.codigo == c2.codigo

    def test_knowledge_clustering_intacto(self):
        """cluster_fingerprints de la DKB sigue igual tras importar mining."""
        from document_intelligence.knowledge import cluster_fingerprints
        clusters = cluster_fingerprints(
            [_fp_estandar(), _fp_estandar(), _fp_libre()], threshold=70
        )
        assert len(clusters) == 2

    def test_matcher_no_cambiado(self):
        from document_intelligence.knowledge import Matcher
        from document_intelligence.knowledge import DocumentProfile
        p = DocumentProfile.new(name="X", company="", family="PDF_ESTANDAR",
                                fingerprint=_fp_estandar())
        result = Matcher().match(_fp_estandar(), [p])
        assert result.similarity >= 90.0
