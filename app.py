import streamlit as st

st.set_page_config(
    page_title="Simulador ML Energia",
    page_icon="⚡",
    layout="wide",
)

st.title("⚡ Simulador Mercado Livre de Energia")

st.markdown(
    """
    Simule a economia ao migrar do mercado regulado (ACR/Cativo) para o
    mercado livre de energia (ACL). Utilize dados reais de tarifas homologadas
    pela ANEEL para calcular descontos, economia e gerar relatórios profissionais.
    """
)

st.divider()

# Market overview metrics
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        label="Distribuidoras Disponíveis",
        value="116+",
        help="Distribuidoras reais com tarifas homologadas pela ANEEL",
    )

with col2:
    st.metric(
        label="Economia Típica",
        value="10–40%",
        help="Faixa de desconto comum para consumidores do Grupo A no mercado livre",
    )

with col3:
    st.metric(
        label="Dados Tarifários",
        value="309 mil+",
        help="Registros de tarifas homologadas no banco de dados ANEEL",
    )

st.divider()

st.subheader("Páginas do Simulador")

st.markdown(
    """
    - **Simulador** — Selecione distribuidora, subgrupo e modalidade, preencha
      os dados de consumo e obtenha o cálculo completo de economia com gráficos
      interativos e relatório PDF.
    - **Multi Unitário** — Processe várias unidades consumidoras de uma vez via
      upload de planilha Excel, com resultados consolidados.
    - **Comparativo** — Compare dois cenários lado a lado (ex: Desconto Garantido
      vs Preço Determinado ou distribuidoras diferentes).
    """
)
