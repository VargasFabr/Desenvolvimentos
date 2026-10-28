# %%
"""
Script para fazer refresh de dataset do Power BI usando variáveis de ambiente.
Usa MSAL com Service Principal (Client ID + Client Secret).

explicação de como criar os clients: https://www.youtube.com/watch?v=IFp1Aingnmw
fazer opasso a passo em https://entra.microsoft.com/

explicação do código: https://www.youtube.com/watch?v=27VB8dVzCis
"""
import requests
import msal
# from dotenv import load_dotenv
# import os

# # Carregar variÃ¡veis de ambiente do arquivo .env
# load_dotenv()

# Obter credenciais do arquivo .env
tenant_id = "9e9dd196-97f4-4d35-ba33-7db6ac127be2"
client_id = "b05142d8-7e4f-4106-8607-e25a29105d6c"
client_secret = "hmg8Q~gEzac1P5xRmYUTUZ2gnU59p3YD462b7a85"

# Configurar autenticaÃ§Ã£o
authority_url = f"https://login.microsoftonline.com/{tenant_id}"
scope = ["https://analysis.windows.net/powerbi/api/.default"]

# Obter token de acesso
app = msal.ConfidentialClientApplication(
    client_id, 
    authority=authority_url, 
    client_credential=client_secret
)
token_response = app.acquire_token_for_client(scopes=scope)
access_token = token_response['access_token']

# IDs do workspace e dataset
workspace_id = "f62624e8-72b6-4c62-b665-4aea40163e6f"
dataset_id = "844b93d9-bb9d-483f-a7da-28b7be1528d6"

# Fazer requisiÃ§Ã£o de refresh
api_url = f'https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets/{dataset_id}/refreshes'
headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {access_token}'
}
response = requests.post(url=api_url, headers=headers)

# Verificar resultado
if response.status_code == 202:
    print("AtualizaÃ§Ã£o iniciada com sucesso!")
else:
    print(f"Erro ao atualizar: {response.status_code} - {response.text}")

