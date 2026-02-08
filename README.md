# Simulador Mercado Livre de Energia

Aplicacao web em Streamlit para simular descontos e economia na migracao do mercado regulado (ACR/Cativo) para o mercado livre de energia (ACL) no Brasil.

Utiliza dados reais de tarifas homologadas pela ANEEL (309 mil+ registros, 116+ distribuidoras) para calculos financeiros com impostos em cascata (PIS/COFINS, ICMS), VPL, graficos interativos Plotly e relatorios PDF profissionais.

## Funcionalidades

- **Simulador** — Selecione distribuidora, subgrupo e modalidade tarifaria. Preencha consumo, demanda e dados tributarios para obter o calculo completo de economia com graficos interativos e relatorio PDF.
- **Multi Unitario** — Processe varias unidades consumidoras de uma vez via upload de planilha Excel, com resultados consolidados e barra de progresso.
- **Comparativo** — Compare dois cenarios lado a lado (ex: Desconto Garantido vs Preco Determinado, ou distribuidoras diferentes) com metricas delta e grafico comparativo.

### Destaques

- Selecao em cascata: Distribuidora → SubGrupo → Modalidade (populados do CSV ANEEL)
- Tarifas vigentes carregadas automaticamente ao selecionar distribuidora
- Calculo ACR/ACL completo com modos Desconto Garantido (DG) e Preco Determinado (PD)
- Graficos interativos Plotly com hover em R$ e zoom
- Relatorio PDF de 3 paginas (resumo executivo, grafico, tabela anual)
- Processamento em lote via Excel com template pre-formatado
- Validacao de dados com mensagens de erro em portugues
- Persistencia de resultados via session state

## Requisitos

- Python 3.10+
- Dependencias listadas em `requirements.txt`

## Instalacao

```bash
git clone https://github.com/carolineruella/mercado-livre-calculadora.git
cd mercado-livre-calculadora
pip install -r requirements.txt
```

## Uso

```bash
streamlit run app.py
```

A aplicacao abrira no navegador em `http://localhost:8501`.

## Estrutura do Projeto

```
├── app.py                          # Pagina inicial (home)
├── requirements.txt                # Dependencias Python
├── tarifas-homologadas-*.csv       # Base de dados ANEEL (~309K registros)
├── .streamlit/
│   └── config.toml                 # Tema e configuracao do Streamlit
├── src/
│   ├── constantes.py               # Constantes do setor eletrico
│   ├── models.py                   # Modelos Pydantic de validacao
│   ├── formatacao.py               # Formatacao brasileira (R$, %)
│   ├── dados_tarifarios.py         # Camada de dados ANEEL (CSV)
│   ├── logica_calculadora.py       # Motor de calculo ACR/ACL/VPL
│   ├── grafico.py                  # Graficos Plotly interativos
│   ├── relatorio_pdf.py            # Gerador de relatorio PDF
│   └── cliente_multi_unitario.py   # Processamento em lote
└── pages/
    ├── 1_Simulador.py              # Simulacao individual
    ├── 2_Multi_Unitario.py         # Processamento multi-unidade
    └── 3_Comparativo.py            # Comparacao de cenarios
```

## Dados Tarifarios

O arquivo `tarifas-homologadas-distribuidoras-energia-eletrica.csv` contem dados reais da ANEEL com 309 mil+ registros e 17 colunas.

Para atualizar as tarifas: baixe o CSV atualizado do [portal de dados abertos da ANEEL](https://dadosabertos.aneel.gov.br/), substitua o arquivo e reinicie a aplicacao.

## Verificacao Rapida

Selecione **CEMIG-D → A4 → Azul → DG 20%** e calcule. O desconto esperado fica na faixa de 10-40%, com economia positiva e PDF de 3 paginas.
