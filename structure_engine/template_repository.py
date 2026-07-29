from __future__ import annotations
import json
from pathlib import Path
from typing import Optional
from .structure_models import StructureTemplate, StructuralFamily, StructuralSignature


class TemplateRepository:

    def __init__(self, path: str | Path = "structure_repository.json"):
        self.path = Path(path)
        self.templates: list[StructureTemplate] = []
        self.families: list[StructuralFamily] = []

    def add_template(self, template: StructureTemplate):
        existing = [t for t in self.templates if t.template_id == template.template_id]
        if existing:
            from .template_builder import TemplateBuilder
            merged = TemplateBuilder.merge_templates(existing[0], template)
            self.templates.remove(existing[0])
            self.templates.append(merged)
        else:
            self.templates.append(template)

    def get(self, template_id: str) -> Optional[StructureTemplate]:
        for t in self.templates:
            if t.template_id == template_id:
                return t
        return None

    @property
    def total_templates(self) -> int:
        return len(self.templates)

    @property
    def total_files(self) -> int:
        return sum(t.frequency for t in self.templates)

    def save(self, path: Optional[str | Path] = None):
        output = path or self.path
        data = {
            "metadata": {
                "total_templates": self.total_templates,
                "total_files": self.total_files,
                "total_families": len(self.families),
            },
            "families": [
                {
                    "name": f.name,
                    "templates": f.templates,
                    "total_members": f.total_members,
                    "avg_depth": f.avg_depth,
                    "common_pattern": f.common_pattern,
                    "description": f.description,
                }
                for f in self.families
            ],
            "templates": [
                {
                    "template_id": t.template_id,
                    "family": t.family,
                    "name": t.name,
                    "type_sequence": t.type_sequence,
                    "level_sequence": t.level_sequence[:100],
                    "section_sequence": list(dict.fromkeys(t.section_sequence))[:30],
                    "max_depth": t.max_depth,
                    "total_nodes": t.total_nodes,
                    "subtotal_count": t.subtotal_count,
                    "section_count": t.section_count,
                    "node_type_counts": t.node_type_counts,
                    "code_format": t.code_format,
                    "column_layout": t.column_layout,
                    "example_files": t.example_files[:5],
                    "frequency": t.frequency,
                }
                for t in self.templates
            ],
        }
        Path(output).write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def load(self, path: Optional[str | Path] = None):
        src = path or self.path
        p = Path(src)
        if not p.exists():
            return
        data = json.loads(p.read_text())
        self.templates = []
        for tdata in data.get("templates", []):
            template = StructureTemplate(
                template_id=tdata["template_id"],
                family=tdata.get("family", ""),
                name=tdata.get("name", ""),
                type_sequence=tdata.get("type_sequence", ""),
                level_sequence=tdata.get("level_sequence", []),
                section_sequence=tdata.get("section_sequence", []),
                max_depth=tdata.get("max_depth", 0),
                total_nodes=tdata.get("total_nodes", 0),
                subtotal_count=tdata.get("subtotal_count", 0),
                section_count=tdata.get("section_count", 0),
                node_type_counts=tdata.get("node_type_counts", {}),
                code_format=tdata.get("code_format", ""),
                column_layout=tdata.get("column_layout", ""),
                example_files=tdata.get("example_files", []),
                frequency=tdata.get("frequency", 1),
            )
            self.templates.append(template)
        self.families = [
            StructuralFamily(**fdata) for fdata in data.get("families", [])
        ]

    def set_families(self, families: list[StructuralFamily]):
        self.families = families
