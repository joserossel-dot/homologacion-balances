
"""
Parser Core 2.0 — Orquestador principal.

Procesa balances tributarios chilenos.

Incluye:
- extracción PDF mediante parser original
- detección orientación 180°
- detección layout
- detección formato códigos
- detección separador miles
- parseo unificado
- métricas
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


from parser_universal import (
    ParserPDF as _ParserPDF,
    validar_archivo,
    normalizar_codigo_ocr,
)


from parsers.config import (
    ParserConfig,
    load_config,
)


from parsers.format_detector import (
    detectar_formato_codigo,
    detectar_separador_miles,
    extraer_muestra_montos,
)


from parsers.line_parser import (
    RawAccount,
    parsear_todas,
)


from parsers.layout_detector import (
    DetectedLayout,
    LayoutDetector,
)


from parsers.hygiene import (
    es_linea_basura,
)



@dataclass
class ParseMetrics:

    total_lines: int = 0
    garbage_lines: int = 0
    parsed_accounts: int = 0
    blank_lines: int = 0
    rejected_lines: int = 0

    ocr_pages: int = 0
    ocr_time_seconds: float = 0.0

    extraction_confidence: float = 0.0
    layout_confidence: float = 0.0

    format_detected: str = ""

    warnings_count: int = 0

    total_time_seconds: float = 0.0


    def to_dict(self) -> dict[str, Any]:
        return asdict(self)



@dataclass
class ParseResult:

    file_name: str

    format: str

    thousands_sep: str

    used_ocr: bool

    rotation: int

    accounts: list[RawAccount]

    layout: DetectedLayout | None = None

    warnings: list[str] = field(
        default_factory=list
    )

    metrics: ParseMetrics = field(
        default_factory=ParseMetrics
    )




class ParserCore2:


    def __init__(
        self,
        config: ParserConfig | None = None
    ):

        self.config = (
            config
            or load_config()
        )

        self.parser_pdf = _ParserPDF()

        self.layout_detector = LayoutDetector()



    def parse(
        self,
        path: str | Path
    ) -> ParseResult:


        inicio = time.perf_counter()

        path = Path(path)



        # --------------------------------
        # VALIDACIÓN
        # --------------------------------

        ok, msg = validar_archivo(path)

        if not ok:

            return ParseResult(

                file_name=path.name,

                format="sin_codigo",

                thousands_sep=".",

                used_ocr=False,

                rotation=0,

                accounts=[],

                warnings=[
                    msg
                ]

            )



        # --------------------------------
        # EXTRACCIÓN ORIGINAL
        # --------------------------------

        resultado = (
            self.parser_pdf
            ._extraer_lineas(path)
        )


        if len(resultado) == 3:

            lineas, uso_ocr, rotacion = resultado

        else:

            lineas, uso_ocr = resultado

            rotacion = 0



        if not lineas:


            return ParseResult(

                file_name=path.name,

                format="sin_codigo",

                thousands_sep=".",

                used_ocr=uso_ocr,

                rotation=rotacion,

                accounts=[],

                warnings=[
                    "No se pudo extraer texto"
                ]

            )



        # --------------------------------
        # NORMALIZACIÓN
        # --------------------------------


        lineas = [

            normalizar_codigo_ocr(l)

            for l in lineas

        ]



        # --------------------------------
        # LAYOUT
        # --------------------------------


        if self.config.layout.enable_detection:

            layout = (
                self.layout_detector
                .detect(lineas)
            )

        else:

            layout = None




        # --------------------------------
        # FORMATO
        # --------------------------------


        tokens_codigo = [

            l.split()[0]

            for l in lineas

            if l.split()

        ][:50]


        formato = detectar_formato_codigo(
            tokens_codigo
        )



        montos = extraer_muestra_montos(
            lineas,
            50
        )


        separador = detectar_separador_miles(
            montos
        )



        # --------------------------------
        # PARSEO CUENTAS
        # --------------------------------


        confianza = (
            0.75
            if uso_ocr
            else 1.0
        )


        cuentas = parsear_todas(

            lineas,

            formato,

            separador,

            confianza

        )



        # --------------------------------
        # MÉTRICAS
        # --------------------------------


        total = len(
            [
                x for x in lineas
                if x.strip()
            ]
        )


        basura = sum(

            1
            for x in lineas
            if es_linea_basura(x)

        )


        rechazadas = max(

            0,

            total
            -
            basura
            -
            len(cuentas)

        )



        metricas = ParseMetrics(

            total_lines=total,

            garbage_lines=basura,

            parsed_accounts=len(cuentas),

            rejected_lines=rechazadas,

            extraction_confidence=confianza,

            layout_confidence=(

                layout.confidence
                if layout
                else 0

            ),

            format_detected=formato.value,

            total_time_seconds=round(

                time.perf_counter()
                -
                inicio,

                3

            )

        )



        warnings=[]


        if uso_ocr:

            warnings.append(
                "Documento procesado con OCR"
            )


        if rotacion == 180:

            warnings.append(
                "Documento corregido rotación 180°"
            )



        return ParseResult(

            file_name=path.name,

            format=formato.value,

            thousands_sep=separador,

            used_ocr=uso_ocr,

            rotation=rotacion,

            accounts=cuentas,

            layout=layout,

            warnings=warnings,

            metrics=metricas

        )
