"""
experiments/pilot_coverage/formats/expected_ground_truth.py

Definición formal e independiente del Ground Truth esperado para los fixtures sintéticos de formatos.
Los resultados esperados se definen a partir de los datos exactos con que fueron construidos,
sin depender de la salida de los extractores.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ExpectedAccount:
    codigo: Optional[str]
    nombre: str
    monto: Optional[float]
    signo: int  # 1 positivo, -1 negativo, 0 cero / neutro
    es_total: bool = False
    seccion: Optional[str] = None  # 'activo', 'pasivo', 'patrimonio', 'resultado'
    origen_columna: Optional[str] = None
    montos_periodos: Dict[str, float] = field(default_factory=dict)
    columnas_8col: Dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 1. Paralelo con códigos (01_paralelo_activo_pasivo.pdf)
# ---------------------------------------------------------------------------
GROUND_TRUTH_PARALELO_CON_CODIGO: List[ExpectedAccount] = [
    # Activos (Izquierda)
    ExpectedAccount(codigo="110101", nombre="Caja", monto=500000.0, signo=1, seccion="activo"),
    ExpectedAccount(codigo="110102", nombre="Banco de Chile", monto=1200000.0, signo=1, seccion="activo"),
    ExpectedAccount(codigo="110201", nombre="Clientes Nacionales", monto=800000.0, signo=1, seccion="activo"),
    ExpectedAccount(codigo="120101", nombre="Maquinarias y Equipos", monto=5000000.0, signo=1, seccion="activo"),
    ExpectedAccount(codigo=None, nombre="TOTAL ACTIVO", monto=7500000.0, signo=1, es_total=True, seccion="activo"),
    # Pasivos y Patrimonio (Derecha)
    ExpectedAccount(codigo="210101", nombre="Proveedores Nacionales", monto=500000.0, signo=1, seccion="pasivo"),
    ExpectedAccount(codigo="210201", nombre="Cuentas por Pagar Comerciales", monto=700000.0, signo=1, seccion="pasivo"),
    ExpectedAccount(codigo="210301", nombre="Retenciones por Pagar", monto=300000.0, signo=1, seccion="pasivo"),
    ExpectedAccount(codigo="310101", nombre="Capital Pagado", monto=6000000.0, signo=1, seccion="patrimonio"),
    ExpectedAccount(codigo=None, nombre="TOTAL PASIVO Y PATRIMONIO", monto=7500000.0, signo=1, es_total=True, seccion="pasivo"),
]

# ---------------------------------------------------------------------------
# 1B. Paralelo sin códigos (01b_paralelo_sin_codigo.pdf)
# ---------------------------------------------------------------------------
GROUND_TRUTH_PARALELO_SIN_CODIGO: List[ExpectedAccount] = [
    ExpectedAccount(codigo=None, nombre="Caja y Bancos", monto=1700000.0, signo=1, seccion="activo"),
    ExpectedAccount(codigo=None, nombre="Deudores por Ventas", monto=800000.0, signo=1, seccion="activo"),
    ExpectedAccount(codigo=None, nombre="Activo Fijo Neto", monto=5000000.0, signo=1, seccion="activo"),
    ExpectedAccount(codigo=None, nombre="Proveedores Varios", monto=1200000.0, signo=1, seccion="pasivo"),
    ExpectedAccount(codigo=None, nombre="Impuestos por Pagar", monto=300000.0, signo=1, seccion="pasivo"),
    ExpectedAccount(codigo=None, nombre="Capital y Reservas", monto=6000000.0, signo=1, seccion="patrimonio"),
]

# ---------------------------------------------------------------------------
# 2. Ocho Columnas (02_ocho_columnas_control_negativo.pdf)
# ---------------------------------------------------------------------------
GROUND_TRUTH_8_COLUMNAS: List[ExpectedAccount] = [
    ExpectedAccount(
        codigo="110101", nombre="CAJA", monto=500000.0, signo=1, seccion="activo",
        columnas_8col={"debito": 1000000.0, "credito": 500000.0, "deudor": 500000.0, "acreedor": 0.0, "activo": 500000.0, "pasivo": 0.0, "perdida": 0.0, "ganancia": 0.0}
    ),
    ExpectedAccount(
        codigo="110201", nombre="BANCO DE CHILE", monto=2000000.0, signo=1, seccion="activo",
        columnas_8col={"debito": 3000000.0, "credito": 1000000.0, "deudor": 2000000.0, "acreedor": 0.0, "activo": 2000000.0, "pasivo": 0.0, "perdida": 0.0, "ganancia": 0.0}
    ),
    ExpectedAccount(
        codigo="210101", nombre="PROVEEDORES", monto=1000000.0, signo=1, seccion="pasivo",
        columnas_8col={"debito": 500000.0, "credito": 1500000.0, "deudor": 0.0, "acreedor": 1000000.0, "activo": 0.0, "pasivo": 1000000.0, "perdida": 0.0, "ganancia": 0.0}
    ),
    ExpectedAccount(
        codigo="410101", nombre="VENTAS", monto=2500000.0, signo=1, seccion="resultado",
        columnas_8col={"debito": 0.0, "credito": 2500000.0, "deudor": 0.0, "acreedor": 2500000.0, "activo": 0.0, "pasivo": 0.0, "perdida": 0.0, "ganancia": 2500000.0}
    ),
    ExpectedAccount(
        codigo="510101", nombre="COSTO DE VENTAS", monto=1000000.0, signo=1, seccion="resultado",
        columnas_8col={"debito": 1000000.0, "credito": 0.0, "deudor": 1000000.0, "acreedor": 0.0, "activo": 0.0, "pasivo": 0.0, "perdida": 1000000.0, "ganancia": 0.0}
    ),
]

# ---------------------------------------------------------------------------
# 3. Clasificado Vertical (03_clasificado_vertical.pdf)
# ---------------------------------------------------------------------------
GROUND_TRUTH_CLASIFICADO_VERTICAL: List[ExpectedAccount] = [
    ExpectedAccount(codigo="110101", nombre="Caja", monto=300000.0, signo=1, seccion="activo"),
    ExpectedAccount(codigo="110102", nombre="Banco", monto=1200000.0, signo=1, seccion="activo"),
    ExpectedAccount(codigo="110201", nombre="Clientes", monto=900000.0, signo=1, seccion="activo"),
    ExpectedAccount(codigo=None, nombre="TOTAL ACTIVO CIRCULANTE", monto=2400000.0, signo=1, es_total=True, seccion="activo"),
    ExpectedAccount(codigo="210101", nombre="Proveedores", monto=1000000.0, signo=1, seccion="pasivo"),
    ExpectedAccount(codigo="210201", nombre="Cuentas por Pagar", monto=400000.0, signo=1, seccion="pasivo"),
    ExpectedAccount(codigo=None, nombre="TOTAL PASIVO CIRCULANTE", monto=1400000.0, signo=1, es_total=True, seccion="pasivo"),
]

# ---------------------------------------------------------------------------
# 4. Comparativo 2 Períodos (04_comparativo_dos_periodos.pdf)
# ---------------------------------------------------------------------------
GROUND_TRUTH_COMPARATIVO: List[ExpectedAccount] = [
    ExpectedAccount(codigo="110101", nombre="Efectivo y equivalentes de efectivo", monto=1500000.0, signo=1, montos_periodos={"2024": 1500000.0, "2023": 1200000.0}),
    ExpectedAccount(codigo="110201", nombre="Deudores comerciales y otras cuentas", monto=850000.0, signo=1, montos_periodos={"2024": 850000.0, "2023": 920000.0}),
    ExpectedAccount(codigo="120101", nombre="Propiedades, planta y equipo", monto=4200000.0, signo=1, montos_periodos={"2024": 4200000.0, "2023": 4000000.0}),
    ExpectedAccount(codigo="210101", nombre="Cuentas por pagar comerciales", monto=1100000.0, signo=1, montos_periodos={"2024": 1100000.0, "2023": 950000.0}),
    ExpectedAccount(codigo="310101", nombre="Capital emitido", monto=5450000.0, signo=1, montos_periodos={"2024": 5450000.0, "2023": 5170000.0}),
]

# ---------------------------------------------------------------------------
# 5. Notas Cercanas a Montos (05_notas_cercanas_a_montos.pdf)
# ---------------------------------------------------------------------------
GROUND_TRUTH_NOTAS: List[ExpectedAccount] = [
    ExpectedAccount(codigo=None, nombre="Efectivo y equivalentes al efectivo", monto=2350000.0, signo=1),
    ExpectedAccount(codigo=None, nombre="Otros activos financieros corrientes", monto=540000.0, signo=1),
    ExpectedAccount(codigo=None, nombre="Deudores comerciales y otras cuentas por cobrar", monto=1890000.0, signo=1),
    ExpectedAccount(codigo=None, nombre="Cuentas por pagar comerciales y otras", monto=1250000.0, signo=1),
]

# ---------------------------------------------------------------------------
# 6. Descripciones Multilínea (06_descripciones_multilinea.pdf)
# ---------------------------------------------------------------------------
GROUND_TRUTH_MULTILINEA: List[ExpectedAccount] = [
    ExpectedAccount(
        codigo="110201",
        nombre="Cuentas por cobrar comerciales y otras cuentas por cobrar a entidades relacionadas del giro",
        monto=3450000.0, signo=1
    ),
    ExpectedAccount(
        codigo="120101",
        nombre="Propiedades de inversion destinadas a arrendamiento operativo de largo plazo segun contrato marco con empresas filiales",
        monto=8900000.0, signo=1
    ),
]

# ---------------------------------------------------------------------------
# 7. Negativos, Ceros y Vacías (07_negativos_ceros_vacias.pdf)
# ---------------------------------------------------------------------------
GROUND_TRUTH_NEGATIVOS_CEROS: List[ExpectedAccount] = [
    ExpectedAccount(codigo="110101", nombre="Caja", monto=100000.0, signo=1),
    ExpectedAccount(codigo="110102", nombre="Banco Saldo Negativo", monto=-450000.0, signo=-1),
    ExpectedAccount(codigo="110201", nombre="Cuenta Sin Movimiento", monto=0.0, signo=0),
    ExpectedAccount(codigo="120101", nombre="Depreciacion Acumulada", monto=-1200000.0, signo=-1),
    ExpectedAccount(codigo="310101", nombre="Perdida del Ejercicio", monto=-890000.0, signo=-1),
]

# ---------------------------------------------------------------------------
# 8. Excel XLSX (08_balance_excel.xlsx)
# ---------------------------------------------------------------------------
GROUND_TRUTH_EXCEL: List[ExpectedAccount] = [
    ExpectedAccount(codigo="110101", nombre="Caja Principal", monto=150000.0, signo=1, seccion="activo"),
    ExpectedAccount(codigo="110102", nombre="Banco Estado", monto=3200000.0, signo=1, seccion="activo"),
    ExpectedAccount(codigo="110201", nombre="Facturas por Cobrar", monto=1450000.0, signo=1, seccion="activo"),
    ExpectedAccount(codigo="210101", nombre="Facturas por Pagar", monto=980000.0, signo=1, seccion="pasivo"),
    ExpectedAccount(codigo="310101", nombre="Capital Social", monto=3820000.0, signo=1, seccion="patrimonio"),
]

# ---------------------------------------------------------------------------
# 9. Espaciado y Alineación Irregular (09_espaciado_y_alineacion.pdf)
# ---------------------------------------------------------------------------
GROUND_TRUTH_ESPACIADO: List[ExpectedAccount] = [
    ExpectedAccount(codigo="110101", nombre="Caja Chica Central", monto=75000.0, signo=1),
    ExpectedAccount(codigo="110201", nombre="Deudores Varios", monto=430000.0, signo=1),
    ExpectedAccount(codigo="210101", nombre="Proveedores", monto=505000.0, signo=1),
]

# ===========================================================================
# FIXTURES ADVERSARIALES OBLIGATORIOS (ENCARGO A4)
# ===========================================================================

# ADV 01: Bloques de diferente anchura (Izquierda estrecho 80mm, Derecha ancho 160mm)
GROUND_TRUTH_ADV_01_ANCHO_DISTINTO: List[ExpectedAccount] = [
    ExpectedAccount(codigo="110101", nombre="Caja Chica", monto=100000.0, signo=1, seccion="activo"),
    ExpectedAccount(codigo="110102", nombre="Banco", monto=900000.0, signo=1, seccion="activo"),
    ExpectedAccount(codigo="210101", nombre="Proveedores Nacionales de Insumos y Servicios Varios", monto=400000.0, signo=1, seccion="pasivo"),
    ExpectedAccount(codigo="210201", nombre="Obligaciones con Instituciones de Credito y Financiamiento", monto=600000.0, signo=1, seccion="pasivo"),
]

# ADV 02: Nombres largos solo en bloque izquierdo
GROUND_TRUTH_ADV_02_LARGOS_IZQ: List[ExpectedAccount] = [
    ExpectedAccount(codigo="110101", nombre="Fondos fijos y valores en custodia en tesoreria central", monto=250000.0, signo=1, seccion="activo"),
    ExpectedAccount(codigo="110201", nombre="Cuentas por cobrar comerciales a clientes del giro nacional", monto=750000.0, signo=1, seccion="activo"),
    ExpectedAccount(codigo="210101", nombre="Proveedores", monto=500000.0, signo=1, seccion="pasivo"),
    ExpectedAccount(codigo="310101", nombre="Capital", monto=500000.0, signo=1, seccion="patrimonio"),
]

# ADV 03: Nombres largos solo en bloque derecho
GROUND_TRUTH_ADV_03_LARGOS_DER: List[ExpectedAccount] = [
    ExpectedAccount(codigo="110101", nombre="Caja", monto=300000.0, signo=1, seccion="activo"),
    ExpectedAccount(codigo="110201", nombre="Banco", monto=800000.0, signo=1, seccion="activo"),
    ExpectedAccount(codigo="210101", nombre="Cuentas comerciales por pagar a entidades relacionadas", monto=450000.0, signo=1, seccion="pasivo"),
    ExpectedAccount(codigo="210201", nombre="Provisiones para beneficios a empleados de corto plazo", monto=650000.0, signo=1, seccion="pasivo"),
]

# ADV 04: Títulos y subtítulos centrados intermedios
GROUND_TRUTH_ADV_04_TITULOS_CENTRADOS: List[ExpectedAccount] = [
    ExpectedAccount(codigo="110101", nombre="Caja Central", monto=200000.0, signo=1, seccion="activo"),
    ExpectedAccount(codigo="110201", nombre="Banco Edwards", monto=1100000.0, signo=1, seccion="activo"),
    ExpectedAccount(codigo="210101", nombre="Proveedores Locales", monto=300000.0, signo=1, seccion="pasivo"),
    ExpectedAccount(codigo="310101", nombre="Capital Emitido", monto=1000000.0, signo=1, seccion="patrimonio"),
]

# ADV 05: Separación central estrecha (10-15 puntos)
GROUND_TRUTH_ADV_05_SEP_ESTRECHA: List[ExpectedAccount] = [
    ExpectedAccount(codigo="110101", nombre="Caja Sucursal", monto=120000.0, signo=1, seccion="activo"),
    ExpectedAccount(codigo="110201", nombre="Banco Estado", monto=880000.0, signo=1, seccion="activo"),
    ExpectedAccount(codigo="210101", nombre="Cuentas por Pagar", monto=400000.0, signo=1, seccion="pasivo"),
    ExpectedAccount(codigo="310101", nombre="Aporte Socios", monto=600000.0, signo=1, seccion="patrimonio"),
]

# ADV 06: Separación central amplia (80-100 puntos)
GROUND_TRUTH_ADV_06_SEP_AMPLIA: List[ExpectedAccount] = [
    ExpectedAccount(codigo="110101", nombre="Caja Moneda Nacional", monto=500000.0, signo=1, seccion="activo"),
    ExpectedAccount(codigo="110201", nombre="Banco Santander", monto=1500000.0, signo=1, seccion="activo"),
    ExpectedAccount(codigo="210101", nombre="Acreedores Varios", monto=700000.0, signo=1, seccion="pasivo"),
    ExpectedAccount(codigo="310101", nombre="Capital Pagado", monto=1300000.0, signo=1, seccion="patrimonio"),
]

# ADV 07: Importes de distinta cantidad de dígitos (desde 100 hasta 150.000.000)
GROUND_TRUTH_ADV_07_MONTOS_DISTINTOS_DIGITOS: List[ExpectedAccount] = [
    ExpectedAccount(codigo="110101", nombre="Fondo Menor", monto=100.0, signo=1, seccion="activo"),
    ExpectedAccount(codigo="110102", nombre="Caja Chica", monto=15000.0, signo=1, seccion="activo"),
    ExpectedAccount(codigo="120101", nombre="Edificios y Terrenos", monto=150000000.0, signo=1, seccion="activo"),
    ExpectedAccount(codigo="210101", nombre="Ajuste Redondeo", monto=50.0, signo=1, seccion="pasivo"),
    ExpectedAccount(codigo="210201", nombre="Retencion Judicial", monto=25000.0, signo=1, seccion="pasivo"),
    ExpectedAccount(codigo="310101", nombre="Patrimonio Institucional", monto=149990050.0, signo=1, seccion="patrimonio"),
]

# ADV 08: Importes enteros sin separadores de miles (ej. 500000, 1200000, 800000)
GROUND_TRUTH_ADV_08_MONTOS_ENTEROS_SIN_SEP: List[ExpectedAccount] = [
    ExpectedAccount(codigo="110101", nombre="Caja", monto=500000.0, signo=1, seccion="activo"),
    ExpectedAccount(codigo="110102", nombre="Banco Chile", monto=1200000.0, signo=1, seccion="activo"),
    ExpectedAccount(codigo="210101", nombre="Proveedores", monto=800000.0, signo=1, seccion="pasivo"),
    ExpectedAccount(codigo="310101", nombre="Capital", monto=900000.0, signo=1, seccion="patrimonio"),
]

# ADV 09: Filas con desplazamiento vertical entre bloques (staggered)
GROUND_TRUTH_ADV_09_FILAS_DESPLAZADAS: List[ExpectedAccount] = [
    ExpectedAccount(codigo="110101", nombre="Caja Central", monto=350000.0, signo=1, seccion="activo"),
    ExpectedAccount(codigo="110201", nombre="Banco", monto=650000.0, signo=1, seccion="activo"),
    ExpectedAccount(codigo="210101", nombre="Proveedores", monto=400000.0, signo=1, seccion="pasivo"),
    ExpectedAccount(codigo="310101", nombre="Capital", monto=600000.0, signo=1, seccion="patrimonio"),
]

# ADV 10: Totales y subtotales paralelos
GROUND_TRUTH_ADV_10_TOTALES_SUBTOTALES: List[ExpectedAccount] = [
    ExpectedAccount(codigo="110101", nombre="Caja", monto=400000.0, signo=1, seccion="activo"),
    ExpectedAccount(codigo="110102", nombre="Banco", monto=600000.0, signo=1, seccion="activo"),
    ExpectedAccount(codigo=None, nombre="SUBTOTAL DISPONIBLE", monto=1000000.0, signo=1, es_total=True, seccion="activo"),
    ExpectedAccount(codigo=None, nombre="TOTAL ACTIVO", monto=1000000.0, signo=1, es_total=True, seccion="activo"),
    ExpectedAccount(codigo="210101", nombre="Proveedores", monto=300000.0, signo=1, seccion="pasivo"),
    ExpectedAccount(codigo="310101", nombre="Capital", monto=700000.0, signo=1, seccion="patrimonio"),
    ExpectedAccount(codigo=None, nombre="SUBTOTAL EXIGIBLE", monto=300000.0, signo=1, es_total=True, seccion="pasivo"),
    ExpectedAccount(codigo=None, nombre="TOTAL PASIVO Y PATRIMONIO", monto=1000000.0, signo=1, es_total=True, seccion="pasivo"),
]

# ADV 11: Control Negativo - Una sola fila aparentemente paralela (debe abstenerse / fallback)
GROUND_TRUTH_ADV_11_UNA_SOLA_FILA: List[ExpectedAccount] = [
    ExpectedAccount(codigo="110101", nombre="Caja General", monto=100000.0, signo=1),
    ExpectedAccount(codigo="110201", nombre="Banco", monto=500000.0, signo=1),
    ExpectedAccount(codigo="210101", nombre="Proveedores", monto=200000.0, signo=1),
]

# ADV 12: Control Negativo - Ocho columnas con muchos números enteros susceptibles de parecer códigos
GROUND_TRUTH_ADV_12_OCHO_COL_MUCHOS_NUMEROS: List[ExpectedAccount] = [
    ExpectedAccount(
        codigo="110101", nombre="CAJA OPERATIVA", monto=500000.0, signo=1, seccion="activo",
        columnas_8col={"debito": 1000000.0, "credito": 500000.0, "deudor": 500000.0, "acreedor": 0.0, "activo": 500000.0, "pasivo": 0.0, "perdida": 0.0, "ganancia": 0.0}
    ),
    ExpectedAccount(
        codigo="210101", nombre="PROVEEDORES DIRECTOS", monto=800000.0, signo=1, seccion="pasivo",
        columnas_8col={"debito": 200000.0, "credito": 1000000.0, "deudor": 0.0, "acreedor": 800000.0, "activo": 0.0, "pasivo": 800000.0, "perdida": 0.0, "ganancia": 0.0}
    ),
]

# ADV 13: Códigos de 5, 6, 7 y 8 dígitos
GROUND_TRUTH_ADV_13_CODIGOS_MIX_DIGITOS: List[ExpectedAccount] = [
    ExpectedAccount(codigo="11010", nombre="Caja 5 Digitos", monto=150000.0, signo=1, seccion="activo"),
    ExpectedAccount(codigo="110101", nombre="Banco 6 Digitos", monto=850000.0, signo=1, seccion="activo"),
    ExpectedAccount(codigo="1201001", nombre="Maquinaria 7 Digitos", monto=2000000.0, signo=1, seccion="activo"),
    ExpectedAccount(codigo="12010001", nombre="Vehiculos 8 Digitos", monto=1000000.0, signo=1, seccion="activo"),
    ExpectedAccount(codigo="21010", nombre="Proveedores 5 Digitos", monto=500000.0, signo=1, seccion="pasivo"),
    ExpectedAccount(codigo="210101", nombre="Retenciones 6 Digitos", monto=200000.0, signo=1, seccion="pasivo"),
    ExpectedAccount(codigo="2101001", nombre="Creditos 7 Digitos", monto=1300000.0, signo=1, seccion="pasivo"),
    ExpectedAccount(codigo="31010001", nombre="Capital 8 Digitos", monto=2000000.0, signo=1, seccion="patrimonio"),
]
