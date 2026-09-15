# Alerta de Licitações  Saúde Pública (PNCP)

Automação que varre o Portal Nacional de Contratações Públicas (PNCP), identifica
licitações relevantes para um fornecedor de equipamentos e serviços de tecnologia
para saúde pública, e separa o que merece atenção comercial do que é ruído.

De **8.554 licitações reais** analisadas numa janela de 7 dias, o filtro aponta
**299 oportunidades** (3,5%) e isola **157 casos ambíguos** para revisão humana.

Uma execução produz duas entregas prontas para uso:
[`output/oportunidades.xlsx`](output/oportunidades.xlsx) e
[`output/alerta.html`](output/alerta.html).

---

## O pipeline

```
API do PNCP  ──>  data/raw/*.json  ──>  tabela tratada  ──>  filtro  ──>  SQLite
                  (bruto, intocado)                                        │
                                                                           ├──>  oportunidades.xlsx
                                                                           └──>  alerta.html
```

| Etapa | Onde |
|---|---|
| Coleta paginada, com retry e persistência do bruto | [`src/coleta/pncp_client.py`](src/coleta/pncp_client.py) |
| Achatamento, tipagem e deduplicação | [`src/tratamento/parser.py`](src/tratamento/parser.py) |
| Filtro de relevância por assunto e corte por valor mínimo | [`src/tratamento/filtro.py`](src/tratamento/filtro.py) |
| Pontuação de prioridade comercial | [`src/tratamento/pontuacao.py`](src/tratamento/pontuacao.py) |
| Persistência estruturada em SQLite | [`src/persistencia/banco.py`](src/persistencia/banco.py) |
| Planilha `.xlsx` | [`src/entregas/planilha.py`](src/entregas/planilha.py) |
| E-mail de alerta HTML | [`src/entregas/email_html.py`](src/entregas/email_html.py) |

---

## Como executar do zero

```bash
git clone <url-do-repositorio>
cd Desafio_ray

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python main.py
```

A API do PNCP é pública e não exige autenticação  **não há chave, senha ou
`.env` para configurar**. O requisito de "nenhuma credencial commitada" é
atendido por construção.

### Opções

```bash
python main.py                            # coleta a janela padrão (7 dias) e gera tudo
python main.py --dias 30                  # janela maior
python main.py --reprocessar data/raw/exemplo      # relê o disco, sem tocar na API
python main.py --saida entregas_semana    # outro diretório para .xlsx e .html
python main.py --destaques 20             # quantas oportunidades o e-mail mostra
```

**Para ver o projeto funcionando em 1 segundo, sem esperar a coleta:**

```bash
python main.py --reprocessar data/raw/exemplo
```

Isso usa a amostra versionada no repositório e gera as duas entregas em
`output/`. Ao final, o terminal imprime onde cada arquivo foi gravado.

O `--reprocessar` existe por um motivo prático: uma coleta de 7 dias são 175
requisições à API  minutos de espera, mesmo com as fatias rodando em paralelo.
Reprocessar o bruto já salvo leva **1 segundo**. Todo o ajuste das palavras-chave
foi feito por essa rota.

> **Se `python3 -m venv` falhar** com "ensurepip is not available" (comum em
> Debian/Ubuntu/WSL), instale `apt install python3-venv` ou crie o ambiente com
> `python3 -m venv --without-pip .venv` e instale o pip dentro dele via
> [get-pip.py](https://bootstrap.pypa.io/get-pip.py).

---

## Estrutura do projeto

```
Desafio_ray/
├── main.py                     Orquestra o pipeline; --reprocessar pula a API
├── config.py                   TODA a regra de negócio: UFs, modalidades, janela,
│                               pesos da pontuação e as 4 listas de palavras-chave
├── requirements.txt
├── src/
│   ├── coleta/
│   │   └── pncp_client.py      Requisições, paginação, retry, gravação do bruto
│   ├── tratamento/
│   │   ├── parser.py           JSON aninhado -> tabela plana, tipada, sem duplicatas
│   │   ├── filtro.py           Classificação por assunto (aprovado/revisar/descartado)
│   │   │                       e corte por valor mínimo
│   │   └── pontuacao.py        Ordena as aprovadas por prioridade comercial
│   ├── persistencia/
│   │   └── banco.py            SQLite: UPSERT por id_pncp, histórico entre execuções
│   └── entregas/
│       ├── planilha.py         .xlsx com 3 abas, formatado para uso direto
│       └── email_html.py       E-mail de alerta, CSS inline, texto escapado
├── data/
│   ├── raw/                    JSON bruto, um arquivo por página, sem transformação
│   │   └── exemplo/            amostra versionada
│   └── processed/              licitacoes.db (gerado; fora do controle de versão)
└── output/                     oportunidades.xlsx e alerta.html
```

A separação não é enfeite: as três partes mudam por razões diferentes. A coleta
muda quando o PNCP altera a API (raro); o filtro muda toda semana conforme o time
comercial refina as palavras-chave; as entregas mudam quando o cliente quer outro
formato. Manter o filtro isolado também permite testá-lo com dados de disco, sem
rede  e foi o que tornou viável iterar cinco vezes sobre as palavras-chave.

---

## Como o filtro foi definido

O perfil do cliente tem três critérios, e cada um é aplicado num ponto diferente
do pipeline  não por acaso, mas porque agir cedo custa menos:

| Critério | Onde é aplicado | Por que ali |
|---|---|---|
| **UF** (PE, BA, CE, SP, MG) | na **chamada à API**, via parâmetro `uf` | A API filtra na origem. Baixar o Brasil inteiro para descartar 22 estados depois seria desperdiçar minutos de rede a cada execução. |
| **Assunto** (palavras-chave) | em memória, [`filtro.py`](src/tratamento/filtro.py) | A API **não tem busca por texto**. Não há alternativa: o objeto da contratação precisa ser analisado no nosso código. |
| **Valor mínimo** (R$ 100.000) | em memória, depois do assunto | A API também não filtra por valor. Fica depois do assunto para que a evidência registre *os dois* motivos quando ambos se aplicam. |

O resto desta seção trata do critério difícil: o de assunto. As listas **não
foram escritas por suposição**. Coletei primeiro um corpus de 8.554 licitações
reais (5 UFs, modalidades 6 e 8, 175 páginas) e desenhei as regras medindo contra
ele.

### Descoberta 1  casamento por substring é inutilizável

A abordagem ingênua (`if palavra in texto`) produz desastres silenciosos.
Medido no corpus:

| Termo buscado | Casou dentro de | Falsos positivos |
|---|---|---|
| `ubs` | s**ubs**crição Oracle | 113 |
| `uti` | hortifr**uti**, **uti**lização | 219 |
| `upa` | ro**upa** de aproximação | 49 |
| `sistema` | **Sistema** de Registro de Preços | centenas |

`Sistema de Registro de Preços` é o mecanismo de compra usado em boa parte dos
editais brasileiros  nada a ver com software. Por isso o filtro casa por
**palavra inteira** (fronteira regex), e `sistema` foi substituído por formas
qualificadas: `sistema de gestão`, `sistema informatizado`, `sistema de informação`.

### Descoberta 2  alguns termos do ramo são 100% enganosos

`servidor` aparece 104 vezes no corpus. **Todas** significam *servidor público*
(funcionário)  nenhuma significa servidor de rede. Fronteira de palavra não
resolve isso; só contexto resolve.

### O desenho resultante: duas dimensões

O filtro cruza **o que se compra** × **contexto de saúde**, em quatro listas
(todas em [`config.py`](config.py)):

| Lista | Tamanho | Papel |
|---|---|---|
| `PRODUTOS_INEQUIVOCOS` | 51 | Sozinhos já provam o ramo: `desfibrilador`, `prontuário eletrônico`, `tomógrafo` |
| `PRODUTOS_AMBIGUOS` | 53 | Do ramo, mas genéricos: `equipamento`, `software`, `computador`. **Só valem com contexto de saúde junto** |
| `CONTEXTO_SAUDE` | 30 | `saúde`, `hospital`, `UPA`, `SAMU`, `atenção básica`, `odontológico` |
| `EXCLUSOES` | 94 | O que o cliente não fornece |

**O contexto é buscado no objeto E no nome do órgão comprador.** Essa é a
principal arma contra falso negativo, porque o nome do órgão é um sinal
independente do texto do edital:

```
objeto: "Aquisição de Equipamentos para a Rede de Atenção Básica"
órgão:  "SECRETARIA MUNICIPAL DE SAÚDE"          -> APROVADO
```

Sem a dimensão de contexto, essa licitação seria descartada  `equipamento`
sozinho não estaria na lista, porque sozinho ele pega grupo gerador e utensílio
de cozinha.

**O impacto é mensurável:** das 299 aprovações, **185 (62%) vieram da regra
produto + contexto**. Só 114 foram capturadas por termos inequívocos. Um filtro
de uma dimensão só perderia quase dois terços das oportunidades.

### Conflito não descarta  vai para revisão

Um objeto pode casar na inclusão e na exclusão ao mesmo tempo. O caso clássico:

```
"Aquisição de ambulância equipada com equipamento médico"      -> o objeto é o VEÍCULO
"Aquisição de equipamento médico para ambulâncias do SAMU"     -> o objeto é o EQUIPAMENTO
```

As mesmas palavras, sentidos opostos. Correspondência de texto não distingue os
dois. Em vez de escolher uma regra que erra metade dos casos em silêncio, o
filtro manda os 157 conflitos para **revisão manual**, com as palavras-chave que
colidiram registradas na coluna `evidencia`.

### Rastreabilidade

Toda licitação sai do filtro com o motivo da decisão:

```
produto do ramo: equipamento medico, eletroencefalograf
produto genérico (equipamento, informatica) em contexto de saúde (saude)
produto do ramo: medico hospitalar  MAS casa em exclusão: material medico
```

Quando o time comercial discordar de um resultado, a razão está escrita. É isso
que torna o refinamento das listas um processo, e não um chute.

---

## Limitações do filtro

### Falsos positivos que permanecem

- **Laboratórios não-clínicos.** `laboratório` conta como contexto de saúde, então
  "calibração de equipamentos do Laboratório de Ensaios Tecnológicos" entra
  indevidamente.
- **Telefonia e TI genérica em órgão de saúde.** "Serviços de Telefonia Fixa e
  Móvel" para uma secretaria de saúde é aprovado; pode ou não interessar.
- **Objetos vagos.** "Aquisição de equipamentos diversos" não diz o que está
  sendo comprado. O filtro aprova pelo contexto e o valor real só aparece no
  edital anexo.

Cada exclusão da lista de 94 termos nasceu de um falso positivo **observado** no
corpus, não imaginado: ar-condicionado, equipamentos recreativos, EPIs, grupo
gerador, gases medicinais, plano de saúde, home care, e `"material químico sem
comodato de equipamentos"`  onde a negação inverte o sentido e o filtro não vê.

### Falsos negativos conhecidos

- **Negação não é tratada.** `"sem comodato de equipamentos"` é lido como
  presença do termo.
- **Lote misto.** "Equipamentos médico-hospitalares **e material de limpeza**"
  cai em revisão em vez de aprovação, porque a exclusão dispara. Preferi esse
  custo: num alerta comercial, o erro caro é o falso positivo  se o e-mail
  encher de merenda e ambulância, o time para de abri-lo.
- **Vocabulário fora da lista.** Siglas técnicas como `RIS/PACS` ou
  `sistema de laudos` aparecem pouco e podem passar batido.

### Uma limitação do dado, não do filtro

**`telemedicina`, `telessaúde` e `teleconsulta`: zero ocorrências em 8.554
licitações.** O cliente declara interesse nessa categoria, mas o PNCP praticamente
não publica com esse vocabulário na janela analisada. Os termos continuam na
lista (custo zero), mas a expectativa comercial precisa ser calibrada: essa
demanda provavelmente chega embutida em "sistema de gestão" ou "serviços de TI".

### Limitação estrutural

O filtro é correspondência literal de termos, sem semântica. Não entende
sinônimos, não lê o anexo do edital e não sabe qual item do lote é o relevante.

---

## As duas entregas

### `output/oportunidades.xlsx`

Três abas, porque três públicos diferentes olham o arquivo:

| Aba | Para quem | Conteúdo |
|---|---|---|
| **Oportunidades** | vendedor | As aprovadas, da maior para a menor prioridade. É a lista de trabalho da semana. |
| **Revisar** | analista | Os conflitos que o filtro se recusou a decidir sozinho, com as palavras-chave que colidiram. |
| **Resumo** | gestor | Quantas foram analisadas, aprovadas, descartadas; valor somado; distribuição por UF. |

A planilha é entregue **pronta para uso**, não como dump: cabeçalho congelado,
filtro automático, largura de coluna ajustada, valor em formato de moeda, data em
`dd/mm/aaaa` e o link do edital clicável.

A coluna **`Por que entrou`** aparece nas duas primeiras abas. É o que torna a
discordância útil: *"esta aqui não interessa, e o motivo que o robô deu foi
`produto genérico (equipamento) em contexto de saúde`"* é um feedback que ajusta
a lista de palavras-chave. *"O robô errou"* não é.

### `output/alerta.html`

O e-mail é a **isca**, não o relatório. Mostra os números da semana, as 10
melhores oportunidades em cartões (órgão, objeto, valor, prazo e link) e manda o
resto para a planilha. Um e-mail com 299 linhas não é lido; um com as 10 mais
relevantes e o total, sim.

Duas restrições moldaram a implementação:

- **Cliente de e-mail não é navegador.** Gmail e Outlook removem `<style>` e
  ignoram flexbox e grid. O layout é feito com `<table>` aninhada e todo o CSS
  vai inline. É deselegante de escrever e é o que renderiza igual em todo lugar.
- **Todo texto vem da API.** `objeto` e `orgao` são campos livres preenchidos por
  servidores de milhares de prefeituras. Tudo passa por `html.escape` antes de
  entrar no template — sem isso, um `<` no texto de um edital quebraria o layout,
  e um edital malicioso injetaria HTML no e-mail de todo mundo.

> **O e-mail é gerado como arquivo, não enviado.** Enviar de verdade exigiria
> host, usuário e senha de SMTP, e o enunciado proíbe credenciais no repositório.
> O entregável pedido é o `.html` de exemplo; o envio seria uma chamada de
> `smtplib` lendo variáveis de ambiente, e preferi não adicionar código que não
> consigo demonstrar rodando.

---

## Decisões técnicas e porquês

### Por que SQLite e não CSV para o dado tratado

O enunciado permite banco **ou** arquivo estruturado, pedindo justificativa. Optei
pelo banco por uma razão específica do problema: **a entrega é um alerta
periódico**.

Execuções sucessivas cobrem janelas de data que se sobrepõem — rodar toda
segunda-feira com janela de 7 dias significa reencontrar as mesmas licitações
várias vezes. Com `id_pncp` como chave primária, o `INSERT ... ON CONFLICT DO
UPDATE` resolve a duplicidade **entre execuções** sem custo nenhum. Um CSV
exigiria reler e reconciliar o arquivo inteiro a cada rodada, reimplementando à
mão o que o banco já faz.

O ganho concreto está na coluna `vista_em`, que guarda a **primeira** aparição de
cada licitação e nunca é sobrescrita. É ela que permite responder *"o que é novo
desde a semana passada"* — que é a pergunta que um alerta periódico existe para
responder. Com CSV, essa informação simplesmente não existiria.

**SQLite e não Postgres** porque é biblioteca padrão do Python: zero dependências
a instalar, zero servidor a subir, e o banco inteiro é um arquivo. Para um volume
de milhares de linhas por semana, um servidor de banco seria infraestrutura sem
contrapartida. Se o projeto crescesse para múltiplos clientes com escrita
concorrente, aí sim a troca se justificaria.

O banco recebe a **tabela inteira**, não só as aprovadas. O descartado de hoje é a
evidência de por que o filtro decidiu assim, quando alguém questionar amanhã.

### Por que JSON e não CSV para o dado bruto

O enunciado permite os dois, mas exige o retorno **sem transformação**. O retorno
do PNCP tem objetos aninhados (`orgaoEntidade`, `unidadeOrgao`, `amparoLegal`).
CSV só aceita tabela plana  salvar em CSV exigiria achatar a estrutura na hora
da coleta, e achatar *é* uma transformação. Salvamos JSON idêntico ao recebido e
achatamos depois, no tratamento, onde achatar é o trabalho esperado.

### Por que um arquivo por página

```
data/raw/2026-09-13/SP_mod8_pag042.json
```

Três motivos: **rastreabilidade** (dá para abrir e ver o que a API devolveu
naquela fatia exata); **resiliência** (se a coleta cair na página 200, as 199
anteriores estão no disco); e **reprocessamento** (ajustar o filtro sem esperar
12 minutos de rede).

### Como a duplicidade é evitada

`numeroControlePNCP` é o identificador único do próprio PNCP  não uma
combinação improvisada de campos. A deduplicação acontece em duas camadas, porque
são dois problemas diferentes:

| Camada | Onde | Resolve |
|---|---|---|
| `drop_duplicates` | [`parser.py`](src/tratamento/parser.py) | A mesma contratação caindo em mais de uma fatia **da mesma coleta** |
| `ON CONFLICT DO UPDATE` | [`banco.py`](src/persistencia/banco.py) | A mesma contratação reaparecendo **entre execuções**, por sobreposição de janela |

A primeira sozinha não bastaria: ela só enxerga a rodada atual. A segunda sozinha
funcionaria, mas faria o banco trabalhar à toa com milhares de linhas repetidas
que já dava para descartar em memória.

### Como os erros são tratados

- **Retry com backoff exponencial** (1s, 2s, 4s, 8s, 16s) para 429 e 5xx. Sem
  isso, uma coleta de centenas de requisições quase sempre morre por um erro
  passageiro.
- **Falha isolada por fatia**: se uma combinação UF × modalidade falhar mesmo
  após os retries, ela é registrada no log e abandonada  as outras continuam.
  Esse mesmo `except` cobre a fatia sem resultados, porque o `JSONDecodeError`
  do corpo vazio é subclasse de `RequestException` (ver Dificuldades).
- **Parada pela lista de dados**, não pelo código de status: o loop encerra
  quando `data` vem vazio ou quando `totalPaginas` é alcançado.

### Janela e modalidades padrão

Padrão de **7 dias** e modalidades **6 (Pregão Eletrônico)** e **8 (Dispensa)**,
configuráveis em `config.py`. As modalidades 4 (Concorrência) e 9
(Inexigibilidade) ficaram de fora do padrão porque dobram o tempo de coleta.
**Essa é uma decisão de custo, não uma medição**  não avaliei quantas
oportunidades relevantes vivem nelas, e essa verificação é um próximo passo
óbvio antes de considerar o padrão definitivo.

---

## Dificuldades encontradas

**1. A API sinaliza ausência de resultados com `HTTP 204` e corpo vazio**, não com
`200` e lista vazia. Verificado nos dois casos: página além da última e página 1
de uma fatia sem nenhum resultado  ambas respondem `204` com 0 bytes. Chamar
`.json()` nessa resposta estoura `JSONDecodeError`.

A saída escolhida **não** foi checar o status. O loop lê `totalPaginas` da
primeira resposta e para nele, então nunca pede uma página além do fim  o caso
mais comum do 204 simplesmente não acontece. Resta a fatia completamente vazia,
e aí o `JSONDecodeError` é subclasse de `RequestException`, então cai no mesmo
tratamento de falha por fatia que já existe: registra no log e abandona **só
aquela** combinação UF × modalidade, sem derrubar as outras.

A condição de parada é `len(payload["data"]) == 0 or pagina >= total_paginas` 
o array, não o código de status. A vantagem é não depender de um detalhe de
protocolo que a documentação do PNCP não promete; a desvantagem é que uma fatia
vazia aparece no log como erro, e não como "nenhum resultado".

**2. `tamanhoPagina` tem mínimo *e* máximo.** Abaixo de 10 a API responde
`400  "must be greater than or equal to 10"`; acima de 50, `400  "Tamanho de
página inválido"`. O mínimo não é documentado de forma evidente; foi descoberto
na prática.

**3. `codigoModalidadeContratacao` é obrigatório e aceita um único valor por
chamada.** Isso transforma a coleta num produto cartesiano UF × modalidade ×
página  a razão de o volume crescer tão rápido.

**4. Volume.** 7 dias × 5 UFs × 2 modalidades = 175 páginas. Em sequência isso
levava ~12 minutos, e uma janela de 30 dias passaria de 700 páginas. A solução
foi paralelizar por fatia: como cada combinação UF × modalidade é independente
(arquivos próprios, sem estado compartilhado) e o gargalo é espera de rede e não
CPU, um `ThreadPoolExecutor` faz o tempo total virar o da fatia mais lenta em vez
da soma de todas. A `Session` é compartilhada entre as threads porque o pool de
conexões do `urllib3` por baixo do `requests` já é thread-safe.

**5. `valorTotalEstimado` vem `null` *e* vem `0.00`.** O caso do zero é o
traiçoeiro: não é capturado por `isna()`, então passa direto pela verificação de
nulo e reprova no corte de valor mínimo, sumindo em silêncio. Um dos registros
com `0.00` era "Filmes Radiológicos com Equipamentos em Regime de Comodato" 
exatamente o tipo de contrato que interessa ao cliente.

**6. Acentuação.** Sem normalizar, `prontuário` nunca casa com `prontuario`. Pior:
`médico-hospitalar` e `médico hospitalar`  que aparecem 47 e 70 vezes no corpus
 seriam textos diferentes. A normalização converte pontuação em espaço, o que
faz as duas grafias virarem a mesma coisa.

**7. HTML de e-mail é uma tecnologia parada em 2005.** Gmail e Outlook descartam
a tag `<style>` e não suportam flexbox nem grid  o layout precisa ser feito com
`<table>` aninhada e CSS inline em cada elemento. Descobrir isso depois de já ter
escrito o template com CSS moderno custou uma reescrita inteira.

**8. O driver do `sqlite3` não aceita tipos do NumPy.** `numpy.int64`,
`numpy.bool_` e `numpy.float64` vêm direto do DataFrame e estouram
`InterfaceError: Error binding parameter`. O mesmo vale para `pd.Timestamp` e
`pd.NaT`. Cada valor precisa passar por uma conversão explícita para tipo nativo
do Python antes de ir para o banco  o `.item()` dos escalares do NumPy resolve,
mas só depois de tratar `NaT` e `NaN` separadamente, porque eles sobrevivem à
conversão e viram lixo no lugar de `NULL`.

---

## Capturas de tela

### Planilha  aba *Oportunidades*

![Planilha gerada](docs/planilha.png)

### E-mail de alerta

![E-mail de alerta](docs/email.png)

---

## O que faria diferente com mais tempo

- **Busca semântica por embeddings** no lugar de correspondência literal.
  Resolveria sinônimos, siglas e o problema da negação, e capturaria
  "RIS/PACS" ou "sistema de laudos" sem precisar antecipar cada grafia.
- **Coleta incremental** usando o `vista_em` do banco para consultar só o
  intervalo ainda não coberto, em vez de rebaixar a janela inteira toda vez. A
  estrutura para isso já existe; faltou o recorte na chamada da API.
- **Separar "novas" de "já vistas" no alerta.** O banco já sabe quais licitações
  são inéditas (`vista_em` = hoje), mas o e-mail ainda mostra todas as aprovadas.
  Destacar só o que mudou desde a última execução é o próximo passo óbvio de um
  alerta periódico  e o de maior retorno para quem recebe.
- **Classificar o lote, não o edital.** A API tem endpoints de itens; descer a
  esse nível resolveria o caso do lote misto, hoje a maior fonte de falso negativo.
- **Painel de refinamento** para o time comercial marcar aprovações erradas,
  alimentando as listas com rótulos reais em vez de inspeção manual.
- **Testes automatizados** do filtro com um conjunto fixo de objetos rotulados,
  para que refinar uma keyword não quebre outra silenciosamente.
