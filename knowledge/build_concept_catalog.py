"""
Construye el Catálogo Maestro de Conceptos Contables a partir de los 78
conceptos detectados en semantic_clusters.json.

NO modifica pipeline. NO agrega regex.
"""

import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

REPORT_DIR = Path(__file__).resolve().parent.parent / "reports"
OUT_DIR = Path(__file__).resolve().parent

CLUSTER_PATH = REPORT_DIR / "semantic_clusters.json"
OUT_JSON = OUT_DIR / "concept_catalog.json"
OUT_MD = OUT_DIR / "concept_catalog.md"
OUT_XLSX = OUT_DIR / "concept_catalog.xlsx"

CMCC_MASTER = {
    "AC.01": {"name": "Efectivo y equivalentes al efectivo", "type": "ACTIVO"},
    "AC.02": {"name": "Otros activos financieros corrientes", "type": "ACTIVO"},
    "AC.03": {"name": "Deudores comerciales y otras cuentas por cobrar corrientes", "type": "ACTIVO"},
    "AC.04": {"name": "Cuentas por cobrar a entidades relacionadas corrientes", "type": "ACTIVO"},
    "AC.05": {"name": "Inventarios corrientes", "type": "ACTIVO"},
    "AC.06": {"name": "Activos biológicos corrientes", "type": "ACTIVO"},
    "AC.06S": {"name": "Semovientes", "type": "ACTIVO"},
    "AC.07": {"name": "Activos por impuestos corrientes", "type": "ACTIVO"},
    "ANC.01": {"name": "Propiedades, planta y equipo", "type": "ACTIVO"},
    "ANC.02": {"name": "Depreciación acumulada", "type": "ACTIVO"},
    "ANC.03": {"name": "Activos intangibles", "type": "ACTIVO"},
    "ANC.04": {"name": "Otros activos financieros no corrientes", "type": "ACTIVO"},
    "PC.01": {"name": "Cuentas por pagar comerciales", "type": "PASIVO"},
    "PC.02": {"name": "Préstamos y obligaciones financieras corrientes", "type": "PASIVO"},
    "PC.03": {"name": "Otros pasivos financieros corrientes", "type": "PASIVO"},
    "PC.04": {"name": "Cuentas por pagar a entidades relacionadas corrientes", "type": "PASIVO"},
    "PC.05": {"name": "Pasivos por impuestos corrientes", "type": "PASIVO"},
    "PC.06": {"name": "Remuneraciones y gastos de personal corrientes", "type": "PASIVO"},
    "PC.07": {"name": "Cuentas por pagar por adelantos de clientes", "type": "PASIVO"},
    "PC.08": {"name": "Otros pasivos no financieros corrientes", "type": "PASIVO"},
    "PNC.01": {"name": "Préstamos y obligaciones financieras no corrientes", "type": "PASIVO"},
    "PNC.03": {"name": "Otros pasivos financieros no corrientes", "type": "PASIVO"},
    "PNC.05": {"name": "Pasivos por impuestos no corrientes", "type": "PASIVO"},
    "PAT.01": {"name": "Capital emitido", "type": "PATRIMONIO"},
    "PAT.02": {"name": "Reservas", "type": "PATRIMONIO"},
    "PAT.03": {"name": "Resultados acumulados", "type": "PATRIMONIO"},
    "PAT.04": {"name": "Resultado del ejercicio", "type": "PATRIMONIO"},
    "ER.01": {"name": "Ingresos de actividades ordinarias", "type": "PERDIDA"},
    "ER.02": {"name": "Costo de ventas / Costo de explotación", "type": "PERDIDA"},
    "ER.04": {"name": "Gastos de administración", "type": "PERDIDA"},
    "ER.05": {"name": "Gastos de venta y distribución", "type": "PERDIDA"},
    "ER.07": {"name": "Depreciación y amortización", "type": "PERDIDA"},
    "ER.09": {"name": "Gastos financieros", "type": "PERDIDA"},
    "ER.10": {"name": "Impuesto a la renta", "type": "PERDIDA"},
    "ER.11": {"name": "Resultado neto", "type": "PERDIDA"},
}


def normalizar(nombre: str) -> str:
    nombre = nombre.lower().strip()
    nombre = unicodedata.normalize("NFKD", nombre)
    nombre = nombre.encode("ascii", "ignore").decode("ascii")
    nombre = re.sub(r"[^\w\s]", " ", nombre)
    nombre = re.sub(r"\s+", " ", nombre)
    return nombre.strip()


def extract_unique_words(families: list[str]) -> list[str]:
    """Extrae words significativos del conjunto de nombres de familia."""
    stop_words = frozenset({
        'total', 'subtotal', 'neto', 'de', 'la', 'el', 'del', 'los', 'las',
        'un', 'una', 'y', 'e', 'o', 'a', 'por', 'al', 'con', 'en', 'para',
        'su', 'que', 'lo', 'no', 'se', 'entre', 's', 'i', 'ii', 'iii', 'iv',
        'v', 'vi', 'vii', 'viii', 'ix', 'x',
    })
    words = set()
    for fname in families:
        norm = normalizar(fname)
        for w in norm.split():
            if w not in stop_words and len(w) > 2 and not re.match(r'^[\d.,]+$', w):
                words.add(w)
    return sorted(words, key=lambda w: (-sum(1 for f in families if w in normalizar(f)), -len(w)))


ABBREVIATIONS = {
    "caja": ["C", "Cja"],
    "bancos": ["C/C", "CC", "Cta Cte", "CTACTE", "Bco", "Bcos"],
    "clientes": ["CxC", "Cxc", "C x C", "Ct x Cob", "Deud.", "Deudores"],
    "proveedores": ["CxP", "Cxp", "C x P", "Ct x Pag", "Prov.", "Acreed."],
    "capital": ["Cap.", "Cap"],
    "remuneraciones": ["Rem.", "Remun.", "Sueld.", "Pers."],
    "honorarios": ["Hon.", "Honor."],
    "impuestos": ["I.", "Imp.", "IVA", "PPM", "SII"],
    "inventarios": ["Inv.", "Invent.", "Stock", "Exist.", "Merc."],
    "depreciacion": ["Depr.", "Deprec.", "Amort.", "D.A."],
    "gastos": ["Gtos", "Gtos.", "Gast."],
    "ingresos": ["Ing.", "Ingres."],
    "ventas": ["Vtas", "Vent.", "V."],
    "prestamos": ["Prést.", "Prst.", "Oblig."],
    "seguros": ["Seg."],
    "fletes": ["Fl."],
    "materiales": ["Mat.", "Mats.", "Mat. Prim."],
    "propiedad": ["PPE", "P.P.E.", "P y E", "Act. Fijo"],
    "maquinaria": ["Maq.", "Maqs.", "Equip."],
    "vehiculos": ["Veh.", "Vehíc."],
    "documentos": ["Doc.", "Dctos", "Docs.", "Let."],
    "correccion_monetaria": ["C.M.", "CM", "Reaj."],
    "margen": ["Mg.", "Mgn"],
    "intereses": ["Int.", "Ints."],
    "reservas": ["Res.", "Resv."],
    "dividendos": ["Div.", "Dvd.", "Ret."],
    "retencion": ["Ret.", "Rete."],
    "anticipo": ["Ant.", "Antic."],
    "resultado": ["Rdo.", "Res."],
    "utilidad": ["Ut.", "Util.", "Gan."],
    "perdida": ["Pérd.", "Pda."],
}

OCR_SUBSTITUTIONS = [
    (re.compile(r'0'), 'O'),
    (re.compile(r'1'), 'I'),
    (re.compile(r'5'), 'S'),
    (re.compile(r'8'), 'B'),
    (re.compile(r'rn'), 'm'),
    (re.compile(r'cl'), 'd'),
    (re.compile(r'vv'), 'w'),
    (re.compile(r'll'), 'ii'),
]


def generate_ocr_variants(word: str) -> list[str]:
    """Genera variantes OCR plausibles para una palabra."""
    variants = set()
    variants.add(word)
    for pat, repl in OCR_SUBSTITUTIONS:
        new = pat.sub(repl, word)
        if new != word:
            variants.add(new)
    # Espacios insertados
    if len(word) > 3:
        for i in range(2, len(word) - 1):
            variants.add(word[:i] + ' ' + word[i:])
    # Caracteres duplicados
    for i in range(len(word)):
        variants.add(word[:i] + word[i] + word[i:])
    return sorted(variants - {word})[:5]


COMMON_ERRORS: dict[str, list[str]] = {
    "bancos": ["bancos", "banc0s", "bcos", "bancoss"],
    "clientes": ["clentes", "clientes", "clietes", "clntes"],
    "proveedores": ["provedores", "proveedores", "proveedres", "proveed"],
    "impuestos": ["impestos", "impustos", "impstos", "impuestos"],
    "remuneraciones": ["remuneracion", "remunaraciones", "remune"],
    "depreciacion": ["depresacion", "depreciacion", "depresiacion"],
    "caja": ["caxa", "caja"],
    "capital": ["capìtal", "capiral", "capitai"],
    "gastos": ["gastos", "gast0s", "gstos"],
    "inventarios": ["inventarios", "inventariios", "invent"],
    "honorarios": ["honorarios", "honorariios", "honrarios"],
    "seguros": ["seguros", "segur0s", "sgros"],
    "fletes": ["fletes", "flet s", "flete"],
    "materiales": ["materiales", "matriales", "materiles"],
    "vehiculos": ["vehiculos", "vehicols", "vehic"],
    "maquinaria": ["maquinaria", "maquinara", "maquina"],
    "documentos": ["documentos", "documntos", "dctos"],
    "intereses": ["intereses", "interez", "intereces"],
    "construccion": ["construccion", "construcion", "contruccion"],
    "instalaciones": ["instalaciones", "instalacione", "instala"],
}

SAME_CODE_MERGE_BLACKLIST = {"POR_DEFINIR"}


PRIMARY_CODE_OVERRIDES = {
    "PROPIEDAD": "ANC.01",
    "DEPRECIACION": "ER.07",
    "BANCOS": "AC.01",
    "GASTOS": "ER.04",
    "IMPUESTOS": "PC.05",
    "PRESTAMOS": "PC.02",
    "DOCUMENTOS": "AC.04",
    "PROVEEDORES": "PC.01",
    "INVERSIONES": "ANC.04",
    "CLIENTES": "AC.03",
    "REMUNERACIONES": "PC.06",
    "INGRESOS": "ER.01",
    "MUEBLES": "ANC.01",
    "CREDITO_FISCAL": "AC.07",
    "SERVICIO": "ER.01",
    "INTERESES": "ER.09",
    "DIFERIDOS": "PC.08",
    "COSTOS": "ER.02",
    "MATERIALES": "AC.05",
    "RESERVAS": "PAT.02",
    "CAPITAL": "PAT.01",
    "INVENTARIOS": "AC.05",
    "UTILIDAD": "PAT.04",
    "PERDIDA": "ER.11",
    "CAJA": "AC.01",
    "ACUMULADO": "PAT.03",
    "ACTIVOS": "POR_DEFINIR",
    "ASESORIAS": "ER.04",
    "PROVISIONES": "PC.08",
    "GASTOS_VENTA": "ER.05",
    "GASTOS_ADMIN": "ER.04",
    "GASTOS_VIAJE": "ER.04",
    "GASTOS_MANTENCION": "ER.04",
    "GASTOS_BANCARIOS": "ER.09",
    "CORRECCION_MONETARIA": "ER.11",
    "HONORARIOS": "PC.06",
    "SEGUROS": "ER.04",
    "PASIVOS": "POR_DEFINIR",
    "ARRENDAMIENTO": "PC.03",
    "RETENCION": "PC.05",
    "FLETES": "ER.02",
    "INTANGIBLE": "ANC.03",
    "ANTICIPO": "AC.07",
    "OBLIGACIONES": "PC.02",
    "PATRIMONIO": "POR_DEFINIR",
    "CONSTRUCCION": "ANC.01",
    "INSTALACIONES": "ANC.01",
    "VEHICULOS": "ANC.01",
    "MAQUINARIA": "ANC.01",
    "MONEDA_EXTRANJERA": "AC.01",
    "COMUNICACIONES": "ER.04",
    "HERRAMIENTAS": "ANC.01",
    "CERTIFICACION": "ER.04",
    "CONTRIBUCION": "PC.05",
    "APORTE": "PAT.01",
    "DESCUENTO": "ER.04",
    "PRODUCTOS": "AC.05",
    "MARCAS": "ANC.03",
    "MARGEN": "ER.02",
    "CENTRALIZACION": "PC.06",
    "NO_CLASIFICADO": "POR_DEFINIR",
    "SOCIEDADES": "ANC.04",
    "ACCIONISTAS": "PAT.01",
    "CUENTAS_PAGAR_RELACIONADAS": "PC.04",
    "AGENCIA": "POR_DEFINIR",
    "CERTIFICACION": "ER.04",
    "CREDITO": "AC.07",
    "ARRENDAMIENTO_FINANCIERO": "PC.03",
}


def infer_primary_code(expected_codes: list[str], concept_name: str = "") -> str:
    """Elige el código CMCC primario de un concepto."""
    # Override por nombre de concepto
    if concept_name in PRIMARY_CODE_OVERRIDES:
        return PRIMARY_CODE_OVERRIDES[concept_name]
    clean = [c for c in expected_codes if c not in SAME_CODE_MERGE_BLACKLIST]
    if not clean:
        return "POR_DEFINIR"
    counter = Counter(clean)
    return counter.most_common(1)[0][0]


CONCEPT_TYPE_OVERRIDES = {
    "ACTIVOS": "ACTIVO",
    "PASIVOS": "PASIVO",
    "PATRIMONIO": "PATRIMONIO",
}


def infer_type(primary_code: str, concept_name: str = "") -> str:
    if concept_name in CONCEPT_TYPE_OVERRIDES:
        return CONCEPT_TYPE_OVERRIDES[concept_name]
    if primary_code in CMCC_MASTER:
        return CMCC_MASTER[primary_code]["type"]
    if primary_code == "POR_DEFINIR":
        return "MIXTO"
    prefix = primary_code.split(".")[0]
    type_map = {"AC": "ACTIVO", "ANC": "ACTIVO", "PC": "PASIVO", "PNC": "PASIVO", "PAT": "PATRIMONIO", "ER": "PERDIDA"}
    return type_map.get(prefix, "MIXTO")


def compute_confidence(expected_codes: list[str], family_count: int) -> str:
    clean = [c for c in expected_codes if c not in SAME_CODE_MERGE_BLACKLIST]
    unique = set(clean)
    if len(unique) == 1 and family_count >= 10:
        return "ALTA"
    if len(unique) <= 2 and family_count >= 5:
        return "ALTA"
    if len(unique) <= 3:
        return "MEDIA"
    return "BAJA"


def generate_synonyms(name: str) -> list[str]:
    """Genera sinónimos plausibles para el nombre del concepto."""
    mapping = {
        "PROPIEDAD": ["Propiedades, Planta y Equipo", "Activo Fijo", "PPE", "Inmuebles"],
        "DEPRECIACION": ["Depreciación y Amortización", "Deterioro", "Desgaste"],
        "BANCOS": ["Efectivo en Bancos", "Cuentas Corrientes", "Disponible Bancario"],
        "GASTOS": ["Gastos Operacionales", "Egresos", "Desembolsos"],
        "IMPUESTOS": ["Tributos", "Cargas Fiscales", "Obligaciones Tributarias"],
        "PRESTAMOS": ["Créditos", "Obligaciones Financieras", "Deuda Financiera"],
        "DOCUMENTOS": ["Efectos por Cobrar/Pagar", "Letras", "Pagares"],
        "PROVEEDORES": ["Acreedores", "Cuentas por Pagar", "Proveedores"],
        "INVERSIONES": ["Inversiones Financieras", "Colocaciones", "Participaciones"],
        "CLIENTES": ["Deudores", "Cuentas por Cobrar", "Deudores Comerciales"],
        "REMUNERACIONES": ["Sueldos", "Salarios", "Personal", "Gastos de Personal"],
        "INGRESOS": ["Ventas", "Facturación", "Ingresos Ordinarios"],
        "MUEBLES": ["Mobiliario", "Equipamiento", "Menaje"],
        "CREDITO_FISCAL": ["Crédito IVA", "IVA Crédito", "Impuesto Recuperable"],
        "SERVICIO": ["Servicios", "Prestación de Servicios"],
        "INTERESES": ["Intereses Financieros", "Gastos Financieros", "Comisiones"],
        "DIFERIDOS": ["Anticipados", "Prepagos", "Devengados"],
        "COSTOS": ["Costos de Explotación", "Costos Operacionales", "Costo de Ventas"],
        "MATERIALES": ["Insumos", "Suministros", "Materias Primas"],
        "RESERVAS": ["Reservas de Capital", "Utilidades Retenidas"],
        "CAPITAL": ["Capital Social", "Aporte de Capital", "Patrimonio"],
        "INVENTARIOS": ["Existencias", "Mercaderías", "Stock"],
        "UTILIDAD": ["Ganancia", "Resultado Positivo", "Beneficio"],
        "PERDIDA": ["Resultado Negativo", "Déficit", "Pérdida del Ejercicio"],
        "CAJA": ["Efectivo", "Disponible", "Caja General"],
        "ACUMULADO": ["Resultados Acumulados", "Utilidades Retenidas"],
        "ACTIVOS": ["Activos Totales", "Bienes"],
        "PASIVOS": ["Pasivos Totales", "Obligaciones"],
        "GASTOS_VENTA": ["Gastos de Venta", "Gastos Comerciales", "Gastos de Distribución"],
        "GASTOS_ADMIN": ["Gastos de Administración", "Gastos Generales"],
        "GASTOS_VIAJE": ["Viáticos", "Gastos de Representación", "Pasajes"],
        "GASTOS_MANTENCION": ["Gastos de Mantención", "Reparaciones", "Conservación"],
        "GASTOS_BANCARIOS": ["Gastos Bancarios", "Comisiones Bancarias", "Servicios Bancarios"],
        "CORRECCION_MONETARIA": ["Reajuste", "Actualización", "Corrección Monetaria"],
        "HONORARIOS": ["Honorarios Profesionales", "Servicios Profesionales"],
        "SEGUROS": ["Pólizas", "Coberturas", "Primas de Seguro"],
        "ARRENDAMIENTO": ["Arriendo", "Leasing", "Renting"],
        "RETENCION": ["Retenciones", "Retención Judicial"],
        "FLETES": ["Transporte", "Fletes", "Acarreos", "Carga"],
        "INTANGIBLE": ["Activos Intangibles", "Goodwill", "Plusvalía"],
        "ANTICIPO": ["Anticipos", "Adelantos", "Pagos Anticipados"],
        "OBLIGACIONES": ["Obligaciones Financieras", "Compromisos"],
        "PATRIMONIO": ["Capital Propio", "Recursos Propios"],
        "CONSTRUCCION": ["Obras Civiles", "Edificaciones"],
        "INSTALACIONES": ["Instalaciones Fijas", "Montajes"],
        "VEHICULOS": ["Vehículos Motorizados", "Flota Vehicular"],
        "MAQUINARIA": ["Maquinarias y Equipos", "Equipo Industrial"],
        "PROVISIONES": ["Provisiones", "Estimaciones", "Previsiones"],
        "ASOCIADAS": ["Empresas Relacionadas", "Filiales", "Coligadas"],
        "MONEDA_EXTRANJERA": ["Dólares", "Divisas", "Moneda Extranjera"],
        "COMUNICACIONES": ["Telecomunicaciones", "Gastos de Comunicación"],
        "HERRAMIENTAS": ["Herramientas Menores", "Utensilios"],
        "CERTIFICACION": ["Certificaciones", "Homologaciones"],
        "CONTRIBUCION": ["Contribuciones", "Aportes"],
        "APORTE": ["Aportes de Capital", "Aportes Socios"],
        "DESCUENTO": ["Descuentos", "Rebajas"],
        "PRODUCTOS": ["Productos Terminados", "Bienes"],
        "MARCAS": ["Marcas Comerciales", "Nombres de Marca"],
        "MARGEN": ["Margen Bruto", "Margen Operacional", "Margen de Explotación"],
        "CENTRALIZACION": ["Consolidación", "Centralización"],
        "ASESORIAS": ["Asesorías Profesionales", "Consultorías"],
        "SOCIEDADES": ["Sociedades Relacionadas", "Filiales"],
        "ACCIONISTAS": ["Socios", "Accionistas", "Partícipes"],
        "CUENTAS_PAGAR_RELACIONADAS": ["Partes Relacionadas", "Entidades Vinculadas"],
        "AGENCIA": ["Sucursales", "Agencias"],
        "CREDITO": ["Crédito", "Financiamiento"],
        "ARRENDAMIENTO_FINANCIERO": ["Leasing Financiero"],
        "NO_CLASIFICADO": ["Varios", "Otros", "No Asignado"],
    }
    return mapping.get(name, [])[:5]


def detect_duplicates(concepts: list[dict]) -> list[dict]:
    """Detecta conceptos duplicados usando similitud de familias."""
    dupes = []
    n = len(concepts)
    for i in range(n):
        for j in range(i + 1, n):
            c1, c2 = concepts[i], concepts[j]
            s1, s2 = set(c1["families"]), set(c2["families"])
            if not s1 or not s2:
                continue
            jaccard = len(s1 & s2) / len(s1 | s2)
            if jaccard > 0.5:
                dupes.append({
                    "concept_a": c1["concept_name"],
                    "id_a": c1["id"],
                    "concept_b": c2["concept_name"],
                    "id_b": c2["id"],
                    "jaccard_similarity": round(jaccard, 3),
                    "overlap_count": len(s1 & s2),
                    "recommendation": "MERGE" if jaccard > 0.7 else "REVIEW",
                })
    return dupes


def detect_merge_candidates(concepts: list[dict]) -> list[dict]:
    """Detecta conceptos que deberían fusionarse (mismo código, palabras clave similares)."""
    candidates = []
    for i, c1 in enumerate(concepts):
        for j, c2 in enumerate(concepts):
            if j <= i:
                continue
            code1 = infer_primary_code(c1["expected_codes"], c1["concept_name"])
            code2 = infer_primary_code(c2["expected_codes"], c2["concept_name"])
            if code1 == code2 and code1 not in SAME_CODE_MERGE_BLACKLIST:
                if c1["concept_name"] == c2["concept_name"]:
                    continue
                w1 = set(extract_unique_words(c1["families"]))
                w2 = set(extract_unique_words(c2["families"]))
                if not w1 or not w2:
                    continue
                word_jaccard = len(w1 & w2) / len(w1 | w2)
                if word_jaccard > 0.3:
                    candidates.append({
                        "concept_a": c1["concept_name"],
                        "id_a": c1["id"],
                        "concept_b": c2["concept_name"],
                        "id_b": c2["id"],
                        "common_code": code1,
                        "word_similarity": round(word_jaccard, 3),
                        "reason": f"Ambos mapean a {code1} con similitud léxica {word_jaccard:.1%}",
                        "recommendation": "MERGE" if word_jaccard > 0.5 else "REVIEW",
                    })
    return candidates


def detect_issues(concept: dict) -> list[str]:
    """Detecta problemas de calidad en un concepto."""
    issues = []
    if len(set(concept["expected_codes"])) > 3:
        issues.append("Demasiados códigos CMCC distintos (>3)")
    if concept["family_count"] > 50 and concept["total_count"] > 200:
        issues.append("Concepto muy amplio — considerar subdividir")
    names = [normalizar(f) for f in concept["families"]]
    noise_indicators = ["000", "111", "123", "999"]
    noise_count = sum(1 for n in names if any(ind in n for ind in noise_indicators))
    if noise_count > concept["family_count"] * 0.1:
        issues.append(f"Posible ruido OCR en {noise_count} familias")
    stop_words_noise = ["total", "subtotal", "suma", "periodo", "ejercicio", "acumulado hasta"]
    sw_count = sum(1 for n in names if any(sw in n for sw in stop_words_noise))
    if sw_count > concept["family_count"] * 0.3:
        issues.append(f"Posibles headers/fechas en {sw_count} familias")
    return issues


def build_description(concept_name: str, primary_code: str) -> str:
    """Genera descripción corta."""
    if primary_code in CMCC_MASTER:
        return CMCC_MASTER[primary_code]["name"]
    desc_map = {
        "PROPIEDAD": "Bienes raíces, edificios, terrenos, construcciones y activos fijos",
        "DEPRECIACION": "Depreciación, amortización y deterioro de activos",
        "BANCOS": "Disponible en cuentas corrientes y otros instrumentos bancarios",
        "GASTOS": "Desembolsos operacionales y de gestión",
        "IMPUESTOS": "Obligaciones tributarias: IVA, Renta, PPM, contribuciones",
        "PRESTAMOS": "Obligaciones financieras con bancos y otras entidades",
        "DOCUMENTOS": "Letras, pagarés y efectos de comercio",
        "PROVEEDORES": "Acreedores comerciales por compra de bienes y servicios",
        "INVERSIONES": "Colocaciones financieras, fondos mutuos, acciones",
        "CLIENTES": "Deudores comerciales originados en ventas",
        "REMUNERACIONES": "Sueldos, salarios y beneficios del personal",
        "INGRESOS": "Ventas, servicios y otros ingresos ordinarios",
        "MUEBLES": "Mobiliario, equipamiento y útiles de oficina",
        "CREDITO_FISCAL": "IVA crédito fiscal y otros impuestos recuperables",
        "SERVICIO": "Prestación de servicios contabilizada",
        "INTERESES": "Gastos financieros por intereses y comisiones",
        "DIFERIDOS": "Gastos pagados por anticipado o ingresos diferidos",
        "COSTOS": "Costos directos e indirectos de producción o explotación",
        "MATERIALES": "Insumos, materias primas y suministros diversos",
        "RESERVAS": "Reservas de capital, legales, estatutarias o voluntarias",
        "CAPITAL": "Aportes de capital, capital social, capital emitido y pagado",
        "INVENTARIOS": "Existencias para la venta o consumo en producción",
        "UTILIDAD": "Ganancia o resultado positivo del período",
        "PERDIDA": "Resultado negativo o déficit del período",
        "CAJA": "Efectivo disponible en caja y valores análogos",
        "ACUMULADO": "Resultados de ejercicios anteriores retenidos",
        "ACTIVOS": "Conjunto de bienes y derechos de la empresa",
        "PASIVOS": "Conjunto de obligaciones y deudas de la empresa",
        "PATRIMONIO": "Capital propio y resultados acumulados",
        "GASTOS_VENTA": "Gastos asociados a la comercialización y distribución",
        "GASTOS_ADMIN": "Gastos de estructura administrativa y gestión",
        "GASTOS_VIAJE": "Viáticos, pasajes y gastos de representación",
        "GASTOS_MANTENCION": "Gastos de mantención y reparación de activos",
        "GASTOS_BANCARIOS": "Servicios y comisiones bancarias",
        "CORRECCION_MONETARIA": "Reajustes por inflación y actualización de valores",
        "HONORARIOS": "Servicios profesionales independientes",
        "SEGUROS": "Coberturas de seguro y pólizas",
        "ARRENDAMIENTO": "Arriendos operativos y financieros",
        "RETENCION": "Retenciones judiciales o contractuales sobre pagos",
        "FLETES": "Gastos de transporte y fletes",
        "INTANGIBLE": "Activos intangibles: marcas, patentes, software",
        "ANTICIPO": "Anticipos a proveedores, empleados o terceros",
        "OBLIGACIONES": "Obligaciones financieras y compromisos de pago",
        "CONSTRUCCION": "Obras en curso y edificaciones",
        "INSTALACIONES": "Instalaciones técnicas y montajes",
        "VEHICULOS": "Flota de vehículos motorizados",
        "MAQUINARIA": "Maquinarias y equipos industriales",
        "PROVISIONES": "Estimaciones contables por obligaciones inciertas",
        "MONEDA_EXTRANJERA": "Operaciones en moneda extranjera",
        "CENTRALIZACION": "Centralización contable de operaciones",
        "ASESORIAS": "Servicios de asesoría y consultoría",
        "COMUNICACIONES": "Gastos en telecomunicaciones",
        "HERRAMIENTAS": "Herramientas menores y utensilios",
        "MARCAS": "Propiedad industrial e intelectual",
        "MARGEN": "Margen sobre ventas o explotación",
        "APORTE": "Aportes de socios o accionistas",
        "DESCUENTO": "Descuentos comerciales o financieros",
        "PRODUCTOS": "Productos terminados o en proceso",
        "SOCIEDADES": "Inversiones en sociedades relacionadas",
        "ACCIONISTAS": "Cuentas corrientes con accionistas",
        "CUENTAS_PAGAR_RELACIONADAS": "Obligaciones con empresas del grupo",
        "AGENCIA": "Sucursales, agencias o establecimientos",
        "CERTIFICACION": "Certificaciones y homologaciones técnicas",
        "CONTRIBUCION": "Contribuciones especiales o gravámenes",
        "CREDITO": "Créditos fiscales o financieros",
        "ARRENDAMIENTO_FINANCIERO": "Contratos de arrendamiento con opción de compra",
    }
    return desc_map.get(concept_name, "Concepto contable no clasificado")


def build_concept_catalog():
    with open(CLUSTER_PATH) as f:
        data = json.load(f)

    raw_concepts = data["concepts"]
    raw_concepts.sort(key=lambda c: -c["total_count"])

    catalog = []
    for idx, c in enumerate(raw_concepts, 1):
        cid = f"CONCEPT_{idx:03d}"
        name = c["concept_name"]

        keywords = extract_unique_words(c["families"])
        primary_code = infer_primary_code(c["expected_codes"], name)
        ctype = infer_type(primary_code, name)
        confidence = compute_confidence(c["expected_codes"], c["family_count"])
        description = build_description(name, primary_code)
        synonyms = generate_synonyms(name)
        issues = detect_issues(c)

        entry = {
            "id": cid,
            "name": name,
            "canonical_name": description,
            "type": ctype,
            "expected_cmcc_code": primary_code,
            "all_cmcc_codes": sorted(set(c["expected_codes"])) if c["expected_codes"] else [],
            "confidence": confidence,
            "description": description,
            "keywords": keywords[:20],
            "synonyms": synonyms,
            "abbreviations": list(ABBREVIATIONS.get(name.lower(), []))[:10],
            "ocr_variants": [],
            "common_errors": COMMON_ERRORS.get(name.lower(), []),
            "related_concepts": [],
            "frequency": c["total_count"],
            "family_count": c["family_count"],
            "pct_of_gap": c["pct"],
            "cumulative_pct": c["cumulative_pct"],
            "families": c["families"],
            "merge_with": [],
            "is_duplicate": False,
            "needs_split": any("Demasiados códigos CMCC" in iss for iss in issues) or any("Concepto muy amplio" in iss for iss in issues),
            "issues": issues,
        }
        catalog.append(entry)

    # Asignar relacionados: conceptos que comparten código CMCC
    code_to_concepts: dict[str, list[int]] = defaultdict(list)
    for i, entry in enumerate(catalog):
        for code in entry["all_cmcc_codes"]:
            code_to_concepts[code].append(i)

    for i, entry in enumerate(catalog):
        related_ids = set()
        for code in entry["all_cmcc_codes"]:
            for j in code_to_concepts.get(code, []):
                if i != j:
                    related_ids.add(j)
        entry["related_concepts"] = [catalog[j]["id"] for j in sorted(related_ids)][:5]

    # Generar OCR variants para el nombre
    for entry in catalog:
        name_norm = normalizar(entry["name"])
        variants = generate_ocr_variants(name_norm)
        entry["ocr_variants"] = variants
        base_keys = [k for k in entry["keywords"][:3]]
        for bk in base_keys:
            entry["ocr_variants"].extend(generate_ocr_variants(bk))
        entry["ocr_variants"] = list(set(entry["ocr_variants"]))[:10]

    # Duplicados
    duplicates = detect_duplicates(raw_concepts)
    duplicate_names = set()
    for d in duplicates:
        duplicate_names.add(d["concept_a"])
        duplicate_names.add(d["concept_b"])
    for entry in catalog:
        if entry["name"] in duplicate_names:
            entry["is_duplicate"] = True
            for d in duplicates:
                if d["concept_a"] == entry["name"]:
                    entry["merge_with"].append(d["id_b"])
                elif d["concept_b"] == entry["name"]:
                    entry["merge_with"].append(d["id_a"])

    # Merge candidates
    merge_candidates = detect_merge_candidates(raw_concepts)
    for mc in merge_candidates:
        for entry in catalog:
            if entry["name"] == mc["concept_a"]:
                if mc["id_b"] not in entry["merge_with"]:
                    entry["merge_with"].append(mc["id_b"])

    output = {
        "metadata": {
            "version": "1.0",
            "generated_date": "2026-07-22",
            "total_concepts": len(catalog),
            "source": "reports/semantic_clusters.json",
            "concepts_with_confidence_alta": sum(1 for c in catalog if c["confidence"] == "ALTA"),
            "concepts_with_confidence_media": sum(1 for c in catalog if c["confidence"] == "MEDIA"),
            "concepts_with_confidence_baja": sum(1 for c in catalog if c["confidence"] == "BAJA"),
            "concepts_needing_split": sum(1 for c in catalog if c["needs_split"]),
            "concepts_flagged_duplicate": sum(1 for c in catalog if c["is_duplicate"]),
            "total_with_issues": sum(1 for c in catalog if c["issues"]),
        },
        "concepts": catalog,
        "duplicates": duplicates,
        "merge_candidates": merge_candidates,
        "issues": [
            {"concept_id": c["id"], "concept_name": c["name"], "issues": c["issues"]}
            for c in catalog if c["issues"]
        ],
    }

    with open(OUT_JSON, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    guardar_md(output)
    guardar_xlsx(output)

    print(f"Catálogo generado: {len(catalog)} conceptos")
    print(f"  ALTA confianza: {output['metadata']['concepts_with_confidence_alta']}")
    print(f"  MEDIA: {output['metadata']['concepts_with_confidence_media']}")
    print(f"  BAJA: {output['metadata']['concepts_with_confidence_baja']}")
    print(f"  Necesitan subdivisión: {output['metadata']['concepts_needing_split']}")
    print(f"  Con duplicados: {output['metadata']['concepts_flagged_duplicate']}")
    print(f"  Con problemas: {output['metadata']['total_with_issues']}")
    print(f"  Pares duplicados: {len(duplicates)}")
    print(f"  Candidatos a fusión: {len(merge_candidates)}")


def guardar_md(output: dict):
    lines = [
        "# Catálogo Maestro de Conceptos Contables\n",
        f"**Versión:** {output['metadata']['version']} — {output['metadata']['generated_date']}  \n",
        f"**Fuente:** {output['metadata']['source']}  \n",
        f"**Total conceptos:** {output['metadata']['total_concepts']}\n",
        "---\n",
        "## Metadatos\n",
        "| Métrica | Valor |",
        "|---|---|",
        f"| Total conceptos | {output['metadata']['total_concepts']} |",
        f"| Confianza ALTA | {output['metadata']['concepts_with_confidence_alta']} |",
        f"| Confianza MEDIA | {output['metadata']['concepts_with_confidence_media']} |",
        f"| Confianza BAJA | {output['metadata']['concepts_with_confidence_baja']} |",
        f"| Necesitan subdivisión | {output['metadata']['concepts_needing_split']} |",
        f"| Con duplicados | {output['metadata']['concepts_flagged_duplicate']} |",
        f"| Con problemas de calidad | {output['metadata']['total_with_issues']} |",
        f"| Pares duplicados | {len(output['duplicates'])} |",
        f"| Candidatos a fusión | {len(output['merge_candidates'])} |",
        "",
        "## Catálogo Completo\n",
        "| ID | Concepto | Cuentas | Familias | % Gap | % Acum | Código Primario | Tipo | Confianza | Problemas |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for c in output["concepts"]:
        issues_flag = "⚠️" if c["issues"] else ""
        dupe_flag = "🔁" if c["is_duplicate"] else ""
        split_flag = "✂️" if c["needs_split"] else ""
        flags = f"{issues_flag}{dupe_flag}{split_flag}"
        lines.append(
            f"| {c['id']} | {c['name']} | {c['frequency']} | {c['family_count']} | "
            f"{c['pct_of_gap']}% | {c['cumulative_pct']}% | {c['expected_cmcc_code']} | "
            f"{c['type']} | {c['confidence']} | {flags} |"
        )

    lines += [
        "",
        "## Duplicados Detectados\n",
        "| Concepto A | ID A | Concepto B | ID B | Jaccard | Overlap | Recomendación |",
        "|---|---|---|---|---|---|---|",
    ]
    for d in output["duplicates"]:
        lines.append(
            f"| {d['concept_a']} | {d['id_a']} | {d['concept_b']} | {d['id_b']} | "
            f"{d['jaccard_similarity']} | {d['overlap_count']} | {d['recommendation']} |"
        )

    lines += [
        "",
        "## Candidatos a Fusión\n",
        "| Concepto A | ID A | Concepto B | ID B | Código Común | Sim. Léxica | Razón | Recomendación |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for mc in output["merge_candidates"]:
        lines.append(
            f"| {mc['concept_a']} | {mc['id_a']} | {mc['concept_b']} | {mc['id_b']} | "
            f"{mc['common_code']} | {mc['word_similarity']} | {mc['reason']} | {mc['recommendation']} |"
        )

    lines += [
        "",
        "## Problemas de Calidad\n",
        "| Concepto | ID | Problemas |",
        "|---|---|---|",
    ]
    for iss in output["issues"]:
        issues_str = "; ".join(iss["issues"])
        lines.append(f"| {iss['concept_name']} | {iss['concept_id']} | {issues_str} |")

    lines += [
        "",
        "---\n*Generated by knowledge/build_concept_catalog.py*",
    ]
    with open(OUT_MD, "w") as f:
        f.write("\n".join(lines))


def guardar_xlsx(output: dict):
    import pandas as pd

    with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as writer:
        # Hoja Catálogo
        rows = []
        for c in output["concepts"]:
            rows.append({
                "ID": c["id"],
                "Concepto": c["name"],
                "Descripción": c["description"],
                "Tipo": c["type"],
                "Código Primario": c["expected_cmcc_code"],
                "Todos los Códigos": ", ".join(c["all_cmcc_codes"]),
                "Confianza": c["confidence"],
                "Keywords": ", ".join(c["keywords"][:10]),
                "Sinónimos": ", ".join(c["synonyms"][:5]),
                "Frecuencia": c["frequency"],
                "Familias": c["family_count"],
                "% Gap": c["pct_of_gap"],
                "% Acumulado": c["cumulative_pct"],
                "Abreviatura": ", ".join(c["abbreviations"][:5]),
                "Errores Comunes": ", ".join(c["common_errors"][:5]),
                "OCR Variants": ", ".join(c["ocr_variants"][:5]),
                "Requiere Split": "Sí" if c["needs_split"] else "No",
                "Es Duplicado": "Sí" if c["is_duplicate"] else "No",
                "Problemas": "; ".join(c["issues"]),
            })
        pd.DataFrame(rows).to_excel(writer, sheet_name="Catálogo", index=False)

        # Hoja Duplicados
        if output["duplicates"]:
            pd.DataFrame(output["duplicates"]).to_excel(writer, sheet_name="Duplicados", index=False)

        # Hoja Merge Candidatos
        if output["merge_candidates"]:
            pd.DataFrame(output["merge_candidates"]).to_excel(writer, sheet_name="Fusiones", index=False)

        # Hoja Problemas
        if output["issues"]:
            pd.DataFrame(output["issues"]).to_excel(writer, sheet_name="Problemas", index=False)

        # Hoja Resumen
        m = output["metadata"]
        summary = [
            {"Métrica": "Versión", "Valor": m["version"]},
            {"Métrica": "Fecha", "Valor": m["generated_date"]},
            {"Métrica": "Total Conceptos", "Valor": m["total_concepts"]},
            {"Métrica": "Confianza ALTA", "Valor": m["concepts_with_confidence_alta"]},
            {"Métrica": "Confianza MEDIA", "Valor": m["concepts_with_confidence_media"]},
            {"Métrica": "Confianza BAJA", "Valor": m["concepts_with_confidence_baja"]},
            {"Métrica": "Requieren Split", "Valor": m["concepts_needing_split"]},
            {"Métrica": "Duplicados", "Valor": m["concepts_flagged_duplicate"]},
            {"Métrica": "Con Problemas", "Valor": m["total_with_issues"]},
            {"Métrica": "Pares Duplicados", "Valor": len(output["duplicates"])},
            {"Métrica": "Candidatos Fusión", "Valor": len(output["merge_candidates"])},
        ]
        pd.DataFrame(summary).to_excel(writer, sheet_name="Resumen", index=False)


if __name__ == "__main__":
    build_concept_catalog()
