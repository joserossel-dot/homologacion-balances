"""special_account_rules.py — Reglas especiales de la contabilidad chilena.

Capa de conocimiento (Sprint 37). Reconoce cuentas típicas chilenas que el
clasificador genérico confunde o no distingue (cuentas con socios/accionistas,
impuestos diferidos, leasing, derivados, intangibles, etc.).

Cada regla incluye:
  - codigo          : código del catálogo maestro cuando existe (None si no).
  - concepto        : nombre canónico del concepto reconocido.
  - patrones        : subcadenas normalizadas que activan la regla.
  - confianza       : nivel de confianza (0-1).
  - explicacion     : qué detecta.
  - motivo          : por qué se distingue del catálogo genérico.

NO modifica el flujo actual: es una capa de conocimiento pura.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from account_name_normalizer import AccountNameNormalizer

_normalizador = AccountNameNormalizer()


def _norm(texto: str) -> str:
    return _normalizador.normalizar(texto, expandir_abreviaciones=True)


def _clave(texto: str) -> str:
    return _normalizador.clave(texto, plural=True)


# ---------------------------------------------------------------------------
# Catálogo de reglas
# ---------------------------------------------------------------------------

RULES: List[Dict[str, Any]] = [
    {
        "codigo": "PAT.10",
        "concepto": "Cuenta Particular Socios",
        "nombre": "Cuenta Particular Socios",
        "patrones": [
            "particular socio", "particular accionista", "corriente socio",
            "corriente accionista", "cuenta socio", "cuenta accionista",
            "prestamo socio", "prestamo accionista", "prestamos socio",
            "prestamos accionista", "anticipo socio", "anticipo accionista",
            "retiro socio", "retiro accionista", "retiros socios",
            "giro socio", "giros socios", "cxc socio", "cxc accionista",
            "c x c socio", "cps", "cta socio", "cta particular",
        ],
        "confianza": 0.95,
        "explicacion": "Reconoce cuentas corrientes o particulares con socios o "
                       "accionistas (préstamos, anticipos, retiros, giros).",
        "motivo": "Es el saldo deudor/acreedor con los socios; en la práctica "
                  "chilena se reporta como 'Cuenta Particular Socios' o 'Cuenta "
                  "Corriente Socios' y no debe confundirse con clientes ni con "
                  "proveedores.",
    },
    {
        "codigo": "PAT.11",
        "concepto": "Interés Minoritario",
        "nombre": "Interés Minoritario",
        "patrones": ["interes minoritario", "interes no controlador",
                     "minoritario"],
        "confianza": 0.97,
        "explicacion": "Reconoce la participación de accionistas minoritarios en "
                       "el patrimonio de la controlada.",
        "motivo": "Nombre histórico chileno; en IFRS se llama 'Participación No "
                  "Controladora' (PAT.05). Debe quedar en patrimonio, no en "
                  "resultados.",
    },
    {
        "codigo": "PAT.05",
        "concepto": "Participación No Controladora",
        "nombre": "Participación No Controladora",
        "patrones": ["participacion no controladora", "participacion no controlador",
                     "participacion de no controladores", "pnc"],
        "confianza": 0.97,
        "explicacion": "Reconoce la porción de patrimonio de una controlada "
                       "atribuible a terceros no controladores.",
        "motivo": "Cuenta de patrimonio (IFRS 10). Sustituye a 'Interés "
                  "Minoritario'.",
    },
    {
        "codigo": "PAT.08",
        "concepto": "Reserva Técnica Revalorización Activo Fijo",
        "nombre": "Reserva Técnica Revalorización Activo Fijo",
        "patrones": ["reserva tecnica revalorizacion", "reserva revalorizacion",
                     "revalorizacion activo fijo", "reserva tecnica"],
        "confianza": 0.93,
        "explicacion": "Reserva de patrimonio originada por revalorización "
                       "técnica del activo fijo.",
        "motivo": "Se presenta en patrimonio separada de reservas de resultados "
                  "(PAT.02).",
    },
    {
        "codigo": "ANC.08",
        "concepto": "Goodwill",
        "nombre": "Goodwill / Plusvalía",
        "patrones": ["goodwill", "plusvalia", "plusvalia comprada",
                     "diferencia positiva combinacion negocio"],
        "confianza": 0.96,
        "explicacion": "Exceso del costo de adquisición sobre el valor justo de "
                       "los activos netos adquiridos.",
        "motivo": "Activo intangible no amortizable (IFRS 3); no debe clasificarse "
                  "como otro activo fijo.",
    },
    {
        "codigo": "ANC.02",
        "concepto": "Propiedades de Inversión",
        "nombre": "Propiedades de Inversión",
        "patrones": ["propiedades de inversion", "propiedad de inversion",
                     "inversion inmobiliaria", "inmuebles de inversion"],
        "confianza": 0.95,
        "explicacion": "Inmuebles mantenidos para obtener rentas o plusvalía.",
        "motivo": "IFRS 40: no se deprecian si se valorizan a valor razonable; se "
                  "separa de activo fijo operativo (ANC.01).",
    },
    {
        "codigo": "AC.09",
        "concepto": "Activos Biológicos",
        "nombre": "Activos Biológicos",
        "patrones": ["activo biologico", "activos biologicos", "plantaciones",
                     "animales vivos", "vino en proceso", "rebanos"],
        "confianza": 0.94,
        "explicacion": "Animales o plantas vivos (IAS 41). Corrientes (AC.09) o "
                       "no corrientes (ANC.07) según ciclo de producción.",
        "motivo": "Regulados por IAS 41 a valor razonable; no son inventario "
                  "común ni activo fijo.",
    },
    {
        "codigo": "ANC.03",
        "concepto": "Patentes y Marcas",
        "nombre": "Patentes / Marcas / Intangibles",
        "patrones": ["patente", "marca", "marcas", "derechos de agua",
                     "concesiones", "concesion", "licencias", "software",
                     "intangibles", "intangible", "franquicia"],
        "confianza": 0.90,
        "explicacion": "Activos intangibles identificables (patentes, marcas, "
                       "concesiones, licencias, derechos de agua).",
        "motivo": "Se separan de goodwill (ANC.08) y del activo fijo tangible.",
    },
    {
        "codigo": None,
        "concepto": "Activos por Impuesto Diferido",
        "nombre": "Activos por Impuesto Diferido",
        "patrones": ["impuesto diferido activo", "activo por impuesto diferido",
                     "activos por impuestos diferidos", "impuestos diferidos activo"],
        "confianza": 0.92,
        "explicacion": "Activos tributarios por diferencias temporarias "
                       "deducibles o pérdidas compensables.",
        "motivo": "IAS 12: se presenta en el activo, distinto de impuestos por "
                  "pagar. Falta código específico en el catálogo.",
        "categoria_sugerida": "activo_no_corriente",
    },
    {
        "codigo": None,
        "concepto": "Pasivos por Impuesto Diferido",
        "nombre": "Pasivos por Impuesto Diferido",
        "patrones": ["impuesto diferido pasivo", "pasivo por impuesto diferido",
                     "pasivos por impuestos diferidos", "impuestos diferidos pasivo"],
        "confianza": 0.92,
        "explicacion": "Pasivos tributarios por diferencias temporarias "
                       "imponibles.",
        "motivo": "IAS 12: pasivo no monetario, distinto de impuestos por pagar. "
                  "Falta código específico en el catálogo.",
        "categoria_sugerida": "pasivo_no_corriente",
    },
    {
        "codigo": "PC.03",
        "concepto": "Pasivos por Leasing",
        "nombre": "Pasivos Leasing (CP/LP)",
        "patrones": ["obligacion leasing", "obligaciones leasing", "pasivo leasing",
                     "deuda leasing", "leasing por pagar", "leaseback por pagar"],
        "confianza": 0.90,
        "explicacion": "Obligaciones por contratos de arrendamiento financiero.",
        "motivo": "IFRS 16: la obligación es deuda (PC.03 corto plazo / PNC.02 "
                  "largo plazo), distinta del arriendo operativo.",
    },
    {
        "codigo": "PC.04",
        "concepto": "Factoring",
        "nombre": "Factoring",
        "patrones": ["factoring", "cesion facturas", "facturas cedidas"],
        "confianza": 0.93,
        "explicacion": "Financiamiento mediante cesión de cuentas por cobrar.",
        "motivo": "Deuda financiera de corto plazo (PC.04).",
    },
    {
        "codigo": "PC.07",
        "concepto": "Obligaciones con Relacionadas",
        "nombre": "Obligaciones / Cuentas con Relacionadas",
        "patrones": ["relacionada", "relacionadas", "empresas relacionadas",
                     "partes relacionadas", "obligaciones relacionadas",
                     "cuenta relacionada", "mutuos relacionadas",
                     "mutuo relacionada"],
        "confianza": 0.88,
        "explicacion": "Cuentas por cobrar/pagar con empresas o partes "
                       "relacionadas (corto y largo plazo).",
        "motivo": "Se reportan por separado según IFRS 24; existen códigos "
                  "AC.06 (activo), PC.07 (pasivo CP), PNC.04 (pasivo LP).",
    },
    {
        "codigo": None,
        "concepto": "Derivados",
        "nombre": "Instrumentos Financieros Derivados",
        "patrones": ["derivado", "derivados", "forward", "forwards", "swap",
                     "swaps", "opcion financiera", "futuro financiero",
                     "cobertura tasa", "cobertura de tasa"],
        "confianza": 0.88,
        "explicacion": "Instrumentos derivados (forward, swap, opciones, "
                       "futuros) a valor razonable.",
        "motivo": "IFRS 9: se valorizan a valor razonable y se presentan como "
                  "activos o pasivos derivados. Falta código en el catálogo.",
        "categoria_sugerida": "activo_no_corriente",
    },
    {
        "codigo": "PC.02",
        "concepto": "Mutuos",
        "nombre": "Mutuos",
        "patrones": ["mutuo", "mutuos", "prestamo mutuo"],
        "confianza": 0.87,
        "explicacion": "Préstamos de dinero (con o sin interés) entre partes.",
        "motivo": "Financiamiento; cuando es con relacionadas se reporta en "
                  "cuentas relacionadas (IFRS 24).",
    },
    {
        "codigo": None,
        "concepto": "Dividendos por Pagar",
        "nombre": "Dividendos por Pagar",
        "patrones": ["dividendo por pagar", "dividendos por pagar",
                     "dividendos a pagar", "dividendo provisorio por pagar"],
        "confianza": 0.95,
        "explicacion": "Obligación de pagar dividendos declarados o provisorios.",
        "motivo": "Pasivo corriente por ley (Ley 18.046). Falta código específico "
                  "en el catálogo.",
        "categoria_sugerida": "pasivo_corriente",
    },
    {
        "codigo": None,
        "concepto": "Dividendos Anticipados",
        "nombre": "Dividendos Anticipados",
        "patrones": ["dividendo anticipado", "dividendos anticipados",
                     "dividendos provisionales pagados", "dividendo provisorio pagado"],
        "confianza": 0.90,
        "explicacion": "Dividendos provisionales pagados durante el ejercicio; "
                       "cuenta deudora contra patrimonio.",
        "motivo": "Es una cuenta regularizadora del patrimonio (deudora), no un "
                  "gasto. Falta código en el catálogo.",
        "categoria_sugerida": "patrimonio",
    },
    {
        "codigo": "ANC.01",
        "concepto": "Activos en Leasing",
        "nombre": "Activos en Leasing",
        "patrones": ["activo en leasing", "activos en leasing", "bienes en leasing",
                     "vehiculos en leasing", "maquinaria en leasing"],
        "confianza": 0.89,
        "explicacion": "Activos por derecho de uso bajo arrendamiento financiero.",
        "motivo": "IFRS 16: se reconocen como activo (derecho de uso) con su "
                  "correspondiente pasivo.",
    },
    {
        "codigo": None,
        "concepto": "Leaseback",
        "nombre": "Leaseback",
        "patrones": ["leaseback", "sale and leaseback", "venta con arrendamiento"],
        "confianza": 0.90,
        "explicacion": "Operación de venta de un activo seguida de su "
                       "arrendamiento de vuelta.",
        "motivo": "IFRS 16: genera un derecho de uso y una obligación; se "
                  "presenta por separado de la venta ordinaria.",
        "categoria_sugerida": "pasivo_no_corriente",
    },
]


class SpecialAccountRules:
    """Motor de reglas especiales chilenas (capa de conocimiento pura)."""

    def __init__(self, rules: Optional[List[Dict[str, Any]]] = None) -> None:
        self.rules: List[Dict[str, Any]] = []
        for regla in rules if rules is not None else RULES:
            copia = dict(regla)
            copia["patrones_norm"] = [
                (_norm(p), _clave(p)) for p in regla["patrones"]
            ]
            self.rules.append(copia)

    def _matchea(self, texto_norm: str, texto_clave: str, regla: Dict[str, Any]) -> Optional[str]:
        for patron_norm, patron_clave in regla["patrones_norm"]:
            for patron, texto in ((patron_norm, texto_norm), (patron_clave, texto_clave)):
                if not patron:
                    continue
                if len(patron) <= 3:
                    if re.search(rf"\b{re.escape(patron)}\b", texto):
                        return patron
                elif patron in texto:
                    return patron
        return None

    def detectar(self, nombre: str) -> List[Dict[str, Any]]:
        """Todas las reglas que matchean `nombre` (ordenadas por confianza)."""
        texto_norm = _norm(nombre)
        if len(texto_norm) < 3:
            return []
        texto_clave = _clave(nombre)
        resultados = []
        for regla in self.rules:
            patron = self._matchea(texto_norm, texto_clave, regla)
            if patron is None:
                continue
            resultados.append({
                "codigo": regla["codigo"],
                "concepto": regla["concepto"],
                "nombre": regla["nombre"],
                "confianza": regla["confianza"],
                "explicacion": regla["explicacion"],
                "motivo": regla["motivo"],
                "categoria_sugerida": regla.get("categoria_sugerida"),
                "patron_match": patron,
            })
        resultados.sort(key=lambda r: -r["confianza"])
        return resultados

    def detectar_uno(self, nombre: str) -> Optional[Dict[str, Any]]:
        resultados = self.detectar(nombre)
        return resultados[0] if resultados else None

    def cubierto(self, nombre: str) -> bool:
        return bool(self.detectar(nombre))


_reglas_globales = SpecialAccountRules()


def detectar_reglas_especiales(nombre: str) -> List[Dict[str, Any]]:
    return _reglas_globales.detectar(nombre)


def aplicar_reglas_especiales(nombre: str) -> Optional[Dict[str, Any]]:
    return _reglas_globales.detectar_uno(nombre)
