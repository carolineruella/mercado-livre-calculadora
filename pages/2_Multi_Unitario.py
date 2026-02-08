import streamlit as st
import pandas as pd
from io import BytesIO

from src.cliente_multi_unitario import (
    gerar_template_excel,
    processar_multi_unitario,
)
from src.dados_tarifarios import carregar_csv_aneel
from src.grafico import criar_grafico_economia
from src.relatorio_pdf import gerar_relatorio
from src.formatacao import formatar_moeda, formatar_percentual

st.set_page_config(page_title="Multi Unitário", page_icon="⚡", layout="wide")
st.title("📋 Processamento Multi Unitário")
st.markdown("Processe várias unidades consumidoras de uma vez via upload de planilha Excel.")

# ---------------------------------------------------------------------------
# Template download
# ---------------------------------------------------------------------------
st.download_button(
    "📥 Baixar Template Excel",
    data=gerar_template_excel(),
    file_name="template_multi_unitario.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

st.divider()

# ---------------------------------------------------------------------------
# Upload and process
# ---------------------------------------------------------------------------
arquivo = st.file_uploader("Upload da planilha preenchida (.xlsx)", type=["xlsx"])

if arquivo is not None:
    try:
        df_preview = pd.read_excel(arquivo, sheet_name="Unidades")
    except Exception:
        df_preview = pd.read_excel(arquivo)

    if len(df_preview) == 0:
        st.warning("A planilha enviada está vazia. Adicione pelo menos uma unidade.")
    else:
        st.markdown(f"**{len(df_preview)} unidade(s) encontrada(s)**")
        st.dataframe(df_preview, hide_index=True, use_container_width=True)

        if st.button("⚡ Processar Todas as Unidades", use_container_width=True):
            df_tarifas = carregar_csv_aneel()
            progress = st.progress(0, text="Processando...")

            def atualizar_progresso(valor, texto):
                progress.progress(valor, text=texto)

            arquivo.seek(0)
            resultado = processar_multi_unitario(
                arquivo.read(), df_tarifas, progress_callback=atualizar_progresso
            )

            progress.progress(1.0, text="Concluído!")
            st.toast("Processamento concluído!", icon="✅")

            unidades = resultado["unidades"]
            consolidado = resultado["consolidado"]

            # --- Consolidated results ---
            st.subheader("Resultados Consolidados")

            df_res = pd.DataFrame([
                {
                    "Nome": r["Nome"],
                    "Distribuidora": r["Distribuidora"],
                    "Desconto": formatar_percentual(r["Desconto"]) if r["Desconto"] else "Erro",
                    "Economia Total": formatar_moeda(r["Economia Total"]),
                    "Economia VPL": formatar_moeda(r["Economia VPL"]),
                }
                for r in unidades
            ])
            st.dataframe(df_res, hide_index=True, use_container_width=True)

            # Totals
            tc1, tc2 = st.columns(2)
            tc1.metric("Economia Total Consolidada", formatar_moeda(consolidado["total_economia"]))
            tc2.metric("Economia VPL Consolidada", formatar_moeda(consolidado["total_vpl"]))

            # Consolidated chart
            valid_results = [r for r in unidades if "_resultado" in r]
            if valid_results:
                all_anos = set()
                for r in valid_results:
                    for a in r["_resultado"]["anos"]:
                        all_anos.add(a)
                anos_sorted = sorted(all_anos)

                gastos_acl_total = []
                economias_total = []
                for ano in anos_sorted:
                    acl_sum = 0.0
                    eco_sum = 0.0
                    for r in valid_results:
                        res = r["_resultado"]
                        for i, a in enumerate(res["anos"]):
                            if a == ano:
                                acl_sum += res["gastos_acl_anual"][i]
                                eco_sum += res["economias_anual"][i]
                    gastos_acl_total.append(acl_sum)
                    economias_total.append(eco_sum)

                fig_consolidado = criar_grafico_economia(gastos_acl_total, economias_total, anos_sorted)
                fig_consolidado.update_layout(title="Economia Consolidada por Ano")
                st.plotly_chart(fig_consolidado, use_container_width=True)

            # Download results Excel
            df_export = pd.DataFrame([
                {
                    "Nome": r["Nome"],
                    "Distribuidora": r["Distribuidora"],
                    "Desconto (%)": round(r["Desconto"] * 100, 2) if r["Desconto"] else 0,
                    "Economia Total (R$)": round(r["Economia Total"], 2),
                    "Economia VPL (R$)": round(r["Economia VPL"], 2),
                    "Erro": r.get("_erro", ""),
                }
                for r in unidades
            ])

            buf_res = BytesIO()
            with pd.ExcelWriter(buf_res, engine="xlsxwriter") as writer:
                df_export.to_excel(writer, index=False, sheet_name="Resultados")
            st.download_button(
                "📊 Baixar Resultados Excel",
                data=buf_res.getvalue(),
                file_name="resultados_multi_unitario.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

            # Show errors
            erros = [r for r in unidades if "_erro" in r]
            if erros:
                st.warning(f"{len(erros)} unidade(s) com erro:")
                for r in erros:
                    st.error(f"**{r['Nome']}**: {r['_erro']}")
