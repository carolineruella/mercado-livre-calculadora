import pandas as pd
import streamlit as st
from src.formatacao import parse_valor_br
from src.models import TarifasVigentes
from src.constantes import SUBGRUPOS_GRUPO_A, MODALIDADES_RELEVANTES

CSV_PATH = "tarifas-homologadas-distribuidoras-energia-eletrica.csv"


@st.cache_data
def carregar_csv_aneel(caminho: str = CSV_PATH) -> pd.DataFrame:
    """Load and pre-filter the ANEEL CSV (~309K rows → ~28-31K after filtering).

    Read:  encoding='latin-1', sep=';'
    Filter:
        DscBaseTarifaria  contains 'Aplica'
        DscSubGrupo       in SUBGRUPOS_GRUPO_A
        DscModalidadeTarifaria in MODALIDADES_RELEVANTES
        DscClasse         contains 'aplica' (case-insensitive)
        DscDetalhe        contains 'aplica' (case-insensitive)
    Convert:
        VlrTUSD, VlrTE   → float via parse_valor_br
        DatInicioVigencia → pd.to_datetime
    """
    df = pd.read_csv(caminho, sep=";", encoding="latin-1")

    mask = (
        df["DscBaseTarifaria"].str.contains("Aplica", na=False)
        & df["DscSubGrupo"].isin(SUBGRUPOS_GRUPO_A)
        & df["DscModalidadeTarifaria"].isin(MODALIDADES_RELEVANTES)
        & df["DscClasse"].str.contains("aplica", case=False, na=False)
        & df["DscDetalhe"].str.contains("aplica", case=False, na=False)
    )
    df = df[mask].copy()

    df["VlrTUSD"] = df["VlrTUSD"].apply(parse_valor_br)
    df["VlrTE"] = df["VlrTE"].apply(parse_valor_br)
    df["DatInicioVigencia"] = pd.to_datetime(df["DatInicioVigencia"], format="mixed")

    return df.reset_index(drop=True)


def listar_distribuidoras(df: pd.DataFrame) -> list[str]:
    """Sorted unique distributor names."""
    return sorted(df["SigAgente"].unique().tolist())


def listar_subgrupos(df: pd.DataFrame, distribuidora: str) -> list[str]:
    """Subgroups available for given distributor."""
    subset = df[df["SigAgente"] == distribuidora]
    return sorted(subset["DscSubGrupo"].unique().tolist())


def listar_modalidades(
    df: pd.DataFrame, distribuidora: str, subgrupo: str
) -> list[str]:
    """Modalities available for given distributor + subgroup."""
    subset = df[(df["SigAgente"] == distribuidora) & (df["DscSubGrupo"] == subgrupo)]
    return sorted(subset["DscModalidadeTarifaria"].unique().tolist())


def _extrair_valor(rows: pd.DataFrame, posto: str, unidade: str, coluna: str) -> float:
    """Extract a single tariff value matching posto and unit."""
    match = rows[
        (rows["NomPostoTarifario"] == posto)
        & (rows["DscUnidadeTerciaria"] == unidade)
    ]
    if match.empty:
        return 0.0
    return float(match[coluna].iloc[0])


def obter_tarifas_vigentes(
    df: pd.DataFrame, distribuidora: str, subgrupo: str, modalidade: str
) -> TarifasVigentes:
    """Extract most recent tariff values.

    1. Filter by distribuidora + subgrupo + modalidade
    2. Find max DatInicioVigencia
    3. From that vigência, extract tariff components by posto/unit.
       Azul: separate Ponta and Fora ponta demand (kW).
       Verde: demand uses 'Não se aplica' (kW), tusd_kw_p = 0.
       TE: prefers 'seca' variants, falls back to plain posto.
    """
    subset = df[
        (df["SigAgente"] == distribuidora)
        & (df["DscSubGrupo"] == subgrupo)
        & (df["DscModalidadeTarifaria"] == modalidade)
    ]

    if subset.empty:
        return TarifasVigentes()

    latest_date = subset["DatInicioVigencia"].max()
    rows = subset[subset["DatInicioVigencia"] == latest_date]

    is_verde = modalidade == "Verde"

    # TUSD kW
    if is_verde:
        tusd_kw_fp = _extrair_valor(rows, "Não se aplica", "kW", "VlrTUSD")
        tusd_kw_p = 0.0
    else:
        tusd_kw_fp = _extrair_valor(rows, "Fora ponta", "kW", "VlrTUSD")
        tusd_kw_p = _extrair_valor(rows, "Ponta", "kW", "VlrTUSD")

    # TUSD MWh
    tusd_mwh_fp = _extrair_valor(rows, "Fora ponta", "MWh", "VlrTUSD")
    tusd_mwh_p = _extrair_valor(rows, "Ponta", "MWh", "VlrTUSD")

    # TE MWh — prefer 'seca' variants, fallback to plain
    te_fp = _extrair_valor(rows, "Fora ponta seca", "MWh", "VlrTE")
    if te_fp == 0.0:
        te_fp = _extrair_valor(rows, "Fora ponta", "MWh", "VlrTE")

    te_p = _extrair_valor(rows, "Ponta seca", "MWh", "VlrTE")
    if te_p == 0.0:
        te_p = _extrair_valor(rows, "Ponta", "MWh", "VlrTE")

    vigencia_str = latest_date.strftime("%d/%m/%Y")

    return TarifasVigentes(
        tusd_kw_fp=tusd_kw_fp,
        tusd_kw_p=tusd_kw_p,
        tusd_mwh_fp=tusd_mwh_fp,
        tusd_mwh_p=tusd_mwh_p,
        te_fp=te_fp,
        te_p=te_p,
        vigencia=vigencia_str,
    )


def obter_historico_tarifas(
    df: pd.DataFrame, distribuidora: str, subgrupo: str, modalidade: str
) -> list[dict]:
    """Tariff snapshots ordered by vigência ascending.
    Each: {vigencia, tusd_kw_fp, tusd_kw_p, tusd_mwh_fp, tusd_mwh_p, te_fp, te_p}
    """
    subset = df[
        (df["SigAgente"] == distribuidora)
        & (df["DscSubGrupo"] == subgrupo)
        & (df["DscModalidadeTarifaria"] == modalidade)
    ]

    if subset.empty:
        return []

    is_verde = modalidade == "Verde"
    vigencias = sorted(subset["DatInicioVigencia"].unique())
    historico = []

    for vig in vigencias:
        rows = subset[subset["DatInicioVigencia"] == vig]

        if is_verde:
            tusd_kw_fp = _extrair_valor(rows, "Não se aplica", "kW", "VlrTUSD")
            tusd_kw_p = 0.0
        else:
            tusd_kw_fp = _extrair_valor(rows, "Fora ponta", "kW", "VlrTUSD")
            tusd_kw_p = _extrair_valor(rows, "Ponta", "kW", "VlrTUSD")

        tusd_mwh_fp = _extrair_valor(rows, "Fora ponta", "MWh", "VlrTUSD")
        tusd_mwh_p = _extrair_valor(rows, "Ponta", "MWh", "VlrTUSD")

        te_fp = _extrair_valor(rows, "Fora ponta seca", "MWh", "VlrTE")
        if te_fp == 0.0:
            te_fp = _extrair_valor(rows, "Fora ponta", "MWh", "VlrTE")

        te_p = _extrair_valor(rows, "Ponta seca", "MWh", "VlrTE")
        if te_p == 0.0:
            te_p = _extrair_valor(rows, "Ponta", "MWh", "VlrTE")

        historico.append({
            "vigencia": pd.Timestamp(vig).strftime("%d/%m/%Y"),
            "tusd_kw_fp": tusd_kw_fp,
            "tusd_kw_p": tusd_kw_p,
            "tusd_mwh_fp": tusd_mwh_fp,
            "tusd_mwh_p": tusd_mwh_p,
            "te_fp": te_fp,
            "te_p": te_p,
        })

    return historico


def obter_mes_reajuste(df: pd.DataFrame, distribuidora: str) -> int:
    """Typical adjustment month derived from most recent DatInicioVigencia."""
    subset = df[df["SigAgente"] == distribuidora]
    if subset.empty:
        return 1
    latest = subset["DatInicioVigencia"].max()
    return latest.month
