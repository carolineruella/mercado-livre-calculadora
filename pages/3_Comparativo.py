import streamlit as st
import pandas as pd

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
from src.grafico import criar_grafico_comparativo
from src.formatacao import formatar_moeda, formatar_percentual

st.set_page_config(page_title="Comparativo", page_icon="⚡", layout="wide")
st.title("🔀 Comparativo de Cenários")
st.markdown("Compare dois cenários lado a lado para avaliar diferentes condições de contrato.")

df_tarifas = carregar_csv_aneel()
distribuidoras = listar_distribuidoras(df_tarifas)


def render_form(key_prefix: str, label: str):
    """Render a scenario form and return the parameters dict."""
    st.markdown(f"### {label}")

    distribuidora = st.selectbox("Distribuidora", distribuidoras, key=f"{key_prefix}_dist")
    subgrupos = listar_subgrupos(df_tarifas, distribuidora)
    subgrupo = st.selectbox("SubGrupo", subgrupos, key=f"{key_prefix}_sg")
    modalidades = listar_modalidades(df_tarifas, distribuidora, subgrupo)
    modalidade = st.selectbox("Modalidade", modalidades, key=f"{key_prefix}_mod")

    tarifas = obter_tarifas_vigentes(df_tarifas, distribuidora, subgrupo, modalidade)

    c1, c2 = st.columns(2)
    with c1:
        demanda_hp = st.number_input("Demanda HP (kW)", min_value=0.0, value=100.0, step=10.0, key=f"{key_prefix}_dhp")
        consumo_hp = st.number_input("Consumo HP (kWh)", min_value=0.0, value=30000.0, step=1000.0, key=f"{key_prefix}_chp")
    with c2:
        demanda_hfp = st.number_input("Demanda HFP (kW)", min_value=0.0, value=300.0, step=10.0, key=f"{key_prefix}_dhfp")
        consumo_hfp = st.number_input("Consumo HFP (kWh)", min_value=0.0, value=120000.0, step=1000.0, key=f"{key_prefix}_chfp")

    tc1, tc2 = st.columns(2)
    with tc1:
        aliq_icms = st.number_input("ICMS (%)", min_value=0.0, max_value=35.0, value=18.0, step=0.5, key=f"{key_prefix}_icms")
        tipo_energia = st.selectbox("Tipo Energia", list(TIPO_ENERGIA.keys()), key=f"{key_prefix}_te")
    with tc2:
        aliq_pis = st.number_input("PIS/COFINS (%)", min_value=0.0, max_value=15.0, value=6.5, step=0.5, key=f"{key_prefix}_pis")
        tipo_icms = st.selectbox("Tipo ICMS", list(TIPO_ICMS.keys()), key=f"{key_prefix}_ticms")

    ccee = st.number_input("CCEE (R$/MWh)", min_value=0.0, value=0.0, step=0.5, key=f"{key_prefix}_ccee")

    pc1, pc2 = st.columns(2)
    with pc1:
        mes_inicio = st.selectbox("Mês Início", list(range(1, 13)),
                                  format_func=lambda m: MESES_PT[m - 1], key=f"{key_prefix}_mi")
        ano_inicio = st.selectbox("Ano Início", list(range(2024, 2036)), index=1, key=f"{key_prefix}_ai")
    with pc2:
        mes_fim = st.selectbox("Mês Fim", list(range(1, 13)), index=11,
                               format_func=lambda m: MESES_PT[m - 1], key=f"{key_prefix}_mf")
        ano_fim = st.selectbox("Ano Fim", list(range(2024, 2036)), index=3, key=f"{key_prefix}_af")

    taxa_vpl = st.number_input("Taxa VPL (% a.a.)", min_value=0.0, max_value=100.0, value=9.67, step=0.5, key=f"{key_prefix}_vpl")

    tipo_oferta_label = st.radio("Tipo de Oferta", ["Desconto Garantido", "Preço Determinado"], key=f"{key_prefix}_to")

    desconto_dg = None
    precos_pd = None
    if tipo_oferta_label == "Desconto Garantido":
        desconto_dg = st.slider("Desconto (%)", min_value=0, max_value=50, value=20, key=f"{key_prefix}_dg")
    else:
        precos_pd_str = st.text_input("Preços por ano (R$/MWh)", value="200,210,220", key=f"{key_prefix}_pd")
        try:
            precos_pd = [float(p.strip()) for p in precos_pd_str.split(",") if p.strip()]
        except ValueError:
            precos_pd = []

    return {
        "distribuidora": distribuidora,
        "subgrupo": subgrupo,
        "modalidade": modalidade,
        "tarifas": tarifas,
        "demanda_hp": demanda_hp,
        "demanda_hfp": demanda_hfp,
        "consumo_hp": consumo_hp,
        "consumo_hfp": consumo_hfp,
        "aliq_icms": aliq_icms,
        "aliq_pis": aliq_pis,
        "tipo_energia": tipo_energia,
        "tipo_icms": tipo_icms,
        "ccee": ccee,
        "mes_inicio": mes_inicio,
        "ano_inicio": ano_inicio,
        "mes_fim": mes_fim,
        "ano_fim": ano_fim,
        "taxa_vpl": taxa_vpl,
        "tipo_oferta": tipo_oferta_label,
        "desconto_dg": desconto_dg,
        "precos_pd": precos_pd,
    }


def build_params(d: dict) -> ParametrosSimulacao:
    return ParametrosSimulacao(
        consumo=DadosConsumo(
            demanda_hp_kw=d["demanda_hp"],
            demanda_hfp_kw=d["demanda_hfp"],
            consumo_hp_kwh=d["consumo_hp"],
            consumo_hfp_kwh=d["consumo_hfp"],
        ),
        tributarios=DadosTributarios(
            aliquota_icms=d["aliq_icms"],
            aliquota_pis_cofins=d["aliq_pis"],
            tipo_energia=d["tipo_energia"],
            despesas_ccee=d["ccee"],
            tipo_icms=d["tipo_icms"],
        ),
        contrato=DadosContrato(
            mes_inicio=d["mes_inicio"],
            ano_inicio=d["ano_inicio"],
            mes_fim=d["mes_fim"],
            ano_fim=d["ano_fim"],
            taxa_vpl=d["taxa_vpl"],
        ),
        oferta=DadosOferta(
            tipo_oferta=d["tipo_oferta"],
            desconto_garantido=d["desconto_dg"],
            precos_por_ano=d["precos_pd"],
        ),
        cliente=DadosCliente(),
        distribuidora=d["distribuidora"],
        subgrupo=d["subgrupo"],
        modalidade=d["modalidade"],
        tarifas=d["tarifas"],
    )


# ---------------------------------------------------------------------------
# Two side-by-side forms
# ---------------------------------------------------------------------------
col_a, col_b = st.columns(2)

with col_a:
    dados_a = render_form("a", "Cenário A")

with col_b:
    dados_b = render_form("b", "Cenário B")

st.divider()

if st.button("🔀 Comparar Cenários", use_container_width=True):
    try:
        params_a = build_params(dados_a)
        params_b = build_params(dados_b)

        resultado_a = LogicaCalculadora(params_a).calcular()
        resultado_b = LogicaCalculadora(params_b).calcular()

        label_a = f"Cenário A ({dados_a['distribuidora']} - {dados_a['tipo_oferta']})"
        label_b = f"Cenário B ({dados_b['distribuidora']} - {dados_b['tipo_oferta']})"

        # --- Delta metrics ---
        st.subheader("Comparação")
        mc1, mc2, mc3 = st.columns(3)

        mc1.metric(
            "Desconto A vs B",
            formatar_percentual(resultado_a["desconto_geral"]),
            delta=f"{(resultado_a['desconto_geral'] - resultado_b['desconto_geral']) * 100:+.2f} p.p.",
        )
        mc2.metric(
            "Economia Total A",
            formatar_moeda(resultado_a["economia_total"]),
            delta=formatar_moeda(resultado_a["economia_total"] - resultado_b["economia_total"]),
        )
        mc3.metric(
            "Economia VPL A",
            formatar_moeda(resultado_a["economia_vpl"]),
            delta=formatar_moeda(resultado_a["economia_vpl"] - resultado_b["economia_vpl"]),
        )

        # --- Grouped bar chart ---
        fig_comp = criar_grafico_comparativo(resultado_a, resultado_b, label_a, label_b)
        st.plotly_chart(fig_comp, use_container_width=True)

        # --- Difference table ---
        st.subheader("Detalhamento")
        diff_data = {
            "Métrica": ["Desconto Médio", "Economia Total", "Economia VPL", "Custo ACR Total", "Custo ACL Total"],
            label_a: [
                formatar_percentual(resultado_a["desconto_geral"]),
                formatar_moeda(resultado_a["economia_total"]),
                formatar_moeda(resultado_a["economia_vpl"]),
                formatar_moeda(sum(resultado_a["gastos_acr_anual"])),
                formatar_moeda(sum(resultado_a["gastos_acl_anual"])),
            ],
            label_b: [
                formatar_percentual(resultado_b["desconto_geral"]),
                formatar_moeda(resultado_b["economia_total"]),
                formatar_moeda(resultado_b["economia_vpl"]),
                formatar_moeda(sum(resultado_b["gastos_acr_anual"])),
                formatar_moeda(sum(resultado_b["gastos_acl_anual"])),
            ],
        }
        st.dataframe(pd.DataFrame(diff_data), hide_index=True, use_container_width=True)

    except Exception as e:
        st.error(f"Erro ao comparar cenários: {e}")
