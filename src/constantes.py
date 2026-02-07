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
