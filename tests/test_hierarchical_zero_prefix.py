"""Trailing zeros in a real group code must not absorb a sibling group."""
import copy

from parser_universal import (
    FormatoCodigo, marcar_subtotales_jerarquicos, parsear_linea,
)


def accounts(lines):
    return [parsear_linea(line, i, FormatoCodigo.COMPACTO, ".")
            for i, line in enumerate(lines)]


def test_nested_explicit_groups_preserve_zero_before_sibling():
    rows = accounts([
        "3 - GASTOS 150 0 150 0 0 0 150 0",
        "32 - GASTOS EN BIENES Y SERVICIOS DE 150 0 150 0 0 0 150 0",
        "3210 - SERVICIOS TECNICOS Y 100 0 100 0 0 0 100 0",
        "3210002 CAPACITACION 40 0 40 0 0 0 40 0",
        "3210003 SERVICIOS INFORMATICOS 60 0 60 0 0 0 60 0",
        "3211 - OTROS GASTOS 50 0 50 0 0 0 50 0",
        "3211001 GASTOS MENORES 50 0 50 0 0 0 50 0",
    ])
    original = copy.deepcopy(rows)
    assert marcar_subtotales_jerarquicos(rows) == 4
    assert [r.es_total for r in rows] == [True, True, True, False, False, True, False]
    assert [r.montos_columnas for r in rows] == [r.montos_columnas for r in original]
    assert [r.codigo for r in rows] == [r.codigo for r in original]
    assert [r.nombre for r in rows] == [r.nombre for r in original]


def test_literal_descendants_cannot_be_replaced_by_sibling_to_force_sum():
    rows = accounts([
        "3210 - SERVICIOS TECNICOS Y 150 0 150 0 0 0 150 0",
        "3210002 CAPACITACION 100 0 100 0 0 0 100 0",
        "3211001 GASTOS MENORES 50 0 50 0 0 0 50 0",
    ])
    assert marcar_subtotales_jerarquicos(rows) == 0
    assert all(not row.es_total for row in rows)


def test_numeric_name_with_no_descendants_stays_operating_account():
    rows = accounts([
        "3210 - SERVICIOS TECNICOS Y 100 0 100 0 0 0 100 0",
        "4110001 OTRA CUENTA 100 0 100 0 0 0 100 0",
    ])
    assert marcar_subtotales_jerarquicos(rows) == 0


def test_padded_group_without_literal_children_remains_supported():
    rows = accounts([
        "32000 GRUPO 100 0 100 0 0 0 100 0",
        "3210001 CAPACITACION 40 0 40 0 0 0 40 0",
        "3220001 SERVICIOS 60 0 60 0 0 0 60 0",
    ])
    assert marcar_subtotales_jerarquicos(rows) == 1
    assert rows[0].es_total
    assert all(not row.es_total for row in rows[1:])
