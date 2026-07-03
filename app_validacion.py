"""
app_validacion.py — Plataforma de homologación de balances tributarios chilenos

Ejecutar con:
    streamlit run app_validacion.py

Requiere en el mismo directorio:
    - catalogo_maestro.json
    - diccionario.json
    - parser_universal.py
    - clasificador_codigo_cuenta.py
    - reglas_especiales.py

Funcionalidad:
    1. Carga de archivo (PDF o Excel)
    2. Clasificación híbrida: código de cuenta → diccionario (exacto/fuzzy) → reglas regex
       (embeddings y LLM quedan como Etapas 3-4 pendientes de infraestructura externa)
    3. Aplicación de reglas especiales (D1-D5 del análisis del vaciador)
    4. Cola de revisión para cuentas con confianza < umbral
    5. Balance normalizado agrupado por catálogo maestro
    6. Feedback loop: las correcciones se agregan al diccionario y son descargables
"""

import json
import re
from pathlib import Path

import pandas as pd
import streamlit as st
from rapidfuzz import fuzz, process

from clasificador_codigo_cuenta import ClasificadorCodigo
from reglas_especiales import ProcesadorReglasEspeciales, calcular_patrimonio_efectivo
from parser_universal import ParserPDF, CuentaRaw, OrigenColumna
from db_repository import RepositorioDiccionario, normalizar_nombre as normalizar_nombre_repo
from extractor_metadata import extraer_metadata, MetadataEmpresa

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent
BASE_DIR = Path(__file__).parent
UMBRAL_REVISION = 0.85  # bajo este valor, la cuenta va a la cola de revisión

st.set_page_config(
    page_title="Homologación de Balances Tributarios",
    page_icon="📊",
    layout="wide",
)


# ─────────────────────────────────────────────────────────────────────────────
# CARGA DE CATÁLOGO Y DICCIONARIO
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data
def cargar_catalogo() -> dict:
    with open(BASE_DIR / 'catalogo_maestro.json', encoding='utf-8') as f:
        return json.load(f)


@st.cache_data
def cargar_diccionario_base() -> list[dict]:
    with open(BASE_DIR / 'diccionario.json', encoding='utf-8') as f:
        return json.load(f)


# ─────────────────────────────────────────────────────────────────────────────
# REGLAS REGEX (subconjunto del motor de reglas — patrones de mayor cobertura)
# ─────────────────────────────────────────────────────────────────────────────

REGLAS_REGEX = [
    (r"\b(caja\s*chica|caja\s*y\s*banco|efectivo\s*y\s*equiv|disponible|caja|banco|cuenta\s*corriente\s*banco|cuenta\s*vista)\b", "AC.01", 0.90),
    (r"\b(inversion(es)?\s*(corto\s*plazo|cp)|fondos?\s*mutuos?|dep[oó]sito(s)?\s*a\s*plazo|pacto(s)?)\b", "AC.02", 0.92),
    (r"\b(clientes?|deudore(s)?\s*por\s*venta|cuentas?\s*por\s*cobrar\s*(clientes?)?)\b", "AC.03", 0.90),
    (r"\b(documento(s)?\s*por\s*cobrar|letras?\s*(por|a)\s*cobrar|pagare(s)?\s*por\s*cobrar|cheques?\s*por\s*cobrar)\b", "AC.04", 0.92),
    (r"\b(inventario(s)?|existencia(s)?|mercader[ií]a(s)?|stock|materia(s)?\s*prima(s)?|productos?\s*(terminado|en\s*proceso))\b", "AC.05", 0.92),
    (r"\b(relacionada(s)?\s*(cp|corriente)|cuenta\s*corriente\s*relacionad)\b", "AC.06", 0.88),
    (r"(cuenta\s+(particular|corriente)\s+(socio|accionista))|(cta\.?\s*(cte|particular)\s+(socio|accionista))|retiro(s)?\s+(de\s+)?socio|dividendo(s)?\s+(provisorio|anticipado)", "AC.06S", 0.93),
    (r"\b(iva\s*(credito|cf)|ppm|impuesto(s)?\s*por\s*recuperar|anticipo(s)?\s*(a\s*)?proveedor|gasto(s)?\s*anticipado(s)?|deudore(s)?\s*varios|fondos?\s*por\s*rendir)\b", "AC.07", 0.88),
    (r"\b(activo\s*fijo|propiedad(es)?\s*planta|maquinaria(s)?|veh[ií]culo(s)?|terreno(s)?|construccion(es)?|mueble(s)?\s*y\s*[uú]til(es)?|equipos?\s*(de\s*)?computacion)\b", "ANC.01", 0.90),
    (r"\b(intangible(s)?|goodwill|marca(s)?|patente(s)?|licencia(s)?|software|llave\s*de\s*negocio)\b", "ANC.03", 0.90),
    (r"\b(inversion(es)?\s*(permanente(s)?|lp|largo\s*plazo)|accione(s)?\s*en\s*sociedad|participacion(es)?\s*(en\s*)?soci)\b", "ANC.04", 0.90),
    (r"\b(relacionada(s)?\s*(lp|largo\s*plazo))\b", "ANC.05", 0.88),
    (r"\b(proveedor(es)?|acreedore(s)?\s*comercial|facturas?\s*por\s*pagar|cuentas?\s*por\s*pagar\s*proveedor)\b", "PC.01", 0.90),
    (r"\b(obligaciones?\s*bancarias?\s*(cp|corto)?|credito(s)?\s*banc|prestamo(s)?\s*banc|linea\s*de\s*credito|sobregiro)\b", "PC.02", 0.88),
    (r"\bleasing\s*(cp|corriente|corto)?\b", "PC.03", 0.90),
    (r"\bfactoring\b", "PC.04", 0.94),
    (r"\b(iva\s*(debito|df)|impuesto(s)?\s*por\s*pagar|provision\s*impuesto|impuesto\s*(a\s*la\s*)?renta|primera\s*categoria|impuesto\s*unico|ppm\s*por\s*pagar|impt?o\s*por\s*pagar)\b", "PC.05", 0.88),
    (r"\b(remuneracion(es)?|sueldo(s)?|vacaciones?|honorario(s)?\s*por\s*pagar|gratificacion(es)?|imposicion(es)?|afp|isapre|leyes\s*sociales|finiquito(s)?|indemnizacion)\b", "PC.06", 0.86),
    (r"\b(relacionada(s)?\s*(cp|corriente)\s*pasivo|cta\s*cte\s*socios?\s*\(?en\s*pasivo)\b", "PC.07", 0.86),
    (r"\b(anticipo(s)?\s*de\s*cliente(s)?|ingreso(s)?\s*(percibido|recibido).*(adelantado|anticipado)|otros?\s*pasivos?\s*(corrientes?|circulantes?)|provision(es)?\s*varia(s)?|acreedore(s)?\s*vario(s)?)\b", "PC.08", 0.85),
    (r"\b(obligaciones?\s*bancarias?\s*(lp|largo)|credito(s)?\s*banc.*largo|prestamo(s)?\s*banc.*largo|mutuo(s)?\s*hipotecario(s)?)\b", "PNC.01", 0.88),
    (r"\bleasing\s*(lp|largo)\b", "PNC.02", 0.90),
    (r"\b(bono(s)?|debenture(s)?)\b", "PNC.03", 0.90),
    (r"\b(relacionada(s)?\s*(lp|largo)\s*pasivo)\b", "PNC.04", 0.86),
    (r"\b(indemnizacion(es)?\s*(por\s*)?a[ñn]os?\s*(de\s*)?servicio|provision(es)?\s*lp|impuesto(s)?\s*diferido(s)?\s*lp)\b", "PNC.05", 0.85),
    (r"\b(capital\s*(pagado|suscrito|social|propio)?|aporte(s)?\s*(de\s*)?(capital|socios?))\b", "PAT.01", 0.90),
    (r"\b(reserva(s)?(\s*legal)?|prima\s*de\s*emision)\b", "PAT.02", 0.88),
    (r"\b(utilidad(es)?\s*(acumulada(s)?|retenida(s)?)|resultado(s)?\s*acumulado(s)?|p[eé]rdida(s)?\s*acumulada(s)?)\b", "PAT.03", 0.90),
    (r"\butilidad\s*del\s*(ejercicio|periodo|a[ñn]o)|resultado\s*del\s*(ejercicio|periodo)|p[eé]rdida\s*del\s*(ejercicio|periodo)|utilidad\s*[/(]?\s*p[eé]rdida\b", "PAT.04", 0.92),
    (r"\b(venta(s)?|ingreso(s)?\s*(por\s*venta|operacional|del\s*giro)|facturacion)\b", "ER.01", 0.90),
    (r"\bcosto(s)?\s*(de\s*)?(venta(s)?|explotacion|produccion|mercader[ií]a)\b", "ER.02", 0.92),
    (r"\bgasto(s)?\s*(de\s*)?(administracion|general(es)?|gestion)\b", "ER.04", 0.88),
    (r"\bgasto(s)?\s*(de\s*)?(venta(s)?|comercial(es)?|marketing|distribucion)\b", "ER.05", 0.88),
    (r"\b(depreciacion|amortizacion)\b", "ER.07", 0.90),
    (r"\bgasto(s)?\s*financiero(s)?|intere(s|ses)?\s*(pagado|bancario|leasing|factoring)|comision(es)?\s*bancaria(s)?", "ER.09", 0.90),
    (r"\bimpuesto\s*(a\s*la\s*renta|primera\s*categoria)\b", "ER.10", 0.90),
    (r"\butilidad\s*neta|resultado\s*neto|net\s*income|ganancia\s*neta", "ER.11", 0.92),
]
REGLAS_COMPILADAS = [(re.compile(p, re.IGNORECASE | re.UNICODE), c, conf) for p, c, conf in REGLAS_REGEX]


# Líneas que son encabezados/metadata del documento, no cuentas contables
PATRON_NO_CUENTA = re.compile(
    r'^(comprendido|periodo|per[ií]odo|desde|hasta|rut|r\.u\.t|balance|'
    r'fecha|p[aá]gina|hora|moneda|firma|declaro|art[ií]culo|situaci[oó]n|'
    r'cifras\s+expresadas|direcci[oó]n|comuna|^giro|raz[oó]n\s+soc|'
    r'^a\s+nivel|contabilidad\s+en)',
    re.IGNORECASE
)


def normalizar_nombre(nombre: str) -> str:
    n = nombre.lower().strip()
    n = re.sub(r"[^\w\sñáéíóú]", " ", n)
    n = re.sub(r"\s+", " ", n)
    return n.strip()


def propagar_clasificacion_resultados(nombre_original: str, codigo_final: str, metodo: str):
    """
    Propaga la clasificación de una cuenta a todos los demás balances cargados
    que tengan cuentas con el mismo nombre y requieran revisión o estén sin clasificar.
    """
    nombre_norm = normalizar_nombre(nombre_original)
    if 'resultados' in st.session_state and isinstance(st.session_state.resultados, dict):
        propagaciones = 0
        for fn in list(st.session_state.resultados.keys()):
            df_res = st.session_state.resultados[fn].copy()
            names = df_res['nombre_original'].fillna('').apply(normalizar_nombre)
            mask = names == nombre_norm
            # Propagar si requiere revisión, no tiene código clasificado o confianza < 1.0
            mask_target = mask & (
                df_res['requiere_revision'] | 
                (df_res['codigo_clasificado'] == '') | 
                (df_res['confianza'] < 1.0)
            )
            if mask_target.any():
                df_res.loc[mask_target, 'codigo_clasificado'] = codigo_final
                df_res.loc[mask_target, 'metodo'] = metodo
                df_res.loc[mask_target, 'confianza'] = 1.0
                df_res.loc[mask_target, 'requiere_revision'] = False
                st.session_state.resultados[fn] = df_res
                propagaciones += 1
        
        if propagaciones > 1:
            st.toast(f"Homologación propagada a {propagaciones - 1} otro(s) balance(s) 🔄", icon="🔄")


# ─────────────────────────────────────────────────────────────────────────────
# MOTOR DE CLASIFICACIÓN HÍBRIDA (Etapas 0-2: código, diccionario, reglas)
# ─────────────────────────────────────────────────────────────────────────────

class MotorHibridoLocal:
    """
    Versión sin PostgreSQL/Ollama del motor de homologación.
    Implementa Etapas 0-2 (código, diccionario exacto/fuzzy, reglas regex).
    Las Etapas 3-4 (embeddings, LLM) quedan pendientes de infraestructura
    y las cuentas que no superan el umbral van directo a la cola de revisión.
    """

    UMBRAL_CODIGO = 0.85

    # Nombres de cuenta que son intrínsecamente ambiguos (ingreso vs gasto)
    # Para estos, la columna de origen tiene prioridad sobre el diccionario
    NOMBRES_AMBIGUOS = {
        'arriendos', 'arriendo', 'intereses', 'interes',
        'honorarios', 'comisiones', 'servicios',
    }

    UMBRAL_DICCIONARIO_EXACTO = 0.98
    UMBRAL_DICCIONARIO_FUZZY = 0.85
    UMBRAL_REGLA = 0.80

    def __init__(self, diccionario: list[dict]):
        self.clasificador_codigo = ClasificadorCodigo()
        self.reglas_especiales = ProcesadorReglasEspeciales()
        # Índice exacto y lista para fuzzy
        self.dic_exacto = {normalizar_nombre(d['cuenta_original']): d for d in diccionario}
        self.dic_lista = list(self.dic_exacto.keys())

    def clasificar(
        self, cuenta: CuentaRaw, giro_empresa: str | None = None
    ) -> dict:
        nombre_norm = normalizar_nombre(cuenta.nombre)

        # ── Etapa 0.5: resolución anticipada por columna para nombres ambiguos ──
        if (cuenta.origen_columna != OrigenColumna.DESCONOCIDO
                and nombre_norm in self.NOMBRES_AMBIGUOS):
            col = cuenta.origen_columna
            es_ing = col in (OrigenColumna.GANANCIA, OrigenColumna.ACTIVO)
            es_gas = col in (OrigenColumna.PERDIDA,  OrigenColumna.PASIVO)
            MAPA_AMBIGUO = {
                'arriendos': ('ER.01', 'ER.04'),
                'arriendo':  ('ER.01', 'ER.04'),
                'intereses': ('ER.12', 'ER.09'),
                'interes':   ('ER.12', 'ER.09'),
                'honorarios':('ER.01', 'ER.04'),
                'honorario': ('ER.01', 'ER.04'),
                'comisiones':('ER.01', 'ER.05'),
                'servicios': ('ER.01', 'ER.04'),
            }
            if nombre_norm in MAPA_AMBIGUO:
                cod_ing, cod_gas = MAPA_AMBIGUO[nombre_norm]
                if es_ing:
                    return {'codigo_estandar': cod_ing, 'metodo': 'columna_ambiguo',
                            'confianza': 0.88, 'requiere_revision': False}
                if es_gas:
                    return {'codigo_estandar': cod_gas, 'metodo': 'columna_ambiguo',
                            'confianza': 0.88, 'requiere_revision': False}

        # ── Etapa 0: código de cuenta ────────────────────────────────────────
        r_codigo = self.clasificador_codigo.clasificar(cuenta.codigo)
        if r_codigo and r_codigo.confianza >= self.UMBRAL_CODIGO:
            resultado = {
                'codigo_estandar': r_codigo.codigo_estandar,
                'metodo': 'codigo',
                'confianza': r_codigo.confianza,
            }
        else:
            # ── Etapa 1: diccionario exacto ──────────────────────────────────
            if nombre_norm in self.dic_exacto:
                d = self.dic_exacto[nombre_norm]
                resultado = {
                    'codigo_estandar': d['codigo_estandar'],
                    'metodo': 'diccionario_exacto',
                    'confianza': self.UMBRAL_DICCIONARIO_EXACTO,
                }
            else:
                # ── Etapa 1b: diccionario fuzzy ──────────────────────────────
                match = process.extractOne(
                    nombre_norm, self.dic_lista, scorer=fuzz.token_sort_ratio
                )
                if match and match[1] >= 90:  # 0-100 scale
                    d = self.dic_exacto[match[0]]
                    resultado = {
                        'codigo_estandar': d['codigo_estandar'],
                        'metodo': 'diccionario_fuzzy',
                        'confianza': round(0.80 + (match[1] - 90) * 0.01, 3),
                    }
                else:
                    # ── Etapa 2: reglas regex ─────────────────────────────────
                    mejor = None
                    for patron, cod, conf in REGLAS_COMPILADAS:
                        if patron.search(nombre_norm):
                            if mejor is None or conf > mejor[1]:
                                mejor = (cod, conf)
                    if mejor:
                        resultado = {
                            'codigo_estandar': mejor[0],
                            'metodo': 'regla_regex',
                            'confianza': mejor[1],
                        }
                    else:
                        # Sin clasificar — pendiente Etapa 3/4 (embeddings/LLM)
                        resultado = {
                            'codigo_estandar': None,
                            'metodo': 'sin_clasificar',
                            'confianza': 0.0,
                        }

        # ── Etapa 3: corrección por columna de origen ────────────────────────
        # Si el nombre es ambiguo, la columna del balance resuelve la duda.
        # Ejemplo: "Arriendos" en columna Ganancia → ER.01 (ingreso)
        #           "Arriendos" en columna Pérdida  → ER.04 (gasto)
        codigo_actual = resultado.get('codigo_estandar')
        origen = cuenta.origen_columna
        if origen != OrigenColumna.DESCONOCIDO and codigo_actual:
            codigo_corregido = self._corregir_por_columna(
                nombre_norm, codigo_actual, origen, cuenta.monto
            )
            if codigo_corregido and codigo_corregido != codigo_actual:
                resultado['codigo_estandar'] = codigo_corregido
                resultado['metodo'] += '+columna'
                resultado['confianza'] = min(resultado['confianza'] + 0.05, 0.99)

        # ── Reglas especiales (post-procesamiento D1-D5) ─────────────────────
        codigo_pre = resultado['codigo_estandar'] or 'AC.08'
        ajuste = self.reglas_especiales.aplicar(
            cuenta.nombre, codigo_pre, cuenta.monto, giro_empresa
        )
        if ajuste.aplica:
            resultado['codigo_estandar'] = ajuste.codigo_final
            resultado['metodo'] += f'+regla_especial({ajuste.flag})'
            resultado['nota_regla_especial'] = ajuste.nota

        resultado['requiere_revision'] = resultado['confianza'] < UMBRAL_REVISION
        return resultado



    def _corregir_por_columna(self, nombre_norm, codigo_actual, origen, monto):
        """
        Usa la columna de origen del balance como desambiguador.
        Resuelve casos donde un mismo nombre puede ser ingreso o gasto.
        """
        from parser_universal import OrigenColumna as OC
        es_ingreso = origen in (OC.GANANCIA, OC.ACTIVO)
        es_gasto   = origen in (OC.PERDIDA,  OC.PASIVO)

        AMBIGUOS = [
            ('arriendo',             'ER.01', 'ER.04'),
            ('interes',              'ER.12', 'ER.09'),
            ('comision',             'ER.01', 'ER.05'),
            ('servicio',             'ER.01', 'ER.04'),
            ('honorario',            'ER.01', 'ER.04'),
            ('diferencia de cambio', 'ER.15', 'ER.15'),
            ('correccion monetaria', 'ER.14', 'ER.14'),
            ('otras ganancias',      'ER.13', 'ER.13'),
            ('reajuste',             'ER.14', 'ER.14'),
        ]

        # Banco con saldo negativo en activo -> sobregiro (PC.02)
        if (monto is not None and monto < 0
                and origen == OC.ACTIVO
                and codigo_actual in ('AC.01',)
                and any(k in nombre_norm for k in ('banco','cta cte','cuenta corriente'))):
            return 'PC.02'

        for keyword, cod_ing, cod_gas in AMBIGUOS:
            if keyword in nombre_norm:
                if es_ingreso and codigo_actual not in (cod_ing, cod_gas):
                    return cod_ing
                if es_gasto and codigo_actual not in (cod_ing, cod_gas):
                    return cod_gas

        # Cuenta clasificada como ER.XX pero aparece en seccion balance
        if origen in (OC.ACTIVO, OC.PASIVO) and codigo_actual and codigo_actual.startswith('ER'):
            return None  # no corregir, dejar para revision humana

        return None


# ─────────────────────────────────────────────────────────────────────────────
# CARGA DE ARCHIVOS
# ─────────────────────────────────────────────────────────────────────────────

def parsear_excel(file) -> list[CuentaRaw]:
    """Parser simple de Excel: detecta columna de nombre y montos finales."""
    df = pd.read_excel(file, header=None)
    cuentas = []
    for i, row in df.iterrows():
        vals = [v for v in row.tolist() if pd.notna(v)]
        if not vals:
            continue
        # primer valor de texto = nombre, último valor numérico = monto
        textos = [v for v in vals if isinstance(v, str)]
        numeros = [v for v in vals if isinstance(v, (int, float))]
        if not textos:
            continue
        nombre = max(textos, key=len)
        if len(nombre) < 3:
            continue
        codigo = None
        primer = str(vals[0])
        if re.match(r'^[\d.\-]+$', primer) and primer != nombre:
            codigo = primer
        monto = numeros[-1] if numeros else None
        cuentas.append(CuentaRaw(
            linea=i, codigo=codigo, nombre=nombre, monto=monto,
            origen_columna=OrigenColumna.DESCONOCIDO, confianza_extraccion=0.9
        ))
    return cuentas


# ─────────────────────────────────────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    st.title("📊 Homologación de Balances Tributarios Chilenos")
    st.caption(
        "Carga uno o más balances (PDF o Excel) → clasificación híbrida automática "
        "(código → diccionario → reglas) → cola de revisión → balance normalizado."
    )

    catalogo = cargar_catalogo()
    dic_base = cargar_diccionario_base()

    if 'diccionario' not in st.session_state:
        st.session_state.diccionario = list(dic_base)
    if 'resultados' not in st.session_state or not isinstance(st.session_state.resultados, dict):
        st.session_state.resultados = {}
    if 'metadata_files' not in st.session_state:
        st.session_state.metadata_files = {}
    if 'correcciones' not in st.session_state:
        st.session_state.correcciones = []

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.header("⚙️ Configuración")
        archivos = st.file_uploader(
            "Balances tributarios", type=['pdf', 'xlsx', 'xls'], accept_multiple_files=True
        )
        giro = st.selectbox(
            "Giro de la empresa (afecta regla D2-Terrenos)",
            ['Otro', 'Inmobiliaria', 'Construcción', 'Promotora'],
            help="Si el giro es inmobiliario/construcción, los terrenos en "
                 "activo corriente se reclasifican como inventario (AC.05)."
        )
        giro_norm = None if giro == 'Otro' else giro.lower()

        st.divider()
        st.metric("Cuentas en diccionario", len(st.session_state.diccionario))
        st.metric("Códigos en catálogo", len(catalogo))

        if st.session_state.correcciones:
            st.divider()
            st.success(f"{len(st.session_state.correcciones)} correcciones pendientes")
            buf = json.dumps(st.session_state.diccionario, ensure_ascii=False, indent=2)
            st.download_button(
                "⬇️ Descargar diccionario actualizado",
                data=buf, file_name="diccionario_actualizado.json",
                mime="application/json"
            )

    if not archivos:
        st.info("⬆️ Carga uno o más archivos en la barra lateral para comenzar.")
        st.session_state.resultados = {}
        st.session_state.metadata_files = {}
        st.session_state.metadata_confirmada = False
        _mostrar_resumen_catalogo(catalogo)
        return

    # ── Detección y confirmación de datos de empresa ──────────────────────────
    if not st.session_state.get('metadata_confirmada', False):
        first_file = archivos[0]
        with st.spinner(f"Detectando metadata de la empresa en {first_file.name}..."):
            lineas_encabezado = _extraer_lineas_encabezado(first_file)
            meta = extraer_metadata(lineas_encabezado)
            st.session_state.company_rut = meta.rut or ""
            st.session_state.company_razon = meta.razon_social or ""
            st.session_state.company_giro = meta.giro or "Otro"

        st.subheader("📋 Confirma los datos de la empresa")
        st.caption("El sistema detectó los siguientes datos generales. Corrígelos si es necesario antes de continuar.")

        with st.form("form_empresa"):
            col1, col2 = st.columns(2)
            with col1:
                rut = st.text_input("RUT", value=st.session_state.company_rut)
                razon = st.text_input("Razón Social", value=st.session_state.company_razon)
            with col2:
                giro_list = ['Otro', 'Inmobiliaria', 'Construcción', 'Promotora']
                default_giro_idx = 0
                if st.session_state.company_giro in giro_list:
                    default_giro_idx = giro_list.index(st.session_state.company_giro)
                giro_sel = st.selectbox(
                    "Giro de la empresa (afecta regla D2-Terrenos)",
                    giro_list,
                    index=default_giro_idx
                )

            submitted = st.form_submit_button("✅ Confirmar y procesar todos los balances")
            if submitted:
                st.session_state.company_rut = rut
                st.session_state.company_razon = razon
                st.session_state.company_giro = giro_sel
                st.session_state.metadata_confirmada = True
                st.session_state.resultados = {}
                st.session_state.metadata_files = {}
                st.rerun()
        return

    company_giro_norm = None if st.session_state.company_giro == 'Otro' else st.session_state.company_giro.lower()

    # Limpiar archivos viejos de resultados
    nombres_subidos = [a.name for a in archivos]
    for k in list(st.session_state.resultados.keys()):
        if k not in nombres_subidos:
            st.session_state.resultados.pop(k, None)
            st.session_state.metadata_files.pop(k, None)

    # Procesar archivos nuevos
    for archivo in archivos:
        if archivo.name not in st.session_state.resultados:
            with st.spinner(f"Clasificando cuentas de {archivo.name}..."):
                lineas_encabezado = _extraer_lineas_encabezado(archivo)
                meta_indiv = extraer_metadata(lineas_encabezado)
                st.session_state.metadata_files[archivo.name] = meta_indiv

                cuentas = _extraer_cuentas(archivo)
                motor = MotorHibridoLocal(st.session_state.diccionario)
                filas = []
                for c in cuentas:
                    if c.monto is None and not c.codigo:
                        continue
                    if not c.codigo and PATRON_NO_CUENTA.match(c.nombre.strip()):
                        continue
                    r = motor.clasificar(c, company_giro_norm)
                    filas.append({
                        'linea': c.linea,
                        'codigo_original': c.codigo or '',
                        'nombre_original': c.nombre,
                        'monto': c.monto,
                        'origen_columna': c.origen_columna.value,
                        'es_total': c.es_total,
                        'codigo_clasificado': r['codigo_estandar'] or '',
                        'metodo': r['metodo'],
                        'confianza': r['confianza'],
                        'requiere_revision': r['requiere_revision'],
                        'nota': r.get('nota_regla_especial', ''),
                        'confianza_extraccion': c.confianza_extraccion,
                        'origen_columna_display': c.origen_columna.value,
                    })
                df_file = pd.DataFrame(filas)
                st.session_state.resultados[archivo.name] = df_file
# After processing all uploaded files, propagate classifications across all balances
if 'propagation_done' not in st.session_state:
    # Define helper to propagate classifications across balances
    def propagar_entre_balances():
        """Propaga códigos clasificados entre balances cargados."""
        # Build mapping from normalized account name to list of (file, index)
        name_map = {}
        resultados = getattr(st.session_state, "resultados", {})
        for fname, df in resultados.items():
            for idx, row in df.iterrows():
                nombre = row['nombre_original']
                if not nombre:
                    continue
                norm = normalizar_nombre(nombre)
                name_map.setdefault(norm, []).append((fname, idx, row['codigo_clasificado']))
        # Propagar si existe alguna clasificación
        for norm, entries in name_map.items():
            classified_code = None
            for fname, idx, cod in entries:
                if cod and cod not in ('', '__EXCLUIR__'):
                    classified_code = cod
                    break
            if classified_code:
                for fname, idx, cod in entries:
                    if not cod or cod == '':
                        st.session_state.resultados[fname].at[idx, 'codigo_clasificado'] = classified_code
                        st.session_state.resultados[fname].at[idx, 'metodo'] = 'propagado_automático'
                        st.session_state.resultados[fname].at[idx, 'confianza'] = 1.0
                        st.session_state.resultados[fname].at[idx, 'requiere_revision'] = False
    propagar_entre_balances()
    st.session_state['propagation_done'] = True

    # ── Selección de archivo activo ───────────────────────────────────────────
    with st.sidebar:
        st.divider()
        st.subheader("📁 Balances Cargados")
        # Mostrar resumen de estado de cada archivo
        if 'nombres_subidos' not in locals() and 'nombres_subidos' not in globals():
            nombres_subidos = []
        for name in nombres_subidos:
            df_f = st.session_state.resultados.get(name)
            if df_f is not None and not df_f.empty:
                pendientes_f = df_f[df_f['requiere_revision'] | (df_f['codigo_clasificado'] == '')]
                pendientes_f = pendientes_f[~pendientes_f['es_total']]
                n_pendientes = len(pendientes_f)
                if n_pendientes > 0:
                    st.caption(f"🔸 `{name}` ({n_pendientes} pendientes)")
                else:
                    st.caption(f"✅ `{name}` (completo)")
            else:
                st.caption(f"⏳ `{name}` (procesando)")

        st.write("")
        archivo_activo_name = st.selectbox(
            "Ver y validar balance:",
            options=nombres_subidos,
            index=0 if nombres_subidos else None,
            key="archivo_activo_select"
        )

    # Obtener el objeto de archivo y el DataFrame correspondiente
    archivo_activo = next(a for a in archivos if a.name == archivo_activo_name)
    df = st.session_state.resultados[archivo_activo_name]
    meta_activo = st.session_state.metadata_files.get(archivo_activo_name)

    if df.empty:
        st.warning(f"No se extrajeron cuentas del archivo {archivo_activo_name}.")
        st.stop()

    # ── Banner empresa ────────────────────────────────────────────────────────
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(f"**{st.session_state.company_razon or '—'}**  \n`{st.session_state.company_rut or '—'}`")
        periodo_str = "—"
        if meta_activo:
            periodo_str = f"{meta_activo.periodo_desde or '—'} → {meta_activo.periodo_hasta or '—'}"
        c2.markdown(f"**Período del Balance**  \n{periodo_str}")
        c3.markdown(f"**Giro**  \n{st.session_state.company_giro or '—'}")
        c4.markdown(f"**Archivo Activo**  \n`{archivo_activo_name}`")

    # ── Layout: visor izquierda | clasificación derecha ──────────────────────
    col_visor, col_trabajo = st.columns([1, 1], gap="medium")

    with col_visor:
        _visor_documento(archivo_activo)

    with col_trabajo:
        tab_resumen, tab_revision, tab_balance, tab_diccionario = st.tabs(
            ["📈 Resumen", "🔍 Cola de Revisión", "📋 Balance Normalizado", "📚 Diccionario"]
        )

        with tab_resumen:
            _tab_resumen(df)

        with tab_revision:
            _tab_revision(
                df,
                catalogo,
                motor=MotorHibridoLocal(st.session_state.diccionario),
                archivo_nombre=archivo_activo_name
            )

        with tab_balance:
            _tab_balance(df, catalogo)

        with tab_diccionario:
            _tab_diccionario()


def _visor_documento(archivo):
    """
    Visor de documento: renderiza el PDF como imágenes de alta resolución
    con controles de página, zoom y rotación. Para Excel muestra tabla HTML.
    """
    import tempfile, base64, io
    from PIL import Image

    suffix = Path(archivo.name).suffix.lower()
    archivo.seek(0)

    # ── Controles del visor ───────────────────────────────────────────────────
    st.markdown("#### 📄 Documento original")

    if suffix == '.pdf':
        # Convertir PDF a imágenes (una por página)
        clave_imgs = f"_imgs_{archivo.name}"
        if clave_imgs not in st.session_state:
            with st.spinner("Cargando páginas del documento..."):
                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                    tmp.write(archivo.read())
                    tmp_path = Path(tmp.name)
                archivo.seek(0)
                try:
                    from pdf2image import convert_from_path
                    import shutil
                    # Detectar ruta de poppler automáticamente
                    pdftoppm_path = shutil.which('pdftoppm')
                    poppler_dir = str(Path(pdftoppm_path).parent) if pdftoppm_path else '/usr/local/bin'
                    imgs = convert_from_path(
                        str(tmp_path),
                        dpi=180,
                        poppler_path=poppler_dir,
                    )
                    st.session_state[clave_imgs] = imgs
                except Exception as e:
                    # Fallback: usar pdftoppm directamente
                    import subprocess, glob
                    tmpdir = tempfile.mkdtemp()
                    subprocess.run(
                        ['/usr/local/bin/pdftoppm', '-png', '-r', '180',
                         str(tmp_path), f'{tmpdir}/page'],
                        capture_output=True
                    )
                    img_files = sorted(glob.glob(f'{tmpdir}/page*.png'))
                    imgs = [Image.open(f) for f in img_files]
                    st.session_state[clave_imgs] = imgs

        imgs = st.session_state.get(clave_imgs, [])
        n_paginas = len(imgs)

        if not imgs:
            st.warning("No se pudo renderizar el documento.")
            return

        # ── Controles de navegación y visualización ───────────────────────────
        ctrl1, ctrl2, ctrl3 = st.columns([2, 2, 2])
        with ctrl1:
            pagina = st.number_input(
                f"Página (1-{n_paginas})",
                min_value=1, max_value=n_paginas,
                value=1, step=1,
                key="visor_pagina"
            )
        with ctrl2:
            zoom = st.slider(
                "Zoom", min_value=50, max_value=200,
                value=100, step=10,
                format="%d%%",
                key="visor_zoom"
            )
        with ctrl3:
            rotacion = st.select_slider(
                "Rotación",
                options=[0, 90, 180, 270],
                value=0,
                format_func=lambda x: f"{x}°",
                key="visor_rot"
            )

        # ── Renderizar la página seleccionada ─────────────────────────────────
        img = imgs[pagina - 1]

        # Aplicar rotación si corresponde
        if rotacion != 0:
            img = img.rotate(-rotacion, expand=True)

        # Aplicar zoom
        if zoom != 100:
            w, h = img.size
            nuevo_w = int(w * zoom / 100)
            nuevo_h = int(h * zoom / 100)
            img = img.resize((nuevo_w, nuevo_h), Image.LANCZOS)

        # Convertir a base64 para mostrar en HTML con scroll
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        b64 = base64.b64encode(buf.getvalue()).decode()

        # Contenedor con scroll fijo — altura 70% del viewport
        html_visor = f"""
        <div style="
            height: 72vh;
            overflow-y: auto;
            overflow-x: auto;
            border: 1px solid #d0d0d0;
            border-radius: 8px;
            background: #f5f5f5;
            padding: 8px;
            text-align: center;
        ">
            <img src="data:image/png;base64,{b64}"
                 style="max-width: none; cursor: zoom-in;"
                 title="Página {pagina} de {n_paginas} — {archivo.name}"/>
        </div>
        <div style="font-size:12px; color:#888; text-align:center; margin-top:4px;">
            Página {pagina} de {n_paginas} · {archivo.name}
        </div>
        """
        st.html(html_visor)

    elif suffix in ('.xlsx', '.xls'):
        # Para Excel: mostrar como tabla HTML desplazable
        archivo.seek(0)
        try:
            df_raw = pd.read_excel(archivo, header=None, dtype=str)
            df_raw = df_raw.fillna('')
            html_tabla = df_raw.to_html(
                index=False, header=False, border=0,
                classes='excel-visor'
            )
            html_visor = f"""
            <style>
                .excel-visor td {{
                    padding: 3px 8px;
                    border-bottom: 1px solid #eee;
                    font-size: 12px;
                    white-space: nowrap;
                    font-family: monospace;
                }}
                .excel-visor tr:nth-child(even) {{ background: #f9f9f9; }}
            </style>
            <div style="
                height: 72vh;
                overflow-y: auto;
                overflow-x: auto;
                border: 1px solid #d0d0d0;
                border-radius: 8px;
                background: white;
                padding: 8px;
            ">
                {html_tabla}
            </div>
            <div style="font-size:12px; color:#888; text-align:center; margin-top:4px;">
                {archivo.name}
            </div>
            """
            st.html(html_visor)
        except Exception as e:
            st.error(f"No se pudo mostrar el Excel: {e}")
        finally:
            archivo.seek(0)


def _extraer_lineas_encabezado(archivo) -> list[str]:
    """Extrae solo las primeras líneas del archivo para detectar metadata."""
    import tempfile
    suffix = Path(archivo.name).suffix.lower()
    archivo.seek(0)
    if suffix == '.pdf':
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            tmp.write(archivo.read())
            tmp_path = Path(tmp.name)
        try:
            import pdfplumber
            with pdfplumber.open(tmp_path) as pdf:
                texto = pdf.pages[0].extract_text() or ""
                return texto.split('\n')[:40]
        except Exception:
            return []
        finally:
            archivo.seek(0)
    else:
        # Excel: leer primeras filas como texto
        archivo.seek(0)
        df = pd.read_excel(archivo, header=None, nrows=15)
        archivo.seek(0)
        lineas = []
        for _, row in df.iterrows():
            vals = [str(v) for v in row if str(v) not in ('nan', 'None', '')]
            if vals:
                lineas.append(' '.join(vals))
        return lineas


def _extraer_cuentas(archivo) -> list[CuentaRaw]:
    suffix = Path(archivo.name).suffix.lower()
    if suffix == '.pdf':
        # ParserPDF espera un Path; guardamos temporalmente
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            tmp.write(archivo.read())
            tmp_path = Path(tmp.name)
        parser = ParserPDF()
        resultado = parser.parsear(tmp_path)
        for adv in resultado.advertencias:
            st.warning(adv)
        return resultado.cuentas
    else:
        return parsear_excel(archivo)


def _tab_resumen(df: pd.DataFrame):
    col1, col2, col3, col4 = st.columns(4)
    total = len(df)
    sin_clasificar = (df['codigo_clasificado'] == '').sum()
    requiere_rev = df['requiere_revision'].sum()
    confianza_prom = df.loc[df['confianza'] > 0, 'confianza'].mean()

    col1.metric("Cuentas extraídas", total)
    col2.metric("Sin clasificar", sin_clasificar,
                 help="Pendientes de Etapa 3 (embeddings) o 4 (LLM)")
    col3.metric("En cola de revisión", int(requiere_rev),
                 delta=f"{100*requiere_rev/total:.0f}% del total" if total else None,
                 delta_color="inverse")
    col4.metric("Confianza promedio", f"{confianza_prom:.0%}" if pd.notna(confianza_prom) else "—")

    st.subheader("Cobertura por método de clasificación")
    dist = df['metodo'].apply(lambda m: m.split('+')[0]).value_counts()
    dist_df = dist.reset_index()
    dist_df.columns = ['Método', 'Cuentas']
    dist_df['% del total'] = (dist_df['Cuentas'] / total * 100).round(1)

    METODO_LABELS = {
        'codigo': '0 · Código de cuenta',
        'diccionario_exacto': '1 · Diccionario (exacto)',
        'diccionario_fuzzy': '1b · Diccionario (fuzzy)',
        'regla_regex': '2 · Reglas regex',
        'sin_clasificar': '3-4 · Pendiente (embeddings/LLM)',
    }
    dist_df['Método'] = dist_df['Método'].map(lambda m: METODO_LABELS.get(m, m))
    st.dataframe(dist_df, use_container_width=True, hide_index=True)

    if (df['metodo'].str.contains('regla_especial')).any():
        st.subheader("⚠️ Reglas especiales aplicadas (D1-D5)")
        especiales = df[df['metodo'].str.contains('regla_especial')]
        st.dataframe(
            especiales[['nombre_original', 'monto', 'codigo_clasificado', 'nota']],
            use_container_width=True, hide_index=True
        )

    if (df['confianza_extraccion'] < 1.0).any():
        n_ocr = (df['confianza_extraccion'] < 1.0).sum()
        st.warning(
            f"⚠️ {n_ocr} cuentas fueron extraídas vía OCR (confianza de extracción "
            f"reducida). Revisar montos manualmente antes de validar."
        )


def _tab_revision(df: pd.DataFrame, catalogo: dict, motor: MotorHibridoLocal, archivo_nombre: str):
    pendientes = df[df['requiere_revision'] | (df['codigo_clasificado'] == '')]
    pendientes = pendientes[~pendientes['es_total']]

    if pendientes.empty:
        st.success("✅ No hay cuentas pendientes de revisión.")
        return

    opciones_codigo = [''] + sorted(catalogo.keys()) + ['➕ NUEVA CATEGORÍA', '🚫 NO INCLUIR']

    # ── Inicializar selección en lote ─────────────────────────────────────────
    if 'lote_seleccion' not in st.session_state:
        st.session_state.lote_seleccion = set()

    # ── PANEL DE ASIGNACIÓN EN LOTE ───────────────────────────────────────────
    n_sel = len(st.session_state.lote_seleccion)
    with st.container(border=True):
        st.markdown(f"#### 📦 Asignación en lote — {n_sel} cuenta(s) seleccionada(s)")

        bc1, bc2, bc3 = st.columns([3, 2, 1])
        with bc1:
            cat_lote = st.selectbox(
                "Clasificar todas las seleccionadas como:",
                opciones_codigo,
                format_func=lambda c: (
                    f"{c} — {catalogo[c]['nombre_estandar']}" if c in catalogo
                    else c if c else "(elegir categoría)"
                ),
                key="lote_categoria"
            )
        with bc2:
            alcance_lote = st.radio(
                "Alcance",
                ["Solo este caso", "Agregar al diccionario"],
                index=1, horizontal=True, key="lote_alcance"
            )
        with bc3:
            st.write("")
            st.write("")
            confirmar_lote = st.button(
                f"✅ Confirmar lote ({n_sel})",
                disabled=(n_sel == 0 or not cat_lote),
                use_container_width=True
            )

        if confirmar_lote and n_sel > 0 and cat_lote:
            codigo_lote = '__EXCLUIR__' if cat_lote == '🚫 NO INCLUIR' else (
                cat_lote if cat_lote != '➕ NUEVA CATEGORÍA' else None
            )
            if codigo_lote:
                procesados = 0
                for idx_lote in list(st.session_state.lote_seleccion):
                    nombre_orig = df.at[idx_lote, 'nombre_original']
                    st.session_state.resultados[archivo_nombre].at[idx_lote, 'codigo_clasificado'] = codigo_lote
                    st.session_state.resultados[archivo_nombre].at[idx_lote, 'metodo'] = 'validacion_humana_lote'
                    st.session_state.resultados[archivo_nombre].at[idx_lote, 'confianza'] = 1.0
                    st.session_state.resultados[archivo_nombre].at[idx_lote, 'requiere_revision'] = False
                    if "diccionario" in alcance_lote:
                        entrada = {
                            'cuenta_original': nombre_orig,
                            'codigo_estandar': codigo_lote,
                            'fuente': 'validacion_humana_lote'
                        }
                        st.session_state.diccionario.append(entrada)
                        st.session_state.correcciones.append(entrada)
                    # PROPAGACIÓN:
                    propagar_clasificacion_resultados(nombre_orig, codigo_lote, 'validacion_humana_lote_propagada')
                    procesados += 1
                if "diccionario" in alcance_lote:
                    with open(BASE_DIR / 'diccionario.json', 'w', encoding='utf-8') as f:
                        json.dump(st.session_state.diccionario, f, ensure_ascii=False, indent=2)
                st.session_state.lote_seleccion = set()
                nombre_cat = catalogo.get(codigo_lote, {}).get('nombre_estandar', codigo_lote)
                st.toast(f"{procesados} cuentas → {codigo_lote} ({nombre_cat})", icon="✅")
                st.rerun()

        # Botones de selección rápida
        qa, qb, qc = st.columns(3)
        if qa.button("☑️ Seleccionar todas", use_container_width=True):
            st.session_state.lote_seleccion = set(pendientes.index.tolist())
            st.rerun()
        if qb.button("🟦 Seleccionar sin clasificar", use_container_width=True):
            st.session_state.lote_seleccion = set(
                pendientes[pendientes['codigo_clasificado'] == ''].index.tolist()
            )
            st.rerun()
        if qc.button("⬜ Limpiar selección", use_container_width=True):
            st.session_state.lote_seleccion = set()
            st.rerun()

    st.write(f"**{len(pendientes)} cuentas** pendientes de revisión")
    st.divider()

    # ── LISTA INDIVIDUAL CON CHECKBOXES ───────────────────────────────────────
    for idx, row in pendientes.iterrows():
        seleccionada = idx in st.session_state.lote_seleccion

        with st.container(border=seleccionada):
            c0, c1, c2, c3 = st.columns([0.4, 3, 2, 3])

            # Checkbox de selección
            with c0:
                st.write("")
                marcado = st.checkbox(
                    "", value=seleccionada, key=f"chk_{idx}",
                    label_visibility="collapsed"
                )
                if marcado and idx not in st.session_state.lote_seleccion:
                    st.session_state.lote_seleccion.add(idx)
                    st.rerun()
                elif not marcado and idx in st.session_state.lote_seleccion:
                    st.session_state.lote_seleccion.discard(idx)
                    st.rerun()

            with c1:
                st.markdown(f"**{row['nombre_original']}**")
                monto_str = f"{row['monto']:,.0f}" if pd.notna(row['monto']) else "—"
                col_origen = row.get("origen_columna_display", "desconocido")
                col_label = {
                    "activo": "📗 Activo", "pasivo": "📕 Pasivo",
                    "ganancia": "📈 Ganancia", "perdida": "📉 Pérdida",
                    "deudor": "Deudor", "acreedor": "Acreedor",
                    "desconocido": "—",
                }.get(col_origen, col_origen)
                st.caption(
                    f"Código original: `{row['codigo_original'] or '—'}` · "
                    f"Monto: **{monto_str}** · Columna: {col_label}"
                )
                if row['nota']:
                    st.caption(f"ℹ️ {row['nota']}")

            with c2:
                metodo_label = row['metodo'].split('+')[0]
                st.write(f"Método: `{metodo_label}`")
                st.write(f"Confianza: {row['confianza']:.0%}")
                sugerido = row['codigo_clasificado']
                if sugerido and sugerido != '__EXCLUIR__':
                    cat_info = catalogo.get(sugerido, {})
                    nombre_sug = cat_info.get('nombre_estandar', sugerido)
                    desc_sug = cat_info.get('descripcion', '')
                    st.write(f"Sugerido: **{sugerido}** — {nombre_sug}")
                    if desc_sug:
                        st.caption(f"📖 {desc_sug}")
                elif sugerido == '__EXCLUIR__':
                    st.write("Marcada: **No incluir** 🚫")
                else:
                    st.write("Sugerido: *(ninguno)*")

            with c3:
                default_idx = (opciones_codigo.index(sugerido)
                               if sugerido in opciones_codigo else 0)
                seleccion = st.selectbox(
                    "Clasificación correcta",
                    opciones_codigo,
                    index=default_idx,
                    format_func=lambda c: (
                        f"{c} — {catalogo[c]['nombre_estandar']}" if c in catalogo
                        else c if c else "(sin clasificar)"
                    ),
                    key=f"sel_{idx}"
                )

                es_nueva_cat = seleccion == '➕ NUEVA CATEGORÍA'
                if es_nueva_cat:
                    st.info("Define la nueva categoría:")
                    nuevo_codigo = st.text_input("Código (ej: AC.10, ER.17)",
                                                  key=f"new_cod_{idx}", max_chars=10)
                    nuevo_nombre = st.text_input("Nombre de la categoría",
                                                  key=f"new_nom_{idx}")
                    nuevo_tipo = st.selectbox("Tipo de estado",
                                              ['balance', 'resultados'],
                                              key=f"new_tipo_{idx}")
                    nuevo_cat = st.selectbox(
                        "Categoría",
                        ['activo_corriente', 'activo_no_corriente',
                         'pasivo_corriente', 'pasivo_no_corriente',
                         'patrimonio', 'resultado'],
                        key=f"new_cat_{idx}"
                    )

                if not es_nueva_cat and seleccion not in ('', '🚫 NO INCLUIR'):
                    alcance = st.radio(
                        "¿Aplicar esta clasificación?",
                        ["Solo para este caso",
                         "Agregar al diccionario (aplica a casos futuros iguales)"],
                        index=1, key=f"alc_{idx}", horizontal=True
                    )
                else:
                    alcance = "Solo para este caso"

                if st.button("✅ Confirmar", key=f"btn_{idx}"):
                    codigo_final = None

                    if es_nueva_cat:
                        if nuevo_codigo and nuevo_nombre:
                            nueva_entrada = {
                                'codigo_estandar': nuevo_codigo.strip().upper(),
                                'nombre_estandar': nuevo_nombre.strip(),
                                'categoria': nuevo_cat,
                                'tipo_estado': nuevo_tipo,
                                'naturaleza': 'deudora' if nuevo_cat.startswith('activo') else 'acreedora',
                                'signo_normal': 1,
                                'es_deuda_financiera': False,
                                'es_activo_liquido': False,
                                'afecta_ebitda': False,
                            }
                            catalogo[nuevo_codigo.strip().upper()] = nueva_entrada
                            with open(BASE_DIR / 'catalogo_maestro.json', 'w', encoding='utf-8') as f:
                                json.dump(catalogo, f, ensure_ascii=False, indent=2)
                            codigo_final = nuevo_codigo.strip().upper()
                            st.toast(f"Nueva categoría '{nuevo_nombre}' ({codigo_final}) creada ✨", icon="🆕")
                        else:
                            st.error("Debes ingresar código y nombre.")

                    elif seleccion == '🚫 NO INCLUIR':
                        st.session_state.resultados[archivo_nombre].at[idx, 'codigo_clasificado'] = '__EXCLUIR__'
                        st.session_state.resultados[archivo_nombre].at[idx, 'metodo'] = 'excluido_analista'
                        st.session_state.resultados[archivo_nombre].at[idx, 'confianza'] = 1.0
                        st.session_state.resultados[archivo_nombre].at[idx, 'requiere_revision'] = False
                        if "diccionario" in alcance:
                            st.session_state.diccionario.append({
                                'cuenta_original': row['nombre_original'],
                                'codigo_estandar': '__EXCLUIR__',
                                'fuente': 'excluido_analista'
                            })
                            with open(BASE_DIR / 'diccionario.json', 'w', encoding='utf-8') as f:
                                json.dump(st.session_state.diccionario, f, ensure_ascii=False, indent=2)
                        # PROPAGACIÓN:
                        propagar_clasificacion_resultados(row['nombre_original'], '__EXCLUIR__', 'excluido_analista_propagado')
                        st.session_state.lote_seleccion.discard(idx)
                        st.toast(f"'{row['nombre_original'][:35]}' excluida", icon="🚫")
                        st.rerun()

                    elif seleccion:
                        codigo_final = seleccion

                    if codigo_final:
                        st.session_state.resultados[archivo_nombre].at[idx, 'codigo_clasificado'] = codigo_final
                        st.session_state.resultados[archivo_nombre].at[idx, 'metodo'] = 'validacion_humana'
                        st.session_state.resultados[archivo_nombre].at[idx, 'confianza'] = 1.0
                        st.session_state.resultados[archivo_nombre].at[idx, 'requiere_revision'] = False
                        st.session_state.lote_seleccion.discard(idx)
                        if "diccionario" in alcance:
                            nuevo_dic = {
                                'cuenta_original': row['nombre_original'],
                                'codigo_estandar': codigo_final,
                                'fuente': 'validacion_humana'
                            }
                            st.session_state.diccionario.append(nuevo_dic)
                            st.session_state.correcciones.append(nuevo_dic)
                            with open(BASE_DIR / 'diccionario.json', 'w', encoding='utf-8') as f:
                                json.dump(st.session_state.diccionario, f, ensure_ascii=False, indent=2)
                            st.toast(f"'{row['nombre_original'][:35]}' → {codigo_final} guardado 📚", icon="✅")
                        else:
                            st.toast(f"'{row['nombre_original'][:35]}' → {codigo_final} (solo este caso)", icon="✅")
                        # PROPAGACIÓN:
                        propagar_clasificacion_resultados(row['nombre_original'], codigo_final, 'validacion_humana_propagada')
                        st.rerun()


def _tab_balance(df: pd.DataFrame, catalogo: dict):
    clasificadas = df[(df['codigo_clasificado'] != '') & (df['codigo_clasificado'] != '__EXCLUIR__') & (~df['es_total'])].copy()
    if clasificadas.empty:
        st.info("No hay cuentas clasificadas todavía.")
        return

    clasificadas['monto'] = clasificadas['monto'].fillna(0)
    agrupado = clasificadas.groupby('codigo_clasificado').agg(
        monto_total=('monto', 'sum'),
        num_cuentas=('nombre_original', 'count'),
    ).reset_index()
    agrupado['nombre_estandar'] = agrupado['codigo_clasificado'].map(
        lambda c: catalogo.get(c, {}).get('nombre_estandar', c)
    )
    agrupado['categoria'] = agrupado['codigo_clasificado'].map(
        lambda c: catalogo.get(c, {}).get('categoria', '')
    )

    orden_cat = ['activo_corriente', 'activo_no_corriente', 'pasivo_corriente',
                  'pasivo_no_corriente', 'patrimonio', 'resultado']
    agrupado['orden'] = agrupado['categoria'].map(
        lambda c: orden_cat.index(c) if c in orden_cat else 99)
    agrupado = agrupado.sort_values(['orden', 'codigo_clasificado'])

    LABELS_CAT = {
        'activo_corriente': '🟦 Activo Corriente',
        'activo_no_corriente': '🟦 Activo No Corriente',
        'pasivo_corriente': '🟥 Pasivo Corriente',
        'pasivo_no_corriente': '🟥 Pasivo No Corriente',
        'patrimonio': '🟩 Patrimonio',
        'resultado': '🟨 Estado de Resultados',
    }

    for cat in orden_cat:
        sub = agrupado[agrupado['categoria'] == cat]
        if sub.empty:
            continue
        st.subheader(LABELS_CAT.get(cat, cat))
        tabla = sub[['codigo_clasificado', 'nombre_estandar', 'monto_total', 'num_cuentas']].copy()
        tabla.columns = ['Código', 'Cuenta Estándar', 'Monto Total', '# Cuentas Agrupadas']
        tabla['Monto Total'] = tabla['Monto Total'].map(lambda x: f"{x:,.0f}")
        st.dataframe(tabla, use_container_width=True, hide_index=True)
        st.metric(f"Subtotal {LABELS_CAT.get(cat, cat)}", f"{sub['monto_total'].sum():,.0f}")
        st.divider()

    # Ajuste D5: patrimonio efectivo
    pat = agrupado[agrupado['categoria'] == 'patrimonio']
    ac06s = agrupado[agrupado['codigo_clasificado'] == 'AC.06S']
    if not pat.empty:
        monto_ac06s = ac06s['monto_total'].sum() if not ac06s.empty else 0.0
        ajuste = calcular_patrimonio_efectivo(
            dict(zip(pat['codigo_clasificado'], pat['monto_total'])), monto_ac06s
        )
        st.subheader("🎯 Patrimonio Efectivo (criterio conservador D5)")
        c1, c2, c3 = st.columns(3)
        c1.metric("Patrimonio contable", f"{ajuste['patrimonio_contable']:,.0f}")
        c2.metric("Ajuste cta. socios (AC.06S)", f"-{ajuste['ajuste_cta_socios']:,.0f}")
        c3.metric("Patrimonio efectivo", f"{ajuste['patrimonio_efectivo']:,.0f}")
        if ajuste['alerta']:
            st.error(
                "⚠️ El ajuste por cuenta corriente de socios supera el 20% del "
                "patrimonio contable. Revisar si corresponde a un préstamo "
                "documentado o a un retiro de utilidades."
            )

    # ── PANEL DE APERTURA: detalle de cuentas agrupadas ─────────────────────
    st.subheader("🔎 Apertura de cuenta estándar")
    opciones_apertura = ['— Seleccionar cuenta —'] + [
        f"{row['codigo_clasificado']} — {row['nombre_estandar']}"
        for _, row in agrupado.iterrows()
        if row['codigo_clasificado'] not in ('', '__EXCLUIR__')
    ]
    seleccion_apertura = st.selectbox(
        "Selecciona una cuenta para ver las cuentas originales que la componen:",
        opciones_apertura,
        key="apertura_cuenta"
    )
    if seleccion_apertura != '— Seleccionar cuenta —':
        codigo_apertura = seleccion_apertura.split(' — ')[0].strip()
        detalle = clasificadas[
            clasificadas['codigo_clasificado'] == codigo_apertura
        ][['codigo_original', 'nombre_original', 'monto', 'metodo', 'confianza']].copy()
        detalle = detalle.sort_values('monto', key=abs, ascending=False)
        detalle.columns = ['Cód. Original', 'Nombre Original', 'Monto', 'Método', 'Confianza']
        detalle['Monto'] = detalle['Monto'].apply(
            lambda x: f"${x:,.0f}" if pd.notna(x) else "—"
        )
        detalle['Confianza'] = detalle['Confianza'].apply(
            lambda x: f"{x:.0%}" if pd.notna(x) else "—"
        )
        nombre_std = agrupado[
            agrupado['codigo_clasificado'] == codigo_apertura
        ]['nombre_estandar'].iloc[0] if not agrupado[
            agrupado['codigo_clasificado'] == codigo_apertura
        ].empty else codigo_apertura
        total_apertura = clasificadas[
            clasificadas['codigo_clasificado'] == codigo_apertura
        ]['monto'].sum()
        st.markdown(
            f"**{codigo_apertura} — {nombre_std}** "
            f"· {len(detalle)} cuenta(s) · Total: **${total_apertura:,.0f}**"
        )
        st.dataframe(detalle, use_container_width=True, hide_index=True)
        # Guardar apertura en session_state para incluirla en el Excel
        st.session_state['_apertura_codigo'] = codigo_apertura
        st.session_state['_apertura_detalle'] = detalle
    st.divider()

    # ── VALIDACIÓN: Cuadre Utilidad ER.11 vs PAT.04 ──────────────────────────
    _validar_cuadre_utilidad(df, agrupado, clasificadas)

    # Exportar
    # Nombre de archivo dinámico
    meta = st.session_state.get("metadata")
    razon = (meta.razon_social or "empresa").replace(" ", "_")[:30] if meta else "empresa"
    rut   = (meta.rut or "").replace(".", "").replace("-", "") if meta else ""
    fecha = (meta.periodo_hasta or "").replace("/", "-") if meta else ""
    nombre_archivo = f"Balance_Unificado-{razon}-{fecha}-{rut}"

    # Exportar Excel con formato
    import io
    export_df = agrupado[["codigo_clasificado", "nombre_estandar", "monto_total", "num_cuentas"]].copy()
    export_df.columns = ["Código", "Cuenta Estándar", "Monto Total (M$)", "# Cuentas Agrupadas"]
    export_df["Monto Total (M$)"] = export_df["Monto Total (M$)"].round(0).astype(int)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        # ── Sección 1: Balance homologado ──────────────────────────────────────
        # Fila de inicio tras el encabezado de empresa (5 filas + 1 header)
        FILA_INICIO_BALANCE = 7  # filas 1-5 empresa, 6 vacía, 7 header datos

        export_df.to_excel(
            writer, index=False,
            sheet_name="Balance Normalizado",
            startrow=FILA_INICIO_BALANCE - 1
        )
        ws = writer.sheets["Balance Normalizado"]

        # Info empresa
        if meta:
            ws["A1"] = "Empresa:";   ws["B1"] = meta.razon_social or ""
            ws["A2"] = "RUT:";       ws["B2"] = meta.rut or ""
            ws["A3"] = "Período:";   ws["B3"] = f'{meta.periodo_desde or ""} al {meta.periodo_hasta or ""}'
            ws["A4"] = "Giro:";      ws["B4"] = meta.giro or ""

        # Ancho de columnas
        ws.column_dimensions["A"].width = 12
        ws.column_dimensions["B"].width = 36
        ws.column_dimensions["C"].width = 22
        ws.column_dimensions["D"].width = 20

        # Estilo header balance
        from openpyxl.styles import Font, PatternFill, Alignment
        AZUL = "1F4E79"; BLANCO = "FFFFFF"; GRIS = "F2F2F2"
        header_fill = PatternFill("solid", fgColor=AZUL)
        header_font = Font(bold=True, color=BLANCO, size=11)
        for cell in ws[FILA_INICIO_BALANCE]:
            cell.fill = header_fill
            cell.font = header_font

        # Alternar filas balance
        for i, row in enumerate(
            ws.iter_rows(
                min_row=FILA_INICIO_BALANCE + 1,
                max_row=FILA_INICIO_BALANCE + len(export_df),
                max_col=4
            ), start=0
        ):
            if i % 2 == 0:
                for cell in row:
                    cell.fill = PatternFill("solid", fgColor=GRIS)

        # ── Sección 2: Apertura de cuentas (debajo del balance) ────────────────
        fila_sep = FILA_INICIO_BALANCE + len(export_df) + 3

        # Construir detalle completo — nombre_estandar no existe en clasificadas,
        # se obtiene desde el catálogo usando codigo_clasificado
        catalogo_local = cargar_catalogo()
        det = clasificadas[
            (clasificadas['codigo_clasificado'] != '') &
            (clasificadas['codigo_clasificado'] != '__EXCLUIR__') &
            (~clasificadas['es_total'])
        ][['codigo_clasificado', 'codigo_original',
           'nombre_original', 'monto', 'metodo', 'confianza']].copy()

        det['nombre_estandar'] = det['codigo_clasificado'].map(
            lambda c: catalogo_local.get(c, {}).get('nombre_estandar', c)
        )

        detalle_completo = det[[
            'codigo_clasificado', 'nombre_estandar', 'codigo_original',
            'nombre_original', 'monto', 'metodo', 'confianza'
        ]].copy()

        detalle_completo = detalle_completo.sort_values(
            ['codigo_clasificado', 'monto'],
            key=lambda x: x.abs() if x.dtype.kind == 'f' else x,
            ascending=[True, False]
        )
        detalle_completo.columns = [
            'Código Estándar', 'Nombre Estándar',
            'Cód. Original', 'Nombre Original',
            'Monto', 'Método Clasificación', 'Confianza'
        ]
        detalle_completo['Monto'] = detalle_completo['Monto'].apply(
            lambda x: round(x, 0) if pd.notna(x) else 0
        )
        detalle_completo['Confianza'] = detalle_completo['Confianza'].apply(
            lambda x: f"{x:.0%}" if pd.notna(x) else ""
        )

        # Título de sección 2
        ws.cell(row=fila_sep, column=1, value="APERTURA DE CUENTAS — DETALLE COMPLETO")
        title_cell = ws.cell(row=fila_sep, column=1)
        title_cell.font = Font(bold=True, size=12, color=AZUL)

        # Escribir detalle
        detalle_completo.to_excel(
            writer, index=False,
            sheet_name="Balance Normalizado",
            startrow=fila_sep  # fila_sep es 1-based, startrow es 0-based => +1 desfase ok
        )

        # Estilo header apertura
        header_row_ap = fila_sep + 1
        naranja = "E26B0A"
        for cell in ws[header_row_ap]:
            cell.fill = PatternFill("solid", fgColor=naranja)
            cell.font = Font(bold=True, color=BLANCO, size=10)

        # Ancho columnas adicionales
        ws.column_dimensions["E"].width = 18
        ws.column_dimensions["F"].width = 22
        ws.column_dimensions["G"].width = 12

    buf.seek(0)
    st.download_button(
        "⬇️ Descargar balance normalizado (Excel)",
        data=buf.getvalue(),
        file_name=f"{nombre_archivo}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


def _validar_cuadre_utilidad(
    df: pd.DataFrame,
    agrupado: pd.DataFrame,
    clasificadas: pd.DataFrame,
):
    """
    Valida que la Utilidad Neta del ER (ER.11) cuadre con el
    Resultado del Ejercicio en Patrimonio (PAT.04).
    Tolerancia: $1.000 pesos.

    En caso de descuadre ejecuta tres diagnósticos:
      A — Detalle del ER con montos y signos
      B — Búsqueda de cuenta con monto igual a la diferencia (signo cambiado)
      C — Cuentas excluidas o sin clasificar que podrían ser del ER
    """
    TOLERANCIA = 1_000

    # ── Obtener valores ───────────────────────────────────────────────────────
    er11_row = agrupado[agrupado['codigo_clasificado'] == 'ER.11']
    pat04_row = agrupado[agrupado['codigo_clasificado'] == 'PAT.04']

    er11 = er11_row['monto_total'].sum() if not er11_row.empty else None
    pat04 = pat04_row['monto_total'].sum() if not pat04_row.empty else None

    st.subheader("🔍 Validación: Cuadre Utilidad del Ejercicio")

    # ── Sin datos suficientes ─────────────────────────────────────────────────
    if er11 is None and pat04 is None:
        st.warning(
            "No se encontraron cuentas clasificadas como ER.11 (Utilidad Neta) "
            "ni PAT.04 (Resultado del Ejercicio). "
            "Verifica que el Estado de Resultados esté completo."
        )
        return

    if er11 is None:
        st.warning(
            f"⚠️ No hay cuentas clasificadas como **ER.11 (Utilidad Neta)**. "
            f"PAT.04 = **${pat04:,.0f}**. "
            "Revisa que todas las líneas del Estado de Resultados estén clasificadas."
        )
        return

    if pat04 is None:
        st.warning(
            f"⚠️ No hay cuentas clasificadas como **PAT.04 (Resultado del Ejercicio)**. "
            f"ER.11 = **${er11:,.0f}**. "
            "Verifica que la línea de resultado en el Patrimonio esté clasificada."
        )
        return

    diferencia = abs(er11 - pat04)
    cuadra = diferencia <= TOLERANCIA

    # ── Métricas de cuadre ────────────────────────────────────────────────────
    c1, c2, c3 = st.columns(3)
    c1.metric(
        "Utilidad Neta ER (ER.11)",
        f"${er11:,.0f}",
    )
    c2.metric(
        "Resultado Patrimonio (PAT.04)",
        f"${pat04:,.0f}",
    )
    c3.metric(
        "Diferencia",
        f"${diferencia:,.0f}",
        delta="✅ Cuadra" if cuadra else f"❌ Descuadre de ${diferencia:,.0f}",
        delta_color="normal" if cuadra else "inverse",
    )

    if cuadra:
        st.success(
            f"✅ La utilidad del período cuadra correctamente "
            f"(diferencia ${diferencia:,.0f} dentro de tolerancia $1.000)."
        )
        return

    # ── DESCUADRE: ejecutar los tres diagnósticos ─────────────────────────────
    st.error(
        f"❌ **Descuadre de ${diferencia:,.0f}** entre Utilidad Neta (ER.11) "
        f"y Resultado del Ejercicio (PAT.04). "
        f"Revisa los diagnósticos a continuación para identificar el error."
    )

    tab_a, tab_b, tab_c = st.tabs([
        "A — Detalle del ER",
        "B — Buscar signo cambiado",
        "C — Cuentas excluidas / sin clasificar",
    ])

    # ── DIAGNÓSTICO A: Detalle completo del ER ────────────────────────────────
    with tab_a:
        st.markdown(
            "**Todas las cuentas del Estado de Resultados clasificadas**, "
            "ordenadas de mayor a menor impacto absoluto. "
            "Verifica que cada monto tenga el signo correcto."
        )

        er_codigos = [c for c in agrupado['codigo_clasificado'] if c.startswith('ER')]
        er_df = agrupado[agrupado['codigo_clasificado'].isin(er_codigos)].copy()

        if er_df.empty:
            st.warning("No hay cuentas del ER clasificadas.")
        else:
            er_df = er_df.sort_values('monto_total', key=abs, ascending=False)
            er_df['Signo'] = er_df['monto_total'].apply(
                lambda x: '📈 Positivo' if x > 0 else '📉 Negativo'
            )
            er_df['Impacto en Utilidad'] = er_df.apply(
                lambda r: (
                    '+' if r['monto_total'] > 0 else ''
                ) + f"${r['monto_total']:,.0f}",
                axis=1
            )
            tabla_a = er_df[[
                'codigo_clasificado', 'nombre_estandar',
                'num_cuentas', 'Signo', 'Impacto en Utilidad'
            ]].copy()
            tabla_a.columns = [
                'Código', 'Cuenta Estándar',
                '# Cuentas', 'Signo', 'Impacto en Utilidad'
            ]
            st.dataframe(tabla_a, use_container_width=True, hide_index=True)

            # Mostrar suma del ER manualmente calculada
            suma_er = er_df['monto_total'].sum()
            st.metric(
                "Suma manual del ER (sin ER.11)",
                f"${er_df[er_df['codigo_clasificado'] != 'ER.11']['monto_total'].sum():,.0f}",
                help="Si esta suma ≠ ER.11, hay un error de clasificación en el ER."
            )

            # Detalle de cuentas originales que componen el ER
            with st.expander("Ver cuentas originales que componen el ER"):
                er_orig = clasificadas[
                    clasificadas['codigo_clasificado'].str.startswith('ER', na=False)
                ][['codigo_original', 'nombre_original', 'monto',
                   'codigo_clasificado', 'metodo', 'confianza']].copy()
                er_orig = er_orig.sort_values('monto', key=abs, ascending=False)
                er_orig.columns = [
                    'Cód. Original', 'Nombre Original', 'Monto',
                    'Clasificado Como', 'Método', 'Confianza'
                ]
                er_orig['Monto'] = er_orig['Monto'].apply(
                    lambda x: f"${x:,.0f}" if pd.notna(x) else "—"
                )
                st.dataframe(er_orig, use_container_width=True, hide_index=True)

    # ── DIAGNÓSTICO B: Buscar cuenta con monto = diferencia ──────────────────
    with tab_b:
        st.markdown(
            f"**Buscando cuentas con monto cercano a ${diferencia:,.0f}** "
            f"(la diferencia exacta). Si alguna tiene ese monto pero con signo "
            f"invertido, esa es la causa del descuadre."
        )

        MARGEN_BUSQUEDA = max(diferencia * 0.05, 1_000)  # 5% de margen

        candidatos = clasificadas[
            (clasificadas['monto'].abs() - diferencia).abs() <= MARGEN_BUSQUEDA
        ].copy()

        if candidatos.empty:
            st.info(
                f"No se encontró ninguna cuenta con monto exacto de ${diferencia:,.0f}. "
                "El error puede ser la suma de varias cuentas mal clasificadas, "
                "o una cuenta del ER clasificada en el Balance (o viceversa)."
            )

            # Buscar cuentas del ER clasificadas en balance y viceversa
            st.markdown("**Posibles cuentas mal ubicadas (ER clasificada en Balance o Balance en ER):**")
            cuentas_er_en_balance = clasificadas[
                clasificadas['codigo_clasificado'].str.startswith('AC', na=False) |
                clasificadas['codigo_clasificado'].str.startswith('ANC', na=False) |
                clasificadas['codigo_clasificado'].str.startswith('PC', na=False) |
                clasificadas['codigo_clasificado'].str.startswith('PNC', na=False)
            ]
            # Filtrar por palabras clave que sugieren que deberían ser ER
            keywords_er = ['gasto', 'costo', 'venta', 'ingreso', 'resultado',
                          'utilidad', 'perdida', 'depreciacion', 'interes',
                          'remuneracion', 'honorario']
            mask = cuentas_er_en_balance['nombre_original'].str.lower().apply(
                lambda n: any(k in n for k in keywords_er)
            )
            sospechosas = cuentas_er_en_balance[mask]
            if not sospechosas.empty:
                tabla_sosp = sospechosas[[
                    'nombre_original', 'monto', 'codigo_clasificado'
                ]].copy()
                tabla_sosp.columns = ['Cuenta Original', 'Monto', 'Clasificada Como']
                tabla_sosp['Monto'] = tabla_sosp['Monto'].apply(
                    lambda x: f"${x:,.0f}" if pd.notna(x) else "—"
                )
                st.dataframe(tabla_sosp, use_container_width=True, hide_index=True)
            else:
                st.info("No se detectaron cuentas de resultado mal clasificadas en el balance.")
        else:
            candidatos_display = candidatos[[
                'codigo_original', 'nombre_original', 'monto',
                'codigo_clasificado', 'metodo'
            ]].copy()
            candidatos_display.columns = [
                'Cód. Original', 'Nombre Original', 'Monto',
                'Clasificada Como', 'Método'
            ]
            candidatos_display['Monto'] = candidatos_display['Monto'].apply(
                lambda x: f"${x:,.0f}" if pd.notna(x) else "—"
            )
            candidatos_display['¿Signo invertido?'] = candidatos[
                'monto'
            ].apply(
                lambda x: "⚠️ Posible signo cambiado" if x is not None and (
                    abs(x + diferencia) <= MARGEN_BUSQUEDA or
                    abs(x - diferencia) <= MARGEN_BUSQUEDA
                ) else "Revisar"
            ).values
            st.dataframe(candidatos_display, use_container_width=True, hide_index=True)
            st.warning(
                "Revisa las cuentas marcadas con ⚠️. Si el monto coincide "
                "con la diferencia pero el signo está invertido, esa cuenta "
                "está causando el descuadre."
            )

    # ── DIAGNÓSTICO C: Excluidas y sin clasificar ─────────────────────────────
    with tab_c:
        st.markdown(
            "**Cuentas excluidas o sin clasificar** que podrían pertenecer "
            "al Estado de Resultados y estar causando el descuadre."
        )

        # Excluidas explícitamente
        excluidas = df[df['codigo_clasificado'] == '__EXCLUIR__'].copy()
        keywords_er = ['gasto', 'costo', 'venta', 'ingreso', 'resultado',
                       'utilidad', 'perdida', 'depreciacion', 'interes',
                       'remuneracion', 'honorario', 'impuesto', 'arriendo']

        if not excluidas.empty:
            mask_er = excluidas['nombre_original'].str.lower().apply(
                lambda n: any(k in n for k in keywords_er)
            )
            excluidas_er = excluidas[mask_er]
            if not excluidas_er.empty:
                st.warning(
                    f"⚠️ {len(excluidas_er)} cuenta(s) marcada(s) como **No Incluir** "
                    f"podrían ser del Estado de Resultados:"
                )
                tabla_exc = excluidas_er[['nombre_original', 'monto', 'origen_columna']].copy()
                tabla_exc.columns = ['Cuenta', 'Monto', 'Columna Origen']
                tabla_exc['Monto'] = tabla_exc['Monto'].apply(
                    lambda x: f"${x:,.0f}" if pd.notna(x) else "—"
                )
                st.dataframe(tabla_exc, use_container_width=True, hide_index=True)
                st.caption(
                    "Si alguna de estas cuentas debería estar en el ER, "
                    "ve a la Cola de Revisión y cámbiala de 'No Incluir' "
                    "a la categoría correcta."
                )

        # Sin clasificar
        sin_clas = df[df['codigo_clasificado'] == ''].copy()
        if not sin_clas.empty:
            mask_er2 = sin_clas['nombre_original'].str.lower().apply(
                lambda n: any(k in n for k in keywords_er)
            )
            sin_clas_er = sin_clas[mask_er2]
            if not sin_clas_er.empty:
                st.warning(
                    f"⚠️ {len(sin_clas_er)} cuenta(s) **sin clasificar** "
                    f"podrían ser del Estado de Resultados:"
                )
                tabla_sc = sin_clas_er[[
                    'nombre_original', 'monto', 'origen_columna'
                ]].copy()
                tabla_sc.columns = ['Cuenta', 'Monto', 'Columna Origen']
                tabla_sc['Monto'] = tabla_sc['Monto'].apply(
                    lambda x: f"${x:,.0f}" if pd.notna(x) else "—"
                )
                st.dataframe(tabla_sc, use_container_width=True, hide_index=True)
                st.caption(
                    "Clasifica estas cuentas en la Cola de Revisión "
                    "para que sean incluidas en el cálculo."
                )

        if excluidas.empty and sin_clas.empty:
            st.info(
                "No hay cuentas excluidas ni sin clasificar. "
                "El descuadre probablemente se debe a un signo cambiado "
                "en alguna cuenta del ER (ver Diagnóstico B)."
            )

    st.divider()


def _tab_diccionario():
    busqueda = st.text_input("Buscar en el diccionario", "")
    catalogo_local = cargar_catalogo()
    dic = st.session_state.diccionario
    df_dic = pd.DataFrame(dic)
    # Agregar nombre estándar desde el catálogo
    df_dic['nombre_estandar'] = df_dic['codigo_estandar'].map(
        lambda c: catalogo_local.get(c, {}).get('nombre_estandar', '') if c else ''
    )
    df_dic['codigo_y_nombre'] = df_dic.apply(
        lambda r: f"{r['codigo_estandar']} — {r['nombre_estandar']}" if r['nombre_estandar']
        else r['codigo_estandar'], axis=1
    )
    if busqueda:
        mask = (
            df_dic['cuenta_original'].str.contains(busqueda, case=False, na=False) |
            df_dic['nombre_estandar'].str.contains(busqueda, case=False, na=False) |
            df_dic['codigo_estandar'].str.contains(busqueda, case=False, na=False)
        )
        df_dic = df_dic[mask]
    st.caption(f"{len(df_dic)} entradas encontradas")
    st.dataframe(
        df_dic[['cuenta_original', 'codigo_y_nombre', 'fuente']].rename(columns={
            'cuenta_original': 'Cuenta Original',
            'codigo_y_nombre': 'Código — Nombre Estándar',
            'fuente': 'Fuente'
        }),
        use_container_width=True, hide_index=True, height=500
    )


def _mostrar_resumen_catalogo(catalogo: dict):
    st.subheader("Catálogo Maestro de Homologación")
    df = pd.DataFrame.from_dict(catalogo, orient='index')
    df = df[['codigo_estandar', 'nombre_estandar', 'categoria', 'tipo_estado']]
    df.columns = ['Código', 'Nombre Estándar', 'Categoría', 'Tipo Estado']
    st.dataframe(df, use_container_width=True, hide_index=True)


if __name__ == '__main__':
    main()
