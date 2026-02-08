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

    def _preparar_dados(self):
        c = self.params.consumo
        t = self.params.tributarios
        ct = self.params.contrato

        self.dem_hp = c.demanda_hp_kw
        self.dem_hfp = c.demanda_hfp_kw
        self.consumo_hp = c.consumo_hp_kwh
        self.consumo_hfp = c.consumo_hfp_kwh
        self.consumo_total_kwh = self.consumo_hp + self.consumo_hfp

        # Avoid division by zero
        if self.consumo_total_kwh == 0:
            self.consumo_total_kwh = 1.0

        self.consumo_total_mwh = self.consumo_total_kwh / 1000.0

        self.prop_hp = self.consumo_hp / self.consumo_total_kwh
        self.prop_hfp = 1.0 - self.prop_hp

        self.aliq_icms = t.aliquota_icms / 100.0
        self.aliq_pis = t.aliquota_pis_cofins / 100.0
        self.despesas_ccee = t.despesas_ccee

        # Monthly NPV rate from annual rate (PRD line 428)
        taxa_anual = ct.taxa_vpl / 100.0
        self.taxa_mensal_vpl = (1 + taxa_anual) ** (1.0 / 12.0) - 1.0

        self.num_energia = TIPO_ENERGIA[t.tipo_energia]
        self.num_icms = TIPO_ICMS[t.tipo_icms]
        self.is_azul = self.params.modalidade == "Azul"

        # Contract period
        self.mes_inicio = ct.mes_inicio
        self.ano_inicio = ct.ano_inicio
        self.mes_fim = ct.mes_fim
        self.ano_fim = ct.ano_fim

        # Offer
        self.tipo_oferta = self.params.oferta.tipo_oferta
        self.desconto_garantido = self.params.oferta.desconto_garantido or 0.0
        self.precos_por_ano = self.params.oferta.precos_por_ano or []

    def _construir_serie_tarifas(self):
        """Build a list of TarifasVigentes, one per contract month.

        Uses the vigent tariffs as base. For months in future years,
        project annually at REAJUSTE_ANUAL_PADRAO (5%).
        """
        base = self.params.tarifas
        self.serie_tarifas = []
        self.meses_contrato = []

        mes = self.mes_inicio
        ano = self.ano_inicio
        ano_base = self.ano_inicio

        while (ano < self.ano_fim) or (ano == self.ano_fim and mes <= self.mes_fim):
            anos_projecao = ano - ano_base
            fator = (1 + REAJUSTE_ANUAL_PADRAO) ** anos_projecao

            tarifas_mes = TarifasVigentes(
                tusd_kw_fp=base.tusd_kw_fp * fator,
                tusd_kw_p=base.tusd_kw_p * fator,
                tusd_mwh_fp=base.tusd_mwh_fp * fator,
                tusd_mwh_p=base.tusd_mwh_p * fator,
                te_fp=base.te_fp * fator,
                te_p=base.te_p * fator,
                vigencia=base.vigencia,
            )
            self.serie_tarifas.append(tarifas_mes)
            self.meses_contrato.append((mes, ano))

            mes += 1
            if mes > 12:
                mes = 1
                ano += 1

    def _calcular_acr_mes(self, t: TarifasVigentes) -> dict:
        """Calculate ACR (regulated market) cost for one month (R$/MWh).

        PRD lines 488-500 (original uses /consumoTotal_kWh * 1000, equivalent to /consumo_mwh):
        Azul:
          fio = (TUSD_KW_P * dem_hp + TUSD_KW_FP * dem_hfp) / consumo_mwh
                + TUSD_MWh_P * prop_hp + TUSD_MWh_FP * prop_hfp
        Verde:
          fio = TUSD_KW_FP * (dem_hp + dem_hfp) / consumo_mwh + TUSD_MWh_FP
        """
        if self.is_azul:
            fio = (
                (t.tusd_kw_p * self.dem_hp + t.tusd_kw_fp * self.dem_hfp)
                / self.consumo_total_mwh
                + t.tusd_mwh_p * self.prop_hp
                + t.tusd_mwh_fp * self.prop_hfp
            )
        else:
            # Verde
            fio = (
                t.tusd_kw_fp * (self.dem_hp + self.dem_hfp)
                / self.consumo_total_mwh
                + t.tusd_mwh_fp
            )

        fio_pis = fio / (1 - self.aliq_pis) - fio if self.aliq_pis < 1 else 0.0
        fio_icms = fio / (1 - self.aliq_icms) - fio if self.aliq_icms < 1 else 0.0

        energia = t.te_fp * self.prop_hfp + t.te_p * self.prop_hp
        energia_pis = energia / (1 - self.aliq_pis) - energia if self.aliq_pis < 1 else 0.0
        energia_icms = energia / (1 - self.aliq_icms) - energia if self.aliq_icms < 1 else 0.0

        custo_acr = fio + fio_pis + fio_icms + energia + energia_pis + energia_icms

        return {
            "fio": fio,
            "fio_pis": fio_pis,
            "fio_icms": fio_icms,
            "energia": energia,
            "energia_pis": energia_pis,
            "energia_icms": energia_icms,
            "custo_total_acr": custo_acr,
        }

    def _calcular_acl_mes(self, t: TarifasVigentes, acr: dict, year_idx: int) -> dict:
        """Calculate ACL (free market) cost for one month (R$/MWh).

        PRD lines 502-541:
        Azul:
          fio_acl = num_energia * (TUSD_KW_P * dem_hp + TUSD_KW_FP * dem_hfp)
                    / consumo_mwh + TUSD_MWh_P
        Verde:
          fio_acl = num_energia * TUSD_KW_FP * (dem_hp + dem_hfp)
                    / consumo_mwh
        """
        if self.is_azul:
            fio_acl = (
                self.num_energia
                * (t.tusd_kw_p * self.dem_hp + t.tusd_kw_fp * self.dem_hfp)
                / self.consumo_total_mwh
                + t.tusd_mwh_p
            )
        else:
            # Verde
            fio_acl = (
                self.num_energia
                * t.tusd_kw_fp * (self.dem_hp + self.dem_hfp)
                / self.consumo_total_mwh
            )

        energia_cg = acr["custo_total_acr"] - fio_acl

        # Energy cost in ACL
        if self.tipo_oferta == "Desconto Garantido":
            energia_acl = energia_cg * (1 - self.desconto_garantido / 100.0)
        else:
            # Preço Determinado
            if year_idx < len(self.precos_por_ano):
                energia_acl = self.precos_por_ano[year_idx]
            else:
                # Fallback: use last known price
                energia_acl = self.precos_por_ano[-1] if self.precos_por_ano else energia_cg

        # Tax application by ICMS type
        # For DG mode, energia_acl derives from custo_total_acr (already taxed),
        # so taxes are already embedded — no re-application needed.
        # For PD mode, the price is a raw energy price that needs tax gross-up.
        if self.tipo_oferta == "Preço Determinado":
            if self.num_icms == 2:  # SP: Contribuinte - ICMS padrão
                energia_final = energia_acl
                if self.aliq_icms < 1:
                    energia_final = energia_final / (1 - self.aliq_icms)
                if self.aliq_pis < 1:
                    energia_final = energia_final / (1 - self.aliq_pis)
            elif self.num_icms == 3:  # SNICMS: Contribuinte - ICMS 0%
                energia_final = energia_acl
                if self.aliq_pis < 1:
                    energia_final = energia_final / (1 - self.aliq_pis)
            else:  # NP(1) or NNICMS(4)
                energia_final = energia_acl
        else:
            # DG mode: discount already applied to taxed amount
            energia_final = energia_acl

        custo_acl = fio_acl + energia_final + self.despesas_ccee

        return {
            "fio_acl": fio_acl,
            "energia_cg": energia_cg,
            "energia_acl": energia_acl,
            "energia_final": energia_final,
            "custo_total_acl": custo_acl,
        }

    def _calcular_mensal(self):
        """Calculate monthly results across the full contract period."""
        self.resultados_mensais = []

        for i, (tarifa, (mes, ano)) in enumerate(
            zip(self.serie_tarifas, self.meses_contrato)
        ):
            year_idx = ano - self.ano_inicio

            acr = self._calcular_acr_mes(tarifa)
            acl = self._calcular_acl_mes(tarifa, acr, year_idx)

            custo_acr = acr["custo_total_acr"]
            custo_acl = acl["custo_total_acl"]

            # Discount percentage: 1 - (ACL / ACR)
            desconto = 1 - (custo_acl / custo_acr) if custo_acr != 0 else 0.0

            # Monthly savings in R$ (cost difference * total consumption in MWh)
            economia = (custo_acr - custo_acl) * self.consumo_total_mwh

            # Total spending in R$
            gasto_acr = custo_acr * self.consumo_total_mwh
            gasto_acl = custo_acl * self.consumo_total_mwh

            self.resultados_mensais.append({
                "mes": mes,
                "ano": ano,
                "mes_nome": MESES_PT[mes - 1],
                "periodo": f"{MESES_PT[mes - 1]}/{ano}",
                "custo_acr_mwh": custo_acr,
                "custo_acl_mwh": custo_acl,
                "desconto": desconto,
                "economia": economia,
                "gasto_acr": gasto_acr,
                "gasto_acl": gasto_acl,
                "acr_detalhado": acr,
                "acl_detalhado": acl,
            })

    def _agregar_anual(self):
        """Aggregate monthly results into annual totals and compute NPV.

        PRD lines 654-735:
        Group by year, sum spending, calculate annual discount.
        NPV: taxa_anual = (1+taxa_mensal)^12 - 1
              economia_vpl = npf.npv(taxa_anual, economias_anuais)
        """
        anos_dict = {}
        for r in self.resultados_mensais:
            ano = r["ano"]
            if ano not in anos_dict:
                anos_dict[ano] = {
                    "ano": ano,
                    "gasto_acr": 0.0,
                    "gasto_acl": 0.0,
                    "economia": 0.0,
                    "meses": 0,
                }
            anos_dict[ano]["gasto_acr"] += r["gasto_acr"]
            anos_dict[ano]["gasto_acl"] += r["gasto_acl"]
            anos_dict[ano]["economia"] += r["economia"]
            anos_dict[ano]["meses"] += 1

        self.resultados_anuais = []
        for ano in sorted(anos_dict.keys()):
            dados = anos_dict[ano]
            desconto = (
                1 - (dados["gasto_acl"] / dados["gasto_acr"])
                if dados["gasto_acr"] != 0
                else 0.0
            )
            self.resultados_anuais.append({
                "ano": dados["ano"],
                "gasto_acr": dados["gasto_acr"],
                "gasto_acl": dados["gasto_acl"],
                "economia": dados["economia"],
                "desconto": desconto,
                "meses": dados["meses"],
            })

        # NPV calculation
        economias_anuais = [r["economia"] for r in self.resultados_anuais]
        taxa_anual = (1 + self.taxa_mensal_vpl) ** 12 - 1

        if len(economias_anuais) > 0 and taxa_anual > 0:
            self.economia_vpl = npf.npv(taxa_anual, economias_anuais)
        else:
            self.economia_vpl = sum(economias_anuais)

    def _montar_resultado(self) -> dict:
        """Assemble the final results dictionary."""
        economia_total = sum(r["economia"] for r in self.resultados_mensais)
        gasto_acr_total = sum(r["gasto_acr"] for r in self.resultados_mensais)
        gasto_acl_total = sum(r["gasto_acl"] for r in self.resultados_mensais)

        desconto_geral = (
            1 - (gasto_acl_total / gasto_acr_total)
            if gasto_acr_total != 0
            else 0.0
        )

        return {
            "resultados_mensais": self.resultados_mensais,
            "resultados_anuais": self.resultados_anuais,
            "desconto_geral": desconto_geral,
            "economia_total": economia_total,
            "economia_vpl": float(self.economia_vpl),
            "periodo": [
                f"{MESES_PT[self.mes_inicio - 1]}/{self.ano_inicio}",
                f"{MESES_PT[self.mes_fim - 1]}/{self.ano_fim}",
            ],
            "gastos_acl_anual": [r["gasto_acl"] for r in self.resultados_anuais],
            "gastos_acr_anual": [r["gasto_acr"] for r in self.resultados_anuais],
            "economias_anual": [r["economia"] for r in self.resultados_anuais],
            "anos": [str(r["ano"]) for r in self.resultados_anuais],
            "tarifas_utilizadas": self.params.tarifas,
        }
