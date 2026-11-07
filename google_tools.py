#ETAPA 1: IMPORTAÇÃO DAS BIBLIOTECAS
import os #acessa os arquivos do sistema
import unicodedata #normaliza os caracteres especiais
import uuid #gera identificadores únicos(para criar os links do meet)
from datetime import datetime #trabalha com datas e horários
from google.auth.exceptions import RefreshError #trata erros de autenticação
from google.auth.transport.requests import Request #faz requisições HTTP
from google.oauth2.credentials import Credentials #gerencia as credenciais de autenticação
from google_auth_oauthlib.flow import InstalledAppFlow #gerencia o fluxo de autenticação
from googleapiclient.discovery import build #constrói o serviço da API (cria objeto de autentitação)

#ETAPA 2: CRIAR OS ESCOPOS DE AUTENTICAÇÃO
SCOPES = [
    'https://www.googleapis.com/auth/calendar.events',  #define o escopo de acesso ao Google Calendar
    'https://www.googleapis.com/auth/spreadsheets' #planilhas do google
] 
#Dicionario com os nomes das colunas nas planilhas e seus respectivos IDs
CAMPOS_DA_PLANILHA = {
    "nome" : {"nome", "nomecandidato"},
    "vaga" : {"vaga", "cargo"},
    "data" : {"data", "dataentrevista"},
    "hora" : {"hora", "horario", "horarioentrevista"},
    "email" : {"email", "emailcandidato"},
    "status" : {"status", "situacao"},
}

#ETAPA 3: FUNÇÃO PARA ATENTICAÇÃO DO GOOGLE
def autenticar_google():
    """Função para autenticar o usuário no Google e retornar o serviço de planilha e calendário."""
    credenciais = None #variavel para armazenar as credenciais do google esta vazia
    if os.path.exists('token.json'): #verifica se o arquivo de token existe
        credenciais = Credentials.from_authorized_user_file('token.json', SCOPES) #carrega as credenciais do arquivo token.json
    if credenciais and credenciais.expired and credenciais.refresh_token: #verifica se as credenciais estão expiradas e se existe um token de atualização
        try:
            credenciais.refresh(Request()) #tenta atualizar as credenciais
        except RefreshError as erro: #se ocorrer um erro de atualização
            if "invalid_grant" in str(erro): #verifica se o erro é de concessão inválida
                raise
            credenciais = None #se não for, define as credenciais como None (vazias)
    if not credenciais or not credenciais.valid: #verifica se as credenciais são válidas
        fluxo = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES) #cria o fluxo de autenticação a partir do arquivo credentials.json
        credenciais = fluxo.run_local_server(port=0) #executa o fluxo de autenticação em um servidor local

    with open('token.json', 'w') as token: #abre o arquivo token.json para escrita
        token.write(credenciais.to_json()) #escreve as credenciais no arquivo_token.json
    return credenciais #retorna as credenciais autenticadas

def agendar_entrevista_com_meet (
        nome_candidato,
        email_candidato,
        data_hora_inicio,
        data_hora_fim,
):
    """Função para agendar uma entrevista no google calendar com link do Google Meet"""
    servico = build('calendar', 'v3', credentials=autenticar_google()) #constrói o serviço da API do Google Calendar

    evento = {
        'summary': f'Entrevista com {nome_candidato}', #título do evento
        'description': f'Entrevista com o time de People.', #descrição do evento
        'start': {
            'dateTime': data_hora_inicio, #data e hora de início do evento
            'timeZone': 'America/Sao_Paulo', #fuso horário
        },
        'end': {
            'dateTime': data_hora_fim, #data e hora de término do evento
            'timeZone': 'America/Sao_Paulo', #fuso horário
        },
        'attendees': [
            {'email': email_candidato}, #adiciona o e-mail do candidato como participante
        ],
        'conferenceData': {
            'createRequest': {
                'requestId': str(uuid.uuid4()), #gera um ID único para a solicitação de criação do link do Meet
                'conferenceSolutionKey': {'type': 'hangoutsMeet'}, #define o tipo de conferência como Google Meet
            },
        },
    }

    evento_criado = servico.events().insert(
        calendarId='primary', #define o calendário principal do usuário
        body=evento, #passa o corpo do evento criado
        conferenceDataVersion=1, #define a versão da API de conferência
        sendUpdates='all', #envia atualizações para todos os participantes
    ).execute() #executa a criação do evento

    link_meet = evento_criado.get('hangoutLink') #obtém o link do Google Meet do evento criado
    return link_meet #retorna o link do Google Meet

def registrar_candidato_planilha(
        id_planilha,
        nome,
        email,
        vaga,
        status,
        data_hora_inicio=None,
        data_hora_fim=None
):
    """Função para registrar os dados do candidato na planilha do Google Sheets"""
    if not id_planilha:
        raise ValueError("ID da planilha não informado.")

    if isinstance(nome, str) and "@" in nome and " " not in nome:
        nome = nome.split("@", 1)[0].replace(".", " ").replace("_", " ").title()
    if isinstance(email, str) and "@" not in email:
        raise ValueError("E-mail inválido.")

    servico = build('sheets', 'v4', credentials=autenticar_google())

    planilha = servico.spreadsheets().get(
        spreadsheetId=id_planilha,
        fields="sheets(properties(sheetId,title))",
    ).execute()

    abas = planilha.get("sheets", [])
    if not abas:
        raise ValueError("Planilha sem abas disponíveis.")

    primeira_aba = abas[0]["properties"]
    nome_aba = primeira_aba.get("title", "Página1")
    nome_aba_escapado = nome_aba.replace("'", "''")
    intervalo = f"'{nome_aba_escapado}'"

    resposta = servico.spreadsheets().values().get(
        spreadsheetId=id_planilha,
        range=f"{intervalo}!A1:Z",
    ).execute()

    linhas = resposta.get("values", [])
    cabecalho = linhas[0] if linhas else []
    cabecalho_normalizado = [str(coluna).strip().lower() for coluna in cabecalho]

    aliases = {
        "nome": {"nome", "nomecandidato", "candidato", "nome do candidato"},
        "email": {"email", "emailcandidato", "e-mail", "email do candidato"},
        "vaga": {"vaga", "vagas", "cargo", "posicao", "perfil", "vaga de interesse"},
        "status": {"status", "situacao", "situacao do candidato"},
        "data": {"data", "dataentrevista", "data da entrevista"},
        "hora": {"hora", "horario", "horarioentrevista", "hora da entrevista", "horario da entrevista"},
    }

    indice_colunas = {campo: None for campo in aliases}
    for idx, coluna in enumerate(cabecalho_normalizado):
        chave = ''.join(
            ch for ch in unicodedata.normalize('NFKD', coluna).encode('ascii', 'ignore').decode('ascii')
            if ch.isalnum() or ch == ' '
        )
        chave = ' '.join(chave.split())
        for campo, nomes in aliases.items():
            normalizados = {" ".join(nome.split()) for nome in nomes}
            if chave in normalizados or any(chave.startswith(n + ' ') or chave.endswith(' ' + n) or chave == n for n in normalizados):
                indice_colunas[campo] = idx
                break

    dados = {
        "nome": nome,
        "email": email,
        "vaga": vaga,
        "status": status,
    }

    if data_hora_inicio:
        try:
            inicio = datetime.fromisoformat(data_hora_inicio)
            if indice_colunas["data"] is not None:
                dados["data"] = inicio.strftime("%d/%m/%Y")
            if indice_colunas["hora"] is not None:
                dados["hora"] = inicio.strftime("%H:%M")
        except ValueError as erro:
            raise ValueError("Formato de data e hora inválido.") from erro

    if not cabecalho:
        cabecalho = ["NOME", "VAGA", "DATA", "HORA", "EMAIL", "STATUS"]
        valores = [nome, vaga, "", "", email, status]
    else:
        max_index = max((idx for idx in indice_colunas.values() if idx is not None), default=-1)
        valores = [""] * max(len(cabecalho), max_index + 1)
        for campo, valor in dados.items():
            indice = indice_colunas.get(campo)
            if indice is not None:
                valores[indice] = valor

    servico.spreadsheets().values().append(
        spreadsheetId=id_planilha,
        range=intervalo,
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": [valores]},
    ).execute()

    return "candidato registrado com sucesso!"