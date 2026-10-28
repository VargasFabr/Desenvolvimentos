
from tqdm.auto import tqdm  # type: ignore[import-not-found]
from datetime import date, datetime
import json
import math
import time
import os
import logging
from typing import Any, TypedDict

repository_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
#print(f"Caminho da pasta raiz do projeto: {repository_root}")
project_root = os.path.abspath(os.path.join(repository_root, '..'))
#print(f"Caminho da pasta raiz do repositório: {project_root}")
this_script_project_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
orulo_project_path = os.path.abspath(os.path.dirname(__file__))

import sys
sys.path.append(repository_root)  # Adiciona a pasta raiz do projeto ao sys.path
TQDM_DISABLE = not sys.stderr.isatty()

from Módulos.cliente_orulo import (
    OruloRegion,
    clean_building_data,
    clean_images_data,
    clean_typologies_data,
    clean_units_data,
    get_highest_resolution_image_url,
)
from Módulos.logs_melnick import setup_logger
from orulo_backup import backup_data
from orulo_diagnostic import run_diagnostic
from orulo_pipeline_utils import (
    add_to_dict_where_none,
    build_index,
    clean_null_values_in_dicts,
    get_values_by_key,
    merge_dicts_best_value,
    paginate_supabase_query_with_filter_by_list_of_values,
    paginate_supabase_query_with_filter_by_list_of_values_batched,
    remove_duplicates_by_keys,
)
from orulo_region_files import persist_region_files, print_previous_errors
#import requests

logger = setup_logger(
    "OruloUpdate",
    logs_path=os.path.join(orulo_project_path, "Logs"),
    level=logging.INFO,
)
logger.info(f"Caminho do projeto deste script: {this_script_project_path}")

# Reduz logs verbosos de requests HTTP de bibliotecas externas
for external_logger_name in ("httpx", "httpcore"):
    external_logger = logging.getLogger(external_logger_name)
    external_logger.setLevel(logging.WARNING)
    external_logger.propagate = False



# Confirma se o .env existe na pasta raiz
env_path = os.path.join(project_root, '.env')

from dotenv import load_dotenv
load_dotenv(env_path)

external_env_path = os.getenv("ORULO_SUPABASE_ENV_PATH")
if external_env_path and os.path.exists(external_env_path):
    load_dotenv(external_env_path)


def get_first_env_value(*keys: str) -> str | None:
    """Retorna o primeiro valor de variável de ambiente disponível na lista de chaves."""
    for key in keys:
        value = os.getenv(key)
        if value:
            return value
    return None

# Criando o cliente Supabase
from supabase import create_client, Client  # type: ignore[import-not-found]
supabase_url = get_first_env_value("NEXT_PUBLIC_SUPABASE_URL", "SUPABASE_URL")
supabase_key = get_first_env_value("NEXT_PUBLIC_SUPABASE_ANON_KEY", "SUPABASE_KEY", "SUPABASE_ANON_KEY")
if not supabase_url or not supabase_key:
    raise ValueError(
        "Defina credenciais Supabase no ambiente: NEXT_PUBLIC_SUPABASE_URL/SUPABASE_URL e "
        "NEXT_PUBLIC_SUPABASE_ANON_KEY/SUPABASE_KEY."
    )

supabase: Client = create_client(supabase_url, supabase_key)



RUN_BACKUP = os.getenv("ORULO_RUN_BACKUP", "1") == "1"
RUN_DIAGNOSTIC = os.getenv("ORULO_RUN_DIAGNOSTIC", "0") == "1"
TEST_BUILDING_ID = int(os.getenv("ORULO_TEST_BUILDING_ID", "54008"))
TEST_TYPOLOGY_ID = int(os.getenv("ORULO_TEST_TYPOLOGY_ID", "82593"))
ORULO_BUILDING_REQUEST_DELAY = float("0.15")
ORULO_TYPOLOGY_REQUEST_DELAY = float("0.05")
ORULO_SUPABASE_IN_BATCH_SIZE = 100
ORULO_UPSERT_BATCH_SIZE = 300
ORULO_UPSERT_MAX_RETRIES = 5
ORULO_UPSERT_RETRY_BASE_DELAY = 3.0
ORULO_SUPABASE_READ_MAX_RETRIES = 4
ORULO_SUPABASE_READ_RETRY_BASE_DELAY = 2.0


class CleanData(TypedDict):
    current_update_time: str
    clean_buildings: list[dict[str, Any]]
    clean_typologies: list[dict[str, Any]]
    clean_images: list[dict[str, Any]]
    clean_units: list[dict[str, Any]]
    clean_units_updates: list[dict[str, Any]]
    supabase_buildings: list[dict[str, Any]]
    supabase_typologies: list[dict[str, Any]]
    supabase_units: list[dict[str, Any]]
    supabase_units_updates: list[dict[str, Any]]


def _sanitize_for_json(value: Any) -> Any:
    """Normaliza valores para tipos serializáveis em JSON."""
    if value is None:
        return None

    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, dict):
        return {key: _sanitize_for_json(item) for key, item in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [_sanitize_for_json(item) for item in value]

    if isinstance(value, str):
        lower_value = value.strip().lower()
        if lower_value in {"nan", "inf", "-inf", "infinity", "-infinity"}:
            return None
        return value

    if isinstance(value, (str, int, bool)):
        return value

    return str(value)


def _sanitize_records_for_json(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_sanitize_for_json(record) for record in records]


def _retry_operation(operation_name: str, max_retries: int, base_delay: float, operation: Any) -> Any:
    for attempt in range(1, max_retries + 1):
        try:
            return operation()
        except Exception as error:
            is_last_attempt = attempt == max_retries

            if is_last_attempt:
                logger.error(
                    f"Falha em '{operation_name}' após {max_retries} tentativas: {error}"
                )
                raise

            sleep_seconds = base_delay * attempt
            logger.warning(
                f"Erro em '{operation_name}' (tentativa {attempt}/{max_retries}): {error}. "
                f"Nova tentativa em {sleep_seconds:.1f}s."
            )
            time.sleep(sleep_seconds)


def _execute_upsert(table_name: str, records: list[dict[str, Any]], **kwargs: Any) -> None:
    if not records:
        return

    sanitized_records = _sanitize_records_for_json(records)

    def _do_upsert() -> None:
        supabase.table(table_name).upsert(sanitized_records, **kwargs).execute()

    try:
        _retry_operation(
            f"upsert:{table_name}",
            ORULO_UPSERT_MAX_RETRIES,
            ORULO_UPSERT_RETRY_BASE_DELAY,
            _do_upsert,
        )
    except Exception as error:
        sample_row = sanitized_records[0] if sanitized_records else {}
        logger.error(
            f"Falha no upsert da tabela '{table_name}' com {len(sanitized_records)} registros: {error}. "
            f"Amostra do payload: {json.dumps(sample_row, ensure_ascii=False, default=str)}"
        )
        raise


def _execute_upsert_batched(
    table_name: str,
    records: list[dict[str, Any]],
    *,
    batch_size: int,
    **kwargs: Any,
) -> None:
    if not records:
        return

    safe_batch_size = max(1, batch_size)

    for range_start in range(0, len(records), safe_batch_size):
        records_batch = records[range_start:range_start + safe_batch_size]
        _execute_upsert(table_name, records_batch, **kwargs)


def _fetch_supabase_batched_with_retry(
    table_name: str,
    id_column_name: str,
    filter_column_name: str,
    filter_values: list[Any],
) -> list[dict[str, Any]]:
    if not filter_values:
        return []

    def _do_fetch() -> list[dict[str, Any]]:
        return paginate_supabase_query_with_filter_by_list_of_values_batched(
            supabase.table(table_name),
            id_column_name,
            filter_column_name,
            filter_values,
            batch_size=ORULO_SUPABASE_IN_BATCH_SIZE,
            logger=logger,
        )

    result = _retry_operation(
        f"read:{table_name}",
        ORULO_SUPABASE_READ_MAX_RETRIES,
        ORULO_SUPABASE_READ_RETRY_BASE_DELAY,
        _do_fetch,
    )
    return result if result is not None else []


def create_regions() -> list[OruloRegion]:
    """Cria e retorna a lista de regiões configuradas para atualização."""
    regions = [
        OruloRegion(
            "POA-RM",
            "Porto Alegre e Região Metropolitana",
            os.getenv("POA_RM_CLIENT_ID"),
            os.getenv("POA_RM_CLIENT_SECRET"),
            data_path=orulo_project_path,
        ),
        # OruloRegion("FLN-RM", "Florianópolis e Região Metropolitana", os.getenv("FLN_RM_CLIENT_ID"), os.getenv("FLN_RM_CLIENT_SECRET"), data_path=this_script_project_path),
        OruloRegion(
            "FLN-RM_CWB-RM_ITAJAI",
            "Florianópolis e Região Metropolitana/Curitiba e Região Metropolitana/Vale do Itajai",
            os.getenv("FLN_RM_CWB_RM_ITAJAI_CLIENT_ID"),
            os.getenv("FLN_RM_CWB_RM_ITAJAI_CLIENT_SECRET"),
            data_path=orulo_project_path,
        ),
    ]

    for region in regions:
        os.makedirs(os.path.join(orulo_project_path, "Regiões", region.code), exist_ok=True)

    return regions

def process_regions(regions: list[OruloRegion]) -> CleanData:
    """Processa regiões, aplica regras de merge e retorna payload limpo para upsert."""
    current_update_time = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    buildings_to_update = []
    typologies_to_update = []
    images_to_update = []
    units_data = []
    units_updates_data = []

    supabase_buildings_snapshot = []
    supabase_typologies_snapshot = []
    supabase_units_snapshot = []
    supabase_units_updates_snapshot = []

    for region in regions:
        list_of_buildings_to_update = region.get_list_of_buildings_to_update()

        logger.info(f"Região: {region.name} - {len(list_of_buildings_to_update)} empreendimentos para atualizar.")
        logger.debug(f"IDs para atualizar: {list_of_buildings_to_update}")

        logger.info("Buscando os dados na Supabase...")
        supabase_buildings = _fetch_supabase_batched_with_retry(
            "buildings",
            "building_id",
            "building_id",
            list_of_buildings_to_update,
        )
        logger.info(f"{len(supabase_buildings)} empreendimentos encontrados na Supabase.")

        supabase_typologies = _fetch_supabase_batched_with_retry(
            "typologies",
            "typology_id",
            "building_id",
            list_of_buildings_to_update,
        )
        logger.info(f"{len(supabase_typologies)} tipologias encontradas na Supabase.")

        supabase_units = _fetch_supabase_batched_with_retry(
            "units",
            "unit_id",
            "building_id",
            list_of_buildings_to_update,
        )
        logger.info(f"{len(supabase_units)} unidades encontradas na Supabase.")

        supabase_units_ids = list(set(get_values_by_key(supabase_units, "unit_id")))
        if supabase_units_ids:
            supabase_units_updates = _fetch_supabase_batched_with_retry(
                "units_updates",
                "unit_id",
                "unit_id",
                supabase_units_ids,
            )
        else:
            supabase_units_updates = []

        logger.info(f"{len(supabase_units_updates)} atualizações de unidades encontradas na Supabase.")
        logger.info("Dados recuperados.")

        supabase_buildings_snapshot.extend(supabase_buildings)
        supabase_typologies_snapshot.extend(supabase_typologies)
        supabase_units_snapshot.extend(supabase_units)
        supabase_units_updates_snapshot.extend(supabase_units_updates)

        supabase_buildings_index = build_index(supabase_buildings, "building_id")
        supabase_typologies_index = build_index(supabase_typologies, ["building_id", "typology_id"])
        supabase_units_index = build_index(supabase_units, "unit_id")
        supabase_units_updates_index = build_index(supabase_units_updates, ["unit_id", "updated_at"])

        for building in tqdm(list_of_buildings_to_update, desc="Processando empreendimentos", disable=TQDM_DISABLE):
            try:
                data = region.get_building(building)
                new_building_data = clean_building_data(data)

                if ORULO_BUILDING_REQUEST_DELAY > 0:
                    time.sleep(ORULO_BUILDING_REQUEST_DELAY)

                if new_building_data == {}:
                    logger.warning(f"Erro ajustando os dados do empreendimento {building}")
                    if data != {}:
                        region.error_buildings_ids.append(building)
                    continue

                supabase_building_data = supabase_buildings_index.get((new_building_data["building_id"],))

                if not supabase_building_data or not supabase_building_data.get("lock_edit"):
                    buildings_to_update.append(merge_dicts_best_value(new_building_data, supabase_building_data))
                else:
                    buildings_to_update.append(add_to_dict_where_none(supabase_building_data, new_building_data))

                images_urls = get_highest_resolution_image_url(region.get_images(building))
                updated_images = clean_images_data(building, data["images"], images_urls, type="images")
                images_to_update.extend(updated_images)

                floor_plans_urls = get_highest_resolution_image_url(region.get_floor_plans(building))
                updated_floor_plans = clean_images_data(building, data["floor_plans"], floor_plans_urls, type="floor_plans")
                images_to_update.extend(updated_floor_plans)

                typologies = clean_typologies_data(data)

                for typology in tqdm(typologies, desc="Processando unidades", leave=False, disable=TQDM_DISABLE):
                    try:
                        supabase_typology_data = supabase_typologies_index.get((new_building_data["building_id"], typology["typology_id"]))

                        if not supabase_typology_data or not supabase_typology_data.get("lock_edit"):
                            typologies_to_update.append(merge_dicts_best_value(typology, supabase_typology_data))
                        else:
                            typologies_to_update.append(add_to_dict_where_none(supabase_typology_data, typology))

                        this_typology_units_data, this_typology_units_updates = clean_units_data(
                            region.get_units(typology["building_id"], typology["typology_id"]),
                            typology["building_id"],
                            typology["typology_id"],
                        )

                        if ORULO_TYPOLOGY_REQUEST_DELAY > 0:
                            time.sleep(ORULO_TYPOLOGY_REQUEST_DELAY)

                        for unit_data, unit_update_data in zip(this_typology_units_data, this_typology_units_updates):
                            supabase_unit_data = supabase_units_index.get((unit_data["unit_id"],))
                            supabase_unit_update_data = supabase_units_updates_index.get((unit_update_data["unit_id"], unit_update_data["updated_at"]))

                            if not supabase_unit_data or not supabase_unit_data.get("lock_edit"):
                                units_data.append(merge_dicts_best_value(unit_data, supabase_unit_data))
                            else:
                                units_data.append(add_to_dict_where_none(supabase_unit_data, unit_data))

                            if not supabase_unit_update_data or not supabase_unit_update_data.get("lock_edit"):
                                units_updates_data.append(merge_dicts_best_value(unit_update_data, supabase_unit_update_data))
                            else:
                                units_updates_data.append(add_to_dict_where_none(supabase_unit_update_data, unit_update_data))
                    except Exception as typology_error:
                        logger.error(
                            f"Erro processando tipologia {typology.get('typology_id')} do empreendimento {building}: {typology_error}"
                        )
                        continue
            except Exception as building_error:
                logger.error(f"Erro processando empreendimento {building}: {building_error}")
                region.error_buildings_ids.append(building)
                continue

    clean_buildings = remove_duplicates_by_keys(buildings_to_update, "building_id")
    clean_typologies = remove_duplicates_by_keys(typologies_to_update, ["building_id", "typology_id"])
    clean_images = remove_duplicates_by_keys(images_to_update, "image_id")
    clean_units = remove_duplicates_by_keys(units_data, "unit_id")
    clean_units_updates = remove_duplicates_by_keys(units_updates_data, ["unit_id", "updated_at"])

    for update in clean_units_updates:
        update["info_source"] = "orulo"

    logger.info(f"Total de unit updates limpas: {len(clean_units_updates)}")
    clean_units = clean_null_values_in_dicts(clean_units)

    return {
        "current_update_time": current_update_time,
        "clean_buildings": clean_buildings,
        "clean_typologies": clean_typologies,
        "clean_images": clean_images,
        "clean_units": clean_units,
        "clean_units_updates": clean_units_updates,
        "supabase_buildings": remove_duplicates_by_keys(supabase_buildings_snapshot, "building_id"),
        "supabase_typologies": remove_duplicates_by_keys(supabase_typologies_snapshot, ["building_id", "typology_id"]),
        "supabase_units": remove_duplicates_by_keys(supabase_units_snapshot, "unit_id"),
        "supabase_units_updates": remove_duplicates_by_keys(supabase_units_updates_snapshot, ["unit_id", "updated_at"]),
    }

def upsert_data(clean_data: CleanData) -> None:
    """Executa upserts no Supabase a partir do payload consolidado."""
    clean_buildings = clean_data["clean_buildings"]
    clean_typologies = clean_data["clean_typologies"]
    clean_images = clean_data["clean_images"]
    clean_units = clean_data["clean_units"]
    clean_units_updates = clean_data["clean_units_updates"]

    _execute_upsert_batched("buildings", clean_buildings, batch_size=ORULO_UPSERT_BATCH_SIZE)
    _execute_upsert_batched("typologies", clean_typologies, batch_size=ORULO_UPSERT_BATCH_SIZE)
    _execute_upsert_batched("images", clean_images, batch_size=ORULO_UPSERT_BATCH_SIZE)
    _execute_upsert_batched(
        "units",
        clean_units,
        batch_size=ORULO_UPSERT_BATCH_SIZE,
        on_conflict="unit_id",
        default_to_null=False,
    )
    _execute_upsert_batched(
        "units_updates",
        clean_units_updates,
        batch_size=ORULO_UPSERT_BATCH_SIZE,
        default_to_null=False,
    )


def main() -> None:
    """Orquestra a execução completa do pipeline de atualização Órulo."""
    regions = create_regions()
    logger.info(
        f"Throttle configurado: ORULO_BUILDING_REQUEST_DELAY={ORULO_BUILDING_REQUEST_DELAY}s, "
        f"ORULO_TYPOLOGY_REQUEST_DELAY={ORULO_TYPOLOGY_REQUEST_DELAY}s"
    )
    clean_data = process_regions(regions)

    upsert_data(clean_data)
    persist_region_files(regions, clean_data["current_update_time"], orulo_project_path, logger)
    print_previous_errors(regions, orulo_project_path, logger)

    if RUN_BACKUP:
        backup_data(clean_data, orulo_project_path, logger)

    if RUN_DIAGNOSTIC:
        run_diagnostic(regions, supabase, TEST_BUILDING_ID, TEST_TYPOLOGY_ID, logger)


if __name__ == "__main__":
    main()


