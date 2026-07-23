from __future__ import annotations

from collections import defaultdict

from rapidfuzz.fuzz import token_sort_ratio

from knowledge.unknown_cluster import normalize_name


KNOWN_SYNONYM_GROUPS: list[list[str]] = [
    ["caja", "caja general", "caja central", "caja m/n", "caja moneda nacional", "caja mn"],
    ["clientes", "cta cte clientes", "deudores por venta", "cuentas por cobrar clientes"],
    ["proveedores", "cta cte proveedores", "acreedores comerciales", "cuentas por pagar proveedores"],
    ["honorarios", "honorarios profesionales", "honorarios por pagar"],
    ["iva", "iva credito fiscal", "iva debito fiscal", "iva credito", "iva debito"],
    ["depreciacion", "depreciacion acumulada", "deprec acumulada", "depreciacion del ejercicio"],
    ["amortizacion", "amortizacion acumulada", "amortiz del ejercicio"],
    ["inventarios", "existencias", "mercaderias", "stock"],
    ["banco", "bancos", "banco estado", "banco chile", "banco santander"],
    ["capital", "capital social", "aporte de capital", "capital suscrito y pagado"],
    ["remuneraciones", "sueldos", "salarios", "remuneraciones por pagar"],
    ["provision", "provisiones", "provision vacaciones", "provision aguinaldo"],
    ["anticipo", "anticipos", "anticipo proveedores", "anticipos de clientes"],
    ["gastos", "gastos generales", "gastos de administracion", "gastos operacionales"],
    ["ingresos", "ingresos operacionales", "ingresos por venta", "ingresos ordinarios"],
    ["cuentas por cobrar", "documentos por cobrar", "deudores"],
    ["cuentas por pagar", "documentos por pagar", "acreedores"],
    ["maquinaria", "maquinarias", "equipos", "maquinaria y equipo"],
    ["terreno", "terrenos", "bienes raices"],
    ["vehiculo", "vehiculos", "automovil", "camioneta", "camion"],
    ["muebles", "mobiliario", "equipo de oficina", "enseres"],
    ["intangibles", "patentes", "marcas", "derechos de llave"],
    ["inversiones", "inversiones financieras", "colocaciones"],
    ["utilidad", "resultado", "ganancia", "perdida"],
    ["accion", "acciones", "participaciones"],
    ["retencion", "retenciones", "impuesto retenido"],
    ["leasing", "arriendo", "arrendamiento financiero"],
    ["factoring", "factoraje"],
    ["credito", "prestamo", "prestamo bancario"],
]


def detect_synonyms(
    accounts: list[dict],
    *,
    threshold: float = 80.0,
) -> list[dict]:
    names = _collect_unique_names(accounts)
    norm_map = {n: normalize_name(n) for n in names}
    found: list[dict] = []

    for group in KNOWN_SYNONYM_GROUPS:
        matched = []
        for raw_name, norm in norm_map.items():
            for keyword in group:
                if keyword in norm:
                    matched.append(raw_name)
                    break
        if len(matched) >= 2:
            found.append({
                "group_label": group[0].title(),
                "keywords": group,
                "variants": _dedup_ordered(matched),
                "num_variants": len(_dedup_ordered(matched)),
                "detected_by": "keyword_group",
            })

    auto = _detect_auto_synonyms(norm_map, threshold)
    found.extend(auto)

    seen_labels: set[str] = set()
    deduped: list[dict] = []
    for g in found:
        label = g["group_label"]
        if label not in seen_labels:
            seen_labels.add(label)
            deduped.append(g)
        else:
            existing = next(d for d in deduped if d["group_label"] == label)
            existing_vars = set(existing["variants"])
            for v in g["variants"]:
                if v not in existing_vars:
                    existing["variants"].append(v)
            existing["num_variants"] = len(existing["variants"])

    return deduped


def _collect_unique_names(accounts: list[dict]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for a in accounts:
        name = a.get("account_name", "")
        if name and name not in seen:
            seen.add(name)
            result.append(name)
    return result


def _dedup_ordered(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _detect_auto_synonyms(
    norm_map: dict[str, str],
    threshold: float,
) -> list[dict]:
    names = list(norm_map.keys())
    groups: list[list[str]] = []
    assigned: set[int] = set()

    for i in range(len(names)):
        if i in assigned:
            continue
        group = [names[i]]
        assigned.add(i)
        for j in range(i + 1, len(names)):
            if j in assigned:
                continue
            score = token_sort_ratio(norm_map[names[i]], norm_map[names[j]])
            if score >= threshold:
                group.append(names[j])
                assigned.add(j)
        if len(group) >= 3:
            groups.append(group)

    result: list[dict] = []
    for g in groups:
        label = normalize_name(g[0])
        words = label.split()
        label_short = " ".join(words[:3]) if words else label
        result.append({
            "group_label": label_short.title(),
            "keywords": [],
            "variants": g,
            "num_variants": len(g),
            "detected_by": "auto_similarity",
        })
    return result
