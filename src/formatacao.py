from src.constantes import MESES_PT


def formatar_moeda(valor: float) -> str:
    """1234.56 → 'R$ 1.234,56'"""
    if valor < 0:
        return f"-R$ {_formatar_numero_br(abs(valor))}"
    return f"R$ {_formatar_numero_br(valor)}"


def formatar_percentual(valor: float) -> str:
    """0.2534 → '25,34%'"""
    pct = valor * 100
    inteiro = int(pct)
    decimal = round(pct - inteiro, 2)
    parte_decimal = f"{decimal:.2f}"[2:]  # "0.34" → "34"
    return f"{inteiro},{parte_decimal}%"


def formatar_periodo(mes_ini: int, ano_ini: int, mes_fim: int, ano_fim: int) -> str:
    """→ 'Jan/2024 a Dez/2026'"""
    return f"{MESES_PT[mes_ini - 1]}/{ano_ini} a {MESES_PT[mes_fim - 1]}/{ano_fim}"


def parse_valor_br(valor_str: str) -> float:
    """'22,81' → 22.81 | ',00' → 0.0 | '' → 0.0"""
    if not valor_str or not isinstance(valor_str, str):
        return 0.0
    valor_str = valor_str.strip()
    if not valor_str:
        return 0.0
    valor_str = valor_str.replace('.', '').replace(',', '.')
    try:
        return float(valor_str)
    except ValueError:
        return 0.0


def _formatar_numero_br(valor: float) -> str:
    """1234.56 → '1.234,56'"""
    inteiro = int(valor)
    decimal = round(valor - inteiro, 2)
    parte_inteira = f"{inteiro:,}".replace(',', '.')
    parte_decimal = f"{decimal:.2f}"[2:]  # "0.56" → "56"
    return f"{parte_inteira},{parte_decimal}"
