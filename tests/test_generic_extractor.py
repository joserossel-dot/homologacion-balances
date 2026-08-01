"""Tests del GenericTableExtractor y el orden de columnas por perfil (Sprint 36).

Cubre:
  ✓ layout_hint_for_profile (keys → layout_hint, orden, casos sin mejora)
  ✓ estructura_coincide (nº de montos, códigos, layout)
  ✓ GenericTableExtractor.extract (perfil → fallback_used=False; fallback)
  ✓ profile_layout_hint (familia sin perfil, cobertura, estructura)
  ✓ integración en ParserPDF: con ENABLE_DYNAMIC_LAYOUT activo el perfil
    se aplica al orden de columnas; con el flag en False NO cambia nada
  ✓ backward compatibility: extracción universal idéntica por defecto
"""

from __future__ import annotations

from pathlib import Path

import pytest

import parser_universal as pu
from document_intelligence.extractors import (
    GenericTableExtractor,
    SpecializedExtractorFactory,
)
from document_intelligence.extractors.profile_driven import (
    estructura_coincide,
    layout_hint_for_profile,
    profile_layout_hint,
)
from document_intelligence.extractors.specialized import (
    AicsaExtractor,
    GonzagriExtractor,
    NogalesExtractor,
)
from document_intelligence.trainer import ColumnProfile, TableProfile
from parser_universal import ParserPDF

BASE_DIR = Path(__file__).resolve().parent.parent
BALANCE_2016 = BASE_DIR / "datasets" / "validacion" / "BALANCE 2016.pdf"

FAM_NOGALES = "cluster_4c326713f3"
FAM_AICSA = "cluster_0a1bebffff"

_LINEAS_2COL = [
    "BALANCE GENERAL",
    "Código Cuenta Debe Haber",
    "1111001 Caja 1.500.000 500.000",
    "1111002 Bancos 5.200.000 1.000.000",
    "TOTAL ACTIVO 6.700.000 1.500.000",
]

_LINEAS_1COL = [
    "ESTADO DE RESULTADOS",
    "Ingresos por ventas 1.500.000",
    "Resultado del ejercicio 600.000",
]


def _perfil_debe_haber() -> TableProfile:
    p = TableProfile(family_id="cluster_x", family_name="Fam X")
    p.layout = "VERTICAL"
    p.n_documents = 5
    p.code_column = ColumnProfile(key="CODIGO", side="left", position=0)
    p.amount_columns = [
        ColumnProfile(key="DEBE", side="right", position=2, detection_rate=1.0),
        ColumnProfile(key="HABER", side="right", position=1, detection_rate=1.0),
    ]
    p.validation = {"coverage": 0.9, "precision": 0.8}
    return p


def _pdf() -> Path:
    if not BALANCE_2016.exists():
        pytest.skip(f"PDF no encontrado: {BALANCE_2016}")
    return BALANCE_2016


# ---------------------------------------------------------------------------
# layout_hint_for_profile
# ---------------------------------------------------------------------------

class TestLayoutHint:
    def test_debe_haber(self) -> None:
        p = _perfil_debe_haber()
        assert layout_hint_for_profile(p) == ["deudor", "acreedor"]

    def test_activo_pasivo(self) -> None:
        p = _perfil_debe_haber()
        p.amount_columns = [
            ColumnProfile(key="ACTIVO", side="right", position=2),
            ColumnProfile(key="PASIVO", side="right", position=1),
        ]
        assert layout_hint_for_profile(p) == ["activo", "pasivo"]

    def test_orden_izquierda_a_derecha(self) -> None:
        p = _perfil_debe_haber()
        p.amount_columns = [
            ColumnProfile(key="MONTO", side="right", position=4),
            ColumnProfile(key="PERDIDA", side="right", position=3),
            ColumnProfile(key="GANANCIA", side="right", position=2),
            ColumnProfile(key="MONTO", side="right", position=1),
        ]
        # position 4 (izquierda) primero → MONTO se neutraliza a "saldo".
        assert layout_hint_for_profile(p) == ["saldo", "perdida", "ganancia", "saldo"]

    def test_una_sola_columna_monetaria(self) -> None:
        p = _perfil_debe_haber()
        p.amount_columns = [ColumnProfile(key="MONTO", side="right", position=1)]
        assert layout_hint_for_profile(p) is None

    def test_todas_monetarias_neutrales(self) -> None:
        p = _perfil_debe_haber()
        p.amount_columns = [
            ColumnProfile(key="MONTO", side="right", position=2),
            ColumnProfile(key="MONTO", side="right", position=1),
        ]
        assert layout_hint_for_profile(p) is None

    def test_sin_perfil(self) -> None:
        assert layout_hint_for_profile(None) is None


# ---------------------------------------------------------------------------
# estructura_coincide
# ---------------------------------------------------------------------------

class TestEstructuraCoincide:
    def test_coincide(self) -> None:
        assert estructura_coincide(_perfil_debe_haber(), _LINEAS_2COL)

    def test_numero_de_montos_distinto(self) -> None:
        assert not estructura_coincide(_perfil_debe_haber(), _LINEAS_1COL)

    def test_sin_lineas(self) -> None:
        assert not estructura_coincide(_perfil_debe_haber(), [])

    def test_sin_perfil(self) -> None:
        assert not estructura_coincide(None, _LINEAS_2COL)


# ---------------------------------------------------------------------------
# profile_layout_hint (gates)
# ---------------------------------------------------------------------------

class TestProfileLayoutHint:
    def test_familia_desconocida(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "document_intelligence.extractors.profile_driven._cargar_perfiles",
            lambda: {"cluster_x": _perfil_debe_haber()},
        )
        assert profile_layout_hint(_pdf(), family_id="DESCONOCIDO") is None

    def test_familia_sin_perfil(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "document_intelligence.extractors.profile_driven._cargar_perfiles",
            lambda: {},
        )
        assert profile_layout_hint(_pdf(), family_id="cluster_nope") is None

    def test_cobertura_insuficiente(self, monkeypatch) -> None:
        p = _perfil_debe_haber()
        p.validation = {"coverage": 0.2}
        monkeypatch.setattr(
            "document_intelligence.extractors.profile_driven._cargar_perfiles",
            lambda: {"cluster_x": p},
        )
        assert profile_layout_hint(_pdf(), family_id="cluster_x") is None

    def test_estructura_no_coincide(self, monkeypatch) -> None:
        p = _perfil_debe_haber()
        monkeypatch.setattr(
            "document_intelligence.extractors.profile_driven._cargar_perfiles",
            lambda: {"cluster_x": p},
        )
        monkeypatch.setattr(
            "document_intelligence.extractors.profile_driven.estructura_coincide",
            lambda *a, **k: False,
        )
        assert profile_layout_hint(_pdf(), family_id="cluster_x") is None

    def test_aplica_hint(self, monkeypatch) -> None:
        p = _perfil_debe_haber()
        monkeypatch.setattr(
            "document_intelligence.extractors.profile_driven._cargar_perfiles",
            lambda: {"cluster_x": p},
        )
        monkeypatch.setattr(
            "document_intelligence.extractors.profile_driven.estructura_coincide",
            lambda *a, **k: True,
        )
        assert profile_layout_hint(_pdf(), family_id="cluster_x") == ["deudor", "acreedor"]


# ---------------------------------------------------------------------------
# GenericTableExtractor.extract
# ---------------------------------------------------------------------------

class TestGenericExtractor:
    def test_scaffolds_heredan_generic(self) -> None:
        for cls in (NogalesExtractor, AicsaExtractor, GonzagriExtractor):
            assert issubclass(cls, GenericTableExtractor)
            assert isinstance(cls(), GenericTableExtractor)

    def test_perfil_aplicado_no_fallback(self, monkeypatch) -> None:
        monkeypatch.setattr(
            SpecializedExtractorFactory, "detect",
            lambda self, path, context=None: {
                "extractor_id": "nogales", "display_name": "Nogales",
                "family_id": FAM_NOGALES, "confidence": 0.9,
                "fallback_used": False, "reason": "test",
            },
        )
        monkeypatch.setattr(
            "document_intelligence.extractors.profile_driven.profile_layout_hint",
            lambda *a, **k: ["deudor", "acreedor"],
        )
        res = NogalesExtractor().extract(_pdf())
        assert res.fallback_used is False
        assert res.extractor_id == "nogales"
        assert res.family_id == FAM_NOGALES
        assert res.result is not None and len(res.result.cuentas) > 0

    def test_sin_perfil_delega_al_universal(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "document_intelligence.extractors.profile_driven.profile_layout_hint",
            lambda *a, **k: None,
        )
        from document_intelligence.extractors.universal import UniversalExtractor as UE

        stub_ok = type("R", (), {"cuentas": [1]})
        result_stub = type("ER", (), {
            "extractor_id": "universal", "display_name": "u",
            "elapsed_ms": 3, "fallback_used": True, "result": stub_ok(),
        })
        monkeypatch.setattr(
            UE, "extract",
            lambda self, path, context=None: result_stub(),
        )
        res = NogalesExtractor().extract(Path("x.pdf"))
        assert res.fallback_used is True
        assert res.extractor_id == "nogales"
        assert res.family_id == FAM_NOGALES


# ---------------------------------------------------------------------------
# Integración en ParserPDF
# ---------------------------------------------------------------------------

class TestParserIntegracion:
    def test_flag_off_no_cambia_nada(self, monkeypatch) -> None:
        """Por defecto (ENABLE_DYNAMIC_LAYOUT=False) la extracción es universal."""
        monkeypatch.setattr(pu, "ENABLE_DYNAMIC_LAYOUT", False)
        resultado = ParserPDF().parsear(_pdf())
        assert resultado.cuentas
        assert not any("Perfil de familia" in w for w in resultado.advertencias)

    def test_flag_on_aplica_perfil(self, monkeypatch) -> None:
        monkeypatch.setattr(pu, "ENABLE_DYNAMIC_LAYOUT", True)
        monkeypatch.setattr(
            SpecializedExtractorFactory, "detect",
            lambda self, path, context=None: {
                "extractor_id": "nogales", "display_name": "Nogales",
                "family_id": FAM_NOGALES, "confidence": 0.9,
                "fallback_used": False, "reason": "test",
            },
        )
        monkeypatch.setattr(
            "document_intelligence.extractors.profile_driven.profile_layout_hint",
            lambda *a, **k: ["deudor", "acreedor"],
        )
        resultado = ParserPDF().parsear(_pdf())
        assert any("Perfil de familia" in w for w in resultado.advertencias)
        assert resultado.extractor_info["family_id"] == FAM_NOGALES

    def test_flag_on_perfil_no_aplicable_usa_heuristica(self, monkeypatch) -> None:
        monkeypatch.setattr(pu, "ENABLE_DYNAMIC_LAYOUT", True)
        monkeypatch.setattr(
            SpecializedExtractorFactory, "detect",
            lambda self, path, context=None: {
                "extractor_id": "nogales", "display_name": "Nogales",
                "family_id": FAM_NOGALES, "confidence": 0.9,
                "fallback_used": False, "reason": "test",
            },
        )
        monkeypatch.setattr(
            "document_intelligence.extractors.profile_driven.profile_layout_hint",
            lambda *a, **k: None,
        )
        resultado = ParserPDF().parsear(_pdf())
        # No se aplicó ningún perfil: no debe haber la advertencia de columnas
        # aplicadas ("Perfil de familia (<id>): N columnas").
        assert not any(
            w.startswith("Perfil de familia (") for w in resultado.advertencias
        )
        # Heurística estándar: el orden de columnas queda como el universal.
        assert resultado.cuentas
