from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SemanticTypeInfo:
    semantic_type: str
    category_group: str
    description: str
    ifrs_reference: str = ""
    chilean_gaap_reference: str = ""


class SemanticCatalog:
    _types: dict[str, SemanticTypeInfo] = {
        "contra_asset": SemanticTypeInfo(
            semantic_type="contra_asset",
            category_group="activo",
            description="Cuenta de valuación que reduce el saldo de un activo",
            ifrs_reference="NIC 16, NIC 38",
            chilean_gaap_reference="Boletín Técnico N° 31",
        ),
        "expense": SemanticTypeInfo(
            semantic_type="expense",
            category_group="resultado",
            description="Cuenta de gasto operacional o no operacional",
            ifrs_reference="NIC 1",
            chilean_gaap_reference="Boletín Técnico N° 1",
        ),
        "asset": SemanticTypeInfo(
            semantic_type="asset",
            category_group="activo",
            description="Cuenta de activo",
            ifrs_reference="NIC 1, NIC 16",
            chilean_gaap_reference="Boletín Técnico N° 1",
        ),
        "liability": SemanticTypeInfo(
            semantic_type="liability",
            category_group="pasivo",
            description="Cuenta de pasivo",
            ifrs_reference="NIC 1, NIC 37",
            chilean_gaap_reference="Boletín Técnico N° 1",
        ),
        "revenue": SemanticTypeInfo(
            semantic_type="revenue",
            category_group="resultado",
            description="Cuenta de ingreso o ganancia",
            ifrs_reference="NIC 1, NIIF 15",
            chilean_gaap_reference="Boletín Técnico N° 1",
        ),
        "equity": SemanticTypeInfo(
            semantic_type="equity",
            category_group="patrimonio",
            description="Cuenta de patrimonio neto",
            ifrs_reference="NIC 1, NIC 32",
            chilean_gaap_reference="Boletín Técnico N° 1",
        ),
        "unknown": SemanticTypeInfo(
            semantic_type="unknown",
            category_group="desconocido",
            description="Tipo semántico no identificado",
        ),
    }

    @classmethod
    def get(cls, semantic_type: str) -> SemanticTypeInfo | None:
        return cls._types.get(semantic_type)

    @classmethod
    def all_types(cls) -> dict[str, SemanticTypeInfo]:
        return dict(cls._types)
