from __future__ import annotations

from .models import TemplatePrediction

try:
    from structure_engine import TemplateRepository, TreeBuilder, TemplateBuilder, TemplateMatcher
    _HAS_STRUCTURE_ENGINE = True
except ImportError:
    _HAS_STRUCTURE_ENGINE = False


MOCK_TEMPLATES = {
    "SIN_CODIGO": {"name": "Template SC", "family": "TRIBUTARIO", "sim": 0.95, "conf": 0.7},
    "COMPACTO": {"name": "Template CP", "family": "TRIBUTARIO", "sim": 0.9, "conf": 0.65},
    "PUNTO": {"name": "Template PT", "family": "BALANCE_ESTANDAR", "sim": 0.85, "conf": 0.75},
    "GUION": {"name": "Template GN", "family": "BALANCE_ESTANDAR", "sim": 0.8, "conf": 0.7},
}


class TemplateClassifier:

    def __init__(self, repo_path: str = "structure_repository.json"):
        self.repo_path = repo_path
        self._repo = None
        self._load_repo()

    def _load_repo(self):
        if not _HAS_STRUCTURE_ENGINE:
            return
        try:
            self._repo = TemplateRepository(self.repo_path)
            self._repo.load()
        except Exception:
            self._repo = None

    def predict(
        self,
        code_format: str = "",
        column_layout: str = "",
        total_lines: int = 0,
        account_lines: list[dict] | None = None,
    ) -> TemplatePrediction | None:
        template = self._predict_from_repo(code_format, account_lines)
        if template:
            return template

        return self._predict_heuristic(code_format, total_lines)

    def _predict_from_repo(
        self,
        code_format: str = "",
        account_lines: list[dict] | None = None,
    ) -> TemplatePrediction | None:
        if not _HAS_STRUCTURE_ENGINE or not self._repo:
            return None
        try:
            if not self._repo.templates:
                return None

            if account_lines:
                builder = TreeBuilder()
                tree = builder.build_tree(account_lines)
                matcher = TemplateMatcher(self._repo.templates)
                match = matcher.best_match(tree)
                if match:
                    tpl = self._repo.get(match.template_id)
                    tname = tpl.name if tpl else match.template_id
                    return TemplatePrediction(
                        template_id=match.template_id,
                        template_name=tname,
                        family=match.family,
                        similarity=match.similarity,
                        confidence=match.confidence,
                        matched_sections=match.matched_sections,
                        total_sections=match.total_sections,
                        signals=[f"repo_match:sim={match.similarity:.2f}"],
                    )

            for t in self._repo.templates:
                if t.code_format == code_format:
                    return TemplatePrediction(
                        template_id=t.template_id,
                        template_name=t.name,
                        family=t.family,
                        similarity=0.85,
                        confidence=0.75,
                        signals=[f"repo_code_format_match:{code_format}"],
                    )
        except Exception:
            pass
        return None

    def _predict_heuristic(
        self,
        code_format: str = "",
        total_lines: int = 0,
    ) -> TemplatePrediction | None:
        mock = MOCK_TEMPLATES.get(code_format)
        if not mock:
            if total_lines > 0:
                mock = MOCK_TEMPLATES.get("PUNTO")
            else:
                return None

        return TemplatePrediction(
            template_id=f"heuristic_{code_format}",
            template_name=mock["name"],
            family=mock["family"],
            similarity=mock["sim"],
            confidence=mock["conf"],
            signals=[f"heuristic:code_format={code_format}"],
        )

    def _build_quick_tree(self, raw_lines: list[str]) -> list[dict]:
        accounts = []
        for i, line in enumerate(raw_lines[:200]):
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            code = ""
            name = line
            if parts and (parts[0].isdigit() or "." in parts[0] or "-" in parts[0]):
                code = parts[0]
                name = " ".join(parts[1:]) if len(parts) > 1 else ""
            accounts.append({
                "nombre": name,
                "monto": 0,
                "codigo": code,
                "origen_columna": "",
                "es_total": False,
                "linea": i,
            })
        return accounts
