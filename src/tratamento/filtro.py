import logging
import re
import unicodedata

import pandas as pd

logger = logging.getLogger(__name__)

APROVADO = "aprovado"
REVISAR = "revisar"
DESCARTADO = "descartado"


def normalizar(texto):
    if not isinstance(texto, str):
        return ""
    texto = unicodedata.normalize("NFKD", texto.lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", texto).strip()


def compilar(termos):
    partes = []
    for termo in termos:
        alvo = normalizar(termo.rstrip("*"))
        if termo.endswith("*"):
            partes.append(rf"\b{re.escape(alvo)}")
        else:
            partes.append(rf"\b{re.escape(alvo)}\b")
    return re.compile("|".join(partes))


def achados(padrao, texto):
    vistos = dict.fromkeys(m.group(0) for m in padrao.finditer(texto))
    return list(vistos)


def classificar_linha(objeto_norm, contexto_norm, padroes):
    inequivocos = achados(padroes["inequivocos"], objeto_norm)
    ambiguos = achados(padroes["ambiguos"], objeto_norm)
    exclusoes = achados(padroes["exclusoes"], objeto_norm)

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


def aplicar_valor_minimo(df, config):
    if df.empty:
        return df
    df = df.copy()
    abaixo_minimo = df["valor_estimado"].notna() & (df["valor_estimado"] < config.VALOR_MINIMO)
    motivo = f"valor estimado abaixo do mínimo de R$ {config.VALOR_MINIMO:,.0f}".replace(",", ".")

    df.loc[abaixo_minimo, "evidencia"] = df.loc[abaixo_minimo, "evidencia"] + "; " + motivo
    df.loc[abaixo_minimo, "destino"] = DESCARTADO

    contagem = df["destino"].value_counts().to_dict()
    logger.info("corte por valor mínimo: %s", contagem)
    return df
