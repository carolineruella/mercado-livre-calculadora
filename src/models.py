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
