"""Entrega 2: e-mail de alerta em HTML.

Três restrições moldaram o formato:

1. **Cliente de e-mail não é navegador.** Gmail e Outlook removem `<style>`,
   ignoram flexbox e grid. Por isso o layout é feito com `<table>` aninhada e
   TODO o CSS vai inline, como se fosse 2005. É feio de escrever e é o que
   funciona.

2. **O alerta é uma isca, não o relatório.** O e-mail mostra as melhores
   oportunidades e manda o resto para a planilha. Um e-mail com 299 linhas não
   é lido; um com as 10 mais relevantes e o número total é.

3. **Todo texto vem da API.** `objeto` e `orgao` são campos livres preenchidos
   por servidores de milhares de prefeituras. Tudo passa por `html.escape`
   antes de entrar no template — sem isso, um `<` no texto de um edital
   quebraria o layout, e um edital malicioso injetaria HTML no e-mail.
"""

import html
import logging
from datetime import date
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

CAMINHO_PADRAO = Path("output/alerta.html")
TOTAL_DESTAQUES = 10

AZUL = "#1f3a5f"
AZUL_CLARO = "#eaf0f7"
CINZA_TEXTO = "#3c4858"
CINZA_FRACO = "#7b8794"
BORDA = "#dde3ea"
VERDE = "#1e7a4b"


def _moeda(valor):
    """R$ no padrão brasileiro, sem depender de locale instalado no sistema."""
    if valor is None or pd.isna(valor) or valor <= 0:
        return "valor não informado"
    inteiro = f"{valor:,.2f}"
    return "R$ " + inteiro.replace(",", "#").replace(".", ",").replace("#", ".")


def _data(valor):
    if valor is None or pd.isna(valor):
        return "não informada"
    return pd.Timestamp(valor).strftime("%d/%m/%Y")


def _escapar(valor):
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ""
    return html.escape(str(valor))


def _cartao(registro):
    """Um bloco de oportunidade. Tabela e CSS inline por exigência do e-mail."""
    objeto = " ".join(_escapar(registro.get("objeto")).split())
    if len(objeto) > 260:
        objeto = objeto[:260].rsplit(" ", 1)[0] + "…"

    orgao = _escapar(registro.get("orgao"))
    municipio = _escapar(registro.get("municipio"))
    uf = _escapar(registro.get("uf"))
    local = f"{municipio}/{uf}" if municipio else uf
    if registro.get("eh_capital"):
        local += " · capital"

    link = _escapar(registro.get("link") or "")
    botao = ""
    if link.startswith("http"):
        botao = (
            f'<a href="{link}" style="display:inline-block;padding:8px 16px;'
            f'background:{AZUL};color:#ffffff;text-decoration:none;'
            f'border-radius:4px;font-size:13px;font-weight:bold;">'
            f'Ver edital no portal de origem</a>'
        )

    return f"""
      <tr>
        <td style="padding:18px 24px;border-bottom:1px solid {BORDA};">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
            <tr>
              <td style="font-size:12px;color:{CINZA_FRACO};padding-bottom:6px;">
                <span style="background:{AZUL_CLARO};color:{AZUL};padding:3px 8px;
                      border-radius:3px;font-weight:bold;">{local}</span>
                &nbsp;prioridade {registro.get('pontuacao', 0):.0f}
              </td>
            </tr>
            <tr>
              <td style="font-size:15px;font-weight:bold;color:{AZUL};padding-bottom:4px;">
                {orgao}
              </td>
            </tr>
            <tr>
              <td style="font-size:14px;color:{CINZA_TEXTO};line-height:1.5;padding-bottom:10px;">
                {objeto}
              </td>
            </tr>
            <tr>
              <td style="font-size:13px;color:{CINZA_TEXTO};padding-bottom:12px;">
                <strong style="color:{VERDE};font-size:15px;">
                  {_moeda(registro.get('valor_estimado'))}</strong><br>
                Propostas até <strong>{_data(registro.get('data_encerramento'))}</strong>
                &nbsp;·&nbsp; {_escapar(registro.get('modalidade'))}
              </td>
            </tr>
            <tr><td>{botao}</td></tr>
          </table>
        </td>
      </tr>"""


def _indicador(numero, rotulo, cor):
    return f"""
      <td align="center" style="padding:14px 8px;">
        <div style="font-size:26px;font-weight:bold;color:{cor};">{numero}</div>
        <div style="font-size:11px;color:{CINZA_FRACO};text-transform:uppercase;
             letter-spacing:.5px;">{rotulo}</div>
      </td>"""


def gerar(analisadas, aprovados, revisar, config, caminho=CAMINHO_PADRAO,
          destaques=TOTAL_DESTAQUES):
    """Escreve o e-mail de alerta. Devolve o caminho gravado."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)

    hoje = date.today().strftime("%d/%m/%Y")
    total = _moeda(aprovados["valor_estimado"].sum() if not aprovados.empty else 0)

    cartoes = "".join(
        _cartao(registro)
        for registro in aprovados.head(destaques).to_dict("records")
    ) or f"""
      <tr><td style="padding:32px 24px;text-align:center;color:{CINZA_FRACO};
          font-size:14px;">Nenhuma oportunidade dentro do perfil nesta janela.</td></tr>"""

    restantes = max(len(aprovados) - destaques, 0)
    rodape_restantes = ""
    if restantes:
        rodape_restantes = (
            f'<p style="margin:0 0 10px;">Outras <strong>{restantes}</strong> '
            f'oportunidades estão na planilha em anexo, na aba '
            f'<strong>Oportunidades</strong>.</p>'
        )

    por_uf = ""
    if not aprovados.empty:
        itens = "".join(
            f'<span style="display:inline-block;background:{AZUL_CLARO};color:{AZUL};'
            f'padding:4px 10px;border-radius:3px;margin:0 6px 6px 0;font-size:12px;">'
            f'{_escapar(uf)} <strong>{quantidade}</strong></span>'
            for uf, quantidade in aprovados["uf"].value_counts().items()
        )
        por_uf = f'<p style="margin:0 0 10px;">Por estado: {itens}</p>'

    documento = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Alerta de licitações — {hoje}</title>
</head>
<body style="margin:0;padding:0;background:#f4f6f8;
      font-family:-apple-system,'Segoe UI',Roboto,Arial,sans-serif;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
       style="background:#f4f6f8;">
  <tr>
    <td align="center" style="padding:24px 12px;">
      <table role="presentation" width="640" cellpadding="0" cellspacing="0" border="0"
             style="max-width:640px;width:100%;background:#ffffff;border:1px solid {BORDA};
             border-radius:6px;overflow:hidden;">

        <tr>
          <td style="background:{AZUL};padding:22px 24px;">
            <div style="color:#ffffff;font-size:19px;font-weight:bold;">
              Alerta de licitações · Saúde pública
            </div>
            <div style="color:#b9c8da;font-size:13px;padding-top:4px;">
              Janela de {config.DIAS_JANELA} dias encerrada em {hoje}
              &nbsp;·&nbsp; {", ".join(config.UFS)}
            </div>
          </td>
        </tr>

        <tr>
          <td style="padding:4px 12px;border-bottom:1px solid {BORDA};">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
              <tr>
                {_indicador(len(aprovados), "oportunidades", VERDE)}
                {_indicador(len(revisar), "para revisar", "#b7791f")}
                {_indicador(len(analisadas), "analisadas", CINZA_FRACO)}
              </tr>
            </table>
          </td>
        </tr>

        <tr>
          <td style="padding:16px 24px 6px;font-size:14px;color:{CINZA_TEXTO};
              line-height:1.6;border-bottom:1px solid {BORDA};">
            Foram analisadas <strong>{len(analisadas)}</strong> contratações
            publicadas no PNCP. Destas, <strong>{len(aprovados)}</strong> se
            encaixam no perfil do cliente, somando <strong>{total}</strong> em
            valor estimado. As mais relevantes estão abaixo.
          </td>
        </tr>

        {cartoes}

        <tr>
          <td style="padding:18px 24px;font-size:13px;color:{CINZA_TEXTO};
              line-height:1.6;background:#fafbfc;">
            {rodape_restantes}
            {por_uf}
            <p style="margin:0 0 10px;">
              <strong>{len(revisar)}</strong> licitações ficaram em revisão manual:
              o texto do edital casa ao mesmo tempo com o que o cliente fornece e
              com o que ele não fornece. Estão na aba <strong>Revisar</strong> da
              planilha, com o motivo do conflito.
            </p>
            <p style="margin:0;color:{CINZA_FRACO};font-size:11px;">
              Gerado automaticamente a partir da API pública do PNCP ·
              filtro por palavras-chave sobre o objeto da contratação ·
              somente contratações acima de {_moeda(config.VALOR_MINIMO)}.
            </p>
          </td>
        </tr>

      </table>
    </td>
  </tr>
</table>
</body>
</html>
"""

    caminho.write_text(documento, encoding="utf-8")
    logger.info("e-mail gravado: %s (%s destaques de %s aprovadas)",
                caminho, min(destaques, len(aprovados)), len(aprovados))
    return caminho
