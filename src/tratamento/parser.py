"""Bruto (JSON aninhado) -> tabela plana, tipada e sem duplicatas."""

import logging

import pandas as pd

logger = logging.getLogger(__name__)

# Campos da API -> nomes usados no projeto. O ponto no nome de origem marca
# onde json_normalize abriu um objeto aninhado.
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
    """Achata, renomeia, tipa e deduplica os registros brutos."""
    if not registros:
        return pd.DataFrame(columns=list(COLUNAS.values()))

    # json_normalize abre os objetos aninhados: {"unidadeOrgao": {"ufSigla": "PE"}}
    # vira a coluna plana "unidadeOrgao.ufSigla".
    df = pd.json_normalize(registros)

    ausentes = [c for c in COLUNAS if c not in df.columns]
    if ausentes:
        logger.warning("campos ausentes no retorno da API: %s", ausentes)

    df = df[[c for c in COLUNAS if c in df.columns]].rename(columns=COLUNAS)

    # Tipagem explícita: o enunciado pede datas como data e valores como número.
    # A API manda ambos como texto/JSON cru.
    for coluna in COLUNAS_DATA:
        if coluna in df.columns:
            df[coluna] = pd.to_datetime(df[coluna], errors="coerce")

    df["valor_estimado"] = pd.to_numeric(df["valor_estimado"], errors="coerce")

    # Deduplicação pela chave única do próprio PNCP. É necessária porque uma
    # mesma contratação pode cair em mais de uma fatia da coleta e porque
    # reexecuções sobrepõem janelas de data.
    antes = len(df)
    df = df.drop_duplicates(subset=["id_pncp"], keep="first")
    if antes != len(df):
        logger.info("deduplicação: %s -> %s registros", antes, len(df))

    return df.reset_index(drop=True)
