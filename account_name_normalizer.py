"""account_name_normalizer.py — Normalizador configurable de nombres de cuentas.

Capa de conocimiento (Sprint 37). NO modifica el Parser Universal ni el
pipeline: es una función pura reutilizable por el motor de sinónimos, las
reglas especiales y el reporte de cobertura.

Normaliza: acentos, mayúsculas, símbolos, espacios, puntos, guiones,
abreviaciones, errores OCR frecuentes y (opcionalmente) plurales.

Todo es configurable: cada etapa usa un mapa del diccionario `config`.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Configuración por defecto (todo sobreescribible al instanciar)
# ---------------------------------------------------------------------------

DEFAULT_CONFIG: Dict[str, Any] = {
    # Abreviaciones → forma completa (boundary de palabra, las más largas primero)
    "abreviaciones": {
        "cta.": "cuenta",
        "ctas.": "cuentas",
        "cta": "cuenta",
        "ctas": "cuentas",
        "cte.": "corriente",
        "cte": "corriente",
        "cta cte.": "cuenta corriente",
        "cta cte": "cuenta corriente",
        "cta cte socios": "cuenta corriente socios",
        "ctc": "cuenta corriente",
        "c t c": "cuenta corriente",
        "c/c": "cuenta corriente",
        "c.c.": "cuenta corriente",
        "c c": "cuenta corriente",
        "cc": "cuenta corriente",
        "vta.": "venta",
        "vta": "venta",
        "deud": "deudores",
        "acreed": "acreedores",
        "acr": "acreedores",
        "cli": "clientes",
        "cxc": "cuentas por cobrar",
        "cxc.": "cuentas por cobrar",
        "c x c": "cuentas por cobrar",
        "cxp": "cuentas por pagar",
        "cxp.": "cuentas por pagar",
        "c x p": "cuentas por pagar",
        "deud.": "deudores",
        "acreed.": "acreedores",
        "prov.": "proveedores",
        "docs": "documentos",
        "doc.": "documentos",
        "doctos": "documentos",
        "docto": "documento",
        "acum.": "acumulada",
        "acum": "acumulada",
        "dep.": "depreciacion",
        "dep": "depreciacion",
        "amort.": "amortizacion",
        "amort": "amortizacion",
        "ptmo": "prestamo",
        "ptmos": "prestamos",
        "ptm": "prestamo",
        "ptmos.": "prestamos",
        "soc.": "sociedad",
        "s.a.": "sociedad anonima",
        "s.a": "sociedad anonima",
        "ltda": "limitada",
        "ltda.": "limitada",
        "spa": "sociedad por acciones",
        "eeff": "estados financieros",
        "eerr": "empresas relacionadas",
        "e.e.r.r.": "empresas relacionadas",
        "er": "estado de resultados",
        "ppm": "pagos provisionales mensuales",
        "p.p.m.": "pagos provisionales mensuales",
        "impto": "impuesto",
        "imptos": "impuestos",
        "rem.": "remuneraciones",
        "rem": "remuneraciones",
        "adm.": "administracion",
        "adm": "administracion",
        "vehic.": "vehiculos",
        "vehic": "vehiculos",
        "eq.": "equipos",
        "eq": "equipos",
        "mob.": "mobiliario",
        "mob": "mobiliario",
        "inst.": "instalaciones",
        "inst": "instalaciones",
        "terr.": "terrenos",
        "terr": "terrenos",
        "cfe": "cuentas por cobrar",
        "dpp": "deudores por ventas",
        "iva": "iva",
        "pnc": "pasivo no corriente",
        "pc": "pasivo corriente",
        "anc": "activo no corriente",
        "ac": "activo corriente",
        "pat": "patrimonio",
        "af": "activo fijo",
        "afi": "activo fijo",
        "cps": "cuenta particular socios",
        "cta pte": "cuenta particular",
    },
    # Errores OCR frecuentes (token → corrección)
    "errores_ocr": {
        "0": "o",
        "l": "i",
        "|": "i",
        "|n": "in",
        "tn": "m",
        "ci": "d",
        "a1": "al",
        "rn": "m",
        "vv": "w",
        "vvv": "w",
        "1l": "il",
    },
    # Símbolos → espacio
    "simbolos": {
        "$": " ",
        "%": " ",
        "#": " ",
        "@": " ",
        "&": " y ",
        "+": " ",
        "=": " ",
        "*": " ",
        "/": " ",
        "\\": " ",
        "(": " ",
        ")": " ",
        "[": " ",
        "]": " ",
        "{": " ",
        "}": " ",
        ":": " ",
        ";": " ",
        ",": " ",
        ".": " ",
        "¿": " ",
        "?": " ",
        "¡": " ",
        "!": " ",
        "-": " ",
        "_": " ",
        "–": " ",
        "—": " ",
        "“": " ",
        "”": " ",
        "'": " ",
        '"': " ",
        "·": " ",
        "•": " ",
    },
    # Plurales irregulares / frecuentes → singular (aplicado a tokens completos)
    "plurales": {
        "cuentas": "cuenta",
        "bancos": "banco",
        "impuestos": "impuesto",
        "prestamos": "prestamo",
        "socios": "socio",
        "accionistas": "accionista",
        "retiros": "retiro",
        "giros": "giro",
        "marcas": "marca",
        "patentes": "patente",
        "concesiones": "concesion",
        "inversiones": "inversion",
        "mercaderias": "mercaderia",
        "existencias": "existencia",
        "proveedores": "proveedor",
        "deudores": "deudor",
        "acreedores": "acreedor",
        "relacionadas": "relacionada",
        "relacionados": "relacionado",
        "acumuladas": "acumulada",
        "acumulados": "acumulado",
        "retenidas": "retenida",
        "utilidades": "utilidad",
        "reservas": "reserva",
        "anticipos": "anticipo",
        "dividendos": "dividendo",
        "mutuos": "mutuo",
        "derivados": "derivado",
        "arriendos": "arriendo",
        "seguros": "seguro",
        "comisiones": "comision",
        "honorarios": "honorario",
        "sueldos": "sueldo",
        "salarios": "salario",
        "remuneraciones": "remuneracion",
        "obligaciones": "obligacion",
        "reajustes": "reajuste",
        "diferencias": "diferencia",
        "ganancias": "ganancia",
        "perdidas": "perdida",
        "impuestos": "impuesto",
        "documentos": "documento",
        "intereses": "interes",
    },
    # Palabras que se eliminan de la clave de agrupación (ruido)
    "stopwords": {
        "de", "la", "el", "los", "las", "del", "al", "y", "e", "o", "a",
        "por", "para", "en", "con", "sobre", "entre", "monto", "mes",
    },
}


class AccountNameNormalizer:
    """Normalizador configurable de nombres de cuentas.

    Uso:

        n = AccountNameNormalizer()
        n.normalizar("Cta. Cte. Socios")   # → "cuenta corriente socios"
        n.clave("C.T.C. SOCIOS")           # → clave para agrupar sinónimos
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        cfg = dict(DEFAULT_CONFIG)
        if config:
            for key, value in config.items():
                if isinstance(value, dict) and isinstance(cfg.get(key), dict):
                    cfg[key].update(value)
                else:
                    cfg[key] = value
        self.config = cfg
        # Abreviaciones ordenadas por longitud (las más largas primero)
        self._abreviaciones = sorted(
            cfg.get("abreviaciones", {}).items(),
            key=lambda kv: -len(kv[0]),
        )
        self._abreviaciones_compiladas = [
            (re.compile(rf"\b{re.escape(k)}\b"), v)
            for k, v in self._abreviaciones
        ]
        self._simbolos = cfg.get("simbolos", {})
        self._errores_ocr = cfg.get("errores_ocr", {})
        self._plurales = cfg.get("plurales", {})
        self._stopwords = cfg.get("stopwords", set())

    # ------------------------------------------------------------------
    # Etapas individuales
    # ------------------------------------------------------------------

    @staticmethod
    def quitar_acentos(texto: str) -> str:
        return unicodedata.normalize("NFKD", texto).encode(
            "ascii", "ignore"
        ).decode("ascii")

    def simbolos_a_espacios(self, texto: str) -> str:
        out = texto
        for simbolo, reemplazo in self._simbolos.items():
            out = out.replace(simbolo, reemplazo)
        return out

    def expandir_abreviaciones(self, texto: str) -> str:
        out = texto
        for patron, reemplazo in self._abreviaciones_compiladas:
            out = patron.sub(reemplazo, out)
        return out

    def corregir_ocr(self, texto: str) -> str:
        if not self._errores_ocr:
            return texto
        tokens = texto.split()
        corregidos = []
        for tok in tokens:
            if tok in self._errores_ocr and len(tok) <= 4:
                tok = self._errores_ocr[tok]
            corregidos.append(tok)
        return " ".join(corregidos)

    def plural_a_singular(self, texto: str) -> str:
        tokens = texto.split()
        return " ".join(self._plurales.get(t, t) for t in tokens)

    def quitar_stopwords(self, texto: str) -> str:
        tokens = texto.split()
        return " ".join(t for t in tokens if t not in self._stopwords)

    # ------------------------------------------------------------------
    # Pipeline completo
    # ------------------------------------------------------------------

    def normalizar(
        self,
        nombre: str,
        *,
        expandir_abreviaciones: bool = True,
        corregir_ocr: bool = False,
        plural: bool = False,
        quitar_stopwords: bool = False,
    ) -> str:
        """Normaliza un nombre a su forma canónica (minúsculas, sin acentos)."""
        if nombre is None:
            return ""
        texto = str(nombre).strip().lower()
        texto = self.quitar_acentos(texto)
        texto = self.simbolos_a_espacios(texto)
        texto = re.sub(r"\s+", " ", texto).strip()
        if expandir_abreviaciones:
            texto = self.expandir_abreviaciones(texto)
        if corregir_ocr:
            texto = self.corregir_ocr(texto)
        if plural:
            texto = self.plural_a_singular(texto)
        if quitar_stopwords:
            texto = self.quitar_stopwords(texto)
        return re.sub(r"\s+", " ", texto).strip()

    def clave(self, nombre: str, *, plural: bool = True) -> str:
        """Clave canónica para agrupar variantes de un mismo concepto.

        Normaliza, expande abreviaciones, unifica plurales y descarta
        stopwords. Dos nombres con la misma clave se consideran variantes.
        """
        return self.normalizar(
            nombre,
            expandir_abreviaciones=True,
            corregir_ocr=True,
            plural=plural,
            quitar_stopwords=True,
        )

    def tokenizar(self, nombre: str, *, plural: bool = True) -> List[str]:
        return self.clave(nombre, plural=plural).split()


_normalizador_global = AccountNameNormalizer()


def normalizar_nombre(
    nombre: str,
    *,
    expandir_abreviaciones: bool = True,
    corregir_ocr: bool = False,
    plural: bool = False,
    quitar_stopwords: bool = False,
) -> str:
    """Función de conveniencia usando la configuración por defecto."""
    return _normalizador_global.normalizar(
        nombre,
        expandir_abreviaciones=expandir_abreviaciones,
        corregir_ocr=corregir_ocr,
        plural=plural,
        quitar_stopwords=quitar_stopwords,
    )


def clave_normalizada(nombre: str, *, plural: bool = True) -> str:
    return _normalizador_global.clave(nombre, plural=plural)
