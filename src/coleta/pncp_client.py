import json
import logging
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

URL = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"

TAMANHO_MAX_PAGINA = 50
TAMANHO_MIN_PAGINA = 10

logger = logging.getLogger(__name__)

def criar_sessao():
    sessao = requests.Session()
    retry = Retry(
        total = 5,
        backoff_factor = 1,  
        status_forcelist = [429, 500, 502, 503, 504],
        allowed_methods = ["GET"],
    )
    sessao.mount("https://", HTTPAdapter(max_retries=retry))
    sessao.headers.update({"Accept": "application/json"})
    return sessao

def coletar_pagina(sessao,data_ini,data_fim,modalidade,uf,Municipio,pagina,tamanho):
    #coleta uma pagina de resultados da api
    if not TAMANHO_MIN_PAGINA <= tamanho <= TAMANHO_MAX_PAGINA:
        raise ValueError(
            f"tamanho de paginas deve estar entre {TAMANHO_MIN_PAGINA} e {TAMANHO_MAX_PAGINA}; recebido {tamanho}"
        )
    resp = sessao.get(
        URL,
        params={
            "dataInicial":data_ini,
            "dataFinal":data_fim,
            "uf":uf,
            "pagina":pagina,
            "tamanhoPagina":tamanho,
            "codigoModalidadeContratacao":modalidade,
            "codigoMunicipioIbge":Municipio,
        },
        timeout=60,#tempo limite de espera de resposta
    )
    resp.raise_for_status()
    return resp.json()