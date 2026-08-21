from __future__ import annotations
from .structure_models import StructuralNode, StructuralTree, SectionInfo
from .structure_detector import StructureDetector


class TreeBuilder:

    def __init__(self):
        self.detector = StructureDetector()

    def build_tree(
        self,
        accounts_raw: list[dict],
        source_file: str = "",
    ) -> StructuralTree:
        tree = StructuralTree(source_file=source_file)

        if not accounts_raw:
            return tree

        tree.code_format = self.detector.detect_code_format(accounts_raw)
        tree.column_layout = self.detector.detect_column_layout(accounts_raw)

        nodes: list[StructuralNode] = []
        current_section = ""
        level_depths: dict[int, int] = {}
        header_count = 0
        detail_count = 0
        subtotal_count = 0

        for i, raw in enumerate(accounts_raw):
            nombre = str(raw.get("nombre", raw.get("account_name", "")))
            monto = raw.get("monto", raw.get("amount", raw.get("classification_amount", 0))) or 0
            if isinstance(monto, str):
                try:
                    monto = float(monto.replace(".", "").replace(",", "."))
                except (ValueError, TypeError):
                    monto = 0.0
            monto = float(monto)
            es_total = bool(raw.get("es_total", False))
            codigo = str(raw.get("codigo", raw.get("account_code", "")) or "")
            col = str(raw.get("origen_columna", raw.get("source_column", raw.get("nature", ""))) or "")
            linea = int(raw.get("linea", raw.get("source_line", i)))

            stype = self.detector.detect_type(nombre, es_total, monto)
            level = self.detector.detect_level(codigo, nombre)
            section = self.detector.detect_section(nombre, col)
            if section:
                current_section = section

            node = StructuralNode(
                original_name=nombre,
                structural_type=stype,
                depth=level,
                level=level,
                position=i,
                line_number=linea,
                section=current_section,
                has_amount=(monto != 0),
                amount=monto,
                original_code=codigo,
                code_format=tree.code_format,
            )
            nodes.append(node)

            level_depths[level] = level_depths.get(level, 0) + 1
            if stype == "H":
                header_count += 1
            elif stype == "D":
                detail_count += 1
            elif stype == "S":
                subtotal_count += 1

        _build_parent_links(nodes)

        tree.nodes = nodes
        tree.total_nodes = len(nodes)
        tree.max_depth = max([n.depth for n in nodes], default=0)
        tree.header_count = header_count
        tree.detail_count = detail_count
        tree.subtotal_count = subtotal_count
        tree.level_distribution = dict(sorted(level_depths.items()))
        tree.type_sequence = self.detector.compute_type_sequence(nodes)
        tree.sections = _extract_sections(nodes)
        tree.section_count = len(tree.sections)

        return tree


def _build_parent_links(nodes: list[StructuralNode]):
    stack: list[StructuralNode] = []
    for node in nodes:
        while stack and stack[-1].level >= node.level:
            stack.pop()
        if stack:
            parent = stack[-1]
            parent.children.append(node)
            node.parent = parent
        stack.append(node)


def _extract_sections(nodes: list[StructuralNode]) -> list[SectionInfo]:
    sections: list[SectionInfo] = []
    current_section = ""
    start = 0
    for i, node in enumerate(nodes):
        if node.section and node.section != current_section:
            if current_section:
                sections.append(SectionInfo(
                    name=current_section,
                    type=current_section,
                    start_line=start,
                    end_line=i - 1,
                    node_count=i - start,
                ))
            current_section = node.section
            start = i
    if current_section:
        sections.append(SectionInfo(
            name=current_section,
            type=current_section,
            start_line=start,
            end_line=len(nodes) - 1,
            node_count=len(nodes) - start,
        ))
    return sections
