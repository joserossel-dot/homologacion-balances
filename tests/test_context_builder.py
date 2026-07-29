"""Tests para ContextBuilder — jerarquía, navegación y metadata."""
from __future__ import annotations

from pathlib import Path

import pytest

from context import AccountContext, ContextBuilder
from parser_universal import CuentaRaw, FormatoCodigo

BASE_DIR = Path(__file__).resolve().parent.parent


# ─────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────

@pytest.fixture
def cuentas_punto() -> list[CuentaRaw]:
    return [
        CuentaRaw(linea=1, codigo='1', nombre='ACTIVO', monto=None),
        CuentaRaw(linea=2, codigo='1.1', nombre='ACTIVO CORRIENTE', monto=None),
        CuentaRaw(linea=3, codigo='1.1.01', nombre='CAJA', monto=1000.0),
        CuentaRaw(linea=4, codigo='1.1.02', nombre='BANCO', monto=2000.0),
        CuentaRaw(linea=5, codigo='1.2', nombre='ACTIVO NO CORRIENTE', monto=None),
        CuentaRaw(linea=6, codigo='1.2.01', nombre='PROPIEDAD', monto=5000.0),
        CuentaRaw(linea=7, codigo='2', nombre='PASIVO', monto=None),
        CuentaRaw(linea=8, codigo='2.1', nombre='PASIVO CORRIENTE', monto=None),
        CuentaRaw(linea=9, codigo='2.1.01', nombre='DEUDAS', monto=300.0),
    ]


@pytest.fixture
def cuentas_guion() -> list[CuentaRaw]:
    return [
        CuentaRaw(linea=1, codigo='1-1', nombre='ACTIVO CORRIENTE', monto=None),
        CuentaRaw(linea=2, codigo='1-1-01', nombre='CAJA', monto=1000.0),
        CuentaRaw(linea=3, codigo='1-1-02', nombre='BANCO', monto=2000.0),
        CuentaRaw(linea=4, codigo='1-2', nombre='ACTIVO NO CORRIENTE', monto=None),
    ]


@pytest.fixture
def cuentas_sin_codigo() -> list[CuentaRaw]:
    return [
        CuentaRaw(linea=1, codigo=None, nombre='ACTIVO', monto=None),
        CuentaRaw(linea=2, codigo=None, nombre='CAJA', monto=1000.0),
        CuentaRaw(linea=3, codigo=None, nombre='BANCO', monto=2000.0),
    ]


@pytest.fixture
def cuentas_compacto() -> list[CuentaRaw]:
    return [
        CuentaRaw(linea=1, codigo='110000', nombre='ACTIVO', monto=None),
        CuentaRaw(linea=2, codigo='110100', nombre='ACTIVO CORRIENTE', monto=None),
        CuentaRaw(linea=3, codigo='110101', nombre='CAJA', monto=1000.0),
        CuentaRaw(linea=4, codigo='110102', nombre='BANCO', monto=2000.0),
    ]


# ─────────────────────────────────────────────────────────────────────
# Tests de jerarquía (formato PUNTO)
# ─────────────────────────────────────────────────────────────────────

class TestJerarquiaPunto:
    def test_cantidad_contextos(self, cuentas_punto):
        contexts = ContextBuilder().build(cuentas_punto, code_format=FormatoCodigo.PUNTO)
        assert len(contexts) == 9

    def test_niveles_jerarquia(self, cuentas_punto):
        contexts = ContextBuilder().build(cuentas_punto, code_format=FormatoCodigo.PUNTO)
        niveles = {ctx.raw.codigo: ctx.hierarchy_level for ctx in contexts}
        assert niveles['1'] == 1
        assert niveles['1.1'] == 2
        assert niveles['1.1.01'] == 3
        assert niveles['1.1.02'] == 3
        assert niveles['2'] == 1

    def test_padre_correcto(self, cuentas_punto):
        contexts = ContextBuilder().build(cuentas_punto, code_format=FormatoCodigo.PUNTO)
        mapa = {ctx.raw.codigo: ctx for ctx in contexts}
        assert mapa['1.1'].parent is mapa['1']
        assert mapa['1.1.01'].parent is mapa['1.1']
        assert mapa['1.1.02'].parent is mapa['1.1']
        assert mapa['1.2'].parent is mapa['1']
        assert mapa['2.1'].parent is mapa['2']

    def test_raiz_sin_padre(self, cuentas_punto):
        contexts = ContextBuilder().build(cuentas_punto, code_format=FormatoCodigo.PUNTO)
        mapa = {ctx.raw.codigo: ctx for ctx in contexts}
        assert mapa['1'].parent is None
        assert mapa['2'].parent is None

    def test_hijos_correctos(self, cuentas_punto):
        contexts = ContextBuilder().build(cuentas_punto, code_format=FormatoCodigo.PUNTO)
        mapa = {ctx.raw.codigo: ctx for ctx in contexts}
        assert [c.raw.codigo for c in mapa['1'].children] == ['1.1', '1.2']
        assert [c.raw.codigo for c in mapa['1.1'].children] == ['1.1.01', '1.1.02']
        assert [c.raw.codigo for c in mapa['1.1.01'].children] == []

    def test_hermanos_correctos(self, cuentas_punto):
        contexts = ContextBuilder().build(cuentas_punto, code_format=FormatoCodigo.PUNTO)
        mapa = {ctx.raw.codigo: ctx for ctx in contexts}
        assert {s.raw.codigo for s in mapa['1'].siblings} == {'2'}
        assert {s.raw.codigo for s in mapa['1.1'].siblings} == {'1.2'}
        assert {s.raw.codigo for s in mapa['1.1.01'].siblings} == {'1.1.02'}
        assert {s.raw.codigo for s in mapa['1.1.02'].siblings} == {'1.1.01'}

    def test_hermanos_sin_padre_compartido(self, cuentas_punto):
        contexts = ContextBuilder().build(cuentas_punto, code_format=FormatoCodigo.PUNTO)
        mapa = {ctx.raw.codigo: ctx for ctx in contexts}
        # 1.2.01 y 2.1.01 tienen padres distintos → no son hermanos
        c_1_2_01 = mapa['1.2.01']
        c_2_1_01 = mapa['2.1.01']
        assert c_1_2_01 not in c_2_1_01.siblings

    def test_secciones(self, cuentas_punto):
        contexts = ContextBuilder().build(cuentas_punto, code_format=FormatoCodigo.PUNTO)
        mapa = {ctx.raw.codigo: ctx for ctx in contexts}
        assert mapa['1'].section == 'activo'
        assert mapa['1.1'].section == 'activo'
        assert mapa['2'].section == 'pasivo'
        assert mapa['2.1'].section == 'pasivo'

    def test_path_jerarquico(self, cuentas_punto):
        contexts = ContextBuilder().build(cuentas_punto, code_format=FormatoCodigo.PUNTO)
        mapa = {ctx.raw.codigo: ctx for ctx in contexts}
        assert mapa['1'].path == '1'
        assert mapa['1.1'].path == '1/1.1'
        assert mapa['1.1.01'].path == '1/1.1/1.1.01'
        assert mapa['1.2'].path == '1/1.2'
        assert mapa['2'].path == '2'


# ─────────────────────────────────────────────────────────────────────
# Tests de jerarquía (formato GUION)
# ─────────────────────────────────────────────────────────────────────

class TestJerarquiaGuion:
    def test_padre_hijos(self, cuentas_guion):
        contexts = ContextBuilder().build(cuentas_guion, code_format=FormatoCodigo.GUION)
        mapa = {ctx.raw.codigo: ctx for ctx in contexts}
        assert mapa['1-1-01'].parent is mapa['1-1']
        assert mapa['1-1-02'].parent is mapa['1-1']
        assert [c.raw.codigo for c in mapa['1-1'].children] == ['1-1-01', '1-1-02']

    def test_hermanos_guion(self, cuentas_guion):
        contexts = ContextBuilder().build(cuentas_guion, code_format=FormatoCodigo.GUION)
        mapa = {ctx.raw.codigo: ctx for ctx in contexts}
        assert {s.raw.codigo for s in mapa['1-1-01'].siblings} == {'1-1-02'}


# ─────────────────────────────────────────────────────────────────────
# Tests sin código
# ─────────────────────────────────────────────────────────────────────

class TestSinCodigo:
    def test_sin_codigo_no_rompe(self, cuentas_sin_codigo):
        contexts = ContextBuilder().build(cuentas_sin_codigo)
        assert len(contexts) == 3

    def test_sin_codigo_niveles_cero(self, cuentas_sin_codigo):
        contexts = ContextBuilder().build(cuentas_sin_codigo)
        for ctx in contexts:
            assert ctx.hierarchy_level == 0

    def test_sin_codigo_sin_padre(self, cuentas_sin_codigo):
        contexts = ContextBuilder().build(cuentas_sin_codigo)
        for ctx in contexts:
            assert ctx.parent is None

    def test_sin_codigo_deteccion_formato(self, cuentas_sin_codigo):
        contexts = ContextBuilder().build(cuentas_sin_codigo)
        assert len(contexts) == 3


# ─────────────────────────────────────────────────────────────────────
# Tests navegación secuencial
# ─────────────────────────────────────────────────────────────────────

class TestNavegacion:
    def test_anterior_siguiente(self, cuentas_punto):
        contexts = ContextBuilder().build(cuentas_punto, code_format=FormatoCodigo.PUNTO)
        for i, ctx in enumerate(contexts):
            if i > 0:
                assert ctx.previous_account is contexts[i - 1]
            else:
                assert ctx.previous_account is None
            if i < len(contexts) - 1:
                assert ctx.next_account is contexts[i + 1]
            else:
                assert ctx.next_account is None

    def test_posicion_correcta(self, cuentas_punto):
        contexts = ContextBuilder().build(cuentas_punto, code_format=FormatoCodigo.PUNTO)
        for i, ctx in enumerate(contexts):
            assert ctx.position == i


# ─────────────────────────────────────────────────────────────────────
# Tests metadata
# ─────────────────────────────────────────────────────────────────────

class TestMetadata:
    def test_layout_en_contexto(self, cuentas_punto):
        layout = ['activo', 'pasivo', 'perdida', 'ganancia']
        contexts = ContextBuilder().build(
            cuentas_punto, code_format=FormatoCodigo.PUNTO, layout=layout,
        )
        for ctx in contexts:
            assert ctx.layout == layout

    def test_account_type_en_contexto(self, cuentas_punto):
        types = {'1': 'activo', '1.1': 'activo', '2': 'pasivo'}
        contexts = ContextBuilder().build(
            cuentas_punto, code_format=FormatoCodigo.PUNTO, account_types=types,
        )
        mapa = {ctx.raw.codigo: ctx for ctx in contexts}
        assert mapa['1'].account_type == 'activo'
        assert mapa['2'].account_type == 'pasivo'
        assert mapa['1.1.01'].account_type is None  # not in map

    def test_confianza(self, cuentas_punto):
        contexts = ContextBuilder().build(cuentas_punto, code_format=FormatoCodigo.PUNTO)
        for ctx in contexts:
            assert ctx.confidence == ctx.raw.confianza_extraccion

    def test_account_context_repr(self, cuentas_punto):
        contexts = ContextBuilder().build(cuentas_punto, code_format=FormatoCodigo.PUNTO)
        r = repr(contexts[0])
        assert 'AccountContext' in r
        assert 'codigo=' in r


# ─────────────────────────────────────────────────────────────────────
# Tests de borde
# ─────────────────────────────────────────────────────────────────────

class TestBorde:
    def test_lista_vacia(self):
        contexts = ContextBuilder().build([])
        assert contexts == []

    def test_sin_codigo_detecta_formato(self):
        cuentas = [CuentaRaw(linea=1, codigo=None, nombre='TEST', monto=None)]
        contexts = ContextBuilder().build(cuentas)
        assert len(contexts) == 1

    def test_formato_auto_detectado(self, cuentas_punto):
        """Si no se especifica formato, se detecta automáticamente."""
        contexts = ContextBuilder().build(cuentas_punto)
        assert len(contexts) == 9
        mapa = {ctx.raw.codigo: ctx for ctx in contexts}
        assert mapa['1.1'].parent is mapa['1']

    def test_account_context_fields(self, cuentas_punto):
        """Verifica que todos los campos existen."""
        contexts = ContextBuilder().build(cuentas_punto, code_format=FormatoCodigo.PUNTO)
        ctx = contexts[0]
        assert hasattr(ctx, 'raw')
        assert hasattr(ctx, 'parent')
        assert hasattr(ctx, 'children')
        assert hasattr(ctx, 'siblings')
        assert hasattr(ctx, 'previous_account')
        assert hasattr(ctx, 'next_account')
        assert hasattr(ctx, 'hierarchy_level')
        assert hasattr(ctx, 'section')
        assert hasattr(ctx, 'layout')
        assert hasattr(ctx, 'account_type')
        assert hasattr(ctx, 'path')
        assert hasattr(ctx, 'position')
        assert hasattr(ctx, 'confidence')


# ─────────────────────────────────────────────────────────────────────
# Tests con PDFs reales
# ─────────────────────────────────────────────────────────────────────

class TestConPDFsReales:
    """Verifica que ContextBuilder funciona con datos reales del dataset."""

    @pytest.fixture(scope='class')
    def real_contexts(self):
        from parsers.integration import parse_with_analysis
        path = BASE_DIR / 'datasets' / 'validacion' / 'BALANCE DENHAM.pdf'
        if not path.exists():
            pytest.skip('PDF de prueba no encontrado')
        result = parse_with_analysis(path)
        contexts = ContextBuilder().build(
            result.cuentas,
            code_format=result.formato_codigo,
            layout=result.analysis.layout.columns if result.analysis else None,
        )
        return contexts

    def test_contextos_creados(self, real_contexts):
        assert len(real_contexts) > 0
        for ctx in real_contexts:
            assert isinstance(ctx, AccountContext)

    def test_cuentas_con_codigo_tienen_nivel(self, real_contexts):
        """Todas las cuentas con código tienen hierarchy_level > 0."""
        with_codes = [ctx for ctx in real_contexts if ctx.raw.codigo]
        for ctx in with_codes:
            assert ctx.hierarchy_level > 0

    def test_cuentas_sin_codigo_nivel_cero(self, real_contexts):
        """Cuentas sin código tienen hierarchy_level = 0."""
        without_codes = [ctx for ctx in real_contexts if not ctx.raw.codigo]
        for ctx in without_codes:
            assert ctx.hierarchy_level == 0

    def test_navegacion_completa(self, real_contexts):
        """Todas las cuentas tienen previous/next (excepto extremos)."""
        for ctx in real_contexts:
            if ctx.position == 0:
                assert ctx.previous_account is None
            else:
                assert ctx.previous_account is not None
            if ctx.position == len(real_contexts) - 1:
                assert ctx.next_account is None
            else:
                assert ctx.next_account is not None

    def test_paths_unicos(self, real_contexts):
        """Cada ruta jerárquica es única."""
        paths = [ctx.path for ctx in real_contexts if ctx.path]
        assert len(paths) == len(set(paths))

    def test_layout_presente(self, real_contexts):
        """Layout está disponible en los contextos."""
        with_layout = [ctx for ctx in real_contexts if ctx.layout]
        assert len(with_layout) > 0

    def test_position_secuencial(self, real_contexts):
        """Las posiciones son secuenciales desde 0."""
        for i, ctx in enumerate(real_contexts):
            assert ctx.position == i
