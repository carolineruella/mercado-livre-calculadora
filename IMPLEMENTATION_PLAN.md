# Simulador de Desconto — Mercado Livre de Energia (Streamlit) Implementation Plan

## Overview

Build a Streamlit web application from scratch that simulates discounts and savings when migrating from Brazil's regulated electricity market (ACR/Cativo) to the free market (ACL). Uses real ANEEL-homologated tariff data (309K rows, 116 distributors) and performs financial calculations including cascading taxes (PIS/COFINS, ICMS), NPV, generating interactive Plotly charts and professional PDF reports.

## Current State Analysis

The project directory contains only documentation and one data asset — zero source code exists.

- `PRD.md` — Full product spec for a desktop PySimpleGUI calculator (1,402 lines)
- `tarifas-homologadas-distribuidoras-energia-eletrica.csv` — Real ANEEL tariff database
- `create_plan.md`, `implement_plan.md`, `research_codebase.md` — Process templates

### Key Discoveries:
- `tarifas-homologadas-distribuidoras-energia-eletrica.csv`: 309,105 rows, 17 columns, `;` separator, `latin-1` encoding, date range 2010–2026
- **116 real distributors** available (vs 27 hardcoded in PRD) — full national coverage
- Column `DscBaseTarifaria` has `"Tarifa de Aplicação"` (actual rate) vs `"Base Econômica"` — only the former is needed
- `VlrTUSD` and `VlrTE` use Brazilian decimal format: `"22,81"` → 22.81, `",00"` → 0.0
- Filtering to Group A + Azul/Verde + Tarifa de Aplicação yields **~28,524 usable rows**
- TE values live in `"Fora ponta seca"` / `"Ponta seca"` rows (the plain `"Fora ponta"` MWh rows often have VlrTE = 0)
- For Verde modality: demand (kW) uses `NomPostoTarifario = "Não se aplica"` instead of `"Fora ponta"/"Ponta"`
- Each distributor has multiple vigência periods (e.g., CEMIG-D A4 Azul has 23) — no separate dates file needed
- Verified CEMIG-D A4 Azul latest vigência (2026-01-01): TUSD kW FP=22.81, TUSD kW P=68.21, TUSD MWh=153.23, TE FP=296.77, TE P=475.91
- PRD formulas fully documented: ACR (`PRD.md:488-500`), ACL (`PRD.md:502-541`), NPV (`PRD.md:654-735`)

## Desired End State

A working web app at `streamlit run app.py` providing:

1. Dynamic cascading selects: Distributor → Subgroup → Modality (populated from CSV)
2. Auto-loaded current tariffs when distributor is selected
3. Full ACR/ACL/discount/savings calculation with DG and PD offer modes
4. Interactive Plotly stacked-bar charts with BR currency hover
5. Downloadable 3-page PDF report
6. Multi-unit batch processing via Excel upload
7. Side-by-side scenario comparison (DG vs PD or different distributors)

Verification: select CEMIG-D → A4 → Azul → DG 20% → Calculate → discount in 10–40% range → download PDF with 3 pages.

## What We're NOT Doing

- Automatic ANEEL tariff scraping/updates
- Relational database (PostgreSQL/SQLite) — CSV read directly
- User authentication or multi-tenancy
- Cloud deployment (AWS/Azure/GCP)
- Separate REST API
- Group B (low voltage) subgroup processing
- Alerting, notification, or CRM integration

## Implementation Approach

Bottom-up in 7 phases: infrastructure → data layer → calculation engine → visualization → UI → batch processing → polish. Each phase is independently verifiable before advancing.

---

## Phase 1: Project Infrastructure

### Overview
Create directory structure, dependency manifest, Streamlit theme configuration, and Python package init.

### Changes Required:

#### 1. Python Dependencies
**File**: `requirements.txt`
**Changes**: All runtime dependencies for the application.

```text
streamlit>=1.30.0
pandas>=1.5.0
numpy>=1.21.0
numpy-financial>=1.0.0
plotly>=5.15.0
kaleido>=0.2.1
reportlab>=3.6.0
openpyxl>=3.0.9
pydantic>=2.0.0
xlsxwriter>=3.1.0
```

#### 2. Streamlit Theme
**File**: `.streamlit/config.toml`
**Changes**: Green energy brand theme matching PRD colors.

```toml
[theme]
primaryColor = "#148c73"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#f0f2f6"
textColor = "#262730"
font = "sans serif"

[server]
headless = true
port = 8501
```

#### 3. Package Init
**File**: `src/__init__.py`
**Changes**: Empty file to make `src/` importable as a Python package.

#### 4. Directory Structure
Create directories: `src/`, `pages/`, `imagens/`, `.streamlit/`

### Success Criteria:

#### Automated Verification:
- [ ] Directories exist: `python -c "import os; dirs=['src','pages','imagens','.streamlit']; assert all(os.path.isdir(d) for d in dirs), f'Missing: {[d for d in dirs if not os.path.isdir(d)]}'"`
- [ ] Dependencies install cleanly: `pip install -r requirements.txt`
- [ ] All imports succeed: `python -c "import streamlit, pandas, numpy, numpy_financial, plotly, reportlab, pydantic, kaleido"`

#### Manual Verification:
- [ ] No manual verification needed for this phase.

**Implementation Note**: After completing this phase and all automated verification passes, proceed directly to Phase 2.

---

## Phase 2: Constants, Data Models, and Formatting Utilities

### Overview
Build the foundational layer: energy sector constants, Pydantic input/output models with validation, and Brazilian locale formatting functions.

### Changes Required:

#### 1. Energy Sector Constants
**File**: `src/constantes.py`
**Changes**: Mappings for energy types, ICMS taxation modes, Portuguese months, relevant subgroups. Distributors are NOT hardcoded — they come dynamically from the CSV.

```python
TIPO_ENERGIA = {
    "Convencional (i1)": 0,       # Incentivada convencional → fator 0
    "50% Incentivada (i5)": 0.5,  # 50% desconto TUSD → fator 0.5
    "Incentivada (i0)": 1,        # 100% desconto TUSD → fator 1
}

TIPO_ICMS = {
    "Não contribuinte": 1,                    # NP
    "Contribuinte - ICMS padrão": 2,          # SP
    "Contribuinte - ICMS 0%": 3,              # SNICMS
    "Não contribuinte - ACL isenta ICMS": 4,  # NNICMS
}

MESES_PT = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun',
            'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']

SUBGRUPOS_GRUPO_A = ['A1', 'A2', 'A3', 'A3a', 'A4', 'AS']
MODALIDADES_RELEVANTES = ['Azul', 'Verde']
REAJUSTE_ANUAL_PADRAO = 0.05  # 5% fallback for tariff projection
```

#### 2. Pydantic Validation Models
**File**: `src/models.py`
**Changes**: Typed, validated data classes for all system inputs and outputs.

```python
from pydantic import BaseModel, Field
from typing import Optional

class DadosConsumo(BaseModel):
    demanda_hp_kw: float = Field(..., ge=0, le=100_000)
    demanda_hfp_kw: float = Field(..., ge=0, le=100_000)
    consumo_hp_kwh: float = Field(..., ge=0)
    consumo_hfp_kwh: float = Field(..., ge=0)

class DadosTributarios(BaseModel):
    aliquota_icms: float = Field(default=18.0, ge=0, le=35)
    aliquota_pis_cofins: float = Field(default=6.5, ge=0, le=15)
    tipo_energia: str
    despesas_ccee: float = Field(default=0.0, ge=0)
    tipo_icms: str

class DadosContrato(BaseModel):
    mes_inicio: int = Field(..., ge=1, le=12)
    ano_inicio: int = Field(..., ge=2020, le=2035)
    mes_fim: int = Field(..., ge=1, le=12)
    ano_fim: int = Field(..., ge=2020, le=2035)
    taxa_vpl: float = Field(default=9.67, ge=0, le=100)

class DadosOferta(BaseModel):
    tipo_oferta: str  # "Desconto Garantido" | "Preço Determinado"
    desconto_garantido: Optional[float] = Field(default=None, ge=0, le=100)
    precos_por_ano: Optional[list[float]] = None

class DadosCliente(BaseModel):
    nome: str = ""
    cnpj: str = ""

class TarifasVigentes(BaseModel):
    tusd_kw_fp: float = 0.0     # TUSD R$/kW Fora Ponta
    tusd_kw_p: float = 0.0      # TUSD R$/kW Ponta (0 for Verde)
    tusd_mwh_fp: float = 0.0    # TUSD R$/MWh Fora Ponta
    tusd_mwh_p: float = 0.0     # TUSD R$/MWh Ponta
    te_fp: float = 0.0          # TE R$/MWh Fora Ponta
    te_p: float = 0.0           # TE R$/MWh Ponta
    vigencia: str = ""          # Vigência date string

class ParametrosSimulacao(BaseModel):
    consumo: DadosConsumo
    tributarios: DadosTributarios
    contrato: DadosContrato
    oferta: DadosOferta
    cliente: DadosCliente
    distribuidora: str
    subgrupo: str
    modalidade: str
    tarifas: TarifasVigentes
```

#### 3. Brazilian Number Formatting
**File**: `src/formatacao.py`
**Changes**: BR locale formatting utilities and CSV value parser.

```python
def formatar_moeda(valor: float) -> str:
    """1234.56 → 'R$ 1.234,56'"""

def formatar_percentual(valor: float) -> str:
    """0.2534 → '25,34%'"""

def formatar_periodo(mes_ini: int, ano_ini: int, mes_fim: int, ano_fim: int) -> str:
    """→ 'Jan/2024 a Dez/2026'"""

def parse_valor_br(valor_str: str) -> float:
    """'22,81' → 22.81 | ',00' → 0.0 | '' → 0.0"""
```

### Success Criteria:

#### Automated Verification:
- [ ] Constants: `python -c "from src.constantes import TIPO_ENERGIA, TIPO_ICMS; assert len(TIPO_ENERGIA)==3; assert len(TIPO_ICMS)==4"`
- [ ] Models: `python -c "from src.models import ParametrosSimulacao, TarifasVigentes; print('OK')"`
- [ ] Currency: `python -c "from src.formatacao import formatar_moeda; assert formatar_moeda(1234.56)=='R$ 1.234,56'"`
- [ ] Percent: `python -c "from src.formatacao import formatar_percentual; assert formatar_percentual(0.2534)=='25,34%%'"`
- [ ] Parse: `python -c "from src.formatacao import parse_valor_br; assert parse_valor_br('22,81')==22.81; assert parse_valor_br(',00')==0.0"`

#### Manual Verification:
- [ ] No manual verification needed for this phase.

**Implementation Note**: After completing this phase and all automated verification passes, proceed directly to Phase 3.

---

## Phase 3: ANEEL Tariff Data Layer

### Overview
Build the data access layer that reads, caches, filters, and queries the real ANEEL CSV. This single file replaces both `bd_tarifario.xlsx` and `datas_rt.xlsx` from the PRD.

### Changes Required:

#### 1. Tariff Data Module
**File**: `src/dados_tarifarios.py`
**Changes**: CSV loading with cache, cascading filter functions, tariff extraction.

```python
import pandas as pd
import streamlit as st
from src.formatacao import parse_valor_br
from src.models import TarifasVigentes
from src.constantes import SUBGRUPOS_GRUPO_A, MODALIDADES_RELEVANTES

CSV_PATH = "tarifas-homologadas-distribuidoras-energia-eletrica.csv"

@st.cache_data
def carregar_csv_aneel(caminho: str = CSV_PATH) -> pd.DataFrame:
    """Load and pre-filter the ANEEL CSV (~309K rows → ~28.5K after filtering).

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

def listar_distribuidoras(df: pd.DataFrame) -> list[str]:
    """Sorted unique distributor names."""

def listar_subgrupos(df: pd.DataFrame, distribuidora: str) -> list[str]:
    """Subgroups available for given distributor."""

def listar_modalidades(df: pd.DataFrame, distribuidora: str, subgrupo: str) -> list[str]:
    """Modalities available for given distributor + subgroup."""

def obter_tarifas_vigentes(df, distribuidora, subgrupo, modalidade) -> TarifasVigentes:
    """Extract most recent tariff values.

    1. Filter by distribuidora + subgrupo + modalidade
    2. Find max DatInicioVigencia
    3. From that vigência, extract:
       Azul:
         tusd_kw_fp  ← VlrTUSD where Posto='Fora ponta' & Unid='kW'
         tusd_kw_p   ← VlrTUSD where Posto='Ponta'      & Unid='kW'
         tusd_mwh_fp ← VlrTUSD where Posto='Fora ponta' & Unid='MWh'
         tusd_mwh_p  ← VlrTUSD where Posto='Ponta'      & Unid='MWh'
         te_fp       ← VlrTE where Posto='Fora ponta seca' & Unid='MWh'
                        (fallback: Posto='Fora ponta' & Unid='MWh' if seca unavailable)
         te_p        ← VlrTE where Posto='Ponta seca' & Unid='MWh'
                        (fallback: Posto='Ponta' & Unid='MWh')
       Verde:
         tusd_kw_fp  ← VlrTUSD where Posto='Não se aplica' & Unid='kW'
         tusd_kw_p   = 0.0
         (rest same as Azul)
    """

def obter_historico_tarifas(df, distribuidora, subgrupo, modalidade) -> list[dict]:
    """Tariff snapshots ordered by vigência ascending.
    Each: {vigencia, tusd_kw_fp, tusd_kw_p, tusd_mwh_fp, tusd_mwh_p, te_fp, te_p}
    """

def obter_mes_reajuste(df: pd.DataFrame, distribuidora: str) -> int:
    """Typical adjustment month derived from most recent DatInicioVigencia."""
```

### Success Criteria:

#### Automated Verification:
- [ ] CSV loads: `python -c "from src.dados_tarifarios import carregar_csv_aneel; df=carregar_csv_aneel(); assert 25000 < len(df) < 35000, f'Got {len(df)} rows'"` (~28,500 expected)
- [ ] Distributors: `python -c "from src.dados_tarifarios import *; df=carregar_csv_aneel(); ds=listar_distribuidoras(df); assert 'CEMIG-D' in ds; assert len(ds) > 50"`
- [ ] Cascading: `python -c "from src.dados_tarifarios import *; df=carregar_csv_aneel(); assert 'A4' in listar_subgrupos(df,'CEMIG-D'); assert 'Azul' in listar_modalidades(df,'CEMIG-D','A4')"`
- [ ] CEMIG-D Azul tariffs: `python -c "from src.dados_tarifarios import *; df=carregar_csv_aneel(); t=obter_tarifas_vigentes(df,'CEMIG-D','A4','Azul'); assert abs(t.tusd_kw_fp-22.81)<0.1; assert abs(t.te_fp-296.77)<1.0; print(t)"`
- [ ] Verde has no peak demand: `python -c "from src.dados_tarifarios import *; df=carregar_csv_aneel(); t=obter_tarifas_vigentes(df,'CEMIG-D','A4','Verde'); assert t.tusd_kw_p==0.0"`
- [ ] Adjustment month: `python -c "from src.dados_tarifarios import *; df=carregar_csv_aneel(); m=obter_mes_reajuste(df,'CEMIG-D'); assert 1<=m<=12; print(f'Month: {m}')"`

#### Manual Verification:
- [ ] No manual verification needed for this phase.

**Implementation Note**: After completing this phase and all automated verification passes, proceed directly to Phase 4.

---

## Phase 4: Calculation Engine

### Overview
Implement the core financial engine following PRD formulas: ACR costs, ACL costs, discount percentage, monthly savings, and annual NPV aggregation.

### Changes Required:

#### 1. Calculation Engine Class
**File**: `src/logica_calculadora.py`
**Changes**: Full calculation pipeline as a single class.

```python
import numpy as np
import numpy_financial as npf
from src.models import ParametrosSimulacao, TarifasVigentes
from src.constantes import TIPO_ENERGIA, TIPO_ICMS, MESES_PT, REAJUSTE_ANUAL_PADRAO

class LogicaCalculadora:

    def __init__(self, params: ParametrosSimulacao):
        self.params = params

    def calcular(self) -> dict:
        self._preparar_dados()
        self._construir_serie_tarifas()
        self._calcular_mensal()
        self._agregar_anual()
        return self._montar_resultado()

    # --- _preparar_dados ---
    # consumo_total_mwh = (consumo_hp + consumo_hfp) / 1000
    # prop_hp  = consumo_hp / (consumo_hp + consumo_hfp)
    # prop_hfp = 1 - prop_hp
    # aliq_icms = aliquota_icms / 100
    # aliq_pis  = aliquota_pis_cofins / 100
    # taxa_mensal_vpl = (1 + taxa_vpl/100)^(1/12) - 1  [PRD line 428]
    # num_energia = TIPO_ENERGIA[tipo_energia]
    # num_icms    = TIPO_ICMS[tipo_icms]
    # is_azul     = modalidade == 'Azul'

    # --- _construir_serie_tarifas ---
    # For each month of the contract:
    #   - Use tarifas vigentes as base
    #   - For months beyond last vigência: project annually at REAJUSTE_ANUAL_PADRAO
    # Result: list of TarifasVigentes, one per contract month

    # --- _calcular_acr_mes(t) --- [PRD lines 488-500]
    # Azul:
    #   fio = (t.tusd_kw_p * dem_hp + t.tusd_kw_fp * dem_hfp) / consumo_mwh * 1000
    #         + t.tusd_mwh_p * prop_hp + t.tusd_mwh_fp * prop_hfp
    # Verde:
    #   fio = t.tusd_kw_fp * (dem_hp + dem_hfp) / consumo_mwh * 1000 + t.tusd_mwh_fp
    #
    # fio_pis  = fio / (1 - aliq_pis) - fio          [PRD line 490]
    # fio_icms = fio / (1 - aliq_icms) - fio          [PRD line 491]
    # energia  = t.te_fp * prop_hfp + t.te_p * prop_hp
    # energia_pis  = energia / (1 - aliq_pis) - energia
    # energia_icms = energia / (1 - aliq_icms) - energia
    # custo_acr = fio + fio_pis + fio_icms + energia + energia_pis + energia_icms

    # --- _calcular_acl_mes(t, acr, year_idx) --- [PRD lines 502-541]
    # Azul:
    #   fio_acl = num_energia * (t.tusd_kw_p * dem_hp + t.tusd_kw_fp * dem_hfp)
    #             / consumo_mwh * 1000 + t.tusd_mwh_p
    # Verde:
    #   fio_acl = num_energia * t.tusd_kw_fp * (dem_hp + dem_hfp)
    #             / consumo_mwh * 1000
    #
    # energia_cg = acr['custo_total_acr'] - fio_acl
    #
    # DG: energia_acl = energia_cg * (1 - desconto/100)
    # PD: energia_acl = precos_por_ano[year_idx]
    #
    # Tax by ICMS type:
    #   SP(2):     energia_final = energia_acl / (1-aliq_icms) / (1-aliq_pis)
    #   SNICMS(3): energia_final = energia_acl / (1-aliq_pis)
    #   NP(1)/NNICMS(4): energia_final = energia_acl
    #
    # custo_acl = fio_acl + energia_final + despesas_ccee

    # --- _calcular_mensal ---
    # For each month: acr → acl → desconto = 1-(acl/acr) → economia = (acr-acl)*consumo_mwh

    # --- _agregar_anual --- [PRD lines 654-735]
    # Group by year, sum gastos, calculate annual discount
    # NPV: taxa_anual = (1+taxa_mensal)^12 - 1
    #       economia_vpl = npf.npv(taxa_anual, economias_anuais)

    # --- _montar_resultado ---
    # Returns dict with: resultados_mensais, resultados_anuais, desconto_geral,
    #   economia_total, economia_vpl, periodo, gastos_acl_anual, gastos_acr_anual,
    #   economias_anual, anos, tarifas_utilizadas
```

### Success Criteria:

#### Automated Verification:
- [ ] Import: `python -c "from src.logica_calculadora import LogicaCalculadora; print('OK')"`
- [ ] CEMIG-D A4 Azul DG 20% end-to-end: `python -c "from src.dados_tarifarios import *; from src.logica_calculadora import LogicaCalculadora; from src.models import *; df=carregar_csv_aneel(); t=obter_tarifas_vigentes(df,'CEMIG-D','A4','Azul'); p=ParametrosSimulacao(consumo=DadosConsumo(demanda_hp_kw=100,demanda_hfp_kw=300,consumo_hp_kwh=30000,consumo_hfp_kwh=120000),tributarios=DadosTributarios(tipo_energia='Convencional (i1)',tipo_icms='Contribuinte - ICMS padrão'),contrato=DadosContrato(mes_inicio=1,ano_inicio=2025,mes_fim=12,ano_fim=2027),oferta=DadosOferta(tipo_oferta='Desconto Garantido',desconto_garantido=20),cliente=DadosCliente(),distribuidora='CEMIG-D',subgrupo='A4',modalidade='Azul',tarifas=t); r=LogicaCalculadora(p).calcular(); assert 0<r['desconto_geral']<0.5; assert r['economia_total']>0; print(f'Discount:{r[\"desconto_geral\"]:.1%} Economy:R${r[\"economia_total\"]:,.0f}')"`
- [ ] NPV is finite: assert economia_vpl is not NaN/Inf
- [ ] ACR > ACL when discount > 0: verified implicitly by economia_total > 0

#### Manual Verification:
- [ ] Calculated discount falls within market benchmark range (10–40% for typical DG 20% scenario)

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation that the calculation results are plausible before proceeding to Phase 5.

---

## Phase 5: Interactive Charts and PDF Report

### Overview
Plotly interactive charts (replacing PRD's static matplotlib) and a 3-page in-memory PDF report via reportlab.

### Changes Required:

#### 1. Plotly Chart Functions
**File**: `src/grafico.py`
**Changes**: Four chart generators returning `plotly.graph_objects.Figure`.

```python
import plotly.graph_objects as go
from src.formatacao import formatar_moeda

def criar_grafico_economia(gastos_acl: list, economias: list, anos: list) -> go.Figure:
    """Stacked bars: ACL cost (#148c73 dark green) + savings (#80c739 light green).
    Hover with R$ values, Y-axis currency format, bar labels."""

def criar_grafico_desconto_mensal(resultados_mensais: list) -> go.Figure:
    """Line chart: discount % over contract months. Color #148c73, filled area."""

def criar_grafico_composicao(acr_components: dict) -> go.Figure:
    """Donut chart: ACR cost breakdown (TUSD Demand, TUSD Consumption, TE, PIS/COFINS, ICMS)."""

def criar_grafico_comparativo(resultado_a: dict, resultado_b: dict,
                               label_a: str, label_b: str) -> go.Figure:
    """Grouped bars comparing two scenarios side by side."""
```

#### 2. PDF Report Generator
**File**: `src/relatorio_pdf.py`
**Changes**: In-memory 3-page PDF using reportlab canvas.

```python
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.platypus import Table, TableStyle

def gerar_relatorio(nome_cliente: str, desconto: float, economia: float,
                    periodo: list[str], grafico_png: bytes,
                    resultados_anuais: list[dict],
                    numero_unidade: int = 0) -> bytes:
    """Returns PDF bytes for st.download_button.

    Page 1 — Executive Summary:
      Title, client name, discount % in Helvetica-Bold 40pt #148c73,
      total savings in 18pt, contract period in 12pt #158d74.

    Page 2 — Full Chart:
      Large stacked bar chart (140×60mm centered).

    Page 3 — Annual Results Table:
      Columns: Ano | Custo ACR | Custo ACL | Economia | Desconto %
      Brazilian formatting, totals row at bottom.
    """
```

### Success Criteria:

#### Automated Verification:
- [ ] Chart imports: `python -c "from src.grafico import criar_grafico_economia, criar_grafico_desconto_mensal, criar_grafico_composicao, criar_grafico_comparativo"`
- [ ] Chart returns Figure: `python -c "from src.grafico import criar_grafico_economia; import plotly.graph_objects as go; fig=criar_grafico_economia([100000,200000],[50000,60000],['2025','2026']); assert isinstance(fig, go.Figure)"`
- [ ] PDF imports: `python -c "from src.relatorio_pdf import gerar_relatorio"`
- [ ] PDF generates non-empty bytes: `python -c "from src.relatorio_pdf import gerar_relatorio; b=gerar_relatorio('Teste',0.25,100000.0,['Jan/2025','Dez/2027'],b'',[{'ano':2025,'gasto_acr':500000,'gasto_acl':375000,'economia':125000,'desconto':0.25}]); assert len(b)>500; print(f'PDF: {len(b)} bytes')"`

#### Manual Verification:
- [ ] Chart renders interactively in Streamlit (hover shows values, zoom works)
- [ ] Downloaded PDF opens in a reader and has 3 distinct pages
- [ ] PDF text is readable with correct Brazilian formatting

**Implementation Note**: After completing this phase and all automated verification passes, pause here for manual confirmation that charts and PDF look correct before proceeding to Phase 6.

---

## Phase 6: Streamlit Application (Home + 3 Pages)

### Overview
Build the complete web interface: landing page with market overview, main simulator page, multi-unit batch page, and scenario comparison page.

### Changes Required:

#### 1. Home / Landing Page
**File**: `app.py`
**Changes**: App config, title, market metrics, navigation instructions.

```python
import streamlit as st
st.set_page_config(page_title="Simulador ML Energia", page_icon="⚡", layout="wide")
# Title, description, 3 metric cards (market stats from PRD), page navigation guide
```

#### 2. Simulator Page
**File**: `pages/1_Simulador.py`
**Changes**: Two-column layout — form on left, results on right.

Left column (inside `st.form`):
- Distribuidora: `st.selectbox` (116 options from CSV)
- SubGrupo: `st.selectbox` (cascading filter)
- Modalidade: `st.selectbox` (cascading filter)
- Info box: auto-loaded tariffs (read-only)
- 4× `st.number_input`: Demanda HP/HFP (kW), Consumo HP/HFP (kWh)
- 2× `st.number_input`: ICMS %, PIS/COFINS %
- `st.selectbox`: Tipo Energia (3 opts), Tipo ICMS (4 opts)
- `st.number_input`: CCEE R$/MWh
- 4× `st.selectbox`: Mês/Ano início, Mês/Ano fim
- `st.number_input`: Taxa VPL % (default 9.67)
- `st.radio`: DG / PD
  - DG → `st.slider` 0–50%
  - PD → `st.text_input` comma-separated prices
- `st.form_submit_button("⚡ Calcular Economia")`

Right column (after submit):
- 3× `st.metric`: Desconto Médio, Economia Total, Economia VPL
- `st.plotly_chart`: stacked bar (economia)
- `st.tabs` with 3 tabs:
  - "Resultados Anuais": `st.dataframe`
  - "Evolução Mensal": line chart
  - "Composição Custo": donut chart
- 2× `st.download_button`: PDF and CSV

#### 3. Multi-Unit Batch Page
**File**: `pages/2_Multi_Unitario.py`
**Changes**: Template download, file upload, batch processing with progress.

- `st.download_button`: Excel template
- `st.file_uploader`: .xlsx
- `st.progress` during processing
- Consolidated results table and chart
- Results Excel download

#### 4. Comparison Page
**File**: `pages/3_Comparativo.py`
**Changes**: Side-by-side scenario comparison.

- Two columns, each with a full form
- "Comparar Cenários" button
- Grouped bar chart + difference table + delta metrics

### Success Criteria:

#### Automated Verification:
- [x] App starts without import errors: `streamlit run app.py --server.headless true &; sleep 5; curl -s http://localhost:8501 | head -1; kill %1` (returns HTML)

#### Manual Verification:
- [ ] Home page loads with title, description, market metrics
- [ ] Simulator: select CEMIG-D → A4 → Azul → tariffs appear (TUSD kW FP ≈ 22.81)
- [ ] Simulator: fill form → Calculate → metrics + chart + table appear
- [ ] Charts are interactive (hover shows R$ values, zoom works)
- [ ] PDF download button works, file opens correctly with 3 pages
- [ ] CSV download produces valid spreadsheet
- [ ] Multi-unit: template downloads with correct column headers
- [ ] Multi-unit: upload filled template → progress bar → consolidated results
- [ ] Comparison: two forms side-by-side → grouped bar chart + delta metrics
- [ ] Changing distributor cascades subgroup/modality options correctly

**Implementation Note**: After completing this phase and all automated verification passes, pause here for comprehensive manual UI testing before proceeding to Phase 7.

---

## Phase 7: Multi-Unit Processing and Final Polish

### Overview
Implement the batch processing backend, add error handling across all modules, and apply session state for UX persistence.

### Changes Required:

#### 1. Batch Processing Module
**File**: `src/cliente_multi_unitario.py`
**Changes**: Template generation and row-by-row processing.

```python
import pandas as pd
from io import BytesIO

TEMPLATE_COLUMNS = [
    'Nome', 'Distribuidora', 'SubGrupo', 'Modalidade',
    'Demanda HP (kW)', 'Demanda HFP (kW)', 'Consumo HP (kWh)', 'Consumo HFP (kWh)',
    'ICMS (%)', 'PIS/COFINS (%)', 'Tipo Energia', 'Tipo ICMS', 'CCEE (R$/MWh)',
    'Mês Início', 'Ano Início', 'Mês Fim', 'Ano Fim',
    'Taxa VPL (%)', 'Tipo Oferta', 'Desconto (%) ou Preços',
]

def gerar_template_excel() -> bytes:
    """Template with headers + 1 example row. Returns .xlsx bytes."""

def processar_multi_unitario(arquivo: bytes, df_tarifas: pd.DataFrame,
                              progress_callback=None) -> dict:
    """Process each row: build params → fetch tariffs → calculate → generate PDF.
    Returns {'unidades': [...], 'consolidado': {...}}
    """
```

#### 2. Error Handling (all files)
- Pydantic validation errors → `st.error()` with Portuguese messages
- `st.warning()` for distributors with missing data
- Division-by-zero guards in all financial calculations
- Try/except around PDF generation with user-friendly fallback
- `st.toast()` for success notifications

#### 3. Session State (pages/1_Simulador.py)
- Store last result in `st.session_state['ultimo_resultado']`
- Persist form values across reruns

### Success Criteria:

#### Automated Verification:
- [ ] Template: `python -c "from src.cliente_multi_unitario import gerar_template_excel; t=gerar_template_excel(); assert len(t)>100"`
- [ ] All modules import: `python -c "from src import constantes, models, formatacao, dados_tarifarios, logica_calculadora, grafico, relatorio_pdf, cliente_multi_unitario; print('All OK')"`

#### Manual Verification:
- [ ] Upload Excel with 3+ units → processes all with progress bar
- [ ] Invalid data in form shows clear Portuguese error message (not traceback)
- [ ] Entering negative demand shows validation error
- [ ] Small distributor (e.g., HIDROPAN) with limited data works gracefully
- [ ] All downloads work: PDF, CSV, Excel template, Excel results
- [ ] App looks professional and consistent across all pages

**Implementation Note**: After completing this phase and all manual verification passes, the implementation is complete.

---

## Testing Strategy

### Unit Tests:
- `formatacao.py`: formatar_moeda (0, negative, large), formatar_percentual, parse_valor_br (empty, comma-only, normal)
- `models.py`: valid construction, rejection of negative demand, ICMS > 35, consumo < 0
- `dados_tarifarios.py`: CSV load shape, filter by known distributor, tariff extraction matches expected values
- `logica_calculadora.py`: ACR > 0 with real tariffs, ACL < ACR for DG > 0, NPV finite, DG ≠ PD results

### Integration Tests:
- Full pipeline: load CSV → extract tariffs → calculate → generate chart → generate PDF
- Multi-unit: generate template → fill 3 rows → process → verify 3 results with economia > 0
- Comparison: DG 20% vs PD R$200/MWh → verify grouped chart has 2 series

### Manual Testing Steps:
1. Open app in browser, navigate all 4 pages (Home + 3)
2. Simulate CEMIG-D A4 Azul DG 20%: verify discount 10–40%, download PDF (3 pages)
3. Switch to PD mode R$200/MWh: verify different results
4. Upload multi-unit Excel with 3 units: verify progress bar and consolidated table
5. Compare DG 20% vs PD R$200: verify grouped chart and delta metrics
6. Test small distributor (HIDROPAN): verify graceful handling
7. Enter invalid data: verify Portuguese error messages, no tracebacks
8. Test all download buttons: PDF, CSV, template, results Excel

## Performance Considerations

- `@st.cache_data` on CSV load: 309K rows read once per Streamlit session (~2–3s first load, instant thereafter)
- Cascading dropdown filters: pandas operations on cached DataFrame (<100ms per filter)
- PDF generation: in-memory via `BytesIO`, no disk writes
- Plotly charts: rendered client-side in browser, zero server rendering cost
- Multi-unit batch: sequential calculation with `st.progress()` feedback (~1s per unit)

## Migration Notes

- Greenfield project — no existing system to migrate
- `tarifas-homologadas-distribuidoras-energia-eletrica.csv` is the sole data source
- To update tariffs: download new CSV from ANEEL open data portal, replace file, restart app
- ANEEL CSV format is standardized and stable

## References

- PRD specification: `PRD.md` (1,402 lines)
- ANEEL tariff data: `tarifas-homologadas-distribuidoras-energia-eletrica.csv` (309,105 rows, 17 columns)
- ACR cost formulas: `PRD.md:488-500`
- ACL cost formulas: `PRD.md:502-541`
- NPV aggregation: `PRD.md:654-735`
- Tax cascade logic: `PRD.md:670-686`
- Formula summary: `PRD.md:1262-1287` (Appendix B)
- Tariff modalities: `PRD.md:206-214`
