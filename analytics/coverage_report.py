from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gold_standard.builder import GoldBuilder
from validation.validation_session import ValidationSession

from analytics.learning_dashboard import LearningDashboard
from analytics.unclassified_analyzer import UnclassifiedAnalyzer

logger = logging.getLogger(__name__)


class CoverageReport:
    def __init__(
        self,
        session: ValidationSession,
        metrics: dict[str, Any],
        db_path: str | Path = "gold_standard.db",
    ) -> None:
        self._session = session
        self._metrics = metrics
        self._db_path = db_path

    def _methods_summary(self) -> dict[str, Any]:
        md = self._metrics.get("methods_distribution", {})
        total = self._metrics.get("accounts_total", 1) or 1
        classified = self._metrics.get("accounts_classified", 0)
        unclassified = self._metrics.get("accounts_unclassified", 0)

        learning = md.get("learning_exact", 0) + md.get("learning_fuzzy", 0)
        code = md.get("code", 0)
        dictionary = md.get("dictionary_exact", 0) + md.get("dictionary_fuzzy", 0)

        return {
            "total_accounts": self._metrics.get("accounts_total", 0),
            "classified": classified,
            "unclassified": unclassified,
            "classified_pct": round(classified / total * 100, 2) if total else 0.0,
            "unclassified_pct": round(unclassified / total * 100, 2) if total else 0.0,
            "learning": learning,
            "learning_pct": round(learning / total * 100, 2) if total else 0.0,
            "code": code,
            "code_pct": round(code / total * 100, 2) if total else 0.0,
            "dictionary": dictionary,
            "dictionary_pct": round(dictionary / total * 100, 2) if total else 0.0,
            "methods": md,
        }

    def _top_frequent_unclassified(self, n: int = 20) -> list[dict[str, Any]]:
        analyzer = UnclassifiedAnalyzer(self._session)
        return analyzer.top_unclassified(n)

    def _gs_stats(self) -> dict[str, Any]:
        dashboard = LearningDashboard(self._db_path)
        stats = dashboard.summary()
        conflicts = dashboard.conflicts
        top = dashboard.top_learned(10)
        dashboard.close()
        return {
            "stats": stats,
            "conflicts": conflicts,
            "top_learned": top,
        }

    def _generate_recommendations(self) -> list[str]:
        recs: list[str] = []
        ms = self._methods_summary()
        gs = self._gs_stats()
        gs_stats = gs["stats"]
        gs_conflicts = gs["conflicts"]

        if ms["unclassified_pct"] > 50:
            recs.append(
                f"**ALTA PRIORIDAD:** El {ms['unclassified_pct']}% de cuentas no están clasificadas. "
                "Se recomienda poblar el Gold Standard con estas cuentas para que el Learning Engine "
                "pueda resolverlas automáticamente."
            )

        if gs_stats["total_records"] < 500:
            recs.append(
                f"**MEDIA PRIORIDAD:** El Gold Standard tiene solo {gs_stats['total_records']} registros. "
                "Un Gold Standard de al menos 500 registros mejoraría significativamente la cobertura "
                "del Learning Engine."
            )

        if ms["dictionary_pct"] > ms["learning_pct"] and ms["learning_pct"] > 0:
            recs.append(
                "**OPORTUNIDAD:** El diccionario aún clasifica más cuentas que el Learning Engine. "
                "Migrar las cuentas del diccionario al Gold Standard mejoraría la mantenibilidad "
                "y permitiría aprendizaje continuo."
            )

        if gs_conflicts:
            recs.append(
                f"**ATENCIÓN:** Hay {len(gs_conflicts)} conflicto(s) en el Gold Standard "
                "(misma cuenta con diferentes códigos). Revisar y resolver manualmente."
            )

        if ms["learning_pct"] > 50:
            recs.append(
                f"**BUENO:** El Learning Engine maneja el {ms['learning_pct']}% de las cuentas. "
                "El sistema está aprendiendo efectivamente."
            )

        if not recs:
            recs.append("Sin recomendaciones específicas. El sistema opera dentro de parámetros esperados.")

        return recs

    def generate(self) -> str:
        ms = self._methods_summary()
        gs = self._gs_stats()
        gs_stats = gs["stats"]
        gs_conflicts = gs["conflicts"]
        conflicts = gs["conflicts"]
        top_learned = gs["top_learned"]
        top_unclassified = self._top_frequent_unclassified(20)
        recs = self._generate_recommendations()
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        lines: list[str] = []
        lines.append("# Coverage Report")
        lines.append("")
        lines.append(f"**Generado:** {timestamp}")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## Resumen General")
        lines.append("")
        lines.append(f"- **Documentos procesados:** {self._metrics.get('total_documents', 0)}")
        lines.append(f"- **Cuentas totales:** {ms['total_accounts']}")
        lines.append(f"- **Clasificadas:** {ms['classified']} ({ms['classified_pct']}%)")
        lines.append(f"- **Sin clasificar:** {ms['unclassified']} ({ms['unclassified_pct']}%)")
        lines.append(f"- **Tiempo total:** {self._metrics.get('processing_time', 0):.3f}s")
        lines.append("")
        lines.append("## Distribución de Métodos")
        lines.append("")
        lines.append("| Método | Cuentas | % del Total |")
        lines.append("|--------|---------|-------------|")
        lines.append(f"| Learning Engine | {ms['learning']} | {ms['learning_pct']}% |")
        lines.append(f"| Código | {ms['code']} | {ms['code_pct']}% |")
        lines.append(f"| Diccionario | {ms['dictionary']} | {ms['dictionary_pct']}% |")
        lines.append(f"| Sin clasificar | {ms['unclassified']} | {ms['unclassified_pct']}% |")
        lines.append("")
        lines.append("### Desglose Learning Engine")
        lines.append("")
        exact = self._metrics.get("methods_distribution", {}).get("learning_exact", 0)
        fuzzy = self._metrics.get("methods_distribution", {}).get("learning_fuzzy", 0)
        lines.append(f"- **Exactas:** {exact}")
        lines.append(f"- **Fuzzy:** {fuzzy}")
        lines.append("")
        lines.append("## Gold Standard")
        lines.append("")
        lines.append(f"- **Registros totales:** {gs_stats['total_records']}")
        lines.append(f"- **Usage count promedio:** {gs_stats['avg_usage_count']}")
        lines.append(f"- **Pendientes de revisión:** {gs_stats['pending_review']}")
        lines.append(f"- **Conflictos:** {gs_stats['conflicts']}")
        lines.append(f"- **Learning Exact:** {gs_stats['learning_exact_pct']}%")
        lines.append(f"- **Learning Fuzzy:** {gs_stats['learning_fuzzy_pct']}%")
        lines.append("")
        if top_learned:
            lines.append("### Top 10 Cuentas Aprendidas")
            lines.append("")
            lines.append("| Cuenta | Código | Veces Usada |")
            lines.append("|--------|--------|-------------|")
            for row in top_learned:
                lines.append(f"| {row['account_name']} | {row['final_code']} | {row['usage_count']} |")
            lines.append("")

        if conflicts:
            lines.append("### Conflictos Detectados")
            lines.append("")
            lines.append("| Cuenta | Códigos en conflicto | Versiones |")
            lines.append("|--------|---------------------|-----------|")
            for c in conflicts[:10]:
                lines.append(f"| {c['account_name']} | {c['codes']} | {c['total_versions']} |")
            lines.append("")

        if top_unclassified:
            lines.append("## Top Cuentas Sin Clasificar")
            lines.append("")
            lines.append("| Nombre Normalizado | Frecuencia | Archivos | Códigos Únicos |")
            lines.append("|--------------------|------------|----------|----------------|")
            for acct in top_unclassified[:20]:
                lines.append(
                    f"| {acct['normalized_name']} | {acct['frequency']} | "
                    f"{acct['files_count']} | {acct['unique_codes_count']} |"
                )
            lines.append("")

        lines.append("## Recomendaciones Automáticas")
        lines.append("")
        for i, rec in enumerate(recs, 1):
            lines.append(f"{i}. {rec}")
        lines.append("")

        return "\n".join(lines)

    def save(self, path: str | Path = "coverage_report.md") -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        content = self.generate()
        out.write_text(content, encoding="utf-8")
        logger.info("Coverage report saved to: %s", out.resolve())
        return out
