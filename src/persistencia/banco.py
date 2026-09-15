"""Persistência do resultado tratado em SQLite.

Por que banco e não CSV: o enunciado permite os dois, mas a entrega é um
alerta PERIÓDICO. Execuções sucessivas cobrem janelas de data que se
sobrepõem, então a mesma licitação volta várias vezes. Com `id_pncp` como
chave primária, o UPSERT resolve a duplicidade entre execuções sem custo —
um CSV exigiria reler e reconciliar o arquivo inteiro a cada rodada.

Além disso o banco guarda `vista_em`, a data em que a licitação apareceu pela
primeira vez. É esse campo que permite responder "o que é novo desde a semana
passada", que é a pergunta que um alerta periódico existe para responder.

SQLite e não Postgres porque é biblioteca padrão do Python: zero dependências,
zero servidor, o banco inteiro é um arquivo que acompanha o repositório.
"""

import logging
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

CAMINHO_PADRAO = Path("data/processed/licitacoes.db")

TABELA = "licitacoes"

# Ordem fixa: é a mesma do INSERT e do CREATE TABLE.
COLUNAS = [
    "id_pncp", "objeto", "valor_estimado", "modalidade", "situacao",
    "data_publicacao", "data_abertura", "data_encerramento", "link",
    "processo", "orgao", "cnpj_orgao", "uf", "municipio", "unidade",
    "destino", "evidencia", "eh_capital", "pontuacao",
]

ESQUEMA = f"""
CREATE TABLE IF NOT EXISTS {TABELA} (
    id_pncp           TEXT PRIMARY KEY,
    objeto            TEXT,
    valor_estimado    REAL,
    modalidade        TEXT,
    situacao          TEXT,
    data_publicacao   TEXT,
    data_abertura     TEXT,
    data_encerramento TEXT,
    link              TEXT,
    processo          TEXT,
    orgao             TEXT,
    cnpj_orgao        TEXT,
    uf                TEXT,
    municipio         TEXT,
    unidade           TEXT,
    destino           TEXT,
    evidencia         TEXT,
    eh_capital        INTEGER,
    pontuacao         REAL,
    vista_em          TEXT NOT NULL,
    atualizada_em     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_destino   ON {TABELA}(destino);
CREATE INDEX IF NOT EXISTS idx_uf        ON {TABELA}(uf);
CREATE INDEX IF NOT EXISTS idx_pontuacao ON {TABELA}(pontuacao DESC);
CREATE INDEX IF NOT EXISTS idx_vista_em  ON {TABELA}(vista_em);
"""


def conectar(caminho=CAMINHO_PADRAO):
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    conexao = sqlite3.connect(caminho)
    conexao.executescript(ESQUEMA)
    return conexao


def _valor_sqlite(valor):
    """Converte um valor do pandas para um tipo que o driver sqlite3 aceita."""
    if valor is None or valor is pd.NaT:
        return None
    if isinstance(valor, float) and pd.isna(valor):
        return None
    if isinstance(valor, pd.Timestamp):
        return valor.isoformat()
    # numpy.bool_ / numpy.int64 / numpy.float64 não são aceitos pelo driver.
    if hasattr(valor, "item"):
        return valor.item()
    return valor


def salvar(df, caminho=CAMINHO_PADRAO):
    """Grava o DataFrame tratado, atualizando o que já existe.

    Devolve (novas, atualizadas). Colunas ausentes no DataFrame entram como
    NULL — `pontuacao` só existe para as aprovadas, por exemplo.
    """
    if df.empty:
        logger.info("nada a persistir: DataFrame vazio")
        return 0, 0

    agora = datetime.now().isoformat(timespec="seconds")

    with closing(conectar(caminho)) as conexao, conexao:
        existentes = {
            linha[0] for linha in conexao.execute(f"SELECT id_pncp FROM {TABELA}")
        }

        presentes = [c for c in COLUNAS if c in df.columns]
        ausentes = [c for c in COLUNAS if c not in df.columns]

        campos = presentes + ["vista_em", "atualizada_em"]
        marcadores = ", ".join("?" * len(campos))
        # vista_em preserva a primeira aparição; só atualizada_em avança.
        atualizacoes = ", ".join(
            f"{c}=excluded.{c}" for c in presentes[1:] + ["atualizada_em"]
        )
        sql = (
            f"INSERT INTO {TABELA} ({', '.join(campos)}) VALUES ({marcadores}) "
            f"ON CONFLICT(id_pncp) DO UPDATE SET {atualizacoes}"
        )

        linhas = [
            tuple(_valor_sqlite(registro[c]) for c in presentes) + (agora, agora)
            for registro in df[presentes].to_dict("records")
        ]
        conexao.executemany(sql, linhas)

    ids = set(df["id_pncp"])
    novas = len(ids - existentes)
    atualizadas = len(ids & existentes)

    if ausentes:
        logger.debug("colunas gravadas como NULL: %s", ausentes)
    logger.info(
        "banco %s: %s novas, %s atualizadas", Path(caminho).name, novas, atualizadas
    )
    return novas, atualizadas


def carregar(caminho=CAMINHO_PADRAO, destino=None):
    """Relê o que está no banco, opcionalmente só um destino."""
    with closing(conectar(caminho)) as conexao:
        sql = f"SELECT * FROM {TABELA}"
        parametros = ()
        if destino:
            sql += " WHERE destino = ?"
            parametros = (destino,)
        sql += " ORDER BY pontuacao DESC"
        return pd.read_sql_query(sql, conexao, params=parametros)


def resumo(caminho=CAMINHO_PADRAO):
    """Contagem por destino — usada para mostrar o acumulado entre execuções."""
    with closing(conectar(caminho)) as conexao:
        return dict(
            conexao.execute(
                f"SELECT destino, COUNT(*) FROM {TABELA} GROUP BY destino"
            )
        )
