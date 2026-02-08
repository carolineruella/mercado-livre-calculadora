import streamlit as st
import pandas as pd
from io import BytesIO
from pydantic import ValidationError

from src.constantes import TIPO_ENERGIA, TIPO_ICMS, MESES_PT
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
    listar_subgrupos,
    listar_modalidades,
    obter_tarifas_vigentes,
)
from src.logica_calculadora import LogicaCalculadora
from src.grafico import (
    criar_grafico_economia,
    criar_grafico_desconto_mensal,
    criar_grafico_composicao,
)
from src.relatorio_pdf import gerar_relatorio
from src.formatacao import formatar_moeda, formatar_percentual

st.set_page_config(page_title="Simulador", page_icon="⚡", layout="wide")
st.title("⚡ Simulador de Economia")

# ---------------------------------------------------------------------------
# Load tariff data (cached)
# ---------------------------------------------------------------------------
df_tarifas = carregar_csv_aneel()
distribuidoras = listar_distribuidoras(df_tarifas)

# ---------------------------------------------------------------------------
# Helper: translate Pydantic validation errors to Portuguese
# ---------------------------------------------------------------------------
_FIELD_LABELS = {
    "demanda_hp_kw": "Demanda HP (kW)",
    "demanda_hfp_kw": "Demanda HFP (kW)",
    "consumo_hp_kwh": "Consumo HP (kWh)",
    "consumo_hfp_kwh": "Consumo HFP (kWh)",
    "aliquota_icms": "ICMS (%)",
    "aliquota_pis_cofins": "PIS/COFINS (%)",
    "despesas_ccee": "Despesas CCEE",
    "mes_inicio": "Mês Início",
    "ano_inicio": "Ano Início",
    "mes_fim": "Mês Fim",
    "ano_fim": "Ano Fim",
    "taxa_vpl": "Taxa VPL (%)",
    "desconto_garantido": "Desconto Garantido (%)",
}


def _traduzir_erro_validacao(e: ValidationError) -> str:
    mensagens = []
    for err in e.errors():
        campo_raw = " > ".join(str(loc) for loc in err["loc"])
        campo = _FIELD_LABELS.get(err["loc"][-1], campo_raw) if err["loc"] else campo_raw
        tipo = err["type"]
        if "greater_than_equal" in tipo:
            limite = err.get("ctx", {}).get("ge", 0)
            mensagens.append(f"**{campo}**: valor deve ser maior ou igual a {limite}")
        elif "less_than_equal" in tipo:
            limite = err.get("ctx", {}).get("le", 0)
            mensagens.append(f"**{campo}**: valor deve ser menor ou igual a {limite}")
        elif "missing" in tipo:
            mensagens.append(f"**{campo}**: campo obrigatório não preenchido")
        else:
            mensagens.append(f"**{campo}**: {err['msg']}")
    return "  \n".join(mensagens)


# ---------------------------------------------------------------------------
# Layout: Form (left) | Results (right)
# ---------------------------------------------------------------------------
col_form, col_result = st.columns([1, 1.4])

with col_form:
    with st.form("form_simulador"):
        st.subheader("Dados da Simulação")

        # --- Distributor / Subgroup / Modality (cascading) ---
        distribuidora = st.selectbox("Distribuidora", distribuidoras)

        subgrupos = listar_subgrupos(df_tarifas, distribuidora)
        subgrupo = st.selectbox("SubGrupo", subgrupos)

        modalidades = listar_modalidades(df_tarifas, distribuidora, subgrupo)
        modalidade = st.selectbox("Modalidade", modalidades)

        # --- Auto-loaded tariffs (read-only info) ---
        tarifas = obter_tarifas_vigentes(df_tarifas, distribuidora, subgrupo, modalidade)

        if tarifas.tusd_kw_fp == 0.0 and tarifas.te_fp == 0.0:
            st.warning(
                f"Tarifas não encontradas para {distribuidora} / {subgrupo} / {modalidade}. "
                "Os valores podem estar incompletos no banco de dados ANEEL."
            )
        else:
            st.info(
                f"**Tarifas vigentes ({tarifas.vigencia}):**  \n"
                f"TUSD kW FP: {tarifas.tusd_kw_fp:.2f} | "
                f"TUSD kW P: {tarifas.tusd_kw_p:.2f} | "
                f"TUSD MWh FP: {tarifas.tusd_mwh_fp:.2f} | "
                f"TUSD MWh P: {tarifas.tusd_mwh_p:.2f}  \n"
                f"TE FP: {tarifas.te_fp:.2f} | TE P: {tarifas.te_p:.2f}"
            )

        st.divider()

        # --- Consumption ---
        st.markdown("**Consumo e Demanda**")
        c1, c2 = st.columns(2)
        with c1:
            demanda_hp = st.number_input("Demanda HP (kW)", min_value=0.0, value=100.0, step=10.0)
            consumo_hp = st.number_input("Consumo HP (kWh)", min_value=0.0, value=30000.0, step=1000.0)
        with c2:
            demanda_hfp = st.number_input("Demanda HFP (kW)", min_value=0.0, value=300.0, step=10.0)
            consumo_hfp = st.number_input("Consumo HFP (kWh)", min_value=0.0, value=120000.0, step=1000.0)

        st.divider()

        # --- Tax / Energy ---
        st.markdown("**Dados Tributários**")
        tc1, tc2 = st.columns(2)
        with tc1:
            aliq_icms = st.number_input("ICMS (%)", min_value=0.0, max_value=35.0, value=18.0, step=0.5)
            tipo_energia = st.selectbox("Tipo Energia", list(TIPO_ENERGIA.keys()))
        with tc2:
            aliq_pis = st.number_input("PIS/COFINS (%)", min_value=0.0, max_value=15.0, value=6.5, step=0.5)
            tipo_icms = st.selectbox("Tipo ICMS", list(TIPO_ICMS.keys()))

        ccee = st.number_input("Despesas CCEE (R$/MWh)", min_value=0.0, value=0.0, step=0.5)

        st.divider()

        # --- Contract Period ---
        st.markdown("**Período do Contrato**")
        pc1, pc2 = st.columns(2)
        with pc1:
            mes_inicio = st.selectbox("Mês Início", list(range(1, 13)),
                                      format_func=lambda m: MESES_PT[m - 1])
            ano_inicio = st.selectbox("Ano Início", list(range(2024, 2036)), index=1)
        with pc2:
            mes_fim = st.selectbox("Mês Fim", list(range(1, 13)), index=11,
                                   format_func=lambda m: MESES_PT[m - 1])
            ano_fim = st.selectbox("Ano Fim", list(range(2024, 2036)), index=3)

        taxa_vpl = st.number_input("Taxa VPL (% a.a.)", min_value=0.0, max_value=100.0, value=9.67, step=0.5)

        st.divider()

        # --- Offer ---
        st.markdown("**Oferta**")
        tipo_oferta_label = st.radio("Tipo de Oferta", ["Desconto Garantido", "Preço Determinado"])

        desconto_dg = None
        precos_pd = None

        if tipo_oferta_label == "Desconto Garantido":
            desconto_dg = st.slider("Desconto Garantido (%)", min_value=0, max_value=50, value=20)
        else:
            precos_pd_str = st.text_input(
                "Preços por ano (R$/MWh, separados por vírgula)",
                value="200,210,220",
            )
            try:
                precos_pd = [float(p.strip()) for p in precos_pd_str.split(",") if p.strip()]
            except ValueError:
                precos_pd = []

        st.divider()

        # --- Client info (optional) ---
        st.markdown("**Cliente (opcional)**")
        nome_cliente = st.text_input("Nome do Cliente")
        cnpj_cliente = st.text_input("CNPJ")

        # --- Submit ---
        submitted = st.form_submit_button("⚡ Calcular Economia", use_container_width=True)

# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

def _exibir_resultados(resultado, params, nome_cliente):
    """Display calculation results in the right column."""
    # --- Key metrics ---
    st.subheader("Resultados")
    m1, m2, m3 = st.columns(3)
    m1.metric("Desconto Médio", formatar_percentual(resultado["desconto_geral"]))
    m2.metric("Economia Total", formatar_moeda(resultado["economia_total"]))
    m3.metric("Economia VPL", formatar_moeda(resultado["economia_vpl"]))

    # --- Main chart ---
    fig_economia = criar_grafico_economia(
        resultado["gastos_acl_anual"],
        resultado["economias_anual"],
        resultado["anos"],
    )
    st.plotly_chart(fig_economia, use_container_width=True)

    # --- Tabs ---
    tab_anual, tab_mensal, tab_composicao = st.tabs(
        ["Resultados Anuais", "Evolução Mensal", "Composição Custo"]
    )

    with tab_anual:
        df_anual = pd.DataFrame(resultado["resultados_anuais"])
        df_display = df_anual.copy()
        df_display["gasto_acr"] = df_display["gasto_acr"].apply(formatar_moeda)
        df_display["gasto_acl"] = df_display["gasto_acl"].apply(formatar_moeda)
        df_display["economia"] = df_display["economia"].apply(formatar_moeda)
        df_display["desconto"] = df_display["desconto"].apply(formatar_percentual)
        df_display = df_display.rename(columns={
            "ano": "Ano",
            "gasto_acr": "Custo ACR",
            "gasto_acl": "Custo ACL",
            "economia": "Economia",
            "desconto": "Desconto",
        })
        st.dataframe(
            df_display[["Ano", "Custo ACR", "Custo ACL", "Economia", "Desconto"]],
            hide_index=True,
            use_container_width=True,
        )

    with tab_mensal:
        fig_mensal = criar_grafico_desconto_mensal(resultado["resultados_mensais"])
        st.plotly_chart(fig_mensal, use_container_width=True)

    with tab_composicao:
        if resultado["resultados_mensais"]:
            acr_comp = resultado["resultados_mensais"][0]["acr_detalhado"]
            fig_comp = criar_grafico_composicao(acr_comp)
            st.plotly_chart(fig_comp, use_container_width=True)

    # --- Downloads ---
    st.divider()
    dl1, dl2 = st.columns(2)

    with dl1:
        try:
            fig_png = fig_economia.to_image(format="png", width=800, height=400)
        except Exception:
            fig_png = b""

        try:
            pdf_bytes = gerar_relatorio(
                nome_cliente=nome_cliente,
                desconto=resultado["desconto_geral"],
                economia=resultado["economia_total"],
                periodo=resultado["periodo"],
                grafico_png=fig_png,
                resultados_anuais=resultado["resultados_anuais"],
            )
            st.download_button(
                "📄 Baixar Relatório PDF",
                data=pdf_bytes,
                file_name="relatorio_simulacao.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        except Exception:
            st.error("Erro ao gerar o relatório PDF. Tente novamente.")

    with dl2:
        df_csv = pd.DataFrame(resultado["resultados_mensais"])
        csv_cols = ["periodo", "custo_acr_mwh", "custo_acl_mwh", "desconto", "economia", "gasto_acr", "gasto_acl"]
        csv_bytes = df_csv[csv_cols].to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
        st.download_button(
            "📊 Baixar Resultados CSV",
            data=csv_bytes,
            file_name="resultados_simulacao.csv",
            mime="text/csv",
            use_container_width=True,
        )


with col_result:
    if submitted:
        # Validate contract period
        if (ano_fim < ano_inicio) or (ano_fim == ano_inicio and mes_fim < mes_inicio):
            st.error("O período final do contrato deve ser posterior ao período inicial.")
        elif consumo_hp + consumo_hfp == 0:
            st.error("Informe ao menos um valor de consumo (HP ou HFP) maior que zero.")
        elif tipo_oferta_label == "Preço Determinado" and not precos_pd:
            st.error("Informe ao menos um preço por ano para a oferta de Preço Determinado.")
        else:
            try:
                params = ParametrosSimulacao(
                    consumo=DadosConsumo(
                        demanda_hp_kw=demanda_hp,
                        demanda_hfp_kw=demanda_hfp,
                        consumo_hp_kwh=consumo_hp,
                        consumo_hfp_kwh=consumo_hfp,
                    ),
                    tributarios=DadosTributarios(
                        aliquota_icms=aliq_icms,
                        aliquota_pis_cofins=aliq_pis,
                        tipo_energia=tipo_energia,
                        despesas_ccee=ccee,
                        tipo_icms=tipo_icms,
                    ),
                    contrato=DadosContrato(
                        mes_inicio=mes_inicio,
                        ano_inicio=ano_inicio,
                        mes_fim=mes_fim,
                        ano_fim=ano_fim,
                        taxa_vpl=taxa_vpl,
                    ),
                    oferta=DadosOferta(
                        tipo_oferta=tipo_oferta_label,
                        desconto_garantido=desconto_dg,
                        precos_por_ano=precos_pd,
                    ),
                    cliente=DadosCliente(nome=nome_cliente, cnpj=cnpj_cliente),
                    distribuidora=distribuidora,
                    subgrupo=subgrupo,
                    modalidade=modalidade,
                    tarifas=tarifas,
                )

                resultado = LogicaCalculadora(params).calcular()

                # Store in session state for persistence across reruns
                st.session_state["ultimo_resultado"] = resultado
                st.session_state["ultimo_params"] = params
                st.session_state["ultimo_nome_cliente"] = nome_cliente

                st.toast("Cálculo realizado com sucesso!", icon="✅")
                _exibir_resultados(resultado, params, nome_cliente)

            except ValidationError as e:
                st.error("Erro de validação nos dados informados:  \n" + _traduzir_erro_validacao(e))
            except ZeroDivisionError:
                st.error("Erro no cálculo: divisão por zero. Verifique os valores de consumo e tarifas informados.")
            except Exception as e:
                st.error(f"Erro ao calcular: {e}")

    elif "ultimo_resultado" in st.session_state:
        # Show last result when page reruns without new submission
        _exibir_resultados(
            st.session_state["ultimo_resultado"],
            st.session_state["ultimo_params"],
            st.session_state.get("ultimo_nome_cliente", ""),
        )
    else:
        st.info("Preencha os dados no formulário e clique em **Calcular Economia** para ver os resultados.")
