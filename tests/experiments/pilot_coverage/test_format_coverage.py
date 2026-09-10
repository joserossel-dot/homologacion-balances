"""
tests/experiments/pilot_coverage/test_format_coverage.py

Evaluación experimental rigurosa y contrastada de cobertura de formatos (Encargo A5).
Compara tres extractores sobre los fixtures sintéticos:
1. Parser Actual (parser_universal.py)
2. Separador Original (document_intelligence.extractors.double_column.py)
3. Variante Experimental Endurecida (experiments.pilot_coverage.formats.experimental_double_column.py)

Reproducibilidad desde Clon Limpio:
- Los fixtures sintéticos se generan automáticamente en tmp_path / temporary directory.
- No se depende de binarios preexistentes o ignorados en git.
- Distingue explícitamente:
  * Pruebas de Reproducibilidad Limpia.
  * Pruebas Geométricas (Nivel 1).
  * Pruebas de Aceptación con Verificación Exhaustiva contra Ground Truth Independiente (Nivel 2).
  * Pruebas Adversariales Obligatorias (Nivel 2B).
  * Pruebas de Caracterización con xfail(strict=True) para Documentar Defectos Conocidos (Nivel 3).
"""

from __future__ import annotations

import pathlib
from typing import Any, Dict
import pytest

from parser_universal import (
    ParserPDF,
    parsear_excel,
)
from document_intelligence.extractors.double_column import (
    _boundary_2_clusters,
    _lado_es_cuenta,
    DoubleColumnExtractor,
)
from experiments.pilot_coverage.formats.experimental_double_column import (
    ExperimentalDoubleColumnExtractor,
)
from experiments.pilot_coverage.formats.generate_fixtures import (
    generar_todos_los_fixtures,
)
from experiments.pilot_coverage.formats.expected_ground_truth import (
    GROUND_TRUTH_PARALELO_CON_CODIGO,
    GROUND_TRUTH_PARALELO_SIN_CODIGO,
    GROUND_TRUTH_8_COLUMNAS,
    GROUND_TRUTH_CLASIFICADO_VERTICAL,
    GROUND_TRUTH_COMPARATIVO,
    GROUND_TRUTH_NOTAS,
    GROUND_TRUTH_MULTILINEA,
    GROUND_TRUTH_NEGATIVOS_CEROS,
    GROUND_TRUTH_EXCEL,
    GROUND_TRUTH_ESPACIADO,
    GROUND_TRUTH_ADV_01_ANCHO_DISTINTO,
    GROUND_TRUTH_ADV_02_LARGOS_IZQ,
    GROUND_TRUTH_ADV_03_LARGOS_DER,
    GROUND_TRUTH_ADV_04_TITULOS_CENTRADOS,
    GROUND_TRUTH_ADV_05_SEP_ESTRECHA,
    GROUND_TRUTH_ADV_06_SEP_AMPLIA,
    GROUND_TRUTH_ADV_07_MONTOS_DISTINTOS_DIGITOS,
    GROUND_TRUTH_ADV_08_MONTOS_ENTEROS_SIN_SEP,
    GROUND_TRUTH_ADV_09_FILAS_DESPLAZADAS,
    GROUND_TRUTH_ADV_10_TOTALES_SUBTOTALES,
    GROUND_TRUTH_ADV_13_CODIGOS_MIX_DIGITOS,
)


@pytest.fixture(scope="session")
def fixtures_dir(tmp_path_factory) -> pathlib.Path:
    """
    Fixture generador de sesión en almacenamiento temporal efímero.
    Garantiza reproducibilidad al 100% sin depender de archivos ignorados preexistentes.
    """
    td = tmp_path_factory.mktemp("session_formats_fixtures")
    generar_todos_los_fixtures(td)
    return td


def _adaptar_8_columnas(c: Any) -> Dict[str, float]:
    """Adaptador exclusivo del experimento para leer las 8 columnas contables de CuentaRaw."""
    cols = dict(c.montos_columnas or {})
    return {
        "debito": float(cols.get("debitos", 0.0) or 0.0),
        "credito": float(cols.get("creditos", 0.0) or 0.0),
        "deudor": float(cols.get("saldo_deudor", 0.0) or 0.0),
        "acreedor": float(cols.get("saldo_acreedor", 0.0) or 0.0),
        "activo": float(cols.get("activo", 0.0) or 0.0),
        "pasivo": float(cols.get("pasivo", 0.0) or 0.0),
        "perdida": float(cols.get("perdida", 0.0) or 0.0),
        "ganancia": float(cols.get("ganancia", 0.0) or 0.0),
    }


# ===========================================================================
# 0. Frente 1: Prueba de Reproducibilidad desde Clon Limpio
# ===========================================================================

def test_reproducibilidad_en_entorno_limpio_sin_fixtures_preexistentes(tmp_path):
    """
    Verifica que el generador y los extractores funcionan de forma 100% reproducible
    en un directorio temporal nuevo, sin depender de ningún archivo binario preexistente.
    """
    rutas = generar_todos_los_fixtures(tmp_path)
    assert len(rutas) >= 23, f"Deben generarse al menos 23 fixtures sintéticos, obtenidos {len(rutas)}"

    # Verificar que el fixture 01 generado en tmp_path es procesado con 100% exactitud por E3
    p1 = rutas["paralelo_con_codigo"]
    assert p1.exists()
    res_exp = ExperimentalDoubleColumnExtractor().extract(p1)
    assert not res_exp.fallback_used
    assert len(res_exp.result.cuentas) == 10

    # Verificar que el fixture 02 de 8 columnas es procesado en tmp_path
    p2 = rutas["ocho_columnas"]
    assert p2.exists()
    res_8col = ParserPDF().parsear(p2)
    assert len(res_8col.cuentas) == 5


# ===========================================================================
# 1. Nivel 1: Pruebas Geométricas con Coordenadas Sintéticas
# ===========================================================================

def test_geom_boundary_2_clusters_identifica_eje_central():
    """Nivel 1: Verifica que el algoritmo de varianza intra-cluster calcule boundary equilibrado."""
    words = []
    for y in [100, 120, 140, 160, 180, 200]:
        words.append({'text': '110101', 'x0': 50.0, 'top': float(y)})
        words.append({'text': 'Caja', 'x0': 110.0, 'top': float(y)})
        words.append({'text': '100000', 'x0': 200.0, 'top': float(y)})

    for y in [100, 120, 140, 160, 180, 200]:
        words.append({'text': '210101', 'x0': 350.0, 'top': float(y)})
        words.append({'text': 'Proveedores', 'x0': 410.0, 'top': float(y)})
        words.append({'text': '100000', 'x0': 500.0, 'top': float(y)})

    boundary = _boundary_2_clusters(words)
    assert boundary is not None
    assert 220.0 < boundary < 330.0


def test_geom_lado_es_cuenta_valida_estructura():
    """Nivel 1: Verifica el discriminador estructural _lado_es_cuenta."""
    assert _lado_es_cuenta(['110101', 'Banco', 'Chile', '1.500.000']) is True
    assert _lado_es_cuenta(['1.01.01', 'Cuentas', 'Cobrar', '250.000']) is True
    assert _lado_es_cuenta(['Banco', 'de', 'Chile', '1.500.000']) is False
    assert _lado_es_cuenta(['TOTAL', 'ACTIVO', 'CIRCULANTE', '10.000.000']) is False


# ===========================================================================
# 2. Nivel 2: Pruebas de Aceptación Formatos Base (Tres Extractores Comparados)
# ===========================================================================

def test_aceptacion_01_paralelo_con_codigo_variante_experimental_exitosa(fixtures_dir: pathlib.Path):
    """
    Aceptación Formato 1: Balance Paralelo con Códigos.
    Compara los 3 extractores:
    - Actual: Corrompe códigos/montos por fusión horizontal.
    - Original (double_column): Sesga el boundary hacia la izquierda y pierde montos de activo.
    - Variante Experimental (consenso): 100% de las 8 cuentas y 2 totales con montos exactos.
    """
    pdf_path = fixtures_dir / "01_paralelo_activo_pasivo.pdf"
    assert pdf_path.exists()

    # 1. Extractor Actual
    res_actual = ParserPDF().parsear(pdf_path)
    cuentas_act_corruptas = [c for c in res_actual.cuentas if c.monto is None or c.codigo == "1.200.000"]
    assert len(cuentas_act_corruptas) >= 2, "Actual debe presentar corrupción de líneas"

    # 2. Separador Original
    res_orig = DoubleColumnExtractor().extract(pdf_path)
    cuentas_orig = [c for c in res_orig.result.cuentas if not c.es_total]
    cuentas_orig_sin_monto = [c for c in cuentas_orig if c.monto is None]
    assert len(cuentas_orig_sin_monto) >= 2, "Original debe presentar montos None por corte sesgado"

    # 3. Variante Experimental
    res_exp = ExperimentalDoubleColumnExtractor().extract(pdf_path)
    assert res_exp.fallback_used is False, "Variante experimental debió activar separación"

    cuentas_exp = [c for c in res_exp.result.cuentas if not c.es_total]
    totales_exp = [c for c in res_exp.result.cuentas if c.es_total]

    gt_detalles = [g for g in GROUND_TRUTH_PARALELO_CON_CODIGO if not g.es_total]
    gt_totales = [g for g in GROUND_TRUTH_PARALELO_CON_CODIGO if g.es_total]

    assert len(cuentas_exp) == len(gt_detalles) == 8, f"Esperadas 8 cuentas, obtenidas {len(cuentas_exp)}"
    assert len(totales_exp) == len(gt_totales) == 2, f"Esperados 2 totales, obtenidos {len(totales_exp)}"

    for gt in gt_detalles:
        match = [c for c in cuentas_exp if c.codigo == gt.codigo]
        assert len(match) == 1, f"Cuenta {gt.codigo} ({gt.nombre}) no encontrada unívocamente"
        c = match[0]
        assert c.monto == gt.monto, f"Monto para {gt.codigo}: esperado {gt.monto}, obtenido {c.monto}"
        assert c.nombre.strip().lower() == gt.nombre.strip().lower(), f"Nombre para {gt.codigo}: esperado {gt.nombre}, obtenido {c.nombre}"

    for gt in gt_totales:
        match = [c for c in totales_exp if gt.nombre.lower() in c.nombre.lower()]
        assert len(match) == 1, f"Total '{gt.nombre}' no encontrado"
        assert match[0].monto == gt.monto, f"Monto total: esperado {gt.monto}, obtenido {match[0].monto}"


def test_aceptacion_01b_paralelo_sin_codigo_extraccion(fixtures_dir: pathlib.Path):
    """Aceptación Formato 1b: Paralelo sin códigos. Verifica fallback seguro."""
    pdf_path = fixtures_dir / "01b_paralelo_sin_codigo.pdf"
    assert pdf_path.exists()

    res = ExperimentalDoubleColumnExtractor().extract(pdf_path)
    assert res.fallback_used is True, "Sin códigos debe hacer fallback seguro al parser universal"
    assert len(res.result.cuentas) == len(GROUND_TRUTH_PARALELO_SIN_CODIGO) == 6


def test_aceptacion_02_ocho_columnas_control_negativo_y_columnas_exhaustivas(fixtures_dir: pathlib.Path):
    """
    Aceptación Formato 2: Balance 8 Columnas (Control Negativo y Exhaustividad de 8 Columnas).
    1. Verifica que E3 active fallback_used=True (NO bisecciona una tabla de 8 columnas).
    2. Verifica la extracción exacta de las 8 columnas contables individuales sin colapso.
    """
    pdf_path = fixtures_dir / "02_ocho_columnas_control_negativo.pdf"
    assert pdf_path.exists()

    res_exp = ExperimentalDoubleColumnExtractor().extract(pdf_path)
    assert res_exp.fallback_used is True, "Control Negativo: 8 columnas NO debe activar bisección"

    cuentas = res_exp.result.cuentas
    assert len(cuentas) == len(GROUND_TRUTH_8_COLUMNAS) == 5

    for gt in GROUND_TRUTH_8_COLUMNAS:
        match = [c for c in cuentas if c.codigo == gt.codigo]
        assert len(match) == 1, f"Cuenta {gt.codigo} no encontrada"
        c = match[0]
        cols_obtenidas = _adaptar_8_columnas(c)

        for col_name in ["debito", "credito", "deudor", "acreedor", "activo", "pasivo", "perdida", "ganancia"]:
            val_exp = gt.columnas_8col.get(col_name, 0.0)
            val_obt = cols_obtenidas.get(col_name, 0.0)
            assert val_obt == val_exp, f"Columna {col_name} en cuenta {gt.codigo}: esperado {val_exp}, obtenido {val_obt}"


def test_aceptacion_03_clasificado_vertical_control_negativo_y_cuentas(fixtures_dir: pathlib.Path):
    """Aceptación Formato 3: Clasificado Vertical. Control Negativo."""
    pdf_path = fixtures_dir / "03_clasificado_vertical.pdf"
    assert pdf_path.exists()

    res_exp = ExperimentalDoubleColumnExtractor().extract(pdf_path)
    assert res_exp.fallback_used is True, "Control Negativo: Vertical no debe activar doble columna"

    cuentas = [c for c in res_exp.result.cuentas if not c.es_total]
    totales = [c for c in res_exp.result.cuentas if c.es_total]

    gt_detalles = [g for g in GROUND_TRUTH_CLASIFICADO_VERTICAL if not g.es_total]
    gt_totales = [g for g in GROUND_TRUTH_CLASIFICADO_VERTICAL if g.es_total]

    assert len(cuentas) == len(gt_detalles) == 5
    assert len(totales) == len(gt_totales) == 2

    for gt in gt_detalles:
        match = [c for c in cuentas if c.codigo == gt.codigo]
        assert len(match) == 1
        assert match[0].monto == gt.monto


def test_aceptacion_07_negativos_ceros_vacias(fixtures_dir: pathlib.Path):
    """Aceptación Formato 7: Negativos parentéticos y ceros."""
    pdf_path = fixtures_dir / "07_negativos_ceros_vacias.pdf"
    assert pdf_path.exists()

    res = ParserPDF().parsear(pdf_path)
    cuentas = [c for c in res.cuentas if not c.es_total]

    assert len(cuentas) == len(GROUND_TRUTH_NEGATIVOS_CEROS) == 5
    for gt in GROUND_TRUTH_NEGATIVOS_CEROS:
        match = [c for c in cuentas if c.codigo == gt.codigo]
        assert len(match) == 1
        c = match[0]
        assert c.monto == gt.monto, f"Monto para {gt.codigo}: esperado {gt.monto}, obtenido {c.monto}"


def test_aceptacion_08_excel_xlsx(fixtures_dir: pathlib.Path):
    """Aceptación Formato 8: Archivos XLSX."""
    xlsx_path = fixtures_dir / "08_balance_excel.xlsx"
    assert xlsx_path.exists()

    with open(xlsx_path, "rb") as f:
        cuentas_todas = parsear_excel(f)

    # Filtrar cuentas contables con código
    cuentas = [c for c in cuentas_todas if c.codigo]
    assert len(cuentas) == len(GROUND_TRUTH_EXCEL) == 5
    for gt in GROUND_TRUTH_EXCEL:
        match = [c for c in cuentas if c.codigo == gt.codigo]
        assert len(match) == 1
        assert match[0].monto == gt.monto


def test_aceptacion_09_espaciado_irregular(fixtures_dir: pathlib.Path):
    """Aceptación Formato 9: Espaciado Irregular."""
    pdf_path = fixtures_dir / "09_espaciado_y_alineacion.pdf"
    assert pdf_path.exists()

    res = ParserPDF().parsear(pdf_path)
    cuentas = [c for c in res.cuentas if not c.es_total]

    assert len(cuentas) == len(GROUND_TRUTH_ESPACIADO) == 3
    for gt in GROUND_TRUTH_ESPACIADO:
        match = [c for c in cuentas if c.codigo == gt.codigo]
        assert len(match) == 1
        assert match[0].monto == gt.monto


def test_aceptacion_10_xls_antiguo_declaracion_no_probado(fixtures_dir: pathlib.Path):
    """Formato 10: XLS Antiguo (Excel 97-2003). Declaración formal de No Probado."""
    pytest.skip("Formato 10 (XLS Antiguo) declarado formalmente No Probado por requerir dependencias binarias no autorizadas")


# ===========================================================================
# 3. Nivel 2B: Pruebas Adversariales Obligatorias (13 Escenarios)
# ===========================================================================

def test_adversarial_01_bloques_ancho_distinto(fixtures_dir: pathlib.Path):
    """ADV 01: Bloques con ancho asimétrico (izq 70mm vs der 150mm)."""
    pdf_path = fixtures_dir / "adv_01_bloques_ancho_distinto.pdf"
    assert pdf_path.exists()
    res = ExperimentalDoubleColumnExtractor().extract(pdf_path)
    assert res.fallback_used is False
    cuentas = [c for c in res.result.cuentas if not c.es_total]
    assert len(cuentas) == len(GROUND_TRUTH_ADV_01_ANCHO_DISTINTO)
    for gt in GROUND_TRUTH_ADV_01_ANCHO_DISTINTO:
        m = [c for c in cuentas if c.codigo == gt.codigo]
        assert len(m) == 1, f"Código {gt.codigo} no encontrado"
        assert m[0].monto == gt.monto


def test_adversarial_02_nombres_largos_solo_izq(fixtures_dir: pathlib.Path):
    """ADV 02: Nombres muy largos en columna izquierda."""
    pdf_path = fixtures_dir / "adv_02_nombres_largos_solo_izq.pdf"
    assert pdf_path.exists()
    res = ExperimentalDoubleColumnExtractor().extract(pdf_path)
    assert res.fallback_used is False
    cuentas = [c for c in res.result.cuentas if not c.es_total]
    assert len(cuentas) == len(GROUND_TRUTH_ADV_02_LARGOS_IZQ)
    for gt in GROUND_TRUTH_ADV_02_LARGOS_IZQ:
        m = [c for c in cuentas if c.codigo == gt.codigo]
        assert len(m) == 1
        assert m[0].monto == gt.monto


def test_adversarial_03_nombres_largos_solo_der(fixtures_dir: pathlib.Path):
    """ADV 03: Nombres muy largos en columna derecha."""
    pdf_path = fixtures_dir / "adv_03_nombres_largos_solo_der.pdf"
    assert pdf_path.exists()
    res = ExperimentalDoubleColumnExtractor().extract(pdf_path)
    assert res.fallback_used is False
    cuentas = [c for c in res.result.cuentas if not c.es_total]
    assert len(cuentas) == len(GROUND_TRUTH_ADV_03_LARGOS_DER)
    for gt in GROUND_TRUTH_ADV_03_LARGOS_DER:
        m = [c for c in cuentas if c.codigo == gt.codigo]
        assert len(m) == 1
        assert m[0].monto == gt.monto


def test_adversarial_04_titulos_subtitulos_centrados(fixtures_dir: pathlib.Path):
    """ADV 04: Títulos largos centrados que atraviesan el eje central."""
    pdf_path = fixtures_dir / "adv_04_titulos_subtitulos_centrados.pdf"
    assert pdf_path.exists()
    res = ExperimentalDoubleColumnExtractor().extract(pdf_path)
    assert res.fallback_used is False
    cuentas = [c for c in res.result.cuentas if not c.es_total]
    assert len(cuentas) == len(GROUND_TRUTH_ADV_04_TITULOS_CENTRADOS)
    for gt in GROUND_TRUTH_ADV_04_TITULOS_CENTRADOS:
        m = [c for c in cuentas if c.codigo == gt.codigo]
        assert len(m) == 1
        assert m[0].monto == gt.monto


def test_adversarial_05_separacion_estrecha(fixtures_dir: pathlib.Path):
    """ADV 05: Separación inter-columnas muy estrecha (5mm / ~14pt)."""
    pdf_path = fixtures_dir / "adv_05_separacion_estrecha.pdf"
    assert pdf_path.exists()
    res = ExperimentalDoubleColumnExtractor().extract(pdf_path)
    assert res.fallback_used is False
    cuentas = [c for c in res.result.cuentas if not c.es_total]
    assert len(cuentas) == len(GROUND_TRUTH_ADV_05_SEP_ESTRECHA)
    for gt in GROUND_TRUTH_ADV_05_SEP_ESTRECHA:
        m = [c for c in cuentas if c.codigo == gt.codigo]
        assert len(m) == 1
        assert m[0].monto == gt.monto


def test_adversarial_06_separacion_amplia(fixtures_dir: pathlib.Path):
    """ADV 06: Separación inter-columnas muy amplia (40mm)."""
    pdf_path = fixtures_dir / "adv_06_separacion_amplia.pdf"
    assert pdf_path.exists()
    res = ExperimentalDoubleColumnExtractor().extract(pdf_path)
    assert res.fallback_used is False
    cuentas = [c for c in res.result.cuentas if not c.es_total]
    assert len(cuentas) == len(GROUND_TRUTH_ADV_06_SEP_AMPLIA)
    for gt in GROUND_TRUTH_ADV_06_SEP_AMPLIA:
        m = [c for c in cuentas if c.codigo == gt.codigo]
        assert len(m) == 1
        assert m[0].monto == gt.monto


def test_adversarial_07_montos_distintos_digitos(fixtures_dir: pathlib.Path):
    """ADV 07: Montos con distinta cantidad de dígitos en la misma fila."""
    pdf_path = fixtures_dir / "adv_07_montos_distintos_digitos.pdf"
    assert pdf_path.exists()
    res = ExperimentalDoubleColumnExtractor().extract(pdf_path)
    assert res.fallback_used is False
    cuentas = [c for c in res.result.cuentas if not c.es_total]
    assert len(cuentas) == len(GROUND_TRUTH_ADV_07_MONTOS_DISTINTOS_DIGITOS)
    for gt in GROUND_TRUTH_ADV_07_MONTOS_DISTINTOS_DIGITOS:
        m = [c for c in cuentas if c.codigo == gt.codigo]
        assert len(m) == 1
        assert m[0].monto == gt.monto


def test_adversarial_08_montos_enteros_sin_separador(fixtures_dir: pathlib.Path):
    """ADV 08: Montos enteros de 6 dígitos sin separador de miles (ej. 500000)."""
    pdf_path = fixtures_dir / "adv_08_montos_enteros_sin_separador.pdf"
    assert pdf_path.exists()
    res = ExperimentalDoubleColumnExtractor().extract(pdf_path)
    assert res.fallback_used is False
    cuentas = [c for c in res.result.cuentas if not c.es_total]
    assert len(cuentas) == len(GROUND_TRUTH_ADV_08_MONTOS_ENTEROS_SIN_SEP)
    for gt in GROUND_TRUTH_ADV_08_MONTOS_ENTEROS_SIN_SEP:
        m = [c for c in cuentas if c.codigo == gt.codigo]
        assert len(m) == 1, f"Código {gt.codigo} ({gt.nombre}) no encontrado"
        assert m[0].monto == gt.monto, f"Monto para {gt.codigo}: esperado {gt.monto}, obtenido {m[0].monto}"


def test_adversarial_09_filas_desplazamiento_vertical(fixtures_dir: pathlib.Path):
    """ADV 09: Filas no alineadas horizontalmente (staggered)."""
    pdf_path = fixtures_dir / "adv_09_filas_desplazamiento_vertical.pdf"
    assert pdf_path.exists()
    res = ExperimentalDoubleColumnExtractor().extract(pdf_path)
    assert res.fallback_used is False
    cuentas = [c for c in res.result.cuentas if not c.es_total]
    assert len(cuentas) == len(GROUND_TRUTH_ADV_09_FILAS_DESPLAZADAS)
    for gt in GROUND_TRUTH_ADV_09_FILAS_DESPLAZADAS:
        m = [c for c in cuentas if c.codigo == gt.codigo]
        assert len(m) == 1
        assert m[0].monto == gt.monto


def test_adversarial_10_totales_subtotales_paralelos(fixtures_dir: pathlib.Path):
    """ADV 10: Totales y subtotales intermedios a ambos lados."""
    pdf_path = fixtures_dir / "adv_10_totales_subtotales_paralelos.pdf"
    assert pdf_path.exists()
    res = ExperimentalDoubleColumnExtractor().extract(pdf_path)
    assert res.fallback_used is False
    cuentas = [c for c in res.result.cuentas if not c.es_total]
    totales = [c for c in res.result.cuentas if c.es_total]
    gt_det = [g for g in GROUND_TRUTH_ADV_10_TOTALES_SUBTOTALES if not g.es_total]
    gt_tot = [g for g in GROUND_TRUTH_ADV_10_TOTALES_SUBTOTALES if g.es_total]
    assert len(cuentas) == len(gt_det)
    assert len(totales) == len(gt_tot)
    for gt in gt_det:
        m = [c for c in cuentas if c.codigo == gt.codigo]
        assert len(m) == 1
        assert m[0].monto == gt.monto


def test_adversarial_11_una_sola_fila_paralela_control_negativo(fixtures_dir: pathlib.Path):
    """ADV 11: Control Negativo - Una sola fila aparentemente paralela (debe abstenerse)."""
    pdf_path = fixtures_dir / "adv_11_una_sola_fila_paralela.pdf"
    assert pdf_path.exists()
    res = ExperimentalDoubleColumnExtractor().extract(pdf_path)
    assert res.fallback_used is True, "Una sola fila no debe activar bisección"


def test_adversarial_12_ocho_columnas_enteros_control_negativo(fixtures_dir: pathlib.Path):
    """ADV 12: Control Negativo - Ocho columnas con muchos números enteros (no confundir con códigos)."""
    pdf_path = fixtures_dir / "adv_12_ocho_columnas_muchos_numeros_tipo_codigo.pdf"
    assert pdf_path.exists()
    res = ExperimentalDoubleColumnExtractor().extract(pdf_path)
    assert res.fallback_used is True, "8 columnas con enteros grandes NO debe activar bisección"


def test_adversarial_13_codigos_5_6_7_8_digitos(fixtures_dir: pathlib.Path):
    """ADV 13: Códigos de 5, 6, 7 y 8 dígitos en paralelo."""
    pdf_path = fixtures_dir / "adv_13_codigos_5_6_7_8_digitos.pdf"
    assert pdf_path.exists()
    res = ExperimentalDoubleColumnExtractor().extract(pdf_path)
    assert res.fallback_used is False
    cuentas = [c for c in res.result.cuentas if not c.es_total]
    assert len(cuentas) == len(GROUND_TRUTH_ADV_13_CODIGOS_MIX_DIGITOS)
    for gt in GROUND_TRUTH_ADV_13_CODIGOS_MIX_DIGITOS:
        m = [c for c in cuentas if c.codigo == gt.codigo]
        assert len(m) == 1, f"Código {gt.codigo} ({gt.nombre}) no encontrado"
        assert m[0].monto == gt.monto


# ===========================================================================
# 4. Nivel 3: Pruebas de Caracterización de Defectos Conocidos (xfail estricto)
# ===========================================================================

@pytest.mark.xfail(strict=True, reason="Defecto caracterizado: El separador original double_column sesga el corte y deja montos de activo en None")
def test_caracterizacion_01_original_falla_en_paralelo_con_codigo(fixtures_dir: pathlib.Path):
    """Demuestra que el separador original double_column falla en el fixture 1."""
    pdf_path = fixtures_dir / "01_paralelo_activo_pasivo.pdf"
    assert pdf_path.exists(), "Pre-verificación: Fixture debe existir"
    res_orig = DoubleColumnExtractor().extract(pdf_path)
    assert res_orig is not None and res_orig.result is not None, "Pre-verificación: Extractor ejecutó"
    cuentas_orig = [c for c in res_orig.result.cuentas if not c.es_total]
    gt_detalles = [g for g in GROUND_TRUTH_PARALELO_CON_CODIGO if not g.es_total]

    for gt in gt_detalles:
        match = [c for c in cuentas_orig if c.codigo == gt.codigo]
        assert len(match) == 1
        assert match[0].monto == gt.monto, f"Falla demostrada en monto original de {gt.codigo}: {match[0].monto} != {gt.monto}"


@pytest.mark.xfail(strict=True, reason="Defecto conocido: ParserPDF en comparativo incluye la fila de encabezado 'Cuenta 2024' como cuenta contable")
def test_caracterizacion_04_comparativo_incluye_fila_encabezado(fixtures_dir: pathlib.Path):
    """Caracteriza que el parser actual extrae 6 filas en vez de las 5 cuentas de detalle puras."""
    pdf_path = fixtures_dir / "04_comparativo_dos_periodos.pdf"
    assert pdf_path.exists(), "Pre-verificación: Fixture debe existir"
    res_actual = ParserPDF().parsear(pdf_path)
    assert res_actual is not None and res_actual.cuentas is not None, "Pre-verificación: Parser ejecutó"
    cuentas_act = [c for c in res_actual.cuentas if not c.es_total]
    assert len(cuentas_act) == len(GROUND_TRUTH_COMPARATIVO) == 5


@pytest.mark.xfail(strict=True, reason="Defecto conocido: En PDF plano sin líneas vectoriales, el número de nota se fusiona con el monto")
def test_caracterizacion_05_notas_cercanas_fusiona_numero_nota(fixtures_dir: pathlib.Path):
    """Caracteriza que en PDF plano el número de nota altera el importe extraído."""
    pdf_path = fixtures_dir / "05_notas_cercanas_a_montos.pdf"
    assert pdf_path.exists(), "Pre-verificación: Fixture debe existir"
    res_actual = ParserPDF().parsear(pdf_path)
    assert res_actual is not None and res_actual.cuentas is not None, "Pre-verificación: Parser ejecutó"
    cuentas_act = [c for c in res_actual.cuentas if not c.es_total]
    for gt in GROUND_TRUTH_NOTAS:
        match = [c for c in cuentas_act if c.nombre and gt.nombre in c.nombre]
        assert len(match) == 1
        assert match[0].monto is not None and float(match[0].monto) == gt.monto


@pytest.mark.xfail(strict=True, reason="Defecto conocido: Descripciones multilínea en PDF plano se dividen en fragmentos separados")
def test_caracterizacion_06_descripciones_multilinea_fragmentadas(fixtures_dir: pathlib.Path):
    """Caracteriza que glosas de 2 y 3 líneas devuelven 4 filas fragmentadas en vez de 2 cuentas completas."""
    pdf_path = fixtures_dir / "06_descripciones_multilinea.pdf"
    assert pdf_path.exists(), "Pre-verificación: Fixture debe existir"
    res_actual = ParserPDF().parsear(pdf_path)
    assert res_actual is not None and res_actual.cuentas is not None, "Pre-verificación: Parser ejecutó"
    cuentas_act = [c for c in res_actual.cuentas if not c.es_total]
    assert len(cuentas_act) == len(GROUND_TRUTH_MULTILINEA) == 2
