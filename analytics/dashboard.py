from __future__ import annotations

from typing import Any


class AnalyticsDashboard:
    """Dashboard principal de Analytics.

    Orquestra la renderización de todas las secciones del panel de
    métricas y cobertura del sistema de homologación.

    Cada sección se renderiza en un método ``_render_*`` independiente.
    Todos los imports pesados (streamlit, pandas, etc.) se hacen dentro
    del método que los necesita para no forzar su carga al importar la
    clase.
    """

    def __init__(
        self,
        session: Any = None,
        metrics: dict[str, Any] | None = None,
    ) -> None:
        self._session = session
        self._metrics = metrics

    def render(self) -> None:
        """Punto de entrada único. Renderiza el dashboard completo."""
        self._render_header()
        self._render_kpis()
        self._render_coverage()
        self._render_gold_standard()
        self._render_learning()
        self._render_unclassified()
        self._render_benchmark()
        self._render_history()
        self._render_exports()

    # ------------------------------------------------------------------
    # Secciones
    # ------------------------------------------------------------------

    def _render_header(self) -> None:
        """Título, descripción, selector de periodo / lote."""

    def _render_kpis(self) -> None:
        """KPIs globales: documentos, cuentas, clasificadas, learning hits."""
        metrics = self._metrics
        if metrics is None and self._session is not None:
            from validation.metrics_engine import MetricsEngine
            engine = MetricsEngine()
            metrics = engine.compute(self._session)
            self._metrics = metrics

        if metrics is None:
            return

        import streamlit as st

        total = metrics.get("accounts_total", 0)
        classified = metrics.get("accounts_classified", 0)
        unclassified = metrics.get("accounts_unclassified", 0)
        coverage = round(classified / total * 100, 1) if total else 0.0

        cols = st.columns(6)
        cols[0].metric("Documentos", metrics.get("total_documents", 0))
        pdf_c = metrics.get("pdf_count", 0)
        xls_c = metrics.get("excel_count", 0)
        cols[0].caption(f"PDF {pdf_c}  ·  Excel {xls_c}")

        cols[1].metric("Cuentas", total)
        cols[1].caption(f"{classified} clasificadas  ·  {unclassified} sin clasificar")

        cols[2].metric("Cobertura", f"{coverage}%")
        cols[2].caption(f"{classified} / {total}")

        cols[3].metric("Learning Hits", metrics.get("learning_hits", 0))
        cols[3].caption("coincidencias vs Gold Standard")

        cols[4].metric("Tiempo Total", f"{metrics.get('processing_time', 0):.1f}s")
        cols[4].caption(f"{metrics.get('avg_time', 0):.2f}s promedio")

        cols[5].metric("Sin Clasificar", unclassified)
        cols[5].caption(f"{round(unclassified / total * 100, 1) if total else 0}% del total")

    def _render_coverage(self) -> None:
        """Distribución de métodos: learning vs código vs diccionario vs sin clasificar."""
        metrics = self._metrics
        if metrics is None and self._session is not None:
            from validation.metrics_engine import MetricsEngine
            engine = MetricsEngine()
            metrics = engine.compute(self._session)
            self._metrics = metrics

        if metrics is None:
            return

        import streamlit as st

        total = metrics.get("accounts_total", 0) or 1
        md = metrics.get("methods_distribution", {})
        unclassified = metrics.get("accounts_unclassified", 0)

        learning = md.get("learning_exact", 0) + md.get("learning_fuzzy", 0)
        code = md.get("code", 0)
        dict_exact = md.get("dictionary_exact", 0)
        dict_fuzzy = md.get("dictionary_fuzzy", 0)

        st.markdown("### Cobertura de Clasificación")
        st.caption(f"Distribución de {metrics.get('accounts_total', 0)} cuentas por método")

        items = [
            ("🧠 Learning", learning, "#1f77b4"),
            ("📘 Diccionario Exacto", dict_exact, "#2ca02c"),
            ("📗 Diccionario Fuzzy", dict_fuzzy, "#98df8a"),
            ("🔢 Código", code, "#ff7f0e"),
            ("❌ Sin clasificar", unclassified, "#d62728"),
        ]

        col_hdr, col_bar = st.columns([1, 4])
        col_hdr.markdown("**Método**")
        col_bar.markdown("**Cuentas**")

        for label, count, color in items:
            pct = count / total * 100
            col_lbl, col_val = st.columns([1, 4])
            col_lbl.markdown(f"{label}")
            pct_str = f"{pct:.1f}%"
            col_val.markdown(f"{label}: **{count}** ({pct_str})")
            col_val.progress(int(pct))

    def _render_gold_standard(self) -> None:
        """Estado del Gold Standard: registros, crecimiento, top learned."""
        if self._session is None and self._metrics is None:
            return

        import streamlit as st
        from gold_standard.builder import GoldBuilder

        builder = GoldBuilder()
        stats = builder.statistics()
        records = builder.list_all()
        conflicts = builder.find_conflicts()
        top = builder.top_learned(1)
        builder.close()

        total = stats["total_records"]
        if total == 0:
            st.info("Gold Standard vacío. Usa *Seed Gold Standard* para poblarlo.")
            return

        usage_counts = [r.usage_count for r in records if r.usage_count]
        avg_usage = round(sum(usage_counts) / len(usage_counts), 2) if usage_counts else 0.0

        last_updated = max(r.last_used for r in records if r.last_used)[:10] if any(r.last_used for r in records) else "—"

        top_name = f"{top[0]['account_name']} → {top[0]['final_code']}" if top else "—"

        st.markdown("### Gold Standard")

        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Registros", total)
        col2.metric("Conflictos", stats["conflicts"])
        col3.metric("Uso Promedio", avg_usage)
        col4.metric("Top Cuenta", top_name)
        col5.metric("Última Actualización", last_updated)

        col_a, col_b = st.columns(2)
        with col_a:
            import csv
            import io as _io
            buf = _io.StringIO()
            fields = [
                "source_file", "account_code_original", "account_name",
                "account_nature", "suggested_code", "suggested_confidence",
                "final_code", "reviewer", "review_date", "comments",
            ]
            writer = csv.DictWriter(buf, fieldnames=fields)
            writer.writeheader()
            for r in records:
                d = r.to_dict()
                writer.writerow({k: d.get(k, "") for k in fields})
            csv_data = buf.getvalue()
            st.download_button(
                "📥 Export Gold Standard",
                data=csv_data,
                file_name="gold_standard.csv",
                mime="text/csv",
            )

        with col_b:
            import json as _json
            conflicts_slim = [
                {"account_name": c["account_name"], "codes": c["codes"], "versions": c["total_versions"]}
                for c in conflicts
            ]
            stats_data = _json.dumps(
                {
                    "total_records": total,
                    "conflicts": stats["conflicts"],
                    "conflict_details": conflicts_slim,
                    "avg_usage_count": avg_usage,
                    "top_account": top_name,
                    "last_updated": last_updated,
                },
                indent=2,
                ensure_ascii=False,
            )
            st.download_button(
                "📥 Export Statistics",
                data=stats_data,
                file_name="gold_standard_stats.json",
                mime="application/json",
            )

    def _render_learning(self) -> None:
        """Detalle del Learning Engine: exact vs fuzzy, cobertura por empresa."""
        if self._session is None and self._metrics is None:
            return

        import streamlit as st
        from gold_standard.builder import GoldBuilder

        builder = GoldBuilder()
        top = builder.top_learned(100)
        builder.close()

        if not top:
            return

        st.markdown("### Top 100 Aprendizaje")

        rows = []
        for row in top:
            rows.append({
                "Cuenta": row["account_name"],
                "Código": row["final_code"],
                "Usos": row["usage_count"],
                "Último Uso": (row["last_used"][:10] if row.get("last_used") else "—"),
            })

        st.dataframe(rows, use_container_width=True, hide_index=True)

    def _render_unclassified(self) -> None:
        """Cuentas sin clasificar: top frecuencias, export."""
        if self._session is None:
            return

        import streamlit as st
        from analytics.unclassified_analyzer import UnclassifiedAnalyzer
        from gold_standard.builder import GoldBuilder
        from gold_standard.models import GoldRecord

        analyzer = UnclassifiedAnalyzer(self._session)
        top = analyzer.top_unclassified(100)

        if not top:
            return

        st.markdown("### Top 100 Sin Clasificar")

        rows = []
        for row in top:
            rows.append({
                "Cuenta": row["example_raw_name"],
                "Frecuencia": row["frequency"],
                "Archivos": row["files_count"],
                "Códigos Distintos": row["unique_codes_count"],
            })

        st.dataframe(rows, use_container_width=True, hide_index=True)

        st.markdown("#### Aprender cuenta")
        labels = {r["example_raw_name"]: f"{r['example_raw_name']} ({r['frequency']}x)" for r in top}
        selected_name = st.selectbox(
            "Cuenta sin clasificar",
            options=[r["example_raw_name"] for r in top],
            format_func=lambda x: labels.get(x, x),
            key="unclassified_learn_select",
        )
        code = st.text_input(
            "Código Estándar",
            placeholder="ej: AC.01",
            key="unclassified_learn_code",
        )
        if st.button("Aprender", key="unclassified_learn_btn", type="primary",
                     disabled=not code):
            builder = GoldBuilder()
            record = GoldRecord(
                account_name=selected_name,
                account_code_original="",
                final_code=code,
                reviewer="analista",
            )
            builder.add_or_update(record)
            builder.close()
            st.success(f"✅ Aprendido: **{selected_name}** → **{code}**")
            st.rerun()

    def _render_benchmark(self) -> None:
        """Benchmark contra Gold Standard: accuracy, precision, recall, F1."""
        if self._session is None:
            return

        import streamlit as st
        from analytics.benchmark_dashboard import BenchmarkDashboard

        if not hasattr(self, "_benchmark_cache"):
            bench = BenchmarkDashboard()
            self._benchmark_cache = bench.evaluate(self._session)
            bench.close()

        result: dict[str, Any] = self._benchmark_cache
        if "error" in result:
            st.info(result["error"])
            return

        metrics = self._metrics or {}
        md = metrics.get("methods_distribution", {})
        learning = md.get("learning_exact", 0) + md.get("learning_fuzzy", 0)
        total = metrics.get("accounts_total", 0) or 1
        learning_pct = round(learning / total * 100, 1)

        st.markdown("### Benchmark vs Gold Standard")

        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Accuracy", f"{result['accuracy']:.1%}")
        col2.metric("Precisión", f"{result['macro_precision']:.1%}")
        col3.metric("Recall", f"{result['macro_recall']:.1%}")
        col4.metric("F1", f"{result['macro_f1']:.1%}")
        col5.metric("Exact Match", result["exact_matches"])

        col6, col7, col8, col9 = st.columns(4)
        col6.metric("Legacy", result["gs_covered_accounts"])
        col7.metric("Nuevo", f"{result['learning_accuracy']:.1%}")
        col8.metric("Learning %", f"{learning_pct}%")
        col9.metric("Shadow Match %", f"{result['non_learning_accuracy']:.1%}")

    def _render_history(self) -> None:
        """Evolución histórica: comparativa contra runs anteriores."""
        import json
        from pathlib import Path

        reports_dir = Path("reports/validation")
        if not reports_dir.is_dir():
            return

        import streamlit as st

        runs = sorted(
            [d for d in reports_dir.iterdir() if d.is_dir() and (d / "metrics.json").exists()]
        )
        if len(runs) < 2:
            st.info("Se necesitan al menos 2 ejecuciones para mostrar histórico.")
            return

        timestamps: list[str] = []
        total_docs: list[int] = []
        total_accts: list[int] = []
        classified: list[int] = []
        unclassified: list[int] = []
        learning_hits: list[int] = []
        dict_hits: list[int] = []
        code_hits: list[int] = []
        fuzzy_hits: list[int] = []
        proc_time: list[float] = []
        avg_time: list[float] = []
        p95_time: list[float] = []

        for run_dir in runs:
            with open(run_dir / "metrics.json") as f:
                m = json.load(f)
            label = run_dir.name[8:]  # HHMMSS
            timestamps.append(label)
            total_docs.append(m.get("total_documents", 0))
            total_accts.append(m.get("accounts_total", 0))
            classified.append(m.get("accounts_classified", 0))
            unclassified.append(m.get("accounts_unclassified", 0))
            learning_hits.append(m.get("learning_hits", 0))
            dict_hits.append(m.get("dictionary_hits", 0))
            code_hits.append(m.get("code_hits", 0))
            fuzzy_hits.append(m.get("fuzzy_hits", 0))
            proc_time.append(round(m.get("processing_time", 0), 1))
            avg_time.append(round(m.get("avg_time", 0), 2))
            p95_time.append(round(m.get("p95_time", 0), 2))

        st.markdown("### Histórico de Ejecuciones")
        st.caption(f"{len(runs)} ejecuciones — {reports_dir}")

        st.markdown("**Cuentas**")
        st.line_chart(
            {"Ejecución": timestamps, "Total": total_accts, "Clasificadas": classified, "Sin Clasificar": unclassified},
            x="Ejecución", y=["Total", "Clasificadas", "Sin Clasificar"],
            use_container_width=True,
        )

        st.markdown("**Tiempo de Procesamiento (s)**")
        st.line_chart(
            {"Ejecución": timestamps, "Total": proc_time, "Promedio": avg_time, "P95": p95_time},
            x="Ejecución", y=["Total", "Promedio", "P95"],
            use_container_width=True,
        )

        st.markdown("**Documentos**")
        st.bar_chart(
            {"Ejecución": timestamps, "Documentos": total_docs},
            x="Ejecución", y="Documentos",
            use_container_width=True,
        )

        st.markdown("**Hits por Método**")
        st.line_chart(
            {"Ejecución": timestamps, "Learning": learning_hits, "Diccionario": dict_hits, "Código": code_hits, "Fuzzy": fuzzy_hits},
            x="Ejecución", y=["Learning", "Diccionario", "Código", "Fuzzy"],
            use_container_width=True,
        )

    def _render_exports(self) -> None:
        """Botones de exportación: Excel, Markdown, JSON."""
        import streamlit as st

        st.markdown("### Exportar Dashboards")

        col_a, col_b = st.columns(2)
        col_c, col_d = st.columns(2)

        # ── coverage_dashboard.xlsx ────────────────────────────────────────
        with col_a:
            coverage_data = self._build_coverage_export()
            st.download_button(
                "📊 Export Coverage",
                data=coverage_data,
                file_name="coverage_dashboard.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

        # ── learning_dashboard.xlsx ────────────────────────────────────────
        with col_b:
            learning_data = self._build_learning_export()
            if learning_data:
                st.download_button(
                    "🧠 Export Learning",
                    data=learning_data,
                    file_name="learning_dashboard.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )

        # ── benchmark_dashboard.xlsx ───────────────────────────────────────
        with col_c:
            benchmark_data = self._build_benchmark_export()
            if benchmark_data:
                st.download_button(
                    "📈 Export Benchmark",
                    data=benchmark_data,
                    file_name="benchmark_dashboard.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )

        # ── unclassified_top500.xlsx ──────────────────────────────────────
        with col_d:
            unclassified_data = self._build_unclassified_export()
            if unclassified_data:
                st.download_button(
                    "❌ Export Unclassified Top 500",
                    data=unclassified_data,
                    file_name="unclassified_top500.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )

    # ------------------------------------------------------------------
    # Helpers de exportación
    # ------------------------------------------------------------------

    def _build_coverage_export(self) -> bytes:
        """Construye Excel de cobertura desde CoverageReport + session."""
        import io

        import pandas as pd

        from analytics.coverage_report import CoverageReport

        if self._session is not None and self._metrics is not None:
            report = CoverageReport(self._session, self._metrics)
            summary = report._methods_summary()
            top_un = report._top_frequent_unclassified(500)
        else:
            summary = {}
            top_un = []

        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            if summary:
                pd.DataFrame([summary]).to_excel(writer, sheet_name="Summary", index=False)
            if top_un:
                pd.DataFrame(top_un).to_excel(writer, sheet_name="Unclassified", index=False)
            pd.DataFrame({"generated": ["ok"]}).to_excel(writer, sheet_name="Info", index=False)
        buf.seek(0)
        return buf.read()

    @staticmethod
    def _temp_excel(export_fn: Any) -> bytes | None:
        """Escribe a archivo temporal via *export_fn*, lee bytes, limpia."""
        import os
        import tempfile

        try:
            with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
                tmp_path = tmp.name
            export_fn(tmp_path)
            with open(tmp_path, "rb") as f:
                data = f.read()
            os.unlink(tmp_path)
            return data
        except Exception:
            return None

    def _build_learning_export(self) -> bytes | None:
        """Usa LearningDashboard.export_excel con archivo temporal."""
        try:
            from analytics.learning_dashboard import LearningDashboard

            dashboard = LearningDashboard()
            def _write(p: str) -> None:
                dashboard.export_excel(p)
                dashboard.close()
            return self._temp_excel(_write)
        except Exception:
            return None

    def _build_benchmark_export(self) -> bytes | None:
        """Usa BenchmarkDashboard.export_excel con archivo temporal."""
        if self._session is None:
            return None

        try:
            from analytics.benchmark_dashboard import BenchmarkDashboard

            dashboard = BenchmarkDashboard()
            def _write(p: str) -> None:
                dashboard.export_excel(p, self._session)
                dashboard.close()
            return self._temp_excel(_write)
        except Exception:
            return None

    def _build_unclassified_export(self) -> bytes | None:
        """Usa UnclassifiedAnalyzer.export_excel con archivo temporal."""
        if self._session is None:
            return None

        try:
            from analytics.unclassified_analyzer import UnclassifiedAnalyzer

            analyzer = UnclassifiedAnalyzer(self._session)
            return self._temp_excel(lambda p: analyzer.export_excel(p, n=500))
        except Exception:
            return None
