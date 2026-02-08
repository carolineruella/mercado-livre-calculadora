import streamlit as st
import pandas as pd
from io import BytesIO

from src.constantes import TIPO_ENERGIA, TIPO_ICMS
from src.models import (
    DadosConsumo,
    DadosContrato,
    DadosOferta,
    DadosTributarios,
    DadosCliente,
    ParametrosSimulacao,
)
from src.dados_tarifarios import (
    carregar_csv_aneel,
    listar_distribuidoras,
    obter_tarifas_vigentes,
)
from src.logica_calculadora import LogicaCalculadora
from src.grafico import criar_grafico_economia
from src.relatorio_pdf import gerar_relatorio
from src.formatacao import formatar_moeda, formatar_percentual

st.set_page_config(page_title="Multi Unitário", page_icon="⚡", layout="wide")
st.title("📋 Processamento Multi Unitário")
st.markdown("Processe várias unidades consumidoras de uma vez via upload de planilha Excel.")

# ---------------------------------------------------------------------------
# Template generation
# ---------------------------------------------------------------------------
TEMPLATE_COLUMNS = [
    "Nome",
    "Distribuidora",
    "SubGrupo",
    "Modalidade",
    "Demanda HP (kW)",
    "Demanda HFP (kW)",
    "Consumo HP (kWh)",
    "Consumo HFP (kWh)",
    "ICMS (%)",
    "PIS/COFINS (%)",
    "Tipo Energia",
    "Tipo ICMS",
    "CCEE (R$/MWh)",
    "Mes Inicio",
    "Ano Inicio",
    "Mes Fim",
    "Ano Fim",
    "Taxa VPL (%)",
    "Tipo Oferta",
    "Desconto (%) ou Precos",
]

EXEMPLO = {
    "Nome": "Unidade Exemplo",
    "Distribuidora": "CEMIG-D",
    "SubGrupo": "A4",
    "Modalidade": "Azul",
    "Demanda HP (kW)": 100,
    "Demanda HFP (kW)": 300,
    "Consumo HP (kWh)": 30000,
    "Consumo HFP (kWh)": 120000,
    "ICMS (%)": 18,
    "PIS/COFINS (%)": 6.5,
    "Tipo Energia": "Convencional (i1)",
    "Tipo ICMS": "Contribuinte - ICMS padrão",
    "CCEE (R$/MWh)": 0,
    "Mes Inicio": 1,
    "Ano Inicio": 2025,
    "Mes Fim": 12,
    "Ano Fim": 2027,
    "Taxa VPL (%)": 9.67,
    "Tipo Oferta": "Desconto Garantido",
    "Desconto (%) ou Precos": 20,
}


def gerar_template_excel() -> bytes:
    buf = BytesIO()
    df = pd.DataFrame([EXEMPLO], columns=TEMPLATE_COLUMNS)
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Unidades")
    return buf.getvalue()


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
        df_upload = pd.read_excel(arquivo, sheet_name="Unidades")
    except Exception:
        df_upload = pd.read_excel(arquivo)

    st.markdown(f"**{len(df_upload)} unidade(s) encontrada(s)**")
    st.dataframe(df_upload, hide_index=True, use_container_width=True)

    if st.button("⚡ Processar Todas as Unidades", use_container_width=True):
        df_tarifas = carregar_csv_aneel()
        resultados = []
        progress = st.progress(0, text="Processando...")

        for idx, row in df_upload.iterrows():
            progress.progress(
                (idx + 1) / len(df_upload),
                text=f"Processando unidade {idx + 1}/{len(df_upload)}: {row.get('Nome', '')}",
            )

            try:
                dist = str(row["Distribuidora"])
                sg = str(row["SubGrupo"])
                mod = str(row["Modalidade"])
                tarifas = obter_tarifas_vigentes(df_tarifas, dist, sg, mod)

                # Parse offer
                tipo_oferta = str(row.get("Tipo Oferta", "Desconto Garantido"))
                desc_ou_preco = row.get("Desconto (%) ou Precos", 20)

                desconto_dg = None
                precos_pd = None
                if tipo_oferta == "Desconto Garantido":
                    desconto_dg = float(desc_ou_preco)
                else:
                    if isinstance(desc_ou_preco, str):
                        precos_pd = [float(p.strip()) for p in desc_ou_preco.split(",") if p.strip()]
                    else:
                        precos_pd = [float(desc_ou_preco)]

                params = ParametrosSimulacao(
                    consumo=DadosConsumo(
                        demanda_hp_kw=float(row["Demanda HP (kW)"]),
                        demanda_hfp_kw=float(row["Demanda HFP (kW)"]),
                        consumo_hp_kwh=float(row["Consumo HP (kWh)"]),
                        consumo_hfp_kwh=float(row["Consumo HFP (kWh)"]),
                    ),
                    tributarios=DadosTributarios(
                        aliquota_icms=float(row.get("ICMS (%)", 18)),
                        aliquota_pis_cofins=float(row.get("PIS/COFINS (%)", 6.5)),
                        tipo_energia=str(row.get("Tipo Energia", "Convencional (i1)")),
                        despesas_ccee=float(row.get("CCEE (R$/MWh)", 0)),
                        tipo_icms=str(row.get("Tipo ICMS", "Contribuinte - ICMS padrão")),
                    ),
                    contrato=DadosContrato(
                        mes_inicio=int(row.get("Mes Inicio", 1)),
                        ano_inicio=int(row.get("Ano Inicio", 2025)),
                        mes_fim=int(row.get("Mes Fim", 12)),
                        ano_fim=int(row.get("Ano Fim", 2027)),
                        taxa_vpl=float(row.get("Taxa VPL (%)", 9.67)),
                    ),
                    oferta=DadosOferta(
                        tipo_oferta=tipo_oferta,
                        desconto_garantido=desconto_dg,
                        precos_por_ano=precos_pd,
                    ),
                    cliente=DadosCliente(nome=str(row.get("Nome", ""))),
                    distribuidora=dist,
                    subgrupo=sg,
                    modalidade=mod,
                    tarifas=tarifas,
                )

                res = LogicaCalculadora(params).calcular()
                resultados.append({
                    "Nome": row.get("Nome", f"Unidade {idx + 1}"),
                    "Distribuidora": dist,
                    "Desconto": res["desconto_geral"],
                    "Economia Total": res["economia_total"],
                    "Economia VPL": res["economia_vpl"],
                    "_resultado": res,
                    "_params": params,
                })
            except Exception as e:
                resultados.append({
                    "Nome": row.get("Nome", f"Unidade {idx + 1}"),
                    "Distribuidora": row.get("Distribuidora", ""),
                    "Desconto": 0,
                    "Economia Total": 0,
                    "Economia VPL": 0,
                    "_erro": str(e),
                })

        progress.progress(1.0, text="Concluído!")

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
            for r in resultados
        ])
        st.dataframe(df_res, hide_index=True, use_container_width=True)

        # Totals
        total_economia = sum(r["Economia Total"] for r in resultados)
        total_vpl = sum(r["Economia VPL"] for r in resultados)
        tc1, tc2 = st.columns(2)
        tc1.metric("Economia Total Consolidada", formatar_moeda(total_economia))
        tc2.metric("Economia VPL Consolidada", formatar_moeda(total_vpl))

        # Consolidated chart
        valid_results = [r for r in resultados if "_resultado" in r]
        if valid_results:
            # Sum annual data across all units
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
            for r in resultados
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
        erros = [r for r in resultados if "_erro" in r]
        if erros:
            st.warning(f"{len(erros)} unidade(s) com erro:")
            for r in erros:
                st.error(f"**{r['Nome']}**: {r['_erro']}")
