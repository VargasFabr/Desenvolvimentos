import os
import glob
from datetime import datetime, timedelta
import pandas as pd


def get_backup_paths(base_project_path, logger):
    backup_dir = os.path.join(base_project_path, "Arquivos", "backup")
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)

    current_time = datetime.now()
    current_month_folder = current_time.strftime("%Y_%m")
    month_dir = os.path.join(backup_dir, current_month_folder)

    if not os.path.exists(month_dir):
        os.makedirs(month_dir)
        logger.info(f"Novo diretório mensal de backup criado: {month_dir}")

    timestamp = current_time.strftime("%Y%m%d_%H%M%S")

    return backup_dir, month_dir, current_time, current_month_folder, timestamp


def get_most_recent_backup(table_name, month_dir, backup_dir, current_time):
    pattern = os.path.join(month_dir, f"{table_name}_*.parquet")
    files = glob.glob(pattern)
    if not files:
        prev_month = (current_time.replace(day=1) - timedelta(days=1)).strftime("%Y_%m")
        prev_month_dir = os.path.join(backup_dir, prev_month)
        if os.path.exists(prev_month_dir):
            pattern = os.path.join(prev_month_dir, f"{table_name}_*.parquet")
            files = glob.glob(pattern)
    return max(files, key=os.path.getctime) if files else None


def merge_with_existing_backup(new_data, table_name, month_dir, backup_dir, current_time):
    if table_name != 'images':
        return pd.DataFrame(new_data)

    most_recent = get_most_recent_backup(table_name, month_dir, backup_dir, current_time)
    if most_recent:
        existing_df = pd.read_parquet(most_recent)
        new_df = pd.DataFrame(new_data)
        combined_df = pd.concat([existing_df, new_df]).drop_duplicates(subset=['image_id'], keep='last')
        return combined_df

    return pd.DataFrame(new_data)


def backup_data(clean_data, base_project_path, logger):
    backup_dir, month_dir, current_time, current_month_folder, timestamp = get_backup_paths(base_project_path, logger)

    tables_to_backup = {
        'buildings': pd.DataFrame(clean_data["clean_buildings"]),
        'typologies': pd.DataFrame(clean_data["clean_typologies"]),
        'units': pd.DataFrame(clean_data["clean_units"]),
        'units_updates': pd.DataFrame(clean_data["clean_units_updates"]),
        'images': merge_with_existing_backup(
            clean_data["clean_images"],
            'images',
            month_dir,
            backup_dir,
            current_time,
        ),
    }

    for table_name, df in tables_to_backup.items():
        current_month_pattern = os.path.join(month_dir, f"{table_name}_*.parquet")
        existing_files = glob.glob(current_month_pattern)
        backup_file = os.path.join(month_dir, f"{table_name}_{timestamp}.parquet")

        if existing_files:
            for old_file in existing_files:
                logger.info(f"Removendo backup existente: {os.path.basename(old_file)}")
                os.remove(old_file)
            logger.info(f"Criando novo backup de {table_name} em {current_month_folder}")
        else:
            logger.info(f"Criando primeiro backup de {table_name}")

        df.to_parquet(backup_file, compression='gzip')
        logger.info(f"Backup de {table_name} salvo em {backup_file}")
        logger.info(f"Tamanho do backup: {os.path.getsize(backup_file) / (1024*1024):.2f} MB")
