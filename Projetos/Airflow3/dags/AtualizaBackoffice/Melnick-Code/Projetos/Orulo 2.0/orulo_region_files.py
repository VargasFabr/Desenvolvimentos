import os


def persist_region_files(regions, current_update_time, base_project_path, logger):
    for region in regions:
        region_dir = os.path.join(base_project_path, "Regiões", region.code)
        os.makedirs(region_dir, exist_ok=True)

        last_update_file_path = os.path.join(base_project_path, "Regiões", region.code, "Última Atualização.txt")
        with open(last_update_file_path, 'w') as last_update_saved:
            last_update_saved.write(current_update_time)
            logger.info(f"Nova data de atualização para {region.name} salva: {current_update_time}")

    for region in regions:
        region_dir = os.path.join(base_project_path, "Regiões", region.code)
        os.makedirs(region_dir, exist_ok=True)

        error_buildings_file_path = os.path.join(base_project_path, "Regiões", region.code, "Empreendimentos com Erro.txt")

        if region.error_buildings_ids:
            with open(error_buildings_file_path, 'w') as error_file:
                error_file.write(f"Data da atualização: {current_update_time}\n")
                error_file.write("IDs dos empreendimentos com erro:\n")
                for building_id in region.error_buildings_ids:
                    error_file.write(f"{building_id}\n")
            logger.warning(f"Empreendimentos com erro na região {region.name}: {region.error_buildings_ids}")
            logger.info(f"Lista de IDs salva em: {error_buildings_file_path}")
        else:
            with open(error_buildings_file_path, 'w') as error_file:
                error_file.write(f"Data da atualização: {current_update_time}\n")
                error_file.write("Nenhum empreendimento com erro.\n")
            logger.info(f"Todos os empreendimentos atualizados na região {region.name} com sucesso.")


def get_error_buildings_from_file(region_code, base_project_path, logger):
    error_buildings = []
    error_buildings_file_path = os.path.join(base_project_path, "Regiões", region_code, "Empreendimentos com Erro.txt")

    try:
        with open(error_buildings_file_path, 'r') as error_file:
            lines = error_file.readlines()
            for line in lines[2:]:
                try:
                    building_id = int(line.strip())
                    error_buildings.append(building_id)
                except ValueError:
                    continue
    except FileNotFoundError:
        logger.info(f"Nenhum arquivo de erro encontrado para a região {region_code}")

    return error_buildings


def print_previous_errors(regions, base_project_path, logger):
    for region in regions:
        error_buildings = get_error_buildings_from_file(region.code, base_project_path, logger)
        if error_buildings:
            logger.info(f"Encontrados {len(error_buildings)} empreendimentos com erro na execução anterior de {region.name}.")
            logger.info(error_buildings)
