"""Tests del Extractor Trainer (Sprint 35).

Cubre:
  ✓ TableProfile / ColumnProfile / HeaderProfile / FooterProfile (to_dict↔from_dict)
  ✓ aprendizaje del perfil desde documentos sintéticos
    (VERTICAL/COMPACTO DEBE-HABER, LIBRE/GUION, ER de 1 columna)
  ✓ filtro de núcleo coherente (outliers por estructura no ensucian el perfil)
  ✓ detection_rate <= 1.0 y columnas ancladas por posición
  ✓ ProfileValidator (cobertura, precisión, columnas, filas perdidas)
  ✓ ProfileRepository (save/load round-trip, archivos individuales, reporte)
  ✓ no-regresión: los módulos del ecosistema siguen exportándose
"""

from __future__ import annotations

from pathlib import Path

import pytest

from document_intelligence.trainer import (
    ColumnProfile,
    FooterProfile,
    HeaderProfile,
    ProfileRepository,
    ProfileValidator,
    TableProfile,
    TableProfileTrainer,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# Balance VERTICAL con códigos COMPACTO, secciones ACTIVO/PASIVO (detector
# clasifica VERTICAL/BALANCE) y encabezado de columnas DEBE/HABER.
DOC_VERTICAL_1 = [
    "BALANCE GENERAL",
    "Código Cuenta Debe Haber",
    "1111001 Caja 1.500.000 500.000",
    "1111002 Bancos 5.200.000 1.000.000",
    "1112001 Deudores 2.000.000 900.000",
    "TOTAL ACTIVO 8.700.000 2.400.000",
    "TOTAL PASIVO 0 0",
]

DOC_VERTICAL_2 = [
    "BALANCE GENERAL",
    "Código Cuenta Debe Haber",
    "1111001 Caja 2.000.000 800.000",
    "1111002 Bancos 3.000.000 1.200.000",
    "1112001 Deudores 4.000.000 1.100.000",
    "TOTAL ACTIVO 9.000.000 3.100.000",
    "TOTAL PASIVO 0 0",
]

# Balance LIBRE con códigos GUION (comprobación sin secciones activo/pasivo:
# el detector del ecosistema la clasifica como OTRO, no BALANCE).
DOC_LIBRE_1 = [
    "BALANCE DE COMPROBACION",
    "RUT: 76.123.456-7",
    "",
    "1-01-01-00 Caja 100.000 50.000",
    "1-02-01-00 Banco 200.000 80.000",
    "1-99-00-00 TOTALES 300.000 130.000",
]

DOC_LIBRE_2 = [
    "BALANCE DE COMPROBACION",
    "RUT: 76.123.456-7",
    "",
    "1-01-01-00 Caja 150.000 60.000",
    "1-02-01-00 Banco 220.000 90.000",
    "1-99-00-00 TOTALES 370.000 150.000",
]

# Estado de Resultados de 1 columna (sin códigos; "Ingresos por ventas"
# es fila contable, no encabezado → no debe teñir las columnas de monto).
DOC_ER_1 = [
    "ESTADO DE RESULTADOS",
    "Ingresos por ventas 1.500.000",
    "Costo de ventas -900.000",
    "Resultado del ejercicio 600.000",
]

DOC_ER_2 = [
    "ESTADO DE RESULTADOS",
    "Ingresos por ventas 2.000.000",
    "Costo de ventas -1.200.000",
    "Resultado del ejercicio 800.000",
]


def _trainer() -> TableProfileTrainer:
    return TableProfileTrainer()


@pytest.fixture
def tmp_profile_dir(tmp_path: Path) -> Path:
    return tmp_path / "profiles"


# ---------------------------------------------------------------------------
# Serialización de perfiles
# ---------------------------------------------------------------------------

class TestProfileSerialization:
    def test_column_profile_roundtrip(self) -> None:
        col = ColumnProfile(key="DEBE", side="right", position=2,
                            detection_rate=1.0, docs=4)
        restored = ColumnProfile.from_dict(col.to_dict())
        assert restored == col

    def test_header_footer_roundtrip(self) -> None:
        h = HeaderProfile(rows=2, row_counts={2: 3}, keywords=["balance"])
        f = FooterProfile(trailing_rows=1, totals_position="BOTTOM",
                          total_keywords=["total"], keywords=["pie"])
        assert HeaderProfile.from_dict(h.to_dict()) == h
        assert FooterProfile.from_dict(f.to_dict()) == f

    def test_table_profile_roundtrip(self) -> None:
        profile = TableProfile(family_id="cluster_x", family_name="Fam X")
        profile.layout = "VERTICAL"
        profile.document_type = "BALANCE"
        profile.header_rows = 2
        profile.columns = [
            ColumnProfile(key="CODIGO", side="left", position=0),
            ColumnProfile(key="NOMBRE", side="left", position=1),
            ColumnProfile(key="DEBE", side="right", position=2),
            ColumnProfile(key="HABER", side="right", position=1),
        ]
        profile.amount_columns = profile.columns[2:]
        profile.n_documents = 5
        profile.docs_total = 7
        profile.docs_outliers = 2
        profile.header = HeaderProfile(rows=2)
        profile.footer = FooterProfile(trailing_rows=0)
        profile.validation = {"coverage": 0.9, "precision": 0.8}

        restored = TableProfile.from_dict(profile.to_dict())
        assert restored.family_id == "cluster_x"
        assert restored.docs_total == 7
        assert restored.docs_outliers == 2
        assert restored.header_rows == 2
        assert [c.key for c in restored.columns] == ["CODIGO", "NOMBRE", "DEBE", "HABER"]
        assert restored.validation == {"coverage": 0.9, "precision": 0.8}
        assert restored.header == profile.header  # type: ignore[union-attr]
        assert restored.footer == profile.footer  # type: ignore[union-attr]

    def test_accessores_semanticos(self) -> None:
        profile = TableProfile(family_id="x")
        profile.amount_columns = [
            ColumnProfile(key="PERDIDA", side="right", position=2),
            ColumnProfile(key="GANANCIA", side="right", position=1),
        ]
        assert profile.perdida is profile.amount_columns[0]
        assert profile.ganancia is profile.amount_columns[1]
        assert profile.activo is None
        assert profile.monto is None


# ---------------------------------------------------------------------------
# Aprendizaje
# ---------------------------------------------------------------------------

class TestTrainer:
    def test_aprende_vertical_debe_haber(self) -> None:
        profile = _trainer().train("cluster_v", "Fam V",
                                   [DOC_VERTICAL_1, DOC_VERTICAL_2])
        assert profile.layout == "VERTICAL"
        assert profile.header_rows == 2
        assert profile.table_start_row == 2
        keys = [c.key for c in profile.amount_columns]
        assert keys == ["DEBE", "HABER"]
        assert profile.amount_columns[0].position == 2
        assert profile.amount_columns[1].position == 1
        assert profile.code_column is not None
        assert profile.name_column is not None
        assert all(c.detection_rate <= 1.0 for c in profile.columns)
        assert profile.n_documents == 2

    def test_aprende_libre_guion(self) -> None:
        profile = _trainer().train("cluster_l", "Fam L",
                                   [DOC_LIBRE_1, DOC_LIBRE_2])
        assert profile.layout == "LIBRE"
        assert profile.code_pattern == "GUION"
        assert profile.code_column is not None
        assert [c.key for c in profile.amount_columns] == ["PERDIDA", "GANANCIA"]
        assert profile.document_type == "OTRO"  # detector del ecosistema

    def test_aprende_er_una_columna(self) -> None:
        profile = _trainer().train("cluster_er", "Fam ER",
                                   [DOC_ER_1, DOC_ER_2])
        assert profile.layout == "VERTICAL"
        assert profile.code_column is None
        assert profile.name_column is not None
        assert [c.key for c in profile.amount_columns] == ["MONTO"]
        assert profile.amount_columns[0].position == 1

    def test_filtro_nucleo_coherente(self) -> None:
        # 3 docs ER (1 columna) + 2 docs BALANCE (4 montos + códigos) → el
        # perfil debe describir la estructura dominante (ER) y marcar outliers.
        balance = [
            "BALANCE GENERAL",
            "Código Cuenta Activo Pasivo Pérdida Ganancia",
            "1111001 Caja 1.500.000 500.000 0 0",
            "TOTAL ACTIVO 1.500.000 500.000 0 0",
        ]
        docs = [DOC_ER_1, DOC_ER_2, DOC_ER_1, balance, balance]
        profile = _trainer().train("cluster_mix", "Fam Mix", docs)
        assert profile.n_documents == 3
        assert profile.docs_total == 5
        assert profile.docs_outliers == 2
        assert [c.key for c in profile.amount_columns] == ["MONTO"]

    def test_detection_rate_nunca_mayor_a_uno(self) -> None:
        # Incluso con montos heterogéneos, detection_rate <= 1.0.
        docs = [DOC_VERTICAL_1, DOC_VERTICAL_2, DOC_LIBRE_1, DOC_ER_1]
        profile = _trainer().train("cluster_het", "Fam Het", docs)
        assert profile.n_documents >= 1
        assert all(c.detection_rate <= 1.0 for c in profile.columns)
        assert all(c.docs <= profile.n_documents for c in profile.columns)

    def test_sin_documentos_utiles(self) -> None:
        profile = _trainer().train("cluster_vac", "Fam Vacía", [])
        assert profile.n_documents == 0
        assert profile.docs_total == 0
        assert profile.layout == "DESCONOCIDO"

    def test_documento_ilegible_no_rompe(self) -> None:
        profile = _trainer().train("cluster_vac", "Fam Vacía",
                                   [["texto", "sin", "números"]])
        assert profile.n_documents == 0


# ---------------------------------------------------------------------------
# Validación
# ---------------------------------------------------------------------------

class TestValidator:
    def test_cobertura_y_precision_perfectas(self) -> None:
        profile = _trainer().train("cluster_v", "Fam V",
                                   [DOC_VERTICAL_1, DOC_VERTICAL_2])
        v = ProfileValidator().validate(profile, [DOC_VERTICAL_1, DOC_VERTICAL_2])
        assert v["docs_validated"] == 2
        assert v["coverage"] == 1.0
        assert v["precision"] == 1.0
        assert v["total_rows_lost"] == 0

    def test_columnas_detectadas(self) -> None:
        profile = _trainer().train("cluster_v", "Fam V",
                                   [DOC_VERTICAL_1, DOC_VERTICAL_2])
        v = ProfileValidator().validate(profile, [DOC_VERTICAL_1])
        assert v["columns_expected"] == 4
        assert v["columns_detected"] == 4.0
        assert v["columns_rate"] == 1.0

    def test_documento_heterogeneo_baja_precision(self) -> None:
        profile = _trainer().train("cluster_v", "Fam V",
                                   [DOC_VERTICAL_1, DOC_VERTICAL_2])
        # Documento con filas de sección (sin montos) dentro de la región.
        con_secciones = [
            "BALANCE GENERAL",
            "Código Cuenta Debe Haber",
            "1111001 Caja 1.500.000 500.000",
            "ACTIVOS",
            "1111002 Bancos 5.200.000 1.000.000",
        ]
        v = ProfileValidator().validate_document(profile, con_secciones)
        assert v["coverage"] == 1.0
        assert 0.0 < v["precision"] < 1.0


# ---------------------------------------------------------------------------
# Repositorio
# ---------------------------------------------------------------------------

class TestRepository:
    def test_roundtrip_archivo_unico(self, tmp_profile_dir: Path) -> None:
        repo = ProfileRepository(tmp_profile_dir / "profiles.json")
        profile = _trainer().train("cluster_v", "Fam V",
                                   [DOC_VERTICAL_1, DOC_VERTICAL_2])
        path = repo.save({"cluster_v": profile})
        assert path.exists()
        loaded = repo.load()
        assert "cluster_v" in loaded
        assert loaded["cluster_v"].layout == "VERTICAL"
        assert loaded["cluster_v"].n_documents == 2

    def test_load_archivo_inexistente(self, tmp_profile_dir: Path) -> None:
        repo = ProfileRepository(tmp_profile_dir / "no.json")
        assert repo.load() == {}

    def test_archivos_individuales(self, tmp_profile_dir: Path) -> None:
        repo = ProfileRepository(tmp_profile_dir / "profiles.json")
        profile = _trainer().train("cluster_v", "Fam V",
                                   [DOC_VERTICAL_1, DOC_VERTICAL_2])
        d = repo.save_individual({"cluster_v": profile}, tmp_profile_dir / "por_familia")
        assert (d / "cluster_v.json").exists()

    def test_write_report(self, tmp_path: Path) -> None:
        repo = ProfileRepository(tmp_path / "profiles.json")
        profile = _trainer().train("cluster_v", "Fam V",
                                   [DOC_VERTICAL_1, DOC_VERTICAL_2])
        profile.validation = ProfileValidator().validate(
            profile, [DOC_VERTICAL_1, DOC_VERTICAL_2],
        )
        report = repo.write_report({"cluster_v": profile}, tmp_path / "report.md")
        text = report.read_text(encoding="utf-8")
        assert "Fam V" in text
        assert "Cobertura" in text
