# Código que atualiza as informações dos contratos no Monday a partir dos dados do DocuSign

#--------------------------------
# SETUP DE VARIÁVEIS DE AMBIENTE
#--------------------------------

# Procura o caminho para a pasta raiz do projeto
import os
autodocu_folder_path = os.path.abspath(os.path.join(os.path.dirname(__file__)))
#print(f"Caminho da pasta do projeto AutoBackoffice: {autodocu_folder_path}")
repository_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
#print(f"Caminho da pasta raiz do projeto: {repository_root}")
project_root = os.path.abspath(os.path.join(repository_root, '..'))
#print(f"Caminho da pasta raiz do repositório: {project_root}")

import sys
sys.path.append(repository_root)  # Adiciona a pasta raiz do projeto ao sys.path

# Confirma se o .env existe na pasta raiz
env_path = os.path.join(project_root, '.env')
if not os.path.exists(env_path):
    raise FileNotFoundError(f"O arquivo .env não foi encontrado na pasta raiz do projeto: {project_root}. Garanta que o arquivo exista para carregar as variáveis de ambiente necessárias.")

# Carrega o arquivo .env localizado na pasta raiz do projeto
from dotenv import load_dotenv
load_dotenv(env_path) # Carrega o arquivo .env

data_file_path = os.path.join(autodocu_folder_path, "Dados/Docusign")



#--------------------------------
# HORÁRIO DE INÍCIO DA ATUALIZAÇÃO
#--------------------------------

from datetime import datetime, timezone, timedelta

# Horário desta execução
current_time_utc = datetime.now(timezone.utc)
# Retira 60 segundos do horário atual para evitar problemas de sincronização
current_time_utc = current_time_utc - timedelta(seconds=60)
# Converte o horário atual para UTC-3
current_time_brt = current_time_utc.astimezone(timezone(timedelta(hours=-3)))
current_time_brt_string = current_time_brt.strftime("%Y-%m-%d %H:%M:%S")
#--------------------------------


#--------------------------------
# SETUP DE LOGGING
#--------------------------------

# Inicializa um logger padrão Melnick para o AutoBackoffice
from Módulos.logs_melnick import setup_logger
import logging

logger = setup_logger(
    name="AutoDocu",
    #logs_path="C:/Users/pedroruppenthal/Documents/Melnick Code",
    log_file=f"{current_time_brt.strftime('%Y-%m-%d %H-%M-%S')} - autodocu.log",
    level=logging.INFO,
)


#--------------------------------
# CONTROLE DE ATUALIZAÇÕES
#--------------------------------

# Data da última atualização completa
last_update_file_path = os.path.join(data_file_path, "ultima_atualizacao.txt")
os.makedirs(os.path.dirname(last_update_file_path), exist_ok=True)  # Garante que a pasta Dados exista dentro da pasta do projeto AutoBackoffice

# Carregar a data da última atualização de um arquivo txt ou usa uma data inicial padrão se o arquivo não existir
if os.path.exists(last_update_file_path):
    with open(last_update_file_path, "r") as f:
        last_updated_at = f.read().strip()
    logger.info(f"Última atualização completa: {last_updated_at}")
else:
    last_updated_at = "2026-02-01 22:00:00"  # Data inicial padrão
    logger.info(f"Arquivo de última atualização não encontrado. Usando data inicial padrão {last_updated_at}.")

# Transforma em datetime para manipulação de fuso horário
last_updated_at_dt = datetime.strptime(last_updated_at, "%Y-%m-%d %H:%M:%S")
# Adiciona 3 horas para converter de UTC-3 para UTC
last_updated_at_dt_utc = last_updated_at_dt.replace(tzinfo=timezone(timedelta(hours=-3))).astimezone(timezone.utc)
# Transforma de volta em string no formato esperado pelo banco de dados
last_updated_at = last_updated_at_dt_utc.strftime("%Y-%m-%d %H:%M:%S")
logger.info(f"Última atualização completa convertida para UTC: {last_updated_at}")
#--------------------------------

#--------------------------------
# SETUP DE CLIENTES
#--------------------------------

# Cliente do Monday
from Módulos.cliente_monday import ClienteMonday

# BUsca e confirma que existe a chave de API do Monday.com
monday_api_key = os.getenv("MONDAY_API_KEY")
if not monday_api_key:
    raise ValueError("A variável de ambiente MONDAY_API_KEY do Monday.com não foi encontrada nas variáveis de ambiente. Verifique o arquivo .env.")
logger.info("Chave de API do Monday.com encontrada com sucesso nas variáveis de ambiente.")
cliente_monday = ClienteMonday(api_key=monday_api_key)

# Cliente do DocuSign
from Módulos.cliente_docusign import DocuClient

# Busca e confirma que existem as variáveis de ambiente do DocuSign
account_id = os.getenv("DOCU_ACCOUNT")
if not account_id:
    raise ValueError("A variável de ambiente DOCUSIGN_ACCOUNT_ID do DocuSign não foi encontrada nas variáveis de ambiente. Verifique o arquivo .env.")
logger.info("Chave de API do DocuSign encontrada com sucesso nas variáveis de ambiente.")

user = os.getenv("DOCU_USER")
if not user:
    raise ValueError("A variável de ambiente DOCUSIGN_USER_EMAIL do DocuSign não foi encontrada nas variáveis de ambiente. Verifique o arquivo .env.")
logger.info("Usuário do DocuSign encontrado com sucesso nas variáveis de ambiente.")

password = os.getenv("DOCU_PASSWORD")
if not password:
    raise ValueError("A variável de ambiente DOCUSIGN_USER_PASSWORD do DocuSign não foi encontrada nas variáveis de ambiente. Verifique o arquivo .env.")
logger.info("Senha do DocuSign encontrada com sucesso nas variáveis de ambiente.")

# token = os.getenv("DOCUSIGN_TOKEN")
# if not token:
#     logger.info("A variável de ambiente DOCUSIGN_TOKEN do DocuSign não foi encontrada nas variáveis de ambiente. O token será gerado automaticamente a partir do usuário e senha fornecidos.")
# else:
#     logger.info("Token do DocuSign encontrado com sucesso nas variáveis de ambiente. Ele será usado para autenticação.")
    

cliente_docu = DocuClient(account_id=account_id, user=user, password=password, data_file_path=data_file_path)
cliente_docu.ensure_authenticated()

#cliente_docu.get_groups() # Testa a autenticação e carrega os dados iniciais
#cliente_docu.get_users() # Carrega os usuários
#cliente_docu.data_manager('save') # Salva os dados iniciais

#--------------------------------
# BUSCA DE ENVELOPES ATUALIZADOS
#--------------------------------
logger.info("Buscando envelopes atualizados desde a última atualização completa...")
# Envelopes atualizados desde a última atualização completa
updated_envelopes = cliente_docu.get_envelopes_with_updates(updated_after=last_updated_at)
# Destinatários dos envelopes atualizados
recipients_data = cliente_docu.get_recipients_data(list(updated_envelopes.keys()))
# Combina os dados dos envelopes atualizados com os dados dos destinatários
for envelope_id, envelope_data in updated_envelopes.items():
    # Adiciona os dados dos destinatários ao envelope
    envelope_recipients = recipients_data.get(envelope_id, {})
    envelope_data.update(envelope_recipients)
    # Separa as infomrações no assunto do envelope
    subject = envelope_data.get("assunto", "")
    if subject is not None and subject != "":
        # Se tiver o "|", separa as partes
        if "|" in subject:
            parts = subject.split("|")
            # Itera pelas partes em ordem inversa para atribuir os valores corretamente
            current = 0
            for part in reversed(parts):
                part = part.strip().lower()  # Remove espaços em branco extras
                if current == 0:
                    envelope_data["nome_cliente"] = part
                    current += 1
                elif current == 1:
                    envelope_data["unidade"] = part
                    current += 1
                elif current == 2:
                    envelope_data["nome_torre"] = part
                    current += 1
                elif current == 3:
                    envelope_data["nome_empreendimento"] = part
                    current += 1

# Busca os itens no Monday relacionados aos envelopes atualizados

BOARD_IDS = {
    "prod": {
        "negocios": 18410571736,
        "contas": 1,
    },
    "dev": {
        "negocios": 18411789432,
        "contas": 18392694351,
    }
}

# De para do status de emissão
"""
completed
created
declined
deleted
delivered
processing
sent
signed
template
voided
"""
EMISSION_STATUS = {
    "created": "Emissão",
    "sent": "Enviado",
    "voided": "Cancelado",
    "completed": "Enviado"
}

environment = (
    os.getenv("AUTOBACKOFFICE_ENVIRONMENT")
    or os.getenv("ENVIRONMENT")
    or "dev"
).strip().lower()
board_id = BOARD_IDS.get(environment, BOARD_IDS["dev"])["negocios"]

if len(updated_envelopes.keys()) == 0:
    logger.info("Nenhum envelope atualizado desde a última execução. Nenhuma atualização necessária no Monday.com.")
    raise SystemExit(0)
else:
    logger.info(f"{len(updated_envelopes.keys())} envelopes atualizados desde a última execução. Buscando itens relacionados no Monday.com...")
    monday_items = cliente_monday.get_items(board_id=board_id, column_id="id_envelope_docusign", value=list(updated_envelopes.keys()))

# Itera pelos negócios encontrados e atualiza as informações dos contratos
logger.info(f"Atualizando os itens relacionados aos envelopes atualizados no Monday.com...")
for monday_id, item_data in monday_items.items():
    envelope_id = item_data["id_envelope"]
    envelope_data = updated_envelopes.get(envelope_id, {})
    if not envelope_data:
        logger.warning(f"Envelope {envelope_id} não encontrado nos envelopes atualizados.")
        continue
    # Busca o status do envelope
    envelope_status = envelope_data.get("status", "")
    # Se o status for enviado, inicializa o status do contrato como "Enviado"
    if envelope_status == "sent":
        signature_status = "Imobiliária"
    else:
        signature_status = None

    # Prepara os dados para atualização
    update_data = {
        "status_emissao": EMISSION_STATUS.get(envelope_status),
        "link_contrato": {
            "url": f"https://apps.docusign.com/send/documents/details/{envelope_id}",
            "text": "Ver Contrato"
        },
        "status_contrato": signature_status,
    }
    # Atualiza o status da assinatura se disponível
    real_estate_signature_status = envelope_data.get("status_assinatura_imobiliaria", "")
    if real_estate_signature_status == "nenhuma_imobiliaria":
        update_data["status_contrato"] = "Em assinatura"
    if real_estate_signature_status == "completo":
        update_data["status_contrato"] = "Em assinatura"
    elif real_estate_signature_status == "parcialmente_assinado":
        update_data["status_contrato"] = "Imobiliária"

    client_signature_status = envelope_data.get("status_assinatura_cliente", "")
    if client_signature_status == "completo":
        update_data["status_contrato"] = "Assinado"
    elif client_signature_status == "parcialmente_assinado":
        update_data["status_contrato"] = "Em assinatura"

    # Atualiza o item no Monday
    try:
        cliente_monday.update_item(
            board_id=board_id,
            item_id=monday_id,
            column_values=update_data
        )
        logger.info(f"Item {monday_id} atualizado com sucesso no Monday.com.")
    except Exception as e:
        logger.error(f"Erro ao atualizar o item {monday_id} no Monday.com: {str(e)}")

# Salva a data e hora do começo dessa execução como a última atualização completa
with open(last_update_file_path, "w") as f:
    f.write(current_time_brt.strftime("%Y-%m-%d %H:%M:%S"))
    logger.info(f"Data e hora desta atualização salva: {current_time_brt.strftime('%Y-%m-%d %H:%M:%S')} (UTC-3)")