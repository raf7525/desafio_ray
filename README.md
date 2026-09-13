# Alerta de Licitações  Saúde Pública (PNCP)

Automação que varre o Portal Nacional de Contratações Públicas (PNCP), identifica
licitações relevantes para um fornecedor de equipamentos e serviços de tecnologia
para saúde pública, e separa o que merece atenção comercial do que é ruído.

De **8.554 licitações reais** analisadas numa janela de 7 dias, o filtro aponta
**299 oportunidades** (3,5%) e isola **157 casos ambíguos** para revisão humana.

---

## Estado atual

Este repositório está em construção. O que já funciona:

| Etapa | Situação |
|---|---|
| Coleta da API com paginação, retry e persistência do bruto | ✅ pronto |
| Tratamento: achatamento, tipagem, deduplicação | ✅ pronto |
| Filtro de relevância por assunto (palavras-chave) | ✅ pronto |
| Corte por valor mínimo (R$ 100.000) | ⏳ pendente |
| Persistência estruturada (SQLite) | ⏳ pendente |
| Planilha `.xlsx` e e-mail `.html` | ⏳ pendente |

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
python main.py                            # coleta a janela padrão (7 dias) e filtra
python main.py --dias 30                  # janela maior
python main.py --reprocessar data/raw/2026-09-13   # relê o disco, sem tocar na API
```

O `--reprocessar` existe por um motivo prático: a coleta de 7 dias leva
**~12 minutos** (175 requisições). Reprocessar o bruto já salvo leva **1 segundo**.
Todo o ajuste das palavras-chave foi feito por essa rota.

> **Se `python3 -m venv` falhar** com "ensurepip is not available" (comum em
> Debian/Ubuntu/WSL), instale `apt install python3-venv` ou crie o ambiente com
> `python3 -m venv --without-pip .venv` e instale o pip dentro dele via
> [get-pip.py](https://bootstrap.pypa.io/get-pip.py).

---

## Estrutura do projeto

```
Desafio_ray/
├── main.py                     Orquestra o pipeline; --reprocessar pula a API
├── config.py                   TODA a regra de negócio: UFs, modalidades,
│                               janela e as 4 listas de palavras-chave
├── requirements.txt
├── src/
│   ├── coleta/
│   │   └── pncp_client.py      Requisições, paginação, retry, gravação do bruto
│   └── tratamento/
│       ├── parser.py           JSON aninhado -> tabela plana, tipada, sem duplicatas
│       └── filtro.py           Classificação por assunto (aprovado/revisar/descartado)
├── data/
│   ├── raw/                    JSON bruto, um arquivo por página, sem transformação
│   │   └── exemplo/            amostra versionada
│   └── processed/              (reservado para a persistência estruturada)
└── output/                     (reservado para .xlsx e .html)
```

A separação não é enfeite: as três partes mudam por razões diferentes. A coleta
muda quando o PNCP altera a API (raro); o filtro muda toda semana conforme o time
comercial refina as palavras-chave; as entregas mudam quando o cliente quer outro
formato. Manter o filtro isolado também permite testá-lo com dados de disco, sem
rede  e foi o que tornou viável iterar cinco vezes sobre as palavras-chave.

---

## Como o filtro foi definido

As listas **não foram escritas por suposição**. Coletei primeiro um corpus de
8.554 licitações reais (5 UFs, modalidades 6 e 8, 175 páginas) e desenhei as
regras medindo contra ele.

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

## Decisões técnicas e porquês

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
combinação improvisada de campos. O `drop_duplicates` sobre ele está em
[`parser.py`](src/tratamento/parser.py), e é necessário porque a mesma contratação
pode cair em mais de uma fatia da coleta e porque reexecuções sobrepõem janelas
de data.

### Como os erros são tratados

- **Retry com backoff exponencial** (1s, 2s, 4s, 8s, 16s) para 429 e 5xx. Sem
  isso, uma coleta de centenas de requisições quase sempre morre por um erro
  passageiro.
- **Falha isolada por fatia**: se uma combinação UF × modalidade falhar mesmo
  após os retries, ela é registrada no log e abandonada  as outras continuam.
- **HTTP 204 tratado explicitamente** (ver Dificuldades).

### Janela e modalidades padrão

Padrão de **7 dias** e modalidades **6 (Pregão Eletrônico)** e **8 (Dispensa)**,
configuráveis em `config.py`. As modalidades 4 (Concorrência) e 9
(Inexigibilidade) ficaram de fora do padrão porque dobram o tempo de coleta.
**Essa é uma decisão de custo, não uma medição**  não avaliei quantas
oportunidades relevantes vivem nelas, e essa verificação é um próximo passo
óbvio antes de considerar o padrão definitivo.

---

## Dificuldades encontradas

**1. A API sinaliza o fim da paginação com `HTTP 204` e corpo vazio**, não com
`200` e lista vazia. Chamar `.json()` nessa resposta estoura `JSONDecodeError`.
É a armadilha menos óbvia da integração e exige checagem explícita do status.

**2. `tamanhoPagina` tem mínimo *e* máximo.** Abaixo de 10 a API responde
`400  "must be greater than or equal to 10"`; acima de 50, `400  "Tamanho de
página inválido"`. O mínimo não é documentado de forma evidente; foi descoberto
na prática.

**3. `codigoModalidadeContratacao` é obrigatório e aceita um único valor por
chamada.** Isso transforma a coleta num produto cartesiano UF × modalidade ×
página  a razão de o volume crescer tão rápido.

**4. Volume.** 7 dias × 5 UFs × 2 modalidades = 175 páginas e ~12 minutos. Uma
janela de 30 dias passaria de 700 páginas e ~50 minutos.

**5. `valorTotalEstimado` vem `null` *e* vem `0.00`.** O caso do zero é o
traiçoeiro: não é capturado por `isna()`, então passa direto pela verificação de
nulo e reprova no corte de valor mínimo, sumindo em silêncio. Um dos registros
com `0.00` era "Filmes Radiológicos com Equipamentos em Regime de Comodato" 
exatamente o tipo de contrato que interessa ao cliente.

**6. Acentuação.** Sem normalizar, `prontuário` nunca casa com `prontuario`. Pior:
`médico-hospitalar` e `médico hospitalar`  que aparecem 47 e 70 vezes no corpus
 seriam textos diferentes. A normalização converte pontuação em espaço, o que
faz as duas grafias virarem a mesma coisa.

---

## O que faria diferente com mais tempo

- **Busca semântica por embeddings** no lugar de correspondência literal.
  Resolveria sinônimos, siglas e o problema da negação, e capturaria
  "RIS/PACS" ou "sistema de laudos" sem precisar antecipar cada grafia.
- **Coleta incremental** por data da última execução, em vez de rebaixar a janela
  inteira toda vez.
- **Classificar o lote, não o edital.** A API tem endpoints de itens; descer a
  esse nível resolveria o caso do lote misto, hoje a maior fonte de falso negativo.
- **Painel de refinamento** para o time comercial marcar aprovações erradas,
  alimentando as listas com rótulos reais em vez de inspeção manual.
- **Testes automatizados** do filtro com um conjunto fixo de objetos rotulados,
  para que refinar uma keyword não quebre outra silenciosamente.
