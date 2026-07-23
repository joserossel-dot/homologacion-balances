from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

logging.disable(logging.CRITICAL)

DICT_PATHS = {
    "dicc": Path("diccionario.json"),
    "actualizado": Path("diccionario_actualizado.json"),
    "optimizado": Path("diccionario_optimizado.json"),
}


# =========================================================================
# LOADING
# =========================================================================


@pytest.mark.parametrize("name,path", DICT_PATHS.items())
def test_load_dictionary(name, path):
    from tools.dictionary_audit import load_dictionary
    entries = load_dictionary(path)
    assert isinstance(entries, list)
    assert len(entries) > 0
    assert "cuenta_original" in entries[0]
    assert "codigo_estandar" in entries[0]
    assert "fuente" in entries[0]


def test_load_all():
    from tools.dictionary_audit import load_all
    dicts = load_all()
    assert len(dicts) == 3
    assert "diccionario.json" in dicts
    assert "diccionario_actualizado.json" in dicts
    assert "diccionario_optimizado.json" in dicts


def test_load_nonexistent(tmp_path):
    from tools.dictionary_audit import load_dictionary
    fake = tmp_path / "nonexistent.json"
    with pytest.raises(FileNotFoundError):
        load_dictionary(fake)


# =========================================================================
# NORMALIZATION
# =========================================================================


def test_normalize_empty():
    from tools.dictionary_audit import normalize
    assert normalize("") == ""
    assert normalize(None) == ""


def test_normalize_basic():
    from tools.dictionary_audit import normalize
    assert normalize("Banco Bci $ Egresos DSI") == "BANCO BCI $ EGRESOS DSI"


def test_normalize_accents():
    from tools.dictionary_audit import normalize
    assert normalize("Depreciación Acumulada") == "DEPRECIACION ACUMULADA"


def test_normalize_spaces():
    from tools.dictionary_audit import normalize
    assert normalize("  Caja   General  ") == "CAJA GENERAL"


# =========================================================================
# ANALYZE FILE
# =========================================================================


def test_analyze_file():
    from tools.dictionary_audit import analyze_file
    entries = [
        {"cuenta_original": "Caja", "codigo_estandar": "AC.01", "fuente": "test"},
        {"cuenta_original": "Banco", "codigo_estandar": "AC.02", "fuente": "test"},
        {"cuenta_original": "Caja", "codigo_estandar": "AC.01", "fuente": "test"},
        {"cuenta_original": "", "codigo_estandar": "", "fuente": ""},
    ]
    result = analyze_file("test.json", entries)
    assert result["file"] == "test.json"
    assert result["total"] == 4
    assert result["unique_names"] == 3  # "Caja", "Banco", ""
    assert len(result["name_duplicates"]) == 1  # "Caja" appears twice
    assert result["empty_name"] == 1
    assert result["empty_code"] == 1


def test_analyze_file_suspicious():
    from tools.dictionary_audit import analyze_file
    entries = [
        {"cuenta_original": "12345", "codigo_estandar": "AC.01", "fuente": "t"},
        {"cuenta_original": "AB", "codigo_estandar": "AC.02", "fuente": "t"},
    ]
    result = analyze_file("susp.json", entries)
    assert len(result["suspicious_names"]) >= 1


def test_analyze_file_invalid_code():
    from tools.dictionary_audit import analyze_file
    entries = [
        {"cuenta_original": "Test", "codigo_estandar": "INVALID", "fuente": "t"},
        {"cuenta_original": "Test2", "codigo_estandar": "__EXCLUIR__", "fuente": "t"},
    ]
    result = analyze_file("codes.json", entries)
    assert len(result["invalid_codes"]) == 1
    assert result["invalid_codes"][0]["code"] == "INVALID"


def test_analyze_file_empty():
    from tools.dictionary_audit import analyze_file
    result = analyze_file("empty.json", [])
    assert result["total"] == 0
    assert result["unique_codes"] == 0


def test_analyze_file_unique_codes():
    from tools.dictionary_audit import analyze_file
    entries = [
        {"cuenta_original": "A", "codigo_estandar": "AC.01", "fuente": "t"},
        {"cuenta_original": "B", "codigo_estandar": "PC.02", "fuente": "t"},
        {"cuenta_original": "C", "codigo_estandar": "AC.01", "fuente": "t"},
    ]
    result = analyze_file("uniq.json", entries)
    assert result["unique_codes"] == 2


# =========================================================================
# COMPARE DICTIONARIES
# =========================================================================


def test_compare_dictionaries():
    from tools.dictionary_audit import compare_dictionaries
    dicts = {
        "A.json": [
            {"cuenta_original": "Caja", "codigo_estandar": "AC.01", "fuente": "t"},
            {"cuenta_original": "Banco", "codigo_estandar": "AC.02", "fuente": "t"},
            {"cuenta_original": "Prov", "codigo_estandar": "PC.01", "fuente": "t"},
        ],
        "B.json": [
            {"cuenta_original": "Caja", "codigo_estandar": "AC.01", "fuente": "t"},
            {"cuenta_original": "Banco", "codigo_estandar": "AC.02", "fuente": "t"},
        ],
        "C.json": [
            {"cuenta_original": "Caja", "codigo_estandar": "AC.01", "fuente": "t"},
        ],
    }
    comp = compare_dictionaries(dicts)
    # Keys are hardcoded: first file → only_in_diccionario_json, etc.
    assert comp["common_in_all"] == 1
    assert comp["only_in_diccionario_json"] == 1  # "Prov" only in A.json (first file)
    assert comp["only_in_actualizado_json"] == 0
    assert comp["only_in_optimizado_json"] == 0
    assert comp["same_name_diff_code_total"] == 0


def test_compare_dictionaries_conflict():
    from tools.dictionary_audit import compare_dictionaries
    dicts = {
        "X.json": [
            {"cuenta_original": "Caja", "codigo_estandar": "AC.01", "fuente": "t"},
        ],
        "Y.json": [
            {"cuenta_original": "Caja", "codigo_estandar": "PC.01", "fuente": "t"},
        ],
        "Z.json": [
            {"cuenta_original": "Caja", "codigo_estandar": "AC.01", "fuente": "t"},
        ],
    }
    comp = compare_dictionaries(dicts)
    assert comp["same_name_diff_code_total"] >= 1
    assert len(comp["same_name_diff_code_all"]) > 0


# =========================================================================
# BUILD INVENTORY
# =========================================================================


def test_build_inventory_reference():
    from tools.dictionary_audit import build_inventory_reference
    inventory = build_inventory_reference()
    assert len(inventory) >= 12
    required_fields = {"archivo", "linea", "funcion", "proposito", "modo", "archivo_dicc"}
    for ref in inventory:
        assert required_fields.issubset(ref.keys())


def test_inventory_has_write_refs():
    from tools.dictionary_audit import build_inventory_reference
    inventory = build_inventory_reference()
    write_refs = [r for r in inventory if r["modo"] == "escritura"]
    assert len(write_refs) >= 3


# =========================================================================
# REPORT GENERATION
# =========================================================================


def test_generate_audit_report(tmp_path):
    from tools.dictionary_audit import (
        analyze_file,
        compare_dictionaries,
        build_inventory_reference,
        generate_audit_report,
    )
    entries = [{"cuenta_original": "Caja", "codigo_estandar": "AC.01", "fuente": "t"}]
    file_results = {
        "diccionario.json": analyze_file("dicc.json", entries),
        "diccionario_actualizado.json": analyze_file("act.json", entries),
        "diccionario_optimizado.json": analyze_file("opt.json", entries),
    }
    dicts_data = {
        "diccionario.json": entries,
        "diccionario_actualizado.json": entries,
        "diccionario_optimizado.json": entries,
    }
    comparison = compare_dictionaries(dicts_data)
    inventory = build_inventory_reference()
    path = generate_audit_report(file_results, comparison, inventory, tmp_path)
    assert path.exists()
    content = path.read_text()
    assert "Resumen Ejecutivo" in content
    assert "Comparación Cruzada" in content
    assert "Inventario de Referencias" in content


def test_generate_statistics_json(tmp_path):
    from tools.dictionary_audit import (
        analyze_file,
        compare_dictionaries,
        generate_statistics_json,
    )
    entries_a = [{"cuenta_original": "Caja", "codigo_estandar": "AC.01", "fuente": "t"}]
    entries_b = [{"cuenta_original": "Banco", "codigo_estandar": "AC.02", "fuente": "t"}]
    entries_c = [{"cuenta_original": "Caja", "codigo_estandar": "AC.01", "fuente": "t"}]
    file_results = {
        "dicc.json": analyze_file("dicc.json", entries_a),
    }
    comparison = compare_dictionaries({
        "dicc.json": entries_a,
        "B.json": entries_b,
        "C.json": entries_c,
    })
    path = generate_statistics_json(file_results, comparison, tmp_path)
    assert path.exists()
    data = json.loads(path.read_text())
    assert "files" in data
    assert "comparison" in data


def test_generate_duplicates_xlsx(tmp_path):
    from tools.dictionary_audit import analyze_file, generate_duplicates_xlsx
    entries = [
        {"cuenta_original": "Caja", "codigo_estandar": "AC.01", "fuente": "t"},
        {"cuenta_original": "", "codigo_estandar": "", "fuente": ""},
    ]
    file_results = {"dicc.json": analyze_file("dicc.json", entries)}
    path = generate_duplicates_xlsx(file_results, tmp_path)
    assert path is not None and path.exists()


def test_generate_conflicts_xlsx(tmp_path):
    from tools.dictionary_audit import (
        _generate_conflicts_xlsx_with_data,
        analyze_file,
        compare_dictionaries,
    )
    entries_a = [{"cuenta_original": "Caja", "codigo_estandar": "AC.01", "fuente": "t"}]
    entries_b = [{"cuenta_original": "Caja", "codigo_estandar": "PC.01", "fuente": "t"}]
    entries_c = [{"cuenta_original": "Caja", "codigo_estandar": "AC.01", "fuente": "t"}]
    file_results = {
        "A.json": analyze_file("A.json", entries_a),
        "B.json": analyze_file("B.json", entries_b),
        "C.json": analyze_file("C.json", entries_c),
    }
    comparison = compare_dictionaries({
        "A.json": entries_a, "B.json": entries_b, "C.json": entries_c,
    })
    path = _generate_conflicts_xlsx_with_data(file_results, comparison, tmp_path)
    assert path is not None and path.exists()


# =========================================================================
# REAL DATA INTEGRATION
# =========================================================================


def test_real_data_analyze_all():
    from tools.dictionary_audit import load_all, analyze_file
    dicts = load_all()
    for name, entries in dicts.items():
        result = analyze_file(name, entries)
        assert result["total"] > 0
        assert result["empty_name"] == 0
        assert result["empty_code"] == 0


def test_real_data_comparison():
    from tools.dictionary_audit import load_all, compare_dictionaries
    dicts = load_all()
    comp = compare_dictionaries(dicts)
    assert comp["common_in_all"] > 0
    assert comp["same_name_diff_code_total"] == 0


def test_real_data_no_internal_duplicates():
    from tools.dictionary_audit import load_all, analyze_file
    dicts = load_all()
    for name, entries in dicts.items():
        result = analyze_file(name, entries)
        assert len(result["name_duplicates"]) == 0, (
            f"{name} tiene duplicados internos"
        )


# =========================================================================
# RUN AUDIT
# =========================================================================


def test_run_audit(tmp_path):
    from tools.dictionary_audit import run_audit
    result = run_audit(output_dir=tmp_path)
    assert result["status"] == "ok"
    assert "audit_md" in result["paths"]
    assert result["paths"]["audit_md"].exists()
    assert "statistics_json" in result["paths"]
    assert "file_results" in result
    assert "comparison" in result
    assert "inventory" in result


def test_print_summary(capsys):
    from tools.dictionary_audit import print_summary, run_audit
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        result = run_audit(output_dir=Path(tmp))
        print_summary(result)
        captured = capsys.readouterr()
        assert "AUDITORÍA" in captured.out
        assert "diccionario.json" in captured.out
