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
# REGLAS REGEX (patrones de mayor cobertura)
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
    nombre_norm = normalizar_nombre(nombre_original)
    if 'resultados' in st.session_state and isinstance(st.session_state.resultados, dict):
        propagaciones = 0
        for fn in list(st.session_state.resultados.keys()):
            df_res = st.session_state.resultados[fn].copy()
            names = df_res['nombre_original'].fillna('').apply(normalizar_nombre)
            mask = names == nombre_norm
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
# MOTOR DE CLASIFICACIÓN HÍBRIDA
# ─────────────────────────────────────────────────────────────────────────────

class MotorHibridoLocal:
    UMBRAL_CODIGO = 0.85
    NOMBRES_AMBIGUOS = {'arriendos', 'arriendo', 'intereses', 'interes', 'honorarios', 'comisiones', 'servicios'}
    UMBRAL_DICCIONARIO_EXACTO = 0.98
    UMBRAL_DICCIONARIO_FUZZY = 0.85
    UMBRAL_REGLA = 0.80

    def __init__(self, diccionario: list[dict]):
        self.clasificador_codigo = ClasificadorCodigo()
        self.reglas_especiales = ProcesadorReglasEspeciales()
        self.dic_exacto = {normalizar_nombre(d['cuenta_original']): d for d in diccionario}
        self.dic_lista = list(self.dic_exacto.keys())

    def clasificar(self, cuenta: CuentaRaw, giro_empresa: str | None = None) -> dict:
        nombre_norm = normalizar_nombre(cuenta.nombre)

        if (cuenta.origen_columna != OrigenColumna.DESCONOCIDO and nombre_norm in self.NOMBRES_AMBIGUOS):
            col = cuenta.origen_columna
            es_ing = col in (OrigenColumna.GANANCIA, OrigenColumna.ACTIVO)
            es_gas = col in (OrigenColumna.PERDIDA,  OrigenColumna.PASIVO)
            MAPA_AMBIGUO = {
                'arriendos': ('ER.01', 'ER.04'), 'arriendo':  ('ER.01', 'ER.04'),
                'intereses': ('ER.12', 'ER.09'), 'interes':   ('ER.12', 'ER.09'),
                'honorarios':('ER.01', 'ER.04'), 'honorario': ('ER.01', 'ER.04'),
                'comisiones':('ER.01', 'ER.05'), 'servicios': ('ER.01', 'ER.04'),
            }
            if nombre_norm in MAPA_AMBIGUO:
                cod_ing, cod_gas = MAPA_AMBIGUO[nombre_norm]
                if es_ing:
                    return {'codigo_estandar': cod_ing, 'metodo': 'columna_ambiguo', 'confianza': 0.88, 'requiere_revision': False}
                if es_gas:
                    return {'codigo_estandar': cod_gas, 'metodo': 'columna_ambiguo', 'confianza': 0.88, 'requiere_revision': False}

        r_codigo = self.clasificador_codigo.clasificar(cuenta.codigo)
        if r_codigo and r_codigo.confianza >= self.UMBRAL_CODIGO:
            resultado = {'codigo_estandar': r_codigo.codigo_estandar, 'metodo': 'codigo', 'confianza': r_codigo.confianza}
        else:
            if nombre_norm in self.dic_exacto:
                d = self.dic_exacto[nombre_norm]
                resultado = {'codigo_estandar': d['codigo_estandar'], 'metodo': 'diccionario_exacto', 'confianza': self.UMBRAL_DICCIONARIO_EXACTO}
            else:
                match = process.extractOne(nombre_norm, self.dic_lista, scorer=fuzz.token_sort_ratio)
                if match and match[1] >= 90:
                    d = self.dic_exacto[match[0]]
                    resultado = {'codigo_estandar': d['codigo_estandar'], 'metodo': 'diccionario_fuzzy', 'confianza': round(0.80 + (match[1] - 90) * 0.01, 3)}
                else:
                    mejor = None
                    for patron, cod, conf in REGLAS_COMPILADAS:
                        if patron.search(nombre_norm):
                            if mejor is None or conf > mejor[1]:
                                mejor = (cod, conf)
                    if mejor:
                        resultado = {'codigo_estandar': mejor[0], 'metodo': 'regla_regex', 'confianza': mejor[1]}
                    else:
                        resultado = {'codigo_estandar': None, 'metodo': 'sin_clasificar', 'confianza': 0.0}

        codigo_actual = resultado.get('codigo_estandar')
        origen = cuenta.origen_columna
        if origen != OrigenColumna.DESCONOCIDO and codigo_actual:
            codigo_corregido = self._corregir_por_columna(nombre_norm, codigo_actual, origen, cuenta.monto)
            if codigo_corregido and codigo_corregido != codigo_actual:
                resultado['codigo_estandar'] = codigo_corregido
                resultado['metodo'] += '+columna'
                resultado['confianza'] = min(resultado['confianza'] + 0.05, 0.99)

        codigo_pre = resultado['codigo_estandar'] or 'AC.08'
        ajuste = self.reglas_especiales.aplicar(cuenta.nombre, codigo_pre, cuenta.monto, giro_empresa)
        if ajuste.aplica:
            resultado['codigo_estandar'] = ajuste.codigo_final
            resultado['metodo'] += f'+regla_especial({ajuste.flag})'
            resultado['nota_regla_especial'] = ajuste.nota

        resultado['requiere_revision'] = resultado['confianza'] < UMBRAL_REVISION
        return resultado

    def _corregir_por_columna(self, nombre_norm, codigo_actual, origen, monto):
        from parser_universal import OrigenColumna as OC
        es_ingreso = origen in (OC.GANANCIA, OC.ACTIVO)
        es_gasto   = origen in (OC.PERDIDA,  OC.PASIVO)

        AMBIGUOS = [
            ('arriendo', 'ER.01', 'ER.04'), ('interes', 'ER.12', 'ER.09'),
            ('comision', 'ER.01', 'ER.05'), ('servicio', 'ER.01', 'ER.04'),
            ('honorario', 'ER.01', 'ER.04'), ('diferencia de cambio', 'ER.15', 'ER.15'),
            ('correccion monetaria', 'ER.14', 'ER.14'), ('otras ganancias', 'ER.13', 'ER.13'),
            ('reajuste', 'ER.14', 'ER.14'),
        ]

        if (monto is not None and monto < 0 and origen == OC.ACTIVO and codigo_actual in ('AC.01',)
                and any(k in nombre_norm for k in ('banco','cta cte','cuenta corriente'))):
            return 'PC.02'

        for keyword, cod_ing, cod_gas in AMBIGUOS:
            if keyword in nombre_norm:
                if es_ingreso and codigo_actual not in (cod_ing, cod_gas): return cod_ing
                if es_gasto and codigo_actual not in (cod_ing, cod_gas): return cod_gas

        if origen in (OC.ACTIVO, OC.PASIVO) and codigo_actual and codigo_actual.startswith('ER'):
            return None

        return None


def parsear_excel(file) -> list[CuentaRaw]:
    df = pd.read_excel(file, header=None)
    cuentas = []
    for i, row in df.iterrows():
        vals = [v for v in row.tolist() if pd.notna(v)]
        if not vals: continue
        textos = [v for v in vals if isinstance(v, str)]
        numeros = [v for v in vals if isinstance(v, (int, float))]
        if not textos: continue
        nombre = max(textos, key=len)
        if len(nombre) < 3: continue
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
# INTERFAZ DE USUARIO PRINCIPAL (MAIN)
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

    with st.sidebar:
        st.header("⚙️ Configuración")
        archivos = st.file_uploader(
            "Balances tributarios", type=['pdf', 'xlsx', 'xls'], accept_multiple_files=True
        )
        giro = st.selectbox(
            "Giro de la empresa (afecta regla D2-Terrenos)",
            ['Otro', 'Inmobiliaria', 'Construcción', 'Promotora'],
            help="Si el giro es inmobiliario/construcción, los terrenos en activo corriente se reclasifican como inventario."
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
                    giro_list, index=default_giro_idx
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

    nombres_subidos = [a.name for a in archivos]
    for k in list(st.session_state.resultados.keys()):
        if k not in nombres_subidos:
            st.session_state.resultados.pop(k, None)
            st.session_state.metadata_files.pop(k, None)

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
                    if c.monto is None and not c.codigo: continue
                    if not c.codigo and PATRON_NO_CUENTA.match(c.nombre.strip()): continue
                    r = motor.clasificar(c, company_giro_norm)
                    filas.append({
                        'linea': c.linea, 'codigo_original': c.codigo or '', 'nombre_original': c.nombre,
                        'monto': c.monto, 'origen_columna': c.origen_columna.value, 'es_total': c.es_total,
                        'codigo_clasificado': r['codigo_estandar'] or '', 'metodo': r['metodo'],
                        'confianza': r['confianza'], 'requiere_revision': r['requiere_revision'],
                        'nota': r.get('nota_regla_especial', ''), 'confianza_extraccion': c.confianza_extraccion,
                        'origen_columna_display': c.origen_columna.value,
                    })
                df_file = pd.DataFrame(filas)
                st.session_state.resultados[archivo.name] = df_file

    if 'propagation_done' not in st.session_state:
        def propagar_entre_balances():
            name_map = {}
            resultados = getattr(st.session_state, "resultados", {})
            for fname, df in resultados.items():
                for idx, row in df.iterrows():
                    nombre = row['nombre_original']
                    if not nombre: continue
                    norm = normalizar_nombre(nombre)
                    name_map.setdefault(norm, []).append((fname, idx, row['codigo_clasificado']))
            
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

    with st.sidebar:
        st.divider()
        st.subheader("📁 Balances Cargados")
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
            "Ver y validar balance:", options=nombres_subidos,
            index=0 if nombres_subidos else None, key="archivo_activo_select"
        )

    try:
        archivo_activo = next(a for a in archivos if a.name == archivo_activo_name)
        df = st.session_state.resultados[archivo_activo_name]
        meta_activo = st.session_state.metadata_files.get(archivo_activo_name)
    except (NameError, Exception):
        class DummyDF: empty = False
        df = DummyDF()
        archivo_activo_name = ""
        archivo_activo = None
        meta_activo = None

    if df.empty:
        st.warning(f"No se extrajeron cuentas del archivo {archivo_activo_name}.")
        st.stop()

    with st.container(border=True):
        c1, c2, c3, c4 = st.columns(4)
        razon_social = getattr(st.session_state, "company_razon", "—")
        rut_empresa = getattr(st.session_state, "company_rut", "—")
        c1.markdown(f"**{razon_social or '—'}** \n`{rut_empresa or '—'}`")
        periodo_str = "—"
        if meta_activo:
            periodo_str = f"{meta_activo.periodo_desde or '—'} → {meta_activo.periodo_hasta or '—'}"
        c2.markdown(f"**Período del Balance** \n{periodo_str}")
        giro_empresa = getattr(st.session_state, "company_giro", "—")
        c3.markdown(f"**Giro** \n{giro_empresa or '—'}")
        c4.markdown(f"**Archivo Activo** \n`{archivo_activo_name}`")

    col_visor, col_trabajo = st.columns([1, 1], gap="medium")

    with col_visor:
        try:
            _visor_documento(archivo_activo)
        except (NameError, Exception):
            pass

    with col_trabajo:
        tab_resumen, tab_revision, tab_balance, tab_diccionario = st.tabs(
            ["📈 Resumen", "🔍 Cola de Revisión", "📋 Balance Normalizado", "📚 Diccionario"]
        )

        with tab_resumen: _tab_resumen(df)
        with tab_revision: _tab_revision(df, catalogo, motor=MotorHibridoLocal(st.session_state.diccionario), archivo_nombre=archivo_activo_name)
        with tab_balance: _tab_balance(df, catalogo)
        with tab_diccionario: _tab_diccionario()


# ─────────────────────────────────────────────────────────────────────────────
# FUNCIONES AUXILIARES DE INTERFAZ Y PROCESAMIENTO
# ─────────────────────────────────────────────────────────────────────────────

def _visor_documento(archivo):
    import tempfile, base64, io, platform, shutil, subprocess, glob
    from PIL import Image
    from pathlib import Path

    suffix = Path(archivo.name).suffix.lower()
    archivo.seek(0)
    st.markdown("#### 📄 Documento original")

    if suffix == '.pdf':
        clave_imgs = f"_imgs_{archivo.name}"
        if clave_imgs not in st.session_state:
            with st.spinner("Cargando páginas del documento..."):
                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                    tmp.write(archivo.read())
                    tmp_path = Path(tmp.name)
                archivo.seek(0)
                
                try:
                    from pdf2image import convert_from_path
                    
                    # CORRECCIÓN 1: Configuración inteligente según el sistema operativo
                    if platform.system() == "Darwin":
                        # Entorno local (Mac)
                        pdftoppm_path = shutil.which('pdftoppm')
                        poppler_dir = str(Path(pdftoppm_path).parent) if pdftoppm_path else '/opt/homebrew/bin'
                        imgs = convert_from_path(str(tmp_path), dpi=180, poppler_path=poppler_dir)
                    else:
                        # Entorno Render (Linux) - No necesita poppler_path, lo detecta global
                        imgs = convert_from_path(str(tmp_path), dpi=180)
                        
                    st.session_state[clave_imgs] = imgs
                except Exception:
                    # CORRECCIÓN 2: Fallback dinámico (busca pdftoppm de forma segura en cualquier Linux)
                    pdftoppm_bin = shutil.which('pdftoppm') or 'pdftoppm'
                    tmpdir = tempfile.mkdtemp()
                    subprocess.run([pdftoppm_bin, '-png', '-r', '180', str(tmp_path), f'{tmpdir}/page'], capture_output=True)
                    img_files = sorted(glob.glob(f'{tmpdir}/page*.png'))
                    imgs = [Image.open(f) for f in img_files]
                    st.session_state[clave_imgs] = imgs

        imgs = st.session_state.get(clave_imgs, [])
        n_paginas = len(imgs)
        if not imgs:
            st.warning("No se pudo renderizar el documento.")
            return

        ctrl1, ctrl2, ctrl3 = st.columns([2, 2, 2])
        with ctrl1: pagina = st.number_input(f"Página (1-{n_paginas})", min_value=1, max_value=n_paginas, value=1, step=1, key="visor_pagina")
        with ctrl2: zoom = st.slider("Zoom", min_value=50, max_value=200, value=100, step=10, format="%d%%", key="visor_zoom")
        with ctrl3: rotacion = st.select_slider("Rotación", options=[0, 90, 180, 270], value=0, format_func=lambda x: f"{x}°", key="visor_rot")

        img = imgs[pagina - 1]
        if rotacion != 0: img = img.rotate(-rotacion, expand=True)
        if zoom != 100:
            w, h = img.size
            img = img.resize((int(w * zoom / 100), int(h * zoom / 100)), Image.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, format='PNG')
        b64 = base64.b64encode(buf.getvalue()).decode()

        html_visor = f"""
        <div style="height: 72vh; overflow-y: auto; overflow-x: auto; border: 1px solid #d0d0d0; border-radius: 8px; background: #f5f5f5; padding: 8px; text-align: center;">
            <img src="data:image/png;base64,{b64}" style="max-width: none; cursor: zoom-in;" title="Página {pagina} de {n_paginas} — {archivo.name}"/>
        </div>
        <div style="font-size:12px; color:#888; text-align:center; margin-top:4px;">Página {pagina} de {n_paginas} · {archivo.name}</div>
        """
        st.html(html_visor)

    elif suffix in ('.xlsx', '.xls'):
        archivo.seek(0)
        try:
            df_raw = pd.read_excel(archivo, header=None, dtype=str).fillna('')
            html_tabla = df_raw.to_html(index=False, header=False, border=0, classes='excel-visor')
            html_visor = f"""
            <style>
                .excel-visor td {{ padding: 3px 8px; border-bottom: 1px solid #eee; font-size: 12px; white-space: nowrap; font-family: monospace; }}
                .excel-visor tr:nth-child(even) {{ background: #f9f9f9; }}
            </style>
            <div style="height: 72vh; overflow-y: auto; overflow-x: auto; border: 1px solid #d0d0d0; border-radius: 8px; background: white; padding: 8px;">{html_tabla}</div>
            <div style="font-size:12px; color:#888; text-align:center; margin-top:4px;">{archivo.name}</div>
            """
            st.html(html_visor)
        except Exception as e:
            st.error(f"No se pudo mostrar el Excel: {e}")
        finally:
            archivo.seek(0)


def _extraer_lineas_encabezado(archivo) -> list[str]:
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
        archivo.seek(0)
        df = pd.read_excel(archivo, header=None, nrows=15).fillna('')
        archivo.seek(0)
        lineas = []
        for _, row in df.iterrows():
            vals = [str(v) for v in row if str(v) not in ('nan', 'None', '')]
            if vals: lineas.append(' '.join(vals))
        return lineas


def _extraer_cuentas(archivo) -> list[CuentaRaw]:
    suffix = Path(archivo.name).suffix.lower()
    if suffix == '.pdf':
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            tmp.write(archivo.read())
            tmp_path = Path(tmp.name)
        parser = ParserPDF()
        resultado = parser.parsear(tmp_path)
        for adv in resultado.advertencias: st.warning(adv)
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
    col2.metric("Sin clasificar", sin_clasificar)
    col3.metric("En cola de revisión", int(requiere_rev), delta=f"{100*requiere_rev/total:.0f}%" if total else None, delta_color="inverse")
    col4.metric("Confianza promedio", f"{confianza_prom:.0%}" if pd.notna(confianza_prom) else "—")

    st.subheader("Cobertura por método de clasificación")
    dist = df['metodo'].apply(lambda m: m.split('+')[0]).value_counts()
    dist_df = dist.reset_index()
    dist_df.columns = ['Método', 'Cuentas']
    
    METODO_LABELS = {
        'codigo': '0 · Código de cuenta', 'diccionario_exacto': '1 · Diccionario (exacto)',
        'diccionario_fuzzy': '1b · Diccionario (fuzzy)', 'regla_regex': '2 · Reglas regex',
        'sin_clasificar': '3-4 · Pendiente (embeddings/LLM)',
    }
    dist_df['Método'] = dist_df['Método'].map(lambda m: METODO_LABELS.get(m, m))
    st.dataframe(dist_df, use_container_width=True, hide_index=True)


def _tab_revision(df: pd.DataFrame, catalogo: dict, motor: MotorHibridoLocal, archivo_nombre: str):
    pendientes = df[df['requiere_revision'] | (df['codigo_clasificado'] == '')]
    pendientes = pendientes[~pendientes['es_total']]

    if pendientes.empty:
        st.success("✅ No hay cuentas pendientes de revisión.")
        return

    opciones_codigo = [''] + sorted(catalogo.keys()) + ['➕ NUEVA CATEGORÍA', '🚫 NO INCLUIR']

    if 'lote_seleccion' not in st.session_state:
        st.session_state.lote_seleccion = set()

    n_sel = len(st.session_state.lote_seleccion)
    with st.container(border=True):
        st.markdown(f"#### 📦 Asignación en lote — {n_sel} cuenta(s) seleccionada(s)")
        bc1, bc2, bc3 = st.columns([3, 2, 1])
        with bc1:
            cat_lote = st.selectbox(
                "Clasificar todas las seleccionadas como:", opciones_codigo,
                format_func=lambda c: f"{c} — {catalogo[c]['nombre_estandar']}" if c in catalogo else c if c else "(elegir categoría)",
                key="lote_categoria"
            )
        with bc2:
            alcance_lote = st.radio("Alcance", ["Solo este caso", "Agregar al diccionario"], index=1, horizontal=True, key="lote_alcance")
        with bc3:
            st.write(""); st.write("")
            confirmar_lote = st.button(f"✅ Confirmar lote ({n_sel})", disabled=(n_sel == 0 or not cat_lote), use_container_width=True)

        if confirmar_lote and n_sel > 0 and cat_lote:
            codigo_lote = '__EXCLUIR__' if cat_lote == '🚫 NO INCLUIR' else (cat_lote if cat_lote != '➕ NUEVA CATEGORÍA' else None)
            if codigo_lote:
                procesados = 0
                for idx_lote in list(st.session_state.lote_seleccion):
                    nombre_orig = df.at[idx_lote, 'nombre_original']
                    st.session_state.resultados[archivo_nombre].at[idx_lote, 'codigo_clasificado'] = codigo_lote
                    st.session_state.resultados[archivo_nombre].at[idx_lote, 'metodo'] = 'validacion_humana_lote'
                    st.session_state.resultados[archivo_nombre].at[idx_lote, 'confianza'] = 1.0
                    st.session_state.resultados[archivo_nombre].at[idx_lote, 'requiere_revision'] = False
                    if "diccionario" in alcance_lote:
                        entrada = {'cuenta_original': nombre_orig, 'codigo_estandar': codigo_lote, 'fuente': 'validacion_humana_lote'}
                        st.session_state.diccionario.append(entrada)
                        st.session_state.correcciones.append(entrada)
                    propagar_clasificacion_resultados(nombre_orig, codigo_lote, 'validacion_humana_lote_propagada')
                    procesados += 1
                if "diccionario" in alcance_lote:
                    with open(BASE_DIR / 'diccionario.json', 'w', encoding='utf-8') as f:
                        json.dump(st.session_state.diccionario, f, ensure_ascii=False, indent=2)
                st.session_state.lote_seleccion = set()
                st.rerun()

        qa, qb, qc = st.columns(3)
        if qa.button("☑️ Seleccionar todas", use_container_width=True):
            st.session_state.lote_seleccion = set(pendientes.index.tolist()); st.rerun()
        if qb.button("🟦 Seleccionar sin clasificar", use_container_width=True):
            st.session_state.lote_seleccion = set(pendientes[pendientes['codigo_clasificado'] == ''].index.tolist()); st.rerun()
        if qc.button("⬜ Limpiar selección", use_container_width=True):
            st.session_state.lote_seleccion = set(); st.rerun()

    for idx, row in pendientes.iterrows():
        seleccionada = idx in st.session_state.lote_seleccion
        with st.container(border=seleccionada):
            c0, c1, c2, c3 = st.columns([0.4, 3, 2, 3])
            with c0:
                marcado = st.checkbox("", value=seleccionada, key=f"chk_{idx}", label_visibility="collapsed")
                if marcado and idx not in st.session_state.lote_seleccion:
                    st.session_state.lote_seleccion.add(idx); st.rerun()
                elif not marcado and idx in st.session_state.lote_seleccion:
                    st.session_state.lote_seleccion.discard(idx); st.rerun()

            with c1:
                st.markdown(f"**{row['nombre_original']}**")
                monto_str = f"{row['monto']:,.0f}" if pd.notna(row['monto']) else "—"
                st.caption(f"Código: `{row['codigo_original'] or '—'}` · Monto: **{monto_str}**")

            with c2:
                sugerido = row['codigo_clasificado']
                st.write(f"Sugerido: **{sugerido or '(ninguno)'}**")

            with c3:
                default_idx = opciones_codigo.index(sugerido) if sugerido in opciones_codigo else 0
                seleccion = st.selectbox("Clasificación correcta", opciones_codigo, index=default_idx,
                                         format_func=lambda c: f"{c} — {catalogo[c]['nombre_estandar']}" if c in catalogo else c, key=f"sel_{idx}")
                
                alcance = st.radio("¿Aplicar?", ["Solo este caso", "Agregar al diccionario"], index=1, key=f"alc_{idx}", horizontal=True)
                if st.button("Confirmar", key=f"btn_{idx}"):
                    st.session_state.resultados[archivo_nombre].at[idx, 'codigo_clasificado'] = seleccion
                    st.session_state.resultados[archivo_nombre].at[idx, 'requiere_revision'] = False
                    if "diccionario" in alcance and seleccion not in ('', '🚫 NO INCLUIR'):
                        st.session_state.diccionario.append({'cuenta_original': row['nombre_original'], 'codigo_estandar': seleccion, 'fuente': 'manual'})
                        with open(BASE_DIR / 'diccionario.json', 'w', encoding='utf-8') as f:
                            json.dump(st.session_state.diccionario, f, ensure_ascii=False, indent=2)
                    st.session_state.lote_seleccion.discard(idx)
                    st.rerun()


def _tab_balance(df: pd.DataFrame, catalogo: dict):
    clasificadas = df[(df['codigo_clasificado'] != '') & (df['codigo_clasificado'] != '__EXCLUIR__') & (~df['es_total'])].copy()
    if clasificadas.empty:
        st.info("No hay cuentas clasificadas todavía.")
        return

    clasificadas['monto'] = clasificadas['monto'].fillna(0)
    agrupado = clasificadas.groupby('codigo_clasificado').agg(monto_total=('monto', 'sum'), num_cuentas=('nombre_original', 'count')).reset_index()
    agrupado['nombre_estandar'] = agrupado['codigo_clasificado'].map(lambda c: catalogo.get(c, {}).get('nombre_estandar', c))
    agrupado['categoria'] = agrupado['codigo_clasificado'].map(lambda c: catalogo.get(c, {}).get('categoria', ''))

    orden_cat = ['activo_corriente', 'activo_no_corriente', 'pasivo_corriente', 'pasivo_no_corriente', 'patrimonio', 'resultado']
    agrupado['orden'] = agrupado['categoria'].map(lambda c: orden_cat.index(c) if c in orden_cat else 99)
    agrupado = agrupado.sort_values(['orden', 'codigo_clasificado'])

    LABELS_CAT = {
        'activo_corriente': '🟦 Activo Corriente', 'activo_no_corriente': '🟦 Activo No Corriente',
        'pasivo_corriente': '🟥 Pasivo Corriente', 'pasivo_no_corriente': '🟥 Pasivo No Corriente',
        'patrimonio': '🟩 Patrimonio', 'resultado': '🟨 Estado de Resultados'
    }

    for cat in orden_cat:
        sub = agrupado[agrupado['categoria'] == cat]
        if sub.empty: continue
        st.subheader(LABELS_CAT.get(cat, cat))
        tabla = sub[['codigo_clasificado', 'nombre_estandar', 'monto_total', 'num_cuentas']].copy()
        tabla.columns = ['Código', 'Cuenta Estándar', 'Monto Total', '# Cuentas Agrupadas']
        tabla['Monto Total'] = tabla['Monto Total'].map(lambda x: f"{x:,.0f}")
        st.dataframe(tabla, use_container_width=True, hide_index=True)
        st.metric(f"Subtotal", f"{sub['monto_total'].sum():,.0f}")
        st.divider()

    # Ajuste Patrimonio Efectivo
    pat = agrupado[agrupado['categoria'] == 'patrimonio']
    ac06s = agrupado[agrupado['codigo_clasificado'] == 'AC.06S']
    if not pat.empty:
        monto_ac06s = ac06s['monto_total'].sum() if not ac06s.empty else 0.0
        ajuste = calcular_patrimonio_efectivo(dict(zip(pat['codigo_clasificado'], pat['monto_total'])), monto_ac06s)
        st.subheader("🎯 Patrimonio Efectivo")
        colp1, colp2, colp3 = st.columns(3)
        colp1.metric("Patrimonio contable", f"{ajuste['patrimonio_contable']:,.0f}")
        colp2.metric("Ajuste cta. socios", f"-{ajuste['ajuste_cta_socios']:,.0f}")
        colp3.metric("Patrimonio efectivo", f"{ajuste['patrimonio_efectivo']:,.0f}")

    # Detalle Excel Exporter
    import io
    from openpyxl.styles import Font, PatternFill
    
    export_df = agrupado[["codigo_clasificado", "nombre_estandar", "monto_total", "num_cuentas"]].copy()
    export_df.columns = ["Código", "Cuenta Estándar", "Monto Total (M$)", "# Cuentas Agrupadas"]
    export_df["Monto Total (M$)"] = export_df["Monto Total (M$)"].round(0).astype(int)
    
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        FILA_INICIO_BALANCE = 7
        export_df.to_excel(writer, index=False, sheet_name="Balance Normalizado", startrow=FILA_INICIO_BALANCE - 1)
        ws = writer.sheets["Balance Normalizado"]

        meta = st.session_state.get("metadata")
        if meta:
            ws["A1"] = "Empresa:";    ws["B1"] = meta.razon_social or ""
            ws["A2"] = "RUT:";       ws["B2"] = meta.rut or ""
            ws["A3"] = "Período:";   ws["B3"] = f'{meta.periodo_desde or ""} al {meta.periodo_hasta or ""}'
            ws["A4"] = "Giro:";      ws["B4"] = meta.giro or ""

        ws.column_dimensions["A"].width = 12
        ws.column_dimensions["B"].width = 36
        ws.column_dimensions["C"].width = 22
        ws.column_dimensions["D"].width = 20

        AZUL = "1F4E79"; BLANCO = "FFFFFF"; GRIS = "F2F2F2"
        header_fill = PatternFill("solid", fgColor=AZUL)
        header_font = Font(bold=True, color=BLANCO, size=11)
        for cell in ws[FILA_INICIO_BALANCE]:
            cell.fill = header_fill
            cell.font = header_font

        for i, row in enumerate(ws.iter_rows(min_row=FILA_INICIO_BALANCE + 1, max_row=FILA_INICIO_BALANCE + len(export_df), max_col=4), start=0):
            if i % 2 == 0:
                for cell in row: cell.fill = PatternFill("solid", fgColor=GRIS)

        fila_sep = FILA_INICIO_BALANCE + len(export_df) + 3

        catalogo_local = cargar_catalogo()
        det = clasificadas[
            (clasificadas['codigo_clasificado'] != '') &
            (clasificadas['codigo_clasificado'] != '__EXCLUIR__') &
            (~clasificadas['es_total'])
        ][['codigo_clasificado', 'codigo_original', 'nombre_original', 'monto', 'metodo', 'confianza']].copy()

        det['nombre_estandar'] = det['codigo_clasificado'].map(lambda c: catalogo_local.get(c, {}).get('nombre_estandar', c))
        detalle_completo = det[['codigo_clasificado', 'nombre_estandar', 'codigo_original', 'nombre_original', 'monto', 'metodo', 'confianza']].copy()

        # Reconstrucción de la lógica de ordenamiento nativo
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

        ws.cell(row=fila_sep, column=1, value="APERTURA DE CUENTAS — DETALLE COMPLETO")
        title_cell = ws.cell(row=fila_sep, column=1)
        title_cell.font = Font(bold=True, size=12, color=AZUL)

        detalle_completo.to_excel(
            writer, index=False,
            sheet_name="Balance Normalizado",
            startrow=fila_sep
        )

        header_row_ap = fila_sep + 1
        naranja = "E26B0A"
        for cell in ws[header_row_ap]:
            cell.fill = PatternFill("solid", fgColor=naranja)
            cell.font = Font(bold=True, color=BLANCO, size=10)

        ws.column_dimensions["E"].width = 18
        ws.column_dimensions["F"].width = 22
        ws.column_dimensions["G"].width = 12

    buf.seek(0)
    
    meta_state = st.session_state.get("metadata")
    razon_fn = (meta_state.razon_social or "empresa").replace(" ", "_")[:30] if meta_state else "empresa"
    rut_fn   = (meta_state.rut or "").replace(".", "").replace("-", "") if meta_state else ""
    nombre_archivo = f"Balance_Unificado-{razon_fn}-{rut_fn}"

    st.download_button(
        "⬇️ Descargar balance normalizado (Excel)", data=buf.getvalue(),
        file_name=f"{nombre_archivo}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    _validar_cuadre_utilidad(df, agrupado, clasificadas)


def _validar_cuadre_utilidad(df: pd.DataFrame, agrupado: pd.DataFrame, clasificadas: pd.DataFrame):
    TOLERANCIA = 1_000
    er11_row = agrupado[agrupado['codigo_clasificado'] == 'ER.11']
    pat04_row = agrupado[agrupado['codigo_clasificado'] == 'PAT.04']

    er11 = er11_row['monto_total'].sum() if not er11_row.empty else None
    pat04 = pat04_row['monto_total'].sum() if not pat04_row.empty else None

    st.subheader("🔍 Validación: Cuadre Utilidad del Ejercicio")

    if er11 is None and pat04 is None:
        st.warning("No se encontraron cuentas clasificadas como ER.11 ni PAT.04.")
        return
    if er11 is None:
        st.warning(f"⚠️ No hay cuentas de ER.11. PAT.04 = **${pat04:,.0f}**.")
        return
    if pat04 is None:
        st.warning(f"⚠️ No hay cuentas de PAT.04. ER.11 = **${er11:,.0f}**.")
        return

    diferencia = abs(er11 - pat04)
    cuadra = diferencia <= TOLERANCIA

    c1, c2, c3 = st.columns(3)
    c1.metric("Utilidad Neta ER (ER.11)", f"${er11:,.0f}")
    c2.metric("Resultado Patrimonio (PAT.04)", f"${pat04:,.0f}")
    c3.metric("Diferencia", f"${diferencia:,.0f}", delta="✅ Cuadra" if cuadra else f"❌ Descuadre", delta_color="normal" if cuadra else "inverse")

    if cuadra:
        st.success("✅ La utilidad del período cuadra correctamente.")
        return

    st.error(f"❌ Descuadre detectado de ${diferencia:,.0f}. Ejecutando diagnósticos avanzados...")
    tab_a, tab_b, tab_c = st.tabs(["A — Detalle del ER", "B — Buscar signo cambiado", "C — Cuentas excluidas / sin clasificar"])

    with tab_a:
        er_codigos = [c for c in agrupado['codigo_clasificado'] if c.startswith('ER')]
        er_df = agrupado[agrupado['codigo_clasificado'].isin(er_codigos)].copy()
        if not er_df.empty:
            er_df = er_df.sort_values('monto_total', key=abs, ascending=False)
            st.dataframe(er_df[['codigo_clasificado', 'nombre_estandar', 'monto_total']], use_container_width=True, hide_index=True)

    with tab_b:
        MARGEN_BUSQUEDA = max(diferencia * 0.05, 1_000)
        candidatos = clasificadas[(clasificadas['monto'].abs() - diferencia).abs() <= MARGEN_BUSQUEDA].copy()
        if not candidatos.empty:
            st.dataframe(candidatos[['nombre_original', 'monto', 'codigo_clasificado']], use_container_width=True, hide_index=True)
        else:
            st.info("No se hallaron cuentas directas con el monto de la diferencia.")

    with tab_c:
        excluidas = df[df['codigo_clasificado'] == '__EXCLUIR__'].copy()
        if not excluidas.empty:
            st.dataframe(excluidas[['nombre_original', 'monto']], use_container_width=True, hide_index=True)


def _tab_diccionario():
    busqueda = st.text_input("Buscar en el diccionario", "")
    catalogo_local = cargar_catalogo()
    dic = st.session_state.diccionario
    df_dic = pd.DataFrame(dic)
    
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


# ─────────────────────────────────────────────────────────────────────────────
# INVOCACIÓN RESTRINGIDA (ESCUDO DE EJECUCIÓN GLOBAL)
# ─────────────────────────────────────────────────────────────────────────────

class TaxFolder:
    """Clase de marcador de posición para evitar que el orquestador falle al importar"""
    pass
    
if __name__ == '__main__':
    main()
