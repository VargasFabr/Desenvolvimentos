# %%
# Código que controla e atualiza o Relatório Comercial do Backoffice no Monday usando informações do Otto.

#--------------------------------
# SETUP DE VARIÁVEIS DE AMBIENTE
#--------------------------------

# Procura o caminho para a pasta raiz do projeto
import os
autobackoffice_folder_path = os.path.abspath(os.path.join(os.path.dirname(__file__)))
#print(f"Caminho da pasta do projeto AutoBackoffice: {autobackoffice_folder_path}")
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

def format_seconds_to_time(seconds):
    """
    Converte segundos em uma string formatada.
    Mostra segundos até que sejam mais que 60 segundos, minutos até que sejam mais que 60 minutos, e HH:MM depois disso.
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours:02}:{minutes:02}"
    elif minutes > 0:
        return f"{minutes} min"
    else:
        return f"{secs} s"

#--------------------------------
# HORÁRIO DE INÍCIO DA ATUALIZAÇÃO
#--------------------------------

from datetime import datetime, timezone, timedelta

# Horário desta execução
current_time_utc = datetime.now(timezone.utc)
# Retira 60 segundos do horário atual para evitar problemas de sincronização
current_time_utc = current_time_utc - timedelta(seconds=60)
# Converte o horário atual para UTC-3
current_time_utc_minus3 = current_time_utc.astimezone(timezone(timedelta(hours=-3)))
current_date_string = current_time_utc_minus3.strftime("%Y-%m-%d %H:%M:%S")

#--------------------------------
# SETUP DE LOGGING
#--------------------------------

# Cria pasta de logs, se não existir
logs_path = os.getenv("AUTOBACKOFFICE_LOGS_PATH")
if not logs_path:
    raise ValueError("A variável de ambiente AUTOBACKOFFICE_LOGS_PATH não foi encontrada nas variáveis de ambiente. Verifique o arquivo .env.")

# Inicializa um logger padrão Melnick para o AutoBackoffice
from Módulos.logs_melnick import setup_logger
import logging

logger = setup_logger(
    name="AutoBackoffice",
    logs_path=logs_path,
    log_file=f"{current_time_utc_minus3.strftime('%Y-%m-%d %H-%M-%S')} - autobackoffice.log",
    level=logging.INFO,
)

#--------------------------------
# SETUP DE CLIENTES
#--------------------------------

# Cliente do Monday
from Módulos.cliente_monday import ClienteMonday

# BUsca e confirma que existe a chave de API do Monday.com
monday_api_key = os.getenv("MONDAY_API_KEY")
if not monday_api_key:
    raise ValueError("A variável de ambiente MONDAY_API_KEY do Monday.com não foi encontrada nas variáveis de ambiente. Verifique o arquivo .env.")
cliente_monday = ClienteMonday(api_key=monday_api_key)

OWNERS = {
    "melnick": "10843311624",
    "permutante": "10843314010",
}

#Cliente do Otto
from Módulos.cliente_otto import ClienteOtto

# Busca e confirma que existem as credenciais do Otto
otto_user = os.getenv("OTTO_DB_USER")
otto_password = os.getenv("OTTO_DB_PASSWORD")
if not otto_user or not otto_password:
    raise ValueError("As variáveis de ambiente OTTO_DB_USER e OTTO_DB_PASSWORD não foram encontradas nas variáveis de ambiente. Verifique o arquivo .env.")

cliente_otto = ClienteOtto(
    user=otto_user,
    password=otto_password
)

# Dicionário de status de propostas e reservas do Otto
# Nome no otto no comentário, para com o nome do status no Monday
STATUS_RESERVA = { 
    6:"Vendida", # Vendida
    5:"Precisa de ajustes", # Precisa de ajustes
    1:"Aguardando aprovação", # Aguardando aprovação
    2:"Aprovada", # Aprovada
    4:"Cancelada", # Cancelada
    3:"Não aprovada", # Não aprovada
    0: "Sem reserva" # Sem reserva
}

STATUS_PROPOSTA = {
    11:"Aprovada", # Aprovada com ajuste no pagamento
    12:"Aprovada", # Aprovada com ajuste
    10:"Cancelada",
    9: "Vendida",
    6: "Não enviada",
    7: "Em alteração",
    1: "Aguardando análise",
    3: "Aprovada",
    8: "Aprovada", # Aprovada com ajustes na comissão
    2: "Em análise",
    4: "Ajustes", # Precisa de ajustes
    5: "Não aprovada",
    0: "Sem proposta" # Sem proposta
}

TEST_KEYS = [
    "/ teste",
    "(teste)",
    " teste",
    "teste ",
    "testando",
]

# Cliente SQL para buscar os dados das empresas do GC
from Módulos.cliente_sql import SQLClient
import json

# Inicializa o cliente SQL e conecta ao banco de dados
client = SQLClient(
    server=os.getenv("SQL_SERVER", ""),
    database='Melnick',
    username=os.getenv("SQL_USER", ""),
    password=os.getenv("SQL_PASS", "")
)
from typing import Any, Dict, List
# Busca os dados das empresas do GC para usar como referência na atualização dos processos
empresas_gc: list[dict[str, Any]] | None = None
empresas_gc_file_path = os.path.join(autobackoffice_folder_path, "Dados", "empresas_gc.json")
os.makedirs(os.path.dirname(empresas_gc_file_path), exist_ok=True)

def normalizar_cnpj(valor):
    if not valor:
        return None
    # Remove tudo que nao for digito
    digitos = "".join(ch for ch in str(valor) if ch.isdigit())
    if len(digitos) != 14:
        return None
    return f"{digitos[0:2]}.{digitos[2:5]}.{digitos[5:8]}/{digitos[8:12]}-{digitos[12:14]}"

try:
    client.connect()
    empresas_gc = client.execute_query("SELECT * FROM dbo.Empresas_GC")
    if empresas_gc is not None:
        with open(empresas_gc_file_path, "w", encoding="utf-8") as f:
            json.dump(empresas_gc, f, ensure_ascii=False, indent=2, default=str)
        logger.info(f"Dados das empresas do GC salvos em {empresas_gc_file_path}.")
except Exception as exc:
    logger.warning(f"Falha ao conectar ou consultar o banco de dados: {exc}. Tentando carregar cache local.")

if empresas_gc is None:
    if os.path.exists(empresas_gc_file_path):
        with open(empresas_gc_file_path, "r", encoding="utf-8") as f:
            empresas_gc = json.load(f)
        logger.warning("Usando dados das empresas do GC carregados do arquivo local.")
    else:
        logger.error("Não foi possível buscar os dados no banco e o arquivo de cache não existe.")

if empresas_gc is not None:
    empresas = {}
    # Limpa os dados das empresas do GC para criar um dicionário com o código do empreendimento como chave e o nome da empresa e o CNPJ como valores, para usar como referência na atualização dos processos
    for empresa in empresas_gc:
        cnpj = normalizar_cnpj(empresa["[cnpj]"])
        if cnpj and cnpj != "" and cnpj != "0":
            empresas[empresa["[cd_empreendimento]"]] = {
                "nm_empresa": empresa["[nm_empresa]"].title() if empresa["[nm_empresa]"] else "",
                "cnpj": cnpj,
            }
else:
    empresas = {}

#print(empresas)

#--------------------------------
# CONTROLE DE ATUALIZAÇÕES
#--------------------------------

# Data da última atualização completa
last_update_file_path = os.path.join(autobackoffice_folder_path, "Dados", "ultima_atualizacao.txt")
os.makedirs(os.path.dirname(last_update_file_path), exist_ok=True)  # Garante que a pasta Dados exista dentro da pasta do projeto AutoBackoffice

# Carregar a data da última atualização de um arquivo txt ou usa uma data inicial padrão se o arquivo não existir
if os.path.exists(last_update_file_path):
    with open(last_update_file_path, "r") as f:
        last_updated_at = f.read().strip()
    logger.info(f"Última atualização completa: {last_updated_at}")
else:
    last_updated_at = "2025-12-18 22:00:00"  # Data inicial padrão
    logger.info(f"Arquivo de última atualização não encontrado. Usando data inicial padrão {last_updated_at}.")

# Transforma em datetime para manipulação de fuso horário
last_updated_at_dt = datetime.strptime(last_updated_at, "%Y-%m-%d %H:%M:%S")
# Adiciona 3 horas para converter de UTC-3 para UTC
last_updated_at_dt_utc = last_updated_at_dt.replace(tzinfo=timezone(timedelta(hours=-3))).astimezone(timezone.utc)
# Transforma de volta em string no formato esperado pelo banco de dados
last_updated_at = last_updated_at_dt_utc.strftime("%Y-%m-%d %H:%M:%S")
logger.debug(f"Última atualização completa convertida para UTC: {last_updated_at}")
#--------------------------------

#--------------------------------    
# BUSCA AS ATUALIZAÇÔES NO OTTO
#--------------------------------
logger.info("#---- Atualizações Otto ----#")
processes = cliente_otto.get_processes(after_date=last_updated_at)
number_of_processes = len(processes)
logger.info(f"Processos atualizados encontrados: {number_of_processes}")
""" Formato do dicionário processes:
{
    id_negocio (str): {
        'negocio_criado_em': datetime,
        'negocio_atualizado_em': datetime,
        'id_corretor': str,
        'cargo_corretor': str,
        'nome_corretor': str,
        'creci_corretor': str,
        'cpf_corretor': str,
        'id_gerente': str,
        'nome_gerente': str,
        'id_executivo': str,
        'nome_executivo': str,
        'id_imobiliaria': str,
        'nome_imobiliaria': str,
        'id_unidade': str,
        'numero_unidade': str,
        'id_integracao_unidade': str,
        'valor_unidade': float,
        'resultado_integracao_unidade': dict,
        'id_torre': str,
        'nome_torre': str,
        'id_integracao_torre': str,
        'id_empreendimento': str,
        'nome_empreendimento': str,
        'id_integracao_empreendimento': str,
        'nome_incorporadora': str,
        'id_cliente': str,
        'nome_cliente': str,
        'cpf_cliente': str,
        'cnpj_cliente': str
    }
}
"""

# Teste de retirada, não parece ser usado
# permutas = 0
# melnick = 0
# ids_unidades = set()

# for process_id, process_data in processes.items():
#     ids_unidades.add(process_data.get("id_unidade"))
#     flag_permuta = process_data.get("flag_permuta", False)
#     if flag_permuta:
#         permutas += 1
#     else:
#         melnick += 1
# print(f"Total: {len(processes)}, Permutas: {permutas}, Melnick: {melnick}")

bookings = cliente_otto.get_bookings(after_date=last_updated_at)
logger.info(f"Reservas atualizadas encontradas: {len(bookings)}")
""" Formato do dicionário bookings:
{
    id_reserva (str): {
        'id_negocio': str,
        'reserva_criada_em': datetime,
        'reserva_atualizada_em': datetime,
        'id_status_reserva': str,
        'posicao_fila': int,
        'inicio_primeira_posicao': datetime,
        'fim_primeira_posicao': datetime,
        'resultado_integracao_reserva': dict
    }
}
"""

proposals = cliente_otto.get_proposals(after_date=last_updated_at)
logger.info(f"Propostas atualizadas encontradas: {len(proposals)}")
""" Formato do dicionário proposals:
{
    id_proposta (str): {
        'id_negocio': str,
        'proposta_enviada_em': datetime,
        'id_status_proposta': str,
        'proposta_criada_em': datetime,
        'proposta_atualizada_em': datetime,
        'id_cliente': str,
        'proposta_entregue_em': datetime,
        'resultado_integracao_proposta': dict
    }
}
"""

# Como podemos ter múltiplas reservas e propostas para o mesmo negócio, precisamos agregar essas informações
# dentro do dicionário de processos para facilitar a atualização no Monday.com
# Para isso, vamos adicionar ao dicionário de processos as reservas e propostas associadas a cada negócio
# Precisamos manter a ordem cronológica de data de atualização para cada reserva e proposta e iterar sobre elas
# nessa ordem para manter o histórico correto e garantir que as regras de negócio sejam aplicadas corretamente

logger.info("Limpando processos...")
# Cria lista de ids únicos de corretores e imobiliárias ligados aos processos
broker_ids = set()
executive_ids = set()
manager_ids = set()
real_estate_ids = set()
units_ids = set()
customer_documents = set()
cnpjs_empresas = set()

for process_id in list(processes.keys()):

    # Confere se o processo tem dados suficientes para ser atualizado
    if processes[process_id].get("id_unidade") is None:
        logger.debug(f"O processo ID {process_id} não possui ID de unidade. Não será processado.")
        processes.pop(process_id)
        continue
    if processes[process_id].get("id_cliente") is None:
        logger.debug(f"O processo ID {process_id} não possui ID de cliente. Não será processado.")
        processes.pop(process_id)
        continue

    # Adiciona os IDs do corretor, executivo, gerente e da imobiliária a lista de IDs de contas
    broker_id = processes[process_id].get("id_corretor")
    if broker_id:
        broker_ids.add(broker_id)
    executive_id = processes[process_id].get("id_executivo")
    if executive_id:
        executive_ids.add(executive_id)
    manager_id = processes[process_id].get("id_gerente")
    if manager_id:
        manager_ids.add(manager_id)
    real_estate_id = processes[process_id].get("id_imobiliaria")
    if real_estate_id:
        real_estate_ids.add(real_estate_id)

    # Limpeza dos dados de integração do empreendimento
    print(f"Processo ID {process_id} - Dados de integração do empreendimento antes da limpeza: {processes[process_id].get('id_integracao_empreendimento')}")
    dados_integracao_empreendimento = processes[process_id].get("id_integracao_empreendimento")
    ids_integracao_empreendimento = dados_integracao_empreendimento.split("|") if dados_integracao_empreendimento else []
    print(f"Processo ID {process_id} - IDs de integração do empreendimento após split: {ids_integracao_empreendimento}")
    #print(f"IDs de integração do empreendimento para o processo ID {process_id}: {ids_integracao_empreendimento}. Original: {dados_integracao_empreendimento}")
    processes[process_id]["id_integracao_empreendimento"] = ids_integracao_empreendimento[0] if len(ids_integracao_empreendimento) > 0 else None
    # Coleta o CNPJ do empreendimento para buscar/evitar duplicidade de empresas no Monday
    try:
        id_empreendimento_int = int(processes[process_id]["id_integracao_empreendimento"]) if processes[process_id]["id_integracao_empreendimento"] else None
    except (TypeError, ValueError):
        id_empreendimento_int = None
    if id_empreendimento_int is not None:
        cnpj_emp = empresas.get(id_empreendimento_int, {}).get("cnpj")
        cnpj_emp = normalizar_cnpj(cnpj_emp)
        if cnpj_emp:
            cnpjs_empresas.add(cnpj_emp)


    # Adiciona o ID da unidade e o documento do cliente para a busca de possíveis conflitos
    unit_id = processes[process_id].get("id_unidade")
    if unit_id:
        units_ids.add(unit_id)
    customer_document = processes[process_id].get("cpf_cliente") or processes[process_id].get("cnpj_cliente")
    if customer_document:
        customer_documents.add(customer_document)
        processes[process_id]["documento_cliente"] = customer_document

    
    # Adicona lista de atualizações vazia para reservas e propostas
    processes[process_id]["atualizacoes"] = []
    # Adiciona a primeira data com alguma atualização para ordenação de atualização
    processes[process_id]["primeira_atualizacao"] = processes[process_id].get("negocio_atualizado_em")

logger.info(f"Processos retirados por falta de dados: {number_of_processes - len(processes)}")
logger.info(f"Processos restantes para atualização: {len(processes)}")

logger.info("Agregando reservas e propostas aos processos...")
# Itera sobre as reservas e adiciona ao dicionário de processos
for booking_id, booking_data in bookings.items():
    process_id = booking_data["id_negocio"]
    updated_at = booking_data["reserva_atualizada_em"]
    if process_id in processes:
        processes[process_id]["atualizacoes"].append({
            "tipo": "reserva",
            "id": booking_id,
            "data_atualizacao": updated_at,
            "dados": booking_data
        })
        # Atualiza a última data de atualização do processo, se necessário
        if updated_at < processes[process_id]["primeira_atualizacao"]:
            processes[process_id]["primeira_atualizacao"] = updated_at
    #else:
        #logger.error(f"Reserva ID {booking_id} associada ao negócio ID {process_id} que não foi encontrado nos processos atualizados.")

# Itera sobre as propostas e adiciona ao dicionário de processos
for proposal_id, proposal_data in proposals.items():
    process_id = proposal_data["id_negocio"]
    updated_at = proposal_data["proposta_atualizada_em"]
    if process_id in processes:
        processes[process_id]["atualizacoes"].append({
            "tipo": "proposta",
            "id": proposal_id,
            "data_atualizacao": proposal_data["proposta_atualizada_em"],
            "dados": proposal_data
        })
        # Atualiza a última data de atualização do processo, se necessário
        if updated_at < processes[process_id]["primeira_atualizacao"]:
            processes[process_id]["primeira_atualizacao"] = updated_at
    #else:
        #logger.error(f"Proposta ID {proposal_id} associada ao negócio ID {process_id} que não foi encontrado nos processos atualizados.")

# Ordena as atualizações dentro de cada processo pela data de atualização
for process_id in list(processes.keys()):
    processes[process_id]["atualizacoes"].sort(key=lambda x: x["data_atualizacao"])
    # Adiciona uma contagem de atualizações no processo para referência futura
    processes[process_id]["total_atualizacoes"] = len(processes[process_id]["atualizacoes"])

# Por fim ordena os processos pela primeira data de atualização, da mais antiga para a mais nova
processes = dict(sorted(processes.items(), key=lambda x: x[1]["primeira_atualizacao"]))

#--------------------------------
# BUSCA ITENS NO MONDAY.COM
#--------------------------------
BOARD_IDS = {
    "prod": {
        "negocios": 18248707918,
        "contas": 1,
    },
    "dev": {
        "negocios": 18392682833,
        "contas": 18392694351,
    }
}

# Seleciona o board correto conforme o ambiente, padrão é dev
THIS_BOARDS_ID = BOARD_IDS.get(os.getenv("AUTOBACKOFFICE_ENVIRONMENT", "dev"), BOARD_IDS["dev"])
PROCESSES_BOARD_ID = THIS_BOARDS_ID["negocios"]
ACCOUNTS_BOARD_ID = THIS_BOARDS_ID["contas"]

logger.info("#---- Itens existentes no Monday ----#")
# Busca os negócios no Monday pelo ID Otto
if len(processes) == 0:
    logger.info("Nenhum processo atualizado para buscar no Monday.com.")
    monday_processes = {}
else:
    logger.info("Buscando itens no Monday.com para os processos atualizados...")
    monday_processes = cliente_monday.get_items(
        board_id=PROCESSES_BOARD_ID,
        column_id="customer_process_id",
        value=list(processes.keys())
    )
    logger.info(f"Negócios encontrados no Monday.com para os processos atualizados: {len(monday_processes)}")
    logger.info("Alterando chave para ID Otto...")
    for monday_process_id in list(monday_processes.keys()):
        process_data = monday_processes.pop(monday_process_id)
        otto_id = process_data.get("id_negocio")
        if otto_id:
            monday_processes[otto_id] = process_data  # Agora a chave é o ID Otto
            monday_processes[otto_id]["id_monday"] = monday_process_id  # Adiciona o ID do item no Monday.com como valor adicional

# Busca corretores no Monday pelos IDs Otto
logger.info(f"IDs únicos de corretores coletados: {len(broker_ids)}")
if len(broker_ids) == 0:
    logger.info("Nenhum corretor associado aos processos atualizados para buscar no Monday.com.")
    monday_brokers = {}
else:
    logger.info("Buscando corretores no Monday.com para os processos atualizados...")
    monday_brokers = cliente_monday.get_items(
        board_id=ACCOUNTS_BOARD_ID,
        #column_id="text_mkywmptw", # ID da coluna de ID Otto nesse board
        #value=list(broker_ids)
        filter_dict={
            "text_mkywmptw": list(broker_ids)
        }
    )
    logger.info(f"Corretores encontrados no Monday.com para os processos atualizados: {len(monday_brokers)}")
    logger.info("Alterando chave para ID Otto...")
    for monday_broker_id in list(monday_brokers.keys()):
        broker_data = monday_brokers.pop(monday_broker_id)
        otto_id = broker_data.get("id_integracao")
        if otto_id:
            monday_brokers[otto_id] = broker_data  # Agora a chave é o ID Otto
            monday_brokers[otto_id]["id_monday"] = monday_broker_id  # Adiciona o ID do item no Monday.com como valor adicional

# Busca imobiliárias no Monday pelos IDs Otto
logger.info(f"IDs únicos de imobiliárias coletados: {len(real_estate_ids)}")
if len(real_estate_ids) == 0:
    logger.info("Nenhuma imobiliária associada aos processos atualizados para buscar no Monday.com.")
    monday_real_estates = {}
else:
    logger.info("Buscando imobiliárias no Monday.com para os processos atualizados...")
    monday_real_estates = cliente_monday.get_items(
        board_id=ACCOUNTS_BOARD_ID,
        #column_id="text_mkywmptw", # ID da coluna de ID Otto nesse board
        #value=list(real_estate_ids)
        filter_dict={
            "tipo_de_conta": "Imobiliária",
            "text_mkywmptw": list(real_estate_ids)
        }
    )
    logger.info(f"Imobiliárias encontradas no Monday.com para os processos atualizados: {len(monday_real_estates)}")
    logger.info("Alterando chave para ID Otto...")
    for monday_real_estate_id in list(monday_real_estates.keys()):
        real_estate_data = monday_real_estates.pop(monday_real_estate_id)
        otto_id = real_estate_data.get("id_integracao")
        if otto_id:
            monday_real_estates[otto_id] = real_estate_data  # Agora a chave é o ID Otto
            monday_real_estates[otto_id]["id_monday"] = monday_real_estate_id  # Adiciona o ID do item no Monday.com como valor adicional

# Busca gerente no Monday pelo ID do Otto
logger.info(f"IDs únicos de gerentes coletados: {len(manager_ids)}")

if len(manager_ids) == 0:
    logger.info("Nenhum gerente associado aos processos atualizados para buscar no Monday.com.")
    monday_managers = {}
else:
    logger.info("Buscando gerentes no Monday.com para os processos atualizados...")
    # Busca todos os itens que tenham como ID do Otto algum dos IDs de gerentes coletados
    monday_managers = cliente_monday.get_items(
        board_id=ACCOUNTS_BOARD_ID,
        #column_id="text_mkywmptw", # ID da coluna de ID Otto nesse board
        #value=list(broker_ids)
        filter_dict={ # Não filtramos por tipo de conta para pegar se for corretor ou executivo
            "text_mkywmptw": list(manager_ids) 
        }
    )
    logger.info(f"Gerentes encontrados no Monday.com para os processos atualizados: {len(monday_managers)}")
    logger.info("Alterando chave para ID Otto...")
    for monday_manager_id in list(monday_managers.keys()): # Itera por todos os ID do Monday dos gerentes encontrados
        manager_data = monday_managers.pop(monday_manager_id) # Coleta os dados do gerente
        otto_id = manager_data.get("id_integracao") # Seta o ID do Otto como o ID de integração do Monday
        if otto_id is not None and otto_id != "": # Se tiver um ID do Otto (o get não retornar None ou não for vazia no Monday)
            monday_managers[otto_id] = manager_data  # Agora a chave é o ID Otto (começa como ID do Monday quando puxa pela API)
            monday_managers[otto_id]["id_monday"] = monday_manager_id  # Adiciona o ID do item no Monday.com como valor adicional


# Busca executivo no Monday pelo ID do Otto
logger.info(f"IDs únicos de executivos coletados: {len(executive_ids)}")

if len(executive_ids) == 0:
    logger.info("Nenhum executivo associado aos processos atualizados para buscar no Monday.com.")
    monday_executives = {}
else:
    logger.info("Buscando executivos no Monday.com para os processos atualizados...")
    # Busca todos os itens que tenham como ID do Otto algum dos IDs de executivos coletados
    monday_executives = cliente_monday.get_items(
        board_id=ACCOUNTS_BOARD_ID,
        #column_id="text_mkywmptw", # ID da coluna de ID Otto nesse board
        #value=list(broker_ids)
        filter_dict={ # Não filtramos por tipo de conta para pegar se for corretor ou executivo
            "text_mkywmptw": list(executive_ids) 
        }
    )
    logger.info(f"Executivos encontrados no Monday.com para os processos atualizados: {len(monday_executives)}")
    logger.info("Alterando chave para ID Otto...")
    for monday_executive_id in list(monday_executives.keys()): # Itera por todos os ID do Monday dos executivos encontrados
        executive_data = monday_executives.pop(monday_executive_id) # Coleta os dados do executivo
        otto_id = executive_data.get("id_integracao") # Seta o ID do Otto como o ID de integração do Monday
        if otto_id is not None and otto_id != "": # Se tiver um ID do Otto (o get não retornar None ou não for vazia no Monday)
            monday_executives[otto_id] = executive_data  # Agora a chave é o ID Otto (começa como ID do Monday quando puxa pela API)
            monday_executives[otto_id]["id_monday"] = monday_executive_id  # Adiciona o ID do item no Monday.com como valor adicional

# Busca empresas no Monday pelos IDs do empreendimento do GC
logger.info(f"CNPJs de empresas coletados: {len(cnpjs_empresas)}")

if len(cnpjs_empresas) == 0:
    logger.info("Nenhuma empresa associada aos processos atualizados para buscar no Monday.com.")
    monday_companies = {}
else:
    logger.info("Buscando empresas no Monday.com para os processos atualizados...")
    # Busca todos os itens que tenham como CNPJ algum dos CNPJs de empresas coletados
    monday_companies = cliente_monday.get_items(
        board_id=ACCOUNTS_BOARD_ID,
        filter_dict={
            "cpf_cnpj": list(cnpjs_empresas)
        }
    )
    logger.info(f"Empresas encontradas no Monday.com para os processos atualizados: {len(monday_companies)}")
    logger.info("Alterando chave para CNPJ...")
    for monday_company_id in list(monday_companies.keys()): # Itera por todos os ID do Monday das empresas encontradas
        company_data = monday_companies.pop(monday_company_id) # Coleta os dados da empresa
        cnpj = company_data.get("cpf_cnpj") or company_data.get("cnpj") # Seta o CNPJ como a chave para essa empresa
        cnpj = normalizar_cnpj(cnpj)
        if cnpj is not None and cnpj != "": # Se tiver um CNPJ (o get não retornar None ou não for vazia no Monday)
            monday_companies[cnpj] = company_data  # Agora a chave é o CNPJ
            monday_companies[cnpj]["id_monday"] = monday_company_id  # Adiciona o ID do item no Monday.com como valor adicional


if len(units_ids) == 0 or len(customer_documents) == 0:
    logger.info("Nenhuma unidade ou documento de cliente associado aos processos atualizados para buscar possíveis conflitos no Monday.com.")
    all_possible_conflicts = {}
else:
    logger.info("Buscando possíveis conflitos no Monday.com para os processos atualizados...")
    # Essa busca deve retornar todos os negócios que tenham o documento e o ID da unidade entre os valores passados.
    # Negócios que tiverem apenas um entre os dois valores não serão retornados. Nem os que tiverem nenhum dos dois.
    all_possible_conflicts = cliente_monday.get_items(
        board_id=PROCESSES_BOARD_ID,
        filter_dict={
            "unit_id": list(units_ids),
            "cpf_cnpj": list(customer_documents)
        }
    )
    logger.info(f"Possíveis conflitos encontrados no Monday.com para os processos atualizados: {len(all_possible_conflicts)}")

#--------------------------------
# ATUALIZA O RELATÓRIO COMERCIAL NO MONDAY
#--------------------------------
logger.info("#---- Atualização no Monday ----#")

# Acompanhamento de desempenho do código
import time
from statistics import mean

update_durations = []
total_processes = len(processes)
start_time = time.time()
counter = 0

for process_id, process_data in processes.items():

    logger.info(f"ID: {process_id}")
    logger.info(f"DATA: {process_data}")

    # Acompanhamento de performance do loop de atualização
    # if counter == 0: # Se for a primeira execução do loop
    #     start_time = time.time() # Início da medição de tempo
    #     logger.info("--------------------------------------------------")
    # else:
    #     logger.info("------------------------------------------------")
    #     # Acompanhamento de desempenho
    #     elapsed_time = time.time() - start_time
    #     update_durations.append(elapsed_time)

    #     # Evita divisão por zero quando não há durações registradas
    #     if update_durations and sum(update_durations) > 0:
    #         expected_remaining_time_string = format_seconds_to_time(mean(update_durations) * (total_processes - counter))
    #         total_elapsed_time_string = format_seconds_to_time(sum(update_durations))
    #         performance = counter / sum(update_durations)
            
    #         # Evita divisão por zero ao calcular segundos por processo
    #         if performance > 0:
    #             performance_string = f"{performance:.2f} p/s" if performance > 1 else f"{(1 / performance):.2f} s/p"
    #         else:
    #             performance_string = "N/A"
    #     else:
    #         expected_remaining_time_string = "N/A"
    #         total_elapsed_time_string = format_seconds_to_time(elapsed_time)
    #         performance_string = "N/A"

    #     # Evita divisão por zero quando não há processos
    #     percentage = (counter / total_processes * 100) if total_processes > 0 else 0.0
    #     logger.info(f"{counter}/{total_processes} - {percentage:.2f}% [{total_elapsed_time_string} / {expected_remaining_time_string}, {performance_string}]")
    #     logger.info("--------------------------------------------------")

    # logger.info(f"Processo ID {process_id}")
    counter += 1
    start_time = time.time() # Início da medição de tempo

    # Busca e confirmar algumas informações básicas do processo

    unit_id = process_data.get("id_unidade")
    if not unit_id:
        logger.warning(f"Nenhum ID de unidade encontrado.")
        continue # Pula a atualização desse processo, pois não faz sentido atualizar um negócio sem unidade
    else:
        unit_name = process_data.get("nome_empreendimento", "SEM EMPREENDIMENTO") + " | " \
            + process_data.get("nome_torre", "SEM TORRE")+ " | " \
            + process_data.get("numero_unidade", "SEM UNIDADE")
        logger.info(f"Unidade ID {unit_id}: {unit_name}")

    customer_id = process_data.get("id_cliente")
    if not customer_id:
        logger.warning(f"Nenhum ID de cliente encontrado.")
        continue # Pula a atualização desse processo, pois não faz sentido atualizar um negócio sem cliente
    else:
        logger.info(f"Cliente ID {customer_id}")
        customer_document = process_data.get("documento_cliente")
        if not customer_document:
            logger.warning(f"Nenhum CPF ou CNPJ encontrado para o cliente ID {customer_id}.")
        
        customer_name = process_data.get("nome_cliente")
        if not customer_name:
            logger.warning(f"Nenhum nome de cliente encontrado para o cliente ID {customer_id}.")
            customer_name = "NOME NÃO INFORMADO"
        else:
            skip_flag = False
            # Confirma se o nome do cliente possui alguma flag de teste dentro da string
            for test_key in TEST_KEYS:
                if test_key.lower() in customer_name.lower():
                    logger.info(f"Nome do cliente [{customer_name}] possui flag de teste '{test_key}'. Pulando atualização desse processo.")
                    skip_flag = True

            if skip_flag:
                continue  # Pula a atualização desse processo
            else:
                logger.info(f"Cliente: {customer_name} | CPF/CNPJ: {customer_document}")
        # Adicionar condicional de pular atualização caso o nome do cliente tenha a flag de teste
        # Combinar essa flag com todos e obrigar todos a usar

    # Confirma que o corretor e a imobiliária estão cadastrados no Monday.com

    # Corretor
    broker_id = process_data.get("id_corretor")
    logger.info(f"Corretor ID {broker_id}: {process_data.get('nome_corretor', 'NOME NÃO INFORMADO')}")

    # Confirma se existe string de teste no nome do corretor
    broker_name = process_data.get("nome_corretor", "")
    skip_flag = False
    for test_key in TEST_KEYS: # itera pelas strings de teste
        if test_key.lower() in broker_name.lower(): # Compara com o nome do corretor
            logger.info(f"Nome do corretor [{broker_name}] possui flag de teste '{test_key}'. Pulando atualização desse processo.")
            skip_flag = True

    if skip_flag:
        continue  # Pula a atualização desse processo

    if broker_id in monday_brokers:
        logger.info(f"Cadastrado no Monday com ID {monday_brokers[broker_id].get('monday_id')}.")
        monday_broker_id = monday_brokers[broker_id].get("id_monday")
        broker_state = "atualizar"
        # Adicionar lógica para comparar os dados do Monday com os do Otto e atualizar no Monday
        # caso tenham diferenças
    else:
        logger.info(f"Corretor sem cadastro no Monday.")
        monday_broker_id = "sem_id"
        broker_state = "criar"

    # Imobiliária
    real_estate_id = process_data.get("id_imobiliaria")
    logger.info(f"Imobiliária ID {real_estate_id}: {process_data.get('nome_imobiliaria', 'NOME NÃO INFORMADO')}")

    real_estate_name = process_data.get("nome_imobiliaria", "")
    skip_flag = False
    for test_key in TEST_KEYS: # itera pelas strings de teste
        if test_key.lower() in real_estate_name.lower(): # Compara com o nome da imobiliária
            logger.info(f"Nome da imobiliária [{real_estate_name}] possui flag de teste '{test_key}'. Pulando atualização desse processo.")
            skip_flag = True
    
    if skip_flag:
        continue  # Pula a atualização desse processo

    if real_estate_id in monday_real_estates:
        logger.info(f"Cadastrada no Monday com ID {monday_real_estates[real_estate_id].get('monday_id')}.")
        monday_real_estate_id = monday_real_estates[real_estate_id].get("id_monday")
        real_estate_state = "atualizar"
        # Adicionar lógica para comparar os dados do Monday com os do Otto e atualizar no Monday
        # caso tenham diferenças
    else:
        logger.info(f"Imobiliária sem cadastro no Monday.")
        monday_real_estate_id = "sem_id"
        real_estate_state = "criar"

    # Gerente
    manager_id = process_data.get("id_gerente")

    # Se negócio sem gerente
    if manager_id is None or manager_id == "":
        logger.info(f"Nenhum gerente associado ao processo.")
        monday_manager_id = "sem_id"
        manager_state = "pular"
    else:
        logger.info(f"Gerente ID {manager_id}: {process_data.get('nome_gerente', 'NOME NÃO INFORMADO')}")

        if manager_id in monday_managers:
            logger.info(f"Cadastrado no Monday com ID {monday_managers[manager_id].get('monday_id')}.")
            monday_manager_id = monday_managers[manager_id].get("id_monday")
            manager_state = "atualizar"
        else:
            logger.info(f"Gerente sem cadastro no Monday.")
            monday_manager_id = "sem_id"
            manager_state = "criar"

    # Executivo
    executive_id = process_data.get("id_executivo")

    # Se negócio sem executivo
    if executive_id is None or executive_id == "":
        logger.info(f"Nenhum executivo associado ao processo.")
        monday_executive_id = "sem_id"
        executive_state = "pular"
    else:
        logger.info(f"Executivo ID {executive_id}: {process_data.get('nome_executivo', 'NOME NÃO INFORMADO')}")

        if executive_id in monday_executives:
            logger.info(f"Cadastrado no Monday com ID {monday_executives[executive_id].get('monday_id')}.")
            monday_executive_id = monday_executives[executive_id].get("id_monday")
            executive_state = "atualizar"
        else:
            logger.info(f"Executivo sem cadastro no Monday.")
            monday_executive_id = "sem_id"
            executive_state = "criar"


    # Busca nos processos do Monday se o processo com esse ID já existe
    monday_process = monday_processes.get(process_id, {})
    """ Formato do dicionário monday_process:
    {
        item_id_monday (str): {
            'nome_processo': str,
            'status_item_monday': str,
            'status_negocio': str,
            'data_negocio': str,
            'id_negocio': int,
            'id_unidade': int,
            'nome_empreendimento': str,
            'nome_torre': str,
            'numero_unidade': int,
            'status_reserva': str,
            'posicao_fila': int,
            'status_integracao_reserva': dict,
            'nome_cliente': str,
            'nome_corretor': str,
            'nome_imobiliaria': str,
            'data_comeco_reserva': str,
            'status_proposta': str,
            'data_proposta': str,
            'perda_vpl': float,
            'desconto_politica': float,
            'percentual_financiado': float,
            'status_integracao_proposta': dict,
            'valor_proposta': float,
            'valor_comissao': float,
            'valor_liquido': float,
            'numero_proposta_gc': int,
            'link_reserva': dict,
            'link_proposta': dict,
            'percentual_comissao': float,
            'status_integracao_docusign': str,
            'id_envelope': str,
            'nome_contrato': str,
            'status_emissao': str,
            'status_contrato': str,
            'pendencias_analise': str,
            'link_contrato': dict,
            'documento_cliente': str,
            'id_corretor': int,
            'id_imobiliaria': int,
            'data_reserva': str,
            'proposta_criada_em': str,
            'status_analise_credito': str,
            'pendencias_credito': str,
            'status_pasta': str
        }
    }
    """
    
    #logger.info(f"ID: {process_id} - DATA: {process_data}")
    monday_id = None
    
    # Confirma se encontrou 0, 1 ou mais processos no Monday
    if monday_process == {}:
        logger.info(f"Nenhum processo encontrado no Monday.")
        # Mesmo que ainda não exista um processo no Monday com esse ID, conferimmos mais abaixo
        # se existem negócios para o mesmo cliente e unidade.
        # Se encontrarmos um negócio para o mesmo cliente e unidade e esse for do mesmo corretor,
        # podemos atualizar esse negócio com o ID do processo atual.
        # Caso contrário, criaremos um novo negócio no Monday para esse processo na etapa mais abaixo
        # onde isso for identificado.
        monday_id = "sem_id"  # ID fictício para indicar que o processo não existe no Monday
    else: # Caso normal, encontrou exatamente um processo, esse será atualizado
        monday_id = monday_process.get("id_monday")
        logger.info(f"Processo encontrado no Monday com ID {monday_id}.")

    # Busca nos possíveis conflitos negócios para o mesmo cliente (CPf ou CNPJ) e na mesma unidade
    if customer_document is None or unit_id is None: # Caso não tenha CPF ou CNPJ ou ID de unidade, não faz sentido buscar conflitos
        logger.warning(f"Nenhum CPF ou CNPJ disponível para buscar possíveis conflitos no Monday. Pulando verificação de conflitos.")
        possible_conflicts = {}
    else:
        possible_conflicts = [
            possible_conflict_monday_id for possible_conflict_monday_id, possible_conflict_item_data in all_possible_conflicts.items()
            if possible_conflict_item_data.get("documento_cliente") == customer_document
            and possible_conflict_item_data.get("id_unidade") == unit_id
        ]
    # podemos trocar para procurar por negócios no mesmo empreendimnento ou na mesma torre se quisermos ser mais rigorosos

    # Itera pelos possíveis conflitos
    # Importante: o negócio atual também pode aparecer como conflito, caso já tenha sido cadastrado anteriormente no Monday, então precisamos ignorá-lo
    #             caso o processo tenha sido criado agora no Monday, ele terá tanto o ID da unidade quanto o CPF/CNPJ do cliente em branco, então não aparecerá como um conflito
    conflict_warning = {}

    if possible_conflicts != []:
        
        total_conflicts = len(possible_conflicts)
        same_process_conflict = 0
        same_broker_conflict = 0
        real_conflicts = 0

        logger.info(f"Possíveis conflitos encontrados para o mesmo cliente na mesma unidade: {total_conflicts}")

        # Itera pelos conflitos encontrados
        for conflict_monday_id in possible_conflicts:

            conflict_item_data = all_possible_conflicts.get(conflict_monday_id, {})
            possible_conflict_brokers = conflict_item_data.get("id_corretor", [])

            # Caso o processo já tenha sido cadastrado anteriormente no Monday,
            # o negócio com o mesmo ID também deve aparecer como um conflito, mas temos que ignorá-lo
            if conflict_monday_id == monday_id:
                logger.debug(f"Ignorando conflito com negócio no Monday ID {monday_id}. Mesmo ID do processo atual.")
                same_process_conflict += 1
                continue
            
            # Também verificamos se o corretor do possível conflito é o mesmo do processo atual
            if possible_conflict_brokers == []:
                logger.warning(f"O possível conflito no Monday ID {conflict_monday_id} não possui corretor associado. Ignorando conflito.")
                continue
            else:
                possible_conflict_monday_brokers_ids = [
                    broker["id"] for broker in possible_conflict_brokers
                ]
                logger.info(f"Corretor(es) associado(s) ao possível conflito no Monday ID {conflict_monday_id}: {possible_conflict_monday_brokers_ids}")

            if monday_broker_id in possible_conflict_monday_brokers_ids:
                logger.info(f"Encontrado um processo no Monday ID {conflict_monday_id} para o mesmo cliente na mesma unidade pertencente ao mesmo corretor ID {monday_broker_id}.")
                # Nesse caso atualizamos o negócio no Monday com o novo ID do processo e 
                monday_id = conflict_monday_id
                monday_process = {monday_id: conflict_item_data}  # Atualiza o dicionário do processo no Monday para o conflito encontrado
                same_broker_conflict += 1
                continue
            else:
                # Caso o corretor seja diferente, podemos considerar que é um conflito de negócios
                # Criar lógica para tratar conflitos, como notificar o usuário ou marcar os itens no Monday.com
                logger.warning(f"Encontrado um processo no Monday ID {conflict_monday_id} para o mesmo cliente na mesma unidade pertencente a um corretor diferente ID {monday_broker_id}.")
                conflict_warning = {"pendencias_analise": {"labels": ["Cruzamento"]}}
                real_conflicts += 1
                # Por enquanto apenas logamos o conflito, mas não fazemos nenhuma ação corretiva automática

        logger.info(f"Mesmo processo: {same_process_conflict} | Mesmo corretor: {same_broker_conflict} | Conflitos reais: {real_conflicts}")

    # Com o ID do processo no Monday confirmado (seja existente ou novo), podemos prosseguir para atualizar os dados
    # com base nas informações do processo e suas atualizações de reservas e propostas

    #--------------------------------
    # INFORMAÇÕES DO PROCESSO
    #--------------------------------

    # Cria um dicionário para armazenar as atualizações a serem feitas no processo do Monday
    monday_update_dict = {
        "id_negocio": process_id,
        "negocio_criado_em": process_data.get("negocio_criado_em").strftime("%Y-%m-%d %H:%M:%S") if process_data.get("negocio_criado_em") else None, # Monday também recebe UTC, não precisa converter
        "id_unidade": unit_id,
        "nome_empreendimento": process_data.get("nome_empreendimento").title() if process_data.get("nome_empreendimento") else None,
        "nome_torre": process_data.get("nome_torre").title() if process_data.get("nome_torre") else None,
        "numero_unidade": process_data.get("numero_unidade"),
        "nome_cliente": customer_name.title() if customer_name else None,
        "documento_cliente": customer_document,
        "id_corretor": {"item_ids": [str(monday_broker_id)]}, # Relação com o quadro de corretores no Monday
        "nome_corretor": process_data.get("nome_corretor").title() if process_data.get("nome_corretor") else None,
        "id_imobiliaria": {"item_ids": [str(monday_real_estate_id)]}, # Relação com o quadro de imobiliárias no Monday
        "nome_imobiliaria": process_data.get("nome_imobiliaria").title() if process_data.get("nome_imobiliaria") else None,
    }

    # Adiciona o aviso de cruzamento caso haja um possível conflito de negócios para o mesmo cliente e unidade com corretor diferente
    if conflict_warning != {}:
        monday_update_dict.update(conflict_warning)
    
    # Caso tenha informação de executivo ou gerente
    if manager_state != "pular":
        monday_update_dict["id_gerente"] = {"item_ids": [str(monday_manager_id)]} # Relação com o quadro de gerentes no Monday
    if executive_state != "pular":
        monday_update_dict["id_executivo"] = {"item_ids": [str(monday_executive_id)]} # Relação com o quadro de executivos no Monday


    # Atualmente essa informação de vendedor só é atualizada na criação do processo no Monday
    if process_data.get("flag_permuta", False):
        monday_update_dict["id_vendedor"] = {"item_ids": [OWNERS["permutante"]]}  # ID do item "Permuta" no board de contas
    else:
        id_empreendimento = int(process_data.get("id_integracao_empreendimento"))
        print(f"ID do empreendimento para buscar vendedor: {id_empreendimento}")
        cnpj_empreendimento = empresas.get(id_empreendimento, {}).get("cnpj")
        cnpj_empreendimento = normalizar_cnpj(cnpj_empreendimento)
        print(f"CNPJ do empreendimento para buscar vendedor: {cnpj_empreendimento}")
        nome_empresa = empresas.get(id_empreendimento, {}).get("nm_empresa", "Empresa não identificada")
        print(f"Nome do empreendimento para buscar vendedor: {nome_empresa}")
        if not cnpj_empreendimento:
            logger.warning(f"CNPJ inválido para o empreendimento ID {id_empreendimento}. Pulando criação de empresa no Monday.")
            empresa_no_monday = {}
        else:
            empresa_no_monday = monday_companies.get(cnpj_empreendimento, {})
        if not empresa_no_monday and cnpj_empreendimento:
            logger.warning(f"Nenhuma empresa encontrada no Monday para o empreendimento ID {id_empreendimento} com CNPJ {cnpj_empreendimento}. Criando nova empresa no Monday para esse empreendimento.")
            id_empresa_no_monday = cliente_monday.create_item(
                board_id=ACCOUNTS_BOARD_ID,
                group_id="group_mkywb4t3",
                item_name=nome_empresa,
                column_values={
                    "cpf_cnpj": cnpj_empreendimento,
                    "tipo_de_conta": "Vendedor",
                }
            )
            logger.info(f"Empresa criada no Monday com ID {id_empresa_no_monday} para o empreendimento ID {id_empreendimento} com CNPJ {cnpj_empreendimento}.")
            empresa_no_monday["id_monday"] = id_empresa_no_monday
            monday_companies.update({cnpj_empreendimento: {"id_monday": id_empresa_no_monday}})
        else:
            logger.info(f"Empresa encontrada no Monday para o empreendimento ID {id_empreendimento} com CNPJ {cnpj_empreendimento}. ID no Monday: {empresa_no_monday.get('id_monday')}.")

        if empresa_no_monday.get("id_monday"):
            monday_update_dict["id_vendedor"] = {"item_ids": [empresa_no_monday["id_monday"]]}

    #--------------------------------
    # REGRAS DE NEGÓCIO
    #--------------------------------

    # Itera sobre as atualizações do processo em ordem cronológica
    for update in process_data["atualizacoes"]:
        update_type = update["tipo"]
        update_data = update["dados"]
        update_id = update["id"]

        if update_type == "reserva":
            logger.info(f"Processando atualização de reserva ID {update_id}.")
            logger.debug(f"Detalhes da reserva: {update_data}")
            booking_status_id = update_data.get("id_status_reserva", 0) if update_data.get("id_status_reserva") is not None else 0
            booking_status = STATUS_RESERVA.get(booking_status_id, "Status desconhecido")

            if booking_status == "Status desconhecido":
                logger.error(f"Status de reserva desconhecido ID {booking_status_id} para a reserva ID {update_id}.")
            elif booking_status == "Cancelada":
                logger.info(f"Reserva ID {update_id} está cancelada. Mantendo o status anterior.")
            else:
                posicao_fila = update_data.get("posicao_fila", None)
                if posicao_fila is not None and posicao_fila > 1:
                    logger.info(f"Reserva está na posição {posicao_fila} da fila. Colocando o status 'Na fila'.")
                    booking_status = "Na fila"
                
                monday_update_dict["status_reserva"] = booking_status
                logger.info(f"Status de reserva atualizado para '{booking_status}'.")

            # Recupera as informações sobre a integração da reserva
            integration_result = update_data.get("resultado_integracao_reserva", {})
            logger.debug(f"Resultado da integração da reserva ID {update_id}: {integration_result}")
            if integration_result is not None:
                integration_status = integration_result.get("status")
                logger.debug(f"Status da integração da reserva ID {update_id}: {integration_status}")
                if integration_status is not None:
                    monday_update_dict.update({
                        "status_integracao_reserva": integration_status,
                    })
            else: # Caso o resultado da integração seja None, limpamos o campo no Monday
                # Os negócios podem ter tido reservas anteriores canceladas depois da integração
                # e novos processos de reserva iniciados sem integração, como em segundo lugar na fila
                monday_update_dict.update({
                    "status_integracao_reserva": None,
                })

            monday_update_dict.update({
                "posicao_fila": update_data.get("posicao_fila"),
                "data_reserva": update_data.get("reserva_criada_em").strftime("%Y-%m-%d %H:%M:%S") if update_data.get("reserva_criada_em") else None,
                "data_comeco_reserva": update_data.get("inicio_primeira_posicao").strftime("%Y-%m-%d %H:%M:%S") if update_data.get("inicio_primeira_posicao") else None,
                "link_reserva": {
                    "url": "https://admin.beotto.com/reserva/" + str(update_id),
                    "text": "Link da Reserva"
                },
            })


        elif update_type == "proposta":
            logger.info(f"Processando atualização de proposta ID {update_id}.")
            logger.debug(f"Detalhes da proposta: {update_data}")
            proposal_status_id = update_data.get("id_status_proposta", 0) if update_data.get("id_status_proposta") is not None else 0
            proposal_status = STATUS_PROPOSTA.get(proposal_status_id, "Status desconhecido")

            if proposal_status == "Status desconhecido":
                logger.error(f"Status de proposta desconhecido ID {proposal_status_id} para a proposta ID {update_id}.")
            elif proposal_status == "Cancelada":
                logger.info(f"Proposta ID {update_id} está cancelada. Mantendo o status anterior.")
            elif proposal_status == "Não enviada":
                logger.info(f"Proposta ID {update_id} não foi enviada ainda.")
            else:
                monday_update_dict["status_proposta"] = proposal_status
                logger.info(f"Status de proposta atualizado para '{proposal_status}'.")

            # Recupera as informações sobre a integração da proposta
            integration_result = update_data.get("resultado_integracao_proposta", {})
            if integration_result:  # Verifica se não é vazio
                integration_status = integration_result.get("status")
                if integration_status is not None:
                    monday_update_dict.update({
                        "status_integracao_proposta": integration_status,
                    })
                    
                    # Tenta extrair o número da proposta GC de forma segura
                    try:
                        numero_pv = integration_result.get('rawResponse', {}).get('PVRet', [{}])[0].get('PnvCod')
                        if numero_pv:
                            monday_update_dict["numero_proposta_gc"] = numero_pv
                    except (KeyError, IndexError, TypeError):
                        logger.warning(f"Não foi possível extrair o número da proposta GC para a proposta ID {update_id}.")
                    
                    # Tenta extrair a perda de VPL de forma segura
                    try:
                        perda_vpl_str = integration_result.get('rawResponse', {}).get('PVRet', [{}])[0].get('PnvPdaVPL')
                        if perda_vpl_str:
                            monday_update_dict["perda_vpl"] = float(perda_vpl_str)
                    except (KeyError, IndexError, TypeError, ValueError):
                        logger.debug(f"Não foi possível extrair a perda de VPL para a proposta ID {update_id}.")
                    
                    # IDEIA: Não modificar mais o número da proposta após a proposta estar como "Aprovada" no Monday
                    # É possível que seja necessário uma lógica para atualizar ou não o número da proposta, 
                    # dependendo de quem a atualização (sistema externo ou usuário manualmente)
                    # Assim é possível corrigir o numero da PV sem que o sistema sobrescreva

            monday_update_dict.update({
                "data_proposta": update_data.get("proposta_enviada_em").strftime("%Y-%m-%d %H:%M:%S") if update_data.get("proposta_enviada_em") else None,
                "proposta_criada_em": update_data.get("proposta_criada_em").strftime("%Y-%m-%d %H:%M:%S") if update_data.get("proposta_criada_em") else None,
                "valor_proposta": float(update_data.get("valor_proposta")) if update_data.get("valor_proposta") is not None else None,
                "valor_comissao": float(update_data.get("valor_comissao")) if update_data.get("valor_comissao") is not None else None,
                "valor_liquido": float(update_data.get("valor_liquido")) if update_data.get("valor_liquido") is not None else None,
                "percentual_financiado": float(update_data.get("percentual_financiado")) if update_data.get("percentual_financiado") is not None else None,
                "percentual_comissao": float(update_data.get("percentual_comissao")) if update_data.get("percentual_comissao") is not None else None,
                "link_proposta": {
                    "url": "https://admin.beotto.com/proposta/" + str(process_id),
                    "text": "Link da Proposta"
                },
            })
    
    # Confirmamos se o negócio precisa ser atualizado no Monday. Faremos isso apenas se ele não existir ainda
    # ou se houver colunas com valores diferentes entre o Otto e o Monday
    if monday_process != {}:
        #logger.info(f"Verificando necessidade de atualização do processo no Monday ID {monday_id}.")
        for key in list(monday_update_dict.keys()):
            monday_value = monday_process.get(key)
            update_value = monday_update_dict.get(key)
            if update_value is not None:
                # Tenta lidar com os formatos diferentes de dados entre o dicionário de atualização e Monday
                logger.debug(f"Tipo do campo '{key}': Monday = {type(monday_value)}, Update = {type(update_value)}")
                if isinstance(monday_value, list) and isinstance(update_value, dict):
                    # Caso especial para colunas do tipo relacionamento (link entre boards)
                    # Onde o Monday retorna uma lista de dicionários:
                    # [{'id': '10835436984', 'name': 'Alex'}]
                    # E o update um dicionário:
                    # {'item_ids': ['10835436984']}
                    logger.debug("Comparando valores de coluna do tipo relacionamento (link entre boards).")
                    ids_in_monday = set()
                    for item in monday_value:
                        ids_in_monday.add(str(item.get("id")))
                    
                    ids_in_update = set(map(str, update_value.get("item_ids", [])))
                    if ids_in_monday != ids_in_update:
                        logger.debug(f"Campo '{key}' será atualizado de '{ids_in_monday}' para '{ids_in_update}'.")
                    else:
                        logger.debug(f"Campo '{key}' não precisa ser atualizado. Valor atual: '{ids_in_monday}'.")
                        monday_update_dict.pop(key)  # Remove do dicionário de atualização para não fazer update desnecessário
                else:
                    logger.debug("Convertendo valores para string e limpando para comparação.")
                    monday_value = str(monday_value).strip() if monday_value is not None else ""
                    update_value = str(update_value).strip() if update_value is not None else ""
                    logger.debug(f"Tipos convertidos do campo '{key}': Monday = {type(monday_value)}, Update = {type(update_value)}")

                    if monday_value != update_value:
                        logger.debug(f"Campo '{key}' será atualizado de '{monday_value}' para '{update_value}'.")
                    else:
                        logger.debug(f"Campo '{key}' não precisa ser atualizado. Valor atual: '{monday_value}'.")
                        monday_update_dict.pop(key)  # Remove do dicionário de atualização para não fazer update desnecessário

    logger.debug(f"Dicionário de atualização antes do mapeamento para o Monday: {monday_update_dict}")
    monday_update_info = monday_update_dict.copy()

    # Mapeia o dicionário final de atualizações para os nomes das colunas do Monday
    from Módulos.mapeamento_dados import map_dict_keys
    monday_update_dict = map_dict_keys("monday", str(PROCESSES_BOARD_ID), monday_update_dict, invert_mapping=True)
    #logger.info(f"DATA: {monday_update_dict}")

    # Controle de o que deve ser criado e o que deve ser atualizado no Monday
    process_state = "pular"

    # Analizamos os casos específicos
    # Caso o negócio não exista no Monday (monday_id == "sem_id") e existam atualizações para ele (monday_update_dict != {})
    if monday_id == "sem_id" and monday_update_dict != {}:
        # Caso não tenhamos status de reserva ou proposta enviada, não criaremos o processo no Monday ainda        
        if "status_reserva" not in monday_update_dict and "status_proposta" not in monday_update_dict:
            logger.info(f"Nenhuma reserva ou proposta enviada encontrada para o processo. Pulando criação no Monday.")
            continue  # Pula para o próximo processo

        # Caso tenhamos algum status, seja de proposta ou reserva, podemos criar o processo no Monday
        process_state = "criar"

    # Caso o negócio não exista no Monday (monday_id == "sem_id") e não existam atualizações para ele (monday_update_dict == {})
    elif monday_id == "sem_id" and monday_update_dict == {}:
        logger.info(f"Nenhuma atualização encontrada para o processo. Pulando criação no Monday.")
        continue  # Pula para o próximo processo
    
    # Caso o ID do monday do negócio chegue aqui como None, algo deu errado
    elif monday_id is None:
        logger.error(f"ID do processo no Monday é None. Não é possível prosseguir com a atualização.")
        continue  # Pula para o próximo processo
    
    # Caso o negócio já exista no Monday (monday_id != "sem_id")
    elif monday_id != "sem_id":
        # Atualizamos o processo existente no Monday
        process_state = "atualizar"

    else:
        logger.error(f"Erro inesperado ao determinar o ID do processo no Monday: {monday_id}. Atualizações: {process_data.get('total_atualizacoes', 0)}. Pulando atualização.")
        continue  # Pula para o próximo processo

    # Atualização ou criação dos itens no Monday
    if process_state == "pular":
        logger.info(f"Nenhuma ação necessária para o processo ID {process_id}.")
        continue
    
    # Corretores
    if broker_state == "criar":
        logger.info(f"Criando corretor no Monday.")

        monday_broker_id = cliente_monday.create_item(
            board_id=ACCOUNTS_BOARD_ID,
            group_id="group_mkyshgwh", # ID do grupo para corretores
            item_name=process_data.get("nome_corretor", "NOME NÃO INFORMADO").title(),
            column_values={
                "text_mkywmptw": broker_id, # Coluna de ID Otto
                "tipo_de_conta": "Corretor",
                "cpf_cnpj": process_data.get("cpf_corretor"),
                "creci": process_data.get("creci_corretor"),
            },
        )

        if not monday_broker_id:
            logger.error(f"Erro ao criar corretor ID {broker_id} no Monday.")
            raise Exception(f"Erro ao criar corretor ID {broker_id} no Monday.")

        logger.info(f"Corretor criado no Monday com ID {monday_broker_id}.")

        monday_brokers[broker_id] = {
            "id_monday": monday_broker_id,
            "nome": process_data.get("nome_corretor", "NOME NÃO INFORMADO"),
            "tipo_de_conta": "Corretor",
            "documento": process_data.get("cpf_corretor"),
            "creci": process_data.get("creci_corretor"),
        }

    elif broker_state == "atualizar":
        logger.info(f"Criar lógica de atualização de corretor no Monday.")

    # Imobiliárias
    if real_estate_state == "criar":
        monday_real_estate_id = cliente_monday.create_item(
            board_id=ACCOUNTS_BOARD_ID,
            group_id="group_title", # ID do grupo para imobiliáris
            item_name=process_data.get("nome_imobiliaria", "NOME NÃO INFORMADO").title(),
            column_values={
                "text_mkywmptw": real_estate_id,
                "tipo_de_conta": "Imobiliária",
                "cpf_cnpj": process_data.get("cnpj_imobiliaria"),
                "creci": process_data.get("creci_imobiliaria"),
            },
        )

        if not monday_real_estate_id:
            logger.error(f"Erro ao criar imobiliária ID {real_estate_id} no Monday.")
            raise Exception(f"Erro ao criar imobiliária ID {real_estate_id} no Monday.")
        
        logger.info(f"Imobiliária criada no Monday com ID {monday_real_estate_id}.")

        monday_real_estates[real_estate_id] = {
            "id_monday": monday_real_estate_id,
            "nome": process_data.get("nome_imobiliaria", "NOME NÃO INFORMADO"),
            "tipo_de_conta": "Imobiliária",
            "documento": process_data.get("cnpj_imobiliaria"),
            "creci": process_data.get("creci_imobiliaria"),
        }
    
    elif real_estate_state == "atualizar":
        logger.info(f"Criar lógica de atualização de imobiliária no Monday.")

    # Gerentes
    if manager_state == "criar":
        monday_manager_id = cliente_monday.create_item(
            board_id=ACCOUNTS_BOARD_ID,
            group_id="group_mm02915k", # ID do grupo para gerentes
            item_name=process_data.get("nome_gerente", "NOME NÃO INFORMADO").title(),
            column_values={
                "text_mkywmptw": manager_id,
                "tipo_de_conta": "Gerente",
                #"cpf_cnpj": process_data.get("cpf_gerente"),
            },
        )

        if not monday_manager_id:
            logger.error(f"Erro ao criar gerente ID {manager_id} no Monday.")
            raise Exception(f"Erro ao criar gerente ID {manager_id} no Monday.")
        
        logger.info(f"Gerente criado no Monday com ID {monday_manager_id}.")

        monday_managers[manager_id] = {
            "id_monday": monday_manager_id,
            "nome": process_data.get("nome_gerente", "NOME NÃO INFORMADO"),
            "tipo_de_conta": "Gerente",
            #"documento": process_data.get("cpf_gerente"),
        }

    elif manager_state == "atualizar":
        logger.info(f"Criar lógica de atualização de gerente no Monday.")

    # Executivos
    if executive_state == "criar":
        monday_executive_id = cliente_monday.create_item(
            board_id=ACCOUNTS_BOARD_ID,
            group_id="group_mm02f9e9", # ID do grupo para executivos
            item_name=process_data.get("nome_executivo", "NOME NÃO INFORMADO").title(),
            column_values={
                "text_mkywmptw": executive_id,
                "tipo_de_conta": "Executivo",
                #"cpf_cnpj": process_data.get("cpf_executivo"),
            },
        )

        if not monday_executive_id:
            logger.error(f"Erro ao criar executivo ID {executive_id} no Monday.")
            raise Exception(f"Erro ao criar executivo ID {executive_id} no Monday.")
        
        logger.info(f"Executivo criado no Monday com ID {monday_executive_id}.")

        monday_executives[executive_id] = {
            "id_monday": monday_executive_id,
            "nome": process_data.get("nome_executivo", "NOME NÃO INFORMADO"),
            "tipo_de_conta": "Executivo",
            #"documento": process_data.get("cpf_executivo"),
        }

    elif executive_state == "atualizar":
        logger.info(f"Criar lógica de atualização de executivo no Monday.")

    # Atualiza o dicionário de atualização com os IDs corretos do corretor, imobiliária, gerente e executivo no Monday
    monday_update_dict["corretor"] = {"item_ids": [str(monday_broker_id)]} # Usa o id da coluna no Monday
    monday_update_dict["imobiliaria"] = {"item_ids": [str(monday_real_estate_id)]} # Usa o id da coluna no Monday
    if manager_state != "pular": # Se for pular o gerente não existe, pular a carga do ID (sem_id)
        monday_update_dict["gerente"] = {"item_ids": [str(monday_manager_id)]} # Usa o id da coluna no Monday
    if executive_state != "pular": # Se for pular o executivo não existe, pular a carga do ID (sem_id)
        monday_update_dict["executivo"] = {"item_ids": [str(monday_executive_id)]} # Usa o id da coluna no Monday

    logger.info(f"DATA: {monday_update_dict}")

    # Negócios
    if process_state == "criar":
        logger.info(f"Criando um novo processo no Monday para este negócio.")
        process_name = (
            process_data.get("nome_empreendimento", "SEM EMPREENDIMENTO") + " | "
            + process_data.get("nome_torre", "SEM TORRE")+ " | "
            + process_data.get("numero_unidade", "SEM UNIDADE") + " | "
            + customer_name
        )
        monday_id = cliente_monday.create_item(
            board_id=PROCESSES_BOARD_ID,
            item_name=process_name.upper(),
            column_values=monday_update_dict,
        )
        monday_process = {monday_id: {}}  # Inicializa o dicionário do processo no Monday
        logger.info(f"Novo processo criado no Monday com ID {monday_id}.")
        all_possible_conflicts[monday_id] = monday_update_info  # Adiciona o novo processo aos possíveis conflitos para futuras iterações

    elif process_state == "atualizar":
        logger.info(f"Atualizando processo existente no Monday ID {monday_id}.")
        if monday_update_dict == {}:
            logger.info(f"Sem informações a atualizar para o processo ID {monday_id}. Pulando atualização.")
            continue  # Pula para o próximo processo

        # TEMPORÁRIO
        monday_update_dict.pop("id_vendedor", None)  # Remove o campo de id_vendedor temporariamente até definirmos a lógica correta para ele
        # Fim do TEMPORÁRIO
        
        cliente_monday.update_item(
            board_id=PROCESSES_BOARD_ID,
            item_id=str(monday_id),
            column_values=monday_update_dict,
        )
        logger.info(f"Processo atualizado com sucesso no Monday.")

    else:
        logger.error(f"Nenhuma ação realizada para o processo ID {process_id}.")

    logger.info("------------------------------------------------")
# # Acompanhamento de desempenho
# elapsed_time = time.time() - start_time
# update_durations.append(elapsed_time)

# # Evita divisão por zero quando não há durações registradas
# if update_durations and sum(update_durations) > 0:
#     expected_remaining_time_string = format_seconds_to_time(mean(update_durations) * (total_processes - counter))
#     total_elapsed_time_string = format_seconds_to_time(sum(update_durations))
#     performance = counter / sum(update_durations)
    
#     # Evita divisão por zero ao calcular segundos por processo
#     if performance > 0:
#         performance_string = f"{performance:.2f} p/s" if performance > 1 else f"{(1 / performance):.2f} s/p"
#     else:
#         performance_string = "N/A"
# else:
#     expected_remaining_time_string = "N/A"
#     total_elapsed_time_string = format_seconds_to_time(elapsed_time) if elapsed_time > 0 else "0 s"
#     performance_string = "N/A"

# # Evita divisão por zero quando não há processos
# percentage = (counter / total_processes * 100) if total_processes > 0 else 0.0
# logger.info(f"{counter}/{total_processes} - {percentage:.2f}% [{total_elapsed_time_string} / {expected_remaining_time_string}, {performance_string}]")
# logger.info("--------------------------------------------------")

#--------------------------------
# FINALIZAÇÃO
#--------------------------------
logger.info("#---- Finalização ----#")
logger.info("Atualização do Relatório Comercial no Monday.com concluída.")

# Salva a data e hora do começo dessa execução como a última atualização completa
with open(last_update_file_path, "w") as f:
    f.write(current_time_utc_minus3.strftime("%Y-%m-%d %H:%M:%S"))
    logger.info(f"Data e hora desta atualização salva: {current_time_utc_minus3.strftime('%Y-%m-%d %H:%M:%S')} (UTC-3)")


logger.info("--------------------------------------------------")
logger.info("#---- Atualização Docusign ----#")
