"""Tests para AccountTypeResolver.

NO clasifica. NO usa regex. NO usa fuzzy matching. NO usa CMCC.
Solo deriva AccountType desde origen_columna + layout + reglas contables.
"""

from parsers.account_type_resolver import AccountTypeResolver, AccountType
from parser_universal import OrigenColumna


class TestDirectMapping:
    """Casos donde el mapeo origen_columna → AccountType es directo (1:1)."""

    def setup_method(self):
        self.r = AccountTypeResolver()

    def test_activo_directo(self):
        res = self.r.resolve(OrigenColumna.ACTIVO)
        assert res.account_type == AccountType.ACTIVO
        assert res.confidence == 1.0
        assert res.method == "origen_columna"

    def test_perdida_directo(self):
        res = self.r.resolve(OrigenColumna.PERDIDA)
        assert res.account_type == AccountType.PERDIDA
        assert res.confidence == 1.0

    def test_ganancia_directo(self):
        res = self.r.resolve(OrigenColumna.GANANCIA)
        assert res.account_type == AccountType.GANANCIA
        assert res.confidence == 1.0

    def test_allowed_types_unambiguous(self):
        res = self.r.resolve(OrigenColumna.ACTIVO)
        assert res.allowed_types == [AccountType.ACTIVO]

    def test_allowed_types_pasivo_includes_patrimonio(self):
        res = self.r.resolve(OrigenColumna.PASIVO)
        assert AccountType.PASIVO in res.allowed_types
        assert AccountType.PATRIMONIO in res.allowed_types

    def test_allowed_types_deudor_includes_activo_perdida(self):
        res = self.r.resolve(OrigenColumna.DEUDOR)
        assert AccountType.ACTIVO in res.allowed_types
        assert AccountType.PERDIDA in res.allowed_types

    def test_allowed_types_acreedor_includes_pasivo_ganancia(self):
        res = self.r.resolve(OrigenColumna.ACREEDOR)
        assert AccountType.PASIVO in res.allowed_types
        assert AccountType.GANANCIA in res.allowed_types

    def test_allowed_types_desconocido_permits_all(self):
        res = self.r.resolve(OrigenColumna.DESCONOCIDO)
        assert len(res.allowed_types) == 5
        assert AccountType.ACTIVO in res.allowed_types
        assert AccountType.GANANCIA in res.allowed_types


class TestPasivoAmbiguo:
    """Resolución de PASIVO → PASIVO o PATRIMONIO."""

    def setup_method(self):
        self.r = AccountTypeResolver()

    def test_pasivo_sin_layout_default(self):
        res = self.r.resolve(OrigenColumna.PASIVO)
        assert res.account_type == AccountType.PASIVO
        assert res.confidence == 0.9

    def test_pasivo_layout_sin_patrimonio(self):
        res = self.r.resolve(OrigenColumna.PASIVO, layout_columns=["activo", "pasivo", "perdida", "ganancia"])
        assert res.account_type == AccountType.PASIVO

    def test_pasivo_layout_patrimonio_sin_codigo(self):
        res = self.r.resolve(OrigenColumna.PASIVO, layout_columns=["activo", "patrimonio", "perdida", "ganancia"])
        assert res.account_type == AccountType.PASIVO

    def test_pasivo_layout_patrimonio_codigo_pat(self):
        res = self.r.resolve(OrigenColumna.PASIVO, codigo="PAT.01", layout_columns=["activo", "patrimonio", "perdida"])
        assert res.account_type == AccountType.PATRIMONIO
        assert res.confidence == 0.95
        assert res.method == "layout+code_prefix"

    def test_pasivo_layout_patrimonio_codigo_ac(self):
        """Código AC en columna pasivo con layout patrimonio → sigue siendo PASIVO."""
        res = self.r.resolve(OrigenColumna.PASIVO, codigo="AC.01", layout_columns=["activo", "patrimonio", "perdida"])
        assert res.account_type == AccountType.PASIVO

    def test_pasivo_con_pat_en_layout_sin_patrimonio_col(self):
        """Patrimonio NO está en layout_columns → no hay evidencia."""
        res = self.r.resolve(OrigenColumna.PASIVO, codigo="PAT.01", layout_columns=["activo", "pasivo", "perdida", "ganancia"])
        assert res.account_type == AccountType.PASIVO


class TestDeudorAmbiguo:
    """Resolución de DEUDOR → ACTIVO o PERDIDA."""

    def setup_method(self):
        self.r = AccountTypeResolver()

    def test_deudor_default_activo(self):
        res = self.r.resolve(OrigenColumna.DEUDOR)
        assert res.account_type == AccountType.ACTIVO
        assert res.confidence == 0.60

    def test_deudor_codigo_ac(self):
        res = self.r.resolve(OrigenColumna.DEUDOR, codigo="AC.03")
        assert res.account_type == AccountType.ACTIVO
        assert res.confidence == 0.85

    def test_deudor_codigo_anc(self):
        res = self.r.resolve(OrigenColumna.DEUDOR, codigo="ANC.01")
        assert res.account_type == AccountType.ACTIVO

    def test_deudor_codigo_er(self):
        res = self.r.resolve(OrigenColumna.DEUDOR, codigo="ER.09")
        assert res.account_type == AccountType.PERDIDA
        assert res.confidence == 0.80
        assert "naturaleza deudora" in res.note

    def test_deudor_codigo_pc(self):
        """PC en columna deudora → se resuelve como PASIVO."""
        res = self.r.resolve(OrigenColumna.DEUDOR, codigo="PC.02")
        assert res.account_type == AccountType.PASIVO
        assert res.confidence == 0.85


class TestAcreedorAmbiguo:
    """Resolución de ACREEDOR → PASIVO o GANANCIA."""

    def setup_method(self):
        self.r = AccountTypeResolver()

    def test_acreedor_default_pasivo(self):
        res = self.r.resolve(OrigenColumna.ACREEDOR)
        assert res.account_type == AccountType.PASIVO
        assert res.confidence == 0.60

    def test_acreedor_codigo_pc(self):
        res = self.r.resolve(OrigenColumna.ACREEDOR, codigo="PC.01")
        assert res.account_type == AccountType.PASIVO
        assert res.confidence == 0.85

    def test_acreedor_codigo_pat(self):
        res = self.r.resolve(OrigenColumna.ACREEDOR, codigo="PAT.02")
        assert res.account_type == AccountType.PATRIMONIO

    def test_acreedor_codigo_er(self):
        res = self.r.resolve(OrigenColumna.ACREEDOR, codigo="ER.01")
        assert res.account_type == AccountType.GANANCIA
        assert res.confidence == 0.80
        assert "naturaleza acreedora" in res.note

    def test_acreedor_codigo_ac(self):
        """AC en columna acreedora → no se resuelve, cae a PASIVO."""
        res = self.r.resolve(OrigenColumna.ACREEDOR, codigo="AC.01")
        assert res.account_type == AccountType.PASIVO


class TestDesconocido:
    """Resolución de DESCONOCIDO."""

    def setup_method(self):
        self.r = AccountTypeResolver()

    def test_desconocido_sin_codigo(self):
        res = self.r.resolve(OrigenColumna.DESCONOCIDO)
        assert res.account_type == AccountType.DESCONOCIDO
        assert res.confidence == 0.50

    def test_desconocido_codigo_ac(self):
        res = self.r.resolve(OrigenColumna.DESCONOCIDO, codigo="AC.01")
        assert res.account_type == AccountType.ACTIVO
        assert res.confidence == 0.70

    def test_desconocido_codigo_pat(self):
        res = self.r.resolve(OrigenColumna.DESCONOCIDO, codigo="PAT.02")
        assert res.account_type == AccountType.PATRIMONIO

    def test_desconocido_codigo_er(self):
        """ER sin columna → DESCONOCIDO (code_prefix no mapea ER)."""
        res = self.r.resolve(OrigenColumna.DESCONOCIDO, codigo="ER.05")
        assert res.account_type == AccountType.DESCONOCIDO


class TestCodePrefix:
    """Reglas de prefijo de código."""

    def setup_method(self):
        self.r = AccountTypeResolver()

    def test_prefix_anc_before_ac(self):
        """ANC debe matchear antes que AC."""
        res = self.r.resolve(OrigenColumna.DEUDOR, codigo="ANC.01")
        assert res.account_type == AccountType.ACTIVO

    def test_prefix_pnc_before_pc(self):
        """PNC debe matchear antes que PC."""
        res = self.r.resolve(OrigenColumna.ACREEDOR, codigo="PNC.03")
        assert res.account_type == AccountType.PASIVO

    def test_prefix_pat(self):
        res = self.r.resolve(OrigenColumna.ACREEDOR, codigo="PAT.01")
        assert res.account_type == AccountType.PATRIMONIO

    def test_codigo_none(self):
        res = self.r.resolve(OrigenColumna.DEUDOR, codigo=None)
        assert res.account_type == AccountType.ACTIVO

    def test_codigo_vacio(self):
        res = self.r.resolve(OrigenColumna.DEUDOR, codigo="")
        assert res.account_type == AccountType.ACTIVO


class TestIntegrationParserUniversal:
    """Verifica que parser_universal importa y usa el resolver con flag."""

    def test_resolver_import_lazy(self):
        """El import lazy del resolver funciona."""
        import parser_universal as pu
        assert hasattr(pu, 'ENABLE_ACCOUNT_TYPE_RESOLVER')
        assert pu.ENABLE_ACCOUNT_TYPE_RESOLVER is False

    def test_cuenta_raw_tiene_tipo_cuenta(self):
        """CuentaRaw tiene el nuevo campo opcional."""
        from parser_universal import CuentaRaw
        c = CuentaRaw(linea=0, codigo=None, nombre="Test", monto=None)
        assert hasattr(c, 'tipo_cuenta')
        assert c.tipo_cuenta is None

    def test_enable_flag_cambia_comportamiento(self):
        """Al activar el flag, las cuentas reciben tipo_cuenta."""
        import parser_universal as pu
        original_flag = pu.ENABLE_ACCOUNT_TYPE_RESOLVER
        pu.ENABLE_ACCOUNT_TYPE_RESOLVER = True
        try:
            from pathlib import Path
            pdfs = sorted(Path("edge_cases").glob("*.pdf"))
            if not pdfs:
                pdfs = sorted(Path("datasets/edge_cases").glob("*.pdf"))
            if pdfs:
                parser = pu.ParserPDF()
                r = parser.parsear(pdfs[0])
                resueltos = sum(1 for c in r.cuentas if c.tipo_cuenta is not None)
                assert resueltos > 0, f"Ninguna cuenta resuelta en {pdfs[0].name}"
                cuenta_con_tipo = next((c for c in r.cuentas if c.tipo_cuenta), None)
                if cuenta_con_tipo:
                    assert cuenta_con_tipo.tipo_cuenta in ("ACTIVO", "PASIVO", "PATRIMONIO", "PERDIDA", "GANANCIA", "DESCONOCIDO")
        finally:
            pu.ENABLE_ACCOUNT_TYPE_RESOLVER = original_flag
