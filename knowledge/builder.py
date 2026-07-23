from __future__ import annotations
import json
from pathlib import Path
from typing import Optional
import pandas as pd

from knowledge.concept import Concept
from knowledge.repository import Repository
from knowledge.normalizer import Normalizer
from knowledge.matcher import Matcher


class Proposal:
    def __init__(self, texto_observado: str, texto_normalizado: str,
                 concepto_sugerido: str, codigo_sugerido: str,
                 score: float, razon: str,
                 empresa: str = "", frecuencia: int = 0):
        self.texto_observado = texto_observado
        self.texto_normalizado = texto_normalizado
        self.concepto_sugerido = concepto_sugerido
        self.codigo_sugerido = codigo_sugerido
        self.score = score
        self.razon = razon
        self.empresa = empresa
        self.frecuencia = frecuencia

    def to_dict(self) -> dict:
        return {
            "texto_observado": self.texto_observado,
            "texto_normalizado": self.texto_normalizado,
            "concepto_sugerido": self.concepto_sugerido,
            "codigo_sugerido": self.codigo_sugerido,
            "score": self.score,
            "razon": self.razon,
            "empresa": self.empresa,
            "frecuencia": self.frecuencia,
        }


class Builder:
    def __init__(self, repository: Repository,
                 normalizer: Optional[Normalizer] = None,
                 matcher: Optional[Matcher] = None,
                 proposals_dir: str | Path = "knowledge/proposals"):
        self.repository = repository
        self.normalizer = normalizer or Normalizer()
        self.matcher = matcher or Matcher(repository, self.normalizer)
        self.proposals_dir = Path(proposals_dir)
        self.proposals_dir.mkdir(parents=True, exist_ok=True)

    def build_from_unclassified(self, path: str | Path) -> list[Proposal]:
        df = pd.read_excel(path)
        proposals = []
        name_groups = df.groupby("account_name")

        for name, group in name_groups:
            freq = len(group)
            empresa = str(group["source_file"].iloc[0]) if "source_file" in group.columns else ""
            raw_text = str(name)

            norm_result = self.normalizer.normalize(raw_text)
            normalized = norm_result.text

            matches = self.matcher.match(raw_text, top_n=1)

            if matches:
                best = matches[0]
                proposals.append(Proposal(
                    texto_observado=raw_text,
                    texto_normalizado=normalized,
                    concepto_sugerido=best.concept.nombre,
                    codigo_sugerido=best.concept.codigo,
                    score=best.score,
                    razon="; ".join(best.reasons),
                    empresa=empresa,
                    frecuencia=freq,
                ))
            else:
                proposals.append(Proposal(
                    texto_observado=raw_text,
                    texto_normalizado=normalized,
                    concepto_sugerido="",
                    codigo_sugerido="",
                    score=0.0,
                    razon="sin_coincidencia",
                    empresa=empresa,
                    frecuencia=freq,
                ))

        proposals.sort(key=lambda p: (-p.score, -p.frecuencia))
        return proposals

    def save_proposals(self, proposals: list[Proposal],
                       name: str = "proposals") -> tuple[Path, Path]:
        xlsx_path = self.proposals_dir / f"{name}.xlsx"
        json_path = self.proposals_dir / f"{name}.json"

        rows = [p.to_dict() for p in proposals]
        df = pd.DataFrame(rows)
        df.to_excel(xlsx_path, index=False)

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=2, ensure_ascii=False)

        return xlsx_path, json_path

    def build_and_save(self, unclassified_path: str | Path) -> tuple[Path, Path]:
        proposals = self.build_from_unclassified(unclassified_path)
        return self.save_proposals(proposals)
