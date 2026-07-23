from __future__ import annotations

import pytest
from parser_universal import _es_linea_basura, GARBAGE_PATTERNS


# ─────────────────────────────────────────────
# _es_linea_basura
# ─────────────────────────────────────────────

class TestEsLineaBasura:
    # ── URLs ──
    def test_url_http(self):
        assert _es_linea_basura("http://www.bci.cl")

    def test_url_https(self):
        assert _es_linea_basura("https://www.sii.cl")

    def test_url_www(self):
        assert _es_linea_basura("www.bci.cl")

    def test_url_no_substring(self):
        """URL dentro de nombre de cuenta NO debe filtrarse."""
        assert not _es_linea_basura("Banco www.bci.cl")

    # ── Emails ──
    def test_email(self):
        assert _es_linea_basura("contacto@empresa.cl")

    def test_email_no_substring(self):
        assert not _es_linea_basura("Email contacto@empresa.cl")

    # ── Teléfonos ──
    def test_phone_intl(self):
        assert _es_linea_basura("+56 9 1234 5678")

    def test_phone_intl_dots(self):
        assert _es_linea_basura("+56-9-1234-5678")

    def test_phone_local(self):
        assert _es_linea_basura("(2) 2123 4567")

    def test_phone_no_substring(self):
        assert not _es_linea_basura("Fono +56 9 1234 5678")

    # ── RUTs ──
    def test_rut(self):
        assert _es_linea_basura("76.123.456-7")

    def test_rut_with_rut_label(self):
        assert _es_linea_basura("RUT : 76.123.456-7")

    def test_rut_no_substring(self):
        assert not _es_linea_basura("Proveedor RUT 76.123.456-7")

    # ── Páginas ──
    def test_pagina(self):
        assert _es_linea_basura("Página 1 de 15")

    def test_pagina_simple(self):
        assert _es_linea_basura("Página 5")

    def test_folio(self):
        assert _es_linea_basura("Folio 123")

    def test_hoja(self):
        assert _es_linea_basura("Hoja 1")

    def test_pagina_no_substring(self):
        assert not _es_linea_basura("Total Página 1")

    # ── Etiquetas administrativas ──
    def test_rut_label(self):
        assert _es_linea_basura("RUT : 76.123.456-7")

    def test_domicilio(self):
        assert _es_linea_basura("Domicilio : Av. Siempre Viva 123")

    def test_comuna(self):
        assert _es_linea_basura("Comuna : Santiago")

    def test_ciudad(self):
        assert _es_linea_basura("Ciudad : Santiago")

    def test_direccion(self):
        assert _es_linea_basura("Dirección : Calle 123")

    def test_telefono_label(self):
        assert _es_linea_basura("Teléfono : +56 2 2123 4567")

    def test_fecha_emision(self):
        assert _es_linea_basura("Fecha de emisión : 15/03/2025")

    # ── Notas al pie ──
    def test_notas(self):
        assert _es_linea_basura("Notas 1 a 25")

    def test_nota_simple(self):
        assert _es_linea_basura("Nota 1")

    def test_ver_notas(self):
        assert _es_linea_basura("Ver Notas 1 a 25")

    def test_notas_no_substring(self):
        assert not _es_linea_basura("Gastos Notas 1")

    # ── Firmas ──
    def test_firma(self):
        assert _es_linea_basura("Firma del Contador")

    def test_representante(self):
        assert _es_linea_basura("Representante Legal")

    def test_contador(self):
        assert _es_linea_basura("Contador Auditor")

    def test_auditor(self):
        assert _es_linea_basura("Auditor Externo")

    # ── Firmas de auditoría ──
    def test_deloitte(self):
        assert _es_linea_basura("Deloitte Auditores Consultores Ltda.")

    def test_kpmg(self):
        assert _es_linea_basura("KPMG Auditores Consultores Ltda.")

    def test_pwc(self):
        assert _es_linea_basura("PricewaterhouseCoopers")

    def test_ernst_young(self):
        assert _es_linea_basura("Ernst Young Ltd")

    # ── Líneas decorativas ──
    def test_dashes(self):
        assert _es_linea_basura("----------------------------")

    def test_equals(self):
        assert _es_linea_basura("============================")

    def test_page_ornament(self):
        assert _es_linea_basura("  - 15 -  ")

    # ── Fechas sueltas ──
    def test_date_text(self):
        assert _es_linea_basura("31 de diciembre de 2024")

    def test_date_numeric(self):
        assert _es_linea_basura("31/12/2024")

    def test_date_no_substring(self):
        assert not _es_linea_basura("Al 31 de diciembre de 2024")

    # ── Cuentas contables que NUNCA deben filtrarse ──
    def test_caja_no_filtrar(self):
        assert not _es_linea_basura("1.01.01 Caja")

    def test_banco_no_filtrar(self):
        assert not _es_linea_basura("1.01.02 Banco Bci $ Egresos DSI")

    def test_deudores_no_filtrar(self):
        assert not _es_linea_basura("1.01.03 Deudores por Ventas")

    def test_existencias_no_filtrar(self):
        assert not _es_linea_basura("1.02.01 Existencias")

    def test_proveedores_no_filtrar(self):
        assert not _es_linea_basura("2.01.01 Proveedores")

    def test_capital_no_filtrar(self):
        assert not _es_linea_basura("3.01.01 Capital")

    def test_ingresos_no_filtrar(self):
        assert not _es_linea_basura("4.01.01 Ingresos por Ventas")

    def test_gastos_no_filtrar(self):
        assert not _es_linea_basura("5.01.01 Gastos de Administración")

    def test_total_no_filtrar(self):
        assert not _es_linea_basura("Total Activos")

    def test_resultado_no_filtrar(self):
        assert not _es_linea_basura("RESULTADO DEL EJERCICIO")

    def test_section_no_filtrar(self):
        assert not _es_linea_basura("ACTIVO")
        assert not _es_linea_basura("PASIVO")
        assert not _es_linea_basura("PATRIMONIO NETO")

    def test_account_with_numbers(self):
        assert not _es_linea_basura("Crédito BCI N° 902445")

    def test_account_with_parentheses(self):
        assert not _es_linea_basura("1.02.01 Existencias (neto)")

    def test_account_with_amounts(self):
        assert not _es_linea_basura("1.01.01 Caja 1.234.567 0 0 0")

    def test_simple_account_name(self):
        assert not _es_linea_basura("Caja")

    def test_account_code_only(self):
        assert not _es_linea_basura("1.01.01")


# ─────────────────────────────────────────────
# GARBAGE_PATTERNS
# ─────────────────────────────────────────────

class TestGarbagePatterns:
    def test_all_patterns_compile(self):
        for p in GARBAGE_PATTERNS:
            assert p is not None

    def test_no_pattern_matches_short_line(self):
        for p in GARBAGE_PATTERNS:
            assert not p.match("a"), f"Pattern {p.pattern} matched 'a'"

    def test_emails_label_substring_safe(self):
        """'Email:' como label no debe matchear 'Email contacto@x.cl' porque
        'Email contacto@x.cl' tiene espacio después de Email."""
        assert _es_linea_basura("Email : contacto@empresa.cl")
