import argparse
import logging
from datetime import date
from pathlib import Path

import config
from src.coleta.pncp_client import carregar_bruto, coletar_tudo
from src.tratamento.filtro import aplicar, aplicar_valor_minimo
from src.tratamento.parser import montar_dataframe
from src.tratamento.pontuacao import calcular as calcular_pontuacao


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dias", type=int, default=config.DIAS_JANELA,
                   help=f"janela de coleta em dias (padrão: {config.DIAS_JANELA})")
    p.add_argument("--reprocessar", metavar="DIR",
                   help="relê o bruto deste diretório em vez de chamar a API")
    return p.parse_args()


def main():
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    log = logging.getLogger("pipeline")

    if args.reprocessar:
        # Reprocessar leva segundos; coletar leva minutos. Durante o ajuste das
        # palavras-chave, só esta rota é usada.
        registros = carregar_bruto(args.reprocessar)
    else:
        data_ini, data_fim = config.janela_datas(args.dias)
        dir_raw = Path("data/raw") / date.today().isoformat()
        log.info("coletando %s a %s | UFs=%s | modalidades=%s",
                 data_ini, data_fim, config.UFS, config.MODALIDADES)
        registros = coletar_tudo(config.UFS, config.MODALIDADES,
                                 data_ini, data_fim, dir_raw,
                                 config.TAMANHO_PAGINA)

    df = montar_dataframe(registros)
    log.info("tabela montada: %s licitações únicas", len(df))

    df = aplicar(df, config)
    df = aplicar_valor_minimo(df, config)

    aprovados = calcular_pontuacao(df[df.destino == "aprovado"], config)
    revisar = df[df.destino == "revisar"]
    #Gerado por IA esse trecho de código:
    print()
    print(f"{'RESULTADO DO FILTRO POR ASSUNTO':^78}")
    print("=" * 78)
    print(f"  analisadas   {len(df):>6}")
    print(f"  aprovadas    {len(aprovados):>6}  ({len(aprovados)/max(len(df),1):.1%})")
    print(f"  para revisão {len(revisar):>6}  (conflito de palavras-chave)")
    print(f"  descartadas  {len(df) - len(aprovados) - len(revisar):>6}")
    print("=" * 78)
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

    return df


if __name__ == "__main__":
    main()
