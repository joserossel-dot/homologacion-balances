"""Repositorio de perfiles aprendidos (Sprint 35).

Guarda y carga los `TableProfile` como JSON:

  - `knowledge_base/extractor_profiles.json` (todos los perfiles juntos)
  - un archivo por familia en `knowledge_base/profiles/<family_id>.json`

También genera `reports/extractor_trainer_report.md` con cobertura y
precisión por familia.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

from .profile import TableProfile


class ProfileRepository:
    """Persistencia de perfiles en JSON."""

    def __init__(self, path: str | Path = "knowledge_base/extractor_profiles.json"):
        self.path = Path(path)

    # ------------------------------------------------------------------
    # Guardar / cargar (archivo único)
    # ------------------------------------------------------------------

    def save(self, profiles: dict[str, TableProfile]) -> Path:
        """Guarda todos los perfiles en un único JSON (familia_id → perfil)."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "n_families": len(profiles),
            "families": {
                fid: profile.to_dict() for fid, profile in profiles.items()
            },
        }
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return self.path

    def load(self) -> dict[str, TableProfile]:
        """Carga los perfiles desde el JSON (familia_id → TableProfile)."""
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        families = data.get("families", {})
        return {
            fid: TableProfile.from_dict(profile)
            for fid, profile in families.items()
        }

    # ------------------------------------------------------------------
    # Archivo por familia
    # ------------------------------------------------------------------

    def save_individual(self, profiles: dict[str, TableProfile],
                        directory: str | Path) -> Path:
        """Guarda un archivo JSON por familia."""
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        for fid, profile in profiles.items():
            (directory / f"{fid}.json").write_text(
                json.dumps(profile.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        return directory

    # ------------------------------------------------------------------
    # Reporte
    # ------------------------------------------------------------------

    def write_report(self, profiles: dict[str, TableProfile],
                     report_path: str | Path) -> Path:
        """Genera un reporte Markdown con cobertura/precisión por familia."""
        report_path = Path(report_path)
        report_path.parent.mkdir(parents=True, exist_ok=True)

        rows = []
        for fid, profile in profiles.items():
            val = profile.validation or {}
            rows.append((
                profile.family_name or fid,
                f"{profile.n_documents}/{profile.docs_total}",
                profile.layout,
                profile.code_pattern,
                profile.document_type,
                f"{val.get('coverage', 0.0):.2f}",
                f"{val.get('precision', 0.0):.2f}",
                f"{val.get('columns_rate', 0.0):.2f}",
                f"{val.get('columns_detected', 0):.1f}/{val.get('columns_expected', 0)}",
                val.get("total_rows_lost", 0),
            ))

        rows.sort(key=lambda r: (-int(r[1].split("/")[0]), r[0]))
        lines = [
            "# Reporte de Perfiles de Extractores — Sprint 35",
            "",
            f"Perfiles generados: **{len(profiles)}** familias",
            "",
            "| Familia | Docs (núcleo/parseables) | Layout | Código | Tipo | "
            "Cobertura | Precisión | Columnas (rate) | Columnas | Filas perdidas |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        for r in rows:
            lines.append("| {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(*r))

        lines += [
            "",
            "> Cobertura = filas contables dentro de la región de tabla predicha "
            "/ total de filas contables.",
            "",
            "> Precisión = filas contables de la región / tamaño de la región.",
            "",
            "> Columnas (rate) = fracción promedio de columnas del perfil "
            "detectadas por documento.",
            "",
        ]
        report_path.write_text("\n".join(lines), encoding="utf-8")
        return report_path
