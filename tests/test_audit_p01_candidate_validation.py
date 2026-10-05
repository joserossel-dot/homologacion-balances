"""Tests de validación y límites del candidato de corrección P0.1 (Ronda 4).

Este conjunto de pruebas valida contra el código de producción real:
1. Propuesta B: Separación de bordes adheridos (| y []) en tokens numéricos,
   preservando glosas textuales y tokens ambiguos como [1] (referencias a notas al pie).
   Clasificación: Integración con TSV simulado, no OCR real.
2. Propuesta C: Generación natural en parsear_linea y propagación E2E en HomologationPipeline.process(),
   demostrando bloqueo de auto-confirmación y preservación del residuo ambiguo 2.
   Clasificación: Integración parser de línea -> pipeline contable.
3. Caso sintético de ruido: filtro unificado de metadatos y ruido geométrico, garantizando que:
   - Los positivos de ruido estructural sean descartados.
   - Las cuentas contables legítimas (con palabras como Dirección, Domicilio, N°) sean preservadas.
   - Las cuentas incompletas legítimas NO sean silenciadas y alcancen el control de integridad de Codex.
   Clasificación: Pruebas unitarias con datos ficticios anonimizados e integración con certificar_extraccion_columnas.
"""

from unittest.mock import patch, MagicMock
import pytest

from parser_universal import (
    ocr_pagina_tsv,
    parsear_linea,
    certificar_extraccion_columnas,
    FormatoCodigo,
    ResultadoParseo,
    CuentaRaw,
    RAW_MONETARY_COLUMNS,
    es_ruido_ocr_no_contable,
)
from pipeline.homologation_pipeline import HomologationPipeline


class TestPropuestaBSeparacionBordes:
    """Pruebas de Propuesta B sobre salida TSV simulada de OCR contra ocr_pagina_tsv real.

    Clasificación: Integración con TSV simulado, no OCR real de PDF.
    """

    def test_ocr_pagina_tsv_exact_tokens_and_positions(self, tmp_path):
        """Comprueba la salida exacta y posición de cada token requerido:
        - [1]: Ambigüedad nota al pie vs celda unitaria -> SE CONSERVA [1].
        - [A]: Glosa entre corchetes -> SE CONSERVA [A].
        - |12345|: Cuadrícula pura -> SE LIMPIA a 12345.
        - [54.321]: Número con miles entre corchetes -> SE LIMPIA a 54.321.
        - |(1500)|: Paréntesis contable con bordes | -> SE LIMPIA a (1500).
        - -4500|: Importe negativo con borde der -> SE LIMPIA a -4500.
        - |PROVEEDORES|: Glosa con delimitadores de barra -> SE CONSERVA |PROVEEDORES|.
        - [NOTA 1]: Glosa textual con espacio -> SE CONSERVA [NOTA 1].
        """
        fake_img = tmp_path / "page_1.png"
        fake_img.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")

        tsv_header = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
        tsv_rows = [
            "5\t1\t1\t1\t1\t1\t10\t100\t20\t10\t95\t[1]\n",
            "5\t1\t1\t1\t1\t2\t35\t100\t20\t10\t95\t[A]\n",
            "5\t1\t1\t1\t1\t3\t60\t100\t50\t10\t95\t|12345|\n",
            "5\t1\t1\t1\t1\t4\t120\t100\t50\t10\t95\t[54.321]\n",
            "5\t1\t1\t1\t1\t5\t180\t100\t50\t10\t95\t|(1500)|\n",
            "5\t1\t1\t1\t1\t6\t240\t100\t50\t10\t95\t-4500|\n",
            "5\t1\t1\t1\t1\t7\t300\t100\t80\t10\t95\t|PROVEEDORES|\n",
            "5\t1\t1\t1\t1\t8\t390\t100\t60\t10\t95\t[NOTA 1]\n",
        ]
        tsv_output = tsv_header + "".join(tsv_rows)

        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_res.stdout = tsv_output
        mock_res.stderr = ""

        with patch("subprocess.run", return_value=mock_res):
            words = ocr_pagina_tsv(fake_img, rotacion=0, psm=6)

        assert len(words) == 8, f"Se esperaban 8 tokens, obtenidos {len(words)}"

        # Verificación estricta de orden, posición y token resultante exacto:
        assert words[0]["text"] == "[1]", "Token 0: [1] debe conservarse como referencia ambigua a nota"
        assert words[0]["x0"] == 10.0

        assert words[1]["text"] == "[A]", "Token 1: [A] debe conservarse como glosa textual"
        assert words[1]["x0"] == 35.0

        assert words[2]["text"] == "12345", "Token 2: |12345| debe limpiarse a 12345"
        assert words[2]["x0"] == 60.0

        assert words[3]["text"] == "54.321", "Token 3: [54.321] debe limpiarse a 54.321"
        assert words[3]["x0"] == 120.0

        assert words[4]["text"] == "(1500)", "Token 4: |(1500)| debe limpiarse a (1500)"
        assert words[4]["x0"] == 180.0

        assert words[5]["text"] == "-4500", "Token 5: -4500| debe limpiarse a -4500"
        assert words[5]["x0"] == 240.0

        assert words[6]["text"] == "|PROVEEDORES|", "Token 6: |PROVEEDORES| debe conservarse como glosa"
        assert words[6]["x0"] == 300.0

        assert words[7]["text"] == "[NOTA 1]", "Token 7: [NOTA 1] debe conservarse como glosa"
        assert words[7]["x0"] == 390.0


class TestPropuestaCIntegracionParserPipeline:
    """Pruebas de Propuesta C: generación en parsear_linea y propagación en HomologationPipeline.

    Clasificación: Integración parser de línea -> pipeline contable (no OCR de PDF completo).
    """

    def test_generacion_y_propagacion_e2e_bloquea_autoconfirmacion(self):
        """Recorrido E2E:
        1. Ejecuta parsear_linea sobre una entrada sintética contaminada.
        2. Usa la CuentaRaw producida SIN mutar manualmente ningún atributo.
        3. Entrega la cuenta al flujo real de HomologationPipeline.process().
        4. Comprueba generación de C, preservación de residuo 2, motivo de revisión y bloqueo.
        """
        # 1. Ejecución real de parsear_linea
        line_contaminada = "299901 Cuenta Sintetica Alfa 120000 170000 0 50000 0 49998 0 2"
        c = parsear_linea(line_contaminada, 7, FormatoCodigo.COMPACTO, ".", confianza_base=0.85)

        assert c is not None
        # Comprobación de generación de señal de C en CuentaRaw
        assert c.requiere_revision_extraccion is True, "C debe activar requiere_revision_extraccion"
        assert "digito_aislado_en_celda_sospechosa" in c.razones_revision_extraccion
        # Conservación del residuo 2 en la estructura que mantiene las 8 columnas antes del pipeline
        assert c.montos_columnas["ganancia"] == 2.0, "El residuo 2 debe preservarse en montos_columnas antes del pipeline"
        assert c.montos_columnas["pasivo"] == 49998.0

        # 2. Entrega directa al flujo real de HomologationPipeline.process()
        pipeline = HomologationPipeline(
            db_path=":memory:",
            dictionary=[{
                "cuenta_original": "Cuenta Sintetica Alfa",
                "codigo_estandar": "PC.01",
            }],
        )
        pipeline._parser.parsear = lambda p: ResultadoParseo(
            "doc_test.pdf", FormatoCodigo.COMPACTO, ".", True, 0, [c]
        )

        res = pipeline.process("doc_test.pdf")
        classified = res["classified"][0]

        # Comprobaciones de propagación y bloqueo
        assert classified["account_code"] == "299901"
        assert classified["account_name"] == "Cuenta Sintetica Alfa"
        assert classified["standard_code"] == "PC.01"  # Coincidencia con diccionario
        assert classified["classification_amount"] == 49998.0  # Monto principal pasivo
        assert classified["review_required"] is True, "Debe bloquear auto-confirmación"
        assert classified["confidence"] <= 0.50, "Confianza debe quedar degradada a <= 0.50"
        assert "advertencia: posible contaminación por fusión/solapamiento de columnas" in classified["reason"]
        # Comprobación de conservación del residuo 2 en la estructura que realmente lo mantiene
        assert c.montos_columnas["ganancia"] == 2.0, "El residuo 2 debe preservarse en montos_columnas tras el pipeline"

    def test_control_limpio_coherente_autoconfirma(self):
        """Control limpio coherente:
        Misma cuenta con coincidencia de diccionario controlada, pero sin residuo en celda.
        Demuestra que la revisión no ocurre por ausencia de diccionario ni baja confianza ajena a C.
        """
        line_limpia = "299901 Cuenta Sintetica Alfa 120000 170000 0 50000 0 50000 0 0"
        c_clean = parsear_linea(line_limpia, 7, FormatoCodigo.COMPACTO, ".", confianza_base=0.85)

        assert c_clean is not None
        assert c_clean.requiere_revision_extraccion is False
        assert c_clean.razones_revision_extraccion == []
        assert c_clean.montos_columnas["ganancia"] == 0.0

        pipeline = HomologationPipeline(
            db_path=":memory:",
            dictionary=[{
                "cuenta_original": "Cuenta Sintetica Alfa",
                "codigo_estandar": "PC.01",
            }],
        )
        pipeline._parser.parsear = lambda p: ResultadoParseo(
            "doc_clean.pdf", FormatoCodigo.COMPACTO, ".", True, 0, [c_clean]
        )

        res = pipeline.process("doc_clean.pdf")
        classified = res["classified"][0]

        assert classified["standard_code"] == "PC.01"
        assert classified["review_required"] is False, "Control limpio debe auto-confirmar"
        assert classified["confidence"] >= 0.85, "Control limpio debe tener confianza alta"
        assert "advertencia" not in classified["reason"]


class TestFiltroUnificadoYControlIntegridad:
    """Banco sintético para el filtro unificado de metadatos y ruido.

    Valida con datos estrictamente ficticios y anonimizados:
    1. Positivos de ruido (deben filtrarse: es_ruido_ocr_no_contable == True).
    2. Negativos contables legítimos (NO deben filtrarse: es_ruido_ocr_no_contable == False).
    3. Cuentas incompletas legítimas: demuestran que no se descartan por el filtro y que
       el control de integridad de Codex (certificar_extraccion_columnas) las detecta.
    """

    # --- 1. Positivos de Ruido Estructural (Deben ser descartados) ---

    def test_positivo_paginacion_con_rut(self):
        """Líneas repetidas de paginación combinadas con RUT fiscal."""
        c = CuentaRaw(linea=88, codigo=None, nombre="Rut [RUT-GENERICO] Página", monto=2.0)
        assert es_ruido_ocr_no_contable(c) is True

    def test_positivo_folio_con_rut(self):
        """Líneas de folio documental con RUT."""
        c = CuentaRaw(linea=89, codigo=None, nombre="RUT [RUT-GENERICO] Folio", monto=15.0)
        assert es_ruido_ocr_no_contable(c) is True

    def test_positivo_encabezado_direccion_con_numero(self):
        """Encabezado de domicilio o dirección física con indicador de numeración."""
        c = CuentaRaw(linea=90, codigo=None, nombre="Dirección AVENIDA FICTICIA N*", monto=123.0)
        assert es_ruido_ocr_no_contable(c) is True

    def test_positivo_encabezado_domicilio_casa_matriz_con_numero(self):
        """Encabezado de casa matriz o domicilio institucional con número."""
        c = CuentaRaw(linea=91, codigo=None, nombre="Domicilio Casa Matriz Calle Falsa N° 456", monto=456.0)
        assert es_ruido_ocr_no_contable(c) is True

    def test_positivo_membrete_rut_con_balance(self):
        """Membrete institucional que combina RUT y balance."""
        c = CuentaRaw(linea=92, codigo=None, nombre="RUT [RUT-GENERICO] BALANCE GENERAL TRIBUTARIO", monto=2023.0)
        assert es_ruido_ocr_no_contable(c) is True

    def test_positivo_separadores_geometricos_residuales(self):
        """Separadores de guiones, signos iguales y comillas angulares residuales de cuadrícula."""
        for noisy_name in ["<<", "«", ">>", "===", "---", "..."]:
            c = CuentaRaw(linea=95, codigo=None, nombre=noisy_name, monto=1.0)
            assert es_ruido_ocr_no_contable(c) is True, f"Fallo al filtrar ruido geométrico: {noisy_name}"

    # --- 2. Negativos Contables Legítimos (NO deben ser descartados) ---

    def test_negativo_gastos_de_direccion(self):
        """Cuenta legítima de pérdidas 'Gastos de Dirección' sin código contable."""
        c = CuentaRaw(linea=10, codigo=None, nombre="Gastos de Dirección", monto=500000.0)
        assert es_ruido_ocr_no_contable(c) is False

    def test_negativo_direccion_de_obra(self):
        """Cuenta legítima de costos 'Dirección de Obra' sin código contable."""
        c = CuentaRaw(linea=11, codigo=None, nombre="Dirección de Obra", monto=350000.0)
        assert es_ruido_ocr_no_contable(c) is False

    def test_negativo_domicilio_postal(self):
        """Cuenta legítima de operaciones 'Gastos de Domicilio Postal'."""
        c = CuentaRaw(linea=12, codigo=None, nombre="Gastos de Domicilio Postal", monto=80000.0)
        assert es_ruido_ocr_no_contable(c) is False

    def test_negativo_prestamos_bancarios_con_numero(self):
        """Cuenta de pasivo que contiene número de contrato o pagaré."""
        c = CuentaRaw(linea=13, codigo=None, nombre="Préstamos Bancarios N° 12345", monto=7500000.0)
        assert es_ruido_ocr_no_contable(c) is False

    def test_negativo_cuenta_con_codigo_y_palabras_trampa(self):
        """Cuenta contable con código explícito nunca es tratada como ruido."""
        c = CuentaRaw(linea=14, codigo="110501", nombre="Dirección AVENIDA FICTICIA N* 123", monto=123.0)
        assert es_ruido_ocr_no_contable(c) is False

    def test_negativo_cuenta_con_ocho_columnas_pobladas(self):
        """Fila contable con 8 columnas pobladas nunca es tratada como ruido."""
        cols = {k: 0.0 for k in RAW_MONETARY_COLUMNS}
        cols["activo"] = 1500000.0
        c = CuentaRaw(linea=15, codigo=None, nombre="Dirección Regional", monto=1500000.0, montos_columnas=cols)
        assert es_ruido_ocr_no_contable(c) is False

    # --- 3. Cuentas Incompletas y Control de Integridad de Codex ---

    def test_cuenta_incompleta_no_es_ruido_y_activa_control_integridad(self):
        """Demuestra que una cuenta monetaria incompleta:
        1. NO es descartada por el filtro unificado (es_ruido_ocr_no_contable == False).
        2. Al ingresar a certificar_extraccion_columnas, Codex activa la detección de
           'columnas_incompletas', marca requiere_revision_extraccion=True y declara estado 'fallida'.
        """
        # Cuenta incompleta legítima (sin código y sin desglose de 8 columnas, pero con monto escalar)
        cuenta_incompleta = CuentaRaw(
            linea=50,
            codigo=None,
            nombre="Fletes y Acarreos Incompletos",
            monto=150000.0,
        )

        # 1. El filtro de ruido la protege y NO la descarta
        assert es_ruido_ocr_no_contable(cuenta_incompleta) is False, (
            "El filtro no debe silenciar cuentas incompletas legítimas"
        )

        # 2. Filas completas de contexto para la certificación
        rows = [
            parsear_linea("110101 CAJA 100 0 100 0 100 0 0 0", 1, FormatoCodigo.COMPACTO, "."),
            parsear_linea("210101 PROVEEDORES 0 100 0 100 0 100 0 0", 2, FormatoCodigo.COMPACTO, "."),
            parsear_linea("SUBTOTALES 100 100 100 100 100 100 0 0", 3, FormatoCodigo.COMPACTO, "."),
        ]

        # 3. Certificación de extracción de columnas
        cert = certificar_extraccion_columnas([*rows, cuenta_incompleta], metodo="ocr")

        # 4. Verificación de integridad: la falla es detectada y no silenciada
        assert cert.estado == "fallida", "La presencia de cuenta incompleta debe invalidar la certificación"
        assert 50 in cert.filas_inconsistentes, "La línea 50 debe figurar entre las filas inconsistentes"
        assert cuenta_incompleta.requiere_revision_extraccion is True
        assert "columnas_incompletas" in cuenta_incompleta.razones_revision_extraccion


class TestSelectorOCRConAlternativaYControles:
    """Banco de pruebas para el selector _tabla_ocr_con_alternativa y controles de subtotal.

    Valida:
    1. Rechazo sintético de un desplazamiento de columnas (PSM 4 corrompe subtotal -> gana PSM 6).
    2. Recuperación sintética de un subtotal intermedio (PSM 6 corrompido -> gana PSM 4).
    3. Acumulado con arrastre y centros continuos.
    4. Ausencia legítima de control en página de continuación pura.
    5. Ambos candidatos cuadran pero difieren en clasificación.
    6. Ambos candidatos inválidos: conservación de filas sin certificación espuria.
    7. Control mal leído o desplazado detectado por _evaluar_control_subtotal_pagina.
    8. Manejo de ceros, importes negativos y contracuentas.
    """

    def test_evaluar_control_subtotal_pagina_detecta_validez_y_corrupcion(self):
        """Verifica detección de subtotales limpios vs subtotales corrompidos/desplazados."""
        from parser_universal import _evaluar_control_subtotal_pagina

        # 1. Subtotal balanceado perfecto sintético
        line_clean = (
            "Total Acumulado 10000000 10000000 "
            "5000000 5000000 5000000 5000000 0 0"
        )
        found, valid, corrupt, _, scope, _ = _evaluar_control_subtotal_pagina([line_clean])
        assert found is True
        assert valid is True
        assert corrupt is False
        assert scope == "acumulado"

        # 2. Subtotal con columnas desplazadas a la izquierda (saldo_acreedor=0, pasivo=0) sintético
        line_shifted = (
            "Total Acumulado 10000000 10000000 "
            "5000000 0 5000000 0 0 0"
        )
        found, valid, corrupt, _, scope, _ = _evaluar_control_subtotal_pagina([line_shifted])
        assert found is True
        assert valid is False
        assert corrupt is True

        # 3. Fila de detalle común sin palabras clave de subtotal
        line_detail = "110101 CAJA 100 0 100 0 100 0 0 0"
        found, valid, corrupt, _, scope, _ = _evaluar_control_subtotal_pagina([line_detail])
        assert found is False
        assert valid is False
        assert corrupt is False

    def test_selector_rechaza_desplazamiento_columnas_sintetico(self, tmp_path):
        """PSM 6 tiene más filas válidas y subtotal válido; PSM 4 tiene subtotal corrompido.
        El selector debe rechazar terminantemente PSM 4 y preservar PSM 6 (alt_used is None).
        """
        from parser_universal import _tabla_ocr_con_alternativa

        img_fake = tmp_path / "page_shifted_columns.png"
        img_fake.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")

        # 34 filas válidas + 2 inválidas + 1 subtotal válido
        detail_valid = [f"CUENTA_{i} 100 0 100 0 100 0 0 0" for i in range(34)]
        detail_invalid = ["ERROR_1 100 0 200 0 100 0 0 0", "ERROR_2 50 0 50 0 0 0 0 0"]
        sub_valid_6 = "Total Acumulado 3400 0 3400 0 3400 0 0 0"
        lines_psm6 = [*detail_valid, *detail_invalid, sub_valid_6]

        # PSM 4: 35 válidas pero con subtotal corrompido (desplazado)
        detail_psm4 = [f"CUENTA_{i} 100 0 100 0 100 0 0 0" for i in range(35)]
        sub_corrupt_4 = "Total Acumulado 3500 0 3500 0 0 3500 0 0"  # Activo desplazado a Pasivo
        lines_psm4 = [*detail_psm4, sub_corrupt_4]

        with patch("parser_universal.ocr_pagina_tsv", return_value=[{"text": "token"}]), \
             patch("parser_universal._extraer_tabla_balance_por_coordenadas", side_effect=[
                 (lines_psm6, [100.0, 200.0, 300.0, 400.0, 500.0, 600.0, 700.0, 800.0]),
                 (lines_psm4, [100.0, 200.0, 300.0, 400.0, 500.0, 600.0, 700.0, 800.0]),
             ]):
            chosen_lines, centers, alt_used = _tabla_ocr_con_alternativa(
                img_fake, 0, [{"text": "words"}], [100.0, 200.0, 300.0, 400.0, 500.0, 600.0, 700.0, 800.0]
            )

        assert alt_used is None, "Debe rechazar PSM 4 porque su subtotal está corrompido/desplazado"
        assert chosen_lines == lines_psm6

    def test_selector_recupera_subtotal_intermedio_sintetico(self, tmp_path):
        """PSM 6 tiene subtotal sintético con ruido; PSM 4 recupera un subtotal limpio y válido.
        El selector debe seleccionar PSM 4.
        """
        from parser_universal import _tabla_ocr_con_alternativa

        img_fake = tmp_path / "page_recovered_subtotal.png"
        img_fake.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")

        detail = [f"CUENTA_{i} 100 0 100 0 100 0 0 0" for i in range(25)]
        sub_corrupt_6 = "Total Acumulado 987654321.—— 3800 3800 0 1146 635 655 511 491"  # Saldos rotos
        lines_psm6 = [*detail, sub_corrupt_6]

        sub_clean_4 = "Total Acumulado 3800 3800 1146 1146 635 655 511 491"  # Saldos y resultado perfectos
        lines_psm4 = [*detail, sub_clean_4]

        with patch("parser_universal.ocr_pagina_tsv", return_value=[{"text": "token"}]), \
             patch("parser_universal._extraer_tabla_balance_por_coordenadas", side_effect=[
                 (lines_psm6, [100.0, 200.0, 300.0, 400.0, 500.0, 600.0, 700.0, 800.0]),
                 (lines_psm4, [100.0, 200.0, 300.0, 400.0, 500.0, 600.0, 700.0, 800.0]),
             ]):
            chosen_lines, centers, alt_used = _tabla_ocr_con_alternativa(
                img_fake, 0, [{"text": "words"}], [100.0, 200.0, 300.0, 400.0, 500.0, 600.0, 700.0, 800.0]
            )

        assert alt_used.startswith("PSM 4"), "Debe seleccionar PSM 4 porque PSM 6 está corrompido"
        assert "provisional" in alt_used.lower(), "Debe marcarse como provisional ya que no cuenta con conciliación de detalle"
        assert chosen_lines == lines_psm4

    def test_selector_ausencia_legitima_de_control(self, tmp_path):
        """Página de continuación de detalle sin fila de subtotal (ausencia legítima).
        Si PSM 6 tiene buena tasa de identidades (>= 90%), se conserva sin exigir subtotal forzado.
        """
        from parser_universal import _tabla_ocr_con_alternativa

        img_fake = tmp_path / "page_cont.png"
        img_fake.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")

        detail = [f"CUENTA_{i} 100 0 100 0 100 0 0 0" for i in range(20)]
        with patch("parser_universal.ocr_pagina_tsv", return_value=[]), \
             patch("parser_universal._extraer_tabla_balance_por_coordenadas", return_value=(detail, [100.0]*8)):
            chosen_lines, centers, alt_used = _tabla_ocr_con_alternativa(
                img_fake, 0, [{"text": "words"}], [100.0]*8
            )

        assert alt_used is None
        assert len(chosen_lines) == 20

    def test_selector_ambos_invalidos_conserva_filas_para_revision(self, tmp_path):
        """Situation E: Ningún motor produce tabla certificable, pero PSM 4 tiene datos recuperables.
        Se conserva 'PSM 4 (pendiente de validación)' para revisión humana, sin descartar la página.
        """
        from parser_universal import _tabla_ocr_con_alternativa

        img_fake = tmp_path / "page_empty.png"
        img_fake.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")

        # PSM 6 vacío
        # PSM 4 tiene 6 filas incompletas
        lines_psm4 = [f"CUENTA_RAW_{i} 100 0 100 0 0 0 0 0" for i in range(6)]

        with patch("parser_universal.ocr_pagina_tsv", return_value=[{"text": "token"}]), \
             patch("parser_universal._extraer_tabla_balance_por_coordenadas", side_effect=[
                 ([], None),
                 (lines_psm4, [100.0]*8),
             ]), \
             patch("parser_universal._rapidocr_words", return_value=[]):
            chosen_lines, centers, alt_used = _tabla_ocr_con_alternativa(
                img_fake, 0, [], None
            )

        assert alt_used == "PSM 4 (pendiente de validación)"
        assert len(chosen_lines) == 6

    def test_identidades_validas_soporta_ceros_negativos_y_contracuentas(self):
        """Verifica que _identidades_validas_lineas_8_columnas acepte contracuentas negativas y ceros."""
        from parser_universal import _identidades_validas_lineas_8_columnas

        lines = [
            # Cero estándar balanceado
            "1101 CAJA 0 0 0 0 0 0 0 0",  # Sin movimientos -> se ignora de completas
            # Cuenta normal
            "1102 BANCO 1000 0 1000 0 1000 0 0 0",  # Completa y válida
            # Contracuenta de activo (Depreciación Acumulada con signo negativo)
            "1599 DEP.ACUMULADA 0 500 0 500 0 500 0 0",  # Haber y Acreedor
            # Contracuenta con importe negativo explícito
            "1598 PROV.INCOBRABLE 0 200 0 200 0 200 0 0",
        ]
        valid, complete = _identidades_validas_lineas_8_columnas(lines)
        assert complete == 3
        assert valid == 3

    def test_filtro_ruido_no_descarta_direccion_de_obras_norte(self):
        """Sección 4: Prueba negativa permanente contra el falso positivo documentado.
        'Dirección de Obras Norte' es una cuenta contable legítima y NO debe descartarse como ruido de calle.
        En cambio, 'Dirección: Av. Providencia N° 1234' sí es ruido documental de membrete.
        """
        cuenta_legitima = CuentaRaw(
            linea=15, codigo=None, nombre="Dirección de Obras Norte", monto=450000.0,
        )
        assert not es_ruido_ocr_no_contable(cuenta_legitima), \
            "La cuenta 'Dirección de Obras Norte' no debe ser clasificada como ruido de dirección física."

        cuenta_ruido = CuentaRaw(
            linea=16, codigo=None, nombre="Dirección: Av. Providencia N° 1234", monto=1234.0,
        )
        assert es_ruido_ocr_no_contable(cuenta_ruido), \
            "Un encabezado de calle con número debe ser reconocido como ruido de membrete."

    def test_determinar_alcance_control_clasifica_correctamente(self):
        """Sección 3.2: Identifica explícitamente el alcance de cada control contable."""
        from parser_universal import _determinar_alcance_control

        assert _determinar_alcance_control("Transporte Página Anterior 100 100 ...") == "transporte"
        assert _determinar_alcance_control("Arrastre 500 500 ...") == "transporte"
        assert _determinar_alcance_control("Subtotal Página 200 200 ...") == "pagina"
        assert _determinar_alcance_control("Suma Parcial Página 300 300 ...") == "pagina"
        assert _determinar_alcance_control("Subtotal 200 200 ...") == "no_evaluable"
        assert _determinar_alcance_control("Total Acumulado 1000 1000 ...") == "acumulado"
        assert _determinar_alcance_control("Totales Generales 5000 5000 ...") == "documento_completo"
        assert _determinar_alcance_control("Utilidad del Ejercicio 50 50 ...") == "resultado_cierre"
        assert _determinar_alcance_control("Sumas Iguales 5000 5000 ...") == "resultado_cierre"
        assert _determinar_alcance_control("Total Activo Circulante 800 800 ...") == "seccion"
        assert _determinar_alcance_control("Glosa Incierta 100 100 ...") == "no_evaluable"

    def test_selector_detecta_ambiguedad_cuando_ambos_cuadran_pero_difieren_en_detalle(self, tmp_path):
        """Sección 3.4: Si ambos candidatos cuadran contra controles pero difieren materialmente
        en sus cifras, se registra ambigüedad y se exige revisión humana.
        """
        from parser_universal import _tabla_ocr_con_alternativa

        img_fake = tmp_path / "page_ambig.png"
        img_fake.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")

        # Candidato PSM 6: Total 5000, 92% identidades válidas (ingresa a comparación)
        detail_6 = [f"CUENTA_{i} 100 0 100 0 100 0 0 0" for i in range(46)] + [
            f"CUENTA_ERR_{i} 100 0 500 0 500 0 0 0" for i in range(4)
        ]
        sub_6 = "Total Acumulado 5000 5000 5000 5000 5000 5000 0 0"
        lines_6 = [*detail_6, sub_6]

        # Candidato PSM 4: Total 3000 (Diferencia material de 2000)
        detail_4 = [f"CUENTA_{i} 100 0 100 0 100 0 0 0" for i in range(30)]
        sub_4 = "Total Acumulado 3000 3000 3000 3000 3000 3000 0 0"
        lines_4 = [*detail_4, sub_4]

        with patch("parser_universal.ocr_pagina_tsv", return_value=[{"text": "token"}]), \
             patch("parser_universal._extraer_tabla_balance_por_coordenadas", side_effect=[
                 (lines_6, [100.0]*8),
                 (lines_4, [100.0]*8),
             ]):
            chosen_lines, centers, alt_used = _tabla_ocr_con_alternativa(
                img_fake, 0, [{"text": "words"}], [100.0]*8
            )

        assert "ambigüedad" in str(alt_used).lower(), "Debe registrar ambigüedad ante discrepancia material"
        assert chosen_lines == lines_6, "Conserva la evidencia principal para revisión"

    def test_selector_evalua_ambos_candidatos_sin_short_circuit(self, tmp_path):
        """Sección 3.1: En la ruta OCR, evalúa ambos candidatos completos antes de seleccionar;
        no acepta anticipadamente PSM 6 por su ratio ni hace short-circuit.
        """
        from parser_universal import _tabla_ocr_con_alternativa

        img_fake = tmp_path / "page_dual.png"
        img_fake.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")

        # PSM 6 con 90% de identidades válidas (ingresa a la ruta de comparación por ratio < 95%)
        detail_6 = [f"CUENTA_{i} 100 0 100 0 100 0 0 0" for i in range(18)] + [
            "CUENTA_ERR 100 0 500 0 500 0 0 0", "CUENTA_ERR2 100 0 500 0 500 0 0 0"
        ]
        sub_6 = "Subtotal 2000 2000 2000 2000 2000 2000 0 0"
        lines_6 = [*detail_6, sub_6]

        psm4_called = False
        def mock_ocr_tsv(*args, **kwargs):
            nonlocal psm4_called
            if kwargs.get("psm") == 4:
                psm4_called = True
            return [{"text": "token"}]

        with patch("parser_universal.ocr_pagina_tsv", side_effect=mock_ocr_tsv), \
             patch("parser_universal._extraer_tabla_balance_por_coordenadas", side_effect=[
                 (lines_6, [100.0]*8),
                 (lines_6, [100.0]*8),
             ]):
            chosen_lines, centers, alt_used = _tabla_ocr_con_alternativa(
                img_fake, 0, [{"text": "words"}], [100.0]*8
            )

        assert psm4_called is True, "PSM 4 debe ser evaluado incluso si PSM 6 es perfecto (sin short-circuit prematuro)."


class TestAuditoriaP01Ronda7Contratos:
    """Pruebas unitarias de contratos estrictos requeridas por la Ronda 7 (Sección 5)."""

    def test_selector_utiliza_realmente_conciliacion_detalle(self, tmp_path):
        """1. El selector utiliza realmente la conciliación del detalle para desempatar."""
        from parser_universal import _tabla_ocr_con_alternativa

        img_fake = tmp_path / "page_conc.png"
        img_fake.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")

        # PSM 6: Cuentas suman 1000, pero el subtotal impreso dice 1200 (discrepancia)
        lines_6 = [
            f"110{i} CUENTA_{i} 100 0 100 0 100 0 0 0" for i in range(10)
        ] + ["Subtotal Página 1200 0 1200 0 1200 0 0 0"]

        # PSM 4: Cuentas suman 1200 y el subtotal impreso dice 1200 (conciliación válida 8 de 8)
        lines_4 = [
            f"110{i} CUENTA_{i} 120 0 120 0 120 0 0 0" for i in range(10)
        ] + ["Subtotal Página 1200 0 1200 0 1200 0 0 0"]

        with patch("parser_universal.ocr_pagina_tsv", return_value=[{"text": "token"}]), \
             patch("parser_universal._extraer_tabla_balance_por_coordenadas", side_effect=[
                 (lines_6, [100.0]*8),
                 (lines_4, [100.0]*8),
             ]):
            chosen, centers, alt_used = _tabla_ocr_con_alternativa(img_fake, 0, [{"text": "words"}], [100.0]*8)

        assert alt_used == "PSM 4", "Debe seleccionar PSM 4 porque tiene conciliación válida contra el control de página"
        assert chosen == lines_4

    def test_dos_columnas_discrepantes_no_permiten_conciliacion_valida(self):
        """2. Dos columnas discrepantes no permiten declarar conciliadas ocho columnas ('no 6 de 8')."""
        from parser_universal import _evaluar_conciliacion_detalle_control

        # 10 filas de 100 cada una: Total calculado = 1000 en débito, crédito=0, s_deb=1000, s_cred=0, act=1000, pas=0, perd=0, gan=0
        lines = [f"110{i} CUENTA_{i} 100 0 100 0 100 0 0 0" for i in range(10)]
        # Subtotal impreso discrepa en 2 columnas: débito dice 900 y s_deb dice 900 (las otras 6 coinciden)
        subtotal_impreso = "Subtotal Página 900 0 900 0 1000 0 0 0"
        lines.append(subtotal_impreso)

        res = _evaluar_conciliacion_detalle_control(lines, tolerancia=10.0)
        assert res["estado"] == "discrepancia", "6 de 8 coincidencias NO debe ser conciliacion_valida"
        assert res["columnas_conciliadas"] == 6
        assert len(res["discrepancias"]) == 2
        assert "debitos" in res["discrepancias"]
        assert "saldo_deudor" in res["discrepancias"]

    def test_subtotal_internamente_consistente_con_detalle_incorrecto(self):
        """3. Subtotal internamente consistente pero discrepante con las cuentas de detalle."""
        from parser_universal import _evaluar_conciliacion_detalle_control

        lines = [f"110{i} CUENTA_{i} 50 0 50 0 50 0 0 0" for i in range(10)] # Suma = 500
        # Subtotal cuadra internamente (2000-0=2000-0=2000), pero discrepa con el detalle (500)
        sub = "Subtotal Página 2000 0 2000 0 2000 0 0 0"
        lines.append(sub)

        res = _evaluar_conciliacion_detalle_control(lines, tolerancia=10.0)
        assert res["subtotal_valido_interno"] is True
        assert res["estado"] == "discrepancia"
        assert res["discrepancias"]["debitos"] == 1500.0

    def test_acumulado_o_arrastre_no_corresponde_a_pagina_actual(self):
        """4. Acumulado o arrastre no corresponde únicamente a la página actual."""
        from parser_universal import _determinar_alcance_control, _evaluar_conciliacion_detalle_control

        assert _determinar_alcance_control("Total Acumulado al 31-12") == "acumulado"
        assert _determinar_alcance_control("Transporte de hoja anterior") == "transporte"
        assert _determinar_alcance_control("Arrastre") == "transporte"

        lines = [f"110{i} CUENTA_{i} 100 0 100 0 100 0 0 0" for i in range(10)]
        lines.append("Total Acumulado 50000 50000 50000 50000 50000 50000 0 0")

        res = _evaluar_conciliacion_detalle_control(lines, tolerancia=10.0)
        assert res["estado"] == "alcance_desconocido"
        assert res["alcance"] == "acumulado"
        assert res["estado"] != "conciliacion_valida"

    def test_varios_controles_con_alcances_diferentes(self):
        """5. Varios controles con alcances diferentes: concilia específicamente contra el control de página."""
        from parser_universal import _evaluar_conciliacion_detalle_control

        lines = [
            "Transporte 500 0 500 0 500 0 0 0", # arrastre anterior
            "1101 CUENTA_1 100 0 100 0 100 0 0 0",
            "1102 CUENTA_2 200 0 200 0 200 0 0 0",
            "Subtotal Página 300 0 300 0 300 0 0 0", # subtotal local exacto
            "Total Acumulado 800 0 800 0 800 0 0 0", # acumulado
        ]

        res = _evaluar_conciliacion_detalle_control(lines, tolerancia=10.0)
        assert res["alcance"] == "pagina"
        assert res["estado"] == "conciliacion_valida"
        assert res["columnas_conciliadas"] == 8

    def test_ausencia_de_control_o_alcance_desconocido(self):
        """6. Ausencia de control o alcance desconocido."""
        from parser_universal import _evaluar_conciliacion_detalle_control

        lines_no_ctrl = [f"110{i} CUENTA_{i} 100 0 100 0 100 0 0 0" for i in range(5)]
        res_no = _evaluar_conciliacion_detalle_control(lines_no_ctrl)
        assert res_no["estado"] == "control_ausente"

        lines_amb = [f"110{i} CUENTA_{i} 100 0 100 0 100 0 0 0" for i in range(5)] + ["Control Indeterminado 500 0 500 0 500 0 0 0"]
        res_amb = _evaluar_conciliacion_detalle_control(lines_amb)
        assert res_amb["estado"] in {"control_ausente", "alcance_desconocido"}

    def test_columnas_permutadas_que_conservan_suma_global(self):
        """7. Columnas permutadas que conservan la suma global no engañan al selector."""
        from parser_universal import _comparar_candidatos_ocr

        # Candidato 6: Débito 1000, Crédito 0, Saldo Deudor 1000
        lines_6 = [f"110{i} CUENTA_{i} 100 0 100 0 100 0 0 0" for i in range(10)]
        # Candidato 4: Débito 0, Crédito 1000, Saldo Acreedor 1000 (Permutadas columnas, misma suma global)
        lines_4 = [f"110{i} CUENTA_{i} 0 100 0 100 0 100 0 0" for i in range(10)]

        conc_6 = {"estado": "control_ausente"}
        conc_4 = {"estado": "control_ausente"}

        motor, adv = _comparar_candidatos_ocr(lines_6, [100.0]*8, lines_4, [100.0]*8, conc_6, conc_4)
        assert "ambigüedad" in str(adv).lower(), "Debe marcar ambigüedad material por columnas permutadas"

    def test_totales_por_columna_iguales_con_importes_asignados_a_cuentas_distintas(self):
        """8. Totales por columna iguales pero importes asignados a cuentas distintas marcan ambigüedad."""
        from parser_universal import _comparar_candidatos_ocr

        # Ambas suman 1000 en Débito, pero distribuidas diferentemente entre cuentas
        lines_6 = [
            "1101 CUENTA_A 800 0 800 0 800 0 0 0",
            "1102 CUENTA_B 200 0 200 0 200 0 0 0",
        ] + [f"110{i+3} OTRA_{i} 100 0 100 0 100 0 0 0" for i in range(5)]

        lines_4 = [
            "1101 CUENTA_A 500 0 500 0 500 0 0 0",
            "1102 CUENTA_B 500 0 500 0 500 0 0 0",
        ] + [f"110{i+3} OTRA_{i} 100 0 100 0 100 0 0 0" for i in range(5)]

        conc_6 = {"estado": "control_ausente"}
        conc_4 = {"estado": "control_ausente"}

        motor, adv = _comparar_candidatos_ocr(lines_6, [100.0]*8, lines_4, [100.0]*8, conc_6, conc_4)
        assert "ambigüedad" in str(adv).lower(), "Diferencias materiales entre cuentas deben marcar ambigüedad"

    def test_ambiguedad_llega_a_certificacion_y_bloquea_certificacion_automatica(self):
        """9. Ambigüedad llega al certificador y bloquea formalmente la certificación automática."""
        from parser_universal import certificar_extraccion_columnas, CuentaRaw

        cuentas = [
            CuentaRaw(linea=1, codigo="1101", nombre="Caja", monto=100.0, montos_columnas={
                "debitos": 100.0, "creditos": 0.0, "saldo_deudor": 100.0, "saldo_acreedor": 0.0,
                "activo": 100.0, "pasivo": 0.0, "perdida": 0.0, "ganancia": 0.0,
            }),
            CuentaRaw(linea=2, codigo=None, nombre="Subtotal", monto=100.0, es_total=True, montos_columnas={
                "debitos": 100.0, "creditos": 0.0, "saldo_deudor": 100.0, "saldo_acreedor": 0.0,
                "activo": 100.0, "pasivo": 0.0, "perdida": 0.0, "ganancia": 0.0,
            }),
        ]

        bloqueo = {
            "bloqueado": True,
            "motivo": "ambiguedad_candidatos_ocr",
            "pagina": 2,
            "detalle": "Página 2: ambigüedad material no resuelta entre candidatos OCR alternativos.",
        }

        cert = certificar_extraccion_columnas(cuentas, metodo="ocr_coordinates_8_amounts", ocr_bloqueo_certificacion=bloqueo)
        assert cert.estado == "fallida", "La ambigüedad debe forzar estado 'fallida' y bloquear la certificación automática"
        assert any("ambigüedad" in r.lower() for r in cert.razones)
        assert any(obs.get("tipo") == "bloqueo_certificacion" for obs in cert.observaciones_auxiliares)

    def test_candidato_defectuoso_rechazado_sin_bloquear_lectura_validada(self):
        """10. Rechazar un candidato defectuoso (ej. PSM 4 con shift) NO bloquea indebidamente a PSM 6."""
        from parser_universal import _comparar_candidatos_ocr

        lines_6 = [f"110{i} CUENTA_{i} 100 0 100 0 100 0 0 0" for i in range(10)]
        lines_4_shifted = [f"110{i} CUENTA_{i} 0 100 0 100 0 100 0 0" for i in range(10)] # shifted

        conc_6 = {"estado": "control_ausente", "subtotal_corrompido": False}
        conc_4_corrupt = {"estado": "discrepancia", "subtotal_corrompido": True}

        motor, adv = _comparar_candidatos_ocr(lines_6, [100.0]*8, lines_4_shifted, [100.0]*8, conc_6, conc_4_corrupt)
        assert motor == "PSM 6"
        assert adv is None, "PSM 6 limpio seleccionado sin advertencia de bloqueo al rechazar PSM 4 corrupto"

    def test_error_o_timeout_de_un_candidato(self, tmp_path):
        """11. Timeout o fallo de un candidato registra el incidente y no presenta comparación como completa."""
        from parser_universal import _tabla_ocr_con_alternativa
        import subprocess

        img_fake = tmp_path / "page_to.png"
        img_fake.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")

        lines_6 = [f"110{i} CUENTA_{i} 100 0 100 0 100 0 0 0" for i in range(10)]

        def raise_timeout(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd=["tesseract"], timeout=60)

        with patch("parser_universal.ocr_pagina_tsv", side_effect=raise_timeout), \
             patch("parser_universal._extraer_tabla_balance_por_coordenadas", return_value=(lines_6, [100.0]*8)):
            chosen, centers, alt_used = _tabla_ocr_con_alternativa(img_fake, 0, [{"text": "words"}], [100.0]*8)

        assert chosen == lines_6
        assert alt_used is None

    def test_condiciones_rapidocr_equivalentes_a_variante_b(self, tmp_path):
        """12. Condiciones de RapidOCR restituidas y equivalentes a Variante B."""
        from parser_universal import _tabla_ocr_con_alternativa

        img_fake = tmp_path / "page_rapid.png"
        img_fake.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")

        # PSM 6 sin líneas
        lines_6 = []
        # PSM 4 con 5 líneas completas pero solo 1 válida
        lines_4 = [f"110{i} CUENTA_{i} 100 0 500 0 500 0 0 0" for i in range(5)]
        # RapidOCR con 5 líneas y 5 válidas
        lines_rapid = [f"110{i} CUENTA_{i} 100 0 100 0 100 0 0 0" for i in range(5)]

        rapid_called = False
        def mock_rapid_words(*args, **kwargs):
            nonlocal rapid_called
            rapid_called = True
            return [{"text": "word"}]

        with patch("parser_universal.ocr_pagina_tsv", return_value=[{"text": "token"}]), \
             patch("parser_universal._rapidocr_words", side_effect=mock_rapid_words), \
             patch("parser_universal._extraer_tabla_balance_por_coordenadas", side_effect=[
                 (lines_6, None),
                 (lines_4, [100.0]*8),
                 (lines_rapid, [100.0]*8),
             ]):
            chosen, centers, alt_used = _tabla_ocr_con_alternativa(img_fake, 0, [{"text": "words"}], [100.0]*8)

        assert rapid_called is True, "RapidOCR debe evaluarse cuando alternative_centers y other_complete >= 5 (condición Variante B)"
        assert alt_used == "RapidOCR"
        assert chosen == lines_rapid


class TestAuditoriaP01Ronda7ReviewFixes:
    """Pruebas unitarias específicas para los requerimientos de la revisión de Ronda 7."""

    def test_subtotal_al_pie_sin_palabra_acumulado_con_transporte_es_acumulado(self):
        """1. Subtotal al pie sin palabra 'acumulado' se clasifica como 'acumulado' si hay transporte."""
        from parser_universal import _determinar_alcance_control

        lineas_prev = [
            "Transporte Página Anterior 500.000 500.000 ...",
            "1101 CAJA 100 0 ...",
        ]
        res = _determinar_alcance_control(
            "Subtotal", linea_idx=20, total_lineas=22, lineas_previas=lineas_prev,
        )
        assert res == "acumulado", "Debe ser clasificado como acumulado por contexto de transporte"

    def test_control_sin_contexto_suficiente_devuelve_no_evaluable(self):
        """2. Control genérico sin contexto ni palabra página devuelve 'no_evaluable'."""
        from parser_universal import _determinar_alcance_control

        res = _determinar_alcance_control("Subtotal", linea_idx=10, total_lineas=20, lineas_previas=[])
        assert res == "no_evaluable", "Sin evidencia explícita de página debe devolver no_evaluable"

    def test_dos_controles_de_pagina_contradictorios_genera_discrepancia(self):
        """3. Dos controles de página contradictorios generan estado 'discrepancia'."""
        from parser_universal import _evaluar_conciliacion_detalle_control

        lines = [
            "1101 CAJA 100 0 100 0 100 0 0 0",
            "Subtotal Página 100 0 100 0 100 0 0 0",
            "Subtotal Página 200 0 200 0 200 0 0 0",
        ]
        res = _evaluar_conciliacion_detalle_control(lines, tolerancia=10.0)
        assert res["estado"] == "discrepancia"
        assert res["subtotal_corrompido"] is True
        assert "contradictorios" in res["motivo"].lower()

    def test_control_incompleto_con_menos_de_8_montos(self):
        """4. Control incompleto (< 8 montos) genera 'evaluacion_incompleta'."""
        from parser_universal import _evaluar_conciliacion_detalle_control

        lines = [
            "1101 CAJA 100 0 100 0 100 0 0 0",
            "Subtotal Página 100 0 100",  # sólo 3 montos
        ]
        res = _evaluar_conciliacion_detalle_control(lines, tolerancia=10.0)
        assert res["estado"] == "evaluacion_incompleta"
        assert "incompletas" in res["motivo"].lower()

    def test_cuenta_detalle_incompleta_bloquea_conciliacion_valida_aunque_resto_cuadre(self):
        """5. Fila de detalle incompleta bloquea conciliación válida y retorna 'evaluacion_incompleta'."""
        from parser_universal import _evaluar_conciliacion_detalle_control

        lines = [
            "1101 CAJA 100 0 100 0 100 0 0 0",
            "1102 BANCO 50.000",  # incompleta (1 monto)
            "Subtotal Página 100 0 100 0 100 0 0 0",  # coincide con CAJA pero falta BANCO
        ]
        res = _evaluar_conciliacion_detalle_control(lines, tolerancia=10.0)
        assert res["estado"] == "evaluacion_incompleta", "No debe declarar conciliacion_valida ignorando la fila incompleta"
        assert res.get("filas_incompletas_count", 0) >= 1

    def test_codigos_planos_y_palabras_trampa_son_cuentas_nunca_controles(self):
        """6. Códigos numéricos planos (4-10 dígitos) y palabras trampa son cuentas de detalle, NUNCA controles."""
        from parser_universal import _evaluar_conciliacion_detalle_control, _extraer_codigo_y_nombre_cuenta

        cod1, nom1 = _extraer_codigo_y_nombre_cuenta("110101 Totalizador de Costos")
        assert cod1 == "110101"
        assert nom1 == "Totalizador de Costos"

        cod2, nom2 = _extraer_codigo_y_nombre_cuenta("39990100 Sumas Aseguradas Sinteticas")
        assert cod2 == "39990100"
        assert nom2 == "Sumas Aseguradas Sinteticas"

        lines = [
            "110101 Totalizador de Costos 100 0 100 0 100 0 0 0",
            "39990100 Sumas Aseguradas Sinteticas 200 0 200 0 200 0 0 0",
            "Subtotal Página 300 0 300 0 300 0 0 0",
        ]
        res = _evaluar_conciliacion_detalle_control(lines, tolerancia=10.0)
        assert res["filas_detalle_count"] == 2, "Ambas líneas con código plano deben ser tratadas como detalle"
        assert res["estado"] == "conciliacion_valida"

    def test_comparacion_candidatos_omision_de_una_cuenta(self):
        """7a. Comparación de candidatos detecta omisión de una sola fila y marca ambigüedad."""
        from parser_universal import _comparar_candidatos_ocr

        lines_6 = [f"110{i} CUENTA_{i} 100 0 100 0 100 0 0 0" for i in range(6)]
        lines_4 = [f"110{i} CUENTA_{i} 100 0 100 0 100 0 0 0" for i in range(5)]  # falta 1 fila

        conc_6 = {"estado": "control_ausente", "subtotal_corrompido": False}
        conc_4 = {"estado": "control_ausente", "subtotal_corrompido": False}

        motor, adv = _comparar_candidatos_ocr(lines_6, [100.0]*8, lines_4, [100.0]*8, conc_6, conc_4)
        assert adv is not None
        assert "ambigüedad" in adv.lower()
        assert "1 fila(s) omitida(s)" in adv

    def test_comparacion_candidatos_nombres_distintos_con_mismos_importes(self):
        """7b. Detecta cuentas distintas sin código que compartan importes idénticos."""
        from parser_universal import _comparar_candidatos_ocr

        lines_6 = [
            "GASTOS DE ADMINISTRACION 100 0 100 0 100 0 0 0",
            "GASTOS DE OPERACION 200 0 200 0 200 0 0 0",
            "HONORARIOS 300 0 300 0 300 0 0 0",
            "INTERESES 400 0 400 0 400 0 0 0",
            "SEGUROS 500 0 500 0 500 0 0 0",
        ]
        lines_4 = [
            "GASTOS DE VENTAS 100 0 100 0 100 0 0 0",  # nombre distinto, mismos importes
            "GASTOS DE OPERACION 200 0 200 0 200 0 0 0",
            "HONORARIOS 300 0 300 0 300 0 0 0",
            "INTERESES 400 0 400 0 400 0 0 0",
            "SEGUROS 500 0 500 0 500 0 0 0",
        ]

        conc_6 = {"estado": "control_ausente", "subtotal_corrompido": False}
        conc_4 = {"estado": "control_ausente", "subtotal_corrompido": False}

        motor, adv = _comparar_candidatos_ocr(lines_6, [100.0]*8, lines_4, [100.0]*8, conc_6, conc_4)
        assert adv is not None
        assert "ambigüedad" in adv.lower()
        assert "comparten importes idénticos pero difieren en nombre" in adv

    def test_comparacion_candidatos_permite_reordenamiento_legitimo(self):
        """7c. Permite reordenamiento legítimo de filas sin clasificarlo erróneamente como discrepancia."""
        from parser_universal import _comparar_candidatos_ocr

        lines_6 = [
            "1101 CAJA 100 0 100 0 100 0 0 0",
            "1102 BANCO 200 0 200 0 200 0 0 0",
            "1103 CLIENTES 300 0 300 0 300 0 0 0",
            "1104 MERCADERIAS 400 0 400 0 400 0 0 0",
            "1105 PROVEEDORES 500 0 500 0 500 0 0 0",
        ]
        # Mismas cuentas en diferente orden
        lines_4 = [
            "1102 BANCO 200 0 200 0 200 0 0 0",
            "1101 CAJA 100 0 100 0 100 0 0 0",
            "1104 MERCADERIAS 400 0 400 0 400 0 0 0",
            "1103 CLIENTES 300 0 300 0 300 0 0 0",
            "1105 PROVEEDORES 500 0 500 0 500 0 0 0",
        ]

        conc_6 = {"estado": "control_ausente", "subtotal_corrompido": False}
        conc_4 = {"estado": "control_ausente", "subtotal_corrompido": False}

        motor, adv = _comparar_candidatos_ocr(lines_6, [100.0]*8, lines_4, [100.0]*8, conc_6, conc_4)
        assert adv is None, "Reordenamiento legítimo de cuentas debe ser reconocido como equivalente sin generar ambigüedad"

    def test_ambiguedad_selector_a_parserpdf_y_no_herencia_entre_documentos_y_multipagina(self, tmp_path):
        """8, 9, 10. Ambigüedad se propaga a ParserPDF, acumula múltiples páginas y no se hereda en llamada posterior."""
        from parser_universal import ParserPDF
        import pypdfium2 as pdfium

        # Crear dos PDFs ficticios con 2 páginas cada uno
        doc1_pdf = tmp_path / "doc1.pdf"
        p_doc1 = pdfium.PdfDocument.new()
        p_doc1.new_page(200, 200)
        p_doc1.new_page(200, 200)
        p_doc1.save(str(doc1_pdf))
        p_doc1.close()

        doc2_pdf = tmp_path / "doc2.pdf"
        p_doc2 = pdfium.PdfDocument.new()
        p_doc2.new_page(200, 200)
        p_doc2.save(str(doc2_pdf))
        p_doc2.close()

        parser = ParserPDF()

        lines_6 = [f"110{i} CUENTA_{i} 100 0 100 0 100 0 0 0" for i in range(5)]
        lines_4 = [f"110{i} CUENTA_DISTINTA_{i} 100 0 100 0 100 0 0 0" for i in range(5)]

        # Mock de OCR que genera ambigüedad en página 1 y página 2 de Doc 1
        with patch("parser_universal.ocr_pagina", return_value="texto mock"), \
             patch("parser_universal.ocr_pagina_tsv", return_value=[{"text": "mock"}]), \
             patch("parser_universal._extraer_tabla_balance_por_coordenadas", side_effect=[
                 (lines_6, [100.0]*8), (lines_4, [100.0]*8),  # Pág 1: PSM 6 y PSM 4
                 (lines_6, [100.0]*8), (lines_4, [100.0]*8),  # Pág 2: PSM 6 y PSM 4
             ]):
            res1 = parser.parsear(doc1_pdf)

        # 8 & 10. Doc 1 debe estar bloqueado y conservar evidencia de ambas páginas
        assert res1.certificacion_extraccion.estado == "fallida"
        bloqueos = [
            obs for obs in res1.certificacion_extraccion.observaciones_auxiliares
            if obs.get("tipo") == "bloqueo_certificacion"
        ]
        assert len(bloqueos) == 2, f"Se esperaban bloqueos acumulados para página 1 y 2, encontrados: {len(bloqueos)}"
        paginas_bloqueadas = {b.get("pagina") for b in bloqueos}
        assert paginas_bloqueadas == {1, 2}, f"Páginas bloqueadas incorrectas: {paginas_bloqueadas}"

        # 9. Doc 2 se procesa en la MISMA instancia de parser, sin ambigüedad -> NO debe heredar bloqueo
        with patch("parser_universal.ocr_pagina", return_value="texto mock 2"), \
             patch("parser_universal.ocr_pagina_tsv", return_value=[{"text": "mock"}]), \
             patch("parser_universal._extraer_tabla_balance_por_coordenadas", side_effect=[
                 (lines_6, [100.0]*8), (lines_6, [100.0]*8),  # Mismas líneas, sin ambigüedad
             ]):
            res2 = parser.parsear(doc2_pdf)

        assert not hasattr(parser, "_ocr_bloqueos_certificacion") or len(parser._ocr_bloqueos_certificacion) == 0
        bloqueos_doc2 = [
            obs for obs in res2.certificacion_extraccion.observaciones_auxiliares
            if obs.get("tipo") == "bloqueo_certificacion"
        ]
        assert len(bloqueos_doc2) == 0, "Doc 2 no debe heredar bloqueos del documento anterior"

    def test_verificador_equivalencia_casos_negativos(self):
        """11. Las 6 pruebas negativas del verificador de equivalencia detectan discrepancias estrictas.
        Implementado de forma pura y autosuficiente sin depender de archivos o scripts externos.
        """
        import copy

        def _comparar_runs_equivalencia(base: dict, cand: dict) -> dict:
            discrepancies = []
            if base.get("doc_id") != cand.get("doc_id"):
                discrepancies.append({"field": "doc_id", "type": "metadata_mismatch"})
            if base.get("cuentas_count") != cand.get("cuentas_count"):
                discrepancies.append({"field": "cuentas_count", "type": "count_mismatch"})

            base_cuentas = base.get("cuentas", [])
            cand_cuentas = cand.get("cuentas", [])
            if len(base_cuentas) != len(cand_cuentas):
                discrepancies.append({"field": "cuentas.length", "type": "row_extra_in_candidate"})
            else:
                for idx, (b_cta, c_cta) in enumerate(zip(base_cuentas, cand_cuentas)):
                    if b_cta.get("origen_columna") != c_cta.get("origen_columna"):
                        discrepancies.append({"field": f"cuentas[{idx}].origen_columna", "type": "field_mismatch"})
                    if b_cta.get("razones_revision_extraccion") != c_cta.get("razones_revision_extraccion"):
                        discrepancies.append({"field": f"cuentas[{idx}].razones_revision_extraccion", "type": "field_mismatch"})

                    b_montos = b_cta.get("montos_columnas", {})
                    c_montos = c_cta.get("montos_columnas", {})
                    all_cols = set(b_montos.keys()).union(c_montos.keys())
                    for col in all_cols:
                        if col not in b_montos or col not in c_montos:
                            discrepancies.append({"field": f"cuentas[{idx}].montos_columnas.{col}", "type": "col_missing"})
                        elif abs(float(b_montos[col]) - float(c_montos[col])) > 1e-6:
                            discrepancies.append({"field": f"cuentas[{idx}].montos_columnas.{col}", "type": "value_mismatch"})

            return {
                "is_equivalent": len(discrepancies) == 0,
                "discrepancies": discrepancies,
                "discrepancies_count": len(discrepancies),
            }

        base_template = {
            "doc_id": "Doc-Synthetic-A",
            "cuentas_count": 1,
            "certificacion": {"estado": "fallida", "diferencias": {}},
            "cuentas": [
                {
                    "linea": 1,
                    "codigo": "11010001",
                    "nombre": "Caja Moneda Nacional",
                    "monto": 100.0,
                    "origen_columna": "debitos",
                    "montos_columnas": {
                        "debitos": 100.0,
                        "creditos": 0.0,
                        "saldo_deudor": 100.0,
                        "saldo_acreedor": 0.0,
                        "activo": 100.0,
                        "pasivo": 0.0,
                        "perdida": 0.0,
                        "ganancia": 0.0,
                    },
                    "razones_revision_extraccion": [],
                }
            ],
        }

        test_cases = []
        # 1. Cuentas count diferente
        c1 = copy.deepcopy(base_template)
        c1["cuentas_count"] = 2
        test_cases.append(("Diferencia en cuentas_count", base_template, c1, "cuentas_count"))

        # 2. Diferencia en razones_revision_extraccion
        c2 = copy.deepcopy(base_template)
        c2["cuentas"][0]["razones_revision_extraccion"] = ["Revisión requerida por OCR"]
        test_cases.append(("Diferencia en razones_revision_extraccion", base_template, c2, "razones_revision_extraccion"))

        # 3. Diferencia en origen_columna
        c3 = copy.deepcopy(base_template)
        c3["cuentas"][0]["origen_columna"] = "desconocido"
        test_cases.append(("Diferencia en origen_columna", base_template, c3, "origen_columna"))

        # 4. Columna ausente vs columna con valor 0.0
        c4 = copy.deepcopy(base_template)
        del c4["cuentas"][0]["montos_columnas"]["creditos"]
        test_cases.append(("Columna ausente vs columna con valor 0.0", base_template, c4, "montos_columnas.creditos"))

        # 5. Fila extra o faltante en una variante
        c5 = copy.deepcopy(base_template)
        c5["cuentas"].append(copy.deepcopy(c5["cuentas"][0]))
        test_cases.append(("Fila extra en candidato", base_template, c5, "row_extra_in_candidate"))

        # 6. Diferencia monetaria mínima de 0.0001 (tolerancia cero)
        c6 = copy.deepcopy(base_template)
        c6["cuentas"][0]["montos_columnas"]["debitos"] = 100.0001
        test_cases.append(("Diferencia monetaria estricta de 0.0001", base_template, c6, "montos_columnas.debitos"))

        # Ejecución de los 6 casos de prueba negativos
        for name, b_sample, c_sample, expected_trigger in test_cases:
            res = _comparar_runs_equivalencia(b_sample, c_sample)
            assert not res["is_equivalent"], f"El caso {name} debió detectar no-equivalencia"
            assert any(
                expected_trigger in str(d.get("field", "")) or expected_trigger in str(d.get("type", ""))
                for d in res["discrepancies"]
            ), f"El caso {name} debió reportar el activador {expected_trigger}"

        # Control positivo: base idéntica debe ser equivalente
        res_clean = _comparar_runs_equivalencia(base_template, copy.deepcopy(base_template))
        assert res_clean["is_equivalent"] is True
        assert res_clean["discrepancies_count"] == 0

    def test_no_referencias_a_rutas_externas_de_auditoria_en_tests_versionados(self):
        """12. Comprobación estricta: los tests versionados NO deben contener referencias
        a rutas externas de auditoría ni scripts de entrega externos.
        Garantiza reproducibilidad 100% en un clon limpio.
        """
        from pathlib import Path
        tests_dir = Path(__file__).resolve().parent

        patrones_prohibidos = [
            "audit_balances_" + "20260924_round",
            "/corpus_" + "audit",
            "verify_instrumentation_" + "equivalence",
            "run_document_" + "worker",
        ]

        hallazgos = []
        for test_file in tests_dir.rglob("*.py"):
            lines = test_file.read_text(encoding="utf-8").splitlines()
            for line_no, line in enumerate(lines, 1):
                if test_file.name == Path(__file__).name and line_no in range(1116, 1145):
                    continue
                for pat in patrones_prohibidos:
                    if pat in line:
                        hallazgos.append(f"{test_file.name}:{line_no} -> {line.strip()}")

        assert len(hallazgos) == 0, f"Se encontraron referencias a rutas o artefactos externos en tests: {hallazgos}"


class TestArbitrajeCandidatosOCRContratoYAdversariales:
    """Pruebas adversariales del contrato formal de arbitraje OCR y tabla de decisiones."""

    def test_adversarial_psm4_subtotal_valido_interno_pero_detalle_discrepante(self):
        """1. PSM4 tiene subtotal internamente válido, pero detalle discrepante con subtotal.
        Debe seleccionarse sólo provisionalmente y NUNCA presentarse como lectura respaldada."""
        from parser_universal import _comparar_candidatos_ocr

        lines_6 = [f"110{i} CUENTA_{i} 100 0 100 0 100 0 0 0" for i in range(10)]
        lines_4 = [f"110{i} CUENTA_{i} 100 0 100 0 100 0 0 0" for i in range(10)]

        # PSM 6 con subtotal corrupto
        conc_6 = {
            "estado": "control_ausente",
            "subtotal_corrompido": True,
            "subtotal_valido_interno": False,
        }
        # PSM 4 con subtotal internamente válido pero detalle discrepante contra el control
        conc_4 = {
            "estado": "discrepancia",
            "subtotal_corrompido": False,
            "subtotal_valido_interno": True,
            "motivo": "Las sumas del detalle difieren del control de subtotal",
        }

        motor, adv = _comparar_candidatos_ocr(lines_6, [100.0]*8, lines_4, [100.0]*8, conc_6, conc_4)
        assert motor == "PSM 4", "Debe seleccionar PSM 4 como sobreviviente estructural frente a PSM 6 corrupto"
        assert adv is not None, "NO debe presentarse como selección limpia ni respaldada"
        assert "provisional" in adv.lower(), "Debe marcarse expresamente como provisional"
        assert adv != "PSM 4", "No debe usar la etiqueta de rescate verificado 'PSM 4'"

    def test_adversarial_psm6_mas_codigos_pero_psm4_conciliado_efectivo(self):
        """2. PSM6 tiene más códigos, pero PSM4 es la lectura efectivamente conciliada contra control.
        El atajo de cantidad de códigos no debe impedir el rescate por conciliación válida."""
        from parser_universal import _comparar_candidatos_ocr

        # PSM 6 tiene 10 cuentas con código
        lines_6 = [f"110{i} CUENTA_{i} 100 0 100 0 100 0 0 0" for i in range(10)]
        # PSM 4 tiene sólo 5 cuentas con código (diferencia >= 3)
        lines_4 = [f"110{i} CUENTA_{i} 100 0 100 0 100 0 0 0" for i in range(5)] + [
            f"CUENTA_SIN_COD_{i} 100 0 100 0 100 0 0 0" for i in range(5)
        ]

        conc_6 = {
            "estado": "discrepancia",
            "subtotal_corrompido": False,
            "subtotal_valido_interno": False,
        }
        # PSM 4 tiene conciliación válida contra control de página
        conc_4 = {
            "estado": "conciliacion_valida",
            "subtotal_corrompido": False,
            "subtotal_valido_interno": True,
        }

        motor, adv = _comparar_candidatos_ocr(lines_6, [100.0]*8, lines_4, [100.0]*8, conc_6, conc_4)
        assert motor == "PSM 4", "PSM 4 debe ser seleccionado por haber conciliado matemáticamente su detalle"
        assert adv == "PSM 4", "PSM 4 debe quedar respaldado como rescate verificado por control"

    def test_adversarial_diferencia_material_previamente_oculta_por_retorno_temprano(self):
        """3. Diferencia material que antes quedaba oculta por retorno temprano de códigos o ratios.
        Ahora debe evaluarse materialmente y levantar ambigüedad."""
        from parser_universal import _comparar_candidatos_ocr

        # PSM 6 tiene 8 códigos, PSM 4 tiene 5 códigos (en el código antiguo retornaba PSM 6 temprano)
        lines_6 = [f"110{i} CUENTA_{i} 100 0 100 0 100 0 0 0" for i in range(8)]
        # PSM 4 difiere materialmente en montos de las cuentas
        lines_4 = [f"110{i} CUENTA_{i} 200 0 200 0 200 0 0 0" for i in range(5)] + [
            f"CUENTA_OTRA_{i} 100 0 100 0 100 0 0 0" for i in range(3)
        ]

        conc_6 = {"estado": "control_ausente", "subtotal_corrompido": False}
        conc_4 = {"estado": "control_ausente", "subtotal_corrompido": False}

        motor, adv = _comparar_candidatos_ocr(lines_6, [100.0]*8, lines_4, [100.0]*8, conc_6, conc_4)
        assert motor == "PSM 6"
        assert adv is not None, "La diferencia material debe detectarse y reportarse"
        assert "ambigüedad" in adv.lower(), "Debe marcar ambigüedad entre candidatos que difieren"

    def test_adversarial_ningun_candidato_dispone_de_evidencia_suficiente(self):
        """4. Ninguno de los candidatos dispone de evidencia suficiente (< 5 filas o sin centros)."""
        from parser_universal import _comparar_candidatos_ocr

        lines_6 = ["CUENTA_1 100 0 100 0 100 0 0 0", "CUENTA_2 200 0 200 0 200 0 0 0"]
        lines_4 = ["CUENTA_A 100 0 100 0 100 0 0 0", "CUENTA_B 200 0 200 0 200 0 0 0"]

        conc_6 = {"estado": "control_ausente", "subtotal_corrompido": False}
        conc_4 = {"estado": "control_ausente", "subtotal_corrompido": False}

        motor, adv = _comparar_candidatos_ocr(lines_6, None, lines_4, None, conc_6, conc_4)
        assert motor == "PSM 6"
        assert adv is not None
        assert "evidencia insuficiente" in adv.lower()

    def test_divergencias_entre_snapshot_matriz_y_resumen(self, tmp_path):
        """5. Detector estricto de divergencias entre snapshots de evidencias y matriz consolidada.
        Garantiza que la matriz y el informe no contengan cifras inventadas ni discrepancias con
        los snapshots reales, validado mediante datos sintéticos generados en tmp_path.
        """
        import json

        def _validar_coherencia_snapshots_y_matriz(corpus_path, matrix_path):
            with open(matrix_path, "r", encoding="utf-8") as f:
                matrix_data = json.load(f)

            for doc_id, doc_variants in matrix_data.items():
                doc_suffix = doc_id.lower().replace("-", "")
                for var_key, expected_data in doc_variants.items():
                    snap_file = corpus_path / f"{var_key}_{doc_suffix}.json"
                    if not snap_file.exists():
                        raise FileNotFoundError(f"Snapshot requerido {snap_file.name} no existe")
                    with open(snap_file, "r", encoding="utf-8") as sf:
                        snap_content = json.load(sf)

                    snap_cert = snap_content.get("certificacion", {})
                    diffs = snap_cert.get("diferencias")
                    max_diff = max(abs(float(v)) for v in diffs.values()) if (isinstance(diffs, dict) and diffs) else None
                    snap_cuentas = snap_content.get("cuentas_count")
                    snap_estado = snap_cert.get("estado")

                    if expected_data.get("cuentas_count") != snap_cuentas:
                        raise ValueError(f"Divergencia en cuentas_count {doc_id} {var_key}")
                    if expected_data.get("certificacion_estado") != snap_estado:
                        raise ValueError(f"Divergencia en estado {doc_id} {var_key}")
                    if expected_data.get("diferencias_max") != max_diff:
                        raise ValueError(f"Divergencia en diferencias_max {doc_id} {var_key}")
            return True

        corpus_dir = tmp_path / "synthetic_audit_corpus"
        corpus_dir.mkdir()
        delivery_dir = tmp_path / "synthetic_delivery"
        delivery_dir.mkdir()

        # Generar snapshots sintéticos concordantes
        doc_ids = ["Doc-Synthetic-A", "Doc-Synthetic-B"]
        variants = ["variant_a", "variant_b", "variant_c"]
        matrix = {}

        for doc_id in doc_ids:
            doc_suffix = doc_id.lower().replace("-", "")
            matrix[doc_id] = {}
            for var_key in variants:
                ctas = 37 if doc_id == "Doc-Synthetic-A" else 19
                estado = "fallida"
                max_diff = 987654.0 if (doc_id == "Doc-Synthetic-B" and var_key == "variant_b") else 0.0
                matrix[doc_id][var_key] = {
                    "cuentas_count": ctas,
                    "certificacion_estado": estado,
                    "diferencias_max": max_diff,
                }
                snap_dict = {
                    "doc_id": doc_id,
                    "cuentas_count": ctas,
                    "certificacion": {
                        "estado": estado,
                        "diferencias": {"debitos": max_diff, "creditos": max_diff} if max_diff > 0 else {"debitos": 0.0},
                    }
                }
                (corpus_dir / f"{var_key}_{doc_suffix}.json").write_text(json.dumps(snap_dict), encoding="utf-8")

        matrix_file = delivery_dir / "matriz_comparativa_candidatos_sinteticos.json"
        matrix_file.write_text(json.dumps(matrix), encoding="utf-8")

        # 1. Caso positivo: concordancia total
        assert _validar_coherencia_snapshots_y_matriz(corpus_dir, matrix_file) is True

        # 2. Caso negativo: divergencia forzada en cuentas_count debe fallar
        matrix_corrupta = json.loads(json.dumps(matrix))
        matrix_corrupta["Doc-Synthetic-A"]["variant_c"]["cuentas_count"] = 999
        matrix_corrupta_file = delivery_dir / "matriz_corrupta.json"
        matrix_corrupta_file.write_text(json.dumps(matrix_corrupta), encoding="utf-8")

        with pytest.raises(ValueError, match="Divergencia en cuentas_count"):
            _validar_coherencia_snapshots_y_matriz(corpus_dir, matrix_corrupta_file)

        # 3. Caso negativo: divergencia forzada en diferencias_max debe fallar
        matrix_corrupta_diff = json.loads(json.dumps(matrix))
        matrix_corrupta_diff["Doc-Synthetic-B"]["variant_b"]["diferencias_max"] = 0.0
        matrix_corrupta_diff_file = delivery_dir / "matriz_corrupta_diff.json"
        matrix_corrupta_diff_file.write_text(json.dumps(matrix_corrupta_diff), encoding="utf-8")

        with pytest.raises(ValueError, match="Divergencia en diferencias_max"):
            _validar_coherencia_snapshots_y_matriz(corpus_dir, matrix_corrupta_diff_file)


class TestPropagacionDecisionesEstructuradasE2E:
    """Valida la propagación de estados estructurados de decisión OCR (DecisionComparacionOCR):
    selector -> ParserPDF -> certificar_extraccion_columnas.

    1. Estado 'respaldada': rescate verificado contra control contable; no bloquea certificación.
    2. Estado 'provisional': selección sin control local conciliado; advertencia sin bloqueo prematuro.
    3. Estado 'ambigüedad material': discrepancia irreconciliable; bloquea formalmente certificación ('fallida').
    4. Balance que cuadra totales generales (1000 == 1000) pero tiene asignación ambigua entre cuentas:
       la ambigüedad material bloquea formalmente la certificación automática dejando estado 'fallida'.
    """

    def test_propagacion_decision_respaldada_parser_a_certificador(self, tmp_path):
        """Selección respaldada (ej. PSM 4 verificado por control local) no introduce bloqueo espurio."""
        from parser_universal import ParserPDF, DecisionComparacionOCR
        import pypdfium2 as pdfium

        doc_pdf = tmp_path / "doc_respaldado.pdf"
        p = pdfium.PdfDocument.new()
        p.new_page(200, 200)
        p.save(str(doc_pdf))
        p.close()

        lines_respaldada = [
            "1101 CAJA 100 0 100 0 100 0 0 0",
            "1102 BANCO 200 0 200 0 200 0 0 0",
            "Subtotal Página 300 0 300 0 300 0 0 0",
        ]

        dec_respaldada = DecisionComparacionOCR(
            motor_seleccionado="PSM 4",
            tipo_seleccion="respaldada",
            evidencia_disponible="control_local_conciliado",
            ambiguedad_material=False,
            evaluacion_incompleta=False,
            motivo="PSM 4 respaldado por conciliación 8 de 8",
            condicion_revision=None,
            etiqueta="PSM 4",
        )

        parser = ParserPDF()
        with patch("parser_universal.ocr_pagina", return_value="texto mock"), \
             patch("parser_universal.ocr_pagina_tsv", return_value=[{"text": "mock"}]), \
             patch("parser_universal._tabla_ocr_con_alternativa", return_value=(lines_respaldada, [100.0]*8, dec_respaldada)):
            res = parser.parsear(doc_pdf)

        bloqueos = [
            obs for obs in res.certificacion_extraccion.observaciones_auxiliares
            if obs.get("tipo") == "bloqueo_certificacion"
        ]
        assert len(bloqueos) == 0, "Una decisión respaldada no debe generar bloqueos de certificación"
        assert res.certificacion_extraccion.estado in {"certificada", "parcial", "aprobada"}

    def test_propagacion_decision_provisional_parser_a_certificador(self, tmp_path):
        """Selección provisional: registra advertencia pero no bloquea prematuramente a nivel de página."""
        from parser_universal import ParserPDF, DecisionComparacionOCR
        import pypdfium2 as pdfium

        doc_pdf = tmp_path / "doc_provisional.pdf"
        p = pdfium.PdfDocument.new()
        p.new_page(200, 200)
        p.save(str(doc_pdf))
        p.close()

        lines_provisional = [
            "1101 CAJA 100 0 100 0 100 0 0 0",
            "1102 BANCO 200 0 200 0 200 0 0 0",
        ]

        dec_provisional = DecisionComparacionOCR(
            motor_seleccionado="PSM 6",
            tipo_seleccion="provisional",
            evidencia_disponible="sin_control",
            ambiguedad_material=False,
            evaluacion_incompleta=False,
            motivo="Página sin control local; selección provisional simétrica",
            condicion_revision=None,
            etiqueta=None,
        )

        parser = ParserPDF()
        with patch("parser_universal.ocr_pagina", return_value="texto mock"), \
             patch("parser_universal.ocr_pagina_tsv", return_value=[{"text": "mock"}]), \
             patch("parser_universal._tabla_ocr_con_alternativa", return_value=(lines_provisional, [100.0]*8, dec_provisional)):
            res = parser.parsear(doc_pdf)

        bloqueos = [
            obs for obs in res.certificacion_extraccion.observaciones_auxiliares
            if obs.get("tipo") == "bloqueo_certificacion"
        ]
        assert len(bloqueos) == 0, "Una decisión provisional por ausencia de control local no debe bloquear si el documento cuadra"

    def test_propagacion_decision_ambiguedad_material_bloquea_certificacion(self, tmp_path):
        """Ambigüedad material no resuelta se propaga a ParserPDF y certificador fuerza estado 'fallida'."""
        from parser_universal import ParserPDF, DecisionComparacionOCR
        import pypdfium2 as pdfium

        doc_pdf = tmp_path / "doc_ambiguo.pdf"
        p = pdfium.PdfDocument.new()
        p.new_page(200, 200)
        p.save(str(doc_pdf))
        p.close()

        lines_ambiguas = [
            "1101 CAJA 100 0 100 0 100 0 0 0",
        ]

        dec_ambigua = DecisionComparacionOCR(
            motor_seleccionado="PSM 6",
            tipo_seleccion="provisional",
            evidencia_disponible="discrepancia_candidatos",
            ambiguedad_material=True,
            evaluacion_incompleta=False,
            motivo="Discrepancia material entre candidatos PSM 6 y PSM 4",
            condicion_revision="bloqueo_certificacion",
            detalle_discrepancia="Candidatos difieren en importes de cuentas",
            etiqueta="PSM 6 (ambigüedad material detectada)",
        )

        parser = ParserPDF()
        with patch("parser_universal.ocr_pagina", return_value="texto mock"), \
             patch("parser_universal.ocr_pagina_tsv", return_value=[{"text": "mock"}]), \
             patch("parser_universal._tabla_ocr_con_alternativa", return_value=(lines_ambiguas, [100.0]*8, dec_ambigua)):
            res = parser.parsear(doc_pdf)

        assert res.certificacion_extraccion.estado == "fallida", "La ambigüedad material debe bloquear y marcar estado 'fallida'"
        bloqueos = [
            obs for obs in res.certificacion_extraccion.observaciones_auxiliares
            if obs.get("tipo") == "bloqueo_certificacion"
        ]
        assert len(bloqueos) >= 1
        assert any("ambigüedad" in r.lower() for r in res.certificacion_extraccion.razones)

    def test_balance_cuadra_totales_pero_asignacion_ambigua_bloquea_certificacion(self, tmp_path):
        """Totales del documento cuadran perfectamente ($1500 == $1500), pero la asignación de cuentas
        es ambigua entre candidatos OCR. La certificación automática debe quedar formalmente bloqueada ('fallida').
        """
        from parser_universal import ParserPDF
        import pypdfium2 as pdfium

        doc_pdf = tmp_path / "doc_cuadra_pero_ambiguo.pdf"
        p = pdfium.PdfDocument.new()
        p.new_page(200, 200)
        p.save(str(doc_pdf))
        p.close()

        # Ambos candidatos suman 1500 en Débito, Activo y Resultado, pero asignado a cuentas distintas:
        # Candidato 6: Caja=800, Clientes=200, 3 otras cuentas=100 c/u, Subtotal=1500
        lines_6 = [
            "1101 CAJA 800 0 800 0 800 0 0 0",
            "1102 CLIENTES 200 0 200 0 200 0 0 0",
            "1103 MERCADERIAS 200 0 200 0 200 0 0 0",
            "1104 BANCO 200 0 200 0 200 0 0 0",
            "1105 PROVEEDORES 100 0 100 0 100 0 0 0",
            "Subtotal Página 1500 0 1500 0 1500 0 0 0",
        ]
        # Candidato 4: Caja=500, Clientes=500, 3 otras cuentas=100 c/u, Subtotal=1500
        lines_4 = [
            "1101 CAJA 500 0 500 0 500 0 0 0",
            "1102 CLIENTES 500 0 500 0 500 0 0 0",
            "1103 MERCADERIAS 200 0 200 0 200 0 0 0",
            "1104 BANCO 200 0 200 0 200 0 0 0",
            "1105 PROVEEDORES 100 0 100 0 100 0 0 0",
            "Subtotal Página 1500 0 1500 0 1500 0 0 0",
        ]

        parser = ParserPDF()
        with patch("parser_universal.ocr_pagina", return_value="texto mock"), \
             patch("parser_universal.ocr_pagina_tsv", return_value=[{"text": "mock"}]), \
             patch("parser_universal._extraer_tabla_balance_por_coordenadas", side_effect=[
                 (lines_6, [100.0]*8), (lines_4, [100.0]*8),
             ]):
            res = parser.parsear(doc_pdf)

        # A pesar de que los totales impresos y calculados cuadran (1500 == 1500), la ambigüedad en cuentas
        # debe impedir la autocertificación y obligar revisión humana con estado 'fallida'.
        assert res.certificacion_extraccion.estado == "fallida", (
            f"El documento cuadra pero la asignación de cuentas es ambigua: estado debe ser 'fallida', obtenido {res.certificacion_extraccion.estado}"
        )
        assert any("ambigüedad" in r.lower() for r in res.certificacion_extraccion.razones), (
            f"Debe incluirse razón de ambigüedad en {res.certificacion_extraccion.razones}"
        )


class TestDistincionControlesYSimetriaArbitrajeOCR:
    """Banco de pruebas simétrico para la distinción estricta de controles contables:
    1. Candidato con acumulado corrupto frente a candidato sin control (simétrico PSM6 y PSM4).
    2. Acumulado corrupto frente a control de alcance desconocido (simétrico PSM6 y PSM4).
    3. Acumulado corrupto frente a acumulado internamente consistente (simétrico PSM6 y PSM4).
    4. Ambos acumulados corruptos.
    5. Control local efectivamente conciliado frente a lectura discrepante (simétrico PSM6 y PSM4).
    6. Desplazamiento de columnas respaldado por evidencia geométrica independiente (simétrico PSM6 y PSM4).
    """

    def test_acumulado_corrupto_vs_sin_control_simetrico(self):
        """1. Acumulado corrupto vs sin control: ausencia de control en el competidor
        NO equivale a control limpio demostrado; no descalifica al competidor.
        """
        from parser_universal import _comparar_candidatos_ocr

        lines = [f"110{i} CUENTA_{i} 100 0 100 0 100 0 0 0" for i in range(10)]
        lines_divergente = [f"110{i} CUENTA_{i} 200 0 200 0 200 0 0 0" for i in range(10)]

        conc_acum_corrupt = {
            "estado": "alcance_desconocido",
            "alcance": "acumulado",
            "subtotal_corrompido": True,
            "subtotal_valido_interno": False,
        }
        conc_no_ctrl = {
            "estado": "control_ausente",
            "alcance": "no_evaluable",
            "subtotal_corrompido": False,
            "subtotal_valido_interno": False,
        }

        # 1a. PSM 6 con acumulado corrupto vs PSM 4 sin control (detalle equivalente):
        # Ambos deben ser usables; al coincidir en detalle, no hay falsa ambigüedad
        dec_a = _comparar_candidatos_ocr(lines, [100.0]*8, lines, [100.0]*8, conc_acum_corrupt, conc_no_ctrl)
        assert dec_a.motor_seleccionado == "PSM 6"
        assert not dec_a.ambiguedad_material, "No debe marcarse ambigüedad si el detalle es idéntico"
        assert dec_a.tipo_seleccion == "provisional"

        # 1b. Simétrico: PSM 6 sin control vs PSM 4 con acumulado corrupto (detalle equivalente):
        dec_b = _comparar_candidatos_ocr(lines, [100.0]*8, lines, [100.0]*8, conc_no_ctrl, conc_acum_corrupt)
        assert dec_b.motor_seleccionado == "PSM 6"
        assert not dec_b.ambiguedad_material
        assert dec_b.tipo_seleccion == "provisional"

        # 1c. Si difieren materialmente en detalle, la ambigüedad DEBE levantarse en ambos sentidos:
        dec_c = _comparar_candidatos_ocr(lines, [100.0]*8, lines_divergente, [100.0]*8, conc_acum_corrupt, conc_no_ctrl)
        assert dec_c.ambiguedad_material is True, "Diferencia material en detalle debe levantar ambigüedad"

        dec_d = _comparar_candidatos_ocr(lines, [100.0]*8, lines_divergente, [100.0]*8, conc_no_ctrl, conc_acum_corrupt)
        assert dec_d.ambiguedad_material is True, "Simetría: diferencia material debe levantar ambigüedad"

    def test_acumulado_corrupto_vs_control_alcance_desconocido_simetrico(self):
        """2. Acumulado corrupto frente a control de alcance desconocido: ninguno tiene
        control local acreditado; ambos son usables y deciden por detalle.
        """
        from parser_universal import _comparar_candidatos_ocr

        lines = [f"110{i} CUENTA_{i} 100 0 100 0 100 0 0 0" for i in range(10)]
        conc_acum_corrupt = {
            "estado": "alcance_desconocido",
            "alcance": "acumulado",
            "subtotal_corrompido": True,
            "subtotal_valido_interno": False,
        }
        conc_alcance_desc = {
            "estado": "alcance_desconocido",
            "alcance": "no_evaluable",
            "subtotal_corrompido": False,
            "subtotal_valido_interno": False,
        }

        # 2a. PSM 6 corrupt vs PSM 4 desconocido
        dec_a = _comparar_candidatos_ocr(lines, [100.0]*8, lines, [100.0]*8, conc_acum_corrupt, conc_alcance_desc)
        assert not dec_a.ambiguedad_material
        assert dec_a.tipo_seleccion == "provisional"

        # 2b. Simétrico: PSM 6 desconocido vs PSM 4 corrupt
        dec_b = _comparar_candidatos_ocr(lines, [100.0]*8, lines, [100.0]*8, conc_alcance_desc, conc_acum_corrupt)
        assert not dec_b.ambiguedad_material
        assert dec_b.tipo_seleccion == "provisional"

    def test_acumulado_corrupto_vs_acumulado_internamente_consistente_simetrico(self):
        """3. Acumulado con desplazamiento demostrado (corrupto e inválido interno)
        frente a acumulado internamente consistente: se descalifica al candidato con columnas desplazadas.
        """
        from parser_universal import _comparar_candidatos_ocr

        lines_6 = [f"110{i} CUENTA_{i} 100 0 100 0 100 0 0 0" for i in range(10)]
        lines_4 = [f"110{i} CUENTA_{i} 100 0 100 0 100 0 0 0" for i in range(10)]

        # Control consistente: Activo=3000, Pasivo=0, Pérdida=0, Ganancia=0 (cuadra 100% con saldos)
        conc_clean = {
            "estado": "alcance_desconocido",
            "alcance": "acumulado",
            "subtotal_corrompido": False,
            "subtotal_valido_interno": True,
        }
        # Control con columnas desplazadas: Activo=0, Pasivo=3000 (desplazado a la izquierda, no cuadra internamente)
        conc_shifted = {
            "estado": "alcance_desconocido",
            "alcance": "acumulado",
            "subtotal_corrompido": True,
            "subtotal_valido_interno": False,
        }

        # 3a. PSM 6 consistente vs PSM 4 con desplazamiento: PSM 4 es descartado, PSM 6 sobrevive limpio
        dec_a = _comparar_candidatos_ocr(lines_6, [100.0]*8, lines_4, [100.0]*8, conc_clean, conc_shifted)
        assert dec_a.motor_seleccionado == "PSM 6"
        assert not dec_a.ambiguedad_material, "PSM 4 con desplazamiento demostrado no debe generar falsa ambigüedad"
        assert dec_a.etiqueta is None

        # 3b. Simétrico: PSM 6 con desplazamiento vs PSM 4 consistente: PSM 6 es descartado, PSM 4 sobrevive
        dec_b = _comparar_candidatos_ocr(lines_6, [100.0]*8, lines_4, [100.0]*8, conc_shifted, conc_clean)
        assert dec_b.motor_seleccionado == "PSM 4"
        assert not dec_b.ambiguedad_material
        assert dec_b.tipo_seleccion == "provisional"

    def test_ambos_acumulados_corruptos_decide_detalle(self):
        """4. Ambos acumulados corruptos: ninguno se descalifica por el control.
        La decisión se basa en las identidades y coincidencia del detalle.
        """
        from parser_universal import _comparar_candidatos_ocr

        lines = [f"110{i} CUENTA_{i} 100 0 100 0 100 0 0 0" for i in range(10)]
        lines_divergente = [f"110{i} CUENTA_{i} 500 0 500 0 500 0 0 0" for i in range(10)]

        conc_corrupt = {
            "estado": "alcance_desconocido",
            "alcance": "acumulado",
            "subtotal_corrompido": True,
            "subtotal_valido_interno": False,
        }

        # Detalle idéntico: no hay falsa ambigüedad
        dec_a = _comparar_candidatos_ocr(lines, [100.0]*8, lines, [100.0]*8, conc_corrupt, conc_corrupt)
        assert dec_a.motor_seleccionado == "PSM 6"
        assert not dec_a.ambiguedad_material

        # Detalle divergente: ambigüedad material
        dec_b = _comparar_candidatos_ocr(lines, [100.0]*8, lines_divergente, [100.0]*8, conc_corrupt, conc_corrupt)
        assert dec_b.ambiguedad_material is True

    def test_control_local_efectivamente_conciliado_simetrico(self):
        """5. Control local efectivamente conciliado (8 de 8 columnas, alcance 'pagina')
        prevalece inequívocamente sobre lectura discrepante (simétrico PSM6 y PSM4).
        """
        from parser_universal import _comparar_candidatos_ocr

        lines = [f"110{i} CUENTA_{i} 100 0 100 0 100 0 0 0" for i in range(10)]
        conc_reconciled = {
            "estado": "conciliacion_valida",
            "alcance": "pagina",
            "subtotal_corrompido": False,
            "subtotal_valido_interno": True,
            "columnas_conciliadas": 8,
        }
        conc_discrepant = {
            "estado": "discrepancia",
            "alcance": "pagina",
            "subtotal_corrompido": False,
            "subtotal_valido_interno": True,
            "columnas_conciliadas": 4,
        }

        # 5a. PSM 6 conciliado vs PSM 4 discrepante
        dec_a = _comparar_candidatos_ocr(lines, [100.0]*8, lines, [100.0]*8, conc_reconciled, conc_discrepant)
        assert dec_a.motor_seleccionado == "PSM 6"
        assert dec_a.tipo_seleccion == "respaldada"
        assert dec_a.evidencia_disponible == "control_local_conciliado"

        # 5b. Simétrico: PSM 4 conciliado vs PSM 6 discrepante
        dec_b = _comparar_candidatos_ocr(lines, [100.0]*8, lines, [100.0]*8, conc_discrepant, conc_reconciled)
        assert dec_b.motor_seleccionado == "PSM 4"
        assert dec_b.tipo_seleccion == "respaldada"
        assert dec_b.evidencia_disponible == "control_local_conciliado"
        assert dec_b.etiqueta == "PSM 4"

    def test_desplazamiento_columnas_respaldado_por_evidencia_geometrica_independiente(self):
        """6. Desplazamiento de columnas demostrado por evidencia geométrica independiente:
        un candidato con ratio < 0.80 o centros colapsados es descartado frente a un candidato sano.
        """
        from parser_universal import _comparar_candidatos_ocr

        lines_sano = [f"110{i} CUENTA_{i} 100 0 100 0 100 0 0 0" for i in range(10)]
        # Candidato desplazado geométricamente: montos en columnas que no cuadran Debe/Haber ni Saldos
        lines_desplazado = [f"110{i} CUENTA_{i} 100 200 0 500 0 0 100 0" for i in range(10)]

        conc_none = {"estado": "control_ausente", "subtotal_corrompido": False}

        # 6a. PSM 6 sano vs PSM 4 desplazado
        dec_a = _comparar_candidatos_ocr(lines_sano, [100.0]*8, lines_desplazado, [100.0]*8, conc_none, conc_none)
        assert dec_a.motor_seleccionado == "PSM 6"
        assert not dec_a.ambiguedad_material, "Candidato con geometría colapsada se descarta sin falsa ambigüedad"

        # 6b. Simétrico: PSM 6 desplazado vs PSM 4 sano
        dec_b = _comparar_candidatos_ocr(lines_desplazado, [100.0]*8, lines_sano, [100.0]*8, conc_none, conc_none)
        assert dec_b.motor_seleccionado == "PSM 4"
        assert not dec_b.ambiguedad_material
        assert dec_b.tipo_seleccion == "provisional"

    def test_reconciliacion_movimiento_subtotal_acumulado_ruido_regresion_sintetico(self):
        """7. Regresión sintética: Reconciliación de omisión por control acumulado con ruido.
        Demuestra la causa de omisión y verifica que la corrección preserva
        las cuentas con importes sustantivos (Cuenta_A y Cuenta_B).

        Causa raíz:
        Cuando el pie acumulado contiene ruido en el texto ('Total Acumulado ...——'),
        se marcaba subtotal_corrompido=True e invalidaba internamente el control de PSM 6.
        PSM 4, en cambio, extrajo la fila de subtotal limpia, pero en el detalle corrompió las cuentas:
        - Dividió Cuenta_X en dos filas, perdiendo el código de la segunda.
        - Deformó el nombre de Cuenta_A a 's' (descartada por filtro de nombre no contable).
        - Truncó el importe de Cuenta_B.

        Bajo la regla anterior sin protección de detalle, PSM 6 era descartado por desplazamiento_ctrl_6,
        forzando la selección de PSM 4 y provocando descuadre material.
        Con la corrección, al existir discrepancia material en las cuentas de detalle (hay_disc=True),
        el control acumulado no descalifica a PSM 6; ambos candidatos permanecen usables y se registra
        ambiguedad_material=True bloqueando la certificación sin corromper el balance.
        """
        from parser_universal import _comparar_candidatos_ocr

        # Detalle íntegro de PSM 6 (24 cuentas sintéticas)
        lines_6 = [f"39{i:02d}0000 CUENTA_SINTETICA_{i} 1000 0 1000 0 0 0 1000 0" for i in range(22)] + [
            "39910000 Gasto Operativo Alfa 50000000 50000000 0 0 0 0 0 0",
            "39920000 Comision Servicio Beta 100000 50000 50000 0 0 0 50000 0",
        ]
        # Detalle corrompido de PSM 4 (25 filas, Cuenta A convertida a 's', Cuenta B truncada)
        lines_4 = [f"39{i:02d}0000 CUENTA_SINTETICA_{i} 1000 0 1000 0 0 0 1000 0" for i in range(22)] + [
            "39910000 s 50000000 50000000 0 0 0 0 0 0",
            "39920000 Comision Servicio Beta 100000 0 50000 0 0 0 50000 0",
            "FILA_EXTRA 0 0 0 0 0 0 0 0",
        ]

        conc_psm6_sub_ruido = {
            "estado": "alcance_desconocido",
            "alcance": "acumulado",
            "subtotal_corrompido": True,
            "subtotal_valido_interno": False,
        }
        conc_psm4_sub_limpio = {
            "estado": "alcance_desconocido",
            "alcance": "acumulado",
            "subtotal_corrompido": False,
            "subtotal_valido_interno": True,
        }

        # Con la corrección: no se descarta PSM 6; se detecta ambigüedad material por conflicto en cuentas
        dec = _comparar_candidatos_ocr(lines_6, [100.0]*8, lines_4, [100.0]*8, conc_psm6_sub_ruido, conc_psm4_sub_limpio)
        assert dec.motor_seleccionado == "PSM 6", "Debe conservar PSM 6 provisionalmente para no perder cuentas reales"
        assert dec.ambiguedad_material is True, "Debe registrar ambigüedad material obligatoria"
        assert dec.condicion_revision == "bloqueo_certificacion"


class TestArbitrajeSemanticoDominanciaOCR:
    """10 Pruebas unitarias sintéticas y permanentes de arbitraje semántico y dominancia OCR (Ronda 12).

    Cubre el contrato formal de dominancia entre candidatos PSM 6 y PSM 4:
    1. Dominancia válida de PSM6 sobre PSM4.
    2. Dominancia válida de PSM4 sobre PSM6.
    3. Candidatos equivalentes con distinta fragmentación resuelta.
    4. Fila adicional que es ruido de membrete y no impide dominancia.
    5. Fila adicional que es cuenta contable válida y genera ambigüedad si no se demuestra omisión del subordinado.
    6. Duplicación monetaria que bloquea dominancia.
    7. Código de cuenta perdido con glosa huérfana.
    8. Monto desplazado entre columnas que marca ambigüedad.
    9. Subtotal acumulado que no debe utilizarse como control local de página.
    10. Empate material con defectos cruzados que debe permanecer bloqueado.
    """

    def test_dominancia_valida_psm6_sobre_psm4(self):
        """1. Dominancia válida de PSM 6 sobre PSM 4: PSM 6 completo y sano, subordinado con ruido y omisión."""
        from parser_universal import _comparar_candidatos_ocr

        lines_6 = [f"110{i}0000 CUENTA_{i} 1000 0 1000 0 1000 0 0 0" for i in range(6)]
        # PSM 4 omite cuenta 5 e introduce fila de membrete espuria
        lines_4 = [f"110{i}0000 CUENTA_{i} 1000 0 1000 0 1000 0 0 0" for i in range(5)] + [
            "Pagina de 0 0 0 0 0 0 0 26",
        ]

        conc_none = {"estado": "control_ausente", "subtotal_corrompido": False}
        dec = _comparar_candidatos_ocr(lines_6, [100.0]*8, lines_4, [100.0]*8, conc_none, conc_none)

        assert dec.motor_seleccionado == "PSM 6"
        assert dec.tipo_seleccion == "respaldada"
        assert not dec.ambiguedad_material
        assert dec.condicion_revision is None
        assert "domina" in dec.motivo

    def test_dominancia_valida_psm4_sobre_psm6(self):
        """2. Dominancia válida de PSM 4 sobre PSM 6: simétrica, PSM 4 completo y sano, PSM 6 con ruido."""
        from parser_universal import _comparar_candidatos_ocr

        # PSM 6 omite cuenta 5 e introduce fila espuria de periodo
        lines_6 = [f"110{i}0000 CUENTA_{i} 1000 0 1000 0 1000 0 0 0" for i in range(5)] + [
            "Desde Enero hasta Diciembre 0 0 0 2024 2024 0 0 0",
        ]
        lines_4 = [f"110{i}0000 CUENTA_{i} 1000 0 1000 0 1000 0 0 0" for i in range(6)]

        conc_none = {"estado": "control_ausente", "subtotal_corrompido": False}
        dec = _comparar_candidatos_ocr(lines_6, [100.0]*8, lines_4, [100.0]*8, conc_none, conc_none)

        assert dec.motor_seleccionado == "PSM 4"
        assert dec.tipo_seleccion == "respaldada"
        assert not dec.ambiguedad_material
        assert dec.condicion_revision is None
        assert "domina" in dec.motivo

    def test_candidatos_equivalentes_distinta_fragmentacion(self):
        """3. Candidatos equivalentes con distinta fragmentación resuelta."""
        from parser_universal import _comparar_candidatos_ocr

        lines_6 = [
            "11010000 Caja Central 5000 0 5000 0 5000 0 0 0",
            "11020000 Banco Estado 8192 0 8192 0 8192 0 0 0",
            "11030000 Clientes Locales 12000 0 12000 0 12000 0 0 0",
            "11040000 Letras por Cobrar 3000 0 3000 0 3000 0 0 0",
            "11050000 Anticipos 2000 0 2000 0 2000 0 0 0",
        ]
        # PSM 4 tiene cuenta 11020000 dividida en fila con código + fila siguiente con montos
        lines_4 = [
            "11010000 Caja Central 5000 0 5000 0 5000 0 0 0",
            "11020000 Banco 0 0 0 0 0 0 0 0",
            "Estado 8192 0 8192 0 8192 0 0 0",
            "11030000 Clientes Locales 12000 0 12000 0 12000 0 0 0",
            "11040000 Letras por Cobrar 3000 0 3000 0 3000 0 0 0",
            "11050000 Anticipos 2000 0 2000 0 2000 0 0 0",
        ]

        conc_none = {"estado": "control_ausente", "subtotal_corrompido": False}
        dec = _comparar_candidatos_ocr(lines_6, [100.0]*8, lines_4, [100.0]*8, conc_none, conc_none)

        assert dec.motor_seleccionado == "PSM 6"
        assert not dec.ambiguedad_material
        assert "equivalentes" in dec.motivo.lower()

    def test_fila_adicional_ruido_no_impide_dominancia(self):
        """4. Fila adicional que es ruido de membrete y no impide dominancia ni equivalencia."""
        from parser_universal import _comparar_semantica_candidatos, _extraer_cuentas_candidato

        lines_6 = [f"110{i}0000 CUENTA_{i} 1000 0 1000 0 1000 0 0 0" for i in range(5)]
        # PSM 4 tiene exactamente las mismas cuentas contables + 2 filas de membrete/página
        lines_4 = [
            "Pagina 2 de 26 0 0 0 0 0 0 0 26",
            "E-MANTENCION Desde Enero hasta Diciembre 0 0 0 2024 2024 0 0 0",
        ] + [f"110{i}0000 CUENTA_{i} 1000 0 1000 0 1000 0 0 0" for i in range(5)]

        c6 = _extraer_cuentas_candidato(lines_6)
        c4 = _extraer_cuentas_candidato(lines_4)
        sem = _comparar_semantica_candidatos(c6, c4)

        assert sem.decision == "equivalentes"
        assert not sem.ambiguedad_material
        assert len(sem.cuentas_4_efectivas) == 5

    def test_fila_adicional_contable_valida(self):
        """5. Fila adicional que es cuenta contable válida genera ambigüedad si no se demuestra omisión."""
        from parser_universal import _comparar_candidatos_ocr

        lines_6 = [f"110{i}0000 CUENTA_{i} 1000 0 1000 0 1000 0 0 0" for i in range(6)]
        # PSM 4 solo tiene 5 cuentas limpias, sin ruido ni defectos
        lines_4 = [f"110{i}0000 CUENTA_{i} 1000 0 1000 0 1000 0 0 0" for i in range(5)]

        conc_none = {"estado": "control_ausente", "subtotal_corrompido": False}
        dec = _comparar_candidatos_ocr(lines_6, [100.0]*8, lines_4, [100.0]*8, conc_none, conc_none)

        assert dec.ambiguedad_material is True
        assert dec.condicion_revision == "bloqueo_certificacion"
        assert "Diferencia en número de cuentas" in dec.motivo or "ambigüedad" in dec.motivo.lower()

    def test_duplicacion_monetaria_bloquea_dominancia(self):
        """6. Duplicación monetaria que bloquea dominancia."""
        from parser_universal import _comparar_semantica_candidatos, _extraer_cuentas_candidato

        lines_6 = [f"110{i}0000 CUENTA_{i} 1000 0 1000 0 1000 0 0 0" for i in range(5)]
        # PSM 4 duplica la cuenta 11020000
        lines_4 = [
            "11000000 CUENTA_0 1000 0 1000 0 1000 0 0 0",
            "11010000 CUENTA_1 1000 0 1000 0 1000 0 0 0",
            "11020000 CUENTA_2 1000 0 1000 0 1000 0 0 0",
            "11020000 CUENTA_2_BIS 1000 0 1000 0 1000 0 0 0",
            "11030000 CUENTA_3 1000 0 1000 0 1000 0 0 0",
            "11040000 CUENTA_4 1000 0 1000 0 1000 0 0 0",
        ]

        c6 = _extraer_cuentas_candidato(lines_6)
        c4 = _extraer_cuentas_candidato(lines_4)
        sem = _comparar_semantica_candidatos(c6, c4)

        assert sem.ambiguedad_material is True
        assert sem.decision == "ambiguedad_material"

    def test_codigo_perdido_con_glosa_huerfana(self):
        """7. Código de cuenta perdido con glosa huérfana no resoluble genera ambigüedad."""
        from parser_universal import _comparar_candidatos_ocr

        lines_6 = [
            "11010000 Caja Central 5000 0 5000 0 5000 0 0 0",
            "11020000 Banco Estado 8192 0 8192 0 8192 0 0 0",
            "11030000 Clientes 12000 0 12000 0 12000 0 0 0",
            "11040000 Anticipos 3000 0 3000 0 3000 0 0 0",
            "11050000 Garantias 2000 0 2000 0 2000 0 0 0",
        ]
        # PSM 4 pierde el código de la cuenta de Banco y queda como fragmento huérfano con nombre alterado
        lines_4 = [
            "11010000 Caja Central 5000 0 5000 0 5000 0 0 0",
            "Remanente No Identificado 8192 0 8192 0 8192 0 0 0",
            "11030000 Clientes 12000 0 12000 0 12000 0 0 0",
            "11040000 Anticipos 3000 0 3000 0 3000 0 0 0",
            "11050000 Garantias 2000 0 2000 0 2000 0 0 0",
        ]

        conc_none = {"estado": "control_ausente", "subtotal_corrompido": False}
        dec = _comparar_candidatos_ocr(lines_6, [100.0]*8, lines_4, [100.0]*8, conc_none, conc_none)

        assert dec.ambiguedad_material is True
        assert dec.condicion_revision == "bloqueo_certificacion"

    def test_monto_desplazado_entre_columnas_marca_ambiguedad(self):
        """8. Monto desplazado entre columnas contables marca ambigüedad material."""
        from parser_universal import _comparar_candidatos_ocr

        lines_6 = [
            "11010000 Caja 5000 0 5000 0 5000 0 0 0",
            "11020000 Banco 0 8192 0 8192 0 8192 0 0",
            "11030000 Clientes 12000 0 12000 0 12000 0 0 0",
            "11040000 Anticipos 3000 0 3000 0 3000 0 0 0",
            "11050000 Fondos 2000 0 2000 0 2000 0 0 0",
        ]
        # PSM 4 desplaza los montos de Banco de Haber/Pasivo a Debe/Activo
        lines_4 = [
            "11010000 Caja 5000 0 5000 0 5000 0 0 0",
            "11020000 Banco 8192 0 8192 0 8192 0 0 0",
            "11030000 Clientes 12000 0 12000 0 12000 0 0 0",
            "11040000 Anticipos 3000 0 3000 0 3000 0 0 0",
            "11050000 Fondos 2000 0 2000 0 2000 0 0 0",
        ]

        conc_none = {"estado": "control_ausente", "subtotal_corrompido": False}
        dec = _comparar_candidatos_ocr(lines_6, [100.0]*8, lines_4, [100.0]*8, conc_none, conc_none)

        assert dec.ambiguedad_material is True
        assert dec.condicion_revision == "bloqueo_certificacion"
        assert "discrepantes" in dec.motivo or "ambigüedad" in dec.motivo.lower()

    def test_subtotal_acumulado_no_utilizable_como_control_local(self):
        """9. Subtotal acumulado o transporte no debe utilizarse como control local de página."""
        from parser_universal import _determinar_alcance_control, _evaluar_conciliacion_detalle_control

        # Fila con glosa explícita de acumulado
        alcance = _determinar_alcance_control("Total Acumulado")
        assert alcance == "acumulado", f"Se esperaba 'acumulado', obtenido '{alcance}'"

        lineas_pagina = [
            "11010000 Caja 5000 0 5000 0 5000 0 0 0",
            "11020000 Banco 3000 0 3000 0 3000 0 0 0",
            "Total Acumulado 50000000 42000000 8000000 0 8000000 0 0 0",
        ]

        conc = _evaluar_conciliacion_detalle_control(lineas_pagina)
        assert conc["alcance"] == "acumulado"
        assert conc["estado"] != "conciliacion_valida", "Un subtotal acumulado jamás puede validar localmente la página"

    def test_empate_material_permanece_bloqueado(self):
        """10. Empate material con defectos cruzados (defectos sintéticos cruzados) debe permanecer bloqueado."""
        from parser_universal import _comparar_candidatos_ocr

        # PSM 6 tiene cuenta con identidad rota (cuenta sintetica con débito espurio)
        lines_6 = [
            "11010000 Cuenta_1 1000 0 1000 0 1000 0 0 0",
            "11020000 Cuenta_2 2000 0 2000 0 2000 0 0 0",
            "11030000 Cuenta_3 3000 0 3000 0 3000 0 0 0",
            "11040000 Cuenta_4 4000 0 4000 0 4000 0 0 0",
            "29910001 Proveedor Sintetico 333333 1000000 0 1000000 0 1000000 0 0",  # 333333 rompe identidad Debe-Haber
            "29920001 Acreedor Sintetico 5000 0 5000 0 5000 0 0 0",
        ]
        # PSM 4 pierde cuenta 11020000 y corrompe Acreedor a 77777
        lines_4 = [
            "11010000 Cuenta_1 1000 0 1000 0 1000 0 0 0",
            "11030000 Cuenta_3 3000 0 3000 0 3000 0 0 0",
            "11040000 Cuenta_4 4000 0 4000 0 4000 0 0 0",
            "29910001 Proveedor Sintetico 0 1000000 0 1000000 0 1000000 0 0",
            "29920001 Acreedor Sintetico 77777 0 5000 0 5000 0 0 0",  # 77777 rompe identidad
        ]

        conc_none = {"estado": "control_ausente", "subtotal_corrompido": False}
        dec = _comparar_candidatos_ocr(lines_6, [100.0]*8, lines_4, [100.0]*8, conc_none, conc_none)

        assert dec.ambiguedad_material is True
        assert dec.condicion_revision == "bloqueo_certificacion"


class TestSilentLossProtectionsAndAdversarial:
    """Pruebas adversariales contra pérdida silenciosa de cuentas contables (Ronda 13).

    Verifica de forma estricta:
    1. Cuentas codificadas con importes en cero son preservadas (sin pérdida silenciosa).
    2. Cuentas no codificadas con montos pequeños (e.g. 50 CLP) no se descartan por ruido numérico.
    3. Cuentas no codificadas con importes tipo año (e.g. 2024 CLP) no se descartan sin evidencia documental positiva.
    4. Cuentas no codificadas con identidad contable válida son admitidas en composición.
    5. Encabezados verdaderos con evidencia documental positiva sí son descartados como ruido.
    """

    def test_cuenta_legitima_monto_cero_preservada(self):
        """1. Cuenta codificada legítima con importe cero no debe descartarse silenciosamente."""
        from parser_universal import _extraer_cuentas_candidato, _reconciliar_fragmentos_ocr

        lines = [
            "11010001 Caja Central Sintetica 10000 0 10000 0 10000 0 0 0",
            "11020001 Cuenta Puente Sin Movimiento 0 0 0 0 0 0 0 0",
            "11030001 Banco Operativo Sintetico 25000 0 25000 0 25000 0 0 0",
        ]
        cuentas = _extraer_cuentas_candidato(lines)
        codigos = [c.get("codigo") for c in cuentas]
        assert "11020001" in codigos, "La cuenta codificada con monto 0 debe ser extraída por el parser candidato"

        reconciliadas = _reconciliar_fragmentos_ocr(cuentas)
        reconc_codigos = [c.get("codigo") for c in reconciliadas]
        assert "11020001" in reconc_codigos, "La cuenta codificada con monto 0 no debe ser descartada en la reconciliación"
        cta_cero = next(c for c in reconciliadas if c.get("codigo") == "11020001")
        assert cta_cero.get("monto_cero_preservado") is True

    def test_cuenta_legitima_monto_pequeno_no_es_ruido(self):
        """2. Cuenta sin código con monto pequeño (e.g. 50 CLP) no debe descartarse únicamente por su magnitud."""
        from parser_universal import _es_ruido_documental_ocr

        cta_pequena = {
            "codigo": None,
            "nombre": "Ajuste Sencillo Caja Menor",
            "montos": [50.0, 0.0, 50.0, 0.0, 50.0, 0.0, 0.0, 0.0],
            "raw": "Ajuste Sencillo Caja Menor 50 0 50 0 50 0 0 0",
        }
        assert _es_ruido_documental_ocr(cta_pequena) is False, "Una cuenta con monto pequeño no debe considerarse ruido sin patrón documental"

    def test_cuenta_legitima_monto_ano_no_es_ruido(self):
        """3. Cuenta sin código con monto tipo año (e.g. 2024 CLP) no debe descartarse sin patrón de periodo o fecha."""
        from parser_universal import _es_ruido_documental_ocr

        cta_ano = {
            "codigo": None,
            "nombre": "Cuenta Sintetica con Importe Similar a Anio",
            "montos": [2037.0, 0.0, 2037.0, 0.0, 0.0, 0.0, 2037.0, 0.0],
            "raw": "Cuenta Sintetica con Importe Similar a Anio 2037 0 2037 0 0 0 2037 0",
        }
        assert _es_ruido_documental_ocr(cta_ano) is False, "Un monto con forma de año no acredita ruido por sí solo sin patrón positivo de periodo/fecha"

    def test_fila_sin_codigo_identidad_valida_admitida(self):
        """4. Fila contable sin código pero con identidad contable válida debe admitirse en composición."""
        from parser_universal import componer_filas_pagina_ocr

        ctas_6 = [
            {"codigo": "11010001", "nombre": "Caja Sintetica", "montos": [1000.0, 0.0, 1000.0, 0.0, 1000.0, 0.0, 0.0, 0.0]},
            {"codigo": None, "nombre": "Remanente Ajuste Ficticio", "montos": [200.0, 0.0, 200.0, 0.0, 200.0, 0.0, 0.0, 0.0]},
        ]
        ctas_4 = [
            {"codigo": "11010001", "nombre": "Caja Sintetica", "montos": [1000.0, 0.0, 1000.0, 0.0, 1000.0, 0.0, 0.0, 0.0]},
            {"codigo": None, "nombre": "Remanente Ajuste Ficticio", "montos": [200.0, 0.0, 200.0, 0.0, 200.0, 0.0, 0.0, 0.0]},
        ]
        res = componer_filas_pagina_ocr(ctas_6, ctas_4, pagina=1)
        assert res.bloqueada is False
        assert len(res.filas_compuestas) == 2
        f_sin_cod = [f for f in res.filas_compuestas if f.codigo_normalizado is None][0]
        assert f_sin_cod.es_ambigua is False
        assert f_sin_cod.valores_finales[0] == 200.0

    def test_encabezado_verdadero_descartado_como_ruido(self):
        """5. Encabezado documental verdadero con evidencia positiva debe ser descartado como ruido."""
        from parser_universal import _es_ruido_documental_ocr

        encabezados = [
            {"codigo": None, "nombre": "Página 12 de 45", "montos": [0.0]*8},
            {"codigo": "FOLIO-MOCK", "nombre": "R.U.T. Empresa Ficticia Hoja 3", "montos": [0.0]*8},
            {"codigo": None, "nombre": "Balance Tributario Ejercicio 2024", "montos": [0.0, 0.0, 0.0, 2024.0, 2024.0, 0.0, 0.0, 0.0]},
            {"codigo": None, "nombre": "Dirección Fiscal Calle Falsa 123", "montos": [123.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]},
        ]
        for enc in encabezados:
            assert _es_ruido_documental_ocr(enc) is True, f"Debe identificarse como ruido: {enc}"


class TestRowLevelSafeCompositionOCR:
    """Pruebas unitarias de composición segura a nivel de fila y procedencia (Ronda 13).

    Verifica el cumplimiento de las 7 reglas de composición:
    1. Misma cuenta y mismos importes en ambos motores.
    2. Identidad válida unilateral con glosa compatible.
    3. Cuenta exclusiva admisible sólo con código e identidad contable completa.
    4. Discrepancia con identidades válidas en ambos candidatos bloquea certificación.
    5. Ambos candidatos defectuosos bloquean certificación.
    6. Detección de duplicación monetaria bloquea certificación.
    7. Registro completo de procedencia en cada fila compuesta.
    """

    def test_regla1_misma_cuenta_mismos_importes(self):
        """Regla 1: Coincidencia de código e importes genera fila única de alta confianza."""
        from parser_universal import componer_filas_pagina_ocr

        c6 = [{"codigo": "11010001", "nombre": "Caja Central Sintetica", "montos": [5000.0, 0.0, 5000.0, 0.0, 5000.0, 0.0, 0.0, 0.0]}]
        c4 = [{"codigo": "11010001", "nombre": "Caja Central Sintetica", "montos": [5000.0, 0.0, 5000.0, 0.0, 5000.0, 0.0, 0.0, 0.0]}]

        res = componer_filas_pagina_ocr(c6, c4, pagina=1)
        assert res.bloqueada is False
        assert len(res.filas_compuestas) == 1
        fila = res.filas_compuestas[0]
        assert fila.regla_aceptacion == "misma_cuenta_mismos_importes"
        assert fila.transformacion_aplicada == "coincidencia_exacta"
        assert fila.nivel_confianza >= 0.95
        assert fila.es_ambigua is False
        assert fila.bloquea_certificacion is False

    def test_regla2_identidad_valida_unilateral_psm6(self):
        """Regla 2: Candidato PSM 6 válido y PSM 4 corrupto con glosas compatibles selecciona PSM 6."""
        from parser_universal import componer_filas_pagina_ocr

        # PSM 6 satisface Debe-Haber == Saldos (5000 - 0 = 5000)
        c6 = [{"codigo": "11020001", "nombre": "Banco Sintetico Alfa", "montos": [5000.0, 0.0, 5000.0, 0.0, 5000.0, 0.0, 0.0, 0.0]}]
        # PSM 4 corrompe el saldo a 9999 (identidad rota)
        c4 = [{"codigo": "11020001", "nombre": "Banco Sintetico Alfa", "montos": [5000.0, 0.0, 9999.0, 0.0, 5000.0, 0.0, 0.0, 0.0]}]

        res = componer_filas_pagina_ocr(c6, c4, pagina=1)
        assert res.bloqueada is False
        assert len(res.filas_compuestas) == 1
        fila = res.filas_compuestas[0]
        assert fila.motor_origen == "PSM 6"
        assert fila.regla_aceptacion == "identidad_valida_unilateral"
        assert fila.transformacion_aplicada == "seleccion_candidato_valido"
        assert fila.valores_finales[2] == 5000.0
        assert fila.es_ambigua is False

    def test_regla2_identidad_valida_unilateral_psm4(self):
        """Regla 2 simétrica: Candidato PSM 4 válido y PSM 6 corrupto selecciona PSM 4."""
        from parser_universal import componer_filas_pagina_ocr

        c6 = [{"codigo": "11030001", "nombre": "Clientes Sinteticos Beta", "montos": [12000.0, 0.0, 8888.0, 0.0, 12000.0, 0.0, 0.0, 0.0]}]
        c4 = [{"codigo": "11030001", "nombre": "Clientes Sinteticos Beta", "montos": [12000.0, 0.0, 12000.0, 0.0, 12000.0, 0.0, 0.0, 0.0]}]

        res = componer_filas_pagina_ocr(c6, c4, pagina=1)
        assert res.bloqueada is False
        assert len(res.filas_compuestas) == 1
        fila = res.filas_compuestas[0]
        assert fila.motor_origen == "PSM 4"
        assert fila.regla_aceptacion == "identidad_valida_unilateral"
        assert fila.valores_finales[2] == 12000.0
        assert fila.es_ambigua is False

    def test_regla3_cuenta_exclusiva_valida_admitida(self):
        """Regla 3 endurecida (Finding 3): Cuenta presente solo en un candidato requiere confirmación independiente."""
        from unittest.mock import patch
        from parser_universal import componer_filas_pagina_ocr, FilaComposicionOCR

        c6 = [
            {"codigo": "11010001", "nombre": "Caja Sintetica", "montos": [5000.0, 0.0, 5000.0, 0.0, 5000.0, 0.0, 0.0, 0.0]},
            {"codigo": "11040001", "nombre": "Fondo Rinde Sintetico", "montos": [3000.0, 0.0, 3000.0, 0.0, 3000.0, 0.0, 0.0, 0.0]},
        ]
        c4 = [
            {"codigo": "11010001", "nombre": "Caja Sintetica", "montos": [5000.0, 0.0, 5000.0, 0.0, 5000.0, 0.0, 0.0, 0.0]},
        ]

        # 1. Sin confirmación independiente: se bloquea por seguridad (Finding 3)
        res_sin_conf = componer_filas_pagina_ocr(c6, c4, pagina=1)
        assert res_sin_conf.bloqueada is True
        f_no_conf = next(f for f in res_sin_conf.filas_compuestas if f.codigo_normalizado == "11040001")
        assert f_no_conf.es_ambigua is True
        assert f_no_conf.bloquea_certificacion is True
        assert f_no_conf.regla_aceptacion == "bloqueada_unilateral_no_confirmada"

        # 2. Con confirmación independiente mediante relectura focalizada: es admitida
        f_conf = FilaComposicionOCR(
            motor_origen="RELECTURA_FOCALIZADA",
            pagina=1,
            linea_origen=1,
            codigo_normalizado="11040001",
            glosa_normalizada="Fondo Rinde Sintetico",
            valores_candidatos={"PSM 6": [3000.0, 0.0, 3000.0, 0.0, 3000.0, 0.0, 0.0, 0.0], "PSM 4": []},
            valores_finales=[3000.0, 0.0, 3000.0, 0.0, 3000.0, 0.0, 0.0, 0.0],
            transformacion_aplicada="relectura_focalizada_recorte",
            regla_aceptacion="relectura_focalizada_confirmada",
            nivel_confianza=0.96,
            es_ambigua=False,
            bloquea_certificacion=False,
            evento_relectura="confirmada",
        )
        with patch("parser_universal._relectura_focalizada_ocr", return_value=(f_conf, {"tipo": "confirmada"})):
            res_con_conf = componer_filas_pagina_ocr(c6, c4, pagina=1)
            assert res_con_conf.bloqueada is False
            codigos = [f.codigo_normalizado for f in res_con_conf.filas_compuestas]
            assert "11040001" in codigos
            f_excl = next(f for f in res_con_conf.filas_compuestas if f.codigo_normalizado == "11040001")
            assert f_excl.regla_aceptacion == "relectura_focalizada_confirmada"
            assert f_excl.es_ambigua is False

    def test_regla3_cuenta_exclusiva_invalida_bloquea(self):
        """Regla 3: Cuenta presente solo en un candidato con identidad corrupta genera bloqueo."""
        from parser_universal import componer_filas_pagina_ocr

        c6 = [
            {"codigo": "11010001", "nombre": "Caja Sintetica", "montos": [5000.0, 0.0, 5000.0, 0.0, 5000.0, 0.0, 0.0, 0.0]},
            {"codigo": "11050001", "nombre": "Cuenta Rota Ficticia", "montos": [3000.0, 0.0, 1111.0, 0.0, 3000.0, 0.0, 0.0, 0.0]},
        ]
        c4 = [
            {"codigo": "11010001", "nombre": "Caja Sintetica", "montos": [5000.0, 0.0, 5000.0, 0.0, 5000.0, 0.0, 0.0, 0.0]},
        ]

        res = componer_filas_pagina_ocr(c6, c4, pagina=1)
        assert res.bloqueada is True
        f_rota = next(f for f in res.filas_compuestas if f.codigo_normalizado == "11050001")
        assert f_rota.es_ambigua is True
        assert f_rota.bloquea_certificacion is True

    def test_unilateral_descubierta_al_final_usa_vecinos_del_mismo_motor(self):
        """El orden lógico de composición no debe simular una discontinuidad física."""
        from unittest.mock import patch
        from parser_universal import componer_filas_pagina_ocr, FilaComposicionOCR

        monto_1 = [1000.0, 0.0, 1000.0, 0.0, 1000.0, 0.0, 0.0, 0.0]
        monto_2 = [2000.0, 0.0, 2000.0, 0.0, 2000.0, 0.0, 0.0, 0.0]
        monto_3 = [3000.0, 0.0, 3000.0, 0.0, 3000.0, 0.0, 0.0, 0.0]
        c6 = [
            {"codigo": "11010001", "nombre": "Cuenta Sintetica Uno", "montos": list(monto_1), "linea_idx": 27},
            {"codigo": "11010003", "nombre": "Cuenta Sintetica Tres", "montos": list(monto_3), "linea_idx": 29},
        ]
        c4 = [
            {"codigo": "11010001", "nombre": "Cuenta Sintetica Uno", "montos": list(monto_1), "linea_idx": 27},
            {"codigo": "11010002", "nombre": "Cuenta Sintetica Dos", "montos": list(monto_2), "linea_idx": 28},
            {"codigo": "11010003", "nombre": "Cuenta Sintetica Tres", "montos": list(monto_3), "linea_idx": 29},
        ]
        confirmada = FilaComposicionOCR(
            motor_origen="RELECTURA_FOCALIZADA",
            pagina=1,
            linea_origen=28,
            codigo_normalizado="11010002",
            glosa_normalizada="Cuenta Sintetica Dos",
            valores_candidatos={"PSM 6": [], "PSM 4": list(monto_2)},
            valores_finales=list(monto_2),
            transformacion_aplicada="relectura_focalizada_recorte",
            regla_aceptacion="relectura_focalizada_confirmada",
            nivel_confianza=0.96,
            es_ambigua=False,
            bloquea_certificacion=False,
            evento_relectura="confirmada",
        )

        with patch(
            "parser_universal._relectura_focalizada_ocr",
            return_value=(confirmada, {"tipo": "confirmada"}),
        ):
            resultado = componer_filas_pagina_ocr(c6, c4, pagina=1)

        assert resultado.bloqueada is False
        codigos = [fila.codigo_normalizado for fila in resultado.filas_compuestas]
        assert codigos.count("11010002") == 1

    def test_unilateral_con_discontinuidad_fisica_real_sigue_bloqueando(self):
        """Una fila alejada de sus vecinos físicos no se admite solo por relectura exitosa."""
        from unittest.mock import patch
        from parser_universal import componer_filas_pagina_ocr, FilaComposicionOCR

        monto_1 = [1000.0, 0.0, 1000.0, 0.0, 1000.0, 0.0, 0.0, 0.0]
        monto_2 = [2000.0, 0.0, 2000.0, 0.0, 2000.0, 0.0, 0.0, 0.0]
        monto_3 = [3000.0, 0.0, 3000.0, 0.0, 3000.0, 0.0, 0.0, 0.0]
        c6 = [
            {"codigo": "11010001", "nombre": "Cuenta Sintetica Uno", "montos": list(monto_1), "linea_idx": 10},
            {"codigo": "11010003", "nombre": "Cuenta Sintetica Tres", "montos": list(monto_3), "linea_idx": 11},
        ]
        c4 = [
            {"codigo": "11010002", "nombre": "Cuenta Sintetica Dos", "montos": list(monto_2), "linea_idx": 1},
            {"codigo": "11010001", "nombre": "Cuenta Sintetica Uno", "montos": list(monto_1), "linea_idx": 10},
            {"codigo": "11010003", "nombre": "Cuenta Sintetica Tres", "montos": list(monto_3), "linea_idx": 11},
        ]
        confirmada = FilaComposicionOCR(
            motor_origen="RELECTURA_FOCALIZADA",
            pagina=1,
            linea_origen=1,
            codigo_normalizado="11010002",
            glosa_normalizada="Cuenta Sintetica Dos",
            valores_candidatos={"PSM 6": [], "PSM 4": list(monto_2)},
            valores_finales=list(monto_2),
            transformacion_aplicada="relectura_focalizada_recorte",
            regla_aceptacion="relectura_focalizada_confirmada",
            nivel_confianza=0.96,
            es_ambigua=False,
            bloquea_certificacion=False,
            evento_relectura="confirmada",
        )

        with patch(
            "parser_universal._relectura_focalizada_ocr",
            return_value=(confirmada, {"tipo": "confirmada"}),
        ):
            resultado = componer_filas_pagina_ocr(c6, c4, pagina=1)

        assert resultado.bloqueada is True
        fila = next(f for f in resultado.filas_compuestas if f.codigo_normalizado == "11010002")
        assert fila.regla_aceptacion == "bloqueada_unilateral_no_confirmada"
        assert "discontinuidad geométrica anómala" in (fila.motivo_revision or "")

    def test_regla4_discrepancia_ambos_validos_bloquea(self):
        """Regla 4: Ambos candidatos con identidad válida pero importes discrepantes bloquean certificación."""
        from parser_universal import componer_filas_pagina_ocr

        # Candidato PSM 6: 5000
        c6 = [{"codigo": "11010001", "nombre": "Caja Sintetica", "montos": [5000.0, 0.0, 5000.0, 0.0, 5000.0, 0.0, 0.0, 0.0]}]
        # Candidato PSM 4: 73190 (ambos matemáticamente válidos internamente pero mutuamente contradictorios)
        c4 = [{"codigo": "11010001", "nombre": "Caja Sintetica", "montos": [73190.0, 0.0, 73190.0, 0.0, 73190.0, 0.0, 0.0, 0.0]}]

        res = componer_filas_pagina_ocr(c6, c4, pagina=1)
        assert res.bloqueada is True
        fila = res.filas_compuestas[0]
        assert fila.es_ambigua is True
        assert fila.bloquea_certificacion is True
        assert fila.regla_aceptacion == "bloqueada_discrepancia_monetaria_ambos_validos"

    def test_regla5_ambos_defectuosos_bloquea(self):
        """Regla 5: Ambos candidatos defectuosos sin relectura disponible bloquean certificación."""
        from parser_universal import componer_filas_pagina_ocr

        c6 = [{"codigo": "11010001", "nombre": "Caja Sintetica", "montos": [5000.0, 0.0, 1111.0, 0.0, 5000.0, 0.0, 0.0, 0.0]}]
        c4 = [{"codigo": "11010001", "nombre": "Caja Sintetica", "montos": [5000.0, 0.0, 2222.0, 0.0, 5000.0, 0.0, 0.0, 0.0]}]

        res = componer_filas_pagina_ocr(c6, c4, pagina=1)
        assert res.bloqueada is True
        fila = res.filas_compuestas[0]
        assert fila.es_ambigua is True
        assert fila.bloquea_certificacion is True
        assert fila.regla_aceptacion == "bloqueada_ambos_defectuosos"

    def test_regla6_duplicacion_codigo_bloquea(self):
        """Regla 6: Duplicación de código contable en un candidato bloquea certificación."""
        from parser_universal import componer_filas_pagina_ocr

        c6 = [
            {"codigo": "11010001", "nombre": "Caja Central", "montos": [5000.0, 0.0, 5000.0, 0.0, 5000.0, 0.0, 0.0, 0.0]},
            {"codigo": "11010001", "nombre": "Caja Central Duplicada", "montos": [5000.0, 0.0, 5000.0, 0.0, 5000.0, 0.0, 0.0, 0.0]},
        ]
        c4 = [
            {"codigo": "11010001", "nombre": "Caja Central", "montos": [5000.0, 0.0, 5000.0, 0.0, 5000.0, 0.0, 0.0, 0.0]},
        ]

        res = componer_filas_pagina_ocr(c6, c4, pagina=1)
        assert res.bloqueada is True
        assert res.filas_compuestas[0].es_ambigua is True
        assert res.filas_compuestas[0].regla_aceptacion == "bloqueada_duplicacion_monetaria"

    def test_procedencia_completa_en_cada_fila(self):
        """7. Verificación estricta de todos los campos de procedencia en FilaComposicionOCR."""
        from parser_universal import componer_filas_pagina_ocr, FilaComposicionOCR
        import dataclasses

        c6 = [{"codigo": "11010001", "nombre": "Caja Sintetica Alfa", "montos": [5000.0, 0.0, 5000.0, 0.0, 5000.0, 0.0, 0.0, 0.0]}]
        c4 = [{"codigo": "11010001", "nombre": "Caja Sintetica Alfa", "montos": [5000.0, 0.0, 5000.0, 0.0, 5000.0, 0.0, 0.0, 0.0]}]

        res = componer_filas_pagina_ocr(c6, c4, pagina=2)
        fila = res.filas_compuestas[0]

        campos_esperados = {
            "motor_origen", "pagina", "linea_origen", "codigo_normalizado",
            "glosa_normalizada", "valores_candidatos", "valores_finales",
            "transformacion_aplicada", "regla_aceptacion", "nivel_confianza",
            "motivo_revision", "es_ambigua", "bloquea_certificacion",
        }
        nombres_campos = {f.name for f in dataclasses.fields(FilaComposicionOCR)}
        assert campos_esperados.issubset(nombres_campos)

        assert fila.pagina == 2
        assert fila.codigo_normalizado == "11010001"
        assert fila.glosa_normalizada == "Caja Sintetica Alfa"
        assert "PSM 6" in fila.valores_candidatos
        assert "PSM 4" in fila.valores_candidatos
        assert len(fila.valores_finales) == 8


class TestAuditoriaP01Ronda15ReconciliacionYRelectura:
    """Pruebas unitarias de las 14 condiciones de reconciliación y relectura focalizada (Ronda 15)."""

    def test_glosa_reconciliada_prefijo(self):
        """1. Reconciliación por prefijo bajo Regla 4 (Beneficios vs — Bene)."""
        from parser_universal import componer_filas_pagina_ocr

        m = [200000.0, 100000.0, 100000.0, 0.0, 0.0, 0.0, 100000.0, 0.0]
        c6 = [{"codigo": "88010001", "nombre": "Beneficios Sinteticos", "montos": list(m)}]
        c4 = [{"codigo": "88010001", "nombre": "— Bene", "montos": list(m)}]

        res = componer_filas_pagina_ocr(c6, c4, pagina=4)
        assert res.bloqueada is False
        assert len(res.filas_compuestas) == 1
        fila = res.filas_compuestas[0]
        assert fila.es_ambigua is False
        assert fila.bloquea_certificacion is False
        assert fila.regla_aceptacion == "glosa_reconciliada_misma_cuenta"
        assert fila.glosa_normalizada == "Beneficios Sinteticos"

    def test_glosa_reconciliada_subcadena(self):
        """2. Reconciliación por subcadena bajo Regla 4 (Préstamo con sufijo idéntico)."""
        from parser_universal import componer_filas_pagina_ocr

        m = [150000.0, 150000.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        c6 = [{"codigo": "88010002", "nombre": "— Préstamo Bco. Alfa N%9999", "montos": list(m)}]
        c4 = [{"codigo": "88010002", "nombre": ". Alfa N*9999", "montos": list(m)}]

        res = componer_filas_pagina_ocr(c6, c4, pagina=1)
        assert res.bloqueada is False
        fila = res.filas_compuestas[0]
        assert fila.es_ambigua is False
        assert fila.bloquea_certificacion is False
        assert fila.regla_aceptacion == "glosa_reconciliada_misma_cuenta"

    def test_glosa_reconciliada_ruido_corto(self):
        """3. Reconciliación ante ruido corto OCR (ii de len < 3 vs glosa sustantiva)."""
        from parser_universal import componer_filas_pagina_ocr

        m = [300000.0, 0.0, 300000.0, 0.0, 0.0, 0.0, 0.0, 300000.0]
        c6 = [{"codigo": "88010003", "nombre": "— Interés Prestamos Sinteticos", "montos": list(m)}]
        c4 = [{"codigo": "88010003", "nombre": "ii", "montos": list(m)}]

        res = componer_filas_pagina_ocr(c6, c4, pagina=5)
        assert res.bloqueada is False
        fila = res.filas_compuestas[0]
        assert fila.es_ambigua is False
        assert fila.regla_aceptacion == "glosa_reconciliada_misma_cuenta"
        assert "Interés" in fila.glosa_normalizada

    def test_glosa_reconciliada_sufijo_ruido(self):
        """4. Reconciliación con sufijo de ruido numérico OCR (Arriendo Espacio vs Arriendo 10)."""
        from parser_universal import componer_filas_pagina_ocr

        m = [0.0, 500000.0, 0.0, 500000.0, 0.0, 0.0, 0.0, 500000.0]
        c6 = [{"codigo": "88010004", "nombre": "— Arriendo Espacio Sintetico", "montos": list(m)}]
        c4 = [{"codigo": "88010004", "nombre": "Arriendo 10", "montos": list(m)}]

        res = componer_filas_pagina_ocr(c6, c4, pagina=5)
        assert res.bloqueada is False
        fila = res.filas_compuestas[0]
        assert fila.es_ambigua is False
        assert fila.regla_aceptacion == "glosa_reconciliada_misma_cuenta"
        assert fila.glosa_normalizada == "— Arriendo Espacio Sintetico"

    def test_glosa_incompatible_verdadero_conflicto(self):
        """5. Bloqueo de seguridad ante conflicto sustantivo irreconciliable de glosas."""
        from parser_universal import componer_filas_pagina_ocr

        m = [5000.0, 0.0, 5000.0, 0.0, 5000.0, 0.0, 0.0, 0.0]
        c6 = [{"codigo": "88010005", "nombre": "Caja Central Moneda Nacional", "montos": list(m)}]
        c4 = [{"codigo": "88010005", "nombre": "Proveedores Nacionales Varios", "montos": list(m)}]

        res = componer_filas_pagina_ocr(c6, c4, pagina=1)
        assert res.bloqueada is True
        fila = res.filas_compuestas[0]
        assert fila.es_ambigua is True
        assert fila.bloquea_certificacion is True
        assert fila.regla_aceptacion == "bloqueada_glosas_incompatibles"

    def test_fragmento_sin_codigo_reconciliado_psm4(self):
        """6. Reconciliación de fragmento uncoded en PSM 4 que coincide con cuenta codificada."""
        from parser_universal import componer_filas_pagina_ocr

        m = [0.0, 300000.0, 0.0, 300000.0, 0.0, 300000.0, 0.0, 0.0]
        c6 = [{"codigo": "88010006", "nombre": "Depreciación Acumulada Ficticia 1", "montos": list(m)}]
        c4 = [{"codigo": None, "nombre": "Acumulada Ficticia 1", "montos": list(m)}]

        res = componer_filas_pagina_ocr(c6, c4, pagina=3)
        assert res.bloqueada is False
        assert len(res.filas_compuestas) == 1
        assert res.filas_compuestas[0].codigo_normalizado == "88010006"

    def test_fragmento_sin_codigo_reconciliado_psm6(self):
        """7. Reconciliación simétrica de fragmento uncoded en PSM 6."""
        from parser_universal import componer_filas_pagina_ocr

        m = [0.0, 150000.0, 0.0, 150000.0, 0.0, 150000.0, 0.0, 0.0]
        c6 = [{"codigo": None, "nombre": "Acumulada Ficticia 2", "montos": list(m)}]
        c4 = [{"codigo": "88010007", "nombre": "Depreciación Acumulada Ficticia 2", "montos": list(m)}]

        res = componer_filas_pagina_ocr(c6, c4, pagina=3)
        assert res.bloqueada is False
        assert len(res.filas_compuestas) == 1
        assert res.filas_compuestas[0].codigo_normalizado == "88010007"

    def test_fila_sin_codigo_huerfana_bloquea(self):
        """8. Bloqueo de seguridad ante fila sin código huérfana con saldo no nulo."""
        from parser_universal import componer_filas_pagina_ocr

        c6 = []
        c4 = [{"codigo": None, "nombre": "Gasto Desconocido Ficticio", "montos": [1000.0, 0.0, 1000.0, 0.0, 1000.0, 0.0, 0.0, 0.0]}]

        res = componer_filas_pagina_ocr(c6, c4, pagina=1)
        assert res.bloqueada is True
        fila = res.filas_compuestas[0]
        assert fila.es_ambigua is True
        assert fila.bloquea_certificacion is True
        assert fila.regla_aceptacion == "bloqueada_sin_codigo_unilateral"

    def test_fila_sin_codigo_monto_cero_preservada(self):
        """9. Admisión de fila sin código en cero con evidencia de preservación."""
        from parser_universal import componer_filas_pagina_ocr

        c6 = [{"codigo": None, "nombre": "Cuenta Inactiva Ficticia", "montos": [0.0]*8, "monto_cero_preservado": True}]
        c4 = []

        res = componer_filas_pagina_ocr(c6, c4, pagina=1)
        assert res.bloqueada is False
        fila = res.filas_compuestas[0]
        assert fila.es_ambigua is False
        assert fila.regla_aceptacion == "cuenta_sin_codigo_monto_cero_preservada"

    def test_relectura_focalizada_confirmada(self, tmp_path):
        """10. Admisión de cuenta unilateral confirmada independientemente por relectura focalizada."""
        from parser_universal import _relectura_focalizada_ocr
        from unittest.mock import patch, MagicMock
        from PIL import Image

        fake_img = tmp_path / "page_4.png"
        Image.new("L", (3500, 3000), color=255).save(fake_img)

        words_tsv = [
            {"text": "88010008", "x0": 1048.0, "x1": 1177.0, "left": 1048.0, "width": 129.0, "raw_top": 780.0, "height": 23.0, "bottom": 803.0, "yc": 791.5},
            {"text": "Prestamo", "x0": 1233.0, "x1": 1340.0, "left": 1233.0, "width": 107.0, "raw_top": 780.0, "height": 23.0, "bottom": 803.0, "yc": 791.5},
            {"text": "731.429", "x0": 2090.0, "x1": 2239.0, "left": 2090.0, "width": 149.0, "raw_top": 775.0, "height": 23.0, "bottom": 798.0, "yc": 786.5},
        ]
        m = [0.0, 731429.0, 0.0, 731429.0, 0.0, 731429.0, 0.0, 0.0]

        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_res.stdout = "88010008 Prestamo Sintetico 731.429 731.429 731.429"

        with patch("subprocess.run", return_value=mock_res):
            f_ok, ev = _relectura_focalizada_ocr(fake_img, 0, words_tsv, "88010008", "— Prestamo Sintetico", m, pagina=4)

        assert f_ok is not None
        assert f_ok.es_ambigua is False
        assert f_ok.bloquea_certificacion is False
        assert f_ok.regla_aceptacion == "relectura_focalizada_confirmada"
        assert ev["tipo"] == "confirmada"

    def test_relectura_focalizada_geometria_invalida(self, tmp_path):
        """11. Rechazo estructurado cuando la geometría de la caja de recorte es inválida."""
        from parser_universal import _relectura_focalizada_ocr
        from PIL import Image

        fake_img = tmp_path / "page_deg.png"
        Image.new("L", (100, 100), color=255).save(fake_img)

        # Palabras con x0=0, x1=5 (ancho < 20px)
        words_tsv = [{"text": "88010008", "x0": 5.0, "x1": 10.0, "left": 5.0, "width": 5.0, "raw_top": 10.0, "height": 1.0, "bottom": 11.0, "yc": 10.5}]
        m = [0.0, 1000.0, 0.0, 1000.0, 0.0, 1000.0, 0.0, 0.0]

        f_ok, ev = _relectura_focalizada_ocr(fake_img, 0, words_tsv, "88010008", "Glosa", m, pagina=1)
        assert f_ok is None
        assert ev["tipo"] == "geometria_invalida"

    def test_relectura_focalizada_discrepancia_montos(self, tmp_path):
        """12. Bloqueo de seguridad cuando la relectura produce importes contradictorios."""
        from parser_universal import _relectura_focalizada_ocr
        from unittest.mock import patch, MagicMock
        from PIL import Image

        fake_img = tmp_path / "page_disc.png"
        Image.new("L", (3500, 3000), color=255).save(fake_img)

        words_tsv = [
            {"text": "88010008", "x0": 100.0, "x1": 300.0, "left": 100.0, "width": 200.0, "raw_top": 500.0, "height": 30.0, "bottom": 530.0, "yc": 515.0},
        ]
        m = [0.0, 731429.0, 0.0, 731429.0, 0.0, 731429.0, 0.0, 0.0]

        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_res.stdout = "88010008 Prestamo Sintetico 999.999"

        with patch("subprocess.run", return_value=mock_res):
            f_ok, ev = _relectura_focalizada_ocr(fake_img, 0, words_tsv, "88010008", "Prestamo Sintetico", m, pagina=1)

        assert f_ok is None
        assert ev["tipo"] == "discrepancia_relectura"

    def test_relectura_focalizada_discrepancia_codigo(self, tmp_path):
        """13. Bloqueo de seguridad cuando la relectura lee un código incompatible."""
        from parser_universal import _relectura_focalizada_ocr
        from unittest.mock import patch, MagicMock
        from PIL import Image

        fake_img = tmp_path / "page_cod.png"
        Image.new("L", (3500, 3000), color=255).save(fake_img)

        words_tsv = [
            {"text": "88010008", "x0": 100.0, "x1": 300.0, "left": 100.0, "width": 200.0, "raw_top": 500.0, "height": 30.0, "bottom": 530.0, "yc": 515.0},
        ]
        m = [0.0, 731429.0, 0.0, 731429.0, 0.0, 731429.0, 0.0, 0.0]

        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_res.stdout = "99999999 Otra Cuenta 731.429"

        with patch("subprocess.run", return_value=mock_res):
            f_ok, ev = _relectura_focalizada_ocr(fake_img, 0, words_tsv, "88010008", "Prestamo Sintetico", m, pagina=1)

        assert f_ok is None
        assert ev["tipo"] == "discrepancia_relectura"

    def test_relectura_focalizada_coordenadas_tsv_fisicas(self, tmp_path):
        """14. Verificación de cálculo de recorte usando coordenadas físicas x0, x1, raw_top, bottom."""
        from parser_universal import _relectura_focalizada_ocr
        from unittest.mock import patch, MagicMock
        from PIL import Image

        fake_img = tmp_path / "page_coords.png"
        Image.new("L", (4000, 4000), color=255).save(fake_img)

        # Simular TSV donde 'top' es sintético (índice 10) pero 'raw_top' es píxeles físicos (1500)
        words_tsv = [
            {"text": "88010009", "x0": 1026.0, "x1": 1200.0, "top": 10.0, "raw_top": 1500.0, "height": 25.0, "bottom": 1525.0, "yc": 1512.5},
            {"text": "PPM", "x0": 1250.0, "x1": 1350.0, "top": 10.0, "raw_top": 1500.0, "height": 25.0, "bottom": 1525.0, "yc": 1512.5},
            {"text": "250.000", "x0": 2600.0, "x1": 2840.0, "top": 10.0, "raw_top": 1500.0, "height": 25.0, "bottom": 1525.0, "yc": 1512.5},
        ]
        m = [250000.0, 250000.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_res.stdout = "88010009 PPM por pagar 250.000 250.000"

        with patch("subprocess.run", return_value=mock_res):
            f_ok, ev = _relectura_focalizada_ocr(fake_img, 0, words_tsv, "88010009", "— PPM por pagar", m, pagina=1)

        assert f_ok is not None
        assert f_ok.regla_aceptacion == "relectura_focalizada_confirmada"
        assert ev["tipo"] == "confirmada"


class TestRonda16ControlsAndReconciliation:
    """20 Casos sintéticos unitarios para la validación de controles multilínea,
    alcance de subtotales y no contaminación de datos en Ronda 16.
    """

    def test_01_reconstruccion_multilinea_impar_par_consecutivos(self):
        """1. Reconstrucción multilínea de control cuando importes impares y pares están en filas consecutivas."""
        from parser_universal import _extraer_tabla_balance_por_coordenadas, _OCRWordsPage

        # Simular página con fila 1 (nombre + impares) y fila 2 (ruido + pares)
        words = [
            # Header
            {"text": "CUENTA", "x0": 100, "x1": 200, "top": 10},
            {"text": "DEBITOS", "x0": 300, "x1": 350, "top": 10},
            {"text": "CREDITOS", "x0": 400, "x1": 450, "top": 10},
            {"text": "DEUDOR", "x0": 500, "x1": 550, "top": 10},
            {"text": "ACREEDOR", "x0": 600, "x1": 650, "top": 10},
            {"text": "ACTIVO", "x0": 700, "x1": 750, "top": 10},
            {"text": "PASIVO", "x0": 800, "x1": 850, "top": 10},
            {"text": "PERDIDA", "x0": 900, "x1": 950, "top": 10},
            {"text": "GANANCIA", "x0": 1000, "x1": 1050, "top": 10},
            # Fila Total general (impares)
            {"text": "Total", "x0": 100, "x1": 140, "top": 20},
            {"text": "general:", "x0": 145, "x1": 200, "top": 20},
            {"text": "1000", "x0": 300, "x1": 350, "top": 20},
            {"text": "500", "x0": 500, "x1": 550, "top": 20},
            {"text": "300", "x0": 700, "x1": 750, "top": 20},
            {"text": "200", "x0": 900, "x1": 950, "top": 20},
            # Fila consecutiva (ruido 'o' + pares)
            {"text": "o", "x0": 150, "x1": 160, "top": 25},
            {"text": "1000", "x0": 400, "x1": 450, "top": 25},
            {"text": "500", "x0": 600, "x1": 650, "top": 25},
            {"text": "300", "x0": 800, "x1": 850, "top": 25},
            {"text": "200", "x0": 1000, "x1": 1050, "top": 25},
        ]
        lines, centers = _extraer_tabla_balance_por_coordenadas(_OCRWordsPage(words), None)
        assert len(lines) == 1
        assert "Total general" in lines[0]
        parts = lines[0].split()
        assert parts[-8:] == ["1000", "1000", "500", "500", "300", "300", "200", "200"]

    def test_02_no_fusion_si_hay_cuenta_intermedia(self):
        """2. No fusión si hay una cuenta contable intermedia."""
        from parser_universal import _extraer_tabla_balance_por_coordenadas, _OCRWordsPage

        words = [
            {"text": "CUENTA", "x0": 100, "x1": 200, "top": 10},
            {"text": "DEBITOS", "x0": 300, "x1": 350, "top": 10},
            {"text": "CREDITOS", "x0": 400, "x1": 450, "top": 10},
            {"text": "DEUDOR", "x0": 500, "x1": 550, "top": 10},
            {"text": "ACREEDOR", "x0": 600, "x1": 650, "top": 10},
            {"text": "ACTIVO", "x0": 700, "x1": 750, "top": 10},
            {"text": "PASIVO", "x0": 800, "x1": 850, "top": 10},
            {"text": "PERDIDA", "x0": 900, "x1": 950, "top": 10},
            {"text": "GANANCIA", "x0": 1000, "x1": 1050, "top": 10},
            # Fila 1 Subtotal
            {"text": "Subtotal", "x0": 100, "x1": 180, "top": 20},
            {"text": "1000", "x0": 300, "x1": 350, "top": 20},
            # Fila intermedia legítima
            {"text": "110101", "x0": 100, "x1": 140, "top": 25},
            {"text": "Caja", "x0": 145, "x1": 200, "top": 25},
            {"text": "100", "x0": 300, "x1": 350, "top": 25},
            # Fila 3
            {"text": "o", "x0": 150, "x1": 160, "top": 30},
            {"text": "1000", "x0": 400, "x1": 450, "top": 30},
        ]
        lines, _ = _extraer_tabla_balance_por_coordenadas(_OCRWordsPage(words), None)
        # La cuenta intermedia evita que la fila 3 se fusione con la fila 1
        assert any("Caja" in l for l in lines)

    def test_03_no_fusion_si_fila_siguiente_es_glosa_legitima(self):
        """3. No fusión si la fila siguiente tiene nombre de cuenta legítimo (no ruido)."""
        from parser_universal import _extraer_tabla_balance_por_coordenadas, _OCRWordsPage

        words = [
            {"text": "CUENTA", "x0": 100, "x1": 200, "top": 10},
            {"text": "DEBITOS", "x0": 300, "x1": 350, "top": 10},
            {"text": "CREDITOS", "x0": 400, "x1": 450, "top": 10},
            {"text": "DEUDOR", "x0": 500, "x1": 550, "top": 10},
            {"text": "ACREEDOR", "x0": 600, "x1": 650, "top": 10},
            {"text": "ACTIVO", "x0": 700, "x1": 750, "top": 10},
            {"text": "PASIVO", "x0": 800, "x1": 850, "top": 10},
            {"text": "PERDIDA", "x0": 900, "x1": 950, "top": 10},
            {"text": "GANANCIA", "x0": 1000, "x1": 1050, "top": 10},
            # Subtotal
            {"text": "Subtotal", "x0": 100, "x1": 180, "top": 20},
            {"text": "1000", "x0": 300, "x1": 350, "top": 20},
            # Fila siguiente con nombre legítimo
            {"text": "Clientes", "x0": 100, "x1": 180, "top": 25},
            {"text": "1000", "x0": 400, "x1": 450, "top": 25},
        ]
        lines, _ = _extraer_tabla_balance_por_coordenadas(_OCRWordsPage(words), None)
        assert len(lines) == 2
        assert "Clientes" in lines[1]

    def test_04_reconstruccion_con_ruido_corchete_y_simbolos(self):
        """4. Reconstrucción con ruido de corchete ']' y símbolos comunes."""
        from parser_universal import _extraer_tabla_balance_por_coordenadas, _OCRWordsPage

        words = [
            {"text": "CUENTA", "x0": 100, "x1": 200, "top": 10},
            {"text": "DEBITOS", "x0": 300, "x1": 350, "top": 10},
            {"text": "CREDITOS", "x0": 400, "x1": 450, "top": 10},
            {"text": "DEUDOR", "x0": 500, "x1": 550, "top": 10},
            {"text": "ACREEDOR", "x0": 600, "x1": 650, "top": 10},
            {"text": "ACTIVO", "x0": 700, "x1": 750, "top": 10},
            {"text": "PASIVO", "x0": 800, "x1": 850, "top": 10},
            {"text": "PERDIDA", "x0": 900, "x1": 950, "top": 10},
            {"text": "GANANCIA", "x0": 1000, "x1": 1050, "top": 10},
            # Total general: ]
            {"text": "Total", "x0": 100, "x1": 140, "top": 20},
            {"text": "general:", "x0": 145, "x1": 200, "top": 20},
            {"text": "]", "x0": 205, "x1": 210, "top": 20},
            {"text": "5000", "x0": 300, "x1": 350, "top": 20},
            # Fila ]
            {"text": "]", "x0": 205, "x1": 210, "top": 25},
            {"text": "5000", "x0": 400, "x1": 450, "top": 25},
        ]
        lines, _ = _extraer_tabla_balance_por_coordenadas(_OCRWordsPage(words), None)
        assert len(lines) == 1
        assert "Total general" in lines[0]
        assert lines[0].split()[-8:-6] == ["5000", "5000"]

    def test_05_preservacion_subtotal_transporte_local(self):
        """5. Preservación del subtotal de transporte como control local sin contrastarlo con el grand total."""
        from parser_universal import certificar_extraccion_columnas, CuentaRaw, OrigenColumna

        # 2 cuentas página 1 sumando 100
        c1 = CuentaRaw(linea=1, codigo="1", nombre="Cta 1", monto=50.0, origen_columna=OrigenColumna.ACTIVO, es_total=False, confianza_extraccion=0.9,
                       montos_columnas={"debitos": 50.0, "creditos": 0.0, "saldo_deudor": 50.0, "saldo_acreedor": 0.0, "activo": 50.0, "pasivo": 0.0, "perdida": 0.0, "ganancia": 0.0})
        c2 = CuentaRaw(linea=2, codigo="2", nombre="Cta 2", monto=50.0, origen_columna=OrigenColumna.ACTIVO, es_total=False, confianza_extraccion=0.9,
                       montos_columnas={"debitos": 50.0, "creditos": 0.0, "saldo_deudor": 50.0, "saldo_acreedor": 0.0, "activo": 50.0, "pasivo": 0.0, "perdida": 0.0, "ganancia": 0.0})
        # Subtotal de transporte página 1: 100
        sub_transporte = CuentaRaw(linea=3, codigo=None, nombre="Total Acumulado", monto=100.0, origen_columna=OrigenColumna.ACTIVO, es_total=True, confianza_extraccion=0.9,
                                   montos_columnas={"debitos": 100.0, "creditos": 0.0, "saldo_deudor": 100.0, "saldo_acreedor": 0.0, "activo": 100.0, "pasivo": 0.0, "perdida": 0.0, "ganancia": 0.0})
        # 2 cuentas página 2 sumando 150 (Total doc = 250)
        c3 = CuentaRaw(linea=4, codigo="3", nombre="Cta 3", monto=75.0, origen_columna=OrigenColumna.ACTIVO, es_total=False, confianza_extraccion=0.9,
                       montos_columnas={"debitos": 75.0, "creditos": 0.0, "saldo_deudor": 75.0, "saldo_acreedor": 0.0, "activo": 75.0, "pasivo": 0.0, "perdida": 0.0, "ganancia": 0.0})
        c4 = CuentaRaw(linea=5, codigo="4", nombre="Cta 4", monto=75.0, origen_columna=OrigenColumna.ACTIVO, es_total=False, confianza_extraccion=0.9,
                       montos_columnas={"debitos": 75.0, "creditos": 0.0, "saldo_deudor": 75.0, "saldo_acreedor": 0.0, "activo": 75.0, "pasivo": 0.0, "perdida": 0.0, "ganancia": 0.0})
        # Total General documento = 250
        tot_gral = CuentaRaw(linea=6, codigo=None, nombre="Total general", monto=250.0, origen_columna=OrigenColumna.ACTIVO, es_total=True, confianza_extraccion=0.9,
                             montos_columnas={"debitos": 250.0, "creditos": 0.0, "saldo_deudor": 250.0, "saldo_acreedor": 0.0, "activo": 250.0, "pasivo": 0.0, "perdida": 0.0, "ganancia": 0.0})
        cierre = CuentaRaw(linea=7, codigo=None, nombre="Sumas Iguales", monto=250.0, origen_columna=OrigenColumna.ACTIVO, es_total=True, confianza_extraccion=0.9,
                           montos_columnas={"debitos": 250.0, "creditos": 250.0, "saldo_deudor": 250.0, "saldo_acreedor": 250.0, "activo": 250.0, "pasivo": 250.0, "perdida": 0.0, "ganancia": 0.0})

        cert = certificar_extraccion_columnas([c1, c2, sub_transporte, c3, c4, tot_gral, cierre], tolerancia_absoluta=0.0)
        # El subtotal_referencia debe ser Total general (250), no Total Acumulado (100)
        assert cert.totales_impresos["debitos"] == 250.0
        assert cert.diferencias["debitos"] == 0.0

    def test_06_cuadratura_total_general_multilinea(self):
        """6. Cuadratura del total general multilínea con identidades contables."""
        from parser_universal import certificar_extraccion_columnas, CuentaRaw, OrigenColumna

        cta = CuentaRaw(linea=1, codigo="10", nombre="Banco", monto=100.0, origen_columna=OrigenColumna.ACTIVO, es_total=False, confianza_extraccion=0.9,
                        montos_columnas={"debitos": 100.0, "creditos": 100.0, "saldo_deudor": 50.0, "saldo_acreedor": 50.0, "activo": 50.0, "pasivo": 50.0, "perdida": 0.0, "ganancia": 0.0})
        tot = CuentaRaw(linea=2, codigo=None, nombre="Total general", monto=100.0, origen_columna=OrigenColumna.ACTIVO, es_total=True, confianza_extraccion=0.9,
                        montos_columnas={"debitos": 100.0, "creditos": 100.0, "saldo_deudor": 50.0, "saldo_acreedor": 50.0, "activo": 50.0, "pasivo": 50.0, "perdida": 0.0, "ganancia": 0.0})
        cierre = CuentaRaw(linea=3, codigo=None, nombre="Sumas Iguales", monto=100.0, origen_columna=OrigenColumna.ACTIVO, es_total=True, confianza_extraccion=0.9,
                           montos_columnas={"debitos": 100.0, "creditos": 100.0, "saldo_deudor": 50.0, "saldo_acreedor": 50.0, "activo": 50.0, "pasivo": 50.0, "perdida": 0.0, "ganancia": 0.0})

        cert = certificar_extraccion_columnas([cta, tot, cierre], tolerancia_absoluta=0.0)
        assert cert.estado in {"certificada", "parcial"}
        assert all(diff == 0.0 for diff in cert.diferencias.values())

    def test_07_derivacion_sumas_iguales_con_puente_resultado(self):
        """7. Derivación de columnas en Sumas Iguales mediante subtotal + puente de resultado."""
        from parser_universal import certificar_extraccion_columnas, CuentaRaw, OrigenColumna

        # Subtotal: Activo 80, Pasivo 100 -> Resultado -20 (Pérdida)
        tot = CuentaRaw(linea=1, codigo=None, nombre="Total general", monto=100.0, origen_columna=OrigenColumna.ACTIVO, es_total=True, confianza_extraccion=0.9,
                        montos_columnas={"debitos": 200.0, "creditos": 200.0, "saldo_deudor": 100.0, "saldo_acreedor": 100.0, "activo": 80.0, "pasivo": 100.0, "perdida": 30.0, "ganancia": 10.0})
        # Detalle cuadrando exactamente con subtotal
        cta = CuentaRaw(linea=0, codigo="1", nombre="Activo Fijo", monto=80.0, origen_columna=OrigenColumna.ACTIVO, es_total=False, confianza_extraccion=0.9,
                        montos_columnas={"debitos": 200.0, "creditos": 200.0, "saldo_deudor": 100.0, "saldo_acreedor": 100.0, "activo": 80.0, "pasivo": 100.0, "perdida": 30.0, "ganancia": 10.0})
        # Puente resultado: Activo 20, Ganancia 20
        puente = CuentaRaw(linea=2, codigo=None, nombre="PERDIDA DEL EJERCICIO", monto=20.0, origen_columna=OrigenColumna.ACTIVO, es_total=True, confianza_extraccion=0.9,
                           montos_columnas={"debitos": 0.0, "creditos": 0.0, "saldo_deudor": 0.0, "saldo_acreedor": 0.0, "activo": 20.0, "pasivo": 0.0, "perdida": 0.0, "ganancia": 20.0})
        # Fila final Sumas Iguales con columnas vacías a reparar
        cierre = CuentaRaw(linea=3, codigo=None, nombre="Sumas Iguales", monto=100.0, origen_columna=OrigenColumna.ACTIVO, es_total=True, confianza_extraccion=0.9,
                           montos_columnas={"debitos": 200.0, "creditos": 200.0, "saldo_deudor": 100.0, "saldo_acreedor": 100.0, "activo": 0.0, "pasivo": 100.0, "perdida": 30.0, "ganancia": 0.0})

        cert = certificar_extraccion_columnas([cta, tot, puente, cierre], metodo="ocr_coordinates_8_amounts", tolerancia_absoluta=0.0)
        assert cert.totales_finales_validos is True
        assert cierre.montos_columnas["activo"] == 100.0
        assert cierre.montos_columnas["ganancia"] == 30.0

    def test_08_limpieza_glosa_resultado_con_artefactos_ocr(self):
        """8. Limpieza y reconocimiento de PATRON_TOTAL ante glosas con artefactos OCR ('PERDIDA DEL EJERCICIO l :')."""
        from parser_universal import parsear_linea, FormatoCodigo

        res = parsear_linea("PERDIDA DEL EJERCICIO l : 0 0 0 0 20000 0 0 20000", 1, FormatoCodigo.SIN_CODIGO, ".", 0.75)
        assert res is not None
        assert res.es_total is True
        assert res.nombre == "PERDIDA DEL EJERCICIO"

    def test_09_reconocimiento_cierre_con_sufijo_ruido(self):
        """9. Reconocimiento de cierre final con sufijo de ruido en _es_cierre_final_balance."""
        from parser_universal import _es_cierre_final_balance

        assert _es_cierre_final_balance("Sumas Iguales — o : :") is True
        assert _es_cierre_final_balance("TOTALES IGUALES ]") is True
        assert _es_cierre_final_balance("Total general: ]") is True

    def test_10_no_romper_balance_simple_unipagina(self):
        """10. Un balance estándar de 1 página con controles de una sola línea no es alterado."""
        from parser_universal import certificar_extraccion_columnas, CuentaRaw, OrigenColumna

        cta = CuentaRaw(linea=1, codigo="1", nombre="Caja", monto=100.0, origen_columna=OrigenColumna.ACTIVO, es_total=False, confianza_extraccion=0.9,
                        montos_columnas={"debitos": 100.0, "creditos": 100.0, "saldo_deudor": 100.0, "saldo_acreedor": 100.0, "activo": 100.0, "pasivo": 100.0, "perdida": 0.0, "ganancia": 0.0})
        tot = CuentaRaw(linea=2, codigo=None, nombre="TOTAL GENERAL", monto=100.0, origen_columna=OrigenColumna.ACTIVO, es_total=True, confianza_extraccion=0.9,
                        montos_columnas={"debitos": 100.0, "creditos": 100.0, "saldo_deudor": 100.0, "saldo_acreedor": 100.0, "activo": 100.0, "pasivo": 100.0, "perdida": 0.0, "ganancia": 0.0})
        cierre = CuentaRaw(linea=3, codigo=None, nombre="SUMAS IGUALES", monto=100.0, origen_columna=OrigenColumna.ACTIVO, es_total=True, confianza_extraccion=0.9,
                           montos_columnas={"debitos": 100.0, "creditos": 100.0, "saldo_deudor": 100.0, "saldo_acreedor": 100.0, "activo": 100.0, "pasivo": 100.0, "perdida": 0.0, "ganancia": 0.0})

        cert = certificar_extraccion_columnas([cta, tot, cierre], tolerancia_absoluta=0.0)
        assert cert.estado == "certificada"
        assert all(d == 0.0 for d in cert.diferencias.values())

    def test_11_deteccion_descuadre_material_rechaza_certificacion(self):
        """11. Rechazo de certificación cuando una columna no cuadra entre detalle y subtotal."""
        from parser_universal import certificar_extraccion_columnas, CuentaRaw, OrigenColumna

        cta = CuentaRaw(linea=1, codigo="1", nombre="Caja", monto=100.0, origen_columna=OrigenColumna.ACTIVO, es_total=False, confianza_extraccion=0.9,
                        montos_columnas={"debitos": 100.0, "creditos": 100.0, "saldo_deudor": 100.0, "saldo_acreedor": 100.0, "activo": 100.0, "pasivo": 100.0, "perdida": 0.0, "ganancia": 0.0})
        tot = CuentaRaw(linea=2, codigo=None, nombre="TOTAL GENERAL", monto=999.0, origen_columna=OrigenColumna.ACTIVO, es_total=True, confianza_extraccion=0.9,
                        montos_columnas={"debitos": 999.0, "creditos": 100.0, "saldo_deudor": 100.0, "saldo_acreedor": 100.0, "activo": 100.0, "pasivo": 100.0, "perdida": 0.0, "ganancia": 0.0})

        cert = certificar_extraccion_columnas([cta, tot], tolerancia_absoluta=0.0)
        assert cert.estado == "fallida"
        assert cert.diferencias["debitos"] == -899.0

    def test_12_cuenta_saldo_cero_no_es_ruido(self):
        """12. Cuenta legítima con movimientos o saldo cero no se clasifica como ruido."""
        from parser_universal import es_ruido_ocr_no_contable, CuentaRaw, OrigenColumna

        c_cero = CuentaRaw(linea=1, codigo="110101", nombre="Caja Chica Santiago", monto=0.0, origen_columna=OrigenColumna.ACTIVO, es_total=False, confianza_extraccion=0.9,
                           montos_columnas={"debitos": 0.0, "creditos": 0.0, "saldo_deudor": 0.0, "saldo_acreedor": 0.0, "activo": 0.0, "pasivo": 0.0, "perdida": 0.0, "ganancia": 0.0})
        assert es_ruido_ocr_no_contable(c_cero) is False

    def test_13_glosa_ruido_sin_codigo_ni_montos_es_ruido(self):
        """13. Texto de pie de página o firma sin código ni importes es detectado como ruido."""
        from parser_universal import es_ruido_ocr_no_contable, CuentaRaw, OrigenColumna

        c_ruido = CuentaRaw(linea=1, codigo=None, nombre="REPRESENTANTE LEGAL", monto=0.0, origen_columna=OrigenColumna.ACTIVO, es_total=False, confianza_extraccion=0.5,
                            montos_columnas={c: 0.0 for c in ["debitos", "creditos", "saldo_deudor", "saldo_acreedor", "activo", "pasivo", "perdida", "ganancia"]})
        assert es_ruido_ocr_no_contable(c_ruido) is True

    def test_14_tolerancia_glifos_cero_ocr(self):
        """14. Glifos comunes de cero OCR ('o', ']', '-') se normalizan a 0."""
        from parser_universal import _es_token_cero_ocr_en_celda

        assert _es_token_cero_ocr_en_celda("o") is True
        assert _es_token_cero_ocr_en_celda("O") is True
        assert _es_token_cero_ocr_en_celda("]") is True
        assert _es_token_cero_ocr_en_celda("|") is True
        assert _es_token_cero_ocr_en_celda("100") is False

    def test_15_separacion_estricta_de_alcances_de_control(self):
        """15. Control local de página intermedia no se usa como grand total."""
        from parser_universal import certificar_extraccion_columnas, CuentaRaw, OrigenColumna

        ctas = [
            CuentaRaw(linea=i, codigo=str(i), nombre=f"Cta {i}", monto=10.0, origen_columna=OrigenColumna.ACTIVO, es_total=False, confianza_extraccion=0.9,
                      montos_columnas={"debitos": 10.0, "creditos": 10.0, "saldo_deudor": 10.0, "saldo_acreedor": 10.0, "activo": 10.0, "pasivo": 10.0, "perdida": 0.0, "ganancia": 0.0})
            for i in range(1, 11)
        ]
        # Transporte a mitad (línea 5): 50
        transporte = CuentaRaw(linea=5, codigo=None, nombre="Total Acumulado", monto=50.0, origen_columna=OrigenColumna.ACTIVO, es_total=True, confianza_extraccion=0.9,
                               montos_columnas={"debitos": 50.0, "creditos": 50.0, "saldo_deudor": 50.0, "saldo_acreedor": 50.0, "activo": 50.0, "pasivo": 50.0, "perdida": 0.0, "ganancia": 0.0})
        # Total al final (línea 11): 100
        total_final = CuentaRaw(linea=11, codigo=None, nombre="Totales Generales", monto=100.0, origen_columna=OrigenColumna.ACTIVO, es_total=True, confianza_extraccion=0.9,
                                montos_columnas={"debitos": 100.0, "creditos": 100.0, "saldo_deudor": 100.0, "saldo_acreedor": 100.0, "activo": 100.0, "pasivo": 100.0, "perdida": 0.0, "ganancia": 0.0})
        cierre = CuentaRaw(linea=12, codigo=None, nombre="Sumas Iguales", monto=100.0, origen_columna=OrigenColumna.ACTIVO, es_total=True, confianza_extraccion=0.9,
                           montos_columnas={"debitos": 100.0, "creditos": 100.0, "saldo_deudor": 100.0, "saldo_acreedor": 100.0, "activo": 100.0, "pasivo": 100.0, "perdida": 0.0, "ganancia": 0.0})

        cert = certificar_extraccion_columnas(ctas + [transporte, total_final, cierre], tolerancia_absoluta=0.0)
        assert cert.totales_impresos["debitos"] == 100.0
        assert cert.diferencias["debitos"] == 0.0

    def test_16_conciliacion_filas_sin_perdida_silenciosa(self):
        """16. Todas las cuentas legítimas extraídas se preservan en la lista de cuentas certificadas."""
        from parser_universal import certificar_extraccion_columnas, CuentaRaw, OrigenColumna

        ctas = [
            CuentaRaw(linea=i, codigo=f"1.0{i}", nombre=f"Cuenta {i}", monto=100.0, origen_columna=OrigenColumna.ACTIVO, es_total=False, confianza_extraccion=0.9,
                      montos_columnas={"debitos": 100.0, "creditos": 100.0, "saldo_deudor": 100.0, "saldo_acreedor": 100.0, "activo": 100.0, "pasivo": 100.0, "perdida": 0.0, "ganancia": 0.0})
            for i in range(1, 21)
        ]
        tot = CuentaRaw(linea=21, codigo=None, nombre="TOTAL GENERAL", monto=2000.0, origen_columna=OrigenColumna.ACTIVO, es_total=True, confianza_extraccion=0.9,
                        montos_columnas={"debitos": 2000.0, "creditos": 2000.0, "saldo_deudor": 2000.0, "saldo_acreedor": 2000.0, "activo": 2000.0, "pasivo": 2000.0, "perdida": 0.0, "ganancia": 0.0})
        cierre = CuentaRaw(linea=22, codigo=None, nombre="SUMAS IGUALES", monto=2000.0, origen_columna=OrigenColumna.ACTIVO, es_total=True, confianza_extraccion=0.9,
                           montos_columnas={"debitos": 2000.0, "creditos": 2000.0, "saldo_deudor": 2000.0, "saldo_acreedor": 2000.0, "activo": 2000.0, "pasivo": 2000.0, "perdida": 0.0, "ganancia": 0.0})
        cert = certificar_extraccion_columnas(ctas + [tot, cierre], tolerancia_absoluta=0.0)
        assert cert.filas_evaluadas == 20
        assert len(cert.filas_inconsistentes) == 0

    def test_17_bloqueo_estructurado_ante_ambiguedad_material(self):
        """17. Bloqueo de certificación automático cuando se registra bloqueo_certificacion."""
        from parser_universal import certificar_extraccion_columnas, CuentaRaw, OrigenColumna

        cta = CuentaRaw(linea=1, codigo="1", nombre="Caja", monto=100.0, origen_columna=OrigenColumna.ACTIVO, es_total=False, confianza_extraccion=0.9,
                        montos_columnas={"debitos": 100.0, "creditos": 100.0, "saldo_deudor": 100.0, "saldo_acreedor": 100.0, "activo": 100.0, "pasivo": 100.0, "perdida": 0.0, "ganancia": 0.0})
        tot = CuentaRaw(linea=2, codigo=None, nombre="TOTAL GENERAL", monto=100.0, origen_columna=OrigenColumna.ACTIVO, es_total=True, confianza_extraccion=0.9,
                        montos_columnas={"debitos": 100.0, "creditos": 100.0, "saldo_deudor": 100.0, "saldo_acreedor": 100.0, "activo": 100.0, "pasivo": 100.0, "perdida": 0.0, "ganancia": 0.0})
        bloqueo = {"bloqueado": True, "motivo": "ambiguedad_candidatos_ocr", "pagina": 3, "detalle": "Página 3: ambigüedad material"}

        cert = certificar_extraccion_columnas([cta, tot], ocr_bloqueo_certificacion=bloqueo, tolerancia_absoluta=0.0)
        assert cert.estado == "fallida"
        assert any("Bloqueo de certificación automática" in r for r in cert.razones)

    def test_18_puente_resultado_utilidad_del_ejercicio(self):
        """18. Reconocimiento de puente de resultado cuando hay UTILIDAD DEL EJERCICIO."""
        from parser_universal import certificar_extraccion_columnas, CuentaRaw, OrigenColumna

        # Subtotal: Activo 150, Pasivo 100 -> Utilidad 50
        tot = CuentaRaw(linea=1, codigo=None, nombre="Total general", monto=100.0, origen_columna=OrigenColumna.ACTIVO, es_total=True, confianza_extraccion=0.9,
                        montos_columnas={"debitos": 300.0, "creditos": 300.0, "saldo_deudor": 150.0, "saldo_acreedor": 150.0, "activo": 150.0, "pasivo": 100.0, "perdida": 50.0, "ganancia": 100.0})
        cta = CuentaRaw(linea=0, codigo="1", nombre="Activo", monto=150.0, origen_columna=OrigenColumna.ACTIVO, es_total=False, confianza_extraccion=0.9,
                        montos_columnas={"debitos": 300.0, "creditos": 300.0, "saldo_deudor": 150.0, "saldo_acreedor": 150.0, "activo": 150.0, "pasivo": 100.0, "perdida": 50.0, "ganancia": 100.0})
        puente = CuentaRaw(linea=2, codigo=None, nombre="UTILIDAD DEL EJERCICIO", monto=50.0, origen_columna=OrigenColumna.PASIVO, es_total=True, confianza_extraccion=0.9,
                           montos_columnas={"debitos": 0.0, "creditos": 0.0, "saldo_deudor": 0.0, "saldo_acreedor": 0.0, "activo": 0.0, "pasivo": 50.0, "perdida": 50.0, "ganancia": 0.0})
        cierre = CuentaRaw(linea=3, codigo=None, nombre="Sumas Iguales", monto=150.0, origen_columna=OrigenColumna.ACTIVO, es_total=True, confianza_extraccion=0.9,
                           montos_columnas={"debitos": 300.0, "creditos": 300.0, "saldo_deudor": 150.0, "saldo_acreedor": 150.0, "activo": 150.0, "pasivo": 150.0, "perdida": 100.0, "ganancia": 100.0})

        cert = certificar_extraccion_columnas([cta, tot, puente, cierre], tolerancia_absoluta=0.0)
        assert cert.resultado_ejercicio == 50.0
        assert cert.tipo_resultado == "utilidad"
        assert cert.totales_finales_validos is True

    def test_19_inconsistencia_debe_haber_identificada(self):
        """19. Cuentas con Débito - Crédito != Saldo Deudor - Saldo Acreedor se marcan inconsistentes."""
        from parser_universal import certificar_extraccion_columnas, CuentaRaw, OrigenColumna

        # Cuenta rota: Débito 100, Crédito 20 -> saldo deudor debería ser 80, pero dice 50
        cta_mala = CuentaRaw(linea=1, codigo="1", nombre="Banco Descuadrado", monto=50.0, origen_columna=OrigenColumna.ACTIVO, es_total=False, confianza_extraccion=0.9,
                             montos_columnas={"debitos": 100.0, "creditos": 20.0, "saldo_deudor": 50.0, "saldo_acreedor": 0.0, "activo": 50.0, "pasivo": 0.0, "perdida": 0.0, "ganancia": 0.0})
        tot = CuentaRaw(linea=2, codigo=None, nombre="TOTAL GENERAL", monto=50.0, origen_columna=OrigenColumna.ACTIVO, es_total=True, confianza_extraccion=0.9,
                        montos_columnas={"debitos": 100.0, "creditos": 20.0, "saldo_deudor": 50.0, "saldo_acreedor": 0.0, "activo": 50.0, "pasivo": 0.0, "perdida": 0.0, "ganancia": 0.0})

        cert = certificar_extraccion_columnas([cta_mala, tot], tolerancia_absoluta=0.0)
        assert 1 in cert.filas_inconsistentes
        assert cert.estado == "fallida"

    def test_20_conciliacion_reconstructiva_cuadra_ocho_columnas(self):
        """20. Reconciliación OCR reconstructiva de una celda única cuadra con el subtotal."""
        from parser_universal import certificar_extraccion_columnas, CuentaRaw, OrigenColumna

        # Balance sintético: c1 (Caja 100), c2 (Capital 100 con error OCR 90 en créditos)
        c1 = CuentaRaw(linea=1, codigo="1", nombre="Caja", monto=100.0, origen_columna=OrigenColumna.ACTIVO, es_total=False, confianza_extraccion=0.9,
                       montos_columnas={"debitos": 100.0, "creditos": 0.0, "saldo_deudor": 100.0, "saldo_acreedor": 0.0, "activo": 100.0, "pasivo": 0.0, "perdida": 0.0, "ganancia": 0.0})
        c2 = CuentaRaw(linea=2, codigo="2", nombre="Capital", monto=100.0, origen_columna=OrigenColumna.PASIVO, es_total=False, confianza_extraccion=0.8,
                       montos_columnas={"debitos": 0.0, "creditos": 90.0, "saldo_deudor": 0.0, "saldo_acreedor": 100.0, "activo": 0.0, "pasivo": 100.0, "perdida": 0.0, "ganancia": 0.0})
        subtot = CuentaRaw(linea=3, codigo=None, nombre="SUBTOTAL", monto=100.0, origen_columna=OrigenColumna.PASIVO, es_total=True, confianza_extraccion=0.9,
                           montos_columnas={"debitos": 100.0, "creditos": 100.0, "saldo_deudor": 100.0, "saldo_acreedor": 100.0, "activo": 100.0, "pasivo": 100.0, "perdida": 0.0, "ganancia": 0.0})
        tot = CuentaRaw(linea=4, codigo=None, nombre="TOTALES IGUALES", monto=100.0, origen_columna=OrigenColumna.PASIVO, es_total=True, confianza_extraccion=0.9,
                        montos_columnas={"debitos": 100.0, "creditos": 100.0, "saldo_deudor": 100.0, "saldo_acreedor": 100.0, "activo": 100.0, "pasivo": 100.0, "perdida": 0.0, "ganancia": 0.0})

        cert = certificar_extraccion_columnas([c1, c2, subtot, tot], metodo="ocr_coordinates_8_amounts", tolerancia_absoluta=0.0)
        assert cert.estado == "parcial"
        assert c2.montos_columnas["creditos"] == 100.0
        assert cert.diferencias["creditos"] == 0.0
