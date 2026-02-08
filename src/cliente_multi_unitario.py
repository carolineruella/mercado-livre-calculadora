import pandas as pd
from io import BytesIO
from pydantic import ValidationError

from src.constantes import TIPO_ENERGIA, TIPO_ICMS
from src.models import (
    DadosConsumo,
    DadosContrato,
    DadosOferta,
    DadosTributarios,
    DadosCliente,
    ParametrosSimulacao,
)
from src.dados_tarifarios import obter_tarifas_vigentes
from src.logica_calculadora import LogicaCalculadora
from src.relatorio_pdf import gerar_relatorio
from src.grafico import criar_grafico_economia

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
    """Template with headers + 1 example row. Returns .xlsx bytes."""
    buf = BytesIO()
    df = pd.DataFrame([EXEMPLO], columns=TEMPLATE_COLUMNS)
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Unidades")
    return buf.getvalue()


def _parse_oferta(row: pd.Series) -> tuple:
    """Parse offer type and values from a spreadsheet row.

    Returns (tipo_oferta, desconto_dg, precos_pd).
    """
    tipo_oferta = str(row.get("Tipo Oferta", "Desconto Garantido"))
    desc_ou_preco = row.get("Desconto (%) ou Precos", 20)

    desconto_dg = None
    precos_pd = None

    if tipo_oferta == "Desconto Garantido":
        desconto_dg = float(desc_ou_preco)
    else:
        if isinstance(desc_ou_preco, str):
            precos_pd = [
                float(p.strip()) for p in desc_ou_preco.split(",") if p.strip()
            ]
        else:
            precos_pd = [float(desc_ou_preco)]

    return tipo_oferta, desconto_dg, precos_pd


def _build_params_from_row(
    row: pd.Series, df_tarifas: pd.DataFrame
) -> ParametrosSimulacao:
    """Build ParametrosSimulacao from a spreadsheet row.

    Raises ValidationError with Portuguese-friendly context on invalid data.
    """
    dist = str(row["Distribuidora"])
    sg = str(row["SubGrupo"])
    mod = str(row["Modalidade"])

    tarifas = obter_tarifas_vigentes(df_tarifas, dist, sg, mod)
    if tarifas.tusd_kw_fp == 0.0 and tarifas.te_fp == 0.0:
        raise ValueError(
            f"Tarifas não encontradas para {dist} / {sg} / {mod}. "
            "Verifique se a distribuidora, subgrupo e modalidade estão corretos."
        )

    tipo_oferta, desconto_dg, precos_pd = _parse_oferta(row)

    tipo_energia = str(row.get("Tipo Energia", "Convencional (i1)"))
    if tipo_energia not in TIPO_ENERGIA:
        raise ValueError(
            f"Tipo de energia inválido: '{tipo_energia}'. "
            f"Valores aceitos: {', '.join(TIPO_ENERGIA.keys())}"
        )

    tipo_icms = str(row.get("Tipo ICMS", "Contribuinte - ICMS padrão"))
    if tipo_icms not in TIPO_ICMS:
        raise ValueError(
            f"Tipo de ICMS inválido: '{tipo_icms}'. "
            f"Valores aceitos: {', '.join(TIPO_ICMS.keys())}"
        )

    return ParametrosSimulacao(
        consumo=DadosConsumo(
            demanda_hp_kw=float(row["Demanda HP (kW)"]),
            demanda_hfp_kw=float(row["Demanda HFP (kW)"]),
            consumo_hp_kwh=float(row["Consumo HP (kWh)"]),
            consumo_hfp_kwh=float(row["Consumo HFP (kWh)"]),
        ),
        tributarios=DadosTributarios(
            aliquota_icms=float(row.get("ICMS (%)", 18)),
            aliquota_pis_cofins=float(row.get("PIS/COFINS (%)", 6.5)),
            tipo_energia=tipo_energia,
            despesas_ccee=float(row.get("CCEE (R$/MWh)", 0)),
            tipo_icms=tipo_icms,
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


def _traduzir_erro_validacao(e: ValidationError) -> str:
    """Convert Pydantic ValidationError to a Portuguese message."""
    mensagens = []
    for err in e.errors():
        campo = " > ".join(str(loc) for loc in err["loc"])
        tipo = err["type"]
        if "greater_than_equal" in tipo:
            mensagens.append(f"Campo '{campo}': valor deve ser >= {err.get('ctx', {}).get('ge', 0)}")
        elif "less_than_equal" in tipo:
            mensagens.append(f"Campo '{campo}': valor deve ser <= {err.get('ctx', {}).get('le', 0)}")
        elif "missing" in tipo:
            mensagens.append(f"Campo '{campo}': obrigatório, mas não foi preenchido")
        else:
            mensagens.append(f"Campo '{campo}': {err['msg']}")
    return "; ".join(mensagens)


def processar_multi_unitario(
    arquivo: bytes, df_tarifas: pd.DataFrame, progress_callback=None
) -> dict:
    """Process each row: build params -> fetch tariffs -> calculate -> generate PDF.

    Args:
        arquivo: Excel file bytes.
        df_tarifas: Pre-loaded ANEEL tariff DataFrame.
        progress_callback: Optional callable(progress_float, status_text).

    Returns:
        {'unidades': [...], 'consolidado': {...}}
        Each unit has keys: Nome, Distribuidora, Desconto, Economia Total,
        Economia VPL, _resultado, _params. On error: _erro replaces _resultado/_params.
    """
    try:
        df_upload = pd.read_excel(BytesIO(arquivo), sheet_name="Unidades")
    except Exception:
        df_upload = pd.read_excel(BytesIO(arquivo))

    total = len(df_upload)
    if total == 0:
        return {"unidades": [], "consolidado": {"total_economia": 0, "total_vpl": 0}}

    resultados = []

    for idx, row in df_upload.iterrows():
        if progress_callback:
            nome_unidade = row.get("Nome", f"Unidade {idx + 1}")
            progress_callback(
                (idx + 1) / total,
                f"Processando unidade {idx + 1}/{total}: {nome_unidade}",
            )

        try:
            params = _build_params_from_row(row, df_tarifas)
            res = LogicaCalculadora(params).calcular()

            resultados.append({
                "Nome": row.get("Nome", f"Unidade {idx + 1}"),
                "Distribuidora": str(row.get("Distribuidora", "")),
                "Desconto": res["desconto_geral"],
                "Economia Total": res["economia_total"],
                "Economia VPL": res["economia_vpl"],
                "_resultado": res,
                "_params": params,
            })
        except ValidationError as e:
            resultados.append({
                "Nome": row.get("Nome", f"Unidade {idx + 1}"),
                "Distribuidora": str(row.get("Distribuidora", "")),
                "Desconto": 0,
                "Economia Total": 0,
                "Economia VPL": 0,
                "_erro": _traduzir_erro_validacao(e),
            })
        except Exception as e:
            resultados.append({
                "Nome": row.get("Nome", f"Unidade {idx + 1}"),
                "Distribuidora": str(row.get("Distribuidora", "")),
                "Desconto": 0,
                "Economia Total": 0,
                "Economia VPL": 0,
                "_erro": str(e),
            })

    total_economia = sum(r["Economia Total"] for r in resultados)
    total_vpl = sum(r["Economia VPL"] for r in resultados)

    return {
        "unidades": resultados,
        "consolidado": {
            "total_economia": total_economia,
            "total_vpl": total_vpl,
        },
    }
