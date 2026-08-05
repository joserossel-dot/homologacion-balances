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
import time
from pathlib import Path

import pandas as pd
import streamlit as st
from rapidfuzz import fuzz, process

from clasificador_codigo_cuenta import ClasificadorCodigo
from catalog_selection import opciones_clasificacion
from gold_standard.builder import GoldBuilder
from gold_standard.models import GoldRecord
from gold_standard.promotion import promote as promover_revisiones
from gold_standard.runtime import RuntimeGoldStorage
from gold_standard.runtime_manager import RuntimeManager
from reglas_especiales import ProcesadorReglasEspeciales, calcular_patrimonio_efectivo
from config.regex_rules import REGLAS_REGEX, REGLAS_COMPILADAS
from parser_universal import ParserPDF, CuentaRaw, OrigenColumna, parsear_excel
from parsers.column_interpretation import es_ingreso as es_ingreso_col, es_gasto as es_gasto_col
from extractor_metadata import extraer_metadata, MetadataEmpresa

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent
UMBRAL_REVISION = 0.85  # bajo este valor, la cuenta va a la cola de revisión
USE_LEGACY_ENGINE = False  # True → MotorHibridoLocal (antiguo); False → HomologationPipeline (nuevo, default)
SHADOW_MODE = True  # True → ejecuta nuevo pipeline en paralelo sin afectar UI, guarda logs en logs/shadow/

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
                if 'origen' in df_res.columns:
                    df_res.loc[mask_target, 'origen'] = (
                        'Manual' if any(k in metodo for k in ('humana', 'manual')) else 'Código'
                    )
                    df_res.loc[mask_target, 'regla'] = metodo
                    df_res.loc[mask_target, 'evidencia'] = 'Propagación automática entre balances'
                st.session_state.resultados[fn] = df_res
                propagaciones += 1
        
        if propagaciones > 1:
            st.toast(f"Homologación propagada a {propagaciones - 1} otro(s) balance(s) 🔄", icon="🔄")


def _nombre_mostrar(row: pd.Series) -> str:
    return row.get('nombre_revision_usuario', '') or row['nombre_original']


# ─────────────────────────────────────────────────────────────────────────────
# EXPLICABILIDAD (P6) — trazabilidad auditable de cada decisión.
# Solo expone información existente: nunca modifica la decisión del motor.
# ─────────────────────────────────────────────────────────────────────────────

ORIGENES_EXPLICABILIDAD = [
    'Runtime', 'Gold', 'Código', 'Regex', 'CMCC', 'Semantic', 'Manual', 'Regla', 'Sin clasificar',
]

_BADGE_ORIGEN_COLORS = {
    'Runtime': '#7B1FA2', 'Gold': '#C2185B', 'Código': '#1565C0', 'Regex': '#00695C',
    'CMCC': '#EF6C00', 'Semantic': '#2E7D32', 'Manual': '#37474F',
    'Regla': '#F9A825', 'Sin clasificar': '#757575',
}


def _badge_origen(origen: str) -> str:
    color = _BADGE_ORIGEN_COLORS.get(origen or '', '#757575')
    label = origen or '—'
    return (
        f"<span style='background:{color}; color:white; padding:2px 8px; border-radius:4px; "
        f"font-size:0.72em; font-weight:600;'>{label}</span>"
    )


def _origen_desde_metodo_display(metodo: str) -> str:
    """Mapea el método de clasificación a la categoría de origen (solo lectura)."""
    m = (metodo or '').lower()
    if not m:
        return 'Sin clasificar'
    if m in ('sin_clasificar', 'unclassified', 'movement_only'):
        return 'Sin clasificar'
    if 'learning' in m or m.startswith('gold_') or m.startswith('runtime_'):
        return 'Gold'
    if 'cmcc' in m:
        return 'CMCC'
    if 'semantic' in m:
        return 'Semantic'
    if 'regex' in m:
        return 'Regex'
    if m.startswith('code') or m == 'codigo' or 'diccionario' in m or 'dictionary' in m:
        return 'Código'
    if 'decision' in m:
        return 'Regla'
    if 'propagad' in m:
        return 'Código'
    if any(k in m for k in ('validacion_humana', 'manual', 'excluido', 'lote')):
        return 'Manual'
    if 'regla_especial' in m or m == 'regla' or 'regla' in m:
        return 'Regla'
    if 'columna_ambiguo' in m:
        return 'Código'
    return 'Regla'


def _fmt_confianza(val) -> str:
    if val is None:
        return '—'
    if isinstance(val, float) and pd.isna(val):
        return '—'
    try:
        return f"{float(val):.0%}"
    except (TypeError, ValueError):
        return str(val)


def _learning_runtime_hit(account_name: str, hp) -> bool:
    """True si el learning_* vino del runtime (consulta read-only)."""
    try:
        rt = hp._learning_engine._runtime_lookup(account_name)
    except Exception:
        rt = None
    return rt is not None


def _origen_desde_clasif(clasif: dict, account_name: str, hp=None) -> str:
    """Origen (Runtime/Gold/Código/Regex/CMCC/Semantic) a partir del dict del motor."""
    metodo = (clasif.get('method') or '').lower()
    if metodo.startswith('learning_'):
        if hp is not None and _learning_runtime_hit(account_name, hp):
            return 'Runtime'
        return 'Gold'
    if metodo.startswith('cmcc'):
        return 'CMCC'
    if metodo.startswith('semantic'):
        return 'Semantic'
    if metodo.startswith('regex'):
        return 'Regex'
    if metodo.startswith('code') or metodo.startswith('diccionario') or metodo.startswith('dictionary'):
        return 'Código'
    if metodo.startswith('decision'):
        de = clasif.get('decision_engine') or {}
        src = (de.get('decision_source') or '').upper()
        if 'SM' in src:
            return 'Semantic'
        if 'REGEX' in src:
            return 'Regex'
        if 'DICT' in src:
            return 'Código'
        return 'Regla'
    if metodo in ('', 'unclassified', 'movement_only'):
        return 'Sin clasificar'
    return 'Regla'


def _resolver_tipo_cuenta(origen_columna, codigo) -> str | None:
    """Account type (read-only) para etapas sensibles al tipo. Never modifica nada."""
    try:
        from parser_universal import OrigenColumna as _OC
        from parsers.account_type_resolver import AccountTypeResolver
        origen = _OC(origen_columna) if origen_columna else _OC.DESCONOCIDO
        return AccountTypeResolver().resolve(origen_columna=origen, codigo=codigo).account_type.value
    except Exception:
        return None


def _explicar_clasificacion(hp, account_code: str, account_name: str, *,
                            account_tipo: str | None = None,
                            origen_columna=None,
                            metodo_actual: str = '') -> list[dict]:
    """Reconstrucción read-only de las reglas evaluadas para la UI.

    No ejecuta ni modifica la decisión del motor: re-evalúa cada etapa para
    auditar la cadena de decisión. Cada lectura va envuelta en try/except para
    que un fallo en una etapa nunca rompa la UI.
    """
    etapas: list[dict] = []

    def _agregar(nombre, result, metodo):
        if result is None:
            etapas.append({
                'regla': nombre, 'coincidio': False, 'resultado': '—',
                'confianza': '—', 'detalle': 'Sin coincidencia', 'ganadora': False,
                '_metodo': metodo,
            })
            return
        detalle = result.get('reason') if isinstance(result, dict) else None
        etapas.append({
            'regla': nombre, 'coincidio': True,
            'resultado': result.get('standard_code') or '—',
            'confianza': _fmt_confianza(result.get('confidence')),
            'detalle': detalle or 'Coincidencia',
            'ganadora': False,
            '_metodo': metodo,
        })

    try:
        _agregar('1 · Código de cuenta',
                 hp._classify_by_code(account_code) if account_code else None, 'code')
    except Exception:
        pass
    try:
        _agregar('2 · Diccionario (exacto)',
                 hp._classify_by_dictionary_exact(account_name), 'dictionary_exact')
    except Exception:
        pass
    try:
        _agregar('3 · Diccionario (fuzzy)',
                 hp._classify_by_dictionary_fuzzy(account_name), 'dictionary_fuzzy')
    except Exception:
        pass
    try:
        _regex = None
        if hp._features.ENABLE_REGEX_FALLBACK:
            _regex = hp._classify_by_regex(account_name, account_tipo)
        _agregar('4 · Regex fallback', _regex, 'regex_fallback')
    except Exception:
        pass
    try:
        _rt = None
        if hp._learning_engine._runtime_path.exists():
            _rt = hp._learning_engine._runtime_lookup(account_name)
        if _rt is not None:
            _agregar('5 · Runtime (gold runtime)', _rt, f"learning_{_rt.get('source')}")
    except Exception:
        pass
    try:
        _gold = hp._learning_engine.best_match(account_name, use_runtime=False)
        if _gold.get('source') != 'none':
            _agregar('6 · Gold Standard', _gold, f"learning_{_gold.get('source')}")
    except Exception:
        pass
    try:
        if hp._features.ENABLE_CMCC:
            _cmcc = hp._cmcc_classifier.classify(account_name)
            _agregar('7 · CMCC', _cmcc, (_cmcc or {}).get('method', 'cmcc'))
    except Exception:
        pass
    try:
        if hp._features.ENABLE_SEMANTIC_MATCHER and hp._semantic_matcher is not None:
            _sm = hp._semantic_matcher.match(account_name, account_tipo)
            if _sm is not None and not _sm.is_unknown:
                _agregar(
                    '8 · Semantic',
                    {'standard_code': _sm.expected_cmcc,
                     'confidence': min(_sm.score, 0.99),
                     'reason': f"tier={_sm.match_tier} concept={_sm.concept_name}"},
                    f"semantic_{_sm.match_tier}",
                )
    except Exception:
        pass

    ma = (metodo_actual or '').lower()
    if ma.startswith('learning_'):
        for e in etapas:
            if str(e.get('_metodo', '')).startswith('learning_'):
                e['ganadora'] = True
                break
    else:
        for e in etapas:
            if e.get('_metodo') == ma:
                e['ganadora'] = True
                break
    return etapas


def _mostrar_detalle_cuenta(row: pd.Series, catalogo: dict, hp=None, close_key: str | None = None):
    if close_key:
        if st.button('✖ Cerrar detalle', key=f"close_{close_key}"):
            st.session_state.pop(close_key, None)
            st.rerun()

    st.markdown('#### 🔍 Detalle de clasificación')
    nombre = _nombre_mostrar(row)
    origen = row.get('origen') if 'origen' in row.index else ''
    origen = origen or _origen_desde_metodo_display(row.get('metodo', ''))
    regla = row.get('regla') if 'regla' in row.index else ''
    regla = regla or row.get('metodo', '')
    evidencia = row.get('evidencia') if 'evidencia' in row.index else ''
    evidencia = evidencia or row.get('nota', '') or 'Sin evidencia adicional.'
    tiempo = row.get('tiempo_clasificacion') if 'tiempo_clasificacion' in row.index else None

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**Nombre original:** {nombre}")
        nombre_norm = row.get('nombre_normalizado') if 'nombre_normalizado' in row.index else ''
        st.markdown(f"**Nombre normalizado:** `{nombre_norm or normalizar_nombre(nombre)}`")
        st.markdown(f"**Código final:** `{row.get('codigo_clasificado', '') or '(sin clasificar)'}`")
    with c2:
        st.markdown(f"**Regla ganadora:** `{regla}`")
        st.markdown(f"**Score:** **{_fmt_confianza(row.get('confianza'))}**")
        st.markdown(f"**Confianza:** {_fmt_confianza(row.get('confianza'))}")
        st.markdown(f"**Origen:** {_badge_origen(origen)}", unsafe_allow_html=True)
        tiempo_txt = f"{tiempo:.2f} ms" if tiempo is not None and pd.notna(tiempo) else '—'
        st.markdown(f"**Tiempo de clasificación:** {tiempo_txt}")
        st.markdown(f"**Runtime usado:** {'Sí' if origen == 'Runtime' else 'No'}")
        st.markdown(f"**Gold usado:** {'Sí' if origen == 'Gold' else 'No'}")

    st.markdown('**Evidencia:**')
    st.info(evidencia)

    if hp is not None:
        etapas = _explicar_clasificacion(
            hp,
            row.get('codigo_original', '') or '',
            nombre,
            origen_columna=row.get('origen_columna'),
            metodo_actual=regla,
        )
        if etapas:
            st.markdown('**Reglas evaluadas (auditoría read-only):**')
            df_etapas = pd.DataFrame([
                {k: v for k, v in e.items() if not k.startswith('_')} for e in etapas
            ])
            st.dataframe(df_etapas, use_container_width=True, hide_index=True)


def _tab_explicabilidad(df: pd.DataFrame, catalogo: dict, hp=None, archivo_nombre: str = ''):
    st.subheader('🔍 Explicabilidad de clasificación')
    st.caption(
        'Trazabilidad auditable por cuenta: código final, origen, score, regla, evidencia y '
        'confianza. La auditoría es de solo lectura y no modifica decisiones del motor.'
    )

    clasificadas = df[
        (df['codigo_clasificado'] != '') &
        (df['codigo_clasificado'] != '__EXCLUIR__') &
        (~df['es_total'])
    ].copy()
    if clasificadas.empty:
        st.info('No hay cuentas clasificadas para auditar.')
        return

    if 'origen' not in clasificadas.columns:
        clasificadas['origen'] = clasificadas['metodo'].map(_origen_desde_metodo_display)
    if 'regla' not in clasificadas.columns:
        clasificadas['regla'] = clasificadas['metodo']
    if 'evidencia' not in clasificadas.columns:
        clasificadas['evidencia'] = ''

    cf1, cf2 = st.columns(2)
    with cf1:
        filtro = st.text_input('Buscar cuenta (nombre o código)', key='exp_buscar')
    with cf2:
        origenes = ['Todos'] + sorted(o for o in clasificadas['origen'].dropna().unique() if o)
        sel_origen = st.selectbox('Origen', origenes, key='exp_origen')

    v = clasificadas
    if filtro:
        f = filtro.lower()
        v = v[
            v['nombre_original'].astype(str).str.lower().str.contains(f, na=False) |
            v['codigo_clasificado'].astype(str).str.lower().str.contains(f, na=False)
        ]
    if sel_origen != 'Todos':
        v = v[v['origen'] == sel_origen]
    v = v.sort_values(
        ['codigo_clasificado', 'monto'],
        key=lambda x: x.abs() if x.dtype.kind == 'f' else x,
        ascending=[True, False],
    )

    st.caption(f"`{archivo_nombre}` · {len(v)} cuenta(s) · filtro origen = {sel_origen}")

    for idx, row in v.iterrows():
        with st.container(border=True):
            cc1, cc2, cc3, cc4, cc5 = st.columns([1.2, 2.5, 1, 1, 1.5])
            with cc1:
                st.markdown(f"`{row['codigo_clasificado']}`")
            with cc2:
                st.markdown(f"**{_nombre_mostrar(row)}**")
            with cc3:
                st.markdown(_badge_origen(row.get('origen', '')), unsafe_allow_html=True)
            with cc4:
                st.markdown(f"**{_fmt_confianza(row.get('confianza'))}**")
            with cc5:
                st.markdown(f"`{row.get('regla', '')}`")
            if st.button('🔍 Ver detalle', key=f"det_exp_{idx}", use_container_width=True):
                st.session_state['detalle_explicabilidad_idx'] = idx
                st.rerun()

    det_idx = st.session_state.get('detalle_explicabilidad_idx')
    if det_idx is not None and det_idx in v.index:
        st.divider()
        _mostrar_detalle_cuenta(v.loc[det_idx], catalogo, hp=hp, close_key='detalle_explicabilidad_idx')


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
            es_ing = es_ingreso_col(col)
            es_gas = es_gasto_col(col)
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
        es_ingreso = es_ingreso_col(origen)
        es_gasto   = es_gasto_col(origen)

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


# ─────────────────────────────────────────────────────────────────────────────
# INTERFAZ DE USUARIO PRINCIPAL (MAIN)
# ─────────────────────────────────────────────────────────────────────────────

def _save_gold_standard(account_name, account_code, final_code, reviewer="analista"):
    try:
        builder = GoldBuilder()
        record = GoldRecord(
            account_name=account_name,
            account_code_original=account_code,
            final_code=final_code,
            reviewer=reviewer,
            source_file=st.session_state.get("archivo_activo_select", ""),
        )
        builder.add_or_update(record)
        builder.close()
    except Exception:
        pass


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
    if 'document_intel' not in st.session_state:
        st.session_state.document_intel = {}
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

    # ── Procesar archivos nuevos ──────────────────────────────────────────────
    if USE_LEGACY_ENGINE:
        # LEGACY PIPELINE (MotorHibridoLocal)
        for archivo in archivos:
            if archivo.name not in st.session_state.resultados:
                with st.spinner(f"Clasificando cuentas de {archivo.name}..."):
                    lineas_encabezado = _extraer_lineas_encabezado(archivo)
                    meta_indiv = extraer_metadata(lineas_encabezado)
                    st.session_state.metadata_files[archivo.name] = meta_indiv

                    cuentas, doc_ctx = _extraer_cuentas(archivo)
                    st.session_state.document_intel[archivo.name] = doc_ctx
                    motor = MotorHibridoLocal(st.session_state.diccionario)
                    filas = []
                    for c in cuentas:
                        if c.monto is None and not c.codigo:
                            continue
                        if not c.codigo and PATRON_NO_CUENTA.match(c.nombre.strip()):
                            continue
                        _t0_legacy = time.perf_counter()
                        r = motor.clasificar(c, company_giro_norm)
                        _t1_legacy = (time.perf_counter() - _t0_legacy) * 1000
                        filas.append({
                            'linea': c.linea,
                            'codigo_original': c.codigo or '',
                            'nombre_original': c.nombre,
                            'nombre_normalizado': normalizar_nombre(c.nombre),
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
                            'nombre_revision_usuario': '',
                            'tipo_revision': '',
                            'origen': _origen_desde_metodo_display(r['metodo']),
                            'regla': r['metodo'],
                            'evidencia': r.get('nota_regla_especial', '') or r['metodo'],
                            'tiempo_clasificacion': round(_t1_legacy, 3),
                        })
                    df_file = pd.DataFrame(filas)
                    st.session_state.resultados[archivo.name] = df_file

                    # SHADOW MODE — homologación comparativa contra motor legacy
                    if SHADOW_MODE and Path(archivo.name).suffix.lower() == '.pdf':
                        import tempfile
                        from pipeline.homologation_pipeline import HomologationPipeline
                        from shadow.shadow_logger import ShadowLogger
                        tmp_shadow = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
                        try:
                            tmp_shadow.write(archivo.read())
                            tmp_shadow.close()
                            sh_path = Path(tmp_shadow.name)
                            hp_shadow = HomologationPipeline()
                            sh_summary = hp_shadow.process(sh_path)
                            logger_sh = ShadowLogger()
                            comparisons = []
                            matches = 0
                            for sh_entry in sh_summary.get("classified", []):
                                aname = sh_entry["account_name"]
                                amatch = df_file[df_file["nombre_original"] == aname]
                                if amatch.empty:
                                    continue
                                comparisons.append(logger_sh.build_comparison(
                                    account_name=aname,
                                    account_code=sh_entry.get("account_code", ""),
                                    legacy_code=amatch.iloc[0]["codigo_clasificado"] or None,
                                    legacy_confidence=amatch.iloc[0]["confianza"],
                                    new_code=sh_entry.get("final_code") or sh_entry.get("standard_code"),
                                    new_confidence=sh_entry.get("confidence", 0.0),
                                    new_method=sh_entry.get("method", ""),
                                    learning_hit="learning" in sh_entry.get("method", ""),
                                ))
                                if comparisons[-1]["match"]:
                                    matches += 1
                            total_comp = len(comparisons)
                            match_rate = matches / total_comp if total_comp else 1.0
                            logger_sh.log(archivo.name, comparisons, match_rate)
                        finally:
                            sh_path.unlink(missing_ok=True)
                            archivo.seek(0)
    else:
        # NEW PIPELINE (HomologationPipeline)
        import logging as _logging
        _shadow_logger = _logging.getLogger("homologation_pipeline")
        from pipeline.homologation_pipeline import HomologationPipeline
        from adapters.account_adapter import AccountAdapter
        from interpreters.balance_interpreter import BalanceInterpreter

        hp = HomologationPipeline()
        for archivo in archivos:
            if archivo.name not in st.session_state.resultados:
                with st.spinner(f"Clasificando cuentas de {archivo.name}..."):
                    _t0 = time.perf_counter()
                    lineas_encabezado = _extraer_lineas_encabezado(archivo)
                    meta_indiv = extraer_metadata(lineas_encabezado)
                    st.session_state.metadata_files[archivo.name] = meta_indiv

                    cuentas, doc_ctx = _extraer_cuentas(archivo)
                    st.session_state.document_intel[archivo.name] = doc_ctx
                    total_cuentas = len(cuentas)
                    filas = []
                    clasificadas = 0
                    learning_hits = 0
                    fallback_count = 0

                    for c in cuentas:
                        if c.monto is None and not c.codigo:
                            continue
                        if not c.codigo and PATRON_NO_CUENTA.match(c.nombre.strip()):
                            continue
                        ab = AccountAdapter.from_cuenta_raw(c)
                        interp = BalanceInterpreter(ab)
                        classification_amount = interp.classification_amount
                        if classification_amount is None:
                            codigo_clasificado = ""
                            metodo = "movement_only"
                            confianza = 0.0
                            requiere_revision = True
                            nota = ""
                            clasif_origen = 'Sin clasificar'
                            clasif_evidencia = ''
                            tiempo_clasif_ms = 0.0
                        else:
                            clasificadas += 1
                            _t0_clasif = time.perf_counter()
                            classification = hp._classify_account(ab.account_code, ab.account_name)
                            tiempo_clasif_ms = round((time.perf_counter() - _t0_clasif) * 1000, 3)
                            adjustment = hp._rule_processor.aplicar(
                                nombre_cuenta=ab.account_name,
                                codigo_clasificado=classification.get("standard_code") or "",
                                monto=classification_amount,
                            )
                            final_code = (
                                adjustment.codigo_final if adjustment.aplica
                                else classification.get("standard_code")
                            )
                            codigo_clasificado = final_code or ""
                            metodo = classification.get("method", "")
                            confianza = classification.get("confidence", 0.0)
                            requiere_revision = confianza < UMBRAL_REVISION
                            nota = adjustment.nota if adjustment.aplica else ""
                            clasif_evidencia = classification.get("reason", "")
                            clasif_origen = _origen_desde_clasif(classification, ab.account_name, hp)
                            if metodo.startswith("learning_"):
                                learning_hits += 1
                            else:
                                fallback_count += 1

                        filas.append({
                            'linea': c.linea,
                            'codigo_original': c.codigo or '',
                            'nombre_original': c.nombre,
                            'nombre_normalizado': normalizar_nombre(c.nombre),
                            'monto': c.monto,
                            'origen_columna': c.origen_columna.value,
                            'es_total': c.es_total,
                            'codigo_clasificado': codigo_clasificado,
                            'metodo': metodo,
                            'confianza': confianza,
                            'requiere_revision': requiere_revision,
                            'nota': nota,
                            'confianza_extraccion': c.confianza_extraccion,
                            'origen_columna_display': c.origen_columna.value,
                            'nombre_revision_usuario': '',
                            'tipo_revision': '',
                            'origen': clasif_origen,
                            'regla': metodo,
                            'evidencia': clasif_evidencia,
                            'tiempo_clasificacion': tiempo_clasif_ms,
                        })

                    df_file = pd.DataFrame(filas)
                    st.session_state.resultados[archivo.name] = df_file

                    _t1 = time.perf_counter()
                    _shadow_logger.info(
                        "archivo=%s cuentas=%d clasificadas=%d learning_hits=%d fallback=%d time=%.3fs",
                        archivo.name, total_cuentas, clasificadas,
                        learning_hits, fallback_count, _t1 - _t0,
                    )
    # After processing all uploaded files, propagate classifications across all balances
    if 'propagation_done' not in st.session_state:
        # Define helper to propagate classifications across balances
        def propagar_entre_balances():
            """Propaga códigos clasificados entre balances cargados."""
            # Build mapping from normalized account name to list of (file, index)
            name_map = {}
            for fname, df in st.session_state.resultados.items():
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
                            if 'origen' in st.session_state.resultados[fname].columns:
                                st.session_state.resultados[fname].at[idx, 'origen'] = 'Código'
                                st.session_state.resultados[fname].at[idx, 'regla'] = 'propagado_automático'
                                st.session_state.resultados[fname].at[idx, 'evidencia'] = 'Propagación automática entre balances'
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

    # Sprint 31 — Información del documento (análisis documental, solo lectura)
    _doc_ctx = st.session_state.document_intel.get(archivo_activo_name)
    if _doc_ctx is not None:
        _mostrar_informacion_documento(_doc_ctx)

    col_visor, col_trabajo = st.columns([1, 1], gap="medium")

    with col_visor:
        try:
            _visor_documento(archivo_activo)
        except (NameError, Exception):
            pass

    with col_trabajo:
        tab_resumen, tab_revision, tab_balance, tab_diccionario, tab_aprendizaje, tab_analytics, tab_conocimiento, tab_inteligencia, tab_km = st.tabs(
            ["📈 Resumen", "🔍 Cola de Revisión", "📋 Balance Normalizado",
             "📚 Diccionario", "🧠 Aprendizaje", "📊 Analytics", "📖 Conocimiento Documental",
             "📈 Inteligencia del Dataset", "🧠 Knowledge Manager"]
        )

        with tab_resumen: _tab_resumen(df)
        with tab_revision: _tab_revision(df, catalogo, motor=MotorHibridoLocal(st.session_state.diccionario), archivo_nombre=archivo_activo_name)
        with tab_balance: _tab_balance(df, catalogo)
        with tab_diccionario: _tab_diccionario()
        with tab_conocimiento: _tab_conocimiento(archivo_activo, _doc_ctx, meta_activo)
        with tab_inteligencia: _tab_inteligencia()
        with tab_km: _tab_knowledge_manager()


        with tab_aprendizaje:
            _tab_aprendizaje()

        with tab_analytics:
            st.markdown("Analytics Dashboard (Work in Progress)")


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


def _extraer_cuentas(archivo) -> tuple[list[CuentaRaw], object]:
    """Extrae cuentas y devuelve (cuentas, document_context).

    `document_context` es el DocumentProcessingContext (Sprint 31) cuando el
    archivo es PDF y el análisis documental corrió; None en caso contrario.
    """
    suffix = Path(archivo.name).suffix.lower()
    if suffix == '.pdf':
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            tmp.write(archivo.read())
            tmp_path = Path(tmp.name)
        parser = ParserPDF()
        resultado = parser.parsear(tmp_path)
        for adv in resultado.advertencias: st.warning(adv)
        return resultado.cuentas, getattr(resultado, 'document_context', None)
    else:
        return parsear_excel(archivo), None


def _mostrar_informacion_documento(ctx) -> None:
    """Sección solo-lectura INFORMACIÓN DEL DOCUMENTO (Sprint 31, FASE 5).

    Muestra la metadata del análisis documental ANTES de los resultados.
    No modifica ningún resultado: si `ctx` no está disponible, no dibuja nada.
    """
    if ctx is None:
        return
    try:
        info = ctx.ui_summary()
    except Exception:
        return

    with st.container(border=True):
        st.markdown("#### 🧾 INFORMACIÓN DEL DOCUMENTO")
        cols = st.columns(4)
        items = [
            ("Documento", info.get("Documento", "—")),
            ("Formato", info.get("Formato", "—")),
            ("Columnas", info.get("Columnas", "—")),
            ("Layout", info.get("Layout", "—")),
            ("OCR", info.get("OCR", "—")),
            ("Extractor", info.get("Extractor", "—")),
            ("Confianza", info.get("Confianza", "—")),
            ("Familia", info.get("Familia", "—")),
        ]
        for i, (label, value) in enumerate(items):
            with cols[i % 4]:
                st.markdown(f"**{label}**  \n`{value}`")


# ─────────────────────────────────────────────────────────────────────────────
# CONOCIMIENTO DOCUMENTAL (Sprint 32 — Document Knowledge Base)
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_resource
def _cargar_document_kb():
    """Carga la DKB desde knowledge_base/document_kb.json (None si no existe)."""
    try:
        from document_intelligence.knowledge import DocumentKnowledgeBase
        path = BASE_DIR / "knowledge_base" / "document_kb.json"
        if not path.exists():
            return None
        kb = DocumentKnowledgeBase()
        kb.load(path)
        return kb
    except Exception:
        return None


def _build_fingerprint_archivo(archivo, doc_ctx):
    """Construye el fingerprint del archivo activo (con caché por nombre)."""
    if "document_fingerprints" not in st.session_state:
        st.session_state.document_fingerprints = {}
    name = archivo.name
    if name in st.session_state.document_fingerprints:
        return st.session_state.document_fingerprints[name]

    import tempfile
    from document_intelligence.knowledge.fingerprint import fingerprint_from_file
    suffix = Path(archivo.name).suffix.lower()
    archivo.seek(0)
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(archivo.read())
        tmp_path = Path(tmp.name)
    try:
        fp = fingerprint_from_file(tmp_path, signature=doc_ctx.signature)
    finally:
        archivo.seek(0)
        tmp_path.unlink(missing_ok=True)
    st.session_state.document_fingerprints[name] = fp
    return fp


def _tab_conocimiento(archivo, doc_ctx, meta_activo) -> None:
    """Sección CONOCIMIENTO DOCUMENTAL: DKB + matching del documento activo.

    Solo lectura. Si la DKB no está disponible o el matcher falla, muestra
    un aviso y NO afecta ningún resultado.
    """
    if archivo is None or doc_ctx is None:
        st.info("El análisis documental no está disponible para este archivo.")
        return

    kb = _cargar_document_kb()
    if kb is None or not getattr(kb, "profiles", None):
        st.info(
            "📖 La Document Knowledge Base aún no existe. "
            "Ejecuta `python tools/build_document_kb.py` para construirla."
        )
        return

    try:
        fp = _build_fingerprint_archivo(archivo, doc_ctx)
        company = ""
        if meta_activo is not None and getattr(meta_activo, "razon_social", ""):
            company = meta_activo.razon_social
        from document_intelligence.knowledge import Matcher
        result = Matcher().match(fp, kb.profiles, company=company)
    except Exception as exc:  # noqa: BLE001 — el matcher nunca rompe el pipeline
        st.warning(f"El matcher de la DKB no pudo ejecutarse ({exc}).")
        return

    profile = result.matched_profile
    if profile is None:
        st.info("No se encontraron perfiles similares en la DKB.")
        return

    st.markdown("#### 📖 Conocimiento Documental")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Perfil detectado", profile.name, help=profile.description)
    c2.metric("Empresa", profile.company)
    c3.metric("Familia", profile.family)
    c4.metric("Extractor recomendado", profile.recommended_extractor)
    c5.metric("Similitud", f"{result.similarity:.0f}%")

    st.markdown("**Top 5 perfiles similares**")
    ranking_rows = []
    for p, sim in result.ranking[:5]:
        ranking_rows.append({
            "Perfil": p.name,
            "Empresa": p.company,
            "Familia": p.family,
            "Similitud": f"{sim:.0f}%",
            "Frecuencia": p.times_seen,
        })
    st.dataframe(ranking_rows, use_container_width=True, hide_index=True)

    st.markdown("**Variantes conocidas**")
    if profile.known_variants:
        st.write(", ".join(profile.known_variants))
    else:
        st.caption("Sin variantes registradas.")

    st.markdown("**Historial**")
    h1, h2, h3 = st.columns(3)
    h1.metric("Primera aparición", profile.first_seen or "—")
    h2.metric("Última aparición", profile.last_seen or "—")
    h3.metric("Frecuencia (documentos)", profile.times_seen)


@st.cache_resource
def _cargar_mining_result():
    """Carga el resultado de minería desde document_mining.json (None si no existe)."""
    try:
        path = BASE_DIR / "knowledge_base" / "document_mining.json"
        if not path.exists():
            return None
        from document_intelligence.mining import load_analysis_result
        return load_analysis_result(path)
    except Exception:
        return None


def _tab_inteligencia() -> None:
    """Inteligencia del Dataset: minería del DKB (solo lectura).

    Muestra familias descubiertas, cobertura esperada, representantes,
    variantes y confianza. NO edita datos.
    """
    result = _cargar_mining_result()
    if result is None:
        st.info(
            "📈 La minería del dataset aún no existe. "
            "Ejecuta `python tools/run_document_mining.py` para generarla."
        )
        return

    st.markdown("#### 📈 Inteligencia del Dataset")
    st.caption("Familias descubiertas por fingerprint (sin empresa ni nombre de archivo).")

    matrix = result.get("matrix", {})
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Familias detectadas", result.get("n_families", 0))
    c2.metric("Documentos analizados", result.get("n_documents", 0))
    c3.metric("Similitud media global", f"{matrix.get('mean_similarity', 0):.0f}%")
    c4.metric("Pares comparados", f"{matrix.get('pairs_computed', 0):,}")

    coverage = result.get("coverage", {}).get("tiers", [])
    if coverage:
        st.markdown("**Cobertura esperada**")
        st.dataframe([{
            "Top N familias": t["top_n"],
            "Familias": t["families"],
            "Documentos": t["documents"],
            "% acumulado": f"{t['cumulative_pct']}%",
            "% restante": f"{t['remaining_pct']}%",
        } for t in coverage], use_container_width=True, hide_index=True)

    familias = result.get("families", [])
    st.markdown("**Top familias**")
    if familias:
        st.dataframe([{
            "Familia": f["id"],
            "Empresa principal": f.get("top_company", "") or "—",
            "Documentos": f["count"],
            "Similitud interna": f"{f['avg_similarity']:.0f}%",
            "Layout": f["dominant_layout"],
            "Código": f["dominant_code_pattern"],
            "Tipo doc": f["dominant_document_type"],
        } for f in familias[:10]], use_container_width=True, hide_index=True)

    representantes = result.get("representatives", [])
    st.markdown("**Representantes**")
    if representantes:
        st.dataframe([{
            "Familia": r["family_id"],
            "Documento representante": r["file"],
            "Similitud promedio": f"{r['avg_similarity']:.0f}%",
            "Documentos": r["n_documents"],
            "Empresa": r["company"],
        } for r in representantes[:10]], use_container_width=True, hide_index=True)

    recomendaciones = result.get("recommendations", [])
    st.markdown("**Recomendación de extractores**")
    if recomendaciones:
        top = recomendaciones[0]
        st.write(
            f"Desarrollar primero un **`{top['extractor_type']}`** para la familia "
            f"`{top['family_name']}` ({top['count']} documentos, "
            f"{top['pct_dataset']}% del dataset)."
        )
        if len(recomendaciones) > 1:
            st.caption("Siguientes candidatas: " + ", ".join(
                r["family_name"] for r in recomendaciones[1:5]
            ))
    else:
        st.caption("Aún no hay familias con volumen suficiente.")

    variantes = result.get("statistics", {}).get("top_variants", [])
    if variantes:
        st.markdown("**Top variantes (empresa · layout)**")
        st.dataframe([{
            "Empresa": v["company"],
            "Layout": v["layout"],
            "Familias": v["count"],
        } for v in variantes[:10]], use_container_width=True, hide_index=True)

    problemas = result.get("quality_issues", [])
    if problemas:
        st.markdown(f"**Problemas detectados ({len(problemas)})**")
        st.dataframe([{
            "Severidad": p["severity"],
            "Tipo": p["kind"],
            "Detalle": p["message"],
        } for p in problemas[:10]], use_container_width=True, hide_index=True)


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

    # Catálogo ordenado por grupos de presentación y sin cuentas no
    # seleccionables (cálculo / TOTAL). Ver catalog_selection.py.
    opciones_codigo = [''] + opciones_clasificacion(catalogo) + ['➕ NUEVA CATEGORÍA', '🚫 NO INCLUIR']

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
                    codigo_orig = df.at[idx_lote, 'codigo_original']
                    st.session_state.resultados[archivo_nombre].at[idx_lote, 'codigo_clasificado'] = codigo_lote
                    st.session_state.resultados[archivo_nombre].at[idx_lote, 'metodo'] = 'validacion_humana_lote'
                    st.session_state.resultados[archivo_nombre].at[idx_lote, 'confianza'] = 1.0
                    st.session_state.resultados[archivo_nombre].at[idx_lote, 'requiere_revision'] = False
                    st.session_state.resultados[archivo_nombre].at[idx_lote, 'origen'] = 'Manual'
                    st.session_state.resultados[archivo_nombre].at[idx_lote, 'regla'] = 'validacion_humana_lote'
                    st.session_state.resultados[archivo_nombre].at[idx_lote, 'evidencia'] = 'Asignación en lote por analista'
                    # Gold Standard autoaprendizaje
                    _save_gold_standard(nombre_orig, codigo_orig, codigo_lote)
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
            c0, c1, c2 = st.columns([0.3, 4, 4])
            with c0:
                marcado = st.checkbox("", value=seleccionada, key=f"chk_{idx}", label_visibility="collapsed")
                if marcado and idx not in st.session_state.lote_seleccion:
                    st.session_state.lote_seleccion.add(idx); st.rerun()
                elif not marcado and idx in st.session_state.lote_seleccion:
                    st.session_state.lote_seleccion.discard(idx); st.rerun()

            with c1:
                col_actual = row.get('origen_columna_display', row.get('origen_columna', '')).upper()
                badge_bg = {
                    'ACTIVO': '#1E90FF', 'PASIVO': '#FF8C00',
                    'PERDIDA': '#DC143C', 'GANANCIA': '#2E8B57',
                }.get(col_actual, '#6B7280')
                st.markdown(
                    f"<span style='background:{badge_bg}; color:white; "
                    f"padding:2px 10px; border-radius:4px; font-size:0.75em; "
                    f"font-weight:600; letter-spacing:0.5px;'>{col_actual}</span>",
                    unsafe_allow_html=True,
                )
                st.markdown(f"**{_nombre_mostrar(row)}**")
                monto_val = row['monto']
                if pd.notna(monto_val):
                    color = 'blue' if monto_val > 0 else ('red' if monto_val < 0 else 'gray')
                    st.markdown(
                        f"<span style='color:{color}; font-weight:bold;'>{monto_val:,.0f}</span>",
                        unsafe_allow_html=True,
                    )

                edit_mode = st.checkbox("Editar cuenta", key=f"edit_{idx}")

                if edit_mode:
                    st.divider()
                    nuevo_nombre = st.text_input("Nombre", value=_nombre_mostrar(row), key=f"ed_nombre_{idx}")
                    opciones_nat = ['ACTIVO', 'PASIVO', 'PERDIDA', 'GANANCIA']
                    idx_nat = opciones_nat.index(col_actual) if col_actual in opciones_nat else 0
                    nueva_nat = st.selectbox("Columna contable", opciones_nat, index=idx_nat, key=f"ed_nat_{idx}")
                    monto_inicial = row['monto'] if pd.notna(row['monto']) else 0.0
                    nuevo_monto = st.number_input("Monto", value=float(monto_inicial), format="%.0f", key=f"ed_monto_{idx}")

                    if st.button("💾 Guardar corrección", key=f"ed_guardar_{idx}", use_container_width=True):
                        df_mod = st.session_state.resultados[archivo_nombre]
                        original_col = row.get('origen_columna', '')
                        original_monto = row['monto']
                        col_changed = nueva_nat.lower() != original_col
                        monto_changed = (nuevo_monto != original_monto) if pd.notna(original_monto) else (nuevo_monto != 0)

                        if col_changed or monto_changed:
                            sel_clave = st.session_state.get(f"sel_{idx}", '')
                            codigo_final = sel_clave if sel_clave not in ('', '➕ NUEVA CATEGORÍA', '🚫 NO INCLUIR') else ''
                            df_mod.at[idx, 'nombre_original'] = nuevo_nombre
                            df_mod.at[idx, 'nombre_revision_usuario'] = ''
                            df_mod.at[idx, 'origen_columna'] = nueva_nat.lower()
                            df_mod.at[idx, 'origen_columna_display'] = nueva_nat.lower()
                            df_mod.at[idx, 'monto'] = nuevo_monto
                            if codigo_final:
                                df_mod.at[idx, 'codigo_clasificado'] = codigo_final
                            df_mod.at[idx, 'metodo'] = 'manual_revision'
                            df_mod.at[idx, 'confianza'] = 1.0
                            df_mod.at[idx, 'requiere_revision'] = False
                            df_mod.at[idx, 'tipo_revision'] = 'correccion_extraccion'
                            df_mod.at[idx, 'origen'] = 'Manual'
                            df_mod.at[idx, 'regla'] = 'manual_revision'
                            df_mod.at[idx, 'evidencia'] = 'Corrección manual de extracción'
                            if codigo_final:
                                _save_gold_standard(nuevo_nombre, row['codigo_original'], codigo_final, reviewer="manual_revision")
                            propagar_clasificacion_resultados(nuevo_nombre, codigo_final or df_mod.at[idx, 'codigo_clasificado'], 'manual_revision_propagada')
                            st.toast(f"'{nuevo_nombre[:35]}' corregida ✅", icon="✅")
                        else:
                            df_mod.at[idx, 'nombre_revision_usuario'] = nuevo_nombre
                            df_mod.at[idx, 'tipo_revision'] = 'visual'
                            st.toast(f"'{nuevo_nombre[:35]}' nombre visual actualizado ✏️", icon="✏️")
                        st.rerun()

            with c2:
                sugerido = row['codigo_clasificado']
                st.write(f"Sugerido: **{sugerido or '(ninguno)'}**")

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
                    nuevo_nombre_cat = st.text_input("Nombre de la categoría",
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
                        if nuevo_codigo and nuevo_nombre_cat:
                            nueva_entrada = {
                                'codigo_estandar': nuevo_codigo.strip().upper(),
                                'nombre_estandar': nuevo_nombre_cat.strip(),
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
                            st.toast(f"Nueva categoría '{nuevo_nombre_cat}' ({codigo_final}) creada ✨", icon="🆕")
                        else:
                            st.error("Debes ingresar código y nombre.")

                    elif seleccion == '🚫 NO INCLUIR':
                        st.session_state.resultados[archivo_nombre].at[idx, 'codigo_clasificado'] = '__EXCLUIR__'
                        st.session_state.resultados[archivo_nombre].at[idx, 'metodo'] = 'excluido_analista'
                        st.session_state.resultados[archivo_nombre].at[idx, 'confianza'] = 1.0
                        st.session_state.resultados[archivo_nombre].at[idx, 'requiere_revision'] = False
                        if "diccionario" in alcance:
                            st.session_state.diccionario.append({
                                'cuenta_original': _nombre_mostrar(row),
                                'codigo_estandar': '__EXCLUIR__',
                                'fuente': 'excluido_analista'
                            })
                            with open(BASE_DIR / 'diccionario.json', 'w', encoding='utf-8') as f:
                                json.dump(st.session_state.diccionario, f, ensure_ascii=False, indent=2)
                        propagar_clasificacion_resultados(row['nombre_original'], '__EXCLUIR__', 'excluido_analista_propagado')
                        st.session_state.lote_seleccion.discard(idx)
                        st.toast(f"'{_nombre_mostrar(row)[:35]}' excluida", icon="🚫")
                        st.rerun()

                    elif seleccion:
                        codigo_final = seleccion

                    if codigo_final:
                        st.session_state.resultados[archivo_nombre].at[idx, 'codigo_clasificado'] = codigo_final
                        st.session_state.resultados[archivo_nombre].at[idx, 'metodo'] = 'validacion_humana'
                        st.session_state.resultados[archivo_nombre].at[idx, 'confianza'] = 1.0
                        st.session_state.resultados[archivo_nombre].at[idx, 'requiere_revision'] = False
                        st.session_state.lote_seleccion.discard(idx)
                        _save_gold_standard(row['nombre_original'], row['codigo_original'], codigo_final)
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
                            st.toast(f"'{_nombre_mostrar(row)[:35]}' → {codigo_final} guardado 📚", icon="✅")
                        else:
                            st.toast(f"'{_nombre_mostrar(row)[:35]}' → {codigo_final} (solo este caso)", icon="✅")
                        propagar_clasificacion_resultados(row['nombre_original'], codigo_final, 'validacion_humana_propagada')
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
        ][['codigo_clasificado', 'codigo_original', 'nombre_original', 'nombre_revision_usuario', 'monto', 'metodo', 'confianza']].copy()

        det['nombre_visual'] = det['nombre_revision_usuario'].where(det['nombre_revision_usuario'] != '', det['nombre_original'])
        det['nombre_estandar'] = det['codigo_clasificado'].map(lambda c: catalogo_local.get(c, {}).get('nombre_estandar', c))
        detalle_completo = det[['codigo_clasificado', 'nombre_estandar', 'codigo_original', 'nombre_visual', 'monto', 'metodo', 'confianza']].copy()

        # Reconstrucción de la lógica de ordenamiento nativo
        detalle_completo = detalle_completo.sort_values(
            ['codigo_clasificado', 'monto'],
            key=lambda x: x.abs() if x.dtype.kind == 'f' else x,
            ascending=[True, False]
        )
        detalle_completo.columns = [
            'Código Estándar', 'Nombre Estándar',
            'Cód. Original', 'Nombre',
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
            candidatos['_nombre_display'] = candidatos['nombre_revision_usuario'].where(candidatos['nombre_revision_usuario'] != '', candidatos['nombre_original'])
            st.dataframe(candidatos[['_nombre_display', 'monto', 'codigo_clasificado']], use_container_width=True, hide_index=True)
        else:
            st.info("No se hallaron cuentas directas con el monto de la diferencia.")

    with tab_c:
        excluidas = df[df['codigo_clasificado'] == '__EXCLUIR__'].copy()
        if not excluidas.empty:
            excluidas['_nombre_display'] = excluidas['nombre_revision_usuario'].where(excluidas['nombre_revision_usuario'] != '', excluidas['nombre_original'])
            st.dataframe(excluidas[['_nombre_display', 'monto']], use_container_width=True, hide_index=True)


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


def _tab_aprendizaje():
    st.subheader("🧠 Autoaprendizaje — Gold Standard")
    try:
        builder = GoldBuilder()
        stats = builder.statistics()
        top = builder.top_learned()
        conflicts = builder.find_conflicts()
        builder.close()
    except Exception as e:
        st.error(f"No se pudieron cargar estadísticas: {e}")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("Registros aprendidos", stats["total_records"])
    c2.metric("Coincidencias exactas", stats["exact_hits"])
    c3.metric("Cuentas con conflicto", stats["conflicts"])

    if stats["total_records"] > 0:
        st.subheader("🏆 Top 20 cuentas más aprendidas")
        top_df = pd.DataFrame(top)
        top_df.columns = ["Cuenta", "Código Final", "Veces Usada", "Último Uso"]
        top_df["Último Uso"] = top_df["Último Uso"].str[:19]
        st.dataframe(top_df, use_container_width=True, hide_index=True)

    if conflicts:
        st.subheader("⚔️ Cuentas con conflicto (múltiples códigos asignados)")
        cf_df = pd.DataFrame(conflicts)
        cf_df.columns = ["Cuenta", "Códigos Distintos", "Códigos", "Versiones"]
        st.dataframe(cf_df, use_container_width=True, hide_index=True)
    else:
        st.info("No hay cuentas con conflictos de clasificación.")

    st.divider()
    st.subheader("🔄 Promoción al Gold Standard (Learning Loop)")
    st.caption(
        "Promueve las revisiones humanas (gold_records) a una base RUNTIME separada "
        "(`gold_standard_runtime.db`). La base del benchmark (2660/2662) NO se modifica. "
        "Ver `reports/product/P1_learning_loop_design.md`."
    )
    pc1, pc2, pc3 = st.columns(3)
    with pc1:
        if st.button("🔍 Previsualizar promoción", use_container_width=True):
            try:
                res = promover_revisiones(dry_run=True)
                st.success(
                    f"Candidatos: {res.candidates} · Promovibles: {res.promotable} · "
                    f"Conflictos: {res.conflicts} · Duplicados: {res.duplicates} · "
                    f"Reservados (total): {res.reserved}"
                )
                if res.conflict_details:
                    st.warning("Conflictos (se omiten de la promoción):")
                    for c in res.conflict_details:
                        st.write(f"- {c['name']}: candidato={c['candidate_code']} gold={c['existing_codes']}")
            except Exception as e:
                st.error(f"No se pudo previsualizar: {e}")
    with pc2:
        if st.button("✅ Aplicar a runtime", use_container_width=True):
            try:
                res = promover_revisiones(dry_run=False)
                st.success(
                    f"Promovidos: {res.promoted} · Conflictos omitidos: {res.conflicts} · "
                    f"Duplicados: {res.duplicates} · Reservados: {res.reserved}"
                )
            except Exception as e:
                st.error(f"No se pudo aplicar: {e}")
    with pc3:
        if st.button("🧹 Borrar runtime", use_container_width=True):
            try:
                rt = RuntimeGoldStorage()
                rt.close()
                rt.path.unlink(missing_ok=True)
                st.success("Runtime eliminado. El benchmark sigue intacto.")
            except Exception as e:
                st.error(f"No se pudo borrar: {e}")


def _km_usuario() -> str:
    return str(st.session_state.get("km_usuario", "analista"))


def _tab_knowledge_manager() -> None:
    """🧠 Knowledge Manager (P5).

    Administra EXCLUSIVAMENTE ``gold_standard_runtime.db`` a través de
    ``RuntimeManager`` (única capa de persistencia). La UI no ejecuta SQL ni
    abre conexiones SQLite. El benchmark (``gold_standard.db``) nunca se escribe.
    Toda acción (promover, rechazar, rollback) requiere aprobación explícita.
    """
    st.subheader("🧠 Knowledge Manager")
    st.caption(
        "Administra exclusivamente `gold_standard_runtime.db` vía `RuntimeManager`. "
        "El benchmark (`gold_standard.db`) permanece intacto. Eventos auditables: "
        "PROMOTE / ROLLBACK / REJECT. Estado del candidato: PENDING / APPROVED / "
        "REJECTED / ROLLED_BACK."
    )

    runtime_path = BASE_DIR / "gold_standard_runtime.db"
    gold_path = BASE_DIR / "gold_standard.db"
    rm = RuntimeManager(runtime_path)

    tab_pend, tab_conf, tab_run, tab_hist, tab_stat = st.tabs(
        ["📥 Promociones pendientes", "⚔️ Conflictos", "🗃️ Runtime",
         "📜 Historial", "📊 Estadísticas"]
    )

    with tab_pend:
        _km_pendientes(rm, gold_path)
    with tab_conf:
        _km_conflictos(rm, gold_path)
    with tab_run:
        _km_runtime(rm)
    with tab_hist:
        _km_historial(rm)
    with tab_stat:
        _km_estadisticas(rm, gold_path)


def _km_pendientes(rm: RuntimeManager, gold_path: Path) -> None:
    """TAB 1 — Promociones pendientes: aprobar/rechazar selección múltiple."""
    st.markdown("#### 📥 Promociones pendientes")
    try:
        pend = rm.get_pending_promotions(gold_path)
    except Exception as e:  # noqa: BLE001
        st.error(f"No se pudieron cargar los candidatos: {e}")
        return

    if not pend:
        st.info("No hay candidatos pendientes de promoción en `gold_records`.")
        return

    df = pd.DataFrame([{
        "Cuenta": p["account_name"],
        "Código sugerido": p["candidate_code"],
        "Origen": p["origen"] or "—",
        "Confianza": p["confidence"],
        "Fecha": (p["fecha"] or "")[:19],
        "Estado": p["state"],
        "Clasificación": p["status"],
        "source_record_id": p["source_record_id"],
    } for p in pend])
    df.insert(0, "Seleccionar", False)

    st.caption(
        "Estado actual derivado de `promotion_history`. Solo los candidatos "
        "PENDING se promueven; duplicados y conflictos se omiten automáticamente."
    )

    edited = st.data_editor(
        df,
        hide_index=True,
        disabled=[c for c in df.columns if c not in ("Seleccionar",)],
        use_container_width=True,
        key="km_pend_editor",
        column_config={
            "Seleccionar": st.column_config.CheckboxColumn("Seleccionar", default=False),
            "Confianza": st.column_config.NumberColumn("Confianza", format="%.2f"),
            "source_record_id": None,
        },
    )

    if not isinstance(edited, pd.DataFrame):
        edited = df
    seleccionadas = edited[edited["Seleccionar"] == True] if "Seleccionar" in edited.columns else edited.iloc[0:0]  # noqa: E712
    ids = [int(r["source_record_id"]) for _, r in seleccionadas.iterrows()]

    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        aprobar = st.button("✅ Aprobar selección", use_container_width=True)
    with c2:
        rechazar = st.button("❌ Rechazar selección", use_container_width=True)
    with c3:
        st.caption(f"{len(ids)} seleccionadas · usuario: `{_km_usuario()}`")

    if aprobar:
        if not ids:
            st.warning("Selecciona al menos una fila para aprobar.")
        else:
            try:
                res = rm.promote(gold_path, dry_run=False, source_ids=ids, usuario=_km_usuario())
                st.success(
                    f"Promovidos: {res.promoted} · Conflictos omitidos: {res.conflicts} · "
                    f"Duplicados: {res.duplicates} · Reservados: {res.reserved}"
                )
            except Exception as e:  # noqa: BLE001
                st.error(f"No se pudo aprobar la selección: {e}")
    if rechazar:
        if not ids:
            st.warning("Selecciona al menos una fila para rechazar.")
        else:
            try:
                n = 0
                for _, r in seleccionadas.iterrows():
                    rm.reject_promotion(
                        source_record_id=int(r["source_record_id"]),
                        account_name=str(r["Cuenta"]),
                        candidate_code=str(r["Código sugerido"]),
                        usuario=_km_usuario(),
                    )
                    n += 1
                st.success(f"Rechazos registrados (REJECT): {n}")
            except Exception as e:  # noqa: BLE001
                st.error(f"No se pudieron registrar los rechazos: {e}")


def _km_conflictos(rm: RuntimeManager, gold_path: Path) -> None:
    """TAB 2 — Conflictos runtime vs gold."""
    st.markdown("#### ⚔️ Conflictos (runtime vs gold)")
    try:
        conf = rm.get_conflicts(gold_path)
    except Exception as e:  # noqa: BLE001
        st.error(f"No se pudieron cargar los conflictos: {e}")
        return

    if not conf:
        st.info("No hay conflictos entre runtime y gold oficial.")
        return

    st.caption(
        "Misma cuenta normalizada con código distinto en runtime y gold. "
        "Resolver: mantener runtime (no hacer nada) o rollback (prevalece gold). "
        "`gold_standard.db` nunca se modifica."
    )
    df = pd.DataFrame([{
        "Cuenta": c["account_name"],
        "Código runtime": c["codigo_runtime"],
        "Código gold": c["codigo_gold"],
    } for c in conf])
    st.dataframe(df, use_container_width=True, hide_index=True)

    for c in conf:
        with st.expander(
            f"⚔️ {c['account_name']} — runtime {c['codigo_runtime']} vs gold {c['codigo_gold']}"
        ):
            hist = rm.get_history(account_name=c["account_name"], limit=20)
            if hist:
                st.dataframe(pd.DataFrame([{
                    "Fecha": (h["fecha"] or "")[:19],
                    "Usuario": h["usuario"],
                    "Acción": h["accion"],
                    "Estado": h["state"],
                    "Código": h["codigo_nuevo"] or h["codigo_anterior"] or "",
                    "Comentario": h["comentario"],
                } for h in hist]), use_container_width=True, hide_index=True)
            else:
                st.caption("Sin historial para esta cuenta.")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("🔁 Rollback (prevalece gold)", key=f"km_rb_{c['runtime_id']}"):
                    try:
                        ok = rm.rollback(
                            int(c["runtime_id"]), usuario=_km_usuario(),
                            comentario="Conflicto resuelto: prevalece gold",
                        )
                        st.success("Rollback aplicado y registrado (ROLLBACK)." if ok else "No se pudo aplicar el rollback.")
                    except Exception as e:  # noqa: BLE001
                        st.error(f"Error en rollback: {e}")
            with c2:
                if st.button("✓ Mantener runtime", key=f"km_keep_{c['runtime_id']}"):
                    st.info("Runtime mantenido (no se modifica nada).")


def _km_runtime(rm: RuntimeManager) -> None:
    """TAB 3 — Cuentas activas del runtime: filtro, buscador y rollback."""
    st.markdown("#### 🗃️ Runtime (`gold_standard_runtime.db`)")
    if not rm.path.exists():
        st.info("El runtime aún no existe. Promueve candidatos desde la pestaña 'Promociones pendientes'.")
        return
    try:
        rows = rm.load_runtime()
    except Exception as e:  # noqa: BLE001
        st.error(f"No se pudieron cargar las cuentas del runtime: {e}")
        return
    if not rows:
        st.info("El runtime existe pero no tiene cuentas activas.")
        return

    df = pd.DataFrame([{
        "id": r["id"],
        "Cuenta": r["nombre_cuenta"],
        "Código": r["codigo_estandar"],
        "Normalizado": r["normalized"],
        "Reviewer": r["reviewer"] or "—",
        "Fecha": (r["promoted_at"] or "")[:19],
    } for r in rows])

    q = st.text_input("🔍 Buscar cuenta o código", key="km_runtime_q")
    if q:
        ql = q.lower().strip()
        df = df[df["Cuenta"].str.lower().str.contains(ql)
                | df["Código"].str.lower().str.contains(ql)
                | df["Normalizado"].str.lower().str.contains(ql)]

    prefijos = sorted({str(c).split(".")[0] for c in df["Código"]})
    filtro = st.selectbox("Filtrar por prefijo de código", ["todos"] + prefijos, key="km_runtime_filtro")
    if filtro != "todos":
        df = df[df["Código"].astype(str).str.startswith(filtro)]

    st.caption(f"{len(df)} cuentas activas en runtime.")
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("**Rollback / Eliminar**")
    st.caption("Rollback elimina la entrada de runtime y registra el evento ROLLBACK (prevalece gold).")
    options = {f"{r['Cuenta']} ({r['Código']})": int(r["id"]) for _, r in df.iterrows()}
    if options:
        sel_label = st.selectbox("Cuenta", list(options), key="km_runtime_sel")
        confirm = st.checkbox("Confirmo el rollback de esta cuenta", key="km_runtime_confirm")
        if st.button("🗑️ Rollback", use_container_width=True, disabled=not confirm):
            try:
                ok = rm.rollback(options[sel_label], usuario=_km_usuario(), comentario="Rollback desde Knowledge Manager")
                st.success("Rollback aplicado y registrado." if ok else "No se pudo aplicar.")
            except Exception as e:  # noqa: BLE001
                st.error(f"Error en rollback: {e}")


def _km_historial(rm: RuntimeManager) -> None:
    """TAB 4 — Historial de promotion_history (solo lectura)."""
    st.markdown("#### 📜 Historial (`promotion_history`)")
    try:
        hist = rm.get_history(limit=500)
    except Exception as e:  # noqa: BLE001
        st.error(f"No se pudo leer el historial: {e}")
        return
    if not hist:
        st.info("Sin eventos registrados en `promotion_history`.")
        return

    df = pd.DataFrame([{
        "Promotion ID": h["promotion_id"][:8],
        "Fecha": (h["fecha"] or "")[:19],
        "Usuario": h["usuario"],
        "Acción": h["accion"],
        "Estado": h["state"],
        "Cuenta": h["account_name"],
        "Código": h["codigo_nuevo"] or h["codigo_anterior"] or "",
        "Comentario": h["comentario"],
    } for h in hist])

    q = st.text_input("🔍 Buscar en historial", key="km_hist_q")
    if q:
        ql = q.lower()
        df = df[df.apply(lambda r: ql in " ".join(str(v) for v in r), axis=1)]

    st.caption("Solo lectura. El historial nunca se borra.")
    st.dataframe(df, use_container_width=True, hide_index=True)


def _km_estadisticas(rm: RuntimeManager, gold_path: Path) -> None:
    """TAB 5 — Estadísticas del runtime y del historial."""
    st.markdown("#### 📊 Estadísticas")
    try:
        s = rm.get_runtime_statistics(gold_path)
    except Exception as e:  # noqa: BLE001
        st.error(f"No se pudieron calcular las estadísticas: {e}")
        return

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Runtime size", s["runtime_size"])
    c2.metric("Promociones (PROMOTE)", s["promotions"])
    c3.metric("Rechazos (REJECT)", s["rejects"])
    c4.metric("Rollback (ROLLBACK)", s["rollbacks"])
    c5.metric("Cobertura", f"{s['coverage']}%")

    st.caption(
        f"Gold oficial: {s['gold_size']} cuentas · Eventos en historial: "
        f"{s['history_events']} · Runtime: {s['runtime_size']} cuentas activas."
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
