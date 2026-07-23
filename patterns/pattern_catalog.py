from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import ClassVar


@dataclass
class AccountingPattern:
    pattern_id: str
    family: str
    description: str
    priority: int
    confidence: float
    regex: re.Pattern
    keywords_forbidden: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    negative_examples: list[str] = field(default_factory=list)
    semantic_type: str = ""
    standard_code: str = ""
    financial_statement: str = ""
    economic_nature: str = ""
    expected_side: str = ""
    contra_account: str = ""
    learnable: bool = True


class PatternCatalog:
    FAMILIES: ClassVar[list[AccountingPattern]] = []

    @classmethod
    def get_all(cls) -> list[AccountingPattern]:
        if not cls.FAMILIES:
            cls.FAMILIES = cls._build_catalog()
        return cls.FAMILIES

    @classmethod
    def get_by_family(cls, family: str) -> list[AccountingPattern]:
        return [p for p in cls.get_all() if p.family == family]

    @classmethod
    def get_by_id(cls, pattern_id: str) -> AccountingPattern | None:
        for p in cls.get_all():
            if p.pattern_id == pattern_id:
                return p
        return None

    @classmethod
    def families_summary(cls) -> list[dict]:
        seen: dict[str, dict] = {}
        for p in cls.get_all():
            if p.family not in seen:
                seen[p.family] = {
                    "family": p.family,
                    "patterns": 0,
                    "min_priority": p.priority,
                    "max_confidence": p.confidence,
                    "examples": [],
                }
            seen[p.family]["patterns"] += 1
            seen[p.family]["min_priority"] = min(
                seen[p.family]["min_priority"], p.priority
            )
            seen[p.family]["max_confidence"] = max(
                seen[p.family]["max_confidence"], p.confidence
            )
            if p.examples and not seen[p.family]["examples"]:
                seen[p.family]["examples"] = p.examples[:3]
        return list(seen.values())

    @classmethod
    def _build_catalog(cls) -> list[AccountingPattern]:
        return [
            # ---- 1. DEPRECIACION_ACUMULADA ----
            AccountingPattern(
                pattern_id="depreciacion_acumulada",
                family="DEPRECIACION_ACUMULADA",
                description="Depreciación Acumulada de Activo Fijo",
                priority=10,
                confidence=0.92,
                regex=re.compile(r"\bDEP\w*(?:\s+AC\w*)+\b"),
                keywords_forbidden=["EJERCICIO", "DEL", "GASTO"],
                examples=[
                    "DEP AC VEHICULOS",
                    "DEPRECIACION ACUMULADA MAQUINARIAS",
                    "DEPREC AC OFICINAS",
                    "DEP ACUM EDIFICIOS",
                    "DEPRECIACION ACUMULADA",
                    "DEP AC CAMIONES",
                ],
                negative_examples=[
                    "DEPRECIACION DEL EJERCICIO",
                    "GASTO POR DEPRECIACION",
                ],
                semantic_type="contra_asset",
                standard_code="AC.02",
                financial_statement="balance_sheet",
                economic_nature="credit",
                expected_side="credit",
                contra_account="PPE",
                learnable=True,
            ),
            # ---- 2. AMORTIZACION_ACUMULADA ----
            AccountingPattern(
                pattern_id="amortizacion_acumulada",
                family="AMORTIZACION_ACUMULADA",
                description="Amortización Acumulada de Activos Intangibles",
                priority=11,
                confidence=0.92,
                regex=re.compile(r"\bAMORT\w*(?:\s+AC\w*)+\b"),
                keywords_forbidden=["EJERCICIO", "DEL", "GASTO"],
                examples=[
                    "AMORT AC INTANGIBLES",
                    "AMORTIZACION ACUMULADA MARCAS",
                    "AMORT ACUM CONCESIONES",
                ],
                negative_examples=["AMORTIZACION DEL EJERCICIO"],
                semantic_type="contra_asset",
                standard_code="AC.03",
                financial_statement="balance_sheet",
                economic_nature="credit",
                expected_side="credit",
                contra_account="INTANGIBLES",
                learnable=True,
            ),
            # ---- 3. DEPRECIACION_DEL_EJERCICIO ----
            AccountingPattern(
                pattern_id="depreciacion_del_ejercicio",
                family="DEPRECIACION_DEL_EJERCICIO",
                description="Depreciación del Ejercicio (Gasto)",
                priority=20,
                confidence=0.90,
                regex=re.compile(r"\bDEP\w*(?:\s+(?:DEL\s+)?EJERCICIO)\b"),
                keywords_forbidden=["ACUMULADA", "ACUM", "AC"],
                examples=[
                    "DEPRECIACION DEL EJERCICIO",
                    "DEP EJERCICIO",
                    "DEPREC EJERCICIO MAQUINARIAS",
                ],
                negative_examples=[
                    "DEPRECIACION ACUMULADA",
                    "DEP AC VEHICULOS",
                ],
                semantic_type="expense",
                standard_code="RE.04",
                financial_statement="income_statement",
                economic_nature="debit",
                expected_side="debit",
                learnable=True,
            ),
            # ---- 4. AMORTIZACION_DEL_EJERCICIO ----
            AccountingPattern(
                pattern_id="amortizacion_del_ejercicio",
                family="AMORTIZACION_DEL_EJERCICIO",
                description="Amortización del Ejercicio (Gasto)",
                priority=21,
                confidence=0.90,
                regex=re.compile(r"\bAMORT\w*(?:\s+(?:DEL\s+)?EJERCICIO)\b"),
                keywords_forbidden=["ACUMULADA", "ACUM", "AC"],
                examples=[
                    "AMORTIZACION DEL EJERCICIO",
                    "AMORT EJERCICIO",
                ],
                negative_examples=[
                    "AMORTIZACION ACUMULADA",
                    "AMORT AC INTANGIBLES",
                ],
                semantic_type="expense",
                standard_code="RE.05",
                financial_statement="income_statement",
                economic_nature="debit",
                expected_side="debit",
                learnable=True,
            ),
            # ---- 5. EMPRESAS_RELACIONADAS ----
            AccountingPattern(
                pattern_id="empresas_relacionadas",
                family="EMPRESAS_RELACIONADAS",
                description="Cuentas con Empresas Relacionadas",
                priority=30,
                confidence=0.88,
                regex=re.compile(
                    r"\bE\s*E\s*R\s*R\b|"
                    r"\bEMP\w*(?:\s+\w+)*\s+REL\w*\b"
                ),
                examples=[
                    "EERR",
                    "E E R R",
                    "EMPRESAS RELACIONADAS",
                    "EMP RELACIONADAS",
                    "CUENTAS POR COBRAR EERR",
                ],
                semantic_type="asset",
                standard_code="AC.04",
                financial_statement="balance_sheet",
                economic_nature="debit",
                expected_side="debit",
                learnable=True,
            ),
            # ---- 6. IVA_CREDITO ----
            AccountingPattern(
                pattern_id="iva_credito",
                family="IVA_CREDITO",
                description="IVA Crédito Fiscal",
                priority=40,
                confidence=0.90,
                regex=re.compile(
                    r"\bIVA\b.*\b(?:CREDITO|CF)\b|"
                    r"\b(?:CREDITO|CF)\b.*\bIVA\b"
                ),
                examples=[
                    "IVA CREDITO FISCAL",
                    "CREDITO FISCAL IVA",
                    "IVA CF",
                ],
                negative_examples=["IVA DEBITO FISCAL", "IVA DF"],
                semantic_type="asset",
                standard_code="AC.05",
                financial_statement="balance_sheet",
                economic_nature="debit",
                expected_side="debit",
                learnable=True,
            ),
            # ---- 7. IVA_DEBITO ----
            AccountingPattern(
                pattern_id="iva_debito",
                family="IVA_DEBITO",
                description="IVA Débito Fiscal",
                priority=41,
                confidence=0.90,
                regex=re.compile(
                    r"\bIVA\b.*\b(?:DEBITO|DF)\b|"
                    r"\b(?:DEBITO|DF)\b.*\bIVA\b"
                ),
                examples=[
                    "IVA DEBITO FISCAL",
                    "DEBITO FISCAL IVA",
                    "IVA DF",
                ],
                negative_examples=["IVA CREDITO FISCAL", "IVA CF"],
                semantic_type="liability",
                standard_code="PC.06",
                financial_statement="balance_sheet",
                economic_nature="credit",
                expected_side="credit",
                learnable=True,
            ),
            # ---- 8. CUENTAS_POR_COBRAR ----
            AccountingPattern(
                pattern_id="cuentas_por_cobrar",
                family="CUENTAS_POR_COBRAR",
                description="Cuentas por Cobrar (Deudores, Clientes)",
                priority=50,
                confidence=0.85,
                regex=re.compile(
                    r"\b(?:CXC|CUENTAS\s+POR\s+COBRAR|"
                    r"CTAS?\s*(?:POR\s+)?COBRAR|"
                    r"DEUDORES?|CLIENTES)\b"
                ),
                examples=[
                    "CXC",
                    "CUENTAS POR COBRAR",
                    "CTAS COBRAR",
                    "CLIENTES",
                    "DEUDORES VARIOS",
                    "CXC Proveedores",
                ],
                semantic_type="asset",
                standard_code="AC.06",
                financial_statement="balance_sheet",
                economic_nature="debit",
                expected_side="debit",
                learnable=True,
            ),
            # ---- 9. CUENTAS_POR_PAGAR ----
            AccountingPattern(
                pattern_id="cuentas_por_pagar",
                family="CUENTAS_POR_PAGAR",
                description="Cuentas por Pagar (Proveedores, Obligaciones)",
                priority=51,
                confidence=0.85,
                regex=re.compile(
                    r"\b(?:CXP|CUENTAS\s+POR\s+PAGAR|"
                    r"CTAS?\s*(?:POR\s+)?PAGAR|"
                    r"PROVEEDORES|OBLIGACIONES?)\b"
                ),
                examples=[
                    "CXP",
                    "CUENTAS POR PAGAR",
                    "CTAS PAGAR",
                    "PROVEEDORES",
                    "OBLIGACIONES POR PAGAR",
                    "CXP Proveedores",
                ],
                semantic_type="liability",
                standard_code="PC.07",
                financial_statement="balance_sheet",
                economic_nature="credit",
                expected_side="credit",
                learnable=True,
            ),
            # ---- 10. CAJA ----
            AccountingPattern(
                pattern_id="caja",
                family="CAJA",
                description="Caja (Efectivo en moneda nacional y extranjera)",
                priority=60,
                confidence=0.80,
                regex=re.compile(r"\bCAJA\b"),
                examples=[
                    "CAJA GENERAL",
                    "CAJA MN",
                    "CAJA ME",
                    "CAJA CENTRAL",
                ],
                semantic_type="asset",
                standard_code="AC.07",
                financial_statement="balance_sheet",
                economic_nature="debit",
                expected_side="debit",
                learnable=True,
            ),
            # ---- 11. BANCOS ----
            AccountingPattern(
                pattern_id="bancos",
                family="BANCOS",
                description="Bancos (Cuentas Corrientes y vistas)",
                priority=61,
                confidence=0.80,
                regex=re.compile(r"\b(?:BANCO\w*|BCO)\b"),
                examples=[
                    "BANCO SANTANDER",
                    "BCO CHILE",
                    "BANCO ESTADO CTA CTE",
                ],
                semantic_type="asset",
                standard_code="AC.08",
                financial_statement="balance_sheet",
                economic_nature="debit",
                expected_side="debit",
                learnable=True,
            ),
            # ---- 12. PROVISIONES ----
            AccountingPattern(
                pattern_id="provisiones",
                family="PROVISIONES",
                description="Provisiones (excepto vacaciones)",
                priority=70,
                confidence=0.75,
                regex=re.compile(r"\bPROVISION\w*\b"),
                keywords_forbidden=["VACACIONES", "VAC"],
                examples=[
                    "PROVISION INCOBRABLES",
                    "PROVISIONES VARIAS",
                    "PROVISION ADICIONAL",
                ],
                negative_examples=["PROVISION VACACIONES"],
                semantic_type="liability",
                standard_code="PC.09",
                financial_statement="balance_sheet",
                economic_nature="credit",
                expected_side="credit",
                learnable=True,
            ),
            # ---- 13. HONORARIOS ----
            AccountingPattern(
                pattern_id="honorarios",
                family="HONORARIOS",
                description="Honorarios (Gastos)",
                priority=80,
                confidence=0.80,
                regex=re.compile(r"\b(?:HONORAR\w*|HON)\b"),
                examples=[
                    "HONORARIOS",
                    "HONORARIOS PROFESIONALES",
                    "HON A PAGAR",
                ],
                semantic_type="expense",
                standard_code="RE.13",
                financial_statement="income_statement",
                economic_nature="debit",
                expected_side="debit",
                learnable=True,
            ),
            # ---- 14. REMUNERACIONES ----
            AccountingPattern(
                pattern_id="remuneraciones",
                family="REMUNERACIONES",
                description="Remuneraciones, Sueldos y Salarios",
                priority=81,
                confidence=0.85,
                regex=re.compile(
                    r"\b(?:REMUNERACION\w*|SUELDOS?|SALARIOS?)\b"
                ),
                examples=[
                    "REMUNERACIONES",
                    "SUELDOS POR PAGAR",
                    "SALARIOS",
                    "REMUNERACION A PAGAR",
                ],
                semantic_type="expense",
                standard_code="RE.14",
                financial_statement="income_statement",
                economic_nature="debit",
                expected_side="debit",
                learnable=True,
            ),
            # ---- 15. CAPITAL ----
            AccountingPattern(
                pattern_id="capital",
                family="CAPITAL",
                description="Capital y Aportes",
                priority=90,
                confidence=0.85,
                regex=re.compile(r"\bCAPITAL\b"),
                examples=[
                    "CAPITAL",
                    "CAPITAL SOCIAL",
                    "CAPITAL PAGADO",
                    "APORTE DE CAPITAL",
                ],
                semantic_type="equity",
                standard_code="PN.15",
                financial_statement="balance_sheet",
                economic_nature="credit",
                expected_side="credit",
                learnable=True,
            ),
        ]
