"""
Generate architecture_semantic_engine.drawio and .json diagram files.
Run once to produce the diagram; the generated files are committed, not this script.
"""

import json
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

# ── Component definitions ──────────────────────────────────────────────

COMPONENTS = [
    # (id, label, phase, y_position)
    ("pdf", "PDF\n(182 formats)", "input", 20),
    ("parser", "ParserPDF", "phase1", 110),
    ("layout", "LayoutDetector", "phase1", 200),
    ("resolver", "AccountType\nResolver", "phase1", 290),
    ("filter", "AccountType\nFilter", "phase1", 380),
    ("normalizer", "Semantic\nNormalizer", "phase3", 470),
    ("matcher", "Semantic\nMatcher", "phase3", 560),
    ("classifier", "CMCC\nClassifier", "phase3", 650),
    ("regex", "Regex\nFallback", "phase2", 740),
    ("review", "Human\nReview", "phase4", 830),
]

PHASE_COLORS = {
    "input": "#E8E8E8",
    "phase1": "#D4E6F1",
    "phase2": "#F9E79F",
    "phase3": "#D5F5E3",
    "phase4": "#FADBD8",
}

SIDE_COMPONENTS = [
    ("catalog", "Concept\nCatalog\nv1.0 — 78 concepts", 380, 130, "#D5F5E3"),
    ("flags", "Feature Flags\nCMCCFeatureFlags\nruntime control", 380, 260, "#F9E79F"),
]

def make_drawio():
    """Generate .drawio (XML) content."""
    x_center = 120
    box_w = 160
    box_h = 60
    arrow_len = 20

    cells = []
    cell_id = [2]  # mutable counter, start after 0 (root) and 1 (layer)

    def add_cell(tag, attrs=None, value="", style="", parent=None, source=None, target=None):
        cid = str(cell_id[0])
        cell_id[0] += 1
        el = ET.Element("mxCell", attrib={"id": cid})
        if parent:
            el.set("parent", parent)
        if source:
            el.set("source", source)
        if target:
            el.set("target", target)
        if style:
            el.set("style", style)
        if value:
            el.set("value", value)
        if tag:
            el.tag = tag
        cells.append(el)
        return cid

    # Root cells
    add_cell("mxCell", {"id": "0"})
    add_cell("mxCell", {"id": "1", "parent": "0"})

    prev_id = None
    comp_ids = {}

    # Main flow boxes + arrows
    for cid, label, phase, y in COMPONENTS:
        color = PHASE_COLORS.get(phase, "#FFFFFF")
        style = (
            f"rounded=1;whiteSpace=wrap;html=1;fillColor={color};"
            f"strokeColor=#333333;fontSize=11;align=center;verticalAlign=middle"
        )
        node_id = add_cell(
            "mxCell",
            {"vertex": "1", "parent": "1"},
            value=escape(label),
            style=style,
        )
        # geometry
        geo = ET.SubElement(cells[-1], "mxGeometry")
        geo.set("x", str(x_center))
        geo.set("y", str(y))
        geo.set("width", str(box_w))
        geo.set("height", str(box_h))
        geo.set("as", "geometry")

        comp_ids[cid] = node_id

        if prev_id:
            arr_id = add_cell(
                "mxCell",
                {"edge": "1", "parent": "1", "source": prev_id, "target": node_id},
                style=(
                    "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;"
                    "jettySize=auto;html=1;strokeWidth=2;"
                ),
            )
            arr_geo = ET.SubElement(cells[-1], "mxGeometry")
            arr_geo.set("relative", "1")
            arr_geo.set("as", "geometry")

        prev_id = node_id

    # Side boxes: Concept Catalog → SemanticMatcher
    cat_id = None
    for cid, label, x_offset, y_offset, color in SIDE_COMPONENTS:
        style = (
            f"rounded=1;whiteSpace=wrap;html=1;fillColor={color};"
            f"strokeColor=#333333;fontSize=10;align=center;verticalAlign=middle;dashed=1"
        )
        node_id = add_cell(
            "mxCell",
            {"vertex": "1", "parent": "1"},
            value=escape(label),
            style=style,
        )
        geo = ET.SubElement(cells[-1], "mxGeometry")
        geo.set("x", str(x_center + box_w + 20))
        geo.set("y", str(y_offset))
        geo.set("width", str(box_w))
        geo.set("height", str(box_h))
        geo.set("as", "geometry")

        if cid == "catalog":
            cat_id = node_id

    # Arrow from Catalog to SemanticMatcher
    if cat_id and comp_ids.get("matcher"):
        matcher_id = comp_ids["matcher"]
        arr_id = add_cell(
            "mxCell",
            {"edge": "1", "parent": "1", "source": cat_id, "target": matcher_id},
            style=(
                "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;"
                "jettySize=auto;html=1;strokeWidth=1;dashed=1;entryX=1;entryY=0.5;"
            ),
        )
        arr_geo = ET.SubElement(cells[-1], "mxGeometry")
        arr_geo.set("relative", "1")
        arr_geo.set("as", "geometry")

    # Legend box
    legend_y = 830 + 80
    legend_items = [
        ("Phase 1: Parser Foundation", "#D4E6F1"),
        ("Phase 2: Pipeline Automation", "#F9E79F"),
        ("Phase 3: Semantic Engine", "#D5F5E3"),
        ("Phase 4: Learning System", "#FADBD8"),
    ]
    legend_id = add_cell(
        "mxCell",
        {"vertex": "1", "parent": "1"},
        value="<b>Legend</b>",
        style=(
            "rounded=1;whiteSpace=wrap;html=1;fillColor=#F4F6F6;"
            "strokeColor=#333333;fontSize=10;align=center;"
        ),
    )
    geo = ET.SubElement(cells[-1], "mxGeometry")
    geo.set("x", str(x_center))
    geo.set("y", str(legend_y))
    geo.set("width", str(box_w))
    geo.set("height", str(55))
    geo.set("as", "geometry")

    # ...drawio file wraps in mxfile+diagram
    diagram = ET.Element("diagram", {"id": "semantic-arch", "name": "Architecture"})
    model = ET.SubElement(diagram, "mxGraphModel")
    model.set("dx", "800")
    model.set("dy", "600")
    model.set("grid", "1")
    model.set("gridSize", "10")
    model.set("guides", "1")
    model.set("tooltips", "1")
    model.set("connect", "1")
    model.set("arrows", "1")
    model.set("fold", "1")
    model.set("page", "1")
    model.set("pageScale", "1")
    model.set("pageWidth", "850")
    model.set("pageHeight", "1100")
    model.set("math", "0")
    model.set("shadow", "0")

    root = ET.SubElement(model, "root")
    for c in cells:
        root.append(c)

    mxfile = ET.Element("mxfile", {
        "host": "app.diagrams.net",
        "modified": "2026-07-22T12:00:00.000Z",
        "agent": "Mozilla/5.0 (generated)",
        "etag": "semantic-arch",
        "version": "21.6.5",
    })
    mxfile.append(diagram)

    # Serialize
    xml_str = ET.tostring(mxfile, encoding="unicode", xml_declaration=True)
    return xml_str


def make_json():
    data = {
        "version": "1.0",
        "title": "Semantic Engine Architecture",
        "flow": [
            {"stage": "PDF", "phase": "input", "responsibility": "Raw PDF file input (182 formats)"},
            {"stage": "ParserPDF", "phase": 1, "responsibility": "Extract text, tables, metadata from PDF"},
            {"stage": "LayoutDetector", "phase": 1, "responsibility": "Identify layout type and column structure"},
            {"stage": "AccountTypeResolver", "phase": 1, "responsibility": "Determine account type (ACTIVO/PASIVO/PERDIDA/PATRIMONIO) from column context"},
            {"stage": "AccountTypeFilter", "phase": 1, "responsibility": "Filter non-account rows (totals, headers, noise)"},
            {"stage": "SemanticNormalizer", "phase": 3, "responsibility": "Normalize, clean OCR errors, expand abbreviations, tokenize"},
            {"stage": "SemanticMatcher", "phase": 3, "responsibility": "Match normalized name to Concept Catalog via RapidFuzz"},
            {"stage": "CMCCClassifier", "phase": 3, "responsibility": "Assign final CMCC code with confidence level"},
            {"stage": "RegexFallback", "phase": 2, "responsibility": "Catch remaining accounts with legacy regex patterns"},
            {"stage": "Human Review", "phase": 4, "responsibility": "Manual resolution of UNKNOWN accounts"},
        ],
        "side_components": [
            {"name": "Concept Catalog", "phase": 3, "description": "78 concepts, versioned JSON, single source of truth", "feeds_into": "SemanticMatcher"},
            {"name": "Feature Flags", "phase": 2, "description": "CMCCFeatureFlags — runtime control of all stages", "controls": "all stages"},
        ],
        "phase_colors": {
            "phase1": "#D4E6F1",
            "phase2": "#F9E79F",
            "phase3": "#D5F5E3",
            "phase4": "#FADBD8",
        },
        "references": {
            "adr": "docs/ADR-001-Semantic-Architecture.md",
            "catalog": "knowledge/concept_catalog.json",
        },
    }
    return json.dumps(data, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    out_dir = __file__ and __file__[:-22]  # strip generate_diagram.py
    import os
    out_dir = os.path.dirname(os.path.abspath(__file__))

    drawio_path = os.path.join(out_dir, "architecture_semantic_engine.drawio")
    with open(drawio_path, "w") as f:
        f.write(make_drawio())
    print(f"Wrote {drawio_path}")

    json_path = os.path.join(out_dir, "architecture_semantic_engine.json")
    with open(json_path, "w") as f:
        f.write(make_json())
    print(f"Wrote {json_path}")
