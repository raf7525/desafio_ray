import numpy as np
import pandas as pd

from src.tratamento.filtro import normalizar


def calcular(df, config):
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
