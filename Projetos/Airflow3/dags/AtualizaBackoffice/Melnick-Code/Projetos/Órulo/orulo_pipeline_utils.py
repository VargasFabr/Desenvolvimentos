from datetime import datetime
import time
import sys
from tqdm.auto import tqdm  # type: ignore[import-not-found]
from Módulos.orulo import format_date

TQDM_DISABLE = not sys.stderr.isatty()


def _log_debug(logger, message):
    if logger:
        logger.debug(message)


def _log_error(logger, message):
    if logger:
        logger.error(message)


def paginate_supabase_query(supabase_query, order_by_column, row_limit=1000, sleep_seconds=0, logger=None):
    supabase_data = []
    range_start = 0
    range_end = row_limit - 1

    while True:
        _log_debug(logger, f"Buscando de {range_start} a {range_end}")

        supabase_response = (
            supabase_query
            .order(order_by_column)
            .range(range_start, range_end)
            .execute()
        ).data

        rows_returned = len(supabase_response)
        _log_debug(logger, f"{rows_returned} linhas retornadas")

        supabase_data.extend(supabase_response)

        if range_start + rows_returned < range_end + 1:
            break

        range_start = range_start + rows_returned
        range_end = range_end + rows_returned

        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    return supabase_data


def paginate_supabase_query_with_filter_by_list_of_values(
    supabase_query,
    order_by_column,
    filter_column,
    filter_value: list,
    row_limit=1000,
    sleep_seconds=0,
):
    supabase_data = []
    range_start = 0
    range_end = row_limit - 1

    while True:
        supabase_response = (
            supabase_query
            .select("*")
            .in_(filter_column, filter_value)
            .order(order_by_column)
            .range(range_start, range_end)
            .execute()
        ).data

        rows_returned = len(supabase_response)
        supabase_data.extend(supabase_response)

        if range_start + rows_returned < range_end + 1:
            break

        range_start = range_start + rows_returned
        range_end = range_end + rows_returned

        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    return supabase_data


def paginate_supabase_query_with_filter_by_list_of_values_batched(
    supabase_query,
    order_by_column,
    filter_column,
    filter_value: list,
    row_limit=1000,
    batch_size=100,
    sleep_seconds=0,
    logger=None,
):
    all_data = []

    for i in tqdm(range(0, len(filter_value), batch_size), desc="Processing batches", disable=TQDM_DISABLE):
        batch = filter_value[i:i + batch_size]

        try:
            batch_data = paginate_supabase_query_with_filter_by_list_of_values(
                supabase_query,
                order_by_column,
                filter_column,
                batch,
                row_limit,
                sleep_seconds=sleep_seconds,
            )
            all_data.extend(batch_data)
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)
        except Exception as e:
            _log_error(logger, f"Erro no lote {i // batch_size + 1}: {e}")
            continue

    return all_data


def build_index(list_of_dicts, key_fields):
    if isinstance(key_fields, str):
        key_fields = [key_fields]

    indexed_data = {}
    for row in list_of_dicts:
        if not all(field in row for field in key_fields):
            continue
        index_key = tuple(row[field] for field in key_fields)
        indexed_data[index_key] = row

    return indexed_data


def merge_dicts_best_value(dict1, dict2):
    if not dict1:
        return dict2.copy()
    if not dict2:
        return dict1.copy()

    merged_dict = {}
    all_keys = set(dict1.keys()) | set(dict2.keys())

    for key in all_keys:
        value1 = dict1.get(key)
        value2 = dict2.get(key)

        if type(value1) == datetime:
            value1 = format_date(value1)
        if type(value2) == datetime:
            value2 = format_date(value2)

        if value1 is None and value2 is not None:
            merged_dict[key] = value2
        elif value1 is not None and value2 is None:
            merged_dict[key] = value1
        elif value1 == value2:
            merged_dict[key] = value1
        elif isinstance(value1, list) and isinstance(value2, list):
            merged_dict[key] = list(set(value1 + value2))
        elif isinstance(value1, str) and isinstance(value2, str):
            merged_dict[key] = value1 if len(value1) >= len(value2) else value2
        else:
            if value1 is not None:
                merged_dict[key] = value1
            elif value2 is not None:
                merged_dict[key] = value2
            else:
                merged_dict[key] = None

    return merged_dict


def add_to_dict_where_none(dict1, dict2):
    merged_dict = {}
    all_keys = set(dict1.keys()) | set(dict2.keys())

    for key in all_keys:
        value1 = dict1.get(key)
        value2 = dict2.get(key)

        if value1 is None:
            merged_dict[key] = value2
        else:
            merged_dict[key] = value1

    return merged_dict


def get_values_by_key(list_of_dicts, key):
    values_list = []
    for dictionary in list_of_dicts:
        if key in dictionary:
            values_list.append(dictionary[key])
    return values_list


def remove_duplicates_by_keys(dict_list, keys):
    if isinstance(keys, str):
        keys = [keys]

    seen_values = set()
    result = []

    for d in dict_list:
        if not all(key in d for key in keys):
            continue

        values_tuple = tuple(d[key] for key in keys)

        if values_tuple not in seen_values:
            seen_values.add(values_tuple)
            result.append(d)

    return result


def clean_null_values_in_dicts(list_of_dicts):
    cleaned_dicts = []
    for dictionary in list_of_dicts:
        cleaned_dict = {k: (None if (v == "NaN" or str(v) == "nan") else v) for k, v in dictionary.items()}
        cleaned_dicts.append(cleaned_dict)
    return cleaned_dicts
