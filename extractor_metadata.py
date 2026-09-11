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
    moneda: Optional[str] = None
    mes_cierre: Optional[str] = None
    anio_cierre: Optional[int] = None
    numero_meses: Optional[int] = None
    periodos_detectados: tuple[str, ...] = ()
    periodos_seleccionados: tuple[str, ...] = ()
    confianza: float = 0.0  # 0-1, cuántos campos se detectaron


# ─── Patrones de RUT chileno ──────────────────────────────────────────────────
PATRON_RUT = re.compile(
    r'\b(\d{1,2}(?:\.\d{3}){2}-[\dkK]|\d{7,8}-[\dkK])\b'
)

# ─── Patrones de período ──────────────────────────────────────────────────────
PATRON_PERIODO_DESDE_HASTA = re.compile(
    r'(?:desde|from|del?|per[ií]odo|periodo|comprendido|al|a)\s*[:\s]*'
    r'(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})'
    r'\s*(?:hasta|to|al|a|-)\s*'
    r'(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})',
    re.IGNORECASE
)
PATRON_PERIODO_TEXTUAL = re.compile(
    r'(?:desde|del?|comprendido(?:\s+el)?)\s+(\d{1,2})\s+de\s+(\w+)\s+(?:de\s+|del\s+)?(\d{4})'
    r'\s+(?:hasta|al?)\s+(\d{1,2})\s+de\s+(\w+)\s+(?:de\s+|del\s+)?(\d{4})',
    re.IGNORECASE
)
PATRON_FECHA_CIERRE = re.compile(
    r'(?:al|a)\s+(\d{1,2})\s+de\s+(\w+)\s+(?:de\s+|del\s+)?(?:año\s+)?(\d{4})',
    re.IGNORECASE
)
PATRON_FECHA_CIERRE_DIGITOS = re.compile(
    r'(?:al|a|cierre(?:\s+al)?)\s*[:\s]*(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2,4})',
    re.IGNORECASE
)
PATRON_ANIO_SIMPLE = re.compile(
    r'(?:año|ejercicio|per[ií]odo\s*tributario|per[ií]odo|periodo)\s*(?:de\s+|del\s+|:\s*)?(\d{4})',
    re.IGNORECASE
)

# ─── Patrones de razón social / etiquetas ────────────────────────────────────
PATRON_EMPRESA_LABEL = re.compile(
    r'(?:empresa|company|razon\s*soc\.?|raz[oó]n\s*social|nombre\s*empresa|cliente|contribuyente|titular)\s*[:\s]+([^\n\r]{3,80})',
    re.IGNORECASE
)
PATRON_RUT_LABEL = re.compile(
    r'(?:rut|r\.u\.t\.?|rut\s*n[oº°]?|r\.u\.t\s*n[oº°]?)\s*[:\s#Nº°]*\s*(\d{1,2}[\.\d]*\d{3}-[\dkK])',
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
PATRON_MES_ANIO = re.compile(
    r'(?:acumulado\s+)?(?:mes\s*[\/\-]\s*a[ñn]o|mes|per[ií]odo|periodo|ejercicio)?\s*[:\s]*'
    r'([a-zA-ZáéíóúÁÉÍÓÚ]+)\s*(?:de|\/|\-|\s)\s*(\d{4})',
    re.IGNORECASE
)
PATRON_CORP_INDICATOR = re.compile(
    r'\b(spa|s\.a\.?|ltda\.?|limitada|sociedad|eirl|e\.i\.r\.l\.|inversiones|comercial|constructora|agricola|agrícola|servicios|asesorias|asesorías|consultora|ingenieria|ingeniería|transportes|distribuidora|exportadora|importadora|holding|corporacion|corporación)\b',
    re.IGNORECASE
)

ERP_NOISE_TERMS = {
    'kame one', 'kame', 'softland', 'defontana', 'erp', 'contapro', 'random',
    'sap', 'oracle', 'hyperion', 'pagina', 'página', 'fecha emision', 'fecha emisión',
    'impreso', 'balance general', 'balance tributario', 'balance clasificado',
    'balance de ocho columnas', 'balance 8 columnas', 'estado de situacion',
    'estado de situación', 'estado de resultados', 'libro mayor', 'plan de cuentas',
}

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


def _es_ruido_empresa(texto: str) -> bool:
    """Detecta si una línea o etiqueta corresponde a software ERP o cabecera genérica."""
    t = texto.strip().lower()
    if any(t.startswith(noise) or t == noise for noise in ERP_NOISE_TERMS):
        return True
    if re.match(r'^(balance|estado|rut|fecha|hora|pagina|página|hoja|usuario|informe)', t):
        return True
    if re.match(r'^[\d/\-\.:\s]+$', t):
        return True
    return False


def extraer_metadata(lineas: list[str]) -> MetadataEmpresa:
    """
    Extrae metadata de empresa desde las primeras líneas del balance.
    Estrategia: analizar las primeras 40 líneas donde suele estar el encabezado.
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
    if m and not _es_ruido_empresa(m.group(1)):
        meta.razon_social = m.group(1).strip().title()
    else:
        # Heurística: preferir líneas con indicadores corporativos (Ltda, SpA, S.A., etc.)
        for linea in lineas[:15]:
            linea_limpia = linea.strip()
            if (len(linea_limpia) > 4
                    and not _es_ruido_empresa(linea_limpia)
                    and not PATRON_RUT.search(linea_limpia)
                    and PATRON_CORP_INDICATOR.search(linea_limpia)):
                meta.razon_social = linea_limpia.title()
                break
        if not meta.razon_social:
            for linea in lineas[:15]:
                linea_limpia = linea.strip()
                if (len(linea_limpia) > 4
                        and not _es_ruido_empresa(linea_limpia)
                        and not PATRON_RUT.search(linea_limpia)):
                    meta.razon_social = linea_limpia.title()
                    break

    # ── 3. Período ────────────────────────────────────────────────────────────
    m_text = PATRON_PERIODO_TEXTUAL.search(texto_encabezado)
    if m_text:
        d1, m1_str, a1 = m_text.group(1), m_text.group(2).lower(), m_text.group(3)
        d2, m2_str, a2 = m_text.group(4), m_text.group(5).lower(), m_text.group(6)
        mes1 = MESES.get(m1_str, '01')
        mes2 = MESES.get(m2_str, '12')
        meta.periodo_desde = f"{d1.zfill(2)}/{mes1}/{a1}"
        meta.periodo_hasta = f"{d2.zfill(2)}/{mes2}/{a2}"
        meta.mes_cierre = m2_str.capitalize()
        meta.anio_cierre = int(a2)
        meta.periodos_detectados = (str(a2),) if a1 == a2 else (str(a2), str(a1))
    else:
        m_rango = PATRON_PERIODO_DESDE_HASTA.search(texto_encabezado)
        if m_rango:
            meta.periodo_desde = normalizar_fecha(m_rango.group(1))
            meta.periodo_hasta = normalizar_fecha(m_rango.group(2))
            partes_hasta = meta.periodo_hasta.split('/')
            if len(partes_hasta) == 3 and partes_hasta[2].isdigit():
                meta.anio_cierre = int(partes_hasta[2])
                meta.periodos_detectados = (partes_hasta[2],)
        else:
            m_mes_anio = PATRON_MES_ANIO.search(texto_encabezado)
            if m_mes_anio and m_mes_anio.group(1).lower() in MESES:
                mes_str, anio = m_mes_anio.group(1).lower(), m_mes_anio.group(2)
                mes = MESES[mes_str]
                meta.periodo_hasta = f"31/{mes}/{anio}"
                meta.periodo_desde = f"01/01/{anio}"
                meta.mes_cierre = mes_str.capitalize()
                meta.anio_cierre = int(anio)
                meta.periodos_detectados = (str(anio),)
            else:
                m_cierre = PATRON_FECHA_CIERRE.search(texto_encabezado)
                if m_cierre:
                    dia, mes_str, anio = m_cierre.group(1), m_cierre.group(2).lower(), m_cierre.group(3)
                    mes = MESES.get(mes_str, '12')
                    meta.periodo_hasta = f"{dia.zfill(2)}/{mes}/{anio}"
                    meta.periodo_desde = f"01/01/{anio}"
                    meta.mes_cierre = mes_str.capitalize()
                    meta.anio_cierre = int(anio)
                    meta.periodos_detectados = (str(anio),)
                else:
                    m_dig = PATRON_FECHA_CIERRE_DIGITOS.search(texto_encabezado)
                    if m_dig:
                        dia, mes, anio = m_dig.group(1), m_dig.group(2), m_dig.group(3)
                        if len(anio) == 2:
                            anio = '20' + anio
                        meta.periodo_hasta = f"{dia.zfill(2)}/{mes.zfill(2)}/{anio}"
                        meta.periodo_desde = f"01/01/{anio}"
                        meta.anio_cierre = int(anio)
                        meta.periodos_detectados = (str(anio),)
                    else:
                        m_anio = PATRON_ANIO_SIMPLE.search(texto_encabezado)
                        if m_anio:
                            anio = m_anio.group(1)
                            meta.periodo_desde = f"01/01/{anio}"
                            meta.periodo_hasta = f"31/12/{anio}"
                            meta.anio_cierre = int(anio)
                            meta.periodos_detectados = (str(anio),)

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
