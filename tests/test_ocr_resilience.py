from __future__ import annotations

import subprocess
from pathlib import Path

from PIL import Image

import parser_universal as parser


def _imagen_temporal(tmp_path: Path, size: tuple[int, int] = (100, 100)) -> Path:
    path = tmp_path / "pagina.png"
    Image.new("RGB", size, "white").save(path)
    return path


def test_tesseract_limita_hilos_en_instancias_pequenas():
    assert parser._tesseract_env()["OMP_THREAD_LIMIT"] == "1"


def test_ocr_timeout_no_aborta_documento(monkeypatch, tmp_path, caplog):
    imagen = _imagen_temporal(tmp_path)

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])

    monkeypatch.setattr(parser.subprocess, "run", timeout)

    assert parser.ocr_pagina(imagen, 0) == ""
    assert "OCR excedió" in caplog.text


def test_ocr_timeout_reintenta_con_imagen_reducida(monkeypatch, tmp_path):
    imagen = _imagen_temporal(tmp_path, (200, 200))
    monkeypatch.setattr(parser, "OCR_MAX_PIXELS", 100_000)
    monkeypatch.setattr(parser, "OCR_RETRY_MAX_PIXELS", 10_000)
    llamadas = []

    def ejecutar(cmd, **kwargs):
        llamadas.append((Path(cmd[1]), kwargs["timeout"]))
        if len(llamadas) == 1:
            raise subprocess.TimeoutExpired(cmd, kwargs["timeout"])
        with Image.open(cmd[1]) as img:
            assert img.width * img.height <= parser.OCR_RETRY_MAX_PIXELS
        return subprocess.CompletedProcess(cmd, 0, stdout="Caja 100\n", stderr="")

    monkeypatch.setattr(parser.subprocess, "run", ejecutar)

    assert parser.ocr_pagina(imagen, 0) == "Caja 100\n"
    assert [timeout for _, timeout in llamadas] == [
        parser.OCR_PAGE_TIMEOUT_SECONDS,
        parser.OCR_RETRY_TIMEOUT_SECONDS,
    ]


def test_ocr_reduce_imagen_grande_antes_de_tesseract(monkeypatch, tmp_path):
    imagen = _imagen_temporal(tmp_path, (200, 200))
    monkeypatch.setattr(parser, "OCR_MAX_PIXELS", 10_000)
    observado = {}

    def ejecutar(cmd, **kwargs):
        entrada = Path(cmd[1])
        with Image.open(entrada) as img:
            observado["pixeles"] = img.width * img.height
        return subprocess.CompletedProcess(cmd, 0, stdout="Caja 100\n", stderr="")

    monkeypatch.setattr(parser.subprocess, "run", ejecutar)

    assert parser.ocr_pagina(imagen, 0) == "Caja 100\n"
    assert observado["pixeles"] <= parser.OCR_MAX_PIXELS


def test_ocr_error_de_tesseract_devuelve_vacio(monkeypatch, tmp_path, caplog):
    imagen = _imagen_temporal(tmp_path)

    monkeypatch.setattr(
        parser.subprocess,
        "run",
        lambda cmd, **kwargs: subprocess.CompletedProcess(
            cmd, 1, stdout="", stderr="language data unavailable"
        ),
    )

    assert parser.ocr_pagina(imagen, 0) == ""
    assert "Tesseract falló" in caplog.text


def test_ocr_reintenta_por_stdin_solo_si_leptonica_no_abre_ruta(monkeypatch, tmp_path):
    imagen = _imagen_temporal(tmp_path)
    llamadas = []

    def ejecutar(cmd, **kwargs):
        llamadas.append((cmd, kwargs))
        if cmd[1] != "stdin":
            return subprocess.CompletedProcess(
                cmd, 1, stdout="", stderr="failed to open locally",
            )
        assert kwargs["input"] == imagen.read_bytes()
        return subprocess.CompletedProcess(
            cmd, 0, stdout=b"Caja 100\n", stderr=b"",
        )

    monkeypatch.setattr(parser.subprocess, "run", ejecutar)

    assert parser.ocr_pagina(imagen, 0) == "Caja 100\n"
    assert [comando[1] for comando, _ in llamadas] == [str(imagen), "stdin"]


def test_tsv_reintenta_por_stdin_y_conserva_palabras(monkeypatch, tmp_path):
    imagen = _imagen_temporal(tmp_path)
    tsv = (
        b"level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
        b"5\t1\t2\t3\t4\t1\t31\t17\t42\t8\t95\t206.182\n"
    )

    def ejecutar(cmd, **kwargs):
        if cmd[1] != "stdin":
            return subprocess.CompletedProcess(
                cmd, 1, stdout="", stderr="image file cannot be read",
            )
        assert kwargs["input"] == imagen.read_bytes()
        return subprocess.CompletedProcess(cmd, 0, stdout=tsv, stderr=b"")

    monkeypatch.setattr(parser.subprocess, "run", ejecutar)

    assert parser.ocr_pagina_tsv(imagen, 0) == [{
        "text": "206.182", "x0": 31.0, "x1": 73.0,
        "image_top": 17.0, "image_bottom": 25.0, "top": 0.0,
    }]


def test_tsv_ocr_conserva_caja_real_para_relectura_focal(monkeypatch, tmp_path):
    imagen = _imagen_temporal(tmp_path)
    tsv = (
        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
        "5\t1\t2\t3\t4\t1\t31\t17\t42\t8\t95\t206.182\n"
    )
    monkeypatch.setattr(
        parser.subprocess,
        "run",
        lambda cmd, **kwargs: subprocess.CompletedProcess(
            cmd, 0, stdout=tsv, stderr="",
        ),
    )

    palabras = parser.ocr_pagina_tsv(imagen, 0)

    assert palabras == [{
        "text": "206.182", "x0": 31.0, "x1": 73.0,
        "image_top": 17.0, "image_bottom": 25.0, "top": 0.0,
    }]


def test_tsv_ocr_no_absorbe_lineas_despues_de_comilla_ocr(monkeypatch, tmp_path):
    imagen = _imagen_temporal(tmp_path)
    tsv = (
        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
        '5\t1\t2\t3\t4\t1\t10\t10\t4\t8\t90\t"\n'
        "5\t1\t2\t3\t5\t1\t20\t20\t24\t8\t90\tCaja\n"
    )
    monkeypatch.setattr(
        parser.subprocess,
        "run",
        lambda cmd, **kwargs: subprocess.CompletedProcess(
            cmd, 0, stdout=tsv, stderr="",
        ),
    )

    palabras = parser.ocr_pagina_tsv(imagen, 0)

    assert [palabra["text"] for palabra in palabras] == ['"', "Caja"]


def test_relectura_focal_desempata_solo_con_dos_umbrales_iguales(monkeypatch, tmp_path):
    imagen = _imagen_temporal(tmp_path)
    lecturas = iter([
        "2.853.529.183", "2.653.529.183", "2.653.529.163", "2.653.529.163",
    ])
    llamadas = []

    def ejecutar(*_args, **_kwargs):
        llamadas.append(True)
        return subprocess.CompletedProcess([], 0, stdout=next(lecturas), stderr="")

    monkeypatch.setattr(parser, "_ejecutar_tesseract_imagen", ejecutar)
    monkeypatch.setattr(parser, "OCR_CELL_THRESHOLDS", (100, 120))
    monkeypatch.setattr(parser, "OCR_CELL_TIEBREAK_THRESHOLDS", (140, 180))

    lectura = parser._releer_celda_ocr_focal(
        {"bbox": (10, 10, 80, 25), "imagen": str(imagen)}, {},
    )

    assert lectura == 2_653_529_163
    assert len(llamadas) == 4


def test_relectura_focal_amplia_celda_tsv_demasiado_baja(monkeypatch, tmp_path):
    imagen = _imagen_temporal(tmp_path, (100, 100))
    tamanos = []

    def ejecutar(imagen_entrada, *_args, **_kwargs):
        with Image.open(imagen_entrada) as recorte:
            tamanos.append((recorte.width, recorte.height))
        return subprocess.CompletedProcess([], 0, stdout="123", stderr="")

    monkeypatch.setattr(parser, "_ejecutar_tesseract_imagen", ejecutar)

    lectura = parser._releer_celda_ocr_focal(
        {"bbox": (10, 10, 20, 15), "imagen": str(imagen)}, {},
    )

    assert lectura == 123
    assert len(tamanos) == len(parser.OCR_CELL_THRESHOLDS)
    assert all(alto >= parser.OCR_CELL_MIN_HEIGHT_PIXELS for _, alto in tamanos)


def test_relectura_focal_nativa_conserva_la_resolucion_del_recorte(monkeypatch, tmp_path):
    imagen = _imagen_temporal(tmp_path, (100, 100))
    tamanos = []

    def ejecutar(imagen_entrada, *_args, **_kwargs):
        with Image.open(imagen_entrada) as recorte:
            tamanos.append((recorte.width, recorte.height))
        return subprocess.CompletedProcess([], 0, stdout="123", stderr="")

    monkeypatch.setattr(parser, "_ejecutar_tesseract_imagen", ejecutar)

    lectura = parser._releer_celda_ocr_focal(
        {"bbox": (10, 10, 20, 15), "imagen": str(imagen)}, {},
        preservar_escala=True,
    )

    assert lectura == 123
    assert len(tamanos) == len(parser.OCR_CELL_THRESHOLDS)
    assert all(alto < parser.OCR_CELL_MIN_HEIGHT_PIXELS for _, alto in tamanos)


def test_relectura_focal_prueba_umbral_alto_si_los_primarios_quedan_vacios(monkeypatch, tmp_path):
    imagen = _imagen_temporal(tmp_path)
    lecturas = iter(["", "", "3.987.645", "3.987645"])

    monkeypatch.setattr(
        parser,
        "_ejecutar_tesseract_imagen",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            [], 0, stdout=next(lecturas), stderr="",
        ),
    )
    monkeypatch.setattr(parser, "OCR_CELL_THRESHOLDS", (100, 120))
    monkeypatch.setattr(
        parser, "OCR_CELL_EMPTY_PRIMARY_THRESHOLDS", (200, 220),
    )

    lectura = parser._releer_celda_ocr_focal(
        {"bbox": (10, 10, 80, 25), "imagen": str(imagen)}, {},
    )

    assert lectura == 3_987_645


def test_relectura_focal_desempata_lecturas_altas_con_coincidencia_central(monkeypatch, tmp_path):
    imagen = _imagen_temporal(tmp_path)
    lecturas = iter(["", "", "6", "0", "0"])
    llamadas = []

    def ejecutar(*_args, **_kwargs):
        llamadas.append(True)
        return subprocess.CompletedProcess(
            [], 0, stdout=next(lecturas), stderr="",
        )

    monkeypatch.setattr(parser, "_ejecutar_tesseract_imagen", ejecutar)
    monkeypatch.setattr(parser, "OCR_CELL_THRESHOLDS", (100, 120))
    monkeypatch.setattr(
        parser, "OCR_CELL_EMPTY_PRIMARY_THRESHOLDS", (200, 220),
    )
    monkeypatch.setattr(
        parser, "OCR_CELL_EMPTY_PRIMARY_TIEBREAK_THRESHOLD", 210,
    )

    lectura = parser._releer_celda_ocr_focal(
        {"bbox": (10, 10, 80, 25), "imagen": str(imagen)}, {},
    )

    assert lectura == 0
    assert len(llamadas) == 5


def test_relectura_focal_rechaza_desempate_alto_sin_coincidencia(monkeypatch, tmp_path):
    imagen = _imagen_temporal(tmp_path)
    lecturas = iter(["", "", "6", "0", "9"])

    monkeypatch.setattr(
        parser,
        "_ejecutar_tesseract_imagen",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            [], 0, stdout=next(lecturas), stderr="",
        ),
    )
    monkeypatch.setattr(parser, "OCR_CELL_THRESHOLDS", (100, 120))
    monkeypatch.setattr(
        parser, "OCR_CELL_EMPTY_PRIMARY_THRESHOLDS", (200, 220),
    )
    monkeypatch.setattr(
        parser, "OCR_CELL_EMPTY_PRIMARY_TIEBREAK_THRESHOLD", 210,
    )

    assert parser._releer_celda_ocr_focal(
        {"bbox": (10, 10, 80, 25), "imagen": str(imagen)}, {},
    ) is None


def test_relectura_focal_interpreta_guion_aislado_como_cero(monkeypatch, tmp_path):
    imagen = _imagen_temporal(tmp_path)
    monkeypatch.setattr(
        parser,
        "_ejecutar_tesseract_imagen",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            [], 0, stdout="-", stderr="",
        ),
    )

    assert parser._releer_celda_ocr_focal(
        {"bbox": (10, 10, 80, 25), "imagen": str(imagen)}, {},
    ) == 0


def test_relectura_focal_rechaza_cuatro_lecturas_sin_consenso(monkeypatch, tmp_path):
    imagen = _imagen_temporal(tmp_path)
    lecturas = iter(["100", "101", "102", "103"])

    monkeypatch.setattr(
        parser,
        "_ejecutar_tesseract_imagen",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            [], 0, stdout=next(lecturas), stderr="",
        ),
    )
    monkeypatch.setattr(parser, "OCR_CELL_THRESHOLDS", (100, 120))
    monkeypatch.setattr(parser, "OCR_CELL_TIEBREAK_THRESHOLDS", (140, 180))

    assert parser._releer_celda_ocr_focal(
        {"bbox": (10, 10, 80, 25), "imagen": str(imagen)}, {},
    ) is None


def test_parseo_sin_texto_expone_advertencia_ocr(monkeypatch, tmp_path):
    pdf = tmp_path / "grande.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    monkeypatch.setattr(parser, "validar_archivo", lambda path: (True, "OK"))
    monkeypatch.setattr(parser.ParserPDF, "_analizar_documento", lambda self, path: None)

    def sin_texto(self, path, context):
        self._ocr_advertencias.append("Página 1: OCR sin texto utilizable")
        return [], True, 0

    monkeypatch.setattr(parser.ParserPDF, "_extraer_lineas", sin_texto)

    resultado = parser.ParserPDF().parsear(pdf)

    assert resultado.requirio_ocr is True
    assert "Página 1: OCR sin texto utilizable" in resultado.advertencias
    assert "No se pudo extraer texto" in resultado.advertencias[-1]


def test_linea_ocr_preserva_ceros_finales_y_columna_activo():
    cuenta = parser.parsear_linea(
        "1010101 Caja 3,100,000 1,385,515 1,714,485 0 1714485 o 0 o",
        numero_linea=10,
        formato_codigo=parser.FormatoCodigo.PUNTO,
        separador_miles=",",
        confianza_base=0.75,
    )

    assert cuenta is not None
    assert cuenta.codigo == "1010101"
    assert cuenta.nombre == "Caja"
    assert cuenta.monto == 1714485
    assert cuenta.origen_columna == parser.OrigenColumna.ACTIVO


def test_linea_ocr_vehiculo_queda_en_activo():
    cuenta = parser.parsear_linea(
        "1.02.03.03 Vehículos 23,871,062 o 23,871,062 O 23,871,062 o 0 o",
        numero_linea=33,
        formato_codigo=parser.FormatoCodigo.PUNTO,
        separador_miles=",",
        confianza_base=0.75,
    )

    assert cuenta is not None
    assert cuenta.nombre == "Vehículos"
    assert cuenta.monto == 23871062
    assert cuenta.origen_columna == parser.OrigenColumna.ACTIVO


def test_linea_ocr_tolera_ruido_breve_dentro_de_columnas_finales():
    cuenta = parser.parsear_linea(
        "1.01.02.01 Documentos en Garantía 2,550,000 0 2,550,000 O 2,550,000 o ly 0",
        numero_linea=12,
        formato_codigo=parser.FormatoCodigo.PUNTO,
        separador_miles=",",
        confianza_base=0.75,
    )

    assert cuenta is not None
    assert cuenta.nombre == "Documentos en Garantía"
    assert cuenta.monto == 2550000
    assert cuenta.origen_columna == parser.OrigenColumna.ACTIVO


def test_linea_ocr_recupera_codigo_con_un_separador_en_documento_punto():
    cuenta = parser.parsear_linea(
        "4.021201 Diferencias de cambio Perdida 572 o 572 o o o 572 o",
        numero_linea=80,
        formato_codigo=parser.FormatoCodigo.PUNTO,
        separador_miles=",",
        confianza_base=0.75,
    )

    assert cuenta is not None
    assert cuenta.codigo == "4.021201"
    assert cuenta.monto == 572
    assert cuenta.origen_columna == parser.OrigenColumna.PERDIDA


def test_linea_ocr_recupera_codigo_uniseparador_antes_de_iva_leido_como_uno():
    cuenta = parser.parsear_linea(
        "1107-03 1.V.A. CREDITO FISCAL 1.379.232.920 1.379.232.920 "
        "0 0 0 0 0 0",
        numero_linea=81,
        formato_codigo=parser.FormatoCodigo.SIN_CODIGO,
        separador_miles=".",
        confianza_base=0.75,
    )

    assert cuenta is not None
    assert cuenta.codigo == "1107-03"
    assert cuenta.nombre == "1.V.A. CREDITO FISCAL"
    assert cuenta.montos_columnas["debitos"] == 1_379_232_920
    assert cuenta.montos_columnas["creditos"] == 1_379_232_920


def test_linea_ocr_no_acepta_glosa_numerica_generica_como_codigo_auxiliar():
    cuenta = parser.parsear_linea(
        "1107-03 2021 CIERRE 100 0 100 0 100 0 0 0",
        numero_linea=82,
        formato_codigo=parser.FormatoCodigo.SIN_CODIGO,
        separador_miles=".",
        confianza_base=0.75,
    )

    assert cuenta is not None
    assert cuenta.codigo is None
    assert cuenta.nombre == "1107-03 2021 CIERRE"


def test_control_final_ocr_acepta_grupos_miles_con_separadores_mixtos():
    cuenta = parser.parsear_linea(
        "Total 5.833,800,607 5,833,800,607 1,090,033,508 1,090,033,508 "
        "368,616,530 368,616,530 741,589,846 741,589,846",
        numero_linea=99,
        formato_codigo=parser.FormatoCodigo.PUNTO,
        separador_miles=".",
        confianza_base=0.75,
    )

    assert cuenta is not None
    assert cuenta.es_total is True
    assert cuenta.montos_columnas == {
        "debitos": 5833800607.0,
        "creditos": 5833800607.0,
        "saldo_deudor": 1090033508.0,
        "saldo_acreedor": 1090033508.0,
        "activo": 368616530.0,
        "pasivo": 368616530.0,
        "perdida": 741589846.0,
        "ganancia": 741589846.0,
    }
    assert parser.parsear_monto("1.234,56", ".") == 1234.56


def test_normaliza_slash_perdido_en_codigo_ocr():
    assert parser.normalizar_codigo_ocr("2/03.01.01 Capital 0 1,000,000") == (
        "2.03.01.01 Capital 0 1,000,000"
    )


def test_tabla_nativa_preserva_posicion_de_perdida_y_ganancia():
    class Pagina:
        @staticmethod
        def extract_tables():
            return [[
                ['Nombre', 'Débitos', 'Créditos', 'Saldo Deudor',
                 'Saldo Acreedor', 'Activo', 'Pasivo', 'Perdida', 'Ganancia'],
                ['COSTO MOTOS', '80.149.009', '2.864.000', '77.285.009',
                 '-', '-', '-', '77.285.009', '-'],
                ['VENTA MOTOS', '546.449.983', '4.215.989.922', '-',
                 '3.669.539.939', '-', '-', '-', '3.669.539.939'],
            ]]

    lineas = parser._extraer_tabla_balance_8_columnas(Pagina())
    perdida = parser.parsear_linea(
        lineas[0], 1, parser.FormatoCodigo.SIN_CODIGO, '.', 1.0
    )
    ganancia = parser.parsear_linea(
        lineas[1], 2, parser.FormatoCodigo.SIN_CODIGO, '.', 1.0
    )

    assert perdida.nombre == 'COSTO MOTOS'
    assert perdida.monto == 77285009
    assert perdida.origen_columna == parser.OrigenColumna.PERDIDA
    assert ganancia.nombre == 'VENTA MOTOS'
    assert ganancia.monto == 3669539939
    assert ganancia.origen_columna == parser.OrigenColumna.GANANCIA
