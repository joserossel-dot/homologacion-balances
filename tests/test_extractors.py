"""Tests del framework de extractores especializados (Sprint 34).

Cubre:
  ✓ registro (decorator + diccionario interno, get/list/get_for_family)
  ✓ ExtractorResult (serialización)
  ✓ scaffolds Nogales/AICSA/Wilug/Gonzagri (registrados, delegan)
  ✓ UniversalExtractor (delegación 1:1, fallback, nunca lanza)
  ✓ SpecializedExtractorFactory (match → especializado, fallback → universal,
    nunca lanza)
  ✓ integración mínima: resultado.extractor_info sin cambiar la extracción
  ✓ el Parser Universal produce EXACTAMENTE la misma salida antes/después
"""

from __future__ import annotations

from pathlib import Path

import pytest

from document_intelligence import (
    DocumentProcessingContext,
    ExtractorType,
    FormatAnalyzer,
    FormatSignature,
)
from document_intelligence.extractors import (
    ExtractorResult,
    SpecializedExtractor,
    SpecializedExtractorFactory,
    UniversalExtractor,
    get_extractor,
    get_extractor_for_family,
    instantiate,
    list_extractors,
    register_extractor,
)
from document_intelligence.extractors.specialized import (
    AicsaExtractor,
    GonzagriExtractor,
    NogalesExtractor,
    WilugExtractor,
)
from document_intelligence.knowledge import DocumentFingerprint
from document_intelligence.mining import DocumentFamily
from document_intelligence.signature import (
    CodePattern,
    ColumnType,
    DocumentType as SigDocumentType,
    Family as SigFamily,
    LayoutType,
    NumericPattern,
)
from parser_universal import ParserPDF

BASE_DIR = Path(__file__).resolve().parent.parent
DATASET_DIR = BASE_DIR / "datasets" / "validacion"
BALANCE_2016 = DATASET_DIR / "BALANCE 2016.pdf"

# Familias reales del mining (Sprint 33).
FAM_NOGALES = "cluster_4c326713f3"
FAM_AICSA = "cluster_0a1bebffff"
FAM_GONZAGRI = "cluster_02e4348704"


def _pdf_path() -> Path:
    if not BALANCE_2016.exists():
        pytest.skip(f"PDF no encontrado: {BALANCE_2016}")
    return BALANCE_2016


def _sig_nogales() -> FormatSignature:
    """Signature típica de la familia Nogales (VERTICAL/COMPACTO/ER)."""
    return FormatSignature(
        document_type=SigDocumentType.ESTADO_RESULTADOS,
        family=SigFamily.PDF_ESTANDAR,
        layout=LayoutType.VERTICAL,
        orientation="portrait",
        code_pattern=CodePattern.COMPACTO,
        numeric_pattern=NumericPattern.CHILENO,
        columns=[ColumnType.CODIGO, ColumnType.NOMBRE, ColumnType.MONTO],
        confidence=0.9,
    )


_LINEAS_NOGALES = [
    "Codigo Cuenta Monto",
    "1111001 Caja 1.500.000",
    "1111002 Bancos 5.200.000",
    "Total Activo 6.700.000",
]


def _familia_nogales() -> DocumentFamily:
    fp = DocumentFingerprint.build(_sig_nogales(), _LINEAS_NOGALES)
    return DocumentFamily(id=FAM_NOGALES, centroid=fp)


def _snapshot_cuentas(resultado) -> list[tuple]:
    """Snapshot EXACTO de todas las cuentas (orden + todos los campos)."""
    return [
        (
            c.linea, c.codigo, c.nombre, c.monto,
            c.origen_columna.value, c.es_total,
            c.confianza_extraccion, c.tipo_cuenta,
        )
        for c in resultado.cuentas
    ]


# ═══════════════════════════════════════════════════════════════════
# Registry
# ═══════════════════════════════════════════════════════════════════

class TestRegistry:
    def test_list_extractors_incluye_scaffolds(self):
        ids = set(list_extractors())
        assert {"nogales", "aicsa", "wilug", "gonzagri"} <= ids

    def test_get_extractor(self):
        assert get_extractor("nogales") is NogalesExtractor
        assert get_extractor("aicsa") is AicsaExtractor
        assert get_extractor("wilug") is WilugExtractor
        assert get_extractor("gonzagri") is GonzagriExtractor
        assert get_extractor("no_existe") is None

    def test_get_extractor_for_family(self):
        assert get_extractor_for_family(FAM_NOGALES) is NogalesExtractor
        assert get_extractor_for_family(FAM_AICSA) is AicsaExtractor
        assert get_extractor_for_family(FAM_GONZAGRI) is GonzagriExtractor
        # Familia sin extractor registrado → None (usa universal).
        assert get_extractor_for_family("cluster_zzz") is None

    def test_register_extractor_decorator_automatico(self):
        @register_extractor()
        class MiExtractor(SpecializedExtractor):
            id = "test_decorador"
            display_name = "Test Decorador"
            supported_families = ["cluster_fake_1"]

        assert get_extractor("test_decorador") is MiExtractor
        assert get_extractor_for_family("cluster_fake_1") is MiExtractor

    def test_register_extractor_con_kwargs(self):
        @register_extractor(id="test_kwargs", families=["cluster_fake_2"])
        class OtroExtractor(SpecializedExtractor):
            display_name = "Otro"

        assert get_extractor("test_kwargs") is OtroExtractor
        assert OtroExtractor.id == "test_kwargs"
        assert OtroExtractor.supported_families == ["cluster_fake_2"]
        assert get_extractor_for_family("cluster_fake_2") is OtroExtractor

    def test_register_idempotente(self, monkeypatch):
        import document_intelligence.extractors.registry as reg_mod

        n_registros = len(reg_mod._REGISTRY)
        n_familia = len(reg_mod._FAMILY_INDEX.get("cluster_fake_3", []))

        @register_extractor()
        class IdemExtractor(SpecializedExtractor):
            id = "test_idem"
            supported_families = ["cluster_fake_3"]

        # Registrar de nuevo la misma clase no duplica entradas.
        register_extractor(IdemExtractor)
        register_extractor(IdemExtractor)

        assert len(reg_mod._REGISTRY) == n_registros + 1
        assert len(reg_mod._FAMILY_INDEX.get("cluster_fake_3", [])) == n_familia + 1

    def test_instantiate(self):
        assert isinstance(instantiate("nogales"), NogalesExtractor)
        assert instantiate("no_existe") is None

    def test_universal_no_esta_en_registry_de_especializados(self):
        # UniversalExtractor es el fallback, no un extractor "especializado"
        # registrado en el diccionario interno.
        assert "universal" not in list_extractors()


# ═══════════════════════════════════════════════════════════════════
# ExtractorResult
# ═══════════════════════════════════════════════════════════════════

class TestExtractorResult:
    def test_valores_por_defecto(self):
        r = ExtractorResult(extractor_id="x", display_name="X")
        assert r.family_id == "DESCONOCIDO"
        assert r.confidence == 0.0
        assert r.elapsed_ms == 0
        assert r.fallback_used is True
        assert r.result is None

    def test_serializacion_round_trip(self):
        r = ExtractorResult(
            extractor_id="nogales",
            display_name="Nogales",
            family_id=FAM_NOGALES,
            confidence=0.85,
            elapsed_ms=123,
            fallback_used=True,
        )
        data = r.to_dict()
        assert data["extractor_id"] == "nogales"
        assert data["family_id"] == FAM_NOGALES
        restored = ExtractorResult.from_dict(data)
        assert restored.extractor_id == "nogales"
        assert restored.display_name == "Nogales"
        assert restored.family_id == FAM_NOGALES
        assert restored.confidence == 0.85
        assert restored.elapsed_ms == 123
        assert restored.fallback_used is True

    def test_to_dict_sin_result(self):
        r = ExtractorResult(extractor_id="universal", display_name="Parser Universal")
        data = r.to_dict()
        assert "result" not in data  # el ResultadoParseo no se serializa


# ═══════════════════════════════════════════════════════════════════
# Scaffolds
# ═══════════════════════════════════════════════════════════════════

class TestScaffolds:
    @pytest.mark.parametrize(
        "cls,extractor_id,families",
        [
            (NogalesExtractor, "nogales", [FAM_NOGALES]),
            (AicsaExtractor, "aicsa", [FAM_AICSA]),
            (WilugExtractor, "wilug", [FAM_NOGALES]),
            (GonzagriExtractor, "gonzagri", [FAM_GONZAGRI]),
        ],
    )
    def test_herencia_y_configuracion(self, cls, extractor_id, families):
        assert issubclass(cls, SpecializedExtractor)
        assert cls.id == extractor_id
        assert cls.display_name
        assert cls.supported_families == families

    def test_extract_delega_al_universal(self, monkeypatch):
        """Los scaffolds NO tienen lógica propia: delegan 1:1."""
        from document_intelligence.extractors.universal import UniversalExtractor as UE

        stub = ExtractorResult(
            extractor_id="universal",
            display_name="Parser Universal",
            result={"cuentas": [1, 2, 3]},
            elapsed_ms=5,
            fallback_used=True,
        )

        def fake_extract(self, path, context=None):
            return stub

        monkeypatch.setattr(UE, "extract", fake_extract)

        for cls in (NogalesExtractor, AicsaExtractor, WilugExtractor, GonzagriExtractor):
            res = cls().extract(Path("x.pdf"))
            assert isinstance(res, ExtractorResult)
            assert res.extractor_id == cls.id
            assert res.display_name == cls.display_name
            assert res.fallback_used is True
            assert res.result == stub.result
            assert res.family_id == cls.supported_families[0]


# ═══════════════════════════════════════════════════════════════════
# UniversalExtractor
# ═══════════════════════════════════════════════════════════════════

class TestUniversalExtractor:
    def test_extract_pdf_real(self):
        res = UniversalExtractor().extract(_pdf_path())
        assert isinstance(res, ExtractorResult)
        assert res.extractor_id == "universal"
        assert res.display_name == "Parser Universal"
        assert res.fallback_used is True
        assert res.elapsed_ms >= 0
        assert res.result is not None
        assert len(res.result.cuentas) > 0

    def test_extract_archivo_inexistente_no_lanza(self):
        res = UniversalExtractor().extract(Path("no_existe.pdf"))
        # ParserPDF retorna un ResultadoParseo con validación fallida;
        # el extractor nunca lanza.
        assert isinstance(res, ExtractorResult)
        assert res.fallback_used is True

    def test_extract_cuando_parser_lanza_usa_fallback(self, monkeypatch):
        from document_intelligence.extractors import universal as uni_mod
        from parser_universal import ParserPDF

        def romper(self, path, context=None):
            raise RuntimeError("parser caído")

        monkeypatch.setattr(ParserPDF, "parsear", romper)
        res = UniversalExtractor().extract(Path("x.pdf"))
        assert isinstance(res, ExtractorResult)
        assert res.result is None
        assert res.fallback_used is True


# ═══════════════════════════════════════════════════════════════════
# SpecializedExtractorFactory
# ═══════════════════════════════════════════════════════════════════

class TestFactory:
    def _context(self, sig: FormatSignature) -> DocumentProcessingContext:
        return DocumentProcessingContext(
            pdf_path=Path("balance.pdf"),
            signature=sig,
            extractor_type=ExtractorType.UNKNOWN,
            confidence=sig.confidence,
        )

    def test_match_familia_registrada_devuelve_extractor(self, monkeypatch):
        import document_intelligence.extractors.factory as fac_mod

        monkeypatch.setattr(fac_mod, "extract_preview_lines", lambda path, **k: list(_LINEAS_NOGALES))
        factory = SpecializedExtractorFactory(families=[_familia_nogales()])

        extractor = factory.build(Path("balance.pdf"), self._context(_sig_nogales()))
        assert isinstance(extractor, NogalesExtractor)

        info = factory.detect(Path("balance.pdf"), self._context(_sig_nogales()))
        assert info["extractor_id"] == "nogales"
        assert info["family_id"] == FAM_NOGALES
        assert info["confidence"] > 0.7
        assert info["fallback_used"] is False

    def test_sin_contexto_devuelve_universal(self):
        factory = SpecializedExtractorFactory(families=[_familia_nogales()])
        assert factory.build(Path("x.pdf"), None).id == "universal"
        info = factory.detect(Path("x.pdf"), None)
        assert info["extractor_id"] == "universal"
        assert info["fallback_used"] is True

    def test_contexto_sin_signature_devuelve_universal(self):
        factory = SpecializedExtractorFactory(families=[_familia_nogales()])
        ctx = object()  # sin atributo .signature
        assert factory.build(Path("x.pdf"), ctx).id == "universal"

    def test_similitud_baja_devuelve_universal(self, monkeypatch):
        import document_intelligence.extractors.factory as fac_mod

        monkeypatch.setattr(fac_mod, "extract_preview_lines", lambda path, **k: list(_LINEAS_NOGALES))
        # Familia totalmente distinta (LIBRE/SIN_CODIGO) → similitud baja.
        fp_libre = DocumentFingerprint.build(
            FormatSignature(
                document_type=SigDocumentType.OTRO,
                family=SigFamily.PDF_LIBRE,
                layout=LayoutType.LIBRE,
                code_pattern=CodePattern.SIN_CODIGO,
                numeric_pattern=NumericPattern.DESCONOCIDO,
                columns=[],
            ),
            ["Balance general", "Activo 100", "Pasivo 50"],
        )
        familia_libre = DocumentFamily(id="cluster_libre", centroid=fp_libre)
        factory = SpecializedExtractorFactory(families=[familia_libre], threshold=70.0)

        extractor = factory.build(Path("balance.pdf"), self._context(_sig_nogales()))
        assert extractor.id == "universal"
        info = factory.detect(Path("balance.pdf"), self._context(_sig_nogales()))
        assert info["fallback_used"] is True
        assert "umbral" in info["reason"]

    def test_familia_conocida_sin_extractor_devuelve_universal(self, monkeypatch):
        import document_intelligence.extractors.factory as fac_mod

        monkeypatch.setattr(fac_mod, "extract_preview_lines", lambda path, **k: list(_LINEAS_NOGALES))
        fp = DocumentFingerprint.build(_sig_nogales(), _LINEAS_NOGALES)
        # Familia con fingerprint idéntico pero SIN extractor registrado.
        familia = DocumentFamily(id="cluster_sin_extractor", centroid=fp)
        factory = SpecializedExtractorFactory(families=[familia])

        info = factory.detect(Path("balance.pdf"), self._context(_sig_nogales()))
        assert info["extractor_id"] == "universal"
        assert info["fallback_used"] is True
        assert "sin extractor" in info["reason"]

    def test_nunca_lanza_con_inputs_rotos(self, monkeypatch):
        factory = SpecializedExtractorFactory(families=[_familia_nogales()])

        class ContextoExplota:
            @property
            def signature(self):
                raise RuntimeError("boom")

        assert factory.build(Path("x.pdf"), ContextoExplota()).id == "universal"
        info = factory.detect(Path("x.pdf"), ContextoExplota())
        assert info["extractor_id"] == "universal"
        assert info["fallback_used"] is True

    def test_factory_por_defecto_carga_mining_real(self):
        """Con el mining real (familia Nogales), el factory no lanza."""
        factory = SpecializedExtractorFactory()
        assert factory.build(Path("no_existe.pdf"), None).id == "universal"


# ═══════════════════════════════════════════════════════════════════
# Integración mínima en el Parser Universal
# ═══════════════════════════════════════════════════════════════════

class TestParserIntegracion:
    def test_parsear_adjunta_extractor_info(self):
        resultado = ParserPDF().parsear(_pdf_path())
        assert resultado.extractor_info is not None
        for key in ("extractor_id", "display_name", "family_id",
                    "confidence", "fallback_used", "reason", "elapsed_ms"):
            assert key in resultado.extractor_info
        assert isinstance(resultado.extractor_info["extractor_id"], str)
        assert 0.0 <= resultado.extractor_info["confidence"] <= 1.0

    def test_parser_misma_salida_antes_despues(self, monkeypatch):
        """El Parser Universal produce EXACTAMENTE la misma salida.

        "Antes" = comportamiento sin Document Intelligence ni anotación
        (pre-Sprint 31/34). "Después" = con análisis + extractor_info.
        """
        import parser_universal as pu

        path = _pdf_path()
        monkeypatch.setattr(pu.ParserPDF, "_analizar_documento", lambda self, p: None)

        antes = pu.ParserPDF().parsear(path)
        snap_antes = _snapshot_cuentas(antes)
        assert antes.extractor_info is None  # sin análisis → sin anotación

        monkeypatch.undo()  # volver al comportamiento normal

        despues = pu.ParserPDF().parsear(path)
        snap_despues = _snapshot_cuentas(despues)
        assert despues.extractor_info is not None

        # Cantidad, nombre, monto, código, orden, tipo: TODO idéntico.
        assert len(snap_antes) == len(snap_despues)
        assert snap_antes == snap_despues

    def test_parser_misma_salida_si_factory_falla(self, monkeypatch):
        """Si la factory falla, extractor_info queda en None y la salida
        del parser es idéntica (fallback absoluto)."""
        import parser_universal as pu
        from document_intelligence.extractors.factory import (
            SpecializedExtractorFactory,
        )

        path = _pdf_path()
        # Baseline con factory sana.
        baseline = _snapshot_cuentas(pu.ParserPDF().parsear(path))

        def romper(self, path, context=None):
            raise RuntimeError("factory caída")

        monkeypatch.setattr(SpecializedExtractorFactory, "detect", romper)
        resultado = pu.ParserPDF().parsear(path)
        assert resultado.extractor_info is None
        assert _snapshot_cuentas(resultado) == baseline

    def test_parsear_determinista(self):
        r1 = ParserPDF().parsear(_pdf_path())
        r2 = ParserPDF().parsear(_pdf_path())
        assert _snapshot_cuentas(r1) == _snapshot_cuentas(r2)

    def test_parsear_sin_document_intelligence(self, monkeypatch):
        import parser_universal as pu

        monkeypatch.setattr(pu.ParserPDF, "_analizar_documento", lambda self, p: None)
        resultado = pu.ParserPDF().parsear(_pdf_path())
        assert resultado.extractor_info is None
        assert len(resultado.cuentas) > 0
