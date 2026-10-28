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

# Salva o arquivo em um local para consulta
output_directory_path = r"Sharepoint"
output_file_path = os.path.join(output_directory_path, "Envelopes.json")

# Carrega os dados existentes dos envelopes atualizados, se o arquivo existir, para evitar perda de dados em caso de falhas durante a execução
import json
if os.path.exists(output_file_path):
    with open(output_file_path, "r", encoding="utf-8") as f:
        existing_data = json.load(f)
    print(f"Dados existentes de envelopes atualizados carregados do arquivo {output_file_path}.")
else:
    existing_data = {}
    print(f"Arquivo {output_file_path} não encontrado. Nenhum dado existente de envelopes atualizado será carregado.")




#--------------------------------
# CONTROLE DE ATUALIZAÇÕES
#--------------------------------

# Data da última atualização completa
last_update_file_path = os.path.join(data_file_path, "ultima_atualizacao_excel_apoio.txt")
os.makedirs(os.path.dirname(last_update_file_path), exist_ok=True)  # Garante que a pasta Dados exista dentro da pasta do projeto AutoBackoffice

# Carregar a data da última atualização de um arquivo txt ou usa uma data inicial padrão se o arquivo não existir
if os.path.exists(last_update_file_path):
    with open(last_update_file_path, "r") as f:
        last_updated_at = f.read().strip()
    print(f"Última atualização completa: {last_updated_at}")
else:
    last_updated_at = "2026-02-01 22:00:00"  # Data inicial padrão
    print(f"Arquivo de última atualização não encontrado. Usando data inicial padrão {last_updated_at}.")

from datetime import datetime, timezone, timedelta

# Horário desta execução
current_time_utc = datetime.now(timezone.utc)
# Retira 60 segundos do horário atual para evitar problemas de sincronização
current_time_utc = current_time_utc - timedelta(seconds=60)
# Converte o horário atual para UTC-3
current_time_brt = current_time_utc.astimezone(timezone(timedelta(hours=-3)))
current_time_brt_string = current_time_brt.strftime("%Y-%m-%d %H:%M:%S")

# Transforma em datetime para manipulação de fuso horário
last_updated_at_dt = datetime.strptime(last_updated_at, "%Y-%m-%d %H:%M:%S")
# Adiciona 3 horas para converter de UTC-3 para UTC
last_updated_at_dt_utc = last_updated_at_dt.replace(tzinfo=timezone(timedelta(hours=-3))).astimezone(timezone.utc)
# Transforma de volta em string no formato esperado pelo banco de dados
last_updated_at = last_updated_at_dt_utc.strftime("%Y-%m-%d %H:%M:%S")
print(f"Última atualização completa convertida para UTC: {last_updated_at}")
#--------------------------------



#--------------------------------
# SETUP DE CLIENTES
#--------------------------------

# Cliente do DocuSign
from Módulos.cliente_docusign import DocuClient

# Busca e confirma que existem as variáveis de ambiente do DocuSign
account_id = os.getenv("DOCU_ACCOUNT")
if not account_id:
    raise ValueError("A variável de ambiente DOCUSIGN_ACCOUNT_ID do DocuSign não foi encontrada nas variáveis de ambiente. Verifique o arquivo .env.")
print("Chave de API do DocuSign encontrada com sucesso nas variáveis de ambiente.")

user = os.getenv("DOCU_USER")
if not user:
    raise ValueError("A variável de ambiente DOCUSIGN_USER_EMAIL do DocuSign não foi encontrada nas variáveis de ambiente. Verifique o arquivo .env.")
print("Usuário do DocuSign encontrado com sucesso nas variáveis de ambiente.")

password = os.getenv("DOCU_PASSWORD")
if not password:
    raise ValueError("A variável de ambiente DOCUSIGN_USER_PASSWORD do DocuSign não foi encontrada nas variáveis de ambiente. Verifique o arquivo .env.")
print("Senha do DocuSign encontrada com sucesso nas variáveis de ambiente.")

# token = os.getenv("DOCUSIGN_TOKEN")
# if not token:
#     print("A variável de ambiente DOCUSIGN_TOKEN do DocuSign não foi encontrada nas variáveis de ambiente. O token será gerado automaticamente a partir do usuário e senha fornecidos.")
# else:
#     print("Token do DocuSign encontrado com sucesso nas variáveis de ambiente. Ele será usado para autenticação.")


cliente_docu = DocuClient(account_id=account_id, user=user, password=password, data_file_path=data_file_path)
cliente_docu.ensure_authenticated()




#--------------------------------
# BUSCA DE ENVELOPES ATUALIZADOS
#--------------------------------
print("Buscando envelopes atualizados desde a última atualização completa...")
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

# Atualiza os dados dos envelopes existentes com os dados dos envelopes atualizados, para evitar perda de dados em caso de falhas durante a execução
if existing_data != {}:
    for envelope_id, envelope_data in updated_envelopes.items():
        existing_data[envelope_id] = envelope_data
    updated_envelopes_data = existing_data
    print(f"Dados dos envelopes atualizados combinados com os dados existentes para evitar perda de dados. Total de envelopes após combinação: {len(updated_envelopes)}.")
else:
    updated_envelopes_data = updated_envelopes
    print(f"Não havia dados existentes de envelopes atualizados. Usando apenas os dados dos envelopes atualizados desta execução. Total de envelopes: {len(updated_envelopes)}.")


# Salva os dados dos envelopes em um arquivo JSON
os.makedirs(output_directory_path, exist_ok=True)  # Garante que a pasta de saída exista
with open(output_file_path, "w", encoding="utf-8") as f:
    print(f"Salvando os dados dos envelopes atualizados no arquivo {output_file_path}...")
    json.dump(updated_envelopes_data, f, ensure_ascii=False, indent=4)

# Salva a data e hora do começo dessa execução como a última atualização completa
with open(last_update_file_path, "w") as f:
    f.write(current_time_brt.strftime("%Y-%m-%d %H:%M:%S"))
    print(f"Data e hora desta atualização salva: {current_time_brt.strftime('%Y-%m-%d %H:%M:%S')} (UTC-3)")