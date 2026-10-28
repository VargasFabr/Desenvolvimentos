import os
from datetime import datetime
import logging
import requests
import json
import pandas as pd
from time import sleep

# Configurations set up
data_directory_name = "Regiões"
logger = logging.getLogger(__name__)

class OruloRegion:
    """
    Classe com dados da região de acesso ao Órulo
    """
    def __init__(self, code, name, client_id, client_secret, authentication=(),
                token="", last_update="01/01/2026 00:00:01", data_path="",
                error_buildings_ids=None):        
        self.code = code # Código da região, usando código de 3 letras para a cidade principal, se essa for a única cidade usar o sufixo "-CI" e se for uma região metropolitana use o sufixo "-RM"
        self.name = name # Usar o nome da cidade, escrito por extendo e juntar "e Região Metropolitana" se for o caso
        self.authentication = (
            client_id,
            client_secret
        )
        self.get_API_token() # Saves the acces token for the API

        self.directory_path = f"{data_path}/{data_directory_name}/{code}" # Caminho para a pasta da região dentro da pasta de Bases
        os.makedirs(self.directory_path, exist_ok=True) # Cria a pasta da região caso ela não exista
        # Define the path for the last update file
        last_update_file_path = f"{self.directory_path}/Última Atualização.txt"

        # Read the last update or create a new file with the default value
        if os.path.exists(last_update_file_path):
            with open(last_update_file_path, 'r') as file:
                self.last_update = file.read().strip() or "01/01/2026 00:00:01"
            if self.last_update == "01/01/2026 00:00:01":
                logger.info(f"Região {self.code}: última atualização vazia no arquivo; usando fallback {self.last_update}")
            else:
                logger.info(f"Região {self.code}: última atualização carregada do arquivo: {self.last_update}")
        else:
            self.last_update = "01/01/2026 00:00:01"
            with open(last_update_file_path, 'w') as file:
                file.write(self.last_update)
            logger.info(
                f"Região {self.code}: arquivo de última atualização não encontrado; criado com fallback {self.last_update}"
            )

        self.error_buildings_ids = [] if error_buildings_ids is None else error_buildings_ids  # Initialize new list for each instance

    def get_API_token(self):
        """
        Salva o token de acesso para a região
        """
        # Parâmetros de acesso.
        body_params = {'grant_type' : 'client_credentials'}
        url = 'https://www.orulo.com.br/oauth/token'
        # Chama a API com request de token    
        response = requests.post(url, data=body_params, auth=self.authentication)
        if response.status_code == 200:
            # Armazena o token na variável para acessos futuros
            token_raw = json.loads(response.text)
            self.token = token_raw["access_token"]
            logger.info(f"Token para {self.name} salvo com sucesso")
        else:
            logger.error(f"A requisição do token para {self.name} falhou")

    def get_list_of_buildings_to_update(self, results_per_page=50):
        """
        Retorna uma lista com os códigos dos empreendimentos a serem atualizados
        """
        buildings_list = []
        # Define os parâmetros do primeiro request
        headers = {"Authorization": "Bearer {}".format(self.token)}
        params = {'include[]':'not_available', 'page':1, 'results_per_page':results_per_page,'updated_after':self.last_update}
        # Chama a primeira página
        logger.info(f"Solicitando a primeira página para a região {self.name}")
        
        max_retries = 5
        data = None
        for attempt in range(max_retries):
            try:
                request_building = requests.get(url="https://www.orulo.com.br/api/v2/buildings", headers=headers, params=params)
                if request_building.status_code != 200:
                    raise Exception(f"Página não encontrada. Erro {request_building.status_code} na requisição da página 1")
                data = json.loads(request_building.text)
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"Erro ao acessar a API do Órulo: {e}")
                    logger.warning(f"Tentativa {attempt + 1}/{max_retries}. Aguardando {wait_time}s antes de tentar novamente...")
                    sleep(wait_time)
                else:
                    raise Exception(f"Erro ao acessar a API do Órulo após {max_retries} tentativas. Verifique sua conexão com a internet ou o status da API.")

        if data is None:
            raise Exception("Falha ao obter dados da primeira página.")

        pages_to_update = data["total_pages"]
        logger.info(f"{data['total']} empreendimentos a serem atualizados em {pages_to_update} páginas")
        buildings_list.extend([building['id'] for building in data['buildings']])
        # Itera pelas páginas restantes
        for page in range(2, pages_to_update + 1):
            logger.debug(f"Solicitando a página {page}")
            params = {'include[]':'not_available', 'comercial_status':'for_sale', 'page':page, 'results_per_page':results_per_page,'updated_after':self.last_update}
            data = None
            
            for attempt in range(max_retries):
                try:
                    request_building = requests.get(url="https://www.orulo.com.br/api/v2/buildings", headers=headers, params=params)
                    if request_building.status_code != 200:
                        raise Exception(f"Erro {request_building.status_code} na requisição da página {page}")
                    data = json.loads(request_building.text)
                    break
                except Exception as e:
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt
                        logger.warning(f"Erro ao acessar a API do Órulo: {e}")
                        logger.warning(f"Tentativa {attempt + 1}/{max_retries}. Aguardando {wait_time}s antes de tentar novamente...")
                        sleep(wait_time)
                    else:
                        raise Exception(f"Erro ao acessar a API do Órulo após {max_retries} tentativas na página {page}.")

            if data is None:
                raise Exception(f"Falha ao obter dados da página {page}.")
            
            buildings_list.extend([building['id'] for building in data['buildings']])
        
        buildings_list = list(set(buildings_list)) # Transforma em set para remover duplicatas
        logger.info(f"{len(buildings_list)} empreendimentos na lista para serem atualizados")
        return buildings_list
    
    def get_building(self, building_id):
        """
        Retorna as informações do empreendimento e das tipologias
        """
        headers = {"Authorization": "Bearer {}".format(self.token)}
        params = {'include[]':'not_available'}
        retries = 0
        max_retries = 3
        request_building = None
        while retries < max_retries:
            try:
                request_building = requests.get(url="https://www.orulo.com.br/api/v2/buildings/" + str(building_id), headers=headers, params=params)
                break
            except:
                logger.warning("Erro ao acessar a API do Órulo. Verifique sua conexão com a internet ou o status da API.")
                logger.warning(f"Tentando novamente obter dados para o empreendimento {building_id}")
                sleep(10) # Espera 10 segundos antes de tentar novamente
                retries += 1

        if retries == max_retries:
            logger.error(f"Falha ao obter dados para o empreendimento {building_id} após {max_retries} tentativas.")
            self.error_buildings_ids.append(building_id)
            return {}

        if request_building is None:
            logger.error(f"Falha ao obter dados para o empreendimento {building_id}.")
            self.error_buildings_ids.append(building_id)
            return {}

        if request_building.status_code != 200: # Caso a requisição retorne erro
            logger.warning(f"Empreendimento {building_id} não encontrado. Erro {request_building.status_code}: {request_building.text}")
            self.error_buildings_ids.append(building_id)
            return {}
        
        building_data = json.loads(request_building.text)
        return building_data
    
    def get_units(self, building_id, typology_id):
        headers = {"Authorization": "Bearer {}".format(self.token)}
        params = {'include[]':'not_available'}
        
        max_retries = 5
        for attempt in range(max_retries):
            try:
                request_units = requests.get(url="https://www.orulo.com.br/api/v2/buildings/" + str(building_id) + "/typologies/" + str(typology_id) + "/units", headers=headers, params=params)
                if request_units.status_code != 200:
                    raise Exception(f"Erro {request_units.status_code}: {request_units.text}")
                data = json.loads(request_units.text)
                return data
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"Erro ao obter unidades do empreendimento {building_id}, tipologia {typology_id}: {e}")
                    logger.warning(f"Tentativa {attempt + 1}/{max_retries}. Aguardando {wait_time}s antes de tentar novamente...")
                    sleep(wait_time)
                else:
                    logger.error(f"Falha ao obter unidades do empreendimento {building_id}, tipologia {typology_id} após {max_retries} tentativas.")
                    self.error_buildings_ids.append(building_id)
                    return {}
    
    def filter_by_region(self, list_data):
        return [item for item in list_data if item.get('region') == self.code]
    
    def get_images(self, building_id):
        headers = {"Authorization": "Bearer {}".format(self.token)}
        params = {'include[]':'not_available', 'dimensions[]':['200x140','520x280', '1024x1024', '2280x1800']}
        data = {}
        
        max_retries = 5
        for attempt in range(max_retries):
            try:
                request_images = requests.get(url="https://www.orulo.com.br/api/v2/buildings/" + str(building_id) + "/images", headers=headers, params=params)
                data = json.loads(request_images.text)
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff: 1, 2, 4, 8, 16 seconds
                    logger.warning(f"Erro ao obter imagens do empreendimento {building_id}: {e}")
                    logger.warning(f"Tentativa {attempt + 1}/{max_retries}. Aguardando {wait_time}s antes de tentar novamente...")
                    sleep(wait_time)
                else:
                    logger.error(f"Falha ao obter imagens do empreendimento {building_id} após {max_retries} tentativas.")
                    return []
        
        try:
            images = data['images']
            return images
        except:
            logger.info(f'Sem imagens para o empreendimento {building_id}')
            return []
        
    def get_floor_plans(self, building_id):
        headers = {"Authorization": "Bearer {}".format(self.token)}
        params = {'include[]':'not_available', 'dimensions[]':['200x140','520x280', '1024x1024', '2280x1800']}
        data = {}
        
        max_retries = 5
        for attempt in range(max_retries):
            try:
                request_floor_plans = requests.get(url="https://www.orulo.com.br/api/v2/buildings/" + str(building_id) + "/floor_plans", headers=headers, params=params)
                data = json.loads(request_floor_plans.text)
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"Erro ao obter plantas do empreendimento {building_id}: {e}")
                    logger.warning(f"Tentativa {attempt + 1}/{max_retries}. Aguardando {wait_time}s antes de tentar novamente...")
                    sleep(wait_time)
                else:
                    logger.error(f"Falha ao obter plantas do empreendimento {building_id} após {max_retries} tentativas.")
                    return []
        
        try:
            images = data['floor_plans']
            return images
        except:
            logger.info(f'Sem plantas para o empreendimento {building_id}')
            return []

def format_date(date_string) -> str | None:
    """Formata datas para o formato aceito pela Supabase"""
    if not date_string:  # Check if the date string is empty or None
        return None

    if isinstance(date_string, datetime):
        return date_string.strftime("%Y-%m-%d")

    if isinstance(date_string, str):
        # Attempt parsing with different formats (add more if needed)
        for fmt in ("%d/%m/%Y", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S"): # Add more formats as needed
            try:

                dt = datetime.strptime(date_string, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                pass  # Try the next format

        logger.warning(f"Atenção: Não foi possível formatar a data: {date_string}") # Print a warning if no format matches
        return None # Return the original string if parsing fails
    else: 
        logger.warning(f"Atenção: Formato inválido para a data: {date_string}")
    
    return None

def parse_date(date_string) -> datetime | None:
    """Formata datas para o formato aceito pela Supabase"""
    if not date_string:  # Check if the date string is empty or None
        return None

    try:
        # Attempt parsing with different formats (add more if needed)
        for fmt in ("%d/%m/%Y", "%d/%m/%Y %H:%M:%S"): # Add more formats as needed
            try:
                dt = datetime.strptime(date_string, fmt)
                return dt
            except ValueError:
                pass  # Try the next format

        logger.warning(f"Atenção:Não foi possível formatar a data: {date_string}") # Print a warning if no format matches
        return date_string # Return the original string if parsing fails
    except TypeError: # Handle cases where date_string might not be a string
        logger.warning(f"Atenção:Formato inválido para a data: {date_string}")
        return None # or date_string if you prefer to keep the original value

def clean_building_data(data):
    buildin_id = data.get("id")
    if not buildin_id:
        logger.error("Erro: ID do empreendimento não encontrado.")
        return {}
    building_data = {
        "building_id": int(data["id"]),
        "name": data["name"],
        "created_at": format_date(data.get("created_at")),
        "opening_date": format_date(data.get("opening_date")),
        "launch_date": format_date(data.get("launch_date")),
        "type": data.get("type"),
        "finality": data.get("finality"),
        "status": data.get("status"),
        "stage": data.get("stage"),
        "developer_id": int(data.get("developer", {}).get("id")),
        "developer_name": data.get("developer", {}).get("name"),
        "address_street_type": data.get("address", {}).get("street_type"),
        "address_street": data.get("address", {}).get("street"),
        "address_number": data.get("address", {}).get("number"),
        "address_area": data.get("address", {}).get("area"),
        "address_city": data.get("address", {}).get("city"),
        "address_state": data.get("address", {}).get("state"),
        "address_latitude": data.get("address", {}).get("latitude"),
        "address_longitude": data.get("address", {}).get("longitude"),
        "opportunity_social_housing_program": data.get("opportunity", {}).get("social_housing_program"),
        "default_image_url": data.get("default_image", {}).get("2280x1800"),
        "features": data.get("features"),
        "number_of_towers": data.get("number_of_towers"),
        "number_of_floors": data.get("number_of_floors"),
        "units_per_floor": data.get("apts_per_floor"),
        "lock_edit": False, # In case the building doesn't exist
        "is_active": True
    }
    return building_data

def clean_typologies_data(data):
    number_of_typologies = len(data["typologies"])
    typologies = []
    for typologie in range(0, number_of_typologies):
        typologie_data = data["typologies"][typologie]
        typologies.append({
            "building_id": int(data["id"]),
            "typology_id": int(typologie_data["id"]),
            "type": typologie_data.get("type"),
            "private_area": typologie_data.get("private_area"),
            "total_area": typologie_data.get("total_area"),
            "bedrooms": typologie_data.get("bedrooms"),
            "bathrooms": typologie_data.get("bathrooms"),
            "suites": typologie_data.get("suites"),
            "parking": typologie_data.get("parking"),
            "total_units": typologie_data.get("total_units"),
            "lock_edit": False
        })
        
    return typologies

def clean_images_data(building_id, images_data, images_urls, type="images"):
    images = []
    for image in images_data:
        
        image_id = image.get("id")
        image_url = None
        
        for img in images_urls:
            if img.get("image_id") == image_id:
                image_url = img.get("image_url")
                break
            else:
                image_url = None

        images.append({
            "building_id": building_id,
            "image_id": image_id,
            "type": image.get("type"),
            "description": image.get("description"),
            "associations_typologies": image.get("associations", {}).get("typologies"),
            "associations_building_units": image.get("associations", {}).get("building_units"),
            "image_type": type,
            "image_url": image_url
        })

    return images

def get_highest_resolution_image_url(image_data_list):
    """
    Extracts the ID and the highest available resolution image URL for each item
    in a list of image dictionaries.

    Args:
        image_data_list: A list of dictionaries, where each dictionary contains
                         an 'id' and keys representing resolutions ('2280x1800',
                         '1024x1024', '520x280', '200x140') mapping to image URLs.

    Returns:
        A dictionary where keys are the image IDs (strings) and values are the
        corresponding highest resolution URLs found. If an item in the input list
        lacks an 'id' key, it will be skipped. If an item has an 'id' but no
        known resolution keys, its value in the dictionary will be None.
        If duplicate IDs exist, the entry corresponding to the *last* occurrence
        in the input list will be stored.
    """
    highest_res_images = []
    # Define resolution keys in order of preference (highest to lowest)
    resolution_keys_ordered = ['2280x1800', '1024x1024', '520x280', '200x140']

    for image_dict in image_data_list:
        image_id = image_dict.get('id')  # Use .get() for safety if 'id' might be missing
        highest_res_url = None

        # Iterate through the preferred resolution keys
        for res_key in resolution_keys_ordered:
            if res_key in image_dict:
                highest_res_url = image_dict[res_key]
                break  # Found the highest available resolution, stop checking

        highest_res_images.append({
            'image_id': image_id,
            'image_url': highest_res_url
        })

    return highest_res_images

def clean_units_data(units_data, building_id, typology_id):
    try:
        number_of_units = len(units_data["units"])
    except:
        logger.error(f"Erro ao ler unidades para tipologia {typology_id}: {units_data}")
        return ([], []) # Retorna tuple com listas vazias
    
    # Cria um dict de referência para testar testar unidades duplicadas
    reference_dict = {}

    for unit in range(0, number_of_units):
        unit_data = units_data["units"][unit]
        unit_id = str(building_id) + str(typology_id) + unit_data.get("reference").strip().upper()
        unit_data["unit_id"] = unit_id
        # unit_number = unit_data.get("flor") + unit_data.get("unit_end").rjust()
        updated_at = unit_data.get("updated_at")

        # Mede a qualidade da informação da unidade
        nulls_count = sum(1 for field in ["section", "floor", "unit_end"] 
                            if unit_data.get(field) is None)

        if unit_id in reference_dict:
            existing_entry = reference_dict[unit_id]
            existing_nulls = existing_entry["nulls_count"]
            existing_date = parse_date(existing_entry["unit_data"].get("updated_at"))
            new_date = parse_date(updated_at)

            # Substituir se a nova unidade tem mais informações que a já salva
            if nulls_count < existing_nulls:
                reference_dict[unit_id] = {
                    "unit_data": unit_data,
                    "nulls_count": nulls_count
                }

            # Se forem igualemnte completas, usar a mais recente
            elif (
                nulls_count == existing_nulls
                and new_date is not None
                and (existing_date is None or new_date > existing_date)
            ):
                reference_dict[unit_id] = {
                    "unit_data": unit_data,
                    "nulls_count": nulls_count
                }

        else:
            reference_dict[unit_id] = {
                "unit_data": unit_data,
                "nulls_count": nulls_count
            }
        
    units = []
    updates = []

    for unit_id, entry in reference_dict.items():
        unit_data = entry["unit_data"]

        units.append({
            "building_id": building_id,
            "typology_id": typology_id,
            "unit_id": unit_id,
            "reference": unit_data.get("reference").strip().upper(),
            "section": unit_data.get("section"),
            "floor": unit_data.get("floor"),
            "unit_end": unit_data.get("unit_end"),
            #"price": unit_data.get("price"),
            "private_area": unit_data.get("private_area"),
            #"available": unit_data.get("available"),
            #"updated_at": format_date(unit_data.get("updated_at"))
            "lock_edit": False
        })
        updates.append({
            #"building_id": building_id,
            #"typology_id": typology_id,
            "unit_id": unit_id,
            #"reference": unit_data.get("reference").upper(),
            #"section": unit_data.get("section"),
            #"floor": unit_data.get("floor"),
            #"unit_end": unit_data.get("unit_end"),
            "price": unit_data.get("price"),
            #"private_area": unit_data.get("private_area")
            "available": unit_data.get("available"),
            "updated_at": format_date(unit_data.get("updated_at")),
            "lock_edit": False
        })

    return units, updates

def list_buildings_and_typologies(data, region_code):
    building_id = data.get("id") 
    typologies = data.get("typologies", [])

    result = []
    for typology in typologies:
        result.append({"building_id": building_id, "typology_id": typology.get("id"), "region": region_code})
    return result

if __name__ == "__main__":
    client_id = os.getenv("FLN_RM_CLIENT_ID")
    client_secret = os.getenv("FLN_RM_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise SystemExit("Defina FLN_RM_CLIENT_ID e FLN_RM_CLIENT_SECRET no .env")
    region = OruloRegion(
        "FLN-RM",
        "Florianópolis e Região Metropolitana",
        client_id,
        client_secret,
    )

    data = region.get_building(1127)
    images_data = region.get_images(1127)
    images_urls = get_highest_resolution_image_url(images_data)
    logger.info(clean_images_data(1127, images_data, images_urls))
    logger.info(list_buildings_and_typologies(data, region.code))