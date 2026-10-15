from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import scripts.certify_local_corpus as corpus_script
from parser_universal import CertificacionExtraccion, CuentaRaw, OrigenColumna
from pipeline.cmcc_classifier import CMCCClassifier
from scripts.certify_local_corpus import (
    PROJECT_ROOT,
    _classify,
    _load_closing_year_manifest,
    _project_runtime_context,
)


class _PipelineForClosingYear:
    """Stub mínimo para probar el espejo de clasificación del lote."""

    def __init__(self) -> None:
        self.result_year_calls: list[tuple[str, str, int | None]] = []
        self.account_types: list[str | None] = []
        self._rule_processor = SimpleNamespace(
            aplicar=lambda **_: SimpleNamespace(
                aplica=False,
                codigo_final="",
                requiere_revision=False,
            ),
        )

    def _classification_for_explicit_result_year(
            self,
            account_name: str,
            account_code: str,
            closing_year: int | None,
    ) -> dict | None:
        self.result_year_calls.append((account_name, account_code, closing_year))
        if closing_year is None:
            return None
        return {
            "standard_code": "PAT.03",
            "confidence": 0.90,
            "method": "historical_result_year",
            "reason": "fixture",
        }

    @staticmethod
    def _classify_debit_balance_financial_liability(_: str) -> None:
        return None

    def _classify_account(
            self,
            _: str,
            __: str,
            account_tipo: str | None = None,
    ) -> dict:
        self.account_types.append(account_tipo)
        return {
            "standard_code": "AC.08",
            "confidence": 0.55,
            "method": "origin_fallback",
            "reason": "fixture",
        }

    @staticmethod
    def _classify_credit_balance_depreciation(*_) -> None:
        return None


def _historical_result_account() -> CuentaRaw:
    return CuentaRaw(
        linea=1,
        codigo="2402-01",
        nombre="RESULTADO AÑO 2022",
        monto=100,
        origen_columna=OrigenColumna.ACTIVO,
    )


def test_manifest_by_id_exposes_confirmed_year_without_filename_inference(tmp_path):
    manifest_path = tmp_path / "closing-years.json"
    manifest_path.write_text(
        json.dumps({
            "by_id": {
                "documento-prueba-001": {
                    "basename": "balance-general.pdf",
                    "closing_year": 2024,
                },
            },
        }),
        encoding="utf-8",
    )

    manifest = _load_closing_year_manifest(manifest_path)

    assert manifest["balance-general.pdf"].year == 2024
    assert (
        manifest["balance-general.pdf"].source
        == "manifest:id:documento-prueba-001"
    )
    assert _load_closing_year_manifest(None) == {}


def test_corpus_classification_uses_confirmed_year_for_historical_result():
    pipeline = _PipelineForClosingYear()

    result = _classify(
        [_historical_result_account()],
        pipeline,
        CertificacionExtraccion(estado="certificada"),
        closing_year=2024,
        closing_year_source="manifest:basename",
    )

    row = result["rows"][0]
    assert pipeline.result_year_calls == [
        ("RESULTADO AÑO 2022", "2402-01", 2024),
    ]
    assert row["source_account_code"] == "2402-01"
    assert row["origen_columna"] == "activo"
    assert row["origen_columna_efectiva"] == "patrimonio"
    assert row["confirmed_closing_year"] == 2024
    assert row["confirmed_closing_year_source"] == "manifest:basename"
    assert row["code"] == "PAT.03"
    assert row["method"] == "historical_result_year"
    assert row["review"] is False


def test_corpus_classification_without_confirmed_year_stays_conservative():
    pipeline = _PipelineForClosingYear()

    result = _classify(
        [_historical_result_account()],
        pipeline,
        CertificacionExtraccion(estado="certificada"),
    )

    row = result["rows"][0]
    assert pipeline.result_year_calls == []
    assert pipeline.account_types == ["ACTIVO"]
    assert row["confirmed_closing_year"] is None
    assert row["code"] == "AC.08"
    assert row["method"] == "origin_fallback"
    assert row["review"] is True


def test_runtime_context_loads_cmcc_when_invoked_outside_project(tmp_path, monkeypatch):
    caller_directory = tmp_path / "external-caller"
    caller_directory.mkdir()
    monkeypatch.chdir(caller_directory)

    with _project_runtime_context() as runtime_directory:
        assert Path.cwd() == PROJECT_ROOT
        assert PROJECT_ROOT not in runtime_directory.parents
        assert CMCCClassifier().concepts

    assert Path.cwd() == caller_directory


def test_main_resolves_relative_cli_paths_before_runtime_context(tmp_path, monkeypatch):
    caller_directory = tmp_path / "external-caller"
    input_directory = caller_directory / "corpus"
    caller_directory.mkdir()
    input_directory.mkdir()
    (caller_directory / "closing-years.json").write_text(
        json.dumps({"by_basename": {}}), encoding="utf-8",
    )
    captured: dict[str, Path] = {}

    class _Pipeline:
        def __init__(self, *, db_path: Path) -> None:
            captured["cwd"] = Path.cwd()
            captured["db_path"] = db_path

    monkeypatch.chdir(caller_directory)
    monkeypatch.setattr(corpus_script, "HomologationPipeline", _Pipeline)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "certify_local_corpus.py",
            "corpus",
            "--output",
            "reports/certification.json",
            "--closing-year-manifest",
            "closing-years.json",
        ],
    )

    assert corpus_script.main() == 0
    assert captured["cwd"] == PROJECT_ROOT
    assert PROJECT_ROOT not in captured["db_path"].parents
    assert (caller_directory / "reports").is_dir()
    assert Path.cwd() == caller_directory
