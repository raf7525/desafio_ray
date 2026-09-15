"""Pipeline completo: coleta no PNCP -> filtro -> banco -> planilha e e-mail."""

import argparse
import logging
from datetime import date
from pathlib import Path

import config
from src.coleta.pncp_client import carregar_bruto, coletar_tudo
from src.entregas import email_html, planilha
from src.persistencia import banco
from src.tratamento.filtro import aplicar, aplicar_valor_minimo
from src.tratamento.parser import montar_dataframe
from src.tratamento.pontuacao import calcular as calcular_pontuacao


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dias", type=int, default=config.DIAS_JANELA,
                   help=f"janela de coleta em dias (padrão: {config.DIAS_JANELA})")
    p.add_argument("--reprocessar", metavar="DIR",
                   help="relê o bruto deste diretório em vez de chamar a API")
    p.add_argument("--saida", default="output", metavar="DIR",
                   help="onde gravar a planilha e o e-mail (padrão: output)")
    p.add_argument("--banco", default=banco.CAMINHO_PADRAO, metavar="ARQUIVO",
                   help=f"arquivo SQLite (padrão: {banco.CAMINHO_PADRAO})")
    p.add_argument("--destaques", type=int, default=email_html.TOTAL_DESTAQUES,
                   help="quantas oportunidades o e-mail mostra")
    return p.parse_args()


def coletar(args, log):
    if args.reprocessar:
        # Reprocessar leva segundos; coletar leva minutos. Durante o ajuste das
        # palavras-chave, só esta rota é usada.
        return carregar_bruto(args.reprocessar)

    data_ini, data_fim = config.janela_datas(args.dias)
    dir_raw = Path("data/raw") / date.today().isoformat()
    log.info("coletando %s a %s | UFs=%s | modalidades=%s",
             data_ini, data_fim, config.UFS, config.MODALIDADES)
    return coletar_tudo(config.UFS, config.MODALIDADES, data_ini, data_fim,
                        dir_raw, config.TAMANHO_PAGINA)


def relatar(df, aprovados, revisar, novas, caminho_planilha, caminho_email):
    print()
    print(f"{'RESULTADO DO FILTRO POR ASSUNTO':^78}")
    print("=" * 78)
    print(f"  analisadas   {len(df):>6}")
    print(f"  aprovadas    {len(aprovados):>6}  ({len(aprovados)/max(len(df),1):.1%})")
    print(f"  para revisão {len(revisar):>6}  (conflito de palavras-chave)")
    print(f"  descartadas  {len(df) - len(aprovados) - len(revisar):>6}")
    print(f"  inéditas     {novas:>6}  (não estavam no banco)")
    print("=" * 78)

    if not aprovados.empty:
        print("\n  aprovadas por UF:")
        for uf, n in aprovados.uf.value_counts().items():
            print(f"    {uf}  {n}")

        print(f"\n{'  PRÉVIA DAS APROVADAS  ':=^78}\n")
        for _, r in aprovados.head(10).iterrows():
            selo_capital = " · capital" if r.eh_capital else ""
            print(f"  {r.uf}{selo_capital} · pontuação {r.pontuacao:.1f} · "
                  f"{r.orgao[:52] if isinstance(r.orgao, str) else ''}")
            print(f"  {' '.join(str(r.objeto).split())[:74]}")
            print(f"  -> {r.evidencia[:74]}\n")

    print(f"{'  ENTREGAS GERADAS  ':=^78}")
    print(f"  planilha  {caminho_planilha}")
    print(f"  e-mail    {caminho_email}")
    print("=" * 78)


def main():
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    log = logging.getLogger("pipeline")

    registros = coletar(args, log)

    df = montar_dataframe(registros)
    log.info("tabela montada: %s licitações únicas", len(df))

    df = aplicar(df, config)
    df = aplicar_valor_minimo(df, config)

    aprovados = calcular_pontuacao(df[df.destino == "aprovado"], config)
    revisar = df[df.destino == "revisar"]

    # A pontuação só é calculada para as aprovadas, mas o banco guarda a tabela
    # inteira: o descartado de hoje é a evidência de que o filtro foi ajustado
    # quando alguém questionar a decisão amanhã.
    df = df.merge(aprovados[["id_pncp", "eh_capital", "pontuacao"]],
                  on="id_pncp", how="left")
    novas, _ = banco.salvar(df, args.banco)

    saida = Path(args.saida)
    caminho_planilha = planilha.gerar(df, aprovados, revisar, config,
                                      saida / "oportunidades.xlsx")
    caminho_email = email_html.gerar(df, aprovados, revisar, config,
                                     saida / "alerta.html",
                                     destaques=args.destaques)

    relatar(df, aprovados, revisar, novas, caminho_planilha, caminho_email)
    return df


if __name__ == "__main__":
    main()
