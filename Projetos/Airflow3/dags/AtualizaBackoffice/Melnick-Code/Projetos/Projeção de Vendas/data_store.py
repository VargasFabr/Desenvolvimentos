import json
import os
from copy import deepcopy

from projection_calcs import (
    build_indice_data,
    series_to_year_map,
    year_map_to_series_and_annuals,
)
from projection_models import ProjectionSeries

DEFAULT_DATA = {
    "empreendimentos": {},
    "projecoes": {},
    "relacoes": {},
}

DEFAULT_CICLO = "CICLO-PRINCIPAL"


def _data_dir() -> str:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, "data")


def empreendimentos_path() -> str:
    return os.path.join(_data_dir(), "empreendimentos.json")


def projecoes_path() -> str:
    return os.path.join(_data_dir(), "projecoes.json")


def series_path() -> str:
    return os.path.join(_data_dir(), "projecoes_series.json")


def _new_year() -> dict:
    return {
        "estoque_inicial": 0,
        "vendas_anuais": 0,
        "distratos_anuais": 0,
        "usar_mensal": False,
        "mensal": {
            str(m): {
                "vendas": 0,
                "distratos": 0,
                "estoque_inicial": None,
                "estoque_final": None,
            }
            for m in range(1, 13)
        },
    }


def _to_int(value: object) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _normalize_year(year_data: dict) -> dict:
    if not isinstance(year_data, dict):
        year_data = {}
    year_data.setdefault("estoque_inicial", 0)
    year_data.setdefault("vendas_anuais", 0)
    year_data.setdefault("distratos_anuais", 0)
    year_data.setdefault("usar_mensal", False)
    mensal = year_data.setdefault("mensal", {})
    if not isinstance(mensal, dict):
        mensal = {}
        year_data["mensal"] = mensal
    for m in range(1, 13):
        key = str(m)
        if key not in mensal or not isinstance(mensal[key], dict):
            mensal[key] = {
                "vendas": 0,
                "distratos": 0,
                "estoque_inicial": None,
                "estoque_final": None,
            }
        else:
            mensal[key].setdefault("vendas", 0)
            mensal[key].setdefault("distratos", 0)
            mensal[key].setdefault("estoque_inicial", None)
            mensal[key].setdefault("estoque_final", None)
    return year_data


def _normalize_torre_meta(torre_data: dict) -> dict:
    if not isinstance(torre_data, dict):
        torre_data = {}
    torre_data.setdefault("id", "")
    torre_data.setdefault("nome", "")
    torre_data.setdefault("segmento", "")
    torre_data.setdefault("total_unidades", 0)
    return torre_data


def _normalize_empreendimento_meta(emp_data: dict) -> dict:
    if not isinstance(emp_data, dict):
        emp_data = {}
    emp_data.setdefault("id", "")
    emp_data.setdefault("nome", "")
    emp_data.setdefault("segmento", "")
    emp_data.setdefault("total_unidades", 0)
    torres = emp_data.setdefault("torres", {})
    if not isinstance(torres, dict):
        torres = {}
        emp_data["torres"] = torres
    for torre_id, torre_data in torres.items():
        if not isinstance(torre_id, str):
            continue
        torres[torre_id] = _normalize_torre_meta(torre_data)
    return emp_data


def _normalize_projecao_meta(proj_data: dict) -> dict:
    if not isinstance(proj_data, dict):
        proj_data = {}
    proj_data.setdefault("id", "")
    proj_data.setdefault("nome", "")
    proj_data.setdefault("tipo", "Comite")
    proj_data.setdefault("updated_at", None)
    return proj_data


def _normalize_relacoes(relacoes: dict) -> dict:
    if not isinstance(relacoes, dict):
        relacoes = {}
    for proj_id, emp_map in relacoes.items():
        if not isinstance(proj_id, str) or not isinstance(emp_map, dict):
            continue
        for emp_id, torre_map in emp_map.items():
            if not isinstance(emp_id, str) or not isinstance(torre_map, dict):
                continue
            for torre_id, rel in torre_map.items():
                if not isinstance(torre_id, str) or not isinstance(rel, dict):
                    continue
                anos = rel.setdefault("anos", {})
                if not isinstance(anos, dict):
                    anos = {}
                    rel["anos"] = anos
                for year_key, year_data in anos.items():
                    if not isinstance(year_key, str):
                        continue
                    anos[year_key] = _normalize_year(year_data)
    return relacoes


def _load_json(path: str, fallback: dict) -> dict:
    if not os.path.exists(path):
        return deepcopy(fallback)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return deepcopy(fallback)


def _save_json(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True, ensure_ascii=False)


def _slug(value: str) -> str:
    cleaned = []
    for char in value.strip():
        if char.isalnum():
            cleaned.append(char.upper())
        elif char in {" ", "-", "_"}:
            cleaned.append("-")
    slug = "".join(cleaned).strip("-")
    return slug or "X"


def _unique_id(prefix: str, name: str, used: set[str]) -> str:
    base = _slug(name)
    candidate = f"{prefix}-{base}"
    counter = 2
    while candidate in used:
        candidate = f"{prefix}-{base}-{counter}"
        counter += 1
    used.add(candidate)
    return candidate


def _select_ciclo(ciclo_map: dict) -> tuple[str, dict] | None:
    if not isinstance(ciclo_map, dict) or not ciclo_map:
        return None
    if DEFAULT_CICLO in ciclo_map:
        return DEFAULT_CICLO, ciclo_map[DEFAULT_CICLO]
    ciclo_ids = sorted(key for key in ciclo_map.keys() if isinstance(key, str))
    if not ciclo_ids:
        return None
    ciclo_id = ciclo_ids[-1]
    return ciclo_id, ciclo_map[ciclo_id]


def _series_to_relacoes(series_root: dict) -> dict:
    relacoes: dict = {}
    if not isinstance(series_root, dict):
        return relacoes
    for proj_id, emp_map in series_root.items():
        if not isinstance(proj_id, str) or not isinstance(emp_map, dict):
            continue
        for emp_id, torre_map in emp_map.items():
            if not isinstance(emp_id, str) or not isinstance(torre_map, dict):
                continue
            for torre_id, ciclo_map in torre_map.items():
                if not isinstance(torre_id, str) or not isinstance(ciclo_map, dict):
                    continue
                selected = _select_ciclo(ciclo_map)
                if not selected:
                    continue
                ciclo_id, series_payload = selected
                if not isinstance(series_payload, dict):
                    continue
                series_obj = ProjectionSeries.from_dict(series_payload)
                year_map = series_to_year_map(series_obj.serie, series_obj.anuais)
                rel = (
                    relacoes
                    .setdefault(proj_id, {})
                    .setdefault(emp_id, {})
                    .setdefault(torre_id, {"anos": {}})
                )
                rel["anos"] = year_map
                rel["ciclo"] = ciclo_id
    return relacoes


def _relacoes_to_series(relacoes: dict) -> dict:
    series_root: dict = {}
    if not isinstance(relacoes, dict):
        return series_root
    for proj_id, emp_map in relacoes.items():
        if not isinstance(proj_id, str) or not isinstance(emp_map, dict):
            continue
        for emp_id, torre_map in emp_map.items():
            if not isinstance(emp_id, str) or not isinstance(torre_map, dict):
                continue
            for torre_id, rel in torre_map.items():
                if not isinstance(torre_id, str) or not isinstance(rel, dict):
                    continue
                anos = rel.get("anos", {}) if isinstance(rel.get("anos"), dict) else {}
                ciclo_id = rel.get("ciclo") if isinstance(rel.get("ciclo"), str) else DEFAULT_CICLO
                serie, annuals = year_map_to_series_and_annuals(anos)
                indice_data = build_indice_data(serie)
                series_obj = ProjectionSeries(
                    projeto_id=proj_id,
                    empreendimento_id=emp_id,
                    torre_id=torre_id,
                    ciclo=ciclo_id,
                    serie=serie,
                    indice_data=indice_data,
                    anuais=annuals,
                )
                (
                    series_root
                    .setdefault(proj_id, {})
                    .setdefault(emp_id, {})
                    .setdefault(torre_id, {})
                )[ciclo_id] = series_obj.to_dict()
    return series_root


def _normalize_empreendimentos(empreendimentos: dict) -> dict:
    if not isinstance(empreendimentos, dict):
        empreendimentos = {}
    for emp_id, emp_data in empreendimentos.items():
        if not isinstance(emp_id, str):
            continue
        empreendimentos[emp_id] = _normalize_empreendimento_meta(emp_data)
    return empreendimentos


def _normalize_projecoes(projecoes: dict) -> dict:
    if not isinstance(projecoes, dict):
        projecoes = {}
    for proj_id, proj_data in projecoes.items():
        if not isinstance(proj_id, str):
            continue
        projecoes[proj_id] = _normalize_projecao_meta(proj_data)
    return projecoes


def load_data() -> dict:
    data = deepcopy(DEFAULT_DATA)

    emp_path = empreendimentos_path()
    proj_path = projecoes_path()
    series_file = series_path()

    data["empreendimentos"] = _load_json(emp_path, {}).get("empreendimentos", {})
    data["projecoes"] = _load_json(proj_path, {}).get("projecoes", {})
    series_root = _load_json(series_file, {}).get("series", {})
    data["relacoes"] = _series_to_relacoes(series_root)

    data["empreendimentos"] = _normalize_empreendimentos(data["empreendimentos"])
    data["projecoes"] = _normalize_projecoes(data["projecoes"])
    data["relacoes"] = _normalize_relacoes(data["relacoes"])
    return data


def save_data(data: dict) -> None:
    _save_json(empreendimentos_path(), {"empreendimentos": data.get("empreendimentos", {})})
    _save_json(projecoes_path(), {"projecoes": data.get("projecoes", {})})
    series_root = _relacoes_to_series(data.get("relacoes", {}))
    _save_json(series_path(), {"series": series_root})


def get_or_create_projection(data: dict, proj_id: str) -> dict:
    projecoes = data.setdefault("projecoes", {})
    if proj_id not in projecoes:
        projecoes[proj_id] = {"id": proj_id, "nome": "", "tipo": "Comite", "updated_at": None}
    projecoes[proj_id] = _normalize_projecao_meta(projecoes[proj_id])
    return projecoes[proj_id]


def get_or_create_empreendimento(data: dict, emp_id: str) -> dict:
    empreendimentos = data.setdefault("empreendimentos", {})
    if emp_id not in empreendimentos:
        empreendimentos[emp_id] = {
            "id": emp_id,
            "nome": "",
            "segmento": "",
            "total_unidades": 0,
            "torres": {},
        }
    empreendimentos[emp_id] = _normalize_empreendimento_meta(empreendimentos[emp_id])
    return empreendimentos[emp_id]


def get_or_create_torre(data: dict, emp_id: str, torre_id: str) -> dict:
    emp_data = get_or_create_empreendimento(data, emp_id)
    torres = emp_data.setdefault("torres", {})
    if torre_id not in torres:
        torres[torre_id] = {
            "id": torre_id,
            "nome": "",
            "segmento": "",
            "total_unidades": 0,
        }
    torres[torre_id] = _normalize_torre_meta(torres[torre_id])
    return torres[torre_id]


def get_or_create_relacao(data: dict, proj_id: str, emp_id: str, torre_id: str) -> dict:
    relacoes = data.setdefault("relacoes", {})
    proj_map = relacoes.setdefault(proj_id, {})
    emp_map = proj_map.setdefault(emp_id, {})
    rel = emp_map.setdefault(torre_id, {"anos": {}})
    rel["anos"] = rel.get("anos", {})
    rel["anos"] = {str(k): _normalize_year(v) for k, v in rel["anos"].items() if isinstance(k, str)}
    if "ciclo" not in rel:
        rel["ciclo"] = DEFAULT_CICLO
    return rel


def get_or_create_year(data: dict, proj_id: str, emp_id: str, torre_id: str, ano: int | str) -> dict:
    rel = get_or_create_relacao(data, proj_id, emp_id, torre_id)
    anos = rel.setdefault("anos", {})
    ano_key = str(ano)
    if ano_key not in anos:
        anos[ano_key] = _new_year()
    anos[ano_key] = _normalize_year(anos[ano_key])
    return anos[ano_key]
