from __future__ import annotations
from collections import Counter
from .structure_models import StructureTemplate, StructuralFamily


FAMILY_RULES = [
    ("CPT_TASACION", lambda t: t.family == "CPT_TASACION" or
     ("cpt_" in t.name.lower())),
    ("EEFF_AUDITADOS", lambda t: t.section_count >= 4 and t.subtotal_count >= 10),
    ("BALANCE_ESTANDAR", lambda t: t.section_count >= 3 and t.subtotal_count >= 4),
    ("TRIBUTARIO", lambda t: t.code_format in ("SIN_CODIGO", "COMPACTO") and t.subtotal_count <= 3),
    ("BALANCE_SIMPLE", lambda t: t.total_nodes <= 15 and t.section_count <= 2),
    ("CLASIFICADO", lambda t: t.subtotal_count >= 5 and t.max_depth >= 2),
    ("DESCONOCIDO", lambda t: True),
]


def _classify_family(template: StructureTemplate) -> str:
    if template.family:
        return template.family
    for name, rule in FAMILY_RULES:
        if rule(template):
            return name
    return "DESCONOCIDO"


class FamilyDetector:

    @staticmethod
    def classify(template: StructureTemplate) -> str:
        family = _classify_family(template)
        template.family = family
        return family

    @staticmethod
    def build_families(templates: list[StructureTemplate]) -> list[StructuralFamily]:
        groups: dict[str, list[StructureTemplate]] = {}
        for t in templates:
            fam = t.family or FamilyDetector.classify(t)
            groups.setdefault(fam, []).append(t)

        families = []
        for fam_name, members in sorted(groups.items()):
            avg_depth = sum(m.max_depth for m in members) / max(len(members), 1)
            type_seqs = [m.type_sequence for m in members]
            seq_count = Counter(type_seqs)
            common_pattern = seq_count.most_common(1)[0][0][:50] if seq_count else ""

            total = sum(m.frequency for m in members)
            families.append(StructuralFamily(
                name=fam_name,
                templates=[m.template_id for m in members],
                total_members=total,
                avg_depth=round(avg_depth, 1),
                common_pattern=common_pattern,
                description=f"{fam_name}: {len(members)} templates, {total} files",
            ))
        return families
