from __future__ import annotations

import pandas as pd
import pytest

from app_validacion import (
    _codigo_compatible_con_origen,
    _etiqueta_origen,
    _origen_efectivo,
    _pendientes_revision,
)


def _nombre_mostrar(row: pd.Series) -> str:
    return row.get('nombre_revision_usuario', '') or row['nombre_original']


COLUMNAS_RESULTADOS = [
    'linea', 'codigo_original', 'nombre_original', 'monto',
    'origen_columna', 'es_total', 'codigo_clasificado', 'metodo',
    'confianza', 'requiere_revision', 'nota', 'confianza_extraccion',
    'origen_columna_display', 'nombre_revision_usuario', 'tipo_revision',
]


@pytest.fixture
def row_base() -> pd.Series:
    return pd.Series({
        'linea': 1,
        'codigo_original': '1.01.05.02',
        'nombre_original': 'Cli. vta. sum.',
        'monto': 1500000.0,
        'origen_columna': 'activo',
        'origen_columna_display': 'activo',
        'es_total': False,
        'codigo_clasificado': 'AC.03',
        'metodo': 'diccionario_exacto',
        'confianza': 0.65,
        'requiere_revision': True,
        'nota': '',
        'confianza_extraccion': 1.0,
        'nombre_revision_usuario': '',
        'tipo_revision': '',
    })


@pytest.fixture
def df_resultados() -> pd.DataFrame:
    return pd.DataFrame([
        {
            'linea': 1,
            'codigo_original': '1.01.05.02',
            'nombre_original': 'Cli. vta. sum.',
            'monto': 1500000.0,
            'origen_columna': 'activo',
            'origen_columna_display': 'activo',
            'es_total': False,
            'codigo_clasificado': 'AC.03',
            'metodo': 'diccionario_exacto',
            'confianza': 0.65,
            'requiere_revision': True,
            'nota': '',
            'confianza_extraccion': 1.0,
            'nombre_revision_usuario': '',
            'tipo_revision': '',
        },
        {
            'linea': 2,
            'codigo_original': '',
            'nombre_original': '123456 500000',
            'monto': 500000.0,
            'origen_columna': 'desconocido',
            'origen_columna_display': 'desconocido',
            'es_total': False,
            'codigo_clasificado': '',
            'metodo': '',
            'confianza': 0.0,
            'requiere_revision': True,
            'nota': '',
            'confianza_extraccion': 0.3,
            'nombre_revision_usuario': '',
            'tipo_revision': '',
        },
    ])


class TestNombreMostrar:
    def test_sin_revision_visual(self, row_base):
        assert _nombre_mostrar(row_base) == 'Cli. vta. sum.'

    def test_con_revision_visual(self, row_base):
        row_base['nombre_revision_usuario'] = 'Clientes por venta de suministros'
        assert _nombre_mostrar(row_base) == 'Clientes por venta de suministros'

    def test_nombre_revision_vacio_usa_original(self, row_base):
        row_base['nombre_revision_usuario'] = ''
        assert _nombre_mostrar(row_base) == row_base['nombre_original']

    def test_nombre_original_interno_no_cambia(self, row_base):
        original = row_base['nombre_original']
        row_base['nombre_revision_usuario'] = 'Nombre visual editado'
        assert row_base['nombre_original'] == original


class TestOrigenContableEnRevision:
    def test_monto_positivo_conserva_columna_extraida(self):
        assert _origen_efectivo('perdida', 41840145) == 'perdida'
        assert _etiqueta_origen('perdida', 41840145) == 'PERDIDA'

    @pytest.mark.parametrize(
        ('extraida', 'contra'),
        [
            ('activo', 'pasivo'),
            ('pasivo', 'activo'),
            ('perdida', 'ganancia'),
            ('ganancia', 'perdida'),
        ],
    )
    def test_monto_negativo_usa_contra_cuenta(self, extraida, contra):
        assert _origen_efectivo(extraida, -100) == contra
        assert _etiqueta_origen(extraida, -100) == (
            f'{extraida.upper()} → {contra.upper()} (monto negativo)'
        )

    def test_perdida_rechaza_sugerencia_de_activo(self):
        assert not _codigo_compatible_con_origen('AC.07', 'perdida', 41840145)

    def test_perdida_permite_estado_de_resultados(self):
        assert _codigo_compatible_con_origen('ER.09', 'perdida', 41840145)

    def test_perdida_negativa_se_trata_como_ganancia(self):
        assert _origen_efectivo('perdida', -41840145) == 'ganancia'
        assert _codigo_compatible_con_origen('ER.01', 'perdida', -41840145)

    def test_pasivo_permite_codigos_de_pasivo_y_patrimonio(self):
        assert _codigo_compatible_con_origen('PC.01', 'pasivo', 100)
        assert _codigo_compatible_con_origen('PNC.01', 'pasivo', 100)
        assert _codigo_compatible_con_origen('PAT.01', 'pasivo', 100)

    def test_pasivo_sigue_rechazando_activos(self):
        assert not _codigo_compatible_con_origen('AC.01', 'pasivo', 100)

    def test_depreciacion_acumulada_en_pasivo_permite_activo_fijo(self):
        assert _codigo_compatible_con_origen(
            'ANC.01', 'pasivo', 8371044, 'Depreciación Acumulada'
        )

    def test_pasivo_comun_no_permite_activo_fijo(self):
        assert not _codigo_compatible_con_origen(
            'ANC.01', 'pasivo', 8371044, 'Proveedores nacionales'
        )

    @pytest.mark.parametrize(
        'nombre',
        [
            'Depreciaciones acumuladas',
            'Amortización acumulada de intangibles',
            'Deterioro acumulado de activos',
        ],
    )
    def test_otras_contra_cuentas_acreedoras_permiten_anc(self, nombre):
        assert _codigo_compatible_con_origen('ANC.01', 'pasivo', 100, nombre)


class TestPendientesRevision:
    def test_excluye_cuentas_con_monto_cero(self, df_resultados):
        df = df_resultados.copy()
        df.at[0, 'monto'] = 0

        pendientes = _pendientes_revision(df)

        assert 0 not in pendientes.index
        assert 1 in pendientes.index

    def test_excluye_cero_textual(self, df_resultados):
        df = df_resultados.copy()
        df['monto'] = df['monto'].astype(object)
        df.at[0, 'monto'] = '0'

        assert 0 not in _pendientes_revision(df).index

    def test_conserva_monto_faltante_para_revision(self, df_resultados):
        df = df_resultados.copy()
        df.at[0, 'monto'] = None

        assert 0 in _pendientes_revision(df).index

    def test_sigue_excluyendo_totales(self, df_resultados):
        df = df_resultados.copy()
        df.at[0, 'es_total'] = True

        assert 0 not in _pendientes_revision(df).index


class TestVisualNameChange:
    def test_solo_cambia_nombre_revision(self, df_resultados):
        df = df_resultados.copy()
        idx = 0

        nombre_original_antes = df.at[idx, 'nombre_original']

        df.at[idx, 'nombre_revision_usuario'] = 'Clientes'
        df.at[idx, 'tipo_revision'] = 'visual'

        assert df.at[idx, 'nombre_revision_usuario'] == 'Clientes'
        assert df.at[idx, 'nombre_original'] == nombre_original_antes
        assert df.at[idx, 'tipo_revision'] == 'visual'
        assert df.at[idx, 'metodo'] == 'diccionario_exacto'

    def test_visual_no_afecta_metodo(self, df_resultados):
        df = df_resultados.copy()
        metodo_antes = df.at[0, 'metodo']
        df.at[0, 'nombre_revision_usuario'] = 'Clientes'
        df.at[0, 'tipo_revision'] = 'visual'
        assert df.at[0, 'metodo'] == metodo_antes

    def test_visual_no_afecta_propagacion(self, df_resultados):
        df = df_resultados.copy()
        df.at[0, 'nombre_revision_usuario'] = 'Clientes'
        df.at[0, 'tipo_revision'] = 'visual'
        assert df.at[0, 'codigo_clasificado'] == 'AC.03'

    def test_multiple_visual_names(self, df_resultados):
        df = df_resultados.copy()
        df.at[0, 'nombre_revision_usuario'] = 'Clientes nacionales'
        df.at[1, 'nombre_revision_usuario'] = 'Proveedores varios'
        assert _nombre_mostrar(df.iloc[0]) == 'Clientes nacionales'
        assert _nombre_mostrar(df.iloc[1]) == 'Proveedores varios'


class TestAccountCorrection:
    def test_correccion_estructural_completa(self, df_resultados):
        df = df_resultados.copy()
        idx = 0

        df.at[idx, 'nombre_original'] = 'Clientes nacionales'
        df.at[idx, 'nombre_revision_usuario'] = ''
        df.at[idx, 'origen_columna'] = 'pasivo'
        df.at[idx, 'origen_columna_display'] = 'pasivo'
        df.at[idx, 'monto'] = 2500000.0
        df.at[idx, 'codigo_clasificado'] = 'AC.05'
        df.at[idx, 'metodo'] = 'manual_revision'
        df.at[idx, 'confianza'] = 1.0
        df.at[idx, 'requiere_revision'] = False
        df.at[idx, 'tipo_revision'] = 'correccion_extraccion'

        assert df.at[idx, 'nombre_original'] == 'Clientes nacionales'
        assert df.at[idx, 'origen_columna'] == 'pasivo'
        assert df.at[idx, 'monto'] == 2500000.0
        assert df.at[idx, 'codigo_clasificado'] == 'AC.05'
        assert df.at[idx, 'metodo'] == 'manual_revision'
        assert df.at[idx, 'confianza'] == 1.0
        assert df.at[idx, 'requiere_revision'] == False
        assert df.at[idx, 'tipo_revision'] == 'correccion_extraccion'

        assert _nombre_mostrar(df.iloc[idx]) == 'Clientes nacionales'

    def test_nombre_revision_limpio_al_corregir(self, df_resultados):
        df = df_resultados.copy()
        idx = 0

        df.at[idx, 'nombre_revision_usuario'] = 'Viejo visual'
        df.at[idx, 'nombre_original'] = 'Nombre corregido'
        df.at[idx, 'nombre_revision_usuario'] = ''
        df.at[idx, 'tipo_revision'] = 'correccion_extraccion'

        assert df.at[idx, 'nombre_revision_usuario'] == ''
        assert _nombre_mostrar(df.iloc[idx]) == 'Nombre corregido'

    def test_cambio_columna_activo_a_pasivo(self, df_resultados):
        df = df_resultados.copy()
        idx = 0

        assert df.at[idx, 'origen_columna'] == 'activo'
        df.at[idx, 'origen_columna'] = 'pasivo'
        df.at[idx, 'origen_columna_display'] = 'pasivo'
        df.at[idx, 'metodo'] = 'manual_revision'
        df.at[idx, 'tipo_revision'] = 'correccion_extraccion'

        assert df.at[idx, 'origen_columna'] == 'pasivo'
        assert df.at[idx, 'origen_columna_display'] == 'pasivo'

    def test_cambio_monto_positivo(self, df_resultados):
        df = df_resultados.copy()
        idx = 0
        df.at[idx, 'monto'] = 999999.0
        df.at[idx, 'metodo'] = 'manual_revision'
        df.at[idx, 'tipo_revision'] = 'correccion_extraccion'
        assert df.at[idx, 'monto'] == 999999.0

    def test_cambio_monto_negativo(self, df_resultados):
        df = df_resultados.copy()
        idx = 0
        df.at[idx, 'monto'] = -750000.0
        df.at[idx, 'metodo'] = 'manual_revision'
        df.at[idx, 'tipo_revision'] = 'correccion_extraccion'
        assert df.at[idx, 'monto'] == -750000.0


class TestNewAccountCreation:
    def test_crear_cuenta_nueva_en_resultados(self, df_resultados):
        df = df_resultados.copy()
        nueva_fila = pd.Series({
            'linea': 99,
            'codigo_original': '',
            'nombre_original': 'Clientes nacionales',
            'monto': 800000.0,
            'origen_columna': 'activo',
            'origen_columna_display': 'activo',
            'es_total': False,
            'codigo_clasificado': 'AC.03',
            'metodo': 'manual_revision',
            'confianza': 1.0,
            'requiere_revision': False,
            'nota': '',
            'confianza_extraccion': 1.0,
            'nombre_revision_usuario': '',
            'tipo_revision': 'correccion_extraccion',
        })
        df = pd.concat([df, nueva_fila.to_frame().T], ignore_index=True)

        assert len(df) == 3
        assert df.at[2, 'nombre_original'] == 'Clientes nacionales'
        assert df.at[2, 'origen_columna'] == 'activo'
        assert df.at[2, 'monto'] == 800000.0
        assert df.at[2, 'codigo_clasificado'] == 'AC.03'
        assert df.at[2, 'metodo'] == 'manual_revision'
        assert df.at[2, 'tipo_revision'] == 'correccion_extraccion'

    def test_cuenta_nueva_aparece_en_agrupacion(self, df_resultados):
        df = df_resultados.copy()
        nueva_fila = pd.Series({
            'linea': 99, 'codigo_original': '', 'nombre_original': 'Clientes nacionales',
            'monto': 800000.0, 'origen_columna': 'activo', 'origen_columna_display': 'activo',
            'es_total': False, 'codigo_clasificado': 'AC.03', 'metodo': 'manual_revision',
            'confianza': 1.0, 'requiere_revision': False, 'nota': '',
            'confianza_extraccion': 1.0, 'nombre_revision_usuario': '', 'tipo_revision': 'correccion_extraccion',
        })
        df = pd.concat([df, nueva_fila.to_frame().T], ignore_index=True)

        clasificadas = df[(df['codigo_clasificado'] != '') & (df['codigo_clasificado'] != '__EXCLUIR__') & (~df['es_total'])].copy()
        agrupado = clasificadas.groupby('codigo_clasificado').agg(
            monto_total=('monto', 'sum'), num_cuentas=('nombre_original', 'count')
        ).reset_index()

        ac03 = agrupado[agrupado['codigo_clasificado'] == 'AC.03']
        assert not ac03.empty
        assert ac03.iloc[0]['monto_total'] == 2300000.0
        assert ac03.iloc[0]['num_cuentas'] == 2


class TestBalanceImpact:
    def test_cambio_monto_afecta_total(self, df_resultados):
        df = df_resultados.copy()
        clasificadas = df[(df['codigo_clasificado'] != '') & (df['codigo_clasificado'] != '__EXCLUIR__') & (~df['es_total'])].copy()
        agrupado = clasificadas.groupby('codigo_clasificado').agg(monto_total=('monto', 'sum')).reset_index()
        total_antes = agrupado['monto_total'].sum()

        df.at[0, 'monto'] = 3000000.0
        df.at[0, 'metodo'] = 'manual_revision'
        df.at[0, 'tipo_revision'] = 'correccion_extraccion'

        clasificadas = df[(df['codigo_clasificado'] != '') & (df['codigo_clasificado'] != '__EXCLUIR__') & (~df['es_total'])].copy()
        agrupado = clasificadas.groupby('codigo_clasificado').agg(monto_total=('monto', 'sum')).reset_index()
        total_despues = agrupado['monto_total'].sum()

        assert total_antes == 1500000.0
        assert total_despues == 3000000.0
        assert total_despues != total_antes

    def test_cambio_columna_no_afecta_monto_total(self, df_resultados):
        df = df_resultados.copy()
        clasificadas = df[(df['codigo_clasificado'] != '') & (df['codigo_clasificado'] != '__EXCLUIR__') & (~df['es_total'])].copy()
        agrupado = clasificadas.groupby('codigo_clasificado').agg(monto_total=('monto', 'sum')).reset_index()
        total_antes = agrupado['monto_total'].sum()

        df.at[0, 'origen_columna'] = 'pasivo'
        df.at[0, 'origen_columna_display'] = 'pasivo'
        df.at[0, 'metodo'] = 'manual_revision'

        clasificadas = df[(df['codigo_clasificado'] != '') & (df['codigo_clasificado'] != '__EXCLUIR__') & (~df['es_total'])].copy()
        agrupado = clasificadas.groupby('codigo_clasificado').agg(monto_total=('monto', 'sum')).reset_index()
        total_despues = agrupado['monto_total'].sum()

        assert total_antes == total_despues


class TestMetodoPersistencia:
    def test_metodo_manual_revision_guardado(self, df_resultados):
        df = df_resultados.copy()
        df.at[0, 'metodo'] = 'manual_revision'
        df.at[0, 'confianza'] = 1.0
        df.at[0, 'requiere_revision'] = False
        df.at[0, 'tipo_revision'] = 'correccion_extraccion'

        assert df.at[0, 'metodo'] == 'manual_revision'
        assert df.at[0, 'confianza'] == 1.0
        assert df.at[0, 'requiere_revision'] == False

    def test_confianza_siempre_uno(self, df_resultados):
        df = df_resultados.copy()
        for idx in df.index:
            df.at[idx, 'confianza'] = 1.0
            df.at[idx, 'requiere_revision'] = False
        assert (df['confianza'] == 1.0).all()
        assert (~df['requiere_revision']).all()

    def test_tipo_revision_visual_persiste(self, df_resultados):
        df = df_resultados.copy()
        df.at[0, 'nombre_revision_usuario'] = 'Nombre visual'
        df.at[0, 'tipo_revision'] = 'visual'
        assert df.at[0, 'tipo_revision'] == 'visual'

    def test_tipo_revision_correccion_persiste(self, df_resultados):
        df = df_resultados.copy()
        df.at[0, 'tipo_revision'] = 'correccion_extraccion'
        assert df.at[0, 'tipo_revision'] == 'correccion_extraccion'

    def test_requiere_revision_falso_despues_guardar(self, df_resultados):
        df = df_resultados.copy()
        df.at[0, 'requiere_revision'] = False
        df.at[0, 'metodo'] = 'manual_revision'
        assert not df.at[0, 'requiere_revision']
