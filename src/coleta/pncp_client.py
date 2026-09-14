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
        total=5,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    sessao.mount("https://", HTTPAdapter(max_retries=retry))
    sessao.headers.update({"Accept": "application/json"})
    return sessao


def coletar_pagina(
    sessao, uf, modalidade, data_ini, data_fim, pagina, tamanho, municipio=None
):
    if not TAMANHO_MIN_PAGINA <= tamanho <= TAMANHO_MAX_PAGINA:
        raise ValueError(
            f"tamanho de paginas deve estar entre {TAMANHO_MIN_PAGINA} e "
            f"{TAMANHO_MAX_PAGINA}; recebido {tamanho}"
        )

    resp = sessao.get(
        URL,
        params={
            "dataInicial": data_ini,
            "dataFinal": data_fim,
            "uf": uf,
            "pagina": pagina,
            "tamanhoPagina": tamanho,
            "codigoModalidadeContratacao": modalidade,
            "codigoMunicipioIbge": municipio,
        },
        timeout=60,
    )

    if resp.status_code == 204 or not resp.content:
        return None

    resp.raise_for_status()
    return resp.json()


def coletar_fatia(
    sessao, uf, modalidade, data_ini, data_fim, dir_raw, tamanho, municipio=None
):
    dir_raw = Path(dir_raw)
    dir_raw.mkdir(parents=True, exist_ok=True)

    registros = []
    pagina = 1
    total_paginas = None

    while True:
        try:
            payload = coletar_pagina(
                sessao, uf, modalidade, data_ini, data_fim, pagina, tamanho, municipio
            )
        except requests.RequestException as erro:
            logger.error(
                "falha em %s/mod%s pag%s, fatia abandonada: %s",
                uf, modalidade, pagina, erro,
            )
            break

        if payload is None:
            break

        dados = payload.get("data") or []

        if total_paginas is None:
            total_paginas = payload.get("totalPaginas") or 0
            logger.info(
                "%s/mod%-2s %6s registros em %3s paginas",
                uf, modalidade, payload.get("totalRegistros", "?"), total_paginas,
            )

        if not dados:
            break

        destino = dir_raw / f"{uf}_mod{modalidade}_{data_ini}_pag{pagina:03d}.json"
        destino.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        registros.extend(dados)

        if total_paginas and pagina >= total_paginas:
            break
        pagina += 1

    return registros
