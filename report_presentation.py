"""Presentación completa del catálogo. No modifica las cuentas ni su clasificación."""
import pandas as pd

CATEGORY_ORDER = (
    "activo_corriente", "activo_no_corriente", "pasivo_corriente",
    "pasivo_no_corriente", "patrimonio", "resultado",
)
CATEGORY_LABELS = dict(zip(CATEGORY_ORDER, (
    "Activo corriente", "Activo no corriente", "Pasivo corriente",
    "Pasivo no corriente", "Patrimonio", "Estado de resultados",
)))
ER_ORDER = (
    "ER.01", "ER.02", "ER.03", "ER.04", "ER.05", "ER.06", "ER.07",
    "ER.08", "ER.12", "ER.09", "ER.13", "ER.14", "ER.15", "ER.16",
    "ER.17", "ER.18", "ER.19", "ER.10", "ER.11",
)
CALCULATED = {"ER.03", "ER.06", "ER.08", "ER.19", "ER.11"}


def complete_catalog(grouped, catalog, has_income_detail):
    existing = {r["codigo_clasificado"]: r for r in grouped.to_dict("records")}
    rows = []
    for code in dict.fromkeys([*catalog, *existing]):
        entry = catalog.get(code, {})
        row = dict(existing.get(code, {}))
        row.update(codigo_clasificado=code,
                   nombre_estandar=entry.get("nombre_estandar", code),
                   categoria=entry.get("categoria", "sin_catalogo"))
        row.setdefault("monto_total", 0.0)
        row.setdefault("num_cuentas", 0)
        row["estado_presentacion"] = "Con cuentas" if row["num_cuentas"] else "Sin cuentas asignadas"
        if entry.get("clasificable") is False:
            row["estado_presentacion"] = "Calculado" if code in existing else "No disponible"
        rows.append(row)
    by_code = {r["codigo_clasificado"]: r for r in rows}
    amounts = {k: float(r["monto_total"]) for k, r in by_code.items()}
    detail_codes = [k for k, r in by_code.items() if r["categoria"] == "resultado"
                    and catalog.get(k, {}).get("clasificable") is not False and k not in CALCULATED]
    formulas = {
        "ER.03": ["ER.01", "ER.02"],
        "ER.06": ["ER.01", "ER.02", "ER.04", "ER.05"],
        "ER.08": ["ER.01", "ER.02", "ER.04", "ER.05", "ER.07"],
        "ER.19": [k for k in detail_codes if k != "ER.10"],
        "ER.11": detail_codes,
    }
    for code, dependencies in formulas.items():
        if code in by_code:
            by_code[code]["monto_total"] = sum(amounts.get(k, 0) for k in dependencies) if has_income_detail else None
            by_code[code]["estado_presentacion"] = "Calculado" if has_income_detail else "No disponible"
    def order(row):
        category = row["categoria"]
        code = row["codigo_clasificado"]
        # Categorías nuevas de resultado se presentan antes del cierre.
        er_index = ER_ORDER.index(code) if code in ER_ORDER else ER_ORDER.index("ER.19") - 0.5
        return (CATEGORY_ORDER.index(category) if category in CATEGORY_ORDER else 99,
                er_index if category == "resultado" else 0, code)
    return pd.DataFrame(sorted(rows, key=order)), formulas


def add_report_sheets(workbook, complete, formulas, *, start_row, unit,
                      meta, processed_at, source_name, pages, definitive, reasons,
                      tolerance=1000):
    """Extiende el exportador operativo, con fórmulas auditables y datos separados."""
    from openpyxl.styles import Alignment, Font, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.formatting.rule import FormulaRule

    blue, grey = "1F4E79", "EAF0F6"
    numeric_format = '#,##0.00;[Red](#,##0.00);0.00'
    balance = workbook["Balance Normalizado"]
    rows = complete.to_dict("records")
    index = {r["codigo_clasificado"]: start_row + i + 1 for i, r in enumerate(rows)}
    def ref(code):
        return f"'Balance Normalizado'!C{index[code]}"
    for code, dependencies in formulas.items():
        if code in index and complete.loc[complete.codigo_clasificado == code, "estado_presentacion"].iloc[0] == "Calculado":
            refs = [ref(k) for k in dependencies if k in index]
            balance.cell(index[code], 3, "=SUM(" + ",".join(refs) + ")" if refs else "=0")
    for i, record in enumerate(rows, start=start_row+1):
        balance.cell(i, 6, CATEGORY_LABELS.get(record["categoria"], record["categoria"]))
        balance.cell(i, 7, record["estado_presentacion"])
    balance.cell(start_row, 6, "Grupo")
    balance.cell(start_row, 7, "Estado")
    balance["E2"], balance["F2"] = "Fecha de proceso", processed_at
    balance["E3"], balance["F3"] = "Analista", None

    summary = workbook.create_sheet("Resumen")
    workbook.move_sheet(summary, offset=-len(workbook.sheetnames) + 1)
    metadata = [
        ("Informe de homologación", "DEFINITIVO" if definitive else "BORRADOR"),
        ("Empresa", getattr(meta, "razon_social", "") or ""),
        ("RUT", getattr(meta, "rut", "") or ""),
        ("Período", f'{getattr(meta, "periodo_desde", "") or ""} al {getattr(meta, "periodo_hasta", "") or ""}'),
        ("Moneda/unidad", unit), ("Fecha de proceso", processed_at),
        ("Analista", None), ("Documento fuente", source_name),
        ("Páginas analizadas", ", ".join(map(str, pages)) if pages else "Documento completo"),
        ("Criterio", "Cero = sin cuentas asignadas. No acredita que falte o no exista una cuenta en el original."),
    ]
    for entry in metadata:
        summary.append(entry)
    summary.append(["Control del balance", f"Importe ({unit})"])
    category_rows = {}
    for category in CATEGORY_ORDER[:-1]:
        row = summary.max_row + 1
        category_rows[category] = row
        refs = [ref(r["codigo_clasificado"]) for r in rows if r["categoria"] == category]
        summary.append([CATEGORY_LABELS[category], "=SUM(" + ",".join(refs) + ")" if refs else "=0"])
    summary.append(["TOTAL ACTIVOS", f"=SUM(B{category_rows['activo_corriente']}:B{category_rows['activo_no_corriente']})"])
    asset_row = summary.max_row
    summary.append(["TOTAL PASIVOS", f"=SUM(B{category_rows['pasivo_corriente']}:B{category_rows['pasivo_no_corriente']})"])
    liability_row = summary.max_row
    summary.append(["TOTAL PATRIMONIO", f"=B{category_rows['patrimonio']}"])
    equity_row = summary.max_row
    summary.append(["PASIVO + PATRIMONIO", f"=SUM(B{liability_row}:B{equity_row})"])
    right_row = summary.max_row
    summary.append(["Diferencia de cuadratura", f"=B{asset_row}-B{right_row}"])
    delta_row = summary.max_row
    summary.append(["Tolerancia de cuadratura", tolerance])
    tolerance_row = summary.max_row
    summary.append(["Cuadratura aritmética", f'=IF(ABS(B{delta_row})<=B{tolerance_row},"CUADRA DENTRO DE TOLERANCIA","NO CUADRA")'])
    summary.append(["Estado de emisión", "DEFINITIVO" if definitive else "BORRADOR: REQUIERE REVISIÓN"])
    summary.append(["Advertencia", "La cuadratura no sustituye la revisión de clasificación y extracción."])
    for reason in reasons:
        summary.append(["Pendiente de resolver", reason])

    income = workbook.create_sheet("Estado de Resultados")
    income.append(["Estado de resultados", unit, "Ingresos positivos, gastos negativos"])
    income.append(["Código", "Clasificación", f"Importe ({unit})", "Tipo"])
    for record in rows:
        if record["categoria"] != "resultado":
            continue
        code = record["codigo_clasificado"]
        value = None if record["estado_presentacion"] == "No disponible" else "=" + ref(code)
        income.append([code, record["nombre_estandar"], value, record["estado_presentacion"]])
    income.append(["", "No sumar los resultados calculados nuevamente al detalle."])
    income.append(["", "EBITDA: ventas + costo de ventas + gastos de administración + gastos de venta (importes con signo)."])
    # La validez del resultado se contrasta en Control de emisión, no se deduce
    # de la mera igualdad entre dos celdas calculadas desde la misma fuente.

    for sheet in (summary, income, balance):
        sheet.sheet_view.showGridLines = False
        sheet.freeze_panes = "C3" if sheet is income else ("C11" if sheet is summary else f"C{start_row+1}")
        sheet.sheet_properties.pageSetUpPr.fitToPage = True
        sheet.page_setup.orientation = "landscape"
        sheet.page_setup.paperSize = sheet.PAPERSIZE_A4
        sheet.page_setup.fitToWidth = 1
        sheet.page_setup.fitToHeight = 0
        sheet.print_options.horizontalCentered = True
        for row in sheet:
            for cell in row:
                cell.alignment = Alignment(vertical="center", wrap_text=True)
                if isinstance(cell.value, (int, float)) or (cell.data_type == "f" and "IF(" not in cell.value):
                    cell.number_format = numeric_format
                    cell.alignment = Alignment(horizontal="right", vertical="center")
        for column in range(1, sheet.max_column+1):
            sheet.column_dimensions[get_column_letter(column)].width = 24
    summary.column_dimensions["A"].width = 33
    summary.column_dimensions["B"].width = 92
    income.column_dimensions["B"].width = 66
    income.column_dimensions["D"].width = 25
    balance.column_dimensions["B"].width = 48
    balance.column_dimensions["F"].width = 40
    for row in range(start_row + 1, start_row + len(rows) + 1):
        balance.cell(row, 4).number_format = "0"
    for sheet, headers in ((summary, (1, 11)), (income, (1, 2)), (balance, (start_row,))):
        for header in headers:
            for cell in sheet[header]:
                cell.fill = PatternFill("solid", fgColor=blue)
                cell.font = Font(bold=True, color="FFFFFF")
        sheet.print_title_rows = f"1:{max(headers)}"
    for row in range(asset_row, delta_row+1):
        for cell in summary[row]:
            cell.fill = PatternFill("solid", fgColor=grey)
            cell.font = Font(bold=True)
            cell.border = Border(top=Side(style="thin", color=blue))
    summary.conditional_formatting.add(
        f"B{delta_row}", FormulaRule(
            formula=[f"ABS(B{delta_row})>B{tolerance_row}"],
            fill=PatternFill("solid", fgColor="FFC7CE")))
    for i, record in enumerate([r for r in rows if r["categoria"] == "resultado"], start=3):
        if record["codigo_clasificado"] in CALCULATED:
            for cell in income[i]:
                cell.font = Font(bold=True)
                cell.fill = PatternFill("solid", fgColor=grey)
