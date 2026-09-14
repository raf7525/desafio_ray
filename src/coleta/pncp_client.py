import json
import logging
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

URL = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"

TAMANHO_MAX_PAGINA = 50

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
