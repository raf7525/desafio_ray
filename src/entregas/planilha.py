"""Entrega 1: planilha .xlsx pronta para o time comercial.

A planilha não é um dump do DataFrame. Ela tem três abas com públicos
diferentes: `Oportunidades` é a lista de trabalho do vendedor, ordenada por
prioridade; `Revisar` são os conflitos que o filtro se recusou a decidir
sozinho (ver filtro.py); `Resumo` é o número agregado para quem só quer saber
o tamanho da semana.

A coluna `Por que entrou` viaja junto em todas as abas. É ela que permite ao
time discordar do filtro de forma útil — "esta aqui não interessa, e o motivo
que o robô deu foi X" é um feedback acionável; "o robô errou" não é.
"""

import logging
from pathlib import Path

import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

logger = logging.getLogger(__name__)

CAMINHO_PADRAO = Path("output/oportunidades.xlsx")

# Ordem de leitura do vendedor: primeiro a prioridade e onde é, depois quem
# compra e o que compra, depois valor e prazos, e por último a rastreabilidade.
COLUNAS = {
    "pontuacao": "Pontuação",
    "uf": "UF",
    "municipio": "Município",
    "orgao": "Órgão",
    "unidade": "Unidade",
    "objeto": "Objeto da contratação",
    "valor_estimado": "Valor estimado",
    "modalidade": "Modalidade",
    "situacao": "Situação",
    "data_publicacao": "Publicação",
    "data_abertura": "Abertura das propostas",
    "data_encerramento": "Encerramento",
    "processo": "Processo",
    "id_pncp": "ID PNCP",
    "link": "Link do edital",
    "evidencia": "Por que entrou",
}

LARGURAS = {
    "Pontuação": 11, "UF": 6, "Município": 20, "Órgão": 38, "Unidade": 34,
    "Objeto da contratação": 70, "Valor estimado": 18, "Modalidade": 22,
    "Situação": 16, "Publicação": 13, "Abertura das propostas": 13,
    "Encerramento": 13, "Processo": 18, "ID PNCP": 26,
    "Link do edital": 42, "Por que entrou": 55,
}

FORMATO_MOEDA = 'R$ #,##0.00'
FORMATO_DATA = "DD/MM/YYYY"

PREENCHIMENTO_CABECALHO = PatternFill("solid", fgColor="1F3A5F")
FONTE_CABECALHO = Font(bold=True, color="FFFFFF", size=11)
FONTE_LINK = Font(color="0563C1", underline="single")


def _preparar(df):
    """Seleciona e renomeia as colunas de saída, na ordem de COLUNAS."""
    if df.empty:
        return pd.DataFrame(columns=list(COLUNAS.values()))
    presentes = [c for c in COLUNAS if c in df.columns]
    return df[presentes].rename(columns=COLUNAS)


def _formatar(planilha, tabela):
    """Cabeçalho, larguras, formatos numéricos, congelamento e filtro."""
    if tabela.empty:
        return

    planilha.freeze_panes = "A2"
    planilha.auto_filter.ref = planilha.dimensions
    planilha.row_dimensions[1].height = 28

    for indice, nome in enumerate(tabela.columns, start=1):
        letra = get_column_letter(indice)
        planilha.column_dimensions[letra].width = LARGURAS.get(nome, 18)

        celula = planilha.cell(row=1, column=indice)
        celula.fill = PREENCHIMENTO_CABECALHO
        celula.font = FONTE_CABECALHO
        celula.alignment = Alignment(horizontal="center", vertical="center",
                                     wrap_text=True)

        if nome == "Valor estimado":
            formato = FORMATO_MOEDA
        elif nome in ("Publicação", "Abertura das propostas", "Encerramento"):
            formato = FORMATO_DATA
        elif nome == "Pontuação":
            formato = "0.0"
        else:
            formato = None

        # O objeto é longo; quebrar a linha é o que torna a planilha legível
        # sem o vendedor precisar alargar a coluna na mão.
        quebra = nome in ("Objeto da contratação", "Por que entrou", "Órgão",
                          "Unidade")

        for linha in range(2, len(tabela) + 2):
            celula = planilha.cell(row=linha, column=indice)
            if formato:
                celula.number_format = formato
            celula.alignment = Alignment(vertical="top", wrap_text=quebra)
            if nome == "Link do edital" and isinstance(celula.value, str) \
                    and celula.value.startswith("http"):
                celula.hyperlink = celula.value
                celula.font = FONTE_LINK


def _montar_resumo(analisadas, aprovados, revisar, config):
    """Devolve (tabela, linhas_monetarias) — as linhas de valor precisam do
    formato de moeda aplicado depois, já que a coluna mistura número e texto."""
    soma = aprovados["valor_estimado"].sum() if not aprovados.empty else 0

    linhas = [
        ("Licitações analisadas", len(analisadas)),
        ("Oportunidades aprovadas", len(aprovados)),
        ("Para revisão manual", len(revisar)),
        ("Descartadas", len(analisadas) - len(aprovados) - len(revisar)),
        ("", ""),
        ("Valor estimado somado (aprovadas)", soma),
        ("Valor mínimo de interesse", config.VALOR_MINIMO),
        ("", ""),
        ("UFs consultadas", ", ".join(config.UFS)),
        ("Modalidades consultadas", ", ".join(str(m) for m in config.MODALIDADES)),
    ]
    monetarias = {5, 6}  # índices de "Valor estimado somado" e "Valor mínimo"

    if not aprovados.empty:
        linhas += [("", ""), ("Aprovadas por UF", "")]
        linhas += list(aprovados["uf"].value_counts().items())
        linhas += [("", ""),
                   ("Aprovadas em capital", int(aprovados["eh_capital"].sum()))]

    return pd.DataFrame(linhas, columns=["Indicador", "Valor"]), monetarias


def gerar(analisadas, aprovados, revisar, config, caminho=CAMINHO_PADRAO):
    """Escreve a planilha com as três abas. Devolve o caminho gravado."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)

    tabela_resumo, monetarias = _montar_resumo(analisadas, aprovados, revisar,
                                               config)
    abas = {
        "Oportunidades": _preparar(aprovados),
        "Revisar": _preparar(revisar),
    }

    with pd.ExcelWriter(caminho, engine="openpyxl",
                        datetime_format=FORMATO_DATA) as escritor:
        for nome, tabela in abas.items():
            tabela.to_excel(escritor, sheet_name=nome, index=False)
            _formatar(escritor.sheets[nome], tabela)

        tabela_resumo.to_excel(escritor, sheet_name="Resumo", index=False)
        resumo = escritor.sheets["Resumo"]
        resumo.column_dimensions["A"].width = 36
        resumo.column_dimensions["B"].width = 26
        for celula in resumo[1]:
            celula.fill = PREENCHIMENTO_CABECALHO
            celula.font = FONTE_CABECALHO
        # +2: uma pela linha de cabeçalho, outra porque o Excel conta de 1.
        for posicao in monetarias:
            resumo.cell(row=posicao + 2, column=2).number_format = FORMATO_MOEDA

    logger.info("planilha gravada: %s (%s oportunidades, %s para revisão)",
                caminho, len(aprovados), len(revisar))
    return caminho
