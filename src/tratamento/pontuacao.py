"""Pontuação de prioridade comercial das licitações aprovadas.

Não decide o que entra ou sai — isso é papel do filtro de relevância e do
corte por valor mínimo (filtro.py). Aqui, dentro do que já foi aprovado,
soma três sinais independentes para ordenar quem merece contato comercial
primeiro. Os pesos ficam em config.py, não aqui, para ajustar a régua sem
mexer na lógica:

1. Valor estimado, em log10: contratos maiores tendem a ser mais rentáveis
   para o cliente, mas o log evita que um único edital de R$ 50 milhões
   domine a nota sozinho.
2. UF prioritária: reforça as regiões que o cenário do cliente já elege como
   foco (Pernambuco, Bahia, Ceará, São Paulo e Minas Gerais).
3. Capital: a presença comercial do cliente é mais forte nas capitais, então
   uma licitação de órgão sediado na capital do estado vale mais que uma do
   interior.
"""

import numpy as np
import pandas as pd

from src.tratamento.filtro import normalizar


def calcular(df, config):
    """Acrescenta `eh_capital` e `pontuacao` ao DataFrame; ordena por nota."""
    if df.empty:
        return df.assign(eh_capital=pd.Series(dtype=bool),
                         pontuacao=pd.Series(dtype=float))

    df = df.copy()

    capital_por_uf = {uf: normalizar(nome) for uf, nome in config.CAPITAIS.items()}
    municipio_norm = df["municipio"].map(normalizar)
    capital_esperada = df["uf"].map(capital_por_uf)
    df["eh_capital"] = capital_esperada.notna() & (municipio_norm == capital_esperada)

    valor = df["valor_estimado"].fillna(0).clip(lower=0)
    pontuacao = config.PESO_VALOR * np.log10(valor + 1)
    pontuacao += df["uf"].isin(config.UFS).astype(float) * config.BONUS_UF_PRIORITARIA
    pontuacao += df["eh_capital"].astype(float) * config.BONUS_CAPITAL

    df["pontuacao"] = pontuacao.round(1)
    return df.sort_values("pontuacao", ascending=False).reset_index(drop=True)
