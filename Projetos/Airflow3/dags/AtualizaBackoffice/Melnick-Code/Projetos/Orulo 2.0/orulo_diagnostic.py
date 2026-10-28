from orulo_db import fetch_by_filter_values


def run_diagnostic(regions, conn, test_building_id, test_typology_id, logger):
    if not regions:
        return

    units_payload = regions[0].get_units(test_building_id, test_typology_id)
    units = units_payload['units'] if units_payload else []
    logger.info(f"Total de unidades no teste: {len(units)}")

    for unit in units:
        reference = unit.get("reference")
        if reference and "C" in reference:
            unit["reference"] = reference.split("C")[0]

    units_ids = []
    new_units_ids = []
    for unit in units:
        reference = unit.get("reference")
        section = unit.get("section")
        if not reference:
            continue

        unit_name = reference + section if section else reference
        new_unit_id = str(test_building_id) + str(test_typology_id) + reference
        new_units_ids.append(new_unit_id)
        units_ids.append(str(test_building_id) + str(test_typology_id) + unit_name)

    logger.info(units_ids)
    logger.info(new_units_ids)

    if units_ids:
        pg_updates = fetch_by_filter_values(conn, "units_updates", "unit_id", units_ids)
    else:
        pg_updates = []

    logger.info(f"Total de atualizações encontradas no teste: {len(pg_updates)}")
