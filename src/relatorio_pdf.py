from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.lib.units import mm
from reportlab.platypus import Table, TableStyle

from src.formatacao import formatar_moeda, formatar_percentual


PAGE_W, PAGE_H = A4
VERDE_ESCURO = HexColor("#148c73")
VERDE_CLARO = HexColor("#80c739")
CINZA_CLARO = HexColor("#f0f2f6")
BRANCO = HexColor("#FFFFFF")
PRETO = HexColor("#262730")
MARGEM = 40


def gerar_relatorio(nome_cliente: str, desconto: float, economia: float,
                    periodo: list[str], grafico_png: bytes,
                    resultados_anuais: list[dict],
                    numero_unidade: int = 0) -> bytes:
    """Returns PDF bytes for st.download_button.

    Page 1 — Executive Summary
    Page 2 — Full Chart
    Page 3 — Annual Results Table
    """
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)

    _pagina_resumo(c, nome_cliente, desconto, economia, periodo, numero_unidade)
    c.showPage()

    _pagina_grafico(c, grafico_png)
    c.showPage()

    _pagina_tabela(c, resultados_anuais, desconto, economia)
    c.showPage()

    c.save()
    return buf.getvalue()


def _pagina_resumo(c: canvas.Canvas, nome_cliente: str, desconto: float,
                   economia: float, periodo: list[str], numero_unidade: int):
    """Page 1: Executive summary with key metrics."""
    # Header bar
    c.setFillColor(VERDE_ESCURO)
    c.rect(0, PAGE_H - 80, PAGE_W, 80, fill=1, stroke=0)

    c.setFillColor(BRANCO)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(MARGEM, PAGE_H - 50, "Simulador Mercado Livre de Energia")
    c.setFont("Helvetica", 11)
    c.drawString(MARGEM, PAGE_H - 70, "Relatório de Simulação de Economia")

    # Client info
    y = PAGE_H - 120
    c.setFillColor(PRETO)
    c.setFont("Helvetica-Bold", 14)
    if nome_cliente:
        c.drawString(MARGEM, y, f"Cliente: {nome_cliente}")
        y -= 25
    if numero_unidade > 0:
        c.drawString(MARGEM, y, f"Unidade: {numero_unidade}")
        y -= 25

    # Period
    c.setFont("Helvetica", 12)
    periodo_str = f"{periodo[0]} a {periodo[1]}" if len(periodo) >= 2 else ""
    c.drawString(MARGEM, y, f"Período: {periodo_str}")
    y -= 60

    # Main discount metric
    c.setFillColor(VERDE_ESCURO)
    c.setFont("Helvetica-Bold", 40)
    desconto_str = formatar_percentual(desconto)
    c.drawCentredString(PAGE_W / 2, y, desconto_str)
    y -= 25
    c.setFont("Helvetica", 14)
    c.drawCentredString(PAGE_W / 2, y, "Desconto Médio")
    y -= 60

    # Total savings
    c.setFillColor(PRETO)
    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(PAGE_W / 2, y, formatar_moeda(economia))
    y -= 22
    c.setFont("Helvetica", 13)
    c.setFillColor(HexColor("#158d74"))
    c.drawCentredString(PAGE_W / 2, y, "Economia Total no Período")

    # Footer
    _rodape(c)


def _pagina_grafico(c: canvas.Canvas, grafico_png: bytes):
    """Page 2: Full chart image."""
    # Header
    c.setFillColor(VERDE_ESCURO)
    c.rect(0, PAGE_H - 60, PAGE_W, 60, fill=1, stroke=0)
    c.setFillColor(BRANCO)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(MARGEM, PAGE_H - 40, "Gastos ACL e Economia por Ano")

    if grafico_png and len(grafico_png) > 0:
        from reportlab.lib.utils import ImageReader
        img_buf = BytesIO(grafico_png)
        try:
            img = ImageReader(img_buf)
            # Center the chart: 140mm wide × 90mm tall
            img_w = 160 * mm
            img_h = 100 * mm
            x = (PAGE_W - img_w) / 2
            y = (PAGE_H - 60 - img_h) / 2
            c.drawImage(img, x, y, width=img_w, height=img_h,
                        preserveAspectRatio=True, anchor="c")
        except Exception:
            c.setFillColor(PRETO)
            c.setFont("Helvetica", 12)
            c.drawCentredString(PAGE_W / 2, PAGE_H / 2,
                                "Gráfico não disponível")
    else:
        c.setFillColor(PRETO)
        c.setFont("Helvetica", 12)
        c.drawCentredString(PAGE_W / 2, PAGE_H / 2,
                            "Gráfico não disponível")

    _rodape(c)


def _pagina_tabela(c: canvas.Canvas, resultados_anuais: list[dict],
                   desconto_geral: float, economia_total: float):
    """Page 3: Annual results table."""
    # Header
    c.setFillColor(VERDE_ESCURO)
    c.rect(0, PAGE_H - 60, PAGE_W, 60, fill=1, stroke=0)
    c.setFillColor(BRANCO)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(MARGEM, PAGE_H - 40, "Resultados Anuais")

    # Build table data
    headers = ["Ano", "Custo ACR", "Custo ACL", "Economia", "Desconto"]
    data = [headers]

    for r in resultados_anuais:
        data.append([
            str(r["ano"]),
            formatar_moeda(r["gasto_acr"]),
            formatar_moeda(r["gasto_acl"]),
            formatar_moeda(r["economia"]),
            formatar_percentual(r["desconto"]),
        ])

    # Totals row
    total_acr = sum(r["gasto_acr"] for r in resultados_anuais)
    total_acl = sum(r["gasto_acl"] for r in resultados_anuais)
    data.append([
        "TOTAL",
        formatar_moeda(total_acr),
        formatar_moeda(total_acl),
        formatar_moeda(economia_total),
        formatar_percentual(desconto_geral),
    ])

    col_widths = [60, 120, 120, 120, 80]
    table = Table(data, colWidths=col_widths)

    style = TableStyle([
        # Header row
        ("BACKGROUND", (0, 0), (-1, 0), VERDE_ESCURO),
        ("TEXTCOLOR", (0, 0), (-1, 0), BRANCO),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        # Data rows
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("ALIGN", (0, 1), (0, -1), "CENTER"),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        # Totals row (last)
        ("BACKGROUND", (0, -1), (-1, -1), CINZA_CLARO),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        # Alternating row colors
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [BRANCO, CINZA_CLARO]),
        # Grid
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#cccccc")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ])
    table.setStyle(style)

    # Position table
    table_w, table_h = table.wrap(0, 0)
    x = (PAGE_W - table_w) / 2
    y = PAGE_H - 90 - table_h
    table.drawOn(c, x, y)

    _rodape(c)


def _rodape(c: canvas.Canvas):
    """Draw footer on current page."""
    c.setFillColor(HexColor("#999999"))
    c.setFont("Helvetica", 8)
    c.drawCentredString(PAGE_W / 2, 20,
                        "Simulador Mercado Livre de Energia — Documento gerado automaticamente")
