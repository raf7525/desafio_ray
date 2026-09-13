"""Filtro de relevância por assunto.

Decide se uma licitação pertence ao ramo do cliente (equipamentos e serviços
de tecnologia para saúde pública) olhando o texto do objeto e o nome do órgão
comprador.

O desenho tem três ideias, todas nascidas de medição sobre dado real:

1. Casamento por PALAVRA, nunca por substring. Substring fazia "ubs" casar
   dentro de "sUBScrição" e "upa" dentro de "roUPA".

2. Duas dimensões: produto × contexto. Termos como "equipamento", "sistema" ou
   "computador" são do ramo do cliente mas aparecem em compras de qualquer
   área. Eles só valem quando há sinal de saúde junto. Já "desfibrilador" ou
   "prontuário eletrônico" dispensam contexto.

3. Conflito não descarta, manda para revisão. Um objeto que casa em inclusão e
   exclusão ao mesmo tempo ("equipamento médico para ambulância") é ambíguo por
   natureza; jogá-lo fora em silêncio esconde oportunidade real.

Este módulo trata SOMENTE a relevância por assunto. Os cortes por valor mínimo
e por UF são etapas separadas do pipeline.
"""

import logging
import re
import unicodedata

import pandas as pd

logger = logging.getLogger(__name__)

APROVADO = "aprovado"
REVISAR = "revisar"
DESCARTADO = "descartado"


def normalizar(texto):
    """Minúsculas, sem acento e com pontuação virada em espaço.

    Os acentos saem porque o edital escreve "prontuário" e a lista diz
    "prontuario". A pontuação vira espaço para que "médico-hospitalar" e
    "médico hospitalar"  as duas grafias aparecem no corpus, 47 e 70 vezes 
    sejam o mesmo texto para o filtro.
    """
    if not isinstance(texto, str):
        return ""
    texto = unicodedata.normalize("NFKD", texto.lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", texto).strip()


def compilar(termos):
    """Transforma a lista de termos do config num padrão único.

    Termo terminado em "*" casa por prefixo: "tomograf*" pega tomografia,
    tomógrafo e tomográfico. Sem "*", exige a palavra inteira.
    """
    partes = []
    for termo in termos:
        alvo = normalizar(termo.rstrip("*"))
        if termo.endswith("*"):
            partes.append(rf"\b{re.escape(alvo)}")
        else:
            partes.append(rf"\b{re.escape(alvo)}\b")
    return re.compile("|".join(partes))


def achados(padrao, texto):
    """Termos distintos que o padrão encontrou, preservando a ordem."""
    vistos = dict.fromkeys(m.group(0) for m in padrao.finditer(texto))
    return list(vistos)


def classificar_linha(objeto_norm, contexto_norm, padroes):
    """Classifica uma licitação. Devolve (destino, evidência)."""
    inequivocos = achados(padroes["inequivocos"], objeto_norm)
    ambiguos = achados(padroes["ambiguos"], objeto_norm)
    exclusoes = achados(padroes["exclusoes"], objeto_norm)

    # O contexto de saúde é procurado no objeto E no nome do órgão comprador.
    # O órgão é um sinal independente do texto do edital: "Secretaria Municipal
    # de Saúde" comprando "Equipamentos" resolve uma ambiguidade que o objeto
    # sozinho não resolve.
    contexto = achados(padroes["contexto"], f"{objeto_norm} {contexto_norm}")

    if inequivocos:
        motivo = f"produto do ramo: {', '.join(inequivocos[:3])}"
    elif ambiguos and contexto:
        motivo = (f"produto genérico ({', '.join(ambiguos[:2])}) "
                  f"em contexto de saúde ({', '.join(contexto[:2])})")
    elif ambiguos:
        return DESCARTADO, (f"produto genérico ({', '.join(ambiguos[:2])}) "
                            f"sem contexto de saúde")
    else:
        return DESCARTADO, "nenhum produto do ramo do cliente"

    if exclusoes:
        return REVISAR, f"{motivo}  MAS casa em exclusão: {', '.join(exclusoes[:3])}"

    return APROVADO, motivo


def aplicar(df, config):
    """Classifica o DataFrame inteiro.

    Acrescenta as colunas `destino` e `evidencia` e devolve o DataFrame. Nada é
    removido: a rastreabilidade de por que cada licitação entrou ou saiu é o
    que permite ao time comercial refinar as listas depois.
    """
    if df.empty:
        return df.assign(destino=pd.Series(dtype=str),
                         evidencia=pd.Series(dtype=str))

    padroes = {
        "inequivocos": compilar(config.PRODUTOS_INEQUIVOCOS),
        "ambiguos": compilar(config.PRODUTOS_AMBIGUOS),
        "contexto": compilar(config.CONTEXTO_SAUDE),
        "exclusoes": compilar(config.EXCLUSOES),
    }

    objeto_norm = df["objeto"].map(normalizar)
    contexto_norm = (df["orgao"].fillna("") + " " + df["unidade"].fillna("")).map(normalizar)

    resultado = [
        classificar_linha(o, c, padroes)
        for o, c in zip(objeto_norm, contexto_norm)
    ]

    df = df.copy()
    df["destino"] = [r[0] for r in resultado]
    df["evidencia"] = [r[1] for r in resultado]

    contagem = df["destino"].value_counts().to_dict()
    logger.info("filtro por assunto: %s", contagem)
    return df
