import sys
import tempfile
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st

from pipeline.homologation_pipeline import HomologationPipeline


st.set_page_config(
    page_title="Homologador de Balances",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Homologador de Balances Tributarios")
st.caption("MVP Producto")


uploaded_file = st.file_uploader(
    "Seleccione un Balance Tributario",
    type=["pdf", "xls", "xlsx"],
)


if uploaded_file:

    suffix = Path(uploaded_file.name).suffix

    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=suffix,
    ) as tmp:
        tmp.write(uploaded_file.read())
        archivo_temporal = tmp.name

    with st.spinner("Analizando balance..."):

        pipeline = HomologationPipeline()

        resultado = pipeline.process(
            archivo_temporal
        )

    st.success("Proceso terminado")

    st.subheader("Resumen")

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Cuentas detectadas",
        resultado["accounts_total"]
    )

    c2.metric(
        "Clasificadas",
        resultado["accounts_classified"]
    )

    c3.metric(
        "Pendientes",
        resultado["accounts_without_dictionary_match"]
    )

    c4.metric(
        "Tiempo",
        f'{resultado["elapsed_seconds"]:.2f}s'
    )

    cuentas = resultado["classified"]

    df = pd.DataFrame(cuentas)

    clasificadas = df[
        df["standard_code"].notna()
    ]

    pendientes = df[
        df["standard_code"].isna()
    ]

    st.divider()

    st.subheader("📥 Exportar resultado")

    buffer = BytesIO()

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(
            writer,
            index=False,
            sheet_name="Resultado"
        )

    buffer.seek(0)

    st.download_button(
        label="⬇ Descargar Excel homologado",
        data=buffer,
        file_name="Balance_Homologado.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    st.divider()

    st.subheader("✅ Cuentas clasificadas")

    if len(clasificadas):

        columnas = [
            "account_name",
            "standard_code",
            "final_code",
            "confidence",
            "method",
            "reason",
        ]

        columnas = [
            c for c in columnas
            if c in clasificadas.columns
        ]

        st.dataframe(
            clasificadas[columnas],
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.info("No hay cuentas clasificadas.")

    st.divider()

    st.subheader("⚠️ Cuentas pendientes")

    if len(pendientes):

        columnas = [
            "account_name",
            "reason",
            "confidence",
        ]

        columnas = [
            c for c in columnas
            if c in pendientes.columns
        ]

        st.dataframe(
            pendientes[columnas],
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.success("Todas las cuentas fueron clasificadas.")
