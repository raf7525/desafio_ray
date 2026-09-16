import logging
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

CAMINHO_PADRAO = Path("data/processed/licitacoes.db")

TABELA = "licitacoes"


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
    if valor is None or valor is pd.NaT:
        return None
    if isinstance(valor, float) and pd.isna(valor):
        return None
    if isinstance(valor, pd.Timestamp):
        return valor.isoformat()
    if hasattr(valor, "item"):
        return valor.item()
    return valor


def salvar(df, caminho=CAMINHO_PADRAO):
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
    with closing(conectar(caminho)) as conexao:
        sql = f"SELECT * FROM {TABELA}"
        parametros = ()
        if destino:
            sql += " WHERE destino = ?"
            parametros = (destino,)
        sql += " ORDER BY pontuacao DESC"
        return pd.read_sql_query(sql, conexao, params=parametros)


def resumo(caminho=CAMINHO_PADRAO):
    with closing(conectar(caminho)) as conexao:
        return dict(
            conexao.execute(
                f"SELECT destino, COUNT(*) FROM {TABELA} GROUP BY destino"
            )
        )
