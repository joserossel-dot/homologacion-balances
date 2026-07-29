from __future__ import annotations
from .subtotal_trace import HierarchyComparison


SECTION_MARKERS = {
    "activo": "ACTIVO",
    "pasivo": "PASIVO",
    "patrimonio": "PATRIMONIO",
    "resultado": "RESULTADO",
    "ingreso": "INGRESOS",
    "costo": "COSTOS",
    "gasto": "GASTOS",
}


def _classify_section(name: str) -> str:
    n = name.strip().lower()
    for marker, section in SECTION_MARKERS.items():
        if n.startswith(marker):
            return section
    return ""


def _normalize_name(name: str) -> str:
    return name.strip().lower()


class HierarchyComparator:

    @staticmethod
    def compare(
        account_name: str,
        amount: float,
        line_number: int,
        all_accounts: list[dict],
        subtotal_results: list,
    ) -> HierarchyComparison:
        hc = HierarchyComparison(
            account_name=account_name,
            amount=amount,
        )

        acct = None
        for a in all_accounts:
            name = str(a.get("nombre", a.get("account_name", ""))).strip()
            if _normalize_name(name) == _normalize_name(account_name):
                acct = a
                break

        if acct is None:
            for a in all_accounts:
                name = str(a.get("nombre", a.get("account_name", ""))).strip()
                if account_name.lower() in name.lower():
                    acct = a
                    break

        if acct:
            hc.exists = True
            hc.account_code = acct.get("codigo", acct.get("account_code", ""))
            hc.found_section = _classify_section(
                acct.get("nombre", acct.get("account_name", ""))
            )
        else:
            hc.exists = False
            return hc

        expected_section = ""
        name_lower = account_name.lower()
        for sr in subtotal_results:
            if sr.passed:
                continue
            sr_name_lower = sr.account_name.lower()
            if name_lower in sr_name_lower or sr_name_lower in name_lower:
                continue

        if hc.found_section:
            for marker, section in SECTION_MARKERS.items():
                if name_lower.startswith(marker):
                    expected_section = section
                    break

        hc.expected_section = expected_section
        if expected_section and hc.found_section:
            hc.in_other_section = expected_section != hc.found_section

        if hc.found_section and expected_section:
            hc.under_correct_parent = expected_section == hc.found_section

        for sr in subtotal_results:
            sr_name_lower = sr.account_name.lower()
            if account_name.lower() in sr_name_lower or sr_name_lower in account_name.lower():
                continue
            for child_name in sr.children:
                if account_name.lower() in child_name.lower():
                    hc.in_other_subtotal = True
                    break

        return hc

    @staticmethod
    def find_duplicates(
        account_name: str,
        all_accounts: list[dict],
    ) -> list[dict]:
        name_norm = _normalize_name(account_name)
        duplicates = []
        for a in all_accounts:
            a_name = str(a.get("nombre", a.get("account_name", ""))).strip()
            if _normalize_name(a_name) == name_norm:
                amt = a.get("amount", a.get("monto", 0)) or 0
                if isinstance(amt, str):
                    try:
                        amt = float(amt.replace(".", "").replace(",", "."))
                    except (ValueError, TypeError):
                        amt = 0.0
                duplicates.append({
                    "account_name": a_name,
                    "amount": float(amt),
                    "line": a.get("linea", a.get("source_line", -1)),
                })
        return duplicates

    @staticmethod
    def find_in_other_sections(
        account_name: str,
        all_accounts: list[dict],
    ) -> list[dict]:
        name_norm = _normalize_name(account_name)
        found = []
        for a in all_accounts:
            a_name = str(a.get("nombre", a.get("account_name", ""))).strip()
            if _normalize_name(a_name) == name_norm:
                continue
            if account_name.lower() in a_name.lower():
                amt = a.get("amount", a.get("monto", 0)) or 0
                if isinstance(amt, str):
                    try:
                        amt = float(amt.replace(".", "").replace(",", "."))
                    except (ValueError, TypeError):
                        amt = 0.0
                section = _classify_section(a_name)
                found.append({
                    "account_name": a_name,
                    "amount": float(amt),
                    "section": section,
                    "line": a.get("linea", a.get("source_line", -1)),
                })
        return found
