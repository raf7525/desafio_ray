#Regras de negócio estão nesse arquivo, para evitar mexer na lógica se for adicionar algo
from datetime import date, timedelta

UFS = ["PE", "BA", "CE", "SP", "MG"]   
MODALIDADES = [6, 8]                   #6 = Pregão Eletrônico, 8 = Dispensa, coloquei esses tipos por serem os mais comuns
DIAS_JANELA = 7
TAMANHO_PAGINA = 50                    #aceitável de 10 até 50

VALOR_MINIMO = 100_000                 #abaixo disso a oportunidade não interessa ao cliente


CAPITAIS = {
    "PE": "Recife",
    "BA": "Salvador",
    "CE": "Fortaleza",
    "SP": "São Paulo",
    "MG": "Belo Horizonte",
}

PESO_VALOR = 10          
BONUS_UF_PRIORITARIA = 15
BONUS_CAPITAL = 20


def janela_datas(dias=None, ate=None):
    fim = ate or date.today()
    ini = fim - timedelta(days=dias or DIAS_JANELA)
    return ini.strftime("%Y%m%d"), fim.strftime("%Y%m%d")

#produtos que se tiver já são aceitos
PRODUTOS_INEQUIVOCOS = [
    # equipamento médico-hospitalar, genérico
    "equipamento medico", "equipamentos medicos", "equipamento hospitalar",
    "equipamentos hospitalares", "medico hospitalar", "medicos hospitalares",
    "medica hospitalar", "equipamento odontologic*", "equipamentos odontologic*",
    "equipamento laboratorial", "equipamentos laboratoriais",
    "instrumento odontologic*", "instrumentos odontologic*",
    "instrumental odontologic*", "instrumental cirurgic*",
    # diagnóstico por imagem
    "ultrassom", "ultrassonograf*", "tomograf*", "mamograf*", "raio x",
    "radiolog*", "ressonancia magnetica", "densitometr*", "arco cirurgico",
    # monitoração e suporte à vida
    "monitor multiparametric*", "ventilador pulmonar", "desfibrilador*",
    "cardioversor*", "oximetro*", "eletrocardiograf*", "eletroencefalograf*",
    "bomba de infusao", "incubadora*", "berco aquecido",
    "maquina de hemodialise", "equipamento de hemodialise",
    # centro cirúrgico e esterilização
    "autoclave*", "foco cirurgico", "mesa cirurgica", "carro de emergencia",
    # software e serviços de saúde
    "prontuario eletronico", "prontuario", "gestao hospitalar",
    "regulacao de leitos", "sistema de saude", "telemedicina", "telessaude",
    "teleconsulta", "telediagnostico", "pacs", "laudo a distancia",
]

# Termos ambiguos que só contam se tiver algo relacionado a sáude na frase, além disso é necessário checar se envolve rede ou algo que o cliente trabalha
PRODUTOS_AMBIGUOS = [
    # hardware e infraestrutura
    "equipamento*", "equip", "computador*", "microcomputador*", "notebook*",
    "desktop*", "tablet*", "impressora*", "scanner*", "servidor de rede",
    "storage", "switch*", "firewall", "nobreak*", "datacenter", "data center",
    "rede logica", "cabeamento", "link de internet", "conectividade",
    "infraestrutura de ti", "ponto de rede", "cabo de rede", "cabo utp",
    "rj45", "certificado digital", "telefon*", "smartphone*",
    # software e serviços de TI
    "software*", "licenciamento", "licenca de uso", "aplicativo*",
    "sistema informatizado", "sistema de informacao", "sistema integrado",
    "sistema de gestao", "sistema web", "sistema online", "sistemas de gestao",
    "plataforma*", "informatica", "tecnologia da informacao", "ti",
    "nuvem", "cloud", "banco de dados", "seguranca da informacao",
    "suporte tecnico", "help desk", "service desk",
    # servicos sobre equipamento
    "locacao de equipamento*", "material permanente", "bem permanente",
]

#termos medicos para facilitar no entendimento do contexto da frase, ajuda a diminuir erros
CONTEXTO_SAUDE = [
    "saude", "hospital*", "medic*", "enfermag*", "enfermeir*", "clinic*",
    "ambulatori*", "policlinic*", "santa casa", "sanitari*", "samu", "upa",
    "ubs", "sus", "caps", "uti", "pronto socorro", "atencao basica",
    "unidade basica", "paciente*", "leito*", "odontolog*", "laboratori*",
    "vigilancia epidemiologica", "vigilancia sanitaria", "farmacia*",
    "materno infantil", "maternidade", "cirurgic*", "diagnostic*",
]

#Coisas que o cliente nao tem interesse
EXCLUSOES = [
    # obras civis
    "obra*", "reforma*", "construcao", "pavimentacao", "edificacao",
    "engenharia civil", "revitalizacao", "recuperacao predial",
    # medicamentos e insumos farmaceuticos
    "medicamento*", "farmaco*", "insumo farmaceutico", "insumos farmaceuticos",
    "soro*", "vacina*", "imunobiologic*", "nutricao enteral", "formula infantil",
    "gases medicinais", "gas oxigenio", "oxigenio medicinal", "gas medicinal",
    # descartaveis e material de consumo
    "material de consumo", "materiais de consumo", "descartave*", "seringa*",
    "cateter*", "sonda*", "kit cateter",
    "luva*", "gaze*", "atadura*", "material penso", "correlatos", "reagente*",
    # limpeza e higiene
    "limpeza", "higienizacao", "saneante*", "material de higiene", "lavanderia",
    # alimentacao
    "alimentacao", "genero alimenticio", "generos alimenticios", "merenda",
    "refeicao", "refeicoes", "hortifruti", "hortifrutigranjeiro*", "agua mineral",
    # veiculos e combustivel
    "veiculo*", "automove*", "ambulancia*", "combustive*", "pneu*",
    "motocicleta*", "caminhao", "retroescavadeira",
    # outros 
    "fardamento", "uniforme*", "material grafico", "material de expediente",
    "mao de obra", "vigilancia armada", "vigilancia patrimonial", "seguro",
    # servicos assistenciais
    "plano de saude", "assistencia medico hospitalar", "home care",
    "tratamento domiciliar", "atencao domiciliar", "exames laboratoriais",
    # material de consumo medico
    # não insumo
    "material medico", "materiais medicos", "material hospitalar",
    "materiais hospitalares", "material quimico", "material bioquimico",
    "material odontologic*", "materiais odontologic*",
    
    #possiveis falsos positivos
    "equipamento recreativo*", "equipamentos recreativos", "ar condicionado",
    "equipamento de cozinha", "equipamentos de cozinha", "equipamento agricola",
    "equipamento de protecao individual", "equipamentos de protecao individual",
    "epi", "epis", "equipamento de som",
    "grupo gerador", "gerador de energia", "estabilizador de tensao",
    "equipamento veterinario", "uso veterinario",
]
