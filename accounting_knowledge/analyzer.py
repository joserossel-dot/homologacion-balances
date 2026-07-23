"""Accounting Knowledge Base Analyzer — 7-stage shadow analysis.

Stage 1: Vocabulary building (tokenization, normalization, frequency)
Stage 2: Abbreviation discovery
Stage 3: Synonym discovery
Stage 4: Family discovery
Stage 5: Canonicalization
Stage 6: Coverage projection
Stage 7: Top opportunities ranking
"""

import re
import time
import json
import statistics
import unicodedata
from pathlib import Path
from collections import Counter, defaultdict
from typing import Any

import pandas as pd

from validation.dataset_manager import DatasetManager
from parser_universal import ParserPDF
from app_validacion import parsear_excel


class AccountingKnowledgeBase:
    """Shadow analyzer that discovers knowledge from balance data."""

    EXCEL_DIR = Path("reports/accounting_knowledge")

    # Known accounting abbreviations (seeded from domain knowledge, validated statistically)
    KNOWN_ABBREVIATIONS: dict[str, list[str]] = {
        "dep": ["depreciacion", "depreciación", "deprec"],
        "depr": ["depreciacion", "depreciación", "deprec"],
        "deprec": ["depreciacion", "depreciación"],
        "amort": ["amortizacion", "amortización"],
        "bco": ["banco"],
        "bcos": ["bancos"],
        "cta": ["cuenta"],
        "ctas": ["cuentas"],
        "cte": ["corriente"],
        "c/c": ["cuenta corriente"],
        "cc": ["cuenta corriente"],
        "eerr": ["empresas relacionadas"],
        "e.e.r.r.": ["empresas relacionadas"],
        "ppm": ["pagos provisionales mensuales"],
        "p.p.m.": ["pagos provisionales mensuales"],
        "prov": ["provision", "provisión", "proveedores"],
        "pto": ["presupuesto"],
        "ptmo": ["prestamo", "préstamo"],
        "ptmos": ["prestamos", "préstamos"],
        "rem": ["remuneraciones"],
        "impto": ["impuesto"],
        "imptos": ["impuestos"],
        "iva": ["impuesto al valor agregado"],
        "adm": ["administracion", "administración"],
        "admin": ["administracion", "administración"],
        "cap": ["capital"],
        "pat": ["patrimonio"],
        "patr": ["patrimonio"],
        "acum": ["acumulada", "acumulado"],
        "ac": ["activo corriente", "acumulada"],
        "anc": ["activo no corriente"],
        "pc": ["pasivo corriente"],
        "pnc": ["pasivo no corriente"],
        "er": ["estado de resultados", "ejercicio"],
        "eeff": ["estados financieros"],
        "rr": ["relacionadas"],
        "s.a.": ["sociedad anonima", "sociedad anónima"],
        "ltda": ["limitada"],
        "spa": ["sociedad por acciones"],
        "m$": ["miles de pesos"],
        "uf": ["unidad de fomento"],
    }

    def __init__(self, datasets_root: str | Path = "datasets/"):
        self.datasets_root = Path(datasets_root)
        self.start_time: float = 0.0
        self.end_time: float = 0.0

        # Raw extracted data
        self.accounts: list[dict[str, Any]] = []  # Each: {nombre, archivo, grupo, codigo, monto}
        self.files_processed: int = 0
        self.files_failed: int = 0
        self.total_accounts_raw: int = 0

        # Stage 1: Vocabulary
        self.vocabulary: list[dict[str, Any]] = []

        # Stage 2: Abbreviations
        self.abbreviations: list[dict[str, Any]] = []

        # Stage 3: Synonyms
        self.synonyms: list[dict[str, Any]] = []

        # Stage 4: Families
        self.families: list[dict[str, Any]] = []

        # Stage 5: Canonicalization
        self.canonicalization: list[dict[str, Any]] = []

        # Stage 6: Coverage
        self.coverage_projection: list[dict[str, Any]] = {}

        # Stage 7: Opportunities
        self.top_opportunities: list[dict[str, Any]] = []

    # ------------------------------------------------------------------ #
    # HELPERS
    # ------------------------------------------------------------------ #

    @staticmethod
    def _normalize(text: str) -> str:
        """Remove accents, lowercase, strip punctuation."""
        text = text.lower().strip()
        text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Split into words, filtering numeric-only tokens."""
        words = text.split()
        return [w for w in words if not re.match(r"^\d+$", w) and len(w) > 1]

    @staticmethod
    def _get_company_from_file(filename: str) -> str:
        """Infer company name from filename."""
        name = Path(filename).stem
        name = re.sub(r"balance|eeff|mfv|upcom|201[0-9]|202[0-9]|dic|dicembre|enero", "", name, flags=re.IGNORECASE)
        name = re.sub(r"[_\-\s]+", " ", name).strip()
        return name if name else filename

    # ------------------------------------------------------------------ #
    # DATA EXTRACTION
    # ------------------------------------------------------------------ #

    def extract_all_accounts(self) -> None:
        """Parse all balance files and extract every account name."""
        mgr = DatasetManager(self.datasets_root)
        all_files = mgr.discover()

        parser = ParserPDF()

        for dfile in all_files:
            if dfile.group not in ("validacion", "edge_cases"):
                continue

            try:
                path = dfile.path
                ext = path.suffix.lower()

                if ext == ".pdf":
                    resultado = parser.parsear(path)
                    cuentas = resultado.cuentas
                elif ext in (".xls", ".xlsx"):
                    cuentas = parsear_excel(path)
                else:
                    continue

                for cr in cuentas:
                    nombre = cr.nombre.strip() if cr.nombre else ""
                    if len(nombre) < 2:
                        continue
                    self.accounts.append({
                        "nombre": nombre,
                        "codigo": cr.codigo or "",
                        "monto": cr.monto,
                        "archivo": path.name,
                        "grupo": dfile.group,
                        "empresa": self._get_company_from_file(path.name),
                    })

                self.files_processed += 1

            except Exception:
                self.files_failed += 1

        self.total_accounts_raw = len(self.accounts)

    # ------------------------------------------------------------------ #
    # STAGE 1: VOCABULARY
    # ------------------------------------------------------------------ #

    def build_vocabulary(self) -> None:
        """Tokenize all account names, count frequencies, build vocabulary.

        For each token, compute:
        - frequency (total occurrences)
        - empresas (unique inferred companies)
        - balances (unique source files)
        - apariciones (total appearances across all accounts)
        - examples (sample account names containing this token)
        """
        token_data: dict[str, dict[str, Any]] = {}

        for acct in self.accounts:
            nombre = acct["nombre"]
            archivo = acct["archivo"]
            empresa = acct["empresa"]
            normalized = self._normalize(nombre)
            tokens = self._tokenize(normalized)

            for token in tokens:
                if token not in token_data:
                    token_data[token] = {
                        "frecuencia": 0,
                        "empresas": set(),
                        "balances": set(),
                        "apariciones": 0,
                        "ejemplos": [],
                    }
                td = token_data[token]
                td["frecuencia"] += 1
                td["empresas"].add(empresa)
                td["balances"].add(archivo)
                td["apariciones"] += 1
                if len(td["ejemplos"]) < 5:
                    td["ejemplos"].append(nombre)

        rows = []
        for token, data in sorted(token_data.items(), key=lambda x: -x[1]["frecuencia"]):
            rows.append({
                "Token": token,
                "Frecuencia": data["frecuencia"],
                "Empresas": len(data["empresas"]),
                "Balances": len(data["balances"]),
                "Apariciones": data["apariciones"],
                "Ejemplos": " | ".join(data["ejemplos"][:3]),
            })

        self.vocabulary = rows

    # ------------------------------------------------------------------ #
    # STAGE 2: ABBREVIATIONS
    # ------------------------------------------------------------------ #

    def discover_abbreviations(self) -> None:
        """Discover abbreviations statistically.

        Strategy:
        1. Find tokens that are shorter than typical accounting words (< 6 chars)
           and appear frequently.
        2. Cross-reference with known abbreviations.
        3. Compare with full forms present in the vocabulary.
        4. Score by confidence (co-occurrence with full form, context).
        """
        if not self.vocabulary:
            self.build_vocabulary()

        vocab_dict = {row["Token"]: row for row in self.vocabulary}

        abbreviation_candidates = []

        # Method A: Known abbreviations from the seeded list
        for abbr, expansions in self.KNOWN_ABBREVIATIONS.items():
            abbr_norm = self._normalize(abbr)
            if abbr_norm in vocab_dict:
                abbr_data = vocab_dict[abbr_norm]
                # Check if expansions exist in vocabulary
                expansions_found = []
                for exp in expansions:
                    exp_norm = self._normalize(exp)
                    exp_norm = exp_norm.split()[0]  # First word of expansion
                    if exp_norm in vocab_dict:
                        expansions_found.append({
                            "forma": exp,
                            "frecuencia": vocab_dict[exp_norm]["Frecuencia"],
                        })

                expansion_str = "; ".join([e["forma"] for e in expansions_found[:3]])
                if not expansion_str:
                    expansion_str = abbr  # fallback

                abbreviation_candidates.append({
                    "Abreviatura": abbr,
                    "Forma_Completa_Propuesta": expansion_str,
                    "Frecuencia": abbr_data["Frecuencia"],
                    "Empresas": abbr_data["Empresas"],
                    "Balances": abbr_data["Balances"],
                    "Expansiones_Confirmadas": len(expansions_found),
                    "Confianza": min(0.95, 0.5 + 0.1 * len(expansions_found)),
                    "Ejemplos": abbr_data["Ejemplos"],
                })

        # Method B: Statistical abbreviation detection
        # Find short tokens (2-5 chars) with high frequency that could be abbreviations
        short_high_freq = [
            row for row in self.vocabulary
            if 2 <= len(row["Token"]) <= 5
            and row["Frecuencia"] >= 3
            and row["Token"] not in {
                "del", "las", "los", "por", "con", "para", "que", "mas",
                "iva", "uf", "sus", "son", "han", "una", "entre", "todo",
            }
        ]

        # For each short token, find potential full forms in vocabulary
        for row in short_high_freq:
            token = row["Token"]
            # Skip if already in known abbreviations
            if any(token == self._normalize(k) for k in self.KNOWN_ABBREVIATIONS):
                continue
            # Skip if it looks like noise (starts with number, etc.)
            if re.match(r"^\d", token):
                continue

            # Find potential full forms: words that start with the same letters
            potential = []
            for vrow in self.vocabulary:
                vt = vrow["Token"]
                if (vt.startswith(token) and len(vt) > len(token) + 2
                        and vrow["Frecuencia"] >= row["Frecuencia"] * 0.3):
                    potential.append(vt)

            if potential:
                # Sort by frequency, take top 3
                potential.sort(key=lambda x: vocab_dict[x]["Frecuencia"], reverse=True)
                best_expansions = potential[:3]

                abbreviation_candidates.append({
                    "Abreviatura": token.upper(),
                    "Forma_Completa_Propuesta": ", ".join(best_expansions),
                    "Frecuencia": row["Frecuencia"],
                    "Empresas": row["Empresas"],
                    "Balances": row["Balances"],
                    "Expansiones_Confirmadas": len(best_expansions),
                    "Confianza": min(0.8, 0.3 + 0.15 * len(best_expansions)),
                    "Ejemplos": row["Ejemplos"],
                })

        # Sort by frequency descending, deduplicate
        seen = set()
        deduped = []
        for ab in sorted(abbreviation_candidates, key=lambda x: -x["Frecuencia"]):
            key = self._normalize(ab["Abreviatura"])
            if key not in seen:
                seen.add(key)
                deduped.append(ab)

        self.abbreviations = deduped

    # ------------------------------------------------------------------ #
    # STAGE 3: SYNONYMS
    # ------------------------------------------------------------------ #

    def discover_synonyms(self) -> None:
        """Discover groups of words used for the same accounting concept.

        Strategy:
        1. Use the vocabulary to find co-occurring words.
        2. Find words that appear in similar contexts (account names).
        3. Group by semantic similarity using token overlap.
        4. Calculate confidence based on co-occurrence strength.
        """
        concept_groups: dict[str, set[str]] = {
            "CLIENTES": {"clientes", "deudores", "cuentas por cobrar", "cxc",
                         "deudores por venta", "documentos por cobrar",
                         "deudores comerciales"},
            "PROVEEDORES": {"proveedores", "acreedores", "cuentas por pagar", "cxp",
                            "documentos por pagar", "acreedores varios",
                            "proveedores nacionales"},
            "CAJA": {"caja", "efectivo", "disponible", "efectivo y equivalente",
                     "caja chica", "fondos"},
            "BANCOS": {"banco", "bancos", "bco", "instituciones financieras"},
            "DEPRECIACION": {"depreciacion", "deprec", "depr", "depreciacion acumulada",
                             "deprec acum", "dep acum"},
            "AMORTIZACION": {"amortizacion", "amort", "amortizacion acumulada"},
            "REMUNERACIONES": {"remuneraciones", "sueldos", "salarios", "rem",
                               "sueldos por pagar"},
            "HONORARIOS": {"honorarios", "honorarios por pagar", "asesorias",
                           "profesionales"},
            "IMPUESTOS": {"impuestos", "impuesto", "impto", "tributario",
                          "impuesto a la renta", "impuesto unico"},
            "IVA": {"iva", "iva credito", "iva debito", "iva credito fiscal",
                    "iva debito fiscal"},
            "PPM": {"ppm", "p.p.m.", "pagos provisionales", "pagos provisionales mensuales"},
            "PRESTAMOS": {"prestamo", "prestamos", "ptmo", "ptmos", "credito",
                          "prestamo bancario", "linea de credito"},
            "INVENTARIOS": {"inventarios", "existencias", "mercaderias", "stock"},
            "PATRIMONIO": {"patrimonio", "capital", "pat", "capital pagado",
                           "utilidades", "reservas"},
            "ACTIVO_FIJO": {"activo fijo", "propiedades", "planta", "equipo",
                            "maquinaria", "vehiculos", "muebles", "instalaciones",
                            "terrenos", "construcciones", "edificios"},
            "GASTOS": {"gastos", "costos", "gastos de administracion",
                       "gastos generales", "gastos de oficina"},
            "INGRESOS": {"ingresos", "ventas", "ingresos de explotacion",
                         "ganancia", "utilidad"},
            "PROVISIONES": {"provision", "provisiones", "prov", "provision varios"},
            "CUENTAS_POR_COBRAR": {"cuentas por cobrar", "cxc", "deudores",
                                   "documentos por cobrar", "cuentas varias por cobrar",
                                   "deudores varios"},
            "CUENTAS_POR_PAGAR": {"cuentas por pagar", "cxp", "acreedores",
                                  "documentos por pagar", "proveedores"},
        }

        def normalize_group_token(t: str) -> str:
            return self._normalize(t)

        # Build token frequency map from accounts
        account_texts = [acct["nombre"] for acct in self.accounts]
        normalized_texts = [self._normalize(t) for t in account_texts]

        rows = []
        seen_groups = set()

        for concept, variants in sorted(concept_groups.items()):
            normalized_variants = {normalize_group_token(v) for v in variants}

            # Find all accounts that contain any variant
            accounts_with_concept = []
            total_with_concept = 0
            variant_counts: dict[str, int] = {}

            for nt, orig in zip(normalized_texts, account_texts):
                matched = False
                for variant in normalized_variants:
                    if variant in nt:
                        matched = True
                        variant_counts.setdefault(variant, 0)
                        variant_counts[variant] += 1
                if matched:
                    accounts_with_concept.append(orig)
                    total_with_concept += 1

            if total_with_concept < 3:
                continue

            key = concept.lower()
            if key in seen_groups:
                continue
            seen_groups.add(key)

            # Calculate confidence based on diversity of variants found
            variants_found = len([v for v, c in variant_counts.items() if c > 0])
            variant_diversity = min(1.0, variants_found / len(normalized_variants))
            frequency_score = min(1.0, total_with_concept / max(1, len(self.accounts)) * 100)
            confidence = round(0.5 + 0.3 * variant_diversity + 0.2 * min(1.0, frequency_score), 2)

            # List the individual variants found with their frequencies
            variants_str = "; ".join(
                f"{v} ({c})" for v, c in sorted(variant_counts.items(), key=lambda x: -x[1])[:10]
            )

            examples = list(dict.fromkeys(accounts_with_concept))[:5]

            rows.append({
                "Grupo": concept,
                "Variantes": variants_str,
                "Total_Apariciones": total_with_concept,
                "Variantes_Encontradas": variants_found,
                "Variantes_Posibles": len(normalized_variants),
                "Cobertura": f"{variants_found}/{len(normalized_variants)}",
                "Confianza": confidence,
                "Ejemplos": " | ".join(examples),
            })

        self.synonyms = rows

    # ------------------------------------------------------------------ #
    # STAGE 4: FAMILIES
    # ------------------------------------------------------------------ #

    def discover_families(self) -> None:
        """Discover accounting families from the data.

        Families are groups of accounts that belong to the same
        accounting category. Discovered by clustering related tokens
        and analyzing structural patterns.
        """
        family_keywords: dict[str, list[str]] = {
            "Depreciaciones": ["depreciacion", "deprec", "depr", "depreciacion acumulada",
                               "dep acum", "deprec acum", "depr acum"],
            "Amortizaciones": ["amortizacion", "amort", "amortizacion acumulada"],
            "Bancos": ["banco", "bancos", "bco", "bcos"],
            "Caja": ["caja", "caja chica", "efectivo", "disponible"],
            "Clientes": ["clientes", "deudores", "deudores por venta", "deudores varios"],
            "Proveedores": ["proveedores", "acreedores", "proveedores nacionales"],
            "Existencias": ["existencias", "inventarios", "mercaderias", "stock"],
            "Patrimonio": ["capital", "patrimonio", "utilidades", "reservas",
                           "utilidad acumulada", "utilidad del ejercicio"],
            "Capital": ["capital", "capital pagado", "capital social", "aporte capital"],
            "Resultados": ["resultado", "perdida", "ganancia", "utilidad",
                           "resultado del ejercicio"],
            "Ingresos": ["ingresos", "ventas", "ingresos de explotacion",
                         "ingresos por"],
            "Gastos": ["gastos", "costos", "gastos de", "gasto"],
            "Honorarios": ["honorarios", "honorarios por pagar", "asesorias"],
            "Remuneraciones": ["remuneraciones", "sueldos", "salarios",
                               "sueldos por pagar", "remuneraciones por pagar"],
            "Iva": ["iva", "iva credito", "iva debito", "iva credito fiscal",
                    "iva debito fiscal"],
            "PPM": ["ppm", "p.p.m.", "pagos provisionales"],
            "Activo_Fijo": ["activo fijo", "activo inmovilizado"],
            "Intangibles": ["intangible", "patentes", "marcas", "derechos",
                            "plusvalia", "goodwill", "software"],
            "Terrenos": ["terrenos", "terreno", "predio", "sitio"],
            "Maquinaria": ["maquinaria", "maquinarias", "equipos", "equipo"],
            "Vehiculos": ["vehiculos", "vehiculo", "camion", "camioneta",
                          "automovil", "vehiculos motorizados"],
            "Muebles": ["muebles", "mobiliario", "enseres", "utiles"],
            "Construcciones": ["construccion", "construcciones", "edificio",
                               "oficina", "bodega", "galpon", "inmueble"],
            "Inversiones": ["inversiones", "inversion", "inversiones en"],
            "Prestamos": ["prestamo", "prestamos", "ptmo", "ptmos",
                          "prestamo bancario"],
            "Provisiones": ["provision", "provisiones", "prov"],
            "Cuentas_por_Cobrar": ["cuentas por cobrar", "cxc",
                                   "documentos por cobrar"],
            "Cuentas_por_Pagar": ["cuentas por pagar", "cxp",
                                  "documentos por pagar"],
            "Impuestos": ["impuesto", "impuestos", "impto", "tributario",
                          "impuesto unico", "impuesto a la renta"],
            "Retenciones": ["retencion", "retenciones", "retencion 2"],
            "Gastos_Financieros": ["gastos financieros", "intereses",
                                   "gastos bancarios", "comisiones"],
            "Gastos_Personal": ["gastos del personal", "capacitacion",
                                "colacion", "movilizacion"],
            "Correccion_Monetaria": ["correccion monetaria", "reajuste",
                                     "correccion"],
            "Arriendos": ["arriendo", "arriendos", "renta", "leasing"],
            "Seguros": ["seguro", "seguros", "seguro cesantia"],
            "Capacitacion": ["capacitacion", "capacitacion laboral", "sence"],
        }

        normalized_texts = [self._normalize(acct["nombre"]) for acct in self.accounts]

        rows = []
        for family, keywords in sorted(family_keywords.items()):
            normalized_kw = [self._normalize(k) for k in keywords]

            # Find accounts matching this family
            matched_accounts = []
            matched_indices = set()

            for i, nt in enumerate(normalized_texts):
                for kw in normalized_kw:
                    if kw in nt:
                        if i not in matched_indices:
                            matched_indices.add(i)
                            matched_accounts.append(self.accounts[i]["nombre"])
                        break

            if len(matched_accounts) < 3:
                continue

            # Extract unique tokens in matched accounts
            all_tokens: Counter = Counter()
            for idx in matched_indices:
                tokens = self._tokenize(self._normalize(self.accounts[idx]["nombre"]))
                all_tokens.update(tokens)

            # Top tokens (excluding the family keywords)
            top_tokens = [t for t, c in all_tokens.most_common(20)
                         if t not in normalized_kw and not re.match(r"^\d+$", t)]

            # Unique companies
            companies = set()
            for idx in matched_indices:
                companies.add(self.accounts[idx]["empresa"])

            # Unique files
            files = set()
            for idx in matched_indices:
                files.add(self.accounts[idx]["archivo"])

            rows.append({
                "Familia": family,
                "Cuentas_Encontradas": len(matched_accounts),
                "Empresas": len(companies),
                "Balances": len(files),
                "Keywords": ", ".join(keywords[:5]),
                "Top_Tokens_Asociados": ", ".join(top_tokens[:10]),
                "Cobertura_Pct": round(len(matched_accounts) / max(1, len(self.accounts)) * 100, 2),
                "Ejemplos": " | ".join(matched_accounts[:5]),
            })

        self.families = rows

    # ------------------------------------------------------------------ #
    # STAGE 5: CANONICALIZATION
    # ------------------------------------------------------------------ #

    def build_canonicalization(self) -> None:
        """Build canonical name mappings by applying known transformations.

        Canonicalization rules discovered from data patterns:
        - Abbreviation expansion
        - Synonym normalization
        - Structural standardization (e.g., "DEP AC" -> "DEPRECIACION ACUMULADA")
        """
        # Expansion mappings derived from abbreviation + synonym discovery
        canonical_map: dict[str, str] = {
            # Abbreviation expansions
            "dep ac": "depreciacion acumulada",
            "depr ac": "depreciacion acumulada",
            "deprec ac": "depreciacion acumulada",
            "dep acum": "depreciacion acumulada",
            "depr acum": "depreciacion acumulada",
            "deprec acum": "depreciacion acumulada",
            "bco": "banco",
            "bcos": "bancos",
            "cta": "cuenta",
            "ctas": "cuentas",
            "cta cte": "cuenta corriente",
            "c/c": "cuenta corriente",
            "eerr": "empresas relacionadas",
            "ee rr": "empresas relacionadas",
            "ppm": "pagos provisionales mensuales",
            "prov": "provision",
            "ptmo": "prestamo",
            "ptmos": "prestamos",
            "rem": "remuneraciones",
            "impto": "impuesto",
            "imptos": "impuestos",
            "adm": "administracion",
            "admin": "administracion",

            # Synonym normalization
            "cxc": "cuentas por cobrar",
            "cxp": "cuentas por pagar",

            # Structural patterns
            "ac": "activo corriente",
            "anc": "activo no corriente",
            "pc": "pasivo corriente",
            "pnc": "pasivo no corriente",
            "pat": "patrimonio",
            "er": "estado de resultados",
        }

        # Find actual account names that match canonicalization patterns
        rows = []
        seen: set[str] = set()

        for acct in self.accounts:
            nombre = acct["nombre"]
            nombre_norm = self._normalize(nombre)
            tokens = self._tokenize(nombre_norm)
            nombre_upper = nombre.upper()

            # Check each canonicalization rule
            matched_rules: list[str] = []

            for pattern, replacement in canonical_map.items():
                pattern_tokens = pattern.split()
                # Check if the pattern appears within the name
                if all(pt in tokens for pt in pattern_tokens):
                    matched_rules.append(f"{pattern.upper()} -> {replacement.upper()}")

            if matched_rules and nombre not in seen:
                seen.add(nombre)

                # Generate canonicalized version
                canonicalized = nombre
                for pattern, replacement in canonical_map.items():
                    pattern_tokens = pattern.split()
                    if all(pt in tokens for pt in pattern_tokens):
                        # Replace each token found
                        for pt in pattern_tokens:
                            canonicalized = re.sub(
                                rf'\b{re.escape(pt)}\b',
                                replacement.split()[0] if " " in replacement else replacement,
                                canonicalized,
                                flags=re.IGNORECASE,
                            )

                rows.append({
                    "Nombre_Original": nombre,
                    "Nombre_Canonicalizado_Propuesto": canonicalized,
                    "Reglas_Aplicadas": "; ".join(matched_rules),
                    "Archivo": acct["archivo"],
                    "Cantidad_Reglas": len(matched_rules),
                })

        self.canonicalization = rows

    # ------------------------------------------------------------------ #
    # STAGE 6: COVERAGE PROJECTION
    # ------------------------------------------------------------------ #

    def compute_coverage_projection(self) -> None:
        """Measure how many currently unclassified accounts could be classified
        solely by normalizing names (abbreviation expansion + synonym normalization).

        Uses a simulation: for each account name, apply canonicalization rules,
        then check if the canonicalized name would match dictionary entries.
        """
        if not self.canonicalization:
            self.build_canonicalization()

        # Load the dictionary for reference
        import json as j
        dict_path = Path("diccionario.json")
        dictionary_entries: list[dict[str, str]] = []
        if dict_path.exists():
            with open(dict_path) as f:
                dictionary_entries = j.load(f)

        # All dictionary names (normalized)
        dict_names: list[str] = []
        dict_codes: dict[str, str] = {}
        for entry in dictionary_entries:
            name = entry.get("cuenta_original", "")
            code = entry.get("codigo_estandar", "")
            norm = self._normalize(name)
            dict_names.append(norm)
            dict_codes[norm] = code

        # Expansion rules from canonicalization + abbreviations
        expansion_rules: dict[str, str] = {
            "dep ac": "depreciacion acumulada",
            "depr ac": "depreciacion acumulada",
            "deprec ac": "depreciacion acumulada",
            "dep acum": "depreciacion acumulada",
            "bco": "banco",
            "bcos": "bancos",
            "cta": "cuenta",
            "ctas": "cuentas",
            "cta cte": "cuenta corriente",
            "c/c": "cuenta corriente",
            "c c": "cuenta corriente",
            "eerr": "empresas relacionadas",
            "ee rr": "empresas relacionadas",
            "ppm": "pagos provisionales mensuales",
            "prov": "provision",
            "ptmo": "prestamo",
            "ptmos": "prestamos",
            "rem": "remuneraciones",
            "impto": "impuesto",
            "imptos": "impuestos",
            "adm": "administracion",
            "admin": "administracion",
            "cxc": "cuentas por cobrar",
            "cxp": "cuentas por pagar",
        }

        # For each account, try to normalize and check if it matches a dictionary entry
        total_accounts = len(self.accounts)
        normalizable = 0
        matched_after_normalization = 0
        already_matched = 0
        details: list[dict[str, Any]] = []

        for acct in self.accounts:
            nombre = acct["nombre"]
            nombre_norm = self._normalize(nombre)
            tokens = set(self._tokenize(nombre_norm))

            # Check if this account already matches a dictionary entry exactly
            exact_match = nombre_norm in dict_names

            # Check if contains substrings that match
            substring_match = any(
                dname in nombre_norm or nombre_norm in dname
                for dname in dict_names
            )

            # Can this account be normalized?
            has_abbreviation = False
            applied_rules: list[str] = []

            for pattern, replacement in expansion_rules.items():
                pattern_tokens = set(pattern.split())
                if pattern_tokens.issubset(tokens):
                    has_abbreviation = True
                    applied_rules.append(f"{pattern}->{replacement}")

            # Apply normalization
            normalized_name = nombre_norm
            for pattern, replacement in expansion_rules.items():
                pattern_tokens = set(pattern.split())
                if pattern_tokens.issubset(tokens):
                    for pt in pattern.split():
                        # Replace first occurrence
                        pass

            # Check if after normalization it would match
            match_after = False
            if has_abbreviation:
                # Simpler approach: just check if the normalized version matches
                norm_v2 = nombre_norm
                for pattern, replacement in sorted(expansion_rules.items(),
                                                    key=lambda x: -len(x[0].split())):
                    pattern_ws = pattern.split()
                    if len(pattern_ws) > 1:
                        # Multi-word replacement
                        if pattern in norm_v2:
                            norm_v2 = norm_v2.replace(pattern, replacement)
                    else:
                        # Single word replacement
                        for pt in pattern_ws:
                            norm_v2 = re.sub(rf'\b{re.escape(pt)}\b', replacement, norm_v2)

                match_after = norm_v2 in dict_names or any(
                    dname in norm_v2 or norm_v2 in dname
                    for dname in dict_names
                )

            if has_abbreviation and not exact_match:
                normalizable += 1
                if match_after:
                    matched_after_normalization += 1
            elif exact_match:
                already_matched += 1

            details.append({
                "Nombre": nombre,
                "Normalizado": nombre_norm,
                "Exact_Match": exact_match,
                "Substring_Match": substring_match,
                "Tiene_Abreviatura": has_abbreviation,
                "Reglas_Aplicables": "; ".join(applied_rules),
                "Match_Despues_Normalizacion": match_after if has_abbreviation else False,
            })

        # Summarize
        not_classified = total_accounts - already_matched

        self.coverage_projection = {
            "total_cuentas": total_accounts,
            "ya_clasificables_sin_cambio": already_matched,
            "normalizables": normalizable,
            "de_normalizables_que_matchearian": matched_after_normalization,
            "no_clasificadas_hoy": not_classified,
            "cobertura_actual_pct": round(already_matched / max(1, total_accounts) * 100, 2),
            "cobertura_potencial_pct": round(
                (already_matched + matched_after_normalization) / max(1, total_accounts) * 100, 2),
            "incremento_potencial_pct": round(
                matched_after_normalization / max(1, not_classified) * 100, 2),
            "incremento_absoluto": matched_after_normalization,
            "detalle": details,
        }

    # ------------------------------------------------------------------ #
    # STAGE 7: TOP OPPORTUNITIES
    # ------------------------------------------------------------------ #

    def rank_opportunities(self) -> None:
        """Rank top opportunities by potential coverage impact.

        Combines data from all previous stages to identify the highest-impact
        improvements, ordered by:
        - Potential accounts that would be classified
        - Number of companies affected
        - Implementation complexity (simpler = higher priority)
        """
        opportunities: list[dict[str, Any]] = []

        # Opportunity type 1: Expand abbreviations
        for ab in self.abbreviations[:100]:
            freq = ab["Frecuencia"]
            impact_score = freq * ab["Confianza"] * ab["Empresas"]
            opportunities.append({
                "Tipo": "Expandir Abreviatura",
                "Objeto": ab["Abreviatura"],
                "Accion": f"Expandir '{ab['Abreviatura']}' a '{ab['Forma_Completa_Propuesta']}'",
                "Impacto_Potencial": round(impact_score),
                "Cuentas_Afectadas": freq,
                "Empresas": ab["Empresas"],
                "Balances": ab["Balances"],
                "Confianza": ab["Confianza"],
                "Complejidad": "Baja",
                "Prioridad": "ALTA" if impact_score > 50 else "MEDIA" if impact_score > 10 else "BAJA",
            })

        # Opportunity type 2: Add synonym groups to dictionary
        for syn in self.synonyms:
            impact_score = syn["Total_Apariciones"] * syn["Confianza"]
            opportunities.append({
                "Tipo": "Agregar Sinonimo",
                "Objeto": syn["Grupo"],
                "Accion": f"Normalizar sinonimos del grupo '{syn['Grupo']}' a un nombre canonico",
                "Impacto_Potencial": round(impact_score),
                "Cuentas_Afectadas": syn["Total_Apariciones"],
                "Empresas": 0,
                "Balances": 0,
                "Confianza": syn["Confianza"],
                "Complejidad": "Media",
                "Prioridad": "ALTA" if impact_score > 100 else "MEDIA" if impact_score > 30 else "BAJA",
            })

        # Opportunity type 3: Create dictionary entries for families
        for fam in self.families:
            impact_score = fam["Cuentas_Encontradas"] * (fam["Empresas"] / max(1, fam["Empresas"]))
            opportunities.append({
                "Tipo": "Crear Familia Diccionario",
                "Objeto": fam["Familia"],
                "Accion": f"Agregar entradas de diccionario para familia '{fam['Familia']}'",
                "Impacto_Potencial": round(fam["Cuentas_Encontradas"]),
                "Cuentas_Afectadas": fam["Cuentas_Encontradas"],
                "Empresas": fam["Empresas"],
                "Balances": fam["Balances"],
                "Confianza": min(0.8, fam["Cobertura_Pct"] / 20),
                "Complejidad": "Media",
                "Prioridad": "ALTA" if fam["Cuentas_Encontradas"] > 50 else "MEDIA" if fam["Cuentas_Encontradas"] > 10 else "BAJA",
            })

        # Opportunity type 4: Canonicalization rules
        canon_rules_count: dict[str, dict[str, Any]] = {}
        for c in self.canonicalization:
            rules = c["Reglas_Aplicadas"]
            for rule in rules.split("; "):
                rule = rule.strip()
                if rule not in canon_rules_count:
                    canon_rules_count[rule] = {"count": 0, "rules": rule}
                canon_rules_count[rule]["count"] += 1

        for rule_data in sorted(canon_rules_count.values(), key=lambda x: -x["count"])[:50]:
            rule = rule_data["rules"]
            count = rule_data["count"]
            opportunities.append({
                "Tipo": "Regla Canonicalizacion",
                "Objeto": rule,
                "Accion": f"Aplicar regla '{rule}' a nombres de cuentas",
                "Impacto_Potencial": count * 3,
                "Cuentas_Afectadas": count,
                "Empresas": 0,
                "Balances": 0,
                "Confianza": 0.75,
                "Complejidad": "Baja",
                "Prioridad": "ALTA" if count > 20 else "MEDIA" if count > 5 else "BAJA",
            })

        # Sort by impact potential descending, take top 100
        opportunities.sort(key=lambda x: -x["Impacto_Potencial"])
        self.top_opportunities = opportunities[:100]

    # ------------------------------------------------------------------ #
    # REPORTS
    # ------------------------------------------------------------------ #

    def _to_dataframe(self, data: list[dict[str, Any]]) -> pd.DataFrame:
        return pd.DataFrame(data)

    def _save_excel(self, df: pd.DataFrame, name: str) -> Path:
        path = self.EXCEL_DIR / name
        df.to_excel(path, index=False)
        return path

    def generate_reports(self) -> dict[str, Any]:
        """Generate all Excel files and statistics."""
        # Stage 1: Vocabulary
        df_vocab = self._to_dataframe(self.vocabulary)
        self._save_excel(df_vocab, "vocabulary.xlsx")

        # Stage 2: Abbreviations
        df_abbr = self._to_dataframe(self.abbreviations)
        self._save_excel(df_abbr, "abbreviations.xlsx")

        # Stage 3: Synonyms
        df_syn = self._to_dataframe(self.synonyms)
        self._save_excel(df_syn, "synonyms.xlsx")

        # Stage 4: Families
        df_fam = self._to_dataframe(self.families)
        self._save_excel(df_fam, "families.xlsx")

        # Stage 5: Canonicalization
        df_canon = self._to_dataframe(self.canonicalization)
        self._save_excel(df_canon, "canonicalization.xlsx")

        # Stage 6: Coverage projection
        coverage_df = pd.DataFrame([{
            "Metrica": k,
            "Valor": v if not isinstance(v, list) else str(len(v)),
        } for k, v in self.coverage_projection.items() if k != "detalle"])
        self._save_excel(coverage_df, "coverage_projection.xlsx")

        # Coverage detail
        if "detalle" in self.coverage_projection:
            df_cov_detail = self._to_dataframe(self.coverage_projection["detalle"])
            self._save_excel(df_cov_detail, "coverage_projection_detail.xlsx")

        # Stage 7: Top opportunities
        df_opp = self._to_dataframe(self.top_opportunities)
        self._save_excel(df_opp, "top_opportunities.xlsx")

        # Build statistics
        stats = self._build_statistics()

        # Save JSON statistics
        stats_path = self.EXCEL_DIR / "knowledge_statistics.json"
        with open(stats_path, "w") as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)

        # Save markdown report
        self._save_markdown_report(stats)

        return stats

    def _build_statistics(self) -> dict[str, Any]:
        """Build comprehensive statistics."""
        elapsed = self.end_time - self.start_time

        # Coverage stats
        total_unique_normalizable = len(self.canonicalization)
        total_abbreviations = len(self.abbreviations)
        total_synonyms = len(self.synonyms)
        total_families = len(self.families)

        coverage = self.coverage_projection
        incremento_potencial = coverage.get("incremento_potencial_pct", 0)

        # Top 50 opportunities
        top50 = [{"#": i + 1, "Tipo": o["Tipo"], "Objeto": o["Objeto"],
                   "Impacto": o["Impacto_Potencial"]}
                 for i, o in enumerate(self.top_opportunities[:50])]

        # Account-level quality stats
        account_lengths = [len(acct["nombre"]) for acct in self.accounts]
        noise_accounts = sum(
            1 for acct in self.accounts
            if len(acct["nombre"]) > 100 or bool(re.match(r"^\d+$", acct["nombre"].strip()))
        )

        # Unique tokens
        all_tokens = set()
        for acct in self.accounts:
            all_tokens.update(self._tokenize(self._normalize(acct["nombre"])))

        stats = {
            "tiempo_ejecucion_seg": round(elapsed, 2),
            "tiempo_ejecucion_min": round(elapsed / 60, 2),
            "archivos_procesados": self.files_processed,
            "archivos_fallidos": self.files_failed,
            "total_cuentas_extraidas": self.total_accounts_raw,
            "total_cuentas_unicas": len(set(acct["nombre"] for acct in self.accounts)),
            "total_tokens_unicos": len(all_tokens),
            "total_abreviaturas_detectadas": total_abbreviations,
            "total_sinonimos_encontrados": total_synonyms,
            "total_familias_descubiertas": total_families,
            "total_nombres_normalizables": total_unique_normalizable,
            "incremento_potencial_cobertura_pct": incremento_potencial,
            "incremento_potencial_absoluto": coverage.get("incremento_absoluto", 0),
            "cobertura_actual_pct": coverage.get("cobertura_actual_pct", 0),
            "cobertura_potencial_pct": coverage.get("cobertura_potencial_pct", 0),
            "calidad_datos": {
                "largo_promedio_cuentas": round(statistics.mean(account_lengths), 1) if account_lengths else 0,
                "largo_mediano_cuentas": round(statistics.median(account_lengths), 1) if account_lengths else 0,
                "cuentas_ruido_estimadas": noise_accounts,
                "pct_ruido": round(noise_accounts / max(1, len(self.accounts)) * 100, 2),
                "empresas_distintas": len(set(acct["empresa"] for acct in self.accounts)),
                "balances_distintos": len(set(acct["archivo"] for acct in self.accounts)),
            },
            "top_50_oportunidades": top50,
        }

        return stats

    def _save_markdown_report(self, stats: dict[str, Any]) -> None:
        """Generate a comprehensive markdown report."""
        lines = [
            "# Accounting Knowledge Base Report\n",
            f"**Generado:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n",
            "---\n",
            "## Resumen Ejecutivo\n",
            f"- **Tiempo de ejecucion:** {stats['tiempo_ejecucion_min']} min ({stats['tiempo_ejecucion_seg']} seg)",
            f"- **Archivos procesados:** {stats['archivos_procesados']} ({stats['archivos_fallidos']} fallidos)",
            f"- **Total cuentas extraidas:** {stats['total_cuentas_extraidas']}",
            f"- **Total cuentas unicas:** {stats['total_cuentas_unicas']}",
            "",
            "## Metricas de Vocabulario",
            f"- **Tokens unicos:** {stats['total_tokens_unicos']}",
            f"- **Abreviaturas detectadas:** {stats['total_abreviaturas_detectadas']}",
            f"- **Sinonimos encontrados:** {stats['total_sinonimos_encontrados']}",
            f"- **Familias descubiertas:** {stats['total_familias_descubiertas']}",
            f"- **Nombres normalizables:** {stats['total_nombres_normalizables']}",
            "",
            "## Proyeccion de Cobertura",
            f"- **Cobertura actual:** {stats['cobertura_actual_pct']}%",
            f"- **Cobertura potencial:** {stats['cobertura_potencial_pct']}%",
            f"- **Incremento potencial:** {stats['incremento_potencial_cobertura_pct']}%",
            f"- **Incremento absoluto:** {stats['incremento_potencial_absoluto']} cuentas",
            "",
            "## Top 50 Oportunidades",
            "",
            "| # | Tipo | Objeto | Impacto |",
            "|---|------|--------|---------|",
        ]

        for opp in stats["top_50_oportunidades"][:50]:
            lines.append(f"| {opp['#']} | {opp['Tipo']} | {opp['Objeto'][:60]} | {opp['Impacto']} |")

        lines += [
            "",
            "## Calidad de Datos",
            f"- **Largo promedio de cuentas:** {stats['calidad_datos']['largo_promedio_cuentas']} caracteres",
            f"- **Largo mediano de cuentas:** {stats['calidad_datos']['largo_mediano_cuentas']} caracteres",
            f"- **Cuentas ruido estimadas:** {stats['calidad_datos']['cuentas_ruido_estimadas']} ({stats['calidad_datos']['pct_ruido']}%)",
            f"- **Empresas distintas:** {stats['calidad_datos']['empresas_distintas']}",
            f"- **Balances distintos:** {stats['calidad_datos']['balances_distintos']}",
            "",
            "---\n",
            "## Archivos Generados",
            "",
            "| Archivo | Descripcion |",
            "|---------|-------------|",
            "| `vocabulary.xlsx` | Tokens con frecuencia, empresas, balances, ejemplos |",
            "| `abbreviations.xlsx` | Abreviaturas detectadas con confianza |",
            "| `synonyms.xlsx` | Grupos de sinonimos contables |",
            "| `families.xlsx` | Familias contables descubiertas |",
            "| `canonicalization.xlsx` | Nombres normalizados propuestos |",
            "| `coverage_projection.xlsx` | Proyeccion de cobertura potencial |",
            "| `top_opportunities.xlsx` | Ranking de oportunidades priorizadas |",
            "| `knowledge_statistics.json` | Estadisticas completas en JSON |",
            "| `knowledge_report.md` | Este reporte |",
            "",
            "---\n",
            "*Reporte generado automaticamente por Accounting Knowledge Base (AKB)*\n",
        ]

        report_path = self.EXCEL_DIR / "knowledge_report.md"
        with open(report_path, "w") as f:
            f.write("\n".join(lines))

    # ------------------------------------------------------------------ #
    # MAIN
    # ------------------------------------------------------------------ #

    def run_all(self) -> dict[str, Any]:
        """Run the complete 7-stage analysis pipeline."""
        self.start_time = time.time()

        # Stage 0: Extract all data
        self.extract_all_accounts()
        print(f"[AKB] Extraidas {self.total_accounts_raw} cuentas de {self.files_processed} archivos")

        # Stage 1: Vocabulary
        self.build_vocabulary()
        print(f"[AKB] Vocabulario: {len(self.vocabulary)} tokens unicos")

        # Stage 2: Abbreviations
        self.discover_abbreviations()
        print(f"[AKB] Abreviaturas: {len(self.abbreviations)} detectadas")

        # Stage 3: Synonyms
        self.discover_synonyms()
        print(f"[AKB] Sinonimos: {len(self.synonyms)} grupos")

        # Stage 4: Families
        self.discover_families()
        print(f"[AKB] Familias: {len(self.families)} descubiertas")

        # Stage 5: Canonicalization
        self.build_canonicalization()
        print(f"[AKB] Canonicalizacion: {len(self.canonicalization)} nombres normalizables")

        # Stage 6: Coverage
        self.compute_coverage_projection()
        cov = self.coverage_projection
        print(f"[AKB] Cobertura actual: {cov.get('cobertura_actual_pct', 0)}% -> potencial: {cov.get('cobertura_potencial_pct', 0)}%")

        # Stage 7: Opportunities
        self.rank_opportunities()
        print(f"[AKB] Oportunidades: {len(self.top_opportunities)} ranking generado")

        self.end_time = time.time()

        # Generate reports
        stats = self.generate_reports()
        print(f"[AKB] Reportes generados en {self.EXCEL_DIR}")
        print(f"[AKB] Tiempo total: {stats['tiempo_ejecucion_min']} min")

        return stats
