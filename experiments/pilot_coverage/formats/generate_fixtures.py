"""
experiments/pilot_coverage/formats/generate_fixtures.py

Generador determinista de fixtures sintéticos en PDF y XLSX para evaluar
la cobertura de 9 formatos contables representativos.
Diseño con coordenadas contables proporcionales estándar.
"""

import pathlib
from fpdf import FPDF  # type: ignore[import-untyped]  # Biblioteca externa de generación PDF
import openpyxl  # type: ignore[import-untyped]  # Biblioteca externa de generación XLSX


def generar_todos_los_fixtures(output_dir: pathlib.Path) -> dict[str, pathlib.Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rutas = {}

    # -----------------------------------------------------------------------
    # 1. Positivo: Activos y Pasivos en bloques paralelos (Doble Columna)
    # -----------------------------------------------------------------------
    # Página A4 Landscape: 297mm de ancho.
    # Columna Izquierda (Activos): x=15 a x=135 (ancho 120mm)
    #   Código: x=15 (w=20)
    #   Nombre: x=35 (w=65)
    #   Monto:  x=100 (w=35)
    # Columna Derecha (Pasivos): x=155 a x=275 (ancho 120mm)
    #   Código: x=155 (w=20)
    #   Nombre: x=175 (w=65)
    #   Monto:  x=240 (w=35)
    # Gap central: x=135 a x=155 (20mm libres) -> Boundary exacto en ~145mm (~410 puntos)
    # -----------------------------------------------------------------------
    p1 = output_dir / "01_paralelo_activo_pasivo.pdf"
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font('Helvetica', size=9)

    # Título
    pdf.set_xy(15, 12)
    pdf.cell(260, 8, text="BALANCE GENERAL CLASIFICADO", align='C')
    # Encabezados
    pdf.set_xy(15, 22)
    pdf.cell(120, 7, text="ACTIVOS", align='L')
    pdf.set_xy(155, 22)
    pdf.cell(120, 7, text="PASIVOS Y PATRIMONIO", align='L')

    filas_paralelas = [
        ("110101", "Caja", "500.000", "210101", "Proveedores Nacionales", "500.000"),
        ("110102", "Banco de Chile", "1.200.000", "210201", "Cuentas por Pagar Comerciales", "700.000"),
        ("110201", "Clientes Nacionales", "800.000", "210301", "Retenciones por Pagar", "300.000"),
        ("120101", "Maquinarias y Equipos", "5.000.000", "310101", "Capital Pagado", "6.000.000"),
    ]
    y = 32
    for c_act, n_act, m_act, c_pas, n_pas, m_pas in filas_paralelas:
        # Columna Izquierda (Activo)
        pdf.set_xy(15, y)
        pdf.cell(20, 6, text=c_act)
        pdf.set_xy(35, y)
        pdf.cell(65, 6, text=n_act)
        pdf.set_xy(100, y)
        pdf.cell(35, 6, text=m_act, align='R')

        # Columna Derecha (Pasivo)
        pdf.set_xy(155, y)
        pdf.cell(20, 6, text=c_pas)
        pdf.set_xy(175, y)
        pdf.cell(65, 6, text=n_pas)
        pdf.set_xy(240, y)
        pdf.cell(35, 6, text=m_pas, align='R')
        y += 8

    # Totales
    pdf.set_xy(15, y + 4)
    pdf.cell(85, 6, text="TOTAL ACTIVO")
    pdf.set_xy(100, y + 4)
    pdf.cell(35, 6, text="7.500.000", align='R')

    pdf.set_xy(155, y + 4)
    pdf.cell(85, 6, text="TOTAL PASIVO Y PATRIMONIO")
    pdf.set_xy(240, y + 4)
    pdf.cell(35, 6, text="7.500.000", align='R')

    pdf.output(str(p1))
    rutas["paralelo_con_codigo"] = p1

    # -----------------------------------------------------------------------
    # 1B. Positivo: Activos y Pasivos paralelos SIN códigos de cuenta
    # -----------------------------------------------------------------------
    p1b = output_dir / "01b_paralelo_sin_codigo.pdf"
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font('Helvetica', size=9)
    pdf.set_xy(15, 12)
    pdf.cell(260, 8, text="BALANCE CLASIFICADO", align='C')
    y = 25
    filas_sin_cod = [
        ("Caja y Bancos", "1.700.000", "Proveedores Varios", "1.200.000"),
        ("Deudores por Ventas", "800.000", "Impuestos por Pagar", "300.000"),
        ("Activo Fijo Neto", "5.000.000", "Capital y Reservas", "6.000.000"),
    ]
    for n_act, m_act, n_pas, m_pas in filas_sin_cod:
        pdf.set_xy(15, y)
        pdf.cell(80, 6, text=n_act)
        pdf.set_xy(95, y)
        pdf.cell(40, 6, text=m_act, align='R')

        pdf.set_xy(155, y)
        pdf.cell(80, 6, text=n_pas)
        pdf.set_xy(235, y)
        pdf.cell(40, 6, text=m_pas, align='R')
        y += 8
    pdf.output(str(p1b))
    rutas["paralelo_sin_codigo"] = p1b

    # -----------------------------------------------------------------------
    # 2. Control Negativo: Balance Tributario 8 Columnas
    # -----------------------------------------------------------------------
    p2 = output_dir / "02_ocho_columnas_control_negativo.pdf"
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font('Helvetica', size=8)
    pdf.set_xy(10, 10)
    pdf.cell(270, 6, text="BALANCE TRIBUTARIO DE 8 COLUMNAS", align='C')

    # Encabezado 8 columnas
    pdf.set_xy(10, 20)
    pdf.cell(18, 5, text="CODIGO")
    pdf.cell(50, 5, text="CUENTA")
    pdf.cell(24, 5, text="DEBITO", align='R')
    pdf.cell(24, 5, text="CREDITO", align='R')
    pdf.cell(24, 5, text="DEUDOR", align='R')
    pdf.cell(24, 5, text="ACREEDOR", align='R')
    pdf.cell(24, 5, text="ACTIVO", align='R')
    pdf.cell(24, 5, text="PASIVO", align='R')
    pdf.cell(24, 5, text="PERDIDA", align='R')
    pdf.cell(24, 5, text="GANANCIA", align='R')

    y = 28
    filas_8col = [
        ("110101", "CAJA", "1.000.000", "500.000", "500.000", "0", "500.000", "0", "0", "0"),
        ("110201", "BANCO DE CHILE", "3.000.000", "1.000.000", "2.000.000", "0", "2.000.000", "0", "0", "0"),
        ("210101", "PROVEEDORES", "500.000", "1.500.000", "0", "1.000.000", "0", "1.000.000", "0", "0"),
        ("410101", "VENTAS", "0", "2.500.000", "0", "2.500.000", "0", "0", "0", "2.500.000"),
        ("510101", "COSTO DE VENTAS", "1.000.000", "0", "1.000.000", "0", "0", "0", "1.000.000", "0"),
    ]
    for cod, nom, deb, cre, s_deb, s_cre, act, pas, per, gan in filas_8col:
        pdf.set_xy(10, y)
        pdf.cell(18, 5, text=cod)
        pdf.cell(50, 5, text=nom)
        pdf.cell(24, 5, text=deb, align='R')
        pdf.cell(24, 5, text=cre, align='R')
        pdf.cell(24, 5, text=s_deb, align='R')
        pdf.cell(24, 5, text=s_cre, align='R')
        pdf.cell(24, 5, text=act, align='R')
        pdf.cell(24, 5, text=pas, align='R')
        pdf.cell(24, 5, text=per, align='R')
        pdf.cell(24, 5, text=gan, align='R')
        y += 6
    pdf.output(str(p2))
    rutas["ocho_columnas"] = p2

    # -----------------------------------------------------------------------
    # 3. Control Negativo: Balance Clasificado Vertical
    # -----------------------------------------------------------------------
    p3 = output_dir / "03_clasificado_vertical.pdf"
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font('Helvetica', size=9)
    pdf.set_xy(10, 10)
    pdf.cell(190, 8, text="ESTADO DE SITUACION FINANCIERA", align='C')
    y = 25
    filas_vert = [
        ("ACTIVO CIRCULANTE", ""),
        ("110101 Caja", "300.000"),
        ("110102 Banco", "1.200.000"),
        ("110201 Clientes", "900.000"),
        ("TOTAL ACTIVO CIRCULANTE", "2.400.000"),
        ("PASIVO CIRCULANTE", ""),
        ("210101 Proveedores", "1.000.000"),
        ("210201 Cuentas por Pagar", "400.000"),
        ("TOTAL PASIVO CIRCULANTE", "1.400.000"),
    ]
    for nom, mnt in filas_vert:
        pdf.set_xy(15, y)
        pdf.cell(120, 6, text=nom)
        pdf.cell(50, 6, text=mnt, align='R')
        y += 7
    pdf.output(str(p3))
    rutas["clasificado_vertical"] = p3

    # -----------------------------------------------------------------------
    # 4. Control Negativo: Estado Comparativo Dos Períodos
    # -----------------------------------------------------------------------
    p4 = output_dir / "04_comparativo_dos_periodos.pdf"
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font('Helvetica', size=9)
    pdf.set_xy(10, 10)
    pdf.cell(190, 8, text="ESTADO DE SITUACION FINANCIERA COMPARATIVO", align='C')
    pdf.set_xy(15, 20)
    pdf.cell(100, 6, text="Cuenta")
    pdf.cell(35, 6, text="2024", align='R')
    pdf.cell(35, 6, text="2023", align='R')
    y = 28
    filas_comp = [
        ("110101 Efectivo y equivalentes de efectivo", "1.500.000", "1.200.000"),
        ("110201 Deudores comerciales y otras cuentas", "850.000", "920.000"),
        ("120101 Propiedades, planta y equipo", "4.200.000", "4.000.000"),
        ("210101 Cuentas por pagar comerciales", "1.100.000", "950.000"),
        ("310101 Capital emitido", "5.450.000", "5.170.000"),
    ]
    for nom, m24, m23 in filas_comp:
        pdf.set_xy(15, y)
        pdf.cell(100, 6, text=nom)
        pdf.cell(35, 6, text=m24, align='R')
        pdf.cell(35, 6, text=m23, align='R')
        y += 7
    pdf.output(str(p4))
    rutas["comparativo_dos_periodos"] = p4

    # -----------------------------------------------------------------------
    # 5. Notas cercanas a los montos
    # -----------------------------------------------------------------------
    p5 = output_dir / "05_notas_cercanas_a_montos.pdf"
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font('Helvetica', size=9)
    pdf.set_xy(10, 10)
    pdf.cell(190, 8, text="BALANCE CON COLUMNA DE NOTAS", align='C')
    pdf.set_xy(15, 20)
    pdf.cell(90, 6, text="Concepto")
    pdf.cell(25, 6, text="Nota", align='C')
    pdf.cell(45, 6, text="2024 (CLP)", align='R')
    y = 28
    filas_notas = [
        ("Efectivo y equivalentes al efectivo", "Nota 5", "2.350.000"),
        ("Otros activos financieros corrientes", "Nota 6", "540.000"),
        ("Deudores comerciales y otras cuentas por cobrar", "Nota 7", "1.890.000"),
        ("Cuentas por pagar comerciales y otras", "Nota 14", "1.250.000"),
    ]
    for nom, nota, mnt in filas_notas:
        pdf.set_xy(15, y)
        pdf.cell(90, 6, text=nom)
        pdf.cell(25, 6, text=nota, align='C')
        pdf.cell(45, 6, text=mnt, align='R')
        y += 7
    pdf.output(str(p5))
    rutas["notas_cercanas"] = p5

    # -----------------------------------------------------------------------
    # 6. Descripciones Multilínea
    # -----------------------------------------------------------------------
    p6 = output_dir / "06_descripciones_multilinea.pdf"
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font('Helvetica', size=9)
    pdf.set_xy(10, 10)
    pdf.cell(190, 8, text="BALANCE CON GLOSAS MULTILINEA", align='C')
    y = 25
    pdf.set_xy(15, y)
    pdf.cell(120, 5, text="110201 Cuentas por cobrar comerciales y otras cuentas por cobrar")
    y += 5
    pdf.set_xy(15, y)
    pdf.cell(120, 5, text="a entidades relacionadas del giro")
    pdf.cell(45, 5, text="3.450.000", align='R')
    y += 8

    pdf.set_xy(15, y)
    pdf.cell(120, 5, text="120101 Propiedades de inversion destinadas a arrendamiento")
    y += 5
    pdf.set_xy(15, y)
    pdf.cell(120, 5, text="operativo de largo plazo segun contrato")
    y += 5
    pdf.set_xy(15, y)
    pdf.cell(120, 5, text="marco con empresas filiales")
    pdf.cell(45, 5, text="8.900.000", align='R')
    y += 8
    pdf.output(str(p6))
    rutas["descripciones_multilinea"] = p6

    # -----------------------------------------------------------------------
    # 7. Importes Negativos, Ceros y Celdas Vacías
    # -----------------------------------------------------------------------
    p7 = output_dir / "07_negativos_ceros_vacias.pdf"
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font('Helvetica', size=9)
    pdf.set_xy(10, 10)
    pdf.cell(190, 8, text="BALANCE CON SALDOS NEGATIVOS Y CEROS", align='C')
    y = 25
    filas_signos = [
        ("110101 Caja", "100.000"),
        ("110102 Banco Saldo Negativo", "(450.000)"),
        ("110201 Cuenta Sin Movimiento", "0"),
        ("120101 Depreciacion Acumulada", "-1.200.000"),
        ("310101 Perdida del Ejercicio", "(890.000)"),
    ]
    for nom, mnt in filas_signos:
        pdf.set_xy(15, y)
        pdf.cell(120, 6, text=nom)
        pdf.cell(45, 6, text=mnt, align='R')
        y += 7
    pdf.output(str(p7))
    rutas["signos_ceros"] = p7

    # -----------------------------------------------------------------------
    # 8. Planilla Excel (.xlsx)
    # -----------------------------------------------------------------------
    p8 = output_dir / "08_balance_excel.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Balance"
    ws.append(["Codigo", "Nombre Cuenta", "Monto CLP"])
    ws.append(["110101", "Caja Principal", 150000])
    ws.append(["110102", "Banco Estado", 3200000])
    ws.append(["110201", "Facturas por Cobrar", 1450000])
    ws.append(["210101", "Facturas por Pagar", 980000])
    ws.append(["310101", "Capital Social", 3820000])
    wb.save(str(p8))
    rutas["excel_xlsx"] = p8

    # -----------------------------------------------------------------------
    # 9. Variaciones de Espaciado y Alineación
    # -----------------------------------------------------------------------
    p9 = output_dir / "09_espaciado_y_alineacion.pdf"
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font('Helvetica', size=9)
    pdf.set_xy(10, 10)
    pdf.cell(190, 8, text="BALANCE CON ESPACIADO IRREGULAR", align='C')
    y = 25
    pdf.set_xy(25, y)
    pdf.cell(80, 6, text="110101   Caja   Chica   Central")
    pdf.cell(60, 6, text="75.000", align='R')
    y += 9
    pdf.set_xy(15, y)
    pdf.cell(100, 6, text="110201      Deudores   Varios")
    pdf.cell(50, 6, text="430.000", align='R')
    y += 12
    pdf.set_xy(30, y)
    pdf.cell(70, 6, text="210101 Proveedores")
    pdf.cell(70, 6, text="505.000", align='R')
    pdf.output(str(p9))
    rutas["espaciado_irregular"] = p9

    # =======================================================================
    # FIXTURES ADVERSARIALES OBLIGATORIOS (ENCARGO A4)
    # =======================================================================

    # ADV 01: Bloques de diferente anchura (Izquierda 70mm, Derecha 150mm)
    p_adv1 = output_dir / "adv_01_bloques_ancho_distinto.pdf"
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font('Helvetica', size=9)
    pdf.set_xy(15, 12)
    pdf.cell(260, 8, text="BALANCE GENERAL - BLOQUES ASIMETRICOS", align='C')
    y = 25
    filas_adv1 = [
        ("110101", "Caja Chica", "100.000", "210101", "Proveedores Nacionales de Insumos y Servicios Varios", "400.000"),
        ("110102", "Banco", "900.000", "210201", "Obligaciones con Instituciones de Credito y Financiamiento", "600.000"),
    ]
    for c_izq, n_izq, m_izq, c_der, n_der, m_der in filas_adv1:
        # Bloque izquierdo estrecho: x=15..85 (ancho 70)
        pdf.set_xy(15, y)
        pdf.cell(16, 6, text=c_izq)
        pdf.set_xy(31, y)
        pdf.cell(32, 6, text=n_izq)
        pdf.set_xy(63, y)
        pdf.cell(22, 6, text=m_izq, align='R')
        # Bloque derecho ancho: x=105..255 (ancho 150)
        pdf.set_xy(105, y)
        pdf.cell(16, 6, text=c_der)
        pdf.set_xy(121, y)
        pdf.cell(105, 6, text=n_der)
        pdf.set_xy(226, y)
        pdf.cell(25, 6, text=m_der, align='R')
        y += 8
    pdf.output(str(p_adv1))
    rutas["adv_01"] = p_adv1

    # ADV 02: Nombres largos solo en bloque izquierdo
    p_adv2 = output_dir / "adv_02_nombres_largos_solo_izq.pdf"
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font('Helvetica', size=8)
    pdf.set_xy(15, 12)
    pdf.cell(260, 8, text="BALANCE - GLOSAS LARGAS IZQUIERDA", align='C')
    y = 25
    filas_adv2 = [
        ("110101", "Fondos fijos y valores en custodia en tesoreria central", "250.000", "210101", "Proveedores", "500.000"),
        ("110201", "Cuentas por cobrar comerciales a clientes del giro nacional", "750.000", "310101", "Capital", "500.000"),
    ]
    for c_izq, n_izq, m_izq, c_der, n_der, m_der in filas_adv2:
        pdf.set_xy(15, y)
        pdf.cell(16, 6, text=c_izq)
        pdf.set_xy(31, y)
        pdf.cell(85, 6, text=n_izq)
        pdf.set_xy(116, y)
        pdf.cell(25, 6, text=m_izq, align='R')

        pdf.set_xy(155, y)
        pdf.cell(16, 6, text=c_der)
        pdf.set_xy(171, y)
        pdf.cell(60, 6, text=n_der)
        pdf.set_xy(235, y)
        pdf.cell(25, 6, text=m_der, align='R')
        y += 8
    pdf.output(str(p_adv2))
    rutas["adv_02"] = p_adv2

    # ADV 03: Nombres largos solo en bloque derecho
    p_adv3 = output_dir / "adv_03_nombres_largos_solo_der.pdf"
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font('Helvetica', size=8)
    pdf.set_xy(15, 12)
    pdf.cell(260, 8, text="BALANCE - GLOSAS LARGAS DERECHA", align='C')
    y = 25
    filas_adv3 = [
        ("110101", "Caja", "300.000", "210101", "Cuentas comerciales por pagar a entidades relacionadas", "450.000"),
        ("110201", "Banco", "800.000", "210201", "Provisiones para beneficios a empleados de corto plazo", "650.000"),
    ]
    for c_izq, n_izq, m_izq, c_der, n_der, m_der in filas_adv3:
        pdf.set_xy(15, y)
        pdf.cell(16, 6, text=c_izq)
        pdf.set_xy(31, y)
        pdf.cell(60, 6, text=n_izq)
        pdf.set_xy(95, y)
        pdf.cell(25, 6, text=m_izq, align='R')

        pdf.set_xy(135, y)
        pdf.cell(16, 6, text=c_der)
        pdf.set_xy(151, y)
        pdf.cell(90, 6, text=n_der)
        pdf.set_xy(245, y)
        pdf.cell(25, 6, text=m_der, align='R')
        y += 8
    pdf.output(str(p_adv3))
    rutas["adv_03"] = p_adv3

    # ADV 04: Títulos y subtítulos centrados
    p_adv4 = output_dir / "adv_04_titulos_subtitulos_centrados.pdf"
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font('Helvetica', size=9)
    pdf.set_xy(15, 10)
    pdf.cell(260, 6, text="EMPRESA MODELO S.A.", align='C')
    pdf.set_xy(15, 16)
    pdf.cell(260, 6, text="BALANCE GENERAL CONSOLIDADO AL 31 DE DICIEMBRE", align='C')
    pdf.set_xy(15, 22)
    pdf.cell(260, 5, text="(Expresado en miles de pesos chilenos)", align='C')
    y = 32
    filas_adv4 = [
        ("110101", "Caja Central", "200.000", "210101", "Proveedores Locales", "300.000"),
        ("110201", "Banco Edwards", "1.100.000", "310101", "Capital Emitido", "1.000.000"),
    ]
    for c_izq, n_izq, m_izq, c_der, n_der, m_der in filas_adv4:
        pdf.set_xy(15, y)
        pdf.cell(16, 6, text=c_izq)
        pdf.set_xy(31, y)
        pdf.cell(60, 6, text=n_izq)
        pdf.set_xy(95, y)
        pdf.cell(25, 6, text=m_izq, align='R')

        pdf.set_xy(145, y)
        pdf.cell(16, 6, text=c_der)
        pdf.set_xy(161, y)
        pdf.cell(60, 6, text=n_der)
        pdf.set_xy(225, y)
        pdf.cell(25, 6, text=m_der, align='R')
        y += 8
    pdf.output(str(p_adv4))
    rutas["adv_04"] = p_adv4

    # ADV 05: Separación central estrecha (gap 5mm / ~14 pt)
    p_adv5 = output_dir / "adv_05_separacion_estrecha.pdf"
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font('Helvetica', size=9)
    pdf.set_xy(15, 12)
    pdf.cell(260, 8, text="BALANCE CON SEPARACION ESTRECHA", align='C')
    y = 25
    filas_adv5 = [
        ("110101", "Caja Sucursal", "120.000", "210101", "Cuentas por Pagar", "400.000"),
        ("110201", "Banco Estado", "880.000", "310101", "Aporte Socios", "600.000"),
    ]
    for c_izq, n_izq, m_izq, c_der, n_der, m_der in filas_adv5:
        # Izquierda x=15..135 (monto termina en 135)
        pdf.set_xy(15, y)
        pdf.cell(16, 6, text=c_izq)
        pdf.set_xy(31, y)
        pdf.cell(75, 6, text=n_izq)
        pdf.set_xy(108, y)
        pdf.cell(27, 6, text=m_izq, align='R')

        # Derecha x=140..260 (código empieza en 140, gap de 5mm)
        pdf.set_xy(140, y)
        pdf.cell(16, 6, text=c_der)
        pdf.set_xy(156, y)
        pdf.cell(75, 6, text=n_der)
        pdf.set_xy(233, y)
        pdf.cell(27, 6, text=m_der, align='R')
        y += 8
    pdf.output(str(p_adv5))
    rutas["adv_05"] = p_adv5

    # ADV 06: Separación central amplia (gap 45mm / ~128 pt)
    p_adv6 = output_dir / "adv_06_separacion_amplia.pdf"
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font('Helvetica', size=9)
    pdf.set_xy(15, 12)
    pdf.cell(260, 8, text="BALANCE CON SEPARACION AMPLIA", align='C')
    y = 25
    filas_adv6 = [
        ("110101", "Caja Moneda Nacional", "500.000", "210101", "Acreedores Varios", "700.000"),
        ("110201", "Banco Santander", "1.500.000", "310101", "Capital Pagado", "1.300.000"),
    ]
    for c_izq, n_izq, m_izq, c_der, n_der, m_der in filas_adv6:
        # Izquierda x=15..110
        pdf.set_xy(15, y)
        pdf.cell(16, 6, text=c_izq)
        pdf.set_xy(31, y)
        pdf.cell(55, 6, text=n_izq)
        pdf.set_xy(86, y)
        pdf.cell(24, 6, text=m_izq, align='R')

        # Derecha x=165..260
        pdf.set_xy(165, y)
        pdf.cell(16, 6, text=c_der)
        pdf.set_xy(181, y)
        pdf.cell(55, 6, text=n_der)
        pdf.set_xy(236, y)
        pdf.cell(24, 6, text=m_der, align='R')
        y += 8
    pdf.output(str(p_adv6))
    rutas["adv_06"] = p_adv6

    # ADV 07: Importes con distinta cantidad de dígitos
    p_adv7 = output_dir / "adv_07_montos_distintos_digitos.pdf"
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font('Helvetica', size=8)
    pdf.set_xy(15, 12)
    pdf.cell(260, 8, text="BALANCE - DIVERSIDAD DE DIGITOS EN MONTOS", align='C')
    y = 25
    filas_adv7 = [
        ("110101", "Fondo Menor", "100", "210101", "Ajuste Redondeo", "50"),
        ("110102", "Caja Chica", "15.000", "210201", "Retencion Judicial", "25.000"),
        ("120101", "Edificios y Terrenos", "150.000.000", "310101", "Patrimonio Institucional", "149.990.050"),
    ]
    for c_izq, n_izq, m_izq, c_der, n_der, m_der in filas_adv7:
        pdf.set_xy(15, y)
        pdf.cell(16, 6, text=c_izq)
        pdf.set_xy(31, y)
        pdf.cell(55, 6, text=n_izq)
        pdf.set_xy(86, y)
        pdf.cell(35, 6, text=m_izq, align='R')

        pdf.set_xy(145, y)
        pdf.cell(16, 6, text=c_der)
        pdf.set_xy(161, y)
        pdf.cell(55, 6, text=n_der)
        pdf.set_xy(216, y)
        pdf.cell(35, 6, text=m_der, align='R')
        y += 8
    pdf.output(str(p_adv7))
    rutas["adv_07"] = p_adv7

    # ADV 08: Importes enteros sin separadores de miles
    p_adv8 = output_dir / "adv_08_montos_enteros_sin_separador.pdf"
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font('Helvetica', size=9)
    pdf.set_xy(15, 12)
    pdf.cell(260, 8, text="BALANCE - MONTOS ENTEROS SIN PUNTOS", align='C')
    y = 25
    filas_adv8 = [
        ("110101", "Caja", "500000", "210101", "Proveedores", "800000"),
        ("110102", "Banco Chile", "1200000", "310101", "Capital", "900000"),
    ]
    for c_izq, n_izq, m_izq, c_der, n_der, m_der in filas_adv8:
        pdf.set_xy(15, y)
        pdf.cell(16, 6, text=c_izq)
        pdf.set_xy(31, y)
        pdf.cell(55, 6, text=n_izq)
        pdf.set_xy(88, y)
        pdf.cell(30, 6, text=m_izq, align='R')

        pdf.set_xy(145, y)
        pdf.cell(16, 6, text=c_der)
        pdf.set_xy(161, y)
        pdf.cell(55, 6, text=n_der)
        pdf.set_xy(218, y)
        pdf.cell(30, 6, text=m_der, align='R')
        y += 8
    pdf.output(str(p_adv8))
    rutas["adv_08"] = p_adv8

    # ADV 09: Filas con desplazamiento vertical entre bloques (staggered)
    p_adv9 = output_dir / "adv_09_filas_desplazamiento_vertical.pdf"
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font('Helvetica', size=9)
    pdf.set_xy(15, 12)
    pdf.cell(260, 8, text="BALANCE - FILAS CON DESPLAZAMIENTO VERTICAL", align='C')
    # Fila 1 izquierda y derecha con offset de 3mm en Y
    pdf.set_xy(15, 25)
    pdf.cell(16, 6, text="110101")
    pdf.cell(55, 6, text="Caja Central")
    pdf.cell(30, 6, text="350.000", align='R')

    pdf.set_xy(145, 29)
    pdf.cell(16, 6, text="210101")
    pdf.cell(55, 6, text="Proveedores")
    pdf.cell(30, 6, text="400.000", align='R')

    pdf.set_xy(15, 37)
    pdf.cell(16, 6, text="110201")
    pdf.cell(55, 6, text="Banco")
    pdf.cell(30, 6, text="650.000", align='R')

    pdf.set_xy(145, 41)
    pdf.cell(16, 6, text="310101")
    pdf.cell(55, 6, text="Capital")
    pdf.cell(30, 6, text="600.000", align='R')

    pdf.output(str(p_adv9))
    rutas["adv_09"] = p_adv9

    # ADV 10: Totales y subtotales paralelos
    p_adv10 = output_dir / "adv_10_totales_subtotales_paralelos.pdf"
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font('Helvetica', size=8)
    pdf.set_xy(15, 10)
    pdf.cell(260, 6, text="BALANCE CON SUB-TOTALES PARALELOS", align='C')
    y = 20
    filas_adv10 = [
        ("110101", "Caja", "400.000", "210101", "Proveedores", "300.000"),
        ("110102", "Banco", "600.000", "310101", "Capital", "700.000"),
    ]
    for c_izq, n_izq, m_izq, c_der, n_der, m_der in filas_adv10:
        pdf.set_xy(15, y)
        pdf.cell(16, 5, text=c_izq)
        pdf.cell(55, 5, text=n_izq)
        pdf.cell(25, 5, text=m_izq, align='R')

        pdf.set_xy(145, y)
        pdf.cell(16, 5, text=c_der)
        pdf.cell(55, 5, text=n_der)
        pdf.cell(25, 5, text=m_der, align='R')
        y += 7
    # Subtotales
    pdf.set_xy(15, y)
    pdf.cell(71, 5, text="SUBTOTAL DISPONIBLE")
    pdf.cell(25, 5, text="1.000.000", align='R')
    pdf.set_xy(145, y)
    pdf.cell(71, 5, text="SUBTOTAL EXIGIBLE")
    pdf.cell(25, 5, text="300.000", align='R')
    y += 7
    # Totales Finales
    pdf.set_xy(15, y)
    pdf.cell(71, 5, text="TOTAL ACTIVO")
    pdf.cell(25, 5, text="1.000.000", align='R')
    pdf.set_xy(145, y)
    pdf.cell(71, 5, text="TOTAL PASIVO Y PATRIMONIO")
    pdf.cell(25, 5, text="1.000.000", align='R')
    pdf.output(str(p_adv10))
    rutas["adv_10"] = p_adv10

    # ADV 11: Control Negativo - Una sola fila aparentemente paralela
    p_adv11 = output_dir / "adv_11_una_sola_fila_paralela.pdf"
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font('Helvetica', size=9)
    pdf.set_xy(15, 15)
    pdf.cell(180, 6, text="BALANCE VERTICAL CON RUIDO AISLADO", align='C')
    # Fila 1 normal
    pdf.set_xy(15, 25)
    pdf.cell(100, 6, text="110101 Caja General")
    pdf.cell(40, 6, text="100.000", align='R')
    # Fila 2 con texto lateral espurio (una sola fila paralela)
    pdf.set_xy(15, 33)
    pdf.cell(100, 6, text="110201 Banco")
    pdf.cell(40, 6, text="500.000", align='R')
    pdf.set_xy(140, 33)
    pdf.cell(40, 6, text="Nota Informativa")
    # Fila 3 normal
    pdf.set_xy(15, 41)
    pdf.cell(100, 6, text="210101 Proveedores")
    pdf.cell(40, 6, text="200.000", align='R')
    pdf.output(str(p_adv11))
    rutas["adv_11"] = p_adv11

    # ADV 12: Control Negativo - Ocho columnas con muchos números enteros susceptibles de parecer códigos
    p_adv12 = output_dir / "adv_12_ocho_columnas_muchos_numeros_tipo_codigo.pdf"
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font('Helvetica', size=8)
    pdf.set_xy(10, 10)
    pdf.cell(270, 6, text="BALANCE 8 COLUMNAS CON MONTOS ENTEROS GRANDES", align='C')
    pdf.set_xy(10, 20)
    pdf.cell(20, 5, text="CODIGO")
    pdf.cell(50, 5, text="CUENTA")
    pdf.cell(24, 5, text="DEBITO", align='R')
    pdf.cell(24, 5, text="CREDITO", align='R')
    pdf.cell(24, 5, text="DEUDOR", align='R')
    pdf.cell(24, 5, text="ACREEDOR", align='R')
    pdf.cell(24, 5, text="ACTIVO", align='R')
    pdf.cell(24, 5, text="PASIVO", align='R')
    pdf.cell(24, 5, text="PERDIDA", align='R')
    pdf.cell(24, 5, text="GANANCIA", align='R')
    y = 28
    filas_adv12 = [
        ("110101", "CAJA OPERATIVA", "1000000", "500000", "500000", "0", "500000", "0", "0", "0"),
        ("210101", "PROVEEDORES DIRECTOS", "200000", "1000000", "0", "800000", "0", "800000", "0", "0"),
    ]
    for cod, nom, deb, cre, s_deb, s_cre, act, pas, per, gan in filas_adv12:
        pdf.set_xy(10, y)
        pdf.cell(20, 5, text=cod)
        pdf.cell(50, 5, text=nom)
        pdf.cell(24, 5, text=deb, align='R')
        pdf.cell(24, 5, text=cre, align='R')
        pdf.cell(24, 5, text=s_deb, align='R')
        pdf.cell(24, 5, text=s_cre, align='R')
        pdf.cell(24, 5, text=act, align='R')
        pdf.cell(24, 5, text=pas, align='R')
        pdf.cell(24, 5, text=per, align='R')
        pdf.cell(24, 5, text=gan, align='R')
        y += 6
    pdf.output(str(p_adv12))
    rutas["adv_12"] = p_adv12

    # ADV 13: Códigos de 5, 6, 7 y 8 dígitos en paralelo
    p_adv13 = output_dir / "adv_13_codigos_5_6_7_8_digitos.pdf"
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font('Helvetica', size=8)
    pdf.set_xy(15, 12)
    pdf.cell(260, 8, text="BALANCE - CODIGOS DE 5, 6, 7 Y 8 DIGITOS", align='C')
    y = 25
    filas_adv13 = [
        ("11010", "Caja 5 Digitos", "150.000", "21010", "Proveedores 5 Digitos", "500.000"),
        ("110101", "Banco 6 Digitos", "850.000", "210101", "Retenciones 6 Digitos", "200.000"),
        ("1201001", "Maquinaria 7 Digitos", "2.000.000", "2101001", "Creditos 7 Digitos", "1.300.000"),
        ("12010001", "Vehiculos 8 Digitos", "1.000.000", "31010001", "Capital 8 Digitos", "2.000.000"),
    ]
    for c_izq, n_izq, m_izq, c_der, n_der, m_der in filas_adv13:
        pdf.set_xy(15, y)
        pdf.cell(20, 6, text=c_izq)
        pdf.set_xy(35, y)
        pdf.cell(60, 6, text=n_izq)
        pdf.set_xy(95, y)
        pdf.cell(30, 6, text=m_izq, align='R')

        pdf.set_xy(145, y)
        pdf.cell(20, 6, text=c_der)
        pdf.set_xy(165, y)
        pdf.cell(60, 6, text=n_der)
        pdf.set_xy(225, y)
        pdf.cell(30, 6, text=m_der, align='R')
        y += 8
    pdf.output(str(p_adv13))
    rutas["adv_13"] = p_adv13

    # MULTIPAGINA: 2 Páginas con cuentas exclusivas y disjuntas (Objetivo 3)
    p_multi = output_dir / "multipagina_cuentas_disjuntas.pdf"
    pdf = FPDF(orientation='P', unit='mm', format='A4')

    # Página 1: Activo Corriente
    pdf.add_page()
    pdf.set_font('Helvetica', size=9)
    pdf.set_xy(20, 15)
    pdf.cell(170, 8, text="BALANCE GENERAL ACTIVO CORRIENTE", align='C')
    y = 30
    filas_p1 = [
        ("110101", "Caja Central P1", "100.000"),
        ("110102", "Banco Estado P1", "200.000"),
        ("110201", "Clientes Locales P1", "300.000"),
    ]
    for cod, nom, monto in filas_p1:
        pdf.set_xy(20, y)
        pdf.cell(25, 6, text=cod)
        pdf.cell(95, 6, text=nom)
        pdf.cell(45, 6, text=monto, align='R')
        y += 8

    # Página 2: Activo No Corriente
    pdf.add_page()
    pdf.set_font('Helvetica', size=9)
    pdf.set_xy(20, 15)
    pdf.cell(170, 8, text="BALANCE GENERAL ACTIVO NO CORRIENTE", align='C')
    y = 30
    filas_p2 = [
        ("120101", "Terrenos Agricolas P2", "400.000"),
        ("120102", "Edificios y Construcciones P2", "500.000"),
        ("120103", "Maquinarias Pesadas P2", "600.000"),
    ]
    for cod, nom, monto in filas_p2:
        pdf.set_xy(20, y)
        pdf.cell(25, 6, text=cod)
        pdf.cell(95, 6, text=nom)
        pdf.cell(45, 6, text=monto, align='R')
        y += 8

    pdf.output(str(p_multi))
    rutas["multipagina_disjunta"] = p_multi

    return rutas


if __name__ == "__main__":
    out = pathlib.Path(__file__).parents[3] / "tests/experiments/pilot_coverage/fixtures/formats"
    rutas = generar_todos_los_fixtures(out)
    print(f"Fixtures regenerados con éxito: {len(rutas)} archivos.")
