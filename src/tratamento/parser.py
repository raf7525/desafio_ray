import logging

import pandas as pd

logger = logging.getLogger(__name__)

#traduzindo os nomes das colunas do json para nomes das variaveis mais faceis
COLUNAS = {
    "numeroControlePNCP": "id_pncp",
    "objetoCompra": "objeto",
    "valorTotalEstimado": "valor_estimado",
    "modalidadeNome": "modalidade",
    "situacaoCompraNome": "situacao",
    "dataPublicacaoPncp": "data_publicacao",
    "dataAberturaProposta": "data_abertura",
    "dataEncerramentoProposta": "data_encerramento",
    "linkSistemaOrigem": "link",
    "processo": "processo",
    "orgaoEntidade.razaoSocial": "orgao",
    "orgaoEntidade.cnpj": "cnpj_orgao",
    "unidadeOrgao.ufSigla": "uf",
    "unidadeOrgao.municipioNome": "municipio",
    "unidadeOrgao.nomeUnidade": "unidade",
}

COLUNAS_DATA = ["data_publicacao", "data_abertura", "data_encerramento"]


def montar_dataframe(registros):
    if not registros:
        return pd.DataFrame(columns=list(COLUNAS.values()))

    df = pd.json_normalize(registros)

    ausentes = [c for c in COLUNAS if c not in df.columns]
    if ausentes:
        logger.warning("campos ausentes no retorno da API: %s", ausentes)

    df = df[[c for c in COLUNAS if c in df.columns]].rename(columns=COLUNAS)

    # checando se eh uma data ou string 
    for coluna in COLUNAS_DATA:
        if coluna in df.columns:
            df[coluna] = pd.to_datetime(df[coluna], errors="coerce")

    df["valor_estimado"] = pd.to_numeric(df["valor_estimado"], errors="coerce")

    # tirando duplicados, caso haja algum registro duplicado no retorno da API, registros podem estar em mais de uma fatia
    antes = len(df)
    df = df.drop_duplicates(subset=["id_pncp"], keep="first")
    if antes != len(df):
        logger.info("deduplicação: %s -> %s registros", antes, len(df))

    return df.reset_index(drop=True)
