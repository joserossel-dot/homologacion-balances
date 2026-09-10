"""
tests/experiments/pilot_coverage/test_benchmark_isolated.py

Suite de pruebas de aislamiento, reproducibilidad y validación taxonómica (Encargo A5).
Verifica:
1. El estado de socket.socket antes, durante y después del contexto de aislamiento.
2. Bloqueo fail-closed de connect y connect_ex sin bloquear bind ni romper socket estándar posterior.
3. Preservación y restauración exacta de variables de entorno (DATABASE_URL, NEON_DATABASE_URL, etc.).
4. Manejo y restauración ante excepciones internas del benchmark.
5. Limpieza garantizada de archivos temporales (tempfile.TemporaryDirectory).
6. Validación taxonómica completa: reglas contables positivas (contra-activos, intangibles, diferidos, patrimonio)
   y controles negativos (códigos inexistentes, no clasificables, familias incompatibles, cruces indebidos).
7. Cálculo honesto de métricas con denominadores explícitos y trazables.
"""

from __future__ import annotations

import json
import os
import pathlib
import socket
import sys
import tempfile
import pytest

from experiments.pilot_coverage.classification.benchmark_classifier_isolated import (
    ejecutar_benchmark_clasificador_aislado,
    isolated_benchmark_environment,
    validar_taxonomia_catalogo,
)

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# FRENTE 2: PRUEBAS DE AISLAMIENTO SIN CONTAMINACIÓN GLOBAL
# ---------------------------------------------------------------------------

def test_benchmark_aislamiento_socket_antes_del_benchmark_es_original():
    """1. Antes del benchmark, socket.socket conserva su implementación original."""
    # Verificar que no es _IsolatedSocket y tiene comportamiento estándar
    s = socket.socket()
    assert not s.__class__.__name__.startswith("_IsolatedSocket")
    s.close()


def test_benchmark_aislamiento_durante_contexto_falla_cerrado():
    """2. Durante el contexto, una conexión externa (connect o connect_ex) falla cerrada."""
    with isolated_benchmark_environment():
        s = socket.socket()
        with pytest.raises(RuntimeError, match=r"Acceso a red bloqueado"):
            s.connect(("127.0.0.1", 5432))
        with pytest.raises(RuntimeError, match=r"Acceso a red bloqueado"):
            s.connect_ex(("127.0.0.1", 5432))
        s.close()


def test_benchmark_aislamiento_despues_del_benchmark_restaura_socket_exacto():
    """3. Después del benchmark, socket.socket es exactamente el objeto original."""
    orig_socket_cls = socket.socket
    with isolated_benchmark_environment():
        pass
    assert socket.socket is orig_socket_cls, "socket.socket debe ser exactamente el objeto original tras salir del contexto"


def test_benchmark_aislamiento_restaura_variables_entorno_exactas():
    """4. Las variables de entorno recuperan exactamente sus valores anteriores."""
    os.environ["DATABASE_URL"] = "postgresql://test_user:test_pass@localhost:5432/test_db"
    os.environ["NEON_DATABASE_URL"] = "postgresql://neon_user:neon_pass@neon.tech/test_db"
    os.environ["MI_VARIABLE_CUSTOM"] = "valor_previo"

    try:
        with isolated_benchmark_environment():
            assert "DATABASE_URL" not in os.environ
            assert "NEON_DATABASE_URL" not in os.environ
            assert os.environ.get("STREAMLIT_SERVER_HEADLESS") == "true"

        assert os.environ.get("DATABASE_URL") == "postgresql://test_user:test_pass@localhost:5432/test_db"
        assert os.environ.get("NEON_DATABASE_URL") == "postgresql://neon_user:neon_pass@neon.tech/test_db"
        assert os.environ.get("MI_VARIABLE_CUSTOM") == "valor_previo"
    finally:
        os.environ.pop("DATABASE_URL", None)
        os.environ.pop("NEON_DATABASE_URL", None)
        os.environ.pop("MI_VARIABLE_CUSTOM", None)


def test_benchmark_aislamiento_excepcion_interna_restaura_todo():
    """5. Una excepción interna dentro del context manager también restaura socket y entorno."""
    orig_socket_cls = socket.socket
    os.environ["DATABASE_URL"] = "test_url_preserved"

    with pytest.raises(ValueError, match="Error simulado"):
        with isolated_benchmark_environment():
            assert "DATABASE_URL" not in os.environ
            raise ValueError("Error simulado dentro del benchmark")

    assert socket.socket is orig_socket_cls
    assert os.environ.get("DATABASE_URL") == "test_url_preserved"
    os.environ.pop("DATABASE_URL", None)


def test_benchmark_aislamiento_imports_diferidos_bloquean_red_y_ocultan_env():
    """5b. Verifica que durante la importación dentro del contexto aislado, DATABASE_URL no exista y la red falle cerrada."""
    os.environ["DATABASE_URL"] = "postgresql://blocked_user@neon.tech/test_db"
    os.environ["NEON_DATABASE_URL"] = "postgresql://blocked_user@neon.tech/test_db"

    try:
        with isolated_benchmark_environment():
            assert "DATABASE_URL" not in os.environ
            assert "NEON_DATABASE_URL" not in os.environ

            from pipeline.homologation_pipeline import HomologationPipeline
            from app_validacion import MotorHibridoLocal
            from parser_universal import ParserPDF

            assert HomologationPipeline is not None
            assert MotorHibridoLocal is not None
            assert ParserPDF is not None

            s = socket.socket()
            with pytest.raises(RuntimeError, match="Acceso a red bloqueado"):
                s.connect(("neon.tech", 5432))
            s.close()

        assert os.environ.get("DATABASE_URL") == "postgresql://blocked_user@neon.tech/test_db"
        assert os.environ.get("NEON_DATABASE_URL") == "postgresql://blocked_user@neon.tech/test_db"
    finally:
        os.environ.pop("DATABASE_URL", None)
        os.environ.pop("NEON_DATABASE_URL", None)


def test_benchmark_aislamiento_proceso_limpio_subprocess():
    """
    5c. Objetivo 1 (A8): Ejecuta un subproceso Python completamente limpio con sys.executable
    para verificar que los módulos productivos no estaban en sys.modules antes del aislamiento,
    que se importan por primera vez dentro del contexto aislado, que la red falla cerrada y
    que el entorno se restaura al salir.
    """
    import subprocess

    code = '''
import os
import sys
import socket

# 1. Definir variables de entorno antes de importar módulos
os.environ["DATABASE_URL"] = "postgresql://blocked_user:pass@neon.tech/test_db"
os.environ["NEON_DATABASE_URL"] = "postgresql://blocked_user:pass@neon.tech/test_db"
os.environ["CONTROL_RESTORATION_VAR"] = "control_value_12345"

# 2. Confirmar que módulos productivos NO están en sys.modules
modulos_productivos = ["pipeline.homologation_pipeline", "app_validacion", "parser_universal"]
for mod in modulos_productivos:
    if mod in sys.modules:
        sys.exit(101)

# 3. Importar únicamente el context manager aislado
from experiments.pilot_coverage.classification.benchmark_classifier_isolated import (
    isolated_benchmark_environment,
)

orig_socket_cls = socket.socket

# 4. Entrar al contexto aislado
with isolated_benchmark_environment():
    if "DATABASE_URL" in os.environ:
        sys.exit(102)
    if "NEON_DATABASE_URL" in os.environ:
        sys.exit(103)
    if os.environ.get("CONTROL_RESTORATION_VAR") != "control_value_12345":
        sys.exit(104)

    s = socket.socket()
    try:
        s.connect(("127.0.0.1", 5432))
        sys.exit(105)
    except RuntimeError:
        pass

    try:
        s.connect_ex(("127.0.0.1", 5432))
        sys.exit(106)
    except RuntimeError:
        pass
    s.close()

    # 5. Importar por primera vez los módulos productivos dentro del contexto
    import pipeline.homologation_pipeline
    import app_validacion
    import parser_universal

    for mod in modulos_productivos:
        if mod not in sys.modules:
            sys.exit(107)

    s2 = socket.socket()
    try:
        s2.connect(("neon.tech", 5432))
        sys.exit(108)
    except RuntimeError:
        pass
    s2.close()

# 6. Fuera del contexto: verificar restauración exacta
if socket.socket is not orig_socket_cls:
    sys.exit(109)
if os.environ.get("DATABASE_URL") != "postgresql://blocked_user:pass@neon.tech/test_db":
    sys.exit(110)
if os.environ.get("NEON_DATABASE_URL") != "postgresql://blocked_user:pass@neon.tech/test_db":
    sys.exit(111)
if os.environ.get("CONTROL_RESTORATION_VAR") != "control_value_12345":
    sys.exit(112)

s_local = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
if s_local.fileno() < 0:
    sys.exit(113)
s_local.close()

print("SUBPROCESS_ISOLATION_OK")
'''

    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)

    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=env,
    )

    assert proc.returncode == 0, f"Fallo en subproceso limpio (rc={proc.returncode}):\\nSTDOUT: {proc.stdout}\\nSTDERR: {proc.stderr}"
    assert "SUBPROCESS_ISOLATION_OK" in proc.stdout


def test_benchmark_socket_normal_crear_y_cerrar_posterior():
    """6. Una prueba posterior puede crear y cerrar un socket normal sin conectarse."""
    _ = ejecutar_benchmark_clasificador_aislado()

    # Crear y cerrar socket sin excepciones
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    assert s.fileno() >= 0
    s.close()


def test_benchmark_limpieza_directorios_temporales():
    """7. Verifica que no queden bases SQLite ni directorios temporales residuales tras la ejecución."""
    tmp_base = pathlib.Path(tempfile.gettempdir())
    antes = set(tmp_base.glob("isolated_bench_*"))

    _ = ejecutar_benchmark_clasificador_aislado()

    despues = set(tmp_base.glob("isolated_bench_*"))
    nuevos_residuales = despues - antes
    assert len(nuevos_residuales) == 0, f"Quedaron directorios temporales sin limpiar: {nuevos_residuales}"


def test_benchmark_no_modifica_archivos_del_proyecto():
    """Verifica que la ejecución del benchmark no altere diccionarios, catálogos ni DBs productivas."""
    cat_path = PROJECT_ROOT / "catalogo_maestro.json"
    dic_path = PROJECT_ROOT / "diccionario.json"

    mtime_cat_before = cat_path.stat().st_mtime
    mtime_dic_before = dic_path.stat().st_mtime

    m = ejecutar_benchmark_clasificador_aislado()
    assert isinstance(m, dict)

    assert cat_path.stat().st_mtime == mtime_cat_before, "catalogo_maestro.json no debe ser modificado"
    assert dic_path.stat().st_mtime == mtime_dic_before, "diccionario.json no debe ser modificado"


# ---------------------------------------------------------------------------
# FRENTE 3: VALIDACIÓN CONTABLE Y PRUEBAS NEGATIVAS DE TAXONOMÍA
# ---------------------------------------------------------------------------

def test_benchmark_taxonomia_casos_obligatorios_contra_activos_y_diferidos():
    """Verifica el cumplimiento de las reglas contables obligatorias del catálogo maestro."""
    catalogo = json.loads((PROJECT_ROOT / "catalogo_maestro.json").read_text())
    validar_taxonomia_catalogo(catalogo)

    # 1. Depreciación Acumulada Maquinarias -> ANC.01.01 (contra-activo)
    assert "ANC.01.01" in catalogo
    item_dep = catalogo["ANC.01.01"]
    assert item_dep["categoria"] == "activo_no_corriente"
    assert item_dep["naturaleza"] == "acreedora"
    assert item_dep["signo_normal"] == -1

    # 2. Amortización Acumulada Intangibles -> ANC.03
    assert "ANC.03" in catalogo
    item_amort = catalogo["ANC.03"]
    assert item_amort["categoria"] == "activo_no_corriente"
    assert "intangib" in item_amort["nombre_estandar"].lower() or "intangib" in item_amort["descripcion"].lower()

    # 3. Pérdidas Acumuladas -> PAT.03
    assert "PAT.03" in catalogo
    item_pat = catalogo["PAT.03"]
    assert item_pat["categoria"] == "patrimonio"

    # 4. Impuestos Diferidos Activo -> ANC.09
    assert "ANC.09" in catalogo
    item_imp_act = catalogo["ANC.09"]
    assert item_imp_act["categoria"] == "activo_no_corriente"

    # 5. Impuestos Diferidos Pasivo -> PNC.06
    assert "PNC.06" in catalogo
    item_imp_pas = catalogo["PNC.06"]
    assert item_imp_pas["categoria"] == "pasivo_no_corriente"


def test_benchmark_taxonomia_negativa_codigo_inexistente():
    """Prueba negativa: Rechazo estricto si se define un código inexistente en el catálogo."""
    catalogo = json.loads((PROJECT_ROOT / "catalogo_maestro.json").read_text())
    casos_invalidos = [{"nombre": "Cuenta Fantasma", "tipo": "ACTIVO", "esperado": "FAKE.999"}]
    with pytest.raises(ValueError, match=r"Código esperado 'FAKE.999'.*no existe en catalogo_maestro.json"):
        validar_taxonomia_catalogo(catalogo, casos=casos_invalidos)


def test_benchmark_taxonomia_negativa_codigo_no_clasificable():
    """Prueba negativa: Rechazo si el código esperado está marcado como clasificable=False."""
    catalogo = json.loads((PROJECT_ROOT / "catalogo_maestro.json").read_text())
    cat_mod = dict(catalogo)
    cat_mod["AC.01"] = dict(cat_mod["AC.01"], clasificable=False)
    casos = [{"nombre": "Caja", "tipo": "ACTIVO", "esperado": "AC.01"}]
    with pytest.raises(ValueError, match=r"marcado como NO clasificable"):
        validar_taxonomia_catalogo(cat_mod, casos=casos)


def test_benchmark_taxonomia_negativa_familia_incompatible():
    """Prueba negativa: Rechazo si el prefijo del código no coincide con su categoría."""
    catalogo = json.loads((PROJECT_ROOT / "catalogo_maestro.json").read_text())
    cat_mod = dict(catalogo)
    cat_mod["AC.99"] = {"categoria": "pasivo_corriente", "clasificable": True, "nombre_estandar": "Error"}
    casos = [{"nombre": "Error Familia", "tipo": "ACTIVO", "esperado": "AC.99"}]
    with pytest.raises(ValueError, match=r"categoría 'pasivo_corriente' incompatible"):
        validar_taxonomia_catalogo(cat_mod, casos=casos)


def test_benchmark_taxonomia_negativa_contra_cuenta_como_pasivo():
    """Prueba negativa: Rechazo si Depreciación Acumulada se asigna a un código de pasivo comercial."""
    catalogo = json.loads((PROJECT_ROOT / "catalogo_maestro.json").read_text())
    casos = [{"nombre": "Depreciación Acumulada Maquinarias", "tipo": "PASIVO", "esperado": "PC.01"}]
    with pytest.raises(ValueError, match=r"debe mapear a ANC.01.01"):
        validar_taxonomia_catalogo(catalogo, casos=casos)


def test_benchmark_taxonomia_negativa_resultado_como_activo():
    """Prueba negativa: Rechazo si una cuenta de resultado se asigna a código de activo de balance."""
    catalogo = json.loads((PROJECT_ROOT / "catalogo_maestro.json").read_text())
    casos = [{"nombre": "Ingresos por Ventas", "tipo": "RESULTADOS", "esperado": "AC.01"}]
    with pytest.raises(ValueError, match=r"Cuenta de resultados 'Ingresos por Ventas' asignada erróneamente"):
        validar_taxonomia_catalogo(catalogo, casos=casos)


def test_benchmark_taxonomia_negativa_anc02_para_amortizacion_intangibles():
    """Prueba negativa: Rechazo si Amortización Intangibles se asigna a ANC.02 (Propiedades de Inversión)."""
    catalogo = json.loads((PROJECT_ROOT / "catalogo_maestro.json").read_text())
    casos = [{"nombre": "Amortización Acumulada Intangibles", "tipo": "PASIVO", "esperado": "ANC.02"}]
    with pytest.raises(ValueError, match=r"Amortización acumulada intangibles debe ser ANC.03"):
        validar_taxonomia_catalogo(catalogo, casos=casos)


# ---------------------------------------------------------------------------
# MÉTRICAS Y DENOMINADORES
# ---------------------------------------------------------------------------

def test_benchmark_metricas_denominadores_y_cobertura_trazable():
    """Verifica la integridad de las fórmulas y denominadores del reporte de métricas."""
    m = ejecutar_benchmark_clasificador_aislado()

    assert m["total_muestra"] == 18
    assert m["total_inequivocos"] == 7
    assert m["total_abstencion"] == 11

    # 7 inequívocos automáticos y correctos
    assert m["auto_correctas"] == 7
    assert m["auto_incorrectas"] == 0
    assert m["auto_indebidas_abstencion"] == 0
    assert m["revisiones_justificadas"] == 11
    assert m["revisiones_evitables"] == 0

    assert m["precision_automatica"] == 1.0
    assert m["cobertura_automatica_inequivocos"] == 1.0
    assert abs(m["cobertura_muestra_completa"] - (7 / 18)) < 1e-6

    # Sugerencias UI
    assert m["denominador_alternativas_catalogo"] == 14
    assert m["top1_hits"] == 9
    assert m["top3_hits"] == 12
    assert abs(m["tasa_top1"] - (9 / 14)) < 1e-6
    assert abs(m["tasa_top3"] - (12 / 14)) < 1e-6
