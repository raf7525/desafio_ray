#aqui acontece a extração de dados, lincado direto com o PNCP

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

URL = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"


TAMANHO_PAGINA_MIN = 10
TAMANHO_PAGINA_MAX = 50

logger = logging.getLogger(__name__)


def criar_sessao():
    sessao = requests.Session()
    retry = Retry(#ajuda a caso algum erro ocorra ele continua tentando
        total=5,
        backoff_factor=1,  # espera 1s, 2s, 4s, 8s, 16s entre tentativas
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    sessao.mount("https://", HTTPAdapter(max_retries=retry))
    sessao.headers.update({"Accept": "application/json"})
    return sessao


def coletar_pagina(sessao, uf, modalidade, data_ini, data_fim, pagina, tamanho):
    #Coleta uma página de resultados da API do PNCP.
    if not TAMANHO_PAGINA_MIN <= tamanho <= TAMANHO_PAGINA_MAX:
        raise ValueError(
            f"tamanhoPagina deve estar entre {TAMANHO_PAGINA_MIN} e "
            f"{TAMANHO_PAGINA_MAX}; recebido {tamanho}"
        )

    resp = sessao.get(
        URL,
        params={
            "dataInicial": data_ini,       # formato AAAAMMDD, sem hífens
            "dataFinal": data_fim,
            "codigoModalidadeContratacao": modalidade,  # um valor por chamada
            "uf": uf,
            "pagina": pagina,
            "tamanhoPagina": tamanho,
        },
        timeout=60,
    )
    resp.raise_for_status()

    # A API sinaliza "sem resultados" com 204 e corpo vazio, não com 200 e lista
    # vazia. Sem esta checagem, .json() estoura JSONDecodeError.
    if resp.status_code == 204 or not resp.content:
        return {"data": [], "totalRegistros": 0, "totalPaginas": 0}

    return resp.json()


def coletar_fatia(sessao, uf, modalidade, data_ini, data_fim, dir_raw, tamanho):
    registros = []
    pagina = 1
    total_paginas = None

    while True:
        try:
            payload = coletar_pagina(
                sessao, uf, modalidade, data_ini, data_fim, pagina, tamanho
            )
        except requests.RequestException as erro:
            # Falha persistente mesmo após os retries: registra e abandona só a fatia em vez do programa inteiro.
            logger.error(
                "falha em %s/mod%s pág%s  fatia abandonada: %s",
                uf, modalidade, pagina, erro,
            )
            break

        if total_paginas is None:
            total_paginas = payload["totalPaginas"]
            logger.info(
                "%s/mod%-2s %6s registros em %3s páginas",
                uf, modalidade, payload["totalRegistros"], total_paginas,
            )

        if not payload["data"]:
            break

        # Grava o bruto ANTES  de qualquer processamento. Uma página por arquivo:
        # se a coleta cair na página 200, as 199 anteriores continuam no disco.
        destino = dir_raw / f"{uf}_mod{modalidade}_pag{pagina:03d}.json"
        destino.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        registros.extend(payload["data"])

        if pagina >= total_paginas:
            break

        pagina += 1

    return registros


def coletar_tudo(ufs, modalidades, data_ini, data_fim, dir_raw,
                 tamanho=TAMANHO_PAGINA_MAX, max_workers=5):
    """Produto cartesiano UF × modalidade × página.

    O laço existe porque a API aceita apenas UMA modalidade por chamada e
    devolve no máximo 50 registros por página. Cada combinação UF/modalidade
    é uma fatia independente (arquivos próprios, sem estado compartilhado),
    então roda em threads: o gargalo é a espera de rede, não CPU, então o
    tempo total passa a ser o da fatia mais lenta em vez da soma de todas.
    A sessão é compartilhada entre as threads porque o pool de conexões do
    urllib3 por baixo do requests.Session já é thread-safe.
    """
    dir_raw = Path(dir_raw)
    dir_raw.mkdir(parents=True, exist_ok=True)
    sessao = criar_sessao()

    combinacoes = [(uf, modalidade) for uf in ufs for modalidade in modalidades]

    registros = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futuros = {
            executor.submit(coletar_fatia, sessao, uf, modalidade, data_ini,
                             data_fim, dir_raw, tamanho): (uf, modalidade)
            for uf, modalidade in combinacoes
        }
        for futuro in as_completed(futuros):
            uf, modalidade = futuros[futuro]
            try:
                registros.extend(futuro.result())
            except Exception:
                logger.exception("falha inesperada em %s/mod%s", uf, modalidade)

    logger.info("coleta concluída: %s registros brutos", len(registros))
    return registros


def carregar_bruto(dir_raw):
    """Relê os arquivos brutos do disco, sem tocar na API.

    É o que permite reprocessar o tratamento em segundos durante o
    desenvolvimento, em vez de esperar a coleta inteira de novo.
    """
    dir_raw = Path(dir_raw)
    registros = []
    for arquivo in sorted(dir_raw.glob("*.json")):
        payload = json.loads(arquivo.read_text(encoding="utf-8"))
        registros.extend(payload["data"])
    logger.info("%s registros relidos de %s", len(registros), dir_raw)
    return registros
