import plotly.graph_objects as go
from src.formatacao import formatar_moeda


def criar_grafico_economia(gastos_acl: list, economias: list, anos: list) -> go.Figure:
    """Stacked bars: ACL cost (dark green) + savings (light green).

    Hover with R$ values, Y-axis currency format, bar labels.
    """
    fig = go.Figure()

    fig.add_trace(go.Bar(
        name="Custo ACL",
        x=anos,
        y=gastos_acl,
        marker_color="#148c73",
        text=[formatar_moeda(v) for v in gastos_acl],
        textposition="inside",
        hovertemplate="Custo ACL: %{customdata}<extra></extra>",
        customdata=[formatar_moeda(v) for v in gastos_acl],
    ))

    fig.add_trace(go.Bar(
        name="Economia",
        x=anos,
        y=economias,
        marker_color="#80c739",
        text=[formatar_moeda(v) for v in economias],
        textposition="inside",
        hovertemplate="Economia: %{customdata}<extra></extra>",
        customdata=[formatar_moeda(v) for v in economias],
    ))

    fig.update_layout(
        barmode="stack",
        title="Gastos ACL e Economia por Ano",
        xaxis_title="Ano",
        yaxis_title="R$",
        yaxis_tickprefix="R$ ",
        yaxis_tickformat=",.0f",
        yaxis_separatethousands=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        plot_bgcolor="white",
        height=450,
    )

    return fig


def criar_grafico_desconto_mensal(resultados_mensais: list) -> go.Figure:
    """Line chart: discount % over contract months. Filled area."""
    periodos = [r["periodo"] for r in resultados_mensais]
    descontos = [r["desconto"] * 100 for r in resultados_mensais]

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=periodos,
        y=descontos,
        mode="lines+markers",
        fill="tozeroy",
        line=dict(color="#148c73", width=2),
        marker=dict(size=4),
        hovertemplate="Período: %{x}<br>Desconto: %{y:.2f}%<extra></extra>",
    ))

    fig.update_layout(
        title="Evolução do Desconto Mensal",
        xaxis_title="Período",
        yaxis_title="Desconto (%)",
        yaxis_ticksuffix="%",
        plot_bgcolor="white",
        height=400,
    )

    # Show a subset of x-axis labels to avoid clutter
    if len(periodos) > 24:
        tick_step = max(1, len(periodos) // 12)
        fig.update_xaxes(
            tickmode="array",
            tickvals=periodos[::tick_step],
            ticktext=periodos[::tick_step],
        )

    return fig


def criar_grafico_composicao(acr_components: dict) -> go.Figure:
    """Donut chart: ACR cost breakdown.

    Expected keys: fio, fio_pis, fio_icms, energia, energia_pis, energia_icms
    """
    labels = [
        "TUSD (Fio)",
        "PIS/COFINS (Fio)",
        "ICMS (Fio)",
        "TE (Energia)",
        "PIS/COFINS (Energia)",
        "ICMS (Energia)",
    ]
    values = [
        acr_components.get("fio", 0),
        acr_components.get("fio_pis", 0),
        acr_components.get("fio_icms", 0),
        acr_components.get("energia", 0),
        acr_components.get("energia_pis", 0),
        acr_components.get("energia_icms", 0),
    ]

    colors = ["#148c73", "#1aad8e", "#20c9a5", "#80c739", "#a3d96b", "#c4ea9c"]

    fig = go.Figure(go.Pie(
        labels=labels,
        values=values,
        hole=0.4,
        marker=dict(colors=colors),
        textinfo="label+percent",
        hovertemplate="%{label}: %{customdata}<br>%{percent}<extra></extra>",
        customdata=[formatar_moeda(v) for v in values],
    ))

    fig.update_layout(
        title="Composição do Custo ACR (R$/MWh)",
        height=450,
    )

    return fig


def criar_grafico_comparativo(resultado_a: dict, resultado_b: dict,
                               label_a: str, label_b: str) -> go.Figure:
    """Grouped bars comparing two scenarios side by side."""
    categorias = ["Custo ACR Total", "Custo ACL Total", "Economia Total", "Economia VPL"]

    valores_a = [
        sum(resultado_a.get("gastos_acr_anual", [])),
        sum(resultado_a.get("gastos_acl_anual", [])),
        resultado_a.get("economia_total", 0),
        resultado_a.get("economia_vpl", 0),
    ]

    valores_b = [
        sum(resultado_b.get("gastos_acr_anual", [])),
        sum(resultado_b.get("gastos_acl_anual", [])),
        resultado_b.get("economia_total", 0),
        resultado_b.get("economia_vpl", 0),
    ]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        name=label_a,
        x=categorias,
        y=valores_a,
        marker_color="#148c73",
        text=[formatar_moeda(v) for v in valores_a],
        textposition="outside",
        hovertemplate="%{x}: %{customdata}<extra></extra>",
        customdata=[formatar_moeda(v) for v in valores_a],
    ))

    fig.add_trace(go.Bar(
        name=label_b,
        x=categorias,
        y=valores_b,
        marker_color="#80c739",
        text=[formatar_moeda(v) for v in valores_b],
        textposition="outside",
        hovertemplate="%{x}: %{customdata}<extra></extra>",
        customdata=[formatar_moeda(v) for v in valores_b],
    ))

    fig.update_layout(
        barmode="group",
        title="Comparativo de Cenários",
        yaxis_title="R$",
        yaxis_tickprefix="R$ ",
        yaxis_tickformat=",.0f",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        plot_bgcolor="white",
        height=500,
    )

    return fig
