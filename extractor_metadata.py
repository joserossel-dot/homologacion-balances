"""
extractor_metadata.py

Detecta automáticamente RUT, razón social y período del balance
desde el texto extraído del archivo (PDF o Excel).

Cubre los 4 formatos encontrados en los balances reales:
  - KAME ONE: "EMPRESA: INGEFIRE SpA", "RUT: 76.693.319-K"
  - Columnar estándar: primera línea = razón social, segunda = RUT
  - Inmobiliaria: "RAZON SOC.: ...", "R.U.T.: ..."
  - Texto libre: busca patrones RUT en cualquier posición
"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class MetadataEmpresa:
    rut: Optional[str] = None
    razon_social: Optional[str] = None
    periodo_desde: Optional[str] = None
    periodo_hasta: Optional[str] = None
    giro: Optional[str] = None
    confianza: float = 0.0  # 0-1, cuántos campos se detectaron


# ─── Patrones de RUT chileno ──────────────────────────────────────────────────
PATRON_RUT = re.compile(
    r'\b(\d{1,2}[\.\d]*\d{3}-[\dkK])\b'
)

# ─── Patrones de período ──────────────────────────────────────────────────────
PATRON_PERIODO_DESDE_HASTA = re.compile(
    r'(?:desde|from|del?|período|periodo|al|a)\s*[:\s]*'
    r'(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})'
    r'\s*(?:hasta|to|al|a)\s*'
    r'(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})',
    re.IGNORECASE
)
PATRON_ANIO_SIMPLE = re.compile(
    r'(?:año|ejercicio|periodo|al\s*31\s*de\s*diciembre)\s*(?:de\s*)?(\d{4})',
    re.IGNORECASE
)
PATRON_FECHA_CIERRE = re.compile(
    r'al\s+(\d{1,2})\s+de\s+(\w+)\s+(?:de\s+)?(\d{4})',
    re.IGNORECASE
)

# ─── Patrones de razón social / etiquetas ────────────────────────────────────
PATRON_EMPRESA_LABEL = re.compile(
    r'(?:empresa|company|razon\s*soc\.?|raz[oó]n\s*social|nombre)\s*[:\s]+([^\n\r]{3,80})',
    re.IGNORECASE
)
PATRON_RUT_LABEL = re.compile(
    r'(?:rut|r\.u\.t\.?|rut\s*n[oº°]?)\s*[:\s#Nº°]*\s*(\d{1,2}[\.\d]*\d{3}-[\dkK])',
    re.IGNORECASE
)
PATRON_GIRO = re.compile(
    r'(?:giro|actividad|rubro)\s*[:\s]+([^\n\r]{3,80})',
    re.IGNORECASE
)
PATRON_PERIODO_LABEL = re.compile(
    r'(?:per[ií]odo|ejercicio|balance)\s*(?:desde|del?|tributario)?\s*[:\s]*'
    r'(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})',
    re.IGNORECASE
)

MESES = {
    'enero': '01', 'febrero': '02', 'marzo': '03', 'abril': '04',
    'mayo': '05', 'junio': '06', 'julio': '07', 'agosto': '08',
    'septiembre': '09', 'octubre': '10', 'noviembre': '11', 'diciembre': '12'
}


def normalizar_fecha(fecha_str: str) -> str:
    """Normaliza fechas a formato DD/MM/YYYY."""
    fecha_str = fecha_str.strip()
    partes = re.split(r'[/\-\.]', fecha_str)
    if len(partes) == 3:
        d, m, a = partes
        if len(a) == 2:
            a = '20' + a
        return f"{d.zfill(2)}/{m.zfill(2)}/{a}"
    return fecha_str


def extraer_metadata(lineas: list[str]) -> MetadataEmpresa:
    """
    Extrae metadata de empresa desde las primeras líneas del balance.
    Estrategia: analizar las primeras 30 líneas donde suele estar el encabezado.
    """
    meta = MetadataEmpresa()
    texto_encabezado = '\n'.join(lineas[:40])

    # ── 1. RUT ────────────────────────────────────────────────────────────────
    # Primero buscar con etiqueta explícita
    m = PATRON_RUT_LABEL.search(texto_encabezado)
    if m:
        meta.rut = m.group(1).strip()
    else:
        # Buscar RUT en cualquier posición (las primeras 20 líneas)
        for linea in lineas[:20]:
            m = PATRON_RUT.search(linea)
            if m:
                meta.rut = m.group(1).strip()
                break

    # ── 2. Razón social ───────────────────────────────────────────────────────
    m = PATRON_EMPRESA_LABEL.search(texto_encabezado)
    if m:
        meta.razon_social = m.group(1).strip().title()
    else:
        # Heurística: primera línea no vacía que no sea fecha/número y
        # que tenga más de 5 chars → probable razón social
        for linea in lineas[:10]:
            linea = linea.strip()
            if (len(linea) > 5
                    and not re.match(r'^[\d/\-\.:]+$', linea)
                    and not re.match(r'^(balance|estado|rut|fecha|hora|pagina)', linea, re.I)
                    and not PATRON_RUT.search(linea)):
                meta.razon_social = linea.title()
                break

    # ── 3. Período ────────────────────────────────────────────────────────────
    m = PATRON_PERIODO_DESDE_HASTA.search(texto_encabezado)
    if m:
        meta.periodo_desde = normalizar_fecha(m.group(1))
        meta.periodo_hasta = normalizar_fecha(m.group(2))
    else:
        # Buscar "al 31 de diciembre de YYYY"
        m = PATRON_FECHA_CIERRE.search(texto_encabezado)
        if m:
            dia, mes_str, anio = m.group(1), m.group(2).lower(), m.group(3)
            mes = MESES.get(mes_str, '12')
            meta.periodo_hasta = f"{dia.zfill(2)}/{mes}/{anio}"
            meta.periodo_desde = f"01/01/{anio}"
        else:
            m = PATRON_ANIO_SIMPLE.search(texto_encabezado)
            if m:
                anio = m.group(1)
                meta.periodo_desde = f"01/01/{anio}"
                meta.periodo_hasta = f"31/12/{anio}"

    # ── 4. Giro ───────────────────────────────────────────────────────────────
    m = PATRON_GIRO.search(texto_encabezado)
    if m:
        meta.giro = m.group(1).strip().title()

    # ── Confianza ─────────────────────────────────────────────────────────────
    campos = [meta.rut, meta.razon_social, meta.periodo_hasta]
    meta.confianza = sum(1 for c in campos if c) / len(campos)

    return meta


# ─── Test ─────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    # Simular líneas del encabezado de INGEFIRE (KAME ONE)
    lineas_kame = [
        "KAME ONE Balance General",
        "BALANCE GENERAL",
        "PERÍODO DESDE 01/01/2023 HASTA 31/12/2023",
        "RUT: 76.693.319-K",
        "EMPRESA: INGEFIRE SpA",
    ]
    # DSI
    lineas_dsi = [
        "DESARROLLO DE SOLUCIONES INTEGRALES CHILE SPA",
        "RUT Nº 76437956-K",
        "AVDA LA DIVISA #0340 COMUNA SAN BERNARDO CIUDAD SANTIAGO",
        "BALANCE TRIBUTARIO",
        "COMPRENDIDO 01 DE ENERO 2023 AL 31 DE DICIEMBRE 2023",
    ]
    # Inmobiliaria
    lineas_inmo = [
        "RAZON SOC. : INMOBILIARIA RUIZ S.A.",
        "R.U.T. : 76.635.890-K",
        "GIRO : ARRIENDO BIENES INMUEBLES",
        "BALANCE GENERAL",
        "Desde 1/1/2023 Al 31/12/2023",
    ]
    # Maestranza
    lineas_maes = [
        "MAESTRANZA ISTRIA Y CIA LTDA.",
        "78951060-1",
        "BALANCE TRIBUTARIO (a nivel 4)",
        "Al 31 de Diciembre de 2021",
    ]

    for nombre, lineas in [
        ('KAME ONE (INGEFIRE)', lineas_kame),
        ('DSI Chile SpA', lineas_dsi),
        ('Inmobiliaria Ruiz', lineas_inmo),
        ('Maestranza Istria', lineas_maes),
    ]:
        m = extraer_metadata(lineas)
        print(f"\n{nombre}:")
        print(f"  RUT:          {m.rut}")
        print(f"  Razón social: {m.razon_social}")
        print(f"  Desde:        {m.periodo_desde}")
        print(f"  Hasta:        {m.periodo_hasta}")
        print(f"  Giro:         {m.giro}")
        print(f"  Confianza:    {m.confianza:.0%}")
