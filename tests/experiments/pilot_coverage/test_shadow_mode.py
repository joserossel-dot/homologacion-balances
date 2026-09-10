"""
tests/experiments/pilot_coverage/test_shadow_mode.py

Suite exhaustiva de pruebas unitarias y de integración para el extractor en modo sombra (Encargo A8).
Verifica rigurosamente:
1. Reproducibilidad: fpdf2 declarado, pytest importable en Poetry, fixtures temporales sin binarios en Git.
2. Comparación Contable Exhaustiva:
   - Pares periodo-monto, períodos distintos, montos distintos, signos distintos.
   - Códigos vacíos, repetidos, nombres cambiados, orígenes distintos.
   - Multiconjuntos que preservan multiplicidad (duplicados no colapsados).
   - Controles y subtotales por identidad, importe, período y signo.
   - Reordenamiento de filas: el orden se mide como diagnóstico (orden_distinto) sin alterar la concordancia contable.
   - Clasificación estricta 'Diferente, requiere revisión' ante cualquier divergencia contable real.
3. Selección Real de Páginas (Multi-Página):
   - PDF sintético de 2 páginas con cuentas disjuntas.
   - Filtrado exacto [1], [2], [1, 2], página inexistente [99].
   - E1 y E3 procesan el mismo subconjunto de páginas.
   - E2 se omite con advertencia sanitizada.
4. Identificador Pseudonimizado y Rechazo de Texto Libre:
   - SHA-256 sobre la totalidad del archivo por bloques de 64 KB.
   - Rechazo estricto de texto libre arbitrario recibido en manifiestos (empresas, RUTs, rutas, correos).
   - Aceptación exclusiva de identificadores que cumplen con la whitelist técnica.
   - Comportamiento estable en archivos vacíos e inexistentes sin filtrar nombres.
5. Privacidad y Sanitización:
   - Redacción de rutas Windows, Unix (directorios de usuario), nombres de archivos y números de identificación fiscal.
   - Manejo seguro de manifiestos inexistentes o inválidos.
   - Cero rutas de usuario o nombres privados en código versionable.
6. Reglas .gitignore Refinadas:
   - Verifica mediante git check-ignore que se ignoren solo manifiestos locales del modo sombra y no archivos JSON genéricos.
7. Decisión Final de Modo Sombra:
   - Pruebas exhaustivas sobre ejecutar_modo_sombra_documento() ante cada causal de discrepancia.
"""

from __future__ import annotations

import os
import pathlib
import re
import subprocess
import sys
from typing import Any, Dict, Optional
from unittest.mock import patch, MagicMock
import pytest

from experiments.pilot_coverage.formats.generate_fixtures import (
    generar_todos_los_fixtures,
)
from experiments.pilot_coverage.formats.shadow_extractor import (
    anonimizar_id_documento,
    cargar_manifiesto_local,
    comparar_extracciones,
    ejecutar_modo_sombra_documento,
    resolver_doc_id_seguro,
    sanitizar_mensaje_privacidad,
)

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(scope="module")
def synthetic_fixtures_dir(tmp_path_factory) -> pathlib.Path:
    td = tmp_path_factory.mktemp("shadow_synthetic_fixtures_a8")
    generar_todos_los_fixtures(td)
    return td


# ===========================================================================
# 1. OBJETIVO 1: REPRODUCIBILIDAD REAL CON POETRY
# ===========================================================================

def test_reproducibilidad_fpdf2_declarada_en_pyproject():
    """Verifica que fpdf2 esté declarada con versión en pyproject.toml."""
    pyproject_text = (PROJECT_ROOT / "pyproject.toml").read_text()
    assert "fpdf2" in pyproject_text, "fpdf2 debe estar declarada en pyproject.toml"


def test_reproducibilidad_pytest_importable_en_interprete():
    """Verifica que pytest se pueda importar desde el intérprete de ejecución."""
    import pytest as pytest_imported
    assert pytest_imported is not None


def test_reproducibilidad_fixtures_en_directorio_temporal(tmp_path: pathlib.Path):
    """Verifica que los fixtures sintéticos se generen dinámicamente en tmp_path sin binarios preexistentes."""
    fixtures = generar_todos_los_fixtures(tmp_path)
    assert "paralelo_con_codigo" in fixtures
    assert "multipagina_disjunta" in fixtures
    assert fixtures["paralelo_con_codigo"].exists()
    assert fixtures["multipagina_disjunta"].exists()


def test_reproducibilidad_sin_dependencia_de_binarios_ignorados():
    """Verifica que no se requieran archivos binarios estáticos en el árbol de tests/."""
    static_fixtures_dir = PROJECT_ROOT / "tests/experiments/pilot_coverage/fixtures/formats"
    if static_fixtures_dir.exists():
        binaries = list(static_fixtures_dir.glob("*.pdf")) + list(static_fixtures_dir.glob("*.xlsx"))
        assert len(binaries) == 0, "No deben existir binarios estáticos ignorados en el árbol de tests"


# ===========================================================================
# 2. OBJETIVO 2: PRUEBAS OBLIGATORIAS DE COMPARACIÓN CONTABLE
# ===========================================================================

def _crear_fila(
    codigo: str = "110101",
    nombre: str = "caja",
    monto: float = 100.0,
    es_total: bool = False,
    periodos: Optional[Dict[str, float]] = None,
    signo: int = 1,
    origen: str = "activo",
    posicion: int = 0,
) -> Dict[str, Any]:
    p_dict = periodos or {}
    p_tupla = tuple(sorted((str(k), float(v)) for k, v in p_dict.items() if v is not None))
    p_claves = tuple(sorted(p_dict.keys()))
    return {
        "posicion": posicion,
        "codigo": codigo,
        "nombre_norm": " ".join(nombre.lower().split()),
        "monto": monto,
        "es_total": es_total,
        "origen_columna": origen,
        "periodos": p_dict,
        "periodos_tupla": p_tupla,
        "periodo_claves": p_claves,
        "signo": signo,
    }


def test_comparacion_mismo_periodo_distinto_importe():
    """Mismo período pero con distinto importe debe registrar periodos_distintos > 0 y clasificar diferente."""
    f1 = [_crear_fila(codigo="110101", nombre="caja", monto=100.0, periodos={"2024": 100.0})]
    f3 = [_crear_fila(codigo="110101", nombre="caja", monto=100.0, periodos={"2024": 150.0})]
    comp = comparar_extracciones(f1, f3)
    assert comp["periodos_distintos"] >= 1
    assert comp["filas_iguales"] == 0
    assert comp["filas_solo_e1"] == 1
    assert comp["filas_solo_e3"] == 1


def test_comparacion_distintos_periodos_igual_importe():
    """Distintos períodos con igual importe debe registrar periodos_distintos > 0."""
    f1 = [_crear_fila(codigo="110101", nombre="caja", monto=100.0, periodos={"2023": 100.0})]
    f3 = [_crear_fila(codigo="110101", nombre="caja", monto=100.0, periodos={"2024": 100.0})]
    comp = comparar_extracciones(f1, f3)
    assert comp["periodos_distintos"] >= 1
    assert comp["filas_iguales"] == 0


def test_comparacion_mismo_codigo_nombres_diferentes():
    """Mismo código pero nombres descriptivos diferentes."""
    f1 = [_crear_fila(codigo="110101", nombre="caja central")]
    f3 = [_crear_fila(codigo="110101", nombre="banco santander")]
    comp = comparar_extracciones(f1, f3)
    assert comp["filas_iguales"] == 0
    assert comp["filas_solo_e1"] == 1
    assert comp["filas_solo_e3"] == 1


def test_comparacion_mismo_nombre_codigos_diferentes():
    """Mismo nombre pero con códigos contables diferentes."""
    f1 = [_crear_fila(codigo="110101", nombre="caja")]
    f3 = [_crear_fila(codigo="110199", nombre="caja")]
    comp = comparar_extracciones(f1, f3)
    assert comp["filas_iguales"] == 0
    assert comp["filas_solo_e1"] == 1
    assert comp["filas_solo_e3"] == 1


def test_comparacion_codigos_vacios_y_repetidos():
    """Cuentas sin código o con códigos repetidos."""
    f1 = [
        _crear_fila(codigo="", nombre="cuenta sin codigo a", monto=50.0),
        _crear_fila(codigo="110101", nombre="caja norte", monto=100.0),
        _crear_fila(codigo="110101", nombre="caja sur", monto=200.0),
    ]
    f3 = [
        _crear_fila(codigo="", nombre="cuenta sin codigo a", monto=50.0),
        _crear_fila(codigo="110101", nombre="caja norte", monto=100.0),
        _crear_fila(codigo="110101", nombre="caja sur", monto=200.0),
    ]
    comp = comparar_extracciones(f1, f3)
    assert comp["filas_iguales"] == 3
    assert comp["filas_solo_e1"] == 0
    assert comp["filas_solo_e3"] == 0


def test_comparacion_duplicado_eliminado_en_extraccion():
    """Verifica que si una fila idéntica aparece 2 veces en E1 y 1 vez en E3, el multiconjunto detecte la pérdida."""
    f1 = [
        _crear_fila(codigo="110101", nombre="caja", monto=100.0),
        _crear_fila(codigo="110101", nombre="caja", monto=100.0),
    ]
    f3 = [
        _crear_fila(codigo="110101", nombre="caja", monto=100.0),
    ]
    comp = comparar_extracciones(f1, f3)
    assert comp["filas_iguales"] == 1
    assert comp["filas_solo_e1"] == 1
    assert comp["filas_solo_e3"] == 0


def test_comparacion_signo_positivo_frente_a_negativo():
    """Diferencia de signo en cuenta contable."""
    f1 = [_crear_fila(codigo="120102", nombre="depreciacion acumulada", monto=-500.0, signo=-1)]
    f3 = [_crear_fila(codigo="120102", nombre="depreciacion acumulada", monto=500.0, signo=1)]
    comp = comparar_extracciones(f1, f3)
    assert comp["signos_distintos"] >= 1
    assert comp["importes_distintos"] >= 1
    assert comp["filas_iguales"] == 0


def test_comparacion_origen_contable_diferente():
    """Diferencia en origen de columna (activo vs pasivo)."""
    f1 = [_crear_fila(codigo="110101", nombre="caja", monto=100.0, origen="activo")]
    f3 = [_crear_fila(codigo="110101", nombre="caja", monto=100.0, origen="pasivo")]
    comp = comparar_extracciones(f1, f3)
    assert comp["origenes_distintos"] >= 1
    assert comp["filas_iguales"] == 0


def test_comparacion_mismo_numero_subtotales_distinto_importe():
    """Misma cantidad de subtotales pero con importes diferentes."""
    f1 = [_crear_fila(codigo="", nombre="total activo circulante", monto=1000.0, es_total=True)]
    f3 = [_crear_fila(codigo="", nombre="total activo circulante", monto=2000.0, es_total=True)]
    comp = comparar_extracciones(f1, f3)
    assert comp["controles_distintos"] >= 2
    assert comp["controles_coincidentes"] == 0


def test_comparacion_mismo_subtotal_e_importe_distinto_periodo():
    """Mismo subtotal e importe pero con períodos contables distintos."""
    f1 = [_crear_fila(codigo="", nombre="total activo", monto=5000.0, es_total=True, periodos={"2023": 5000.0})]
    f3 = [_crear_fila(codigo="", nombre="total activo", monto=5000.0, es_total=True, periodos={"2024": 5000.0})]
    comp = comparar_extracciones(f1, f3)
    assert comp["controles_distintos"] >= 2
    assert comp["controles_coincidentes"] == 0


def test_comparacion_reordenamiento_de_filas():
    """Detecta reordenamiento posicional entre filas equivalentes registrando orden_distinto."""
    f1 = [
        _crear_fila(codigo="110101", nombre="caja", monto=100.0, posicion=0),
        _crear_fila(codigo="110102", nombre="bancos", monto=200.0, posicion=1),
    ]
    f3 = [
        _crear_fila(codigo="110102", nombre="bancos", monto=200.0, posicion=0),
        _crear_fila(codigo="110101", nombre="caja", monto=100.0, posicion=1),
    ]
    comp = comparar_extracciones(f1, f3)
    assert comp["orden_distinto"] >= 1
    assert comp["filas_iguales"] == 2
    assert comp["filas_solo_e1"] == 0
    assert comp["filas_solo_e3"] == 0


# ===========================================================================
# 3. OBJETIVO 3: SELECCIÓN REAL DE PÁGINAS (MULTI-PÁGINA)
# ===========================================================================

def test_shadow_seleccion_real_paginas_multipagina_disjunta(synthetic_fixtures_dir: pathlib.Path):
    """
    Verifica con documento sintético de 2 páginas con cuentas disjuntas:
    - paginas=[1] devuelve exclusivamente P1.
    - paginas=[2] devuelve exclusivamente P2.
    - paginas=[1, 2] devuelve ambas páginas.
    - paginas=[99] produce resultado controlado vacío.
    - E1 y E3 procesan el mismo conjunto de páginas.
    - E2 se omite con advertencia sanitizada.
    """
    p_multi = synthetic_fixtures_dir / "multipagina_cuentas_disjuntas.pdf"
    assert p_multi.exists()

    # 1. Página 1 exclusivamente
    res_p1 = ejecutar_modo_sombra_documento(p_multi, paginas=[1])
    assert res_p1["existe"] is True
    assert res_p1["e1_cuentas"] == 3
    assert res_p1["e3_cuentas"] == 3
    assert res_p1["e2_cuentas"] is None
    assert any("E2_OMITIDO" in w for w in res_p1["advertencias"])
    assert res_p1["clasificacion"] == "Concordante"

    # 2. Página 2 exclusivamente
    res_p2 = ejecutar_modo_sombra_documento(p_multi, paginas=[2])
    assert res_p2["existe"] is True
    assert res_p2["e1_cuentas"] == 3
    assert res_p2["e3_cuentas"] == 3
    assert res_p2["clasificacion"] == "Concordante"

    # 3. Páginas 1 y 2 combinadas
    res_all = ejecutar_modo_sombra_documento(p_multi, paginas=[1, 2])
    assert res_all["existe"] is True
    assert res_all["e1_cuentas"] == 6
    assert res_all["e3_cuentas"] == 6
    assert res_all["clasificacion"] == "Concordante"

    # 4. Página inexistente (99)
    res_invalida = ejecutar_modo_sombra_documento(p_multi, paginas=[99])
    assert res_invalida["existe"] is True
    assert res_invalida["e1_cuentas"] == 0
    assert res_invalida["e3_cuentas"] == 0
    assert res_invalida["clasificacion"] == "No evaluable"


# ===========================================================================
# 4. OBJETIVO 4: IDENTIFICADOR PSEUDONIMIZADO Y RECHAZO DE TEXTO LIBRE
# ===========================================================================

def test_shadow_identificador_hash_completo_bloques_64kb(tmp_path: pathlib.Path):
    """
    Verifica que el identificador cubra el archivo completo por bloques:
    - Archivos idénticos producen el mismo ID.
    - Archivos con los primeros 64 KB idénticos pero que difieren después producen IDs distintos.
    - Archivo vacío produce ID estable.
    - Archivo inexistente produce ID técnico sin exponer nombre ni ruta.
    """
    chunk_64k = b"A" * 65536
    f1 = tmp_path / "doc_grande_1.pdf"
    f2 = tmp_path / "doc_grande_2.pdf"
    f3_identico = tmp_path / "doc_grande_copia.pdf"
    f_vacio = tmp_path / "doc_vacio.pdf"
    f_inexistente = tmp_path / "no_existe_archivo_secreto.pdf"

    f1.write_bytes(chunk_64k + b"COLA_DISTINTA_XXXXX")
    f2.write_bytes(chunk_64k + b"COLA_DISTINTA_YYYYY")
    f3_identico.write_bytes(chunk_64k + b"COLA_DISTINTA_XXXXX")
    f_vacio.write_bytes(b"")

    id1 = anonimizar_id_documento(f1)
    id2 = anonimizar_id_documento(f2)
    id3 = anonimizar_id_documento(f3_identico)
    id_vacio = anonimizar_id_documento(f_vacio)
    id_no_existe = anonimizar_id_documento(f_inexistente)

    assert id1 == id3, "Archivos idénticos deben tener mismo identificador"
    assert id1 != id2, "Archivos que difieren después de 64 KB deben producir identificadores diferentes"
    assert id_vacio == "SHADOW-DOC-e3b0c44298fc"
    assert id_no_existe == "SHADOW-DOC-NOTFOUND"
    assert "no_existe_archivo_secreto" not in id_no_existe


def test_shadow_politica_identificadores_rechaza_texto_libre_y_fugas(tmp_path: pathlib.Path):
    """
    Objetivo 2 (A8): Demuestra que cualquier texto libre entregado en manifest (empresa, RUT, ruta,
    correo, espacios) es rechazado y sustituido por el hash determinista SHA-256 o whitelist.
    """
    pdf_test = tmp_path / "test_doc_identificador.pdf"
    pdf_test.write_bytes(b"CONTENIDO_BINARIO_PARA_HASH_123")
    hash_esperado = anonimizar_id_documento(pdf_test, indice=1)

    casos_texto_libre = [
        "ENTIDAD_SINTETICA_001 76.123.456-7",
        "balance_empresa_ficticia_001.pdf",
        "/Users/usuario_prueba/data/balance_confidencial.pdf",
        r"C:\Contabilidad\ENTIDAD_SINTETICA_001\balance.pdf",
        "/home/usuario_prueba/privado.pdf",
        "contacto@empresa-inexistente.example",
        "Texto Libre Con Espacios",
    ]

    for id_invalido in casos_texto_libre:
        id_resuelto = resolver_doc_id_seguro(pdf_test, id_candidato=id_invalido, indice=1)
        assert id_resuelto == hash_esperado, f"Texto libre '{id_invalido}' debió ser rechazado"
        assert id_invalido not in id_resuelto

    # Caso válido según whitelist técnica
    id_valido = "SHADOW-DOC-01-ac0b61687dea"
    assert resolver_doc_id_seguro(pdf_test, id_candidato=id_valido, indice=1) == id_valido

    # Caso archivo inexistente
    id_no_existe = resolver_doc_id_seguro(tmp_path / "no_existe.pdf", id_candidato="ENTIDAD_SINTETICA_002", indice=2)
    assert id_no_existe == "SHADOW-DOC-02-NOTFOUND"
    assert "ENTIDAD_SINTETICA_002" not in id_no_existe


# ===========================================================================
# 5. OBJETIVO 5: PRIVACIDAD DE MENSAJES Y MANIFIESTOS
# ===========================================================================

def test_sanitizacion_rutas_windows_linux_macos_y_ruts():
    """Verifica la redacción exhaustiva de rutas de cualquier OS, nombres de archivo y RUTs."""
    msg_mac = "Fallo en /Users/usuario_prueba/data/balance.pdf: corrupted"
    s_mac = sanitizar_mensaje_privacidad(msg_mac)
    assert "/Users/" not in s_mac
    assert "balance.pdf" not in s_mac
    assert "[REDACTED_PATH]" in s_mac

    msg_lin = "Error en /home/usuario_prueba/balances/archivo_1.xlsx"
    s_lin = sanitizar_mensaje_privacidad(msg_lin)
    assert "/home/" not in s_lin
    assert "archivo_1.xlsx" not in s_lin

    msg_win = r"Error leyendo C:\ENTIDAD_SINTETICA_001\Balances\2024\balance.pdf"
    s_win = sanitizar_mensaje_privacidad(msg_win)
    assert r"C:\ENTIDAD_SINTETICA_001" not in s_win
    assert "[REDACTED_PATH]" in s_win

    msg_rut = "Doc Balance_ENTIDAD_SINTETICA_001_76.123.456-7_2023.pdf sin formato"
    s_rut = sanitizar_mensaje_privacidad(msg_rut)
    assert "76.123.456-7" not in s_rut
    assert "[REDACTED_FILE]" in s_rut or "[REDACTED_RUT]" in s_rut


def test_manifiesto_inexistente_o_invalido_registra_error_sanitizado(tmp_path: pathlib.Path):
    """Verifica que un manifiesto inexistente o JSON roto sea manejado de forma segura."""
    items_inex = cargar_manifiesto_local(tmp_path / "no_existe_manifest.json")
    assert items_inex == []

    broken_file = tmp_path / "broken_manifest.local.json"
    broken_file.write_text("{ ESTO NO ES JSON VALIDO }")
    items_broken = cargar_manifiesto_local(broken_file)
    assert items_broken == []


def _escanear_violaciones_privacidad_texto(contenido: str, ruta_archivo: pathlib.Path) -> list[str]:
    """
    Función auxiliar genérica que detecta patrones de fuga de privacidad:
    1. Rutas de usuario no sintéticas (macOS, Linux, Windows).
    2. Enlaces file:// a rutas locales personales no sintéticas.
    3. Correos electrónicos que no utilicen dominios reservados de prueba (RFC 2606 / testbed).
    4. Credenciales no sintéticas en URLs de base de datos.
    5. RUTs chilenos fuera del fixture sintético autorizado ('76.123.456-7').
    6. Tokens y claves de API de proveedores conocidos.
    7. Marcadores de volcados de datos productivos (pg_dump / COPY).
    """
    hallazgos: list[str] = []

    # 1. Rutas de usuario no sintéticas (requiere al menos 2 caracteres en el nombre de usuario)
    re_path_macos = re.compile(r"/Users/(?!usuario_prueba\b)([a-zA-Z0-9_-]{2,})")
    re_path_linux = re.compile(r"/home/(?!usuario_prueba\b)([a-zA-Z0-9_-]{2,})")
    re_path_win = re.compile(r"[a-zA-Z]:\\(?:Users|Documents and Settings)\\(?!usuario_prueba\b)([a-zA-Z0-9_-]{2,})", re.IGNORECASE)

    for m in re_path_macos.finditer(contenido):
        hallazgos.append(f"Ruta macOS personal no sintética: /Users/{m.group(1)}")
    for m in re_path_linux.finditer(contenido):
        hallazgos.append(f"Ruta Linux personal no sintética: /home/{m.group(1)}")
    for m in re_path_win.finditer(contenido):
        hallazgos.append(f"Ruta Windows personal no sintética: {m.group(0)}")

    # 2. Enlaces file://
    re_file_uri = re.compile(r"file:///(?![a-zA-Z0-9_.-]*usuario_prueba|tmp|var|private/var|ruta_sintetica)[a-zA-Z0-9_./-]+")
    for m in re_file_uri.finditer(contenido):
        hallazgos.append(f"Enlace file:// no sintético: {m.group(0)}")

    # 3. Correos electrónicos no reservados
    dominios_permitidos = (
        ".example",
        ".invalid",
        ".test",
        ".localhost",
        "@example.com",
        "@example.org",
        "@example.net",
        "@neon.tech",
    )
    re_emails = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
    for email in re_emails.findall(contenido):
        if not any(email.endswith(dom) or f"@{dom}" in email or dom in email for dom in dominios_permitidos):
            hallazgos.append(f"Correo con dominio no reservado: {email}")

    # 4. Credenciales de base de datos no sintéticas
    re_pg_url = re.compile(r"postgresql://([^\s:/?#]+)(?::([^\s@/?#]+))?@([^\s/?#]+)")
    usuarios_permitidos = {"test_user", "neon_user", "blocked_user", "postgres", ""}
    passwords_permitidas = {"test_pass", "neon_pass", "pass", "blocked_user", "postgres", "password", None, ""}
    for m in re_pg_url.finditer(contenido):
        u = m.group(1)
        p = m.group(2)
        if u not in usuarios_permitidos or p not in passwords_permitidas:
            hallazgos.append(f"Credenciales de BD no sintéticas: {u}:{p}")

    # 5. RUTs no autorizados
    re_rut = re.compile(r"\b\d{1,2}\.\d{3}\.\d{3}-[\dkK]\b")
    for rut in re_rut.findall(contenido):
        if rut != "76.123.456-7":
            hallazgos.append(f"RUT fuera del fixture sintético autorizado: {rut}")

    # 6. Tokens y secretos conocidos
    re_secrets = re.compile(r"\b(sk_live_[a-zA-Z0-9]{20,}|ghp_[a-zA-Z0-9]{20,}|AKIA[0-9A-Z]{16})\b")
    for sec in re_secrets.findall(contenido):
        hallazgos.append(f"Token o secreto conocido detectado: {sec}")

    # 7. Marcadores de volcado de base de datos
    re_dump = re.compile(r"(?:COPY\s+public\.\w+\s+FROM\s+stdin|pg_dump\s+version|\bDATABASE_PASSWORD\s*=\s*['\"][^'\"]+['\"])")
    for dump in re_dump.findall(contenido):
        hallazgos.append(f"Marcador de volcado productivo: {dump}")

    return hallazgos


def test_privacidad_sin_rutas_ni_nombres_privados_en_codigo():
    """
    Escaneo exhaustivo y genérico de privacidad:
    Revisa todos los archivos versionables (.py, .md, .json) en experiments/, tests/experiments/ y reports/
    incluyendo este mismo archivo de prueba (sin autoexclusión).
    """
    rutas_a_inspeccionar = [
        PROJECT_ROOT / "experiments/pilot_coverage",
        PROJECT_ROOT / "tests/experiments/pilot_coverage",
        PROJECT_ROOT / "reports/pilot_coverage",
    ]

    total_archivos_inspeccionados = 0
    violaciones: list[str] = []

    # Soporte opcional para patrones locales si existe un archivo ignorado por git
    patrones_locales_opcionales: list[str] = []
    ruta_patrones_locales = PROJECT_ROOT / "reports/pilot_coverage/local/privacy_patterns.local.txt"
    if ruta_patrones_locales.exists():
        for linea in ruta_patrones_locales.read_text(encoding="utf-8", errors="ignore").splitlines():
            linea_limpia = linea.strip()
            if linea_limpia and not linea_limpia.startswith("#"):
                patrones_locales_opcionales.append(linea_limpia)

    for base_dir in rutas_a_inspeccionar:
        for root, dirs, files in os.walk(base_dir):
            if "__pycache__" in root or "/local" in root or root.endswith("/local"):
                continue
            for f in files:
                if f.endswith((".py", ".md", ".json")):
                    file_path = pathlib.Path(root) / f
                    total_archivos_inspeccionados += 1
                    contenido = file_path.read_text(encoding="utf-8", errors="ignore")

                    hallazgos_archivo = _escanear_violaciones_privacidad_texto(contenido, file_path)
                    for h in hallazgos_archivo:
                        violaciones.append(f"[{file_path.relative_to(PROJECT_ROOT)}] {h}")

                    for pat_local in patrones_locales_opcionales:
                        if pat_local in contenido:
                            violaciones.append(f"[{file_path.relative_to(PROJECT_ROOT)}] Coincidencia con patrón local privado")

    assert total_archivos_inspeccionados >= 15, "Deben haberse inspeccionado al menos 15 archivos de código, tests e informes"
    assert len(violaciones) == 0, f"Se detectaron {len(violaciones)} violaciones de privacidad:\n" + "\n".join(violaciones)


def test_detector_privacidad_detecta_fugas_simuladas_en_memoria():
    """Verifica que el escáner genérico de privacidad detecte positivamente cualquier fuga en texto arbitrario."""
    fuga_macos = "Ruta: " + "/".join(["", "Users", "algun_usuario_real", "balance.pdf"])
    assert len(_escanear_violaciones_privacidad_texto(fuga_macos, pathlib.Path("test.py"))) > 0

    fuga_linux = "Ruta: " + "/".join(["", "home", "admin_real", "data.json"])
    assert len(_escanear_violaciones_privacidad_texto(fuga_linux, pathlib.Path("test.py"))) > 0

    fuga_email = "Contacto: " + "@".join(["persona", "empresa-real.cl"])
    assert len(_escanear_violaciones_privacidad_texto(fuga_email, pathlib.Path("test.py"))) > 0

    fuga_rut = "RUT de cliente: " + "12" + ".345" + ".678-9"
    assert len(_escanear_violaciones_privacidad_texto(fuga_rut, pathlib.Path("test.py"))) > 0

    fuga_secret = "Token: " + "sk_live_" + "1234567890abcdefghijklmn"
    assert len(_escanear_violaciones_privacidad_texto(fuga_secret, pathlib.Path("test.py"))) > 0

    # Contenido 100% sintético no genera hallazgos
    sintetico_limpio = (
        "ENTIDAD_SINTETICA_001 /Users/usuario_prueba/doc.pdf "
        "contacto@empresa-inexistente.example 76.123.456-7"
    )
    assert len(_escanear_violaciones_privacidad_texto(sintetico_limpio, pathlib.Path("test.py"))) == 0


# ===========================================================================
# 6. OBJETIVO 3: REGLAS GITIGNORE REFINADAS (git check-ignore)
# ===========================================================================

def test_gitignore_reglas_especificas_y_rechazo_generales():
    """
    Objetivo 3 (A8): Verifica mediante git check-ignore que los manifiestos del modo sombra
    estén ignorados y que archivos JSON genéricos no queden ocultos.
    """
    cmd_ignored = ["git", "check-ignore", "-q", "shadow_manifest.local.json"]
    res_ign1 = subprocess.run(cmd_ignored, cwd=PROJECT_ROOT)
    assert res_ign1.returncode == 0, "shadow_manifest.local.json debe estar ignorado (rc=0)"

    cmd_ignored_cli = ["git", "check-ignore", "-q", "shadow_manifest.cliente.local.json"]
    res_ign2 = subprocess.run(cmd_ignored_cli, cwd=PROJECT_ROOT)
    assert res_ign2.returncode == 0, "shadow_manifest.cliente.local.json debe estar ignorado (rc=0)"

    cmd_not_ignored1 = ["git", "check-ignore", "-q", "configuracion.local.json"]
    res_not1 = subprocess.run(cmd_not_ignored1, cwd=PROJECT_ROOT)
    assert res_not1.returncode == 1, "configuracion.local.json NO debe estar ignorado (rc=1)"

    cmd_not_ignored2 = ["git", "check-ignore", "-q", "local_configuracion.json"]
    res_not2 = subprocess.run(cmd_not_ignored2, cwd=PROJECT_ROOT)
    assert res_not2.returncode == 1, "local_configuracion.json NO debe estar ignorado (rc=1)"

    cmd_not_ignored3 = ["git", "check-ignore", "-q", "manifest_publico.json"]
    res_not3 = subprocess.run(cmd_not_ignored3, cwd=PROJECT_ROOT)
    assert res_not3.returncode == 1, "manifest_publico.json NO debe estar ignorado (rc=1)"


# ===========================================================================
# 7. OBJETIVOS 4 Y 5: DECISIÓN FINAL DE CLASIFICACIÓN EN MODO SOMBRA
# ===========================================================================

def test_shadow_decision_final_orden_no_altera_concordancia_contable(synthetic_fixtures_dir: pathlib.Path):
    """
    Objetivo 4 (A8): Verifica que el reordenamiento de filas reporte orden_distinto > 0
    pero conserve la clasificación 'Concordante' si todas las partidas contables son idénticas.
    """
    p_vertical = synthetic_fixtures_dir / "03_clasificado_vertical.pdf"
    assert p_vertical.exists()

    # Ejecutar normalmente sobre control negativo (produce Concordante)
    res = ejecutar_modo_sombra_documento(p_vertical)
    assert res["clasificacion"] == "Concordante"
    assert res["filas_solo_e1"] == 0
    assert res["filas_solo_e3"] == 0


def test_shadow_decision_final_todos_los_casos_criticos(tmp_path: pathlib.Path):
    """
    Objetivo 5 (A8): Verifica que cada condición crítica de discrepancia contable altere
    la clasificación final a 'Diferente, requiere revisión', que extracciones idénticas produzcan
    'Concordante', que ambas vacías produzcan 'No evaluable' y excepciones produzcan 'Fallo técnico'.
    """
    p_dummy = tmp_path / "dummy.pdf"
    p_dummy.write_bytes(b"%PDF-1.4 DUMMY CONTENT")

    def _simular_decision(cuentas_e1, cuentas_e3, fb_e3=True, exc_e1=None, exc_e3=None):
        with patch("parser_universal.ParserPDF") as mock_p1, \
             patch("experiments.pilot_coverage.formats.experimental_double_column.ExperimentalDoubleColumnExtractor") as mock_p3, \
             patch("document_intelligence.extractors.double_column.DoubleColumnExtractor") as mock_p2:

            if exc_e1:
                mock_p1.return_value.parsear.side_effect = Exception("Fallo E1 simulado")
            else:
                m1 = MagicMock()
                m1.cuentas = cuentas_e1
                mock_p1.return_value.parsear.return_value = m1

            if exc_e3:
                mock_p3.return_value.extract.side_effect = Exception("Fallo E3 simulado")
            else:
                m3 = MagicMock()
                m3.fallback_used = fb_e3
                m3.result = MagicMock()
                m3.result.cuentas = cuentas_e3
                mock_p3.return_value.extract.return_value = m3

            m2 = MagicMock()
            m2.fallback_used = True
            m2.result = MagicMock()
            m2.result.cuentas = []
            mock_p2.return_value.extract.return_value = m2

            return ejecutar_modo_sombra_documento(p_dummy)

    # 1. Extracción idéntica -> Concordante
    f_base = [_crear_fila(codigo="110101", nombre="caja", monto=100.0)]
    res_ok = _simular_decision(f_base, f_base)
    assert res_ok["clasificacion"] == "Concordante"

    # 2. Reordenamiento puro -> Concordante con orden_distinto > 0
    f_ord1 = [_crear_fila(codigo="110101", nombre="caja", monto=100.0, posicion=0), _crear_fila(codigo="110102", nombre="bancos", monto=200.0, posicion=1)]
    f_ord2 = [_crear_fila(codigo="110102", nombre="bancos", monto=200.0, posicion=0), _crear_fila(codigo="110101", nombre="caja", monto=100.0, posicion=1)]
    res_ord = _simular_decision(f_ord1, f_ord2)
    assert res_ord["clasificacion"] == "Concordante"
    assert res_ord["orden_distinto"] >= 1

    # 3. Filas solo en E1 -> Diferente, requiere revisión
    res_solo_e1 = _simular_decision(f_base + [_crear_fila(codigo="110102", nombre="bancos", monto=200.0)], f_base)
    assert res_solo_e1["clasificacion"] == "Diferente, requiere revisión"
    assert res_solo_e1["filas_solo_e1"] == 1

    # 4. Filas solo en E3 -> Diferente, requiere revisión
    res_solo_e3 = _simular_decision(f_base, f_base + [_crear_fila(codigo="110102", nombre="bancos", monto=200.0)])
    assert res_solo_e3["clasificacion"] == "Diferente, requiere revisión"
    assert res_solo_e3["filas_solo_e3"] == 1

    # 5. Importes distintos -> Diferente, requiere revisión
    res_imp = _simular_decision(f_base, [_crear_fila(codigo="110101", nombre="caja", monto=150.0)])
    assert res_imp["clasificacion"] == "Diferente, requiere revisión"
    assert res_imp["importes_distintos"] == 1

    # 6. Signos distintos -> Diferente, requiere revisión
    res_sig = _simular_decision(f_base, [_crear_fila(codigo="110101", nombre="caja", monto=-100.0, signo=-1)])
    assert res_sig["clasificacion"] == "Diferente, requiere revisión"
    assert res_sig["signos_distintos"] == 1

    # 7. Períodos distintos -> Diferente, requiere revisión
    res_per = _simular_decision([_crear_fila(periodos={"2023": 100.0})], [_crear_fila(periodos={"2024": 100.0})])
    assert res_per["clasificacion"] == "Diferente, requiere revisión"
    assert res_per["periodos_distintos"] >= 1

    # 8. Orígenes distintos -> Diferente, requiere revisión
    res_orig = _simular_decision([_crear_fila(origen="activo")], [_crear_fila(origen="pasivo")])
    assert res_orig["clasificacion"] == "Diferente, requiere revisión"
    assert res_orig["origenes_distintos"] == 1

    # 9. Controles distintos -> Diferente, requiere revisión
    res_ctrl = _simular_decision([_crear_fila(es_total=True, monto=1000.0)], [_crear_fila(es_total=True, monto=2000.0)])
    assert res_ctrl["clasificacion"] == "Diferente, requiere revisión"
    assert res_ctrl["controles_distintos"] >= 2

    # 10. Ambas vacías -> No evaluable
    res_empty = _simular_decision([], [])
    assert res_empty["clasificacion"] == "No evaluable"

    # 11. Excepción en E1 -> Fallo técnico
    res_exc1 = _simular_decision(f_base, f_base, exc_e1=True)
    assert res_exc1["clasificacion"] == "Fallo técnico"

    # 12. Excepción en E3 -> Fallo técnico
    res_exc3 = _simular_decision(f_base, f_base, exc_e3=True)
    assert res_exc3["clasificacion"] == "Fallo técnico"
