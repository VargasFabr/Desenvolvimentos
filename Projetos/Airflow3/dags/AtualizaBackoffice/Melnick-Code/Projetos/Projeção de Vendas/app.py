import datetime as dt
import io
from typing import Tuple

import altair as alt
import pandas as pd
import streamlit as st

from data_store import (
    get_or_create_empreendimento,
    get_or_create_projection,
    get_or_create_relacao,
    get_or_create_torre,
    get_or_create_year,
    load_data,
    save_data,
)

st.set_page_config(page_title="Projecao de Vendas", layout="wide")

PROJECTION_TYPES = ["Comitê", "Meta", "Viabilidade", "Comercial", "Realizado"]
NEW_OPTION = "(novo)"
ALL_OPTION = "(todas)"


@st.cache_data(show_spinner=False)
def _today_year() -> int:
    return dt.date.today().year


def _to_int(value: object) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _to_number(value: object) -> float:
    if value is None:
        return 0.0
    if isinstance(value, str):
        cleaned = value.strip().replace(",", ".")
    else:
        cleaned = value
    try:
        number = float(cleaned)
    except (TypeError, ValueError):
        return 0.0
    if number < 0:
        return 0.0
    return number


def _format_number(value: float) -> str:
    if abs(value - round(value)) < 1e-6:
        return str(int(round(value)))
    return f"{value:.2f}"


def _clean_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _ensure_data() -> dict:
    if "data" not in st.session_state:
        st.session_state["data"] = load_data()
    return st.session_state["data"]


def _save_data(data: dict) -> None:
    save_data(data)


def _mark_dirty_sidebar() -> None:
    st.session_state["dirty"] = True
    st.session_state["dirty_scope"] = "sidebar"


def _mark_dirty_projection() -> None:
    st.session_state["dirty"] = True
    st.session_state["dirty_scope"] = "projection"


def _build_month_df(year_data: dict) -> pd.DataFrame:
    rows = []
    for month in range(1, 13):
        month_key = str(month)
        values = year_data["mensal"][month_key]
        rows.append({
            "mes": month,
            "vendas": _to_number(values.get("vendas", 0)),
            "distratos": _to_number(values.get("distratos", 0)),
        })
    df = pd.DataFrame(rows)
    df = df.set_index("mes")
    return df


def _update_year_from_df(year_data: dict, df: pd.DataFrame) -> None:
    for month in range(1, 13):
        if month not in df.index:
            continue
        row = df.loc[month]
        year_data["mensal"][str(month)]["vendas"] = _to_number(row.get("vendas", 0))
        year_data["mensal"][str(month)]["distratos"] = _to_number(row.get("distratos", 0))


def _calc_annual_totals(year_data: dict) -> Tuple[float, float]:
    if year_data.get("usar_mensal"):
        vendas_total = 0.0
        distratos_total = 0.0
        for month in range(1, 13):
            values = year_data["mensal"][str(month)]
            vendas_total += _to_number(values.get("vendas", 0))
            distratos_total += _to_number(values.get("distratos", 0))
        return vendas_total, distratos_total
    return (
        _to_number(year_data.get("vendas_anuais", 0)),
        _to_number(year_data.get("distratos_anuais", 0)),
    )


def _calc_monthly_stock(year_data: dict) -> list[float]:
    estoque = _to_number(year_data.get("estoque_inicial", 0))
    estoque_mensal = []
    for month in range(1, 13):
        values = year_data["mensal"][str(month)]
        estoque -= _to_number(values.get("vendas", 0))
        estoque += _to_number(values.get("distratos", 0))
        estoque_mensal.append(estoque)
    return estoque_mensal


def _month_has_activity(month_data: dict) -> bool:
    vendas = _to_number(month_data.get("vendas", 0))
    distratos = _to_number(month_data.get("distratos", 0))
    return abs(vendas) > 0 or abs(distratos) > 0


def _recalc_monthly_fields(year_data: dict, total_unidades: float) -> None:
    if not isinstance(year_data, dict):
        return
    mensal = year_data.get("mensal")
    if not isinstance(mensal, dict):
        return

    base_estoque = year_data.get("estoque_inicial")
    if base_estoque is None or (
        base_estoque == 0 and year_data.get("estoque_inicial_origem") is None
    ):
        base_estoque = total_unidades
    base_estoque = _to_number(base_estoque)

    prev_final = None
    for month in range(1, 13):
        month_key = str(month)
        month_data = mensal.get(month_key)
        if not isinstance(month_data, dict):
            month_data = {}
            mensal[month_key] = month_data
        vendas = _to_number(month_data.get("vendas", 0))
        distratos = _to_number(month_data.get("distratos", 0))
        has_existing = (
            month_data.get("estoque_inicial") is not None
            or month_data.get("estoque_final") is not None
        )
        if _month_has_activity(month_data) or has_existing or prev_final is not None:
            estoque_inicial = base_estoque if prev_final is None else prev_final
            estoque_final = estoque_inicial - vendas + distratos
            month_data["estoque_inicial"] = estoque_inicial
            month_data["estoque_final"] = estoque_final
            prev_final = estoque_final


def _latest_monthly_stock(year_data: dict, total_unidades: float) -> float | None:
    if not isinstance(year_data, dict):
        return None
    mensal = year_data.get("mensal")
    if not isinstance(mensal, dict):
        return None

    _recalc_monthly_fields(year_data, total_unidades)

    latest_stock = None
    for month in range(1, 13):
        month_data = mensal.get(str(month), {})
        if not isinstance(month_data, dict):
            continue
        estoque_final = month_data.get("estoque_final")
        has_month = _month_has_activity(month_data) or estoque_final is not None
        if has_month and estoque_final is not None:
            latest_stock = _to_number(estoque_final)
    return latest_stock


def _calc_year_final_stock(year_data: dict, total_unidades: float) -> float:
    latest_stock = _latest_monthly_stock(year_data, total_unidades)
    if latest_stock is not None:
        return latest_stock

    vendas_total, distratos_total = _calc_annual_totals(year_data)
    base_estoque = year_data.get("estoque_inicial")
    if base_estoque is None or (
        base_estoque == 0 and year_data.get("estoque_inicial_origem") is None
    ):
        base_estoque = total_unidades
    base_estoque = _to_number(base_estoque)
    return base_estoque - vendas_total + distratos_total


def _recompute_all_monthly_fields(data: dict) -> bool:
    relacoes = data.get("relacoes", {})
    empreendimentos = data.get("empreendimentos", {})
    updated = False
    if not isinstance(relacoes, dict):
        return False

    for emp_map in relacoes.values():
        if not isinstance(emp_map, dict):
            continue
        for emp_id, torre_map in emp_map.items():
            if not isinstance(torre_map, dict):
                continue
            emp_data = empreendimentos.get(emp_id, {})
            torres_meta = emp_data.get("torres", {}) if isinstance(emp_data, dict) else {}
            for torre_id, relacao in torre_map.items():
                if not isinstance(relacao, dict):
                    continue
                total_unidades = _to_int(
                    torres_meta.get(torre_id, {}).get("total_unidades", 0)
                )
                anos = relacao.get("anos", {})
                if not isinstance(anos, dict):
                    continue
                for year_data in anos.values():
                    if not isinstance(year_data, dict):
                        continue
                    _recalc_monthly_fields(year_data, total_unidades)
                    updated = True
    return updated


def _render_stock_metric(label: str, value: float) -> None:
    color = ""
    if value < 0:
        color = "#e74c3c"
    elif value == 0:
        color = "#2ecc71"
    style = f"color: {color};" if color else ""
    parts = label.split(" ", 1)
    if len(parts) == 2:
        label_html = f"{parts[0]}<br>{parts[1]}"
    else:
        label_html = label
    style_attr = f' style="{style}"' if style else ""
    st.markdown(
        (
            '<div class="metric-row">'
            f'<div class="metric-label">{label_html}</div>'
            f'<div class="metric-value"{style_attr}>{_format_number(value)}</div>'
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def _inject_metric_styles() -> None:
    st.markdown(
        """
<style>
.metric-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  margin-top: 0.15rem;
  min-height: 2.6rem;
}
.metric-label {
  font-size: 0.8rem;
  color: #a6a6a6;
  line-height: 1.05;
  text-align: left;
  min-height: 1.7rem;
}
.metric-value {
  font-size: 1.4rem;
  font-weight: 600;
  line-height: 1;
  text-align: right;
}
div[data-testid="stSidebar"] button[kind="primary"] {
    background-color: #c0392b;
    border-color: #c0392b;
}
div[data-testid="stSidebar"] button[kind="primary"]:hover {
    background-color: #a93226;
    border-color: #a93226;
}
</style>
""",
        unsafe_allow_html=True,
    )


def _render_compact_metric(label: str, value: float) -> None:
    st.markdown(
        (
            f'<div style="font-size:0.8rem; color:#a6a6a6; margin-top:0.2rem;">{label}</div>'
            f'<div style="font-size:1.2rem; font-weight:600; line-height:1.1;">{_format_number(value)}</div>'
        ),
        unsafe_allow_html=True,
    )


def _seed_year_state(
    key_prefix: str,
    years: list[int],
    base_year: int,
    base_data: dict,
    year_data_map: dict[int, dict],
) -> None:
    vendas_key = f"{key_prefix}_vendas_anuais_{base_year}"
    distratos_key = f"{key_prefix}_distratos_anuais_{base_year}"
    if vendas_key not in st.session_state:
        st.session_state[vendas_key] = _to_number(base_data.get("vendas_anuais", 0))
    if distratos_key not in st.session_state:
        st.session_state[distratos_key] = _to_number(base_data.get("distratos_anuais", 0))

    for year in years[1:]:
        year_data = year_data_map[year]
        vendas_key = f"{key_prefix}_vendas_anuais_{year}"
        distratos_key = f"{key_prefix}_distratos_anuais_{year}"
        if vendas_key not in st.session_state:
            st.session_state[vendas_key] = _to_number(year_data.get("vendas_anuais", 0))
        if distratos_key not in st.session_state:
            st.session_state[distratos_key] = _to_number(
                year_data.get("distratos_anuais", 0)
            )


def _number_input_stateful(label: str, key: str, value: float, **kwargs) -> float:
    if key in st.session_state:
        return st.number_input(label, key=key, **kwargs)
    return st.number_input(label, key=key, value=value, **kwargs)


def _filtered_relacoes(data: dict, proj_id: str, emp_id: str, emp_data: dict) -> dict:
    relacoes = data.get("relacoes", {}).get(proj_id, {}).get(emp_id, {})
    allowed_torres = {
        torre_id
        for torre_id in emp_data.get("torres", {}).keys()
        if isinstance(torre_id, str) and torre_id and torre_id != "null"
    }
    return {
        torre_id: rel
        for torre_id, rel in relacoes.items()
        if torre_id in allowed_torres
    }


def _year_range(start_year: int, count: int) -> list[int]:
    return [start_year + offset for offset in range(count)]


def _resolve_base_year(anos: dict) -> int:
    current_year = _today_year()
    if not isinstance(anos, dict):
        return current_year
    try:
        years = sorted(int(year) for year in anos.keys())
    except (TypeError, ValueError):
        years = []

    if current_year in years:
        return current_year
    if years:
        return years[-1]
    return current_year


def _key_prefix(*parts: str | None) -> str:
    cleaned = []
    for part in parts:
        if not part:
            cleaned.append("none")
        else:
            cleaned.append(str(part).replace(" ", "_").lower())
    return "__".join(cleaned)


def _label_for(options: dict, option_id: str) -> str:
    if option_id in (NEW_OPTION, ALL_OPTION):
        return option_id
    entry = options.get(option_id, {})
    name = entry.get("nome") if isinstance(entry, dict) else ""
    if name:
        return f"{option_id} - {name}"
    return f"{option_id} - (sem nome)"


def _slug(value: str) -> str:
    cleaned = []
    for char in value.strip():
        if char.isalnum():
            cleaned.append(char.upper())
        elif char in {" ", "-", "_"}:
            cleaned.append("-")
    slug = "".join(cleaned).strip("-")
    return slug or "PROJ"


def _generate_proj_id(projecoes: dict, name: str) -> str:
    used = {key for key in projecoes.keys() if isinstance(key, str)}
    base = _slug(name)
    if not base.startswith("PROJ"):
        base = f"PROJ-{base}"
    candidate = base
    counter = 2
    while candidate in used:
        candidate = f"{base}-{counter}"
        counter += 1
    return candidate


def _rename_key(container: dict, old_id: str, new_id: str) -> str:
    if not new_id or new_id == old_id or new_id in container:
        return old_id
    container[new_id] = container.pop(old_id)
    if isinstance(container[new_id], dict):
        container[new_id]["id"] = new_id
    return new_id


def _rename_emp_id(data: dict, old_id: str, new_id: str) -> str:
    empreendimentos = data.get("empreendimentos", {})
    new_id = _rename_key(empreendimentos, old_id, new_id)
    for proj_id, emp_map in data.get("relacoes", {}).items():
        if old_id in emp_map and old_id != new_id:
            emp_map[new_id] = emp_map.pop(old_id)
    return new_id


def _rename_torre_id(data: dict, emp_id: str, old_id: str, new_id: str) -> str:
    emp_data = data.get("empreendimentos", {}).get(emp_id, {})
    torres = emp_data.get("torres", {})
    new_id = _rename_key(torres, old_id, new_id)
    for proj_id, emp_map in data.get("relacoes", {}).items():
        torre_map = emp_map.get(emp_id, {})
        if old_id in torre_map and old_id != new_id:
            torre_map[new_id] = torre_map.pop(old_id)
    return new_id


def _render_sidebar(data: dict) -> Tuple[str | None, str | None, str | None, bool]:
    st.sidebar.header("Cadastro")

    projecoes = data.setdefault("projecoes", {})
    proj_ids = sorted(key for key in projecoes.keys() if isinstance(key, str))

    if "pending_proj" in st.session_state:
        pending_proj = st.session_state.pop("pending_proj")
        if pending_proj not in projecoes:
            get_or_create_projection(data, pending_proj)
        st.session_state["selected_proj"] = pending_proj

    if "selected_proj" not in st.session_state:
        st.session_state["selected_proj"] = proj_ids[0] if proj_ids else NEW_OPTION

    if st.session_state["selected_proj"] not in proj_ids + [NEW_OPTION]:
        st.session_state["selected_proj"] = NEW_OPTION

    with st.sidebar.expander("Projecao", expanded=True):
        proj_choice = st.selectbox(
            "Projecao",
            [NEW_OPTION] + proj_ids,
            key="selected_proj",
            format_func=lambda value: _label_for(projecoes, value),
        )

        if proj_choice == NEW_OPTION:
            new_proj_nome = _clean_text(st.text_input("Nome da projecao"))
            new_proj_tipo = st.selectbox(
                "Tipo da projecao",
                options=PROJECTION_TYPES,
                key="new_proj_tipo",
            )
            new_proj_id = _generate_proj_id(projecoes, new_proj_nome)
            st.caption(f"ID gerado: {new_proj_id}")
            if st.button("Criar projecao"):
                proj_data = get_or_create_projection(data, new_proj_id)
                proj_data["nome"] = new_proj_nome or proj_data.get("nome", "")
                proj_data["tipo"] = new_proj_tipo
                _save_data(data)
                st.session_state["pending_proj"] = new_proj_id
                st.rerun()
            return None, None, None, False

        proj_data = get_or_create_projection(data, proj_choice)
        if st.session_state.get("last_proj_choice") != proj_choice:
            st.session_state["last_proj_choice"] = proj_choice
            st.session_state[f"proj_nome_{proj_choice}"] = proj_data.get("nome", "")
            current_tipo = proj_data.get("tipo", "Comite")
            if current_tipo == "Comite":
                current_tipo = "Comitê"
            st.session_state[f"proj_tipo_{proj_choice}"] = current_tipo
        proj_data["nome"] = _clean_text(
            st.text_input(
            "Nome da projecao",
            key=f"proj_nome_{proj_choice}",
            on_change=_mark_dirty_sidebar,
            )
        )
        current_tipo = st.session_state.get(
            f"proj_tipo_{proj_choice}",
            proj_data.get("tipo", "Comite"),
        )
        if current_tipo == "Comite":
            current_tipo = "Comitê"
        proj_data["tipo"] = st.selectbox(
            "Tipo da projecao",
            options=PROJECTION_TYPES,
            index=PROJECTION_TYPES.index(current_tipo) if current_tipo in PROJECTION_TYPES else 0,
            key=f"proj_tipo_{proj_choice}",
            on_change=_mark_dirty_sidebar,
        )

        if st.button("Importar Excel/CSV", use_container_width=True):
            st.session_state["show_import_modal"] = True
        if st.button("Resetar projecao", use_container_width=True):
            st.session_state["show_reset_confirm"] = True
        if st.session_state.get("show_reset_confirm"):
            st.warning("Isso vai zerar vendas/distratos e ajustar o estoque inicial. Deseja continuar?")
            if st.button("Confirmar reset", type="primary", use_container_width=True):
                st.session_state["request_reset_projection"] = True
                st.session_state["show_reset_confirm"] = False
                st.rerun()
            if st.button("Cancelar", use_container_width=True):
                st.session_state["show_reset_confirm"] = False
                st.rerun()

    with st.sidebar.expander("Empreendimentos", expanded=True):
        empreendimentos = data.setdefault("empreendimentos", {})
        emp_ids = sorted(key for key in empreendimentos.keys() if isinstance(key, str))

        if "pending_emp" in st.session_state:
            pending_emp = st.session_state.pop("pending_emp")
            if pending_emp not in empreendimentos:
                get_or_create_empreendimento(data, pending_emp)
            st.session_state["selected_emp"] = pending_emp

        if "selected_emp" not in st.session_state:
            st.session_state["selected_emp"] = emp_ids[0] if emp_ids else NEW_OPTION

        if st.session_state["selected_emp"] not in emp_ids + [NEW_OPTION]:
            st.session_state["selected_emp"] = NEW_OPTION

        emp_choice = st.selectbox(
            "Empreendimento",
            [NEW_OPTION] + emp_ids,
            key="selected_emp",
            format_func=lambda value: _label_for(empreendimentos, value),
        )

        if emp_choice == NEW_OPTION:
            new_emp_id = _clean_text(st.text_input("ID do empreendimento"))
            new_emp_nome = _clean_text(st.text_input("Nome do empreendimento"))
            new_emp_segmento = _clean_text(st.text_input("Segmento do empreendimento"))
            new_emp_total = st.number_input(
                "Total de unidades",
                min_value=0,
                step=1,
                value=0,
            )
            if st.button("Criar empreendimento"):
                if not new_emp_id:
                    st.error("Informe um ID de empreendimento.")
                elif new_emp_id in empreendimentos:
                    st.error("ID de empreendimento ja existe.")
                else:
                    emp_data = get_or_create_empreendimento(data, new_emp_id)
                    emp_data["nome"] = new_emp_nome
                    emp_data["segmento"] = new_emp_segmento
                    emp_data["total_unidades"] = _to_int(new_emp_total)
                    _save_data(data)
                    st.session_state["pending_emp"] = new_emp_id
                    st.rerun()
            return proj_choice, None, None, False

        emp_data = get_or_create_empreendimento(data, emp_choice)
        old_emp_id = emp_choice
        emp_state_key = f"{proj_choice}::{emp_choice}"
        emp_key_prefix = _key_prefix("emp", proj_choice, emp_choice)
        if st.session_state.get("last_emp_choice") != emp_state_key:
            st.session_state["last_emp_choice"] = emp_state_key
            st.session_state["selected_torre"] = ALL_OPTION
            st.session_state[f"{emp_key_prefix}_id"] = emp_data.get("id", old_emp_id)
            st.session_state[f"{emp_key_prefix}_nome"] = emp_data.get("nome", "")
            st.session_state[f"{emp_key_prefix}_segmento"] = emp_data.get("segmento", "")
            st.session_state[f"{emp_key_prefix}_total"] = _to_int(
                emp_data.get("total_unidades", 0)
            )
        else:
            if f"{emp_key_prefix}_id" not in st.session_state:
                st.session_state[f"{emp_key_prefix}_id"] = emp_data.get("id", old_emp_id)
            if f"{emp_key_prefix}_nome" not in st.session_state:
                st.session_state[f"{emp_key_prefix}_nome"] = emp_data.get("nome", "")
            if f"{emp_key_prefix}_segmento" not in st.session_state:
                st.session_state[f"{emp_key_prefix}_segmento"] = emp_data.get("segmento", "")
            if f"{emp_key_prefix}_total" not in st.session_state:
                st.session_state[f"{emp_key_prefix}_total"] = _to_int(
                    emp_data.get("total_unidades", 0)
                )
        new_emp_id = _clean_text(
            st.text_input(
            "ID do empreendimento",
                key=f"{emp_key_prefix}_id",
            on_change=_mark_dirty_sidebar,
            )
        )
        if new_emp_id and new_emp_id != old_emp_id:
            emp_choice = _rename_emp_id(data, old_emp_id, new_emp_id)
            emp_data = get_or_create_empreendimento(data, emp_choice)
            st.session_state["selected_emp"] = emp_choice

        emp_data["id"] = emp_choice
        emp_data["nome"] = _clean_text(
            st.text_input(
            "Nome do empreendimento",
                key=f"{emp_key_prefix}_nome",
            on_change=_mark_dirty_sidebar,
            )
        )
        emp_data["segmento"] = _clean_text(
            st.text_input(
            "Segmento do empreendimento",
                key=f"{emp_key_prefix}_segmento",
            on_change=_mark_dirty_sidebar,
            )
        )
        emp_data["total_unidades"] = _to_int(
            st.number_input(
                "Total de unidades",
                min_value=0,
                step=1,
                key=f"{emp_key_prefix}_total",
                on_change=_mark_dirty_sidebar,
            )
        )

        torres = emp_data.setdefault("torres", {})
        torre_ids = sorted(key for key in torres.keys() if isinstance(key, str))

        if "pending_torre" in st.session_state:
            pending_torre = st.session_state.pop("pending_torre")
            if pending_torre not in torres:
                get_or_create_torre(data, emp_choice, pending_torre)
            st.session_state["selected_torre"] = pending_torre

        if "selected_torre" not in st.session_state:
            st.session_state["selected_torre"] = ALL_OPTION if torre_ids else NEW_OPTION

        if st.session_state["selected_torre"] not in torre_ids + [NEW_OPTION, ALL_OPTION]:
            st.session_state["selected_torre"] = ALL_OPTION if torre_ids else NEW_OPTION

        torre_choice = st.selectbox(
            "Torre",
            [ALL_OPTION, NEW_OPTION] + torre_ids,
            key="selected_torre",
            format_func=lambda value: _label_for(torres, value),
        )

        if torre_choice == NEW_OPTION:
            new_torre_id = _clean_text(st.text_input("ID da torre"))
            new_torre_nome = _clean_text(st.text_input("Nome da torre"))
            new_torre_segmento = _clean_text(st.text_input("Segmento da torre"))
            new_torre_total = st.number_input(
                "Total de unidades da torre",
                min_value=0,
                step=1,
                value=0,
            )
            if st.button("Criar torre"):
                if not new_torre_id:
                    st.error("Informe um ID de torre.")
                elif new_torre_id in torres:
                    st.error("ID de torre ja existe.")
                else:
                    torre_data = get_or_create_torre(data, emp_choice, new_torre_id)
                    torre_data["nome"] = new_torre_nome
                    torre_data["segmento"] = new_torre_segmento
                    torre_data["total_unidades"] = _to_int(new_torre_total)
                    _save_data(data)
                    st.session_state["pending_torre"] = new_torre_id
                    st.rerun()
            return proj_choice, emp_choice, None, False

        is_aggregate = torre_choice == ALL_OPTION
        selected_torre = None if is_aggregate else torre_choice

        if not is_aggregate:
            torre_data = get_or_create_torre(data, emp_choice, torre_choice)
            old_torre_id = torre_choice
            torre_state_key = f"{proj_choice}::{emp_choice}::{torre_choice}"
            torre_key_prefix = _key_prefix("torre", proj_choice, emp_choice, torre_choice)
            if st.session_state.get("last_torre_choice") != torre_state_key:
                st.session_state["last_torre_choice"] = torre_state_key
                st.session_state[f"{torre_key_prefix}_id"] = torre_data.get(
                    "id", old_torre_id
                )
                st.session_state[f"{torre_key_prefix}_nome"] = torre_data.get("nome", "")
                st.session_state[f"{torre_key_prefix}_segmento"] = torre_data.get(
                    "segmento", ""
                )
                st.session_state[f"{torre_key_prefix}_total"] = _to_int(
                    torre_data.get("total_unidades", 0)
                )
            else:
                if f"{torre_key_prefix}_id" not in st.session_state:
                    st.session_state[f"{torre_key_prefix}_id"] = torre_data.get(
                        "id", old_torre_id
                    )
                if f"{torre_key_prefix}_nome" not in st.session_state:
                    st.session_state[f"{torre_key_prefix}_nome"] = torre_data.get(
                        "nome", ""
                    )
                if f"{torre_key_prefix}_segmento" not in st.session_state:
                    st.session_state[f"{torre_key_prefix}_segmento"] = torre_data.get(
                        "segmento", ""
                    )
                if f"{torre_key_prefix}_total" not in st.session_state:
                    st.session_state[f"{torre_key_prefix}_total"] = _to_int(
                        torre_data.get("total_unidades", 0)
                    )
            new_torre_id = _clean_text(
                st.text_input(
                "ID da torre",
                    key=f"{torre_key_prefix}_id",
                on_change=_mark_dirty_sidebar,
                )
            )
            if new_torre_id and new_torre_id != old_torre_id:
                selected_torre = _rename_torre_id(data, emp_choice, old_torre_id, new_torre_id)
                torre_data = get_or_create_torre(data, emp_choice, selected_torre)
                st.session_state["selected_torre"] = selected_torre

            torre_data["id"] = selected_torre
            torre_data["nome"] = _clean_text(
                st.text_input(
                "Nome da torre",
                    key=f"{torre_key_prefix}_nome",
                on_change=_mark_dirty_sidebar,
                )
            )
            torre_data["segmento"] = _clean_text(
                st.text_input(
                "Segmento da torre",
                    key=f"{torre_key_prefix}_segmento",
                on_change=_mark_dirty_sidebar,
                )
            )
            torre_data["total_unidades"] = _to_int(
                st.number_input(
                    "Total de unidades da torre",
                    min_value=0,
                    step=1,
                    key=f"{torre_key_prefix}_total",
                    on_change=_mark_dirty_sidebar,
                )
            )

    return proj_choice, emp_choice, selected_torre, is_aggregate


def _render_stock_timeline(year_summaries: dict[int, dict]) -> None:
    years = sorted(year_summaries.keys())
    stock_df = pd.DataFrame(
        {
            "ano": years,
            "estoque": [year_summaries[year]["estoque_final"] for year in years],
        }
    ).set_index("ano")
    st.subheader("Estoque no tempo")
    st.line_chart(stock_df)


def _percent_series_for_projection(
    data: dict,
    proj_id: str,
    emp_id: str,
    torre_id: str | None,
    is_aggregate: bool,
    years: list[int],
    emp_data: dict,
) -> list[dict] | None:
    if not proj_id or not emp_id:
        return None

    if is_aggregate:
        relacoes = _filtered_relacoes(data, proj_id, emp_id, emp_data)
        if not relacoes:
            return None
        total_unidades_map = {
            torre_id: _to_int(torre.get("total_unidades", 0))
            for torre_id, torre in emp_data.get("torres", {}).items()
            if isinstance(torre_id, str) and isinstance(torre, dict)
        }
        total_unidades = sum(total_unidades_map.values())
    else:
        if not torre_id:
            return None
        relacao = data.get("relacoes", {}).get(proj_id, {}).get(emp_id, {}).get(torre_id, {})
        if not isinstance(relacao, dict):
            return None
        total_unidades = _to_int(
            emp_data.get("torres", {}).get(torre_id, {}).get("total_unidades", 0)
        )
        relacoes = {torre_id: relacao}

    if total_unidades <= 0:
        return None

    rows: list[dict] = []
    has_data = False
    for year in years:
        if is_aggregate:
            estoque_final_total = 0.0
            for torre_key, unidades in total_unidades_map.items():
                torre_rel = relacoes.get(torre_key)
                year_data = (
                    torre_rel.get("anos", {}).get(str(year))
                    if isinstance(torre_rel, dict)
                    else None
                )
                if isinstance(year_data, dict):
                    estoque_final_total += _calc_year_final_stock(year_data, unidades)
                    has_data = True
                else:
                    estoque_final_total += unidades
        else:
            year_data = relacoes[torre_id].get("anos", {}).get(str(year))
            if isinstance(year_data, dict):
                estoque_final_total = _calc_year_final_stock(year_data, total_unidades)
                has_data = True
            else:
                estoque_final_total = total_unidades

        vendido_total = max(0.0, total_unidades - estoque_final_total)
        percentual = (vendido_total / total_unidades * 100) if total_unidades > 0 else 0
        percentual = max(0.0, min(100.0, percentual))
        rows.append({"ano": str(year), "percentual": percentual})

    if not has_data:
        return None
    return rows


def _available_years_for_projection(
    data: dict,
    proj_id: str,
    emp_id: str,
    torre_id: str | None,
    is_aggregate: bool,
    emp_data: dict,
) -> set[int]:
    years: set[int] = set()
    if not proj_id or not emp_id:
        return years

    if is_aggregate:
        relacoes = _filtered_relacoes(data, proj_id, emp_id, emp_data)
    else:
        if not torre_id:
            return years
        relacao = data.get("relacoes", {}).get(proj_id, {}).get(emp_id, {}).get(torre_id, {})
        if not isinstance(relacao, dict):
            return years
        relacoes = {torre_id: relacao}

    for torre_rel in relacoes.values():
        anos = torre_rel.get("anos", {})
        if not isinstance(anos, dict):
            continue
        for year_key in anos.keys():
            try:
                years.add(int(year_key))
            except (TypeError, ValueError):
                continue
    return years


def _build_year_rows_for_projection(
    data: dict,
    proj_id: str,
    emp_id: str,
    torre_id: str | None,
    is_aggregate: bool,
    years: list[int],
    emp_data: dict,
) -> list[dict]:
    if not proj_id or not emp_id:
        return []

    if is_aggregate:
        relacoes = _filtered_relacoes(data, proj_id, emp_id, emp_data)
        total_unidades_map = {
            torre_id: _to_int(torre.get("total_unidades", 0))
            for torre_id, torre in emp_data.get("torres", {}).items()
            if isinstance(torre_id, str) and isinstance(torre, dict)
        }
        total_unidades = sum(total_unidades_map.values())
    else:
        if not torre_id:
            return []
        relacao = data.get("relacoes", {}).get(proj_id, {}).get(emp_id, {}).get(torre_id, {})
        if not isinstance(relacao, dict):
            return []
        relacoes = {torre_id: relacao}
        total_unidades = _to_int(
            emp_data.get("torres", {}).get(torre_id, {}).get("total_unidades", 0)
        )

    rows = []
    for year in years:
        total_vendas = 0.0
        total_distratos = 0.0
        estoque_final_total = 0.0
        for torre_rel in relacoes.values():
            year_data = torre_rel.get("anos", {}).get(str(year))
            if not isinstance(year_data, dict):
                continue
            vendas_total, distratos_total = _calc_annual_totals(year_data)
            total_vendas += vendas_total
            total_distratos += distratos_total
        if is_aggregate:
            for torre_key, unidades in total_unidades_map.items():
                torre_rel = relacoes.get(torre_key)
                year_data = (
                    torre_rel.get("anos", {}).get(str(year))
                    if isinstance(torre_rel, dict)
                    else None
                )
                if isinstance(year_data, dict):
                    estoque_final_total += _calc_year_final_stock(year_data, unidades)
                else:
                    estoque_final_total += unidades
        else:
            year_data = relacoes[torre_id].get("anos", {}).get(str(year))
            if isinstance(year_data, dict):
                estoque_final_total = _calc_year_final_stock(year_data, total_unidades)
            else:
                estoque_final_total = total_unidades

        vendido_total = max(0.0, total_unidades - estoque_final_total)
        percentual = (vendido_total / total_unidades * 100) if total_unidades > 0 else 0
        percentual = max(0.0, min(100.0, percentual))
        rows.append(
            {
                "ano": str(year),
                "vendas": total_vendas,
                "distratos": -total_distratos,
                "percentual": percentual,
            }
        )
    return rows


def _render_sales_mix_chart(
    year_summaries: dict[int, dict],
    data: dict,
    proj_id: str,
    emp_id: str,
    torre_id: str | None,
    is_aggregate: bool,
    emp_data: dict,
) -> None:
    if not year_summaries:
        return

    selected_years = _available_years_for_projection(
        data,
        proj_id,
        emp_id,
        torre_id,
        is_aggregate,
        emp_data,
    )
    viabilidade_years = _available_years_for_projection(
        data,
        "PROJ-VIABILIDADE",
        emp_id,
        torre_id,
        is_aggregate,
        emp_data,
    )
    realizado_years = _available_years_for_projection(
        data,
        "PROJ-REALIZADO",
        emp_id,
        torre_id,
        is_aggregate,
        emp_data,
    )
    all_years = set(year_summaries.keys()) | selected_years | viabilidade_years | realizado_years
    if all_years:
        start_year = min(all_years)
        end_year = max(all_years)
        years = list(range(start_year, end_year + 1))
    else:
        years = sorted(year_summaries.keys())

    rows = _build_year_rows_for_projection(
        data,
        proj_id,
        emp_id,
        torre_id,
        is_aggregate,
        years,
        emp_data,
    )

    start_idx = None
    for idx, row in enumerate(rows):
        if abs(row.get("vendas", 0)) > 0 or abs(row.get("distratos", 0)) > 0:
            start_idx = idx
            break
    if start_idx is None:
        line_rows = []
    else:
        line_rows = [
            {
                "ano": row["ano"],
                "percentual": row["percentual"],
                "serie": "Selecionada",
            }
            for row in rows[start_idx:]
            if row.get("percentual", 0) > 0
        ]

    if proj_id != "PROJ-VIABILIDADE":
        viabilidade_rows = _percent_series_for_projection(
            data,
            "PROJ-VIABILIDADE",
            emp_id,
            torre_id,
            is_aggregate,
            years,
            emp_data,
        )
        if viabilidade_rows:
            line_rows.extend(
                {
                    "ano": row["ano"],
                    "percentual": row["percentual"],
                    "serie": "Viabilidade",
                }
                for row in viabilidade_rows
            )

    if proj_id != "PROJ-REALIZADO":
        realizado_rows = _percent_series_for_projection(
            data,
            "PROJ-REALIZADO",
            emp_id,
            torre_id,
            is_aggregate,
            years,
            emp_data,
        )
        if realizado_rows:
            current_year = _today_year()
            realizado_rows = [
                row
                for row in realizado_rows
                if int(row.get("ano", 0)) <= current_year
            ]
        if realizado_rows:
            line_rows.extend(
                {
                    "ano": row["ano"],
                    "percentual": row["percentual"],
                    "serie": "Realizado",
                }
                for row in realizado_rows
            )

    chart_df = pd.DataFrame(rows)
    x_domain = [str(year) for year in years]
    bar_chart = (
        alt.Chart(chart_df)
        .transform_fold(["vendas", "distratos"], as_=["tipo", "valor"])
        .transform_calculate(
            tipo_label="datum.tipo == 'vendas' ? 'Vendas' : 'Distratos'"
        )
        .mark_bar()
        .encode(
            x=alt.X(
                "ano:O",
                title=None,
                scale=alt.Scale(domain=x_domain),
                axis=alt.Axis(labelFontSize=12, labelOverlap="greedy", labelAngle=0),
            ),
            y=alt.Y("valor:Q", title=None, axis=None),
            color=alt.Color(
                "tipo_label:N",
                scale=alt.Scale(domain=["Vendas", "Distratos"], range=["#2e7d59", "#a3473f"]),
                legend=alt.Legend(title="Volume"),
            ),
            tooltip=[
                alt.Tooltip("ano:N", title="Ano"),
                alt.Tooltip("tipo_label:N", title="Tipo"),
                alt.Tooltip("valor:Q", title="Total", format=".2f"),
            ],
        )
    )

    bar_labels_bg = (
        alt.Chart(chart_df)
        .transform_fold(["vendas", "distratos"], as_=["tipo", "valor"])
        .transform_calculate(center="datum.valor / 2")
        .mark_text(
            fontSize=18,
            color="#0f1114",
            opacity=0.6,
            align="center",
            baseline="middle",
        )
        .encode(
            x=alt.X("ano:O", scale=alt.Scale(domain=x_domain)),
            y=alt.Y("center:Q", axis=None),
            text=alt.Text("valor:Q", format=".2f"),
        )
    )

    bar_labels = (
        alt.Chart(chart_df)
        .transform_fold(["vendas", "distratos"], as_=["tipo", "valor"])
        .transform_calculate(center="datum.valor / 2")
        .mark_text(fontSize=16, color="#f3f3f3", align="center", baseline="middle")
        .encode(
            x=alt.X("ano:O", scale=alt.Scale(domain=x_domain)),
            y=alt.Y("center:Q", axis=None),
            text=alt.Text("valor:Q", format=".2f"),
        )
    )

    line_df = pd.DataFrame(line_rows, columns=["ano", "percentual", "serie"])
    max_percentual = 100 if line_df.empty else max(line_df["percentual"].max(), 100)
    line_chart = (
        alt.Chart(line_df)
        .mark_line(point=True)
        .encode(
            x=alt.X(
                "ano:O",
                title=None,
                scale=alt.Scale(domain=x_domain),
                axis=alt.Axis(labelFontSize=12, labelOverlap="greedy", labelAngle=0),
            ),
            y=alt.Y(
                "percentual:Q",
                title=None,
                axis=alt.Axis(orient="right", format=".0f", labels=False, ticks=False),
                scale=alt.Scale(domain=[0, max_percentual]),
            ),
            color=alt.Color(
                "serie:N",
                scale=alt.Scale(
                    domain=["Selecionada", "Viabilidade", "Realizado"],
                    range=["#6a1b9a", "#ff8f00", "#D1DD2D"],
                ),
                legend=alt.Legend(title="Percentual vendido"),
            ),
            tooltip=[
                alt.Tooltip("ano:N", title="Ano"),
                alt.Tooltip("serie:N", title="Serie"),
                alt.Tooltip("percentual:Q", title="% vendido", format=".1f"),
            ],
        )
    )

    line_labels_bg = (
        alt.Chart(line_df)
        .mark_text(fontSize=20, color="#0f1114", opacity=0.6, dy=-10)
        .encode(
            x=alt.X("ano:O", scale=alt.Scale(domain=x_domain)),
            y=alt.Y("percentual:Q", axis=None),
            text=alt.Text("percentual:Q", format=".0f"),
        )
    )

    line_labels = (
        alt.Chart(line_df)
        .mark_text(fontSize=16, color="#eef4ff", dy=-10)
        .encode(
            x=alt.X("ano:O", scale=alt.Scale(domain=x_domain)),
            y=alt.Y("percentual:Q", axis=None),
            text=alt.Text("percentual:Q", format=".0f"),
        )
    )

    st.subheader("Vendas e distratos no tempo")
    st.altair_chart(
        alt.layer(line_chart, line_labels_bg, line_labels)
        .resolve_scale(color="independent")
        .properties(height=260),
        use_container_width=True,
    )
    st.altair_chart(
        alt.layer(bar_chart, bar_labels_bg, bar_labels)
        .resolve_scale(y="independent", color="independent")
        .properties(height=320),
        use_container_width=True,
    )


IMPORT_COLUMNS = ["proj_id", "emp_id", "torre_id", "ano", "mes", "vendas", "distratos"]


def _excel_template() -> bytes | None:
    example = [
        {
            "proj_id": "PROJ-EXEMPLO",
            "emp_id": "EMP-EXEMPLO",
            "torre_id": "TOR-EXEMPLO",
            "ano": 2026,
            "mes": 1,
            "vendas": 2.5,
            "distratos": 0,
        }
    ]
    buffer = io.BytesIO()
    try:
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            pd.DataFrame(example).to_excel(writer, index=False, sheet_name="importacao")
    except ImportError:
        return None
    buffer.seek(0)
    return buffer.read()


def _csv_template() -> str:
    example = [
        {
            "proj_id": "PROJ-EXEMPLO",
            "emp_id": "EMP-EXEMPLO",
            "torre_id": "TOR-EXEMPLO",
            "ano": 2026,
            "mes": 1,
            "vendas": 2.5,
            "distratos": 0,
        }
    ]
    return pd.DataFrame(example).to_csv(index=False)


def _get_or_create_realizado_proj(data: dict) -> str:
    projecoes = data.setdefault("projecoes", {})
    for proj_id, proj_data in projecoes.items():
        if isinstance(proj_data, dict) and proj_data.get("tipo") == "Realizado":
            return proj_id

    proj_id = "PROJ-REALIZADO"
    if proj_id in projecoes:
        proj_id = _generate_proj_id(projecoes, "Realizado")
    proj_data = get_or_create_projection(data, proj_id)
    proj_data["nome"] = "Historico Realizado"
    proj_data["tipo"] = "Realizado"
    return proj_id


def _read_import_file(uploaded_file) -> Tuple[pd.DataFrame | None, list[str]]:
    if uploaded_file is None:
        return None, []

    content = uploaded_file.getvalue()
    if not content:
        return None, ["Arquivo vazio."]

    errors: list[str] = []
    filename = (uploaded_file.name or "").lower()
    try:
        if filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content))
        else:
            df = pd.read_excel(io.BytesIO(content))
    except ImportError:
        return None, ["Dependencia ausente para ler Excel (openpyxl)."]
    except Exception:
        return None, ["Nao foi possivel ler o arquivo."]

    df.columns = [str(col).strip().lower() for col in df.columns]
    missing = [col for col in IMPORT_COLUMNS if col not in df.columns]
    if missing:
        errors.append(f"Colunas obrigatorias ausentes: {', '.join(missing)}.")
        return None, errors

    return df, errors


def _parse_int_value(value: object) -> Tuple[int | None, bool]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None, False
    try:
        number = int(float(str(value).strip().replace(",", ".")))
    except (TypeError, ValueError):
        return None, False
    return number, True


def _parse_optional_number(value: object) -> Tuple[float, bool]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 0.0, True
    if isinstance(value, str) and not value.strip():
        return 0.0, True
    cleaned = str(value).strip().replace(",", ".")
    try:
        number = float(cleaned)
    except (TypeError, ValueError):
        return 0.0, False
    if number < 0:
        number = 0.0
    return number, True


def _resolve_torre_id(emp_data: dict, torre_id: str) -> str | None:
    torres = emp_data.get("torres", {}) if isinstance(emp_data, dict) else {}
    if torre_id in torres:
        return torre_id
    cleaned = torre_id.strip()
    if not cleaned.isdigit():
        return None

    try:
        target = int(cleaned)
    except ValueError:
        return None

    matches = []
    for candidate in torres.keys():
        if not isinstance(candidate, str):
            continue
        candidate_clean = candidate.strip()
        if not candidate_clean.isdigit():
            continue
        try:
            candidate_value = int(candidate_clean)
        except ValueError:
            continue
        if candidate_value == target:
            matches.append(candidate)

    if len(matches) == 1:
        return matches[0]
    return None


def _validate_import_df(
    df: pd.DataFrame,
    data: dict,
    use_csv_proj: bool,
    dest_proj_id: str | None,
) -> Tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    rows: list[dict] = []
    invalid_rows: list[dict] = []
    errors: list[str] = []

    empreendimentos = data.get("empreendimentos", {})
    projecoes = data.get("projecoes", {})

    for idx, raw in df.iterrows():
        row_errors: list[str] = []
        proj_id = _clean_text(raw.get("proj_id", ""))
        emp_id = _clean_text(raw.get("emp_id", ""))
        torre_id = _clean_text(raw.get("torre_id", ""))

        if use_csv_proj:
            if not proj_id:
                row_errors.append("proj_id vazio")
            elif proj_id not in projecoes:
                row_errors.append("proj_id nao encontrado")
        else:
            proj_id = dest_proj_id or ""

        if not emp_id:
            row_errors.append("emp_id vazio")
        elif emp_id not in empreendimentos:
            row_errors.append("emp_id nao encontrado")

        torre_map = {}
        emp_data = None
        if emp_id in empreendimentos:
            emp_data = empreendimentos[emp_id]
            torre_map = emp_data.get("torres", {})
        if not torre_id:
            row_errors.append("torre_id vazio")
        elif torre_id not in torre_map:
            resolved = _resolve_torre_id(emp_data, torre_id) if emp_data else None
            if resolved:
                torre_id = resolved
            else:
                row_errors.append("torre_id nao encontrado")

        ano, ano_ok = _parse_int_value(raw.get("ano"))
        mes, mes_ok = _parse_int_value(raw.get("mes"))
        if not ano_ok:
            row_errors.append("ano invalido")
        elif ano < 1900:
            row_errors.append("ano fora do intervalo")
        if not mes_ok:
            row_errors.append("mes invalido")
        elif mes < 1 or mes > 12:
            row_errors.append("mes fora do intervalo")

        vendas, vendas_ok = _parse_optional_number(raw.get("vendas"))
        distratos, distratos_ok = _parse_optional_number(raw.get("distratos"))
        if not vendas_ok:
            row_errors.append("vendas invalido")
        if not distratos_ok:
            row_errors.append("distratos invalido")

        if row_errors:
            row_number = idx + 2
            errors.append(f"Linha {row_number}: {'; '.join(row_errors)}.")
            invalid_row = raw.to_dict()
            invalid_row["erros"] = "; ".join(row_errors)
            invalid_rows.append(invalid_row)
            continue

        rows.append(
            {
                "proj_id": proj_id,
                "emp_id": emp_id,
                "torre_id": torre_id,
                "ano": ano,
                "mes": mes,
                "vendas": vendas,
                "distratos": distratos,
            }
        )

    return pd.DataFrame(rows), pd.DataFrame(invalid_rows), errors


def _apply_import_rows(
    data: dict,
    rows: pd.DataFrame,
    import_mode: str,
) -> Tuple[int, set[str]]:
    updated = 0
    touched_proj: set[str] = set()
    for _, row in rows.iterrows():
        proj_id = row["proj_id"]
        emp_id = row["emp_id"]
        torre_id = row["torre_id"]
        ano = int(row["ano"])
        mes = int(row["mes"])
        vendas = float(row["vendas"])
        distratos = float(row["distratos"])

        year_data = get_or_create_year(data, proj_id, emp_id, torre_id, ano)
        year_data["usar_mensal"] = True
        month_key = str(mes)
        current = year_data["mensal"].get(month_key, {"vendas": 0, "distratos": 0})

        if import_mode == "Somar":
            year_data["mensal"][month_key]["vendas"] = _to_number(current.get("vendas", 0)) + vendas
            year_data["mensal"][month_key]["distratos"] = _to_number(
                current.get("distratos", 0)
            ) + distratos
        else:
            year_data["mensal"][month_key]["vendas"] = vendas
            year_data["mensal"][month_key]["distratos"] = distratos

        torre_total = _to_int(
            get_or_create_torre(data, emp_id, torre_id).get("total_unidades", 0)
        )
        if year_data.get("estoque_inicial") is None:
            year_data["estoque_inicial"] = torre_total
        _recalc_monthly_fields(year_data, torre_total)

        touched_proj.add(proj_id)
        updated += 1

    return updated, touched_proj


def _render_import_section(data: dict) -> None:
    st.write(
        "Use uma linha por mes com as colunas: proj_id, emp_id, torre_id, ano, mes, vendas, distratos."
    )
    template_bytes = _excel_template()
    if template_bytes is None:
        st.warning("Instale openpyxl para baixar o modelo Excel.")
    else:
        st.download_button(
            "Baixar modelo Excel",
            data=template_bytes,
            file_name="modelo_importacao_mensal.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    st.download_button(
        "Baixar modelo CSV",
        data=_csv_template(),
        file_name="modelo_importacao_mensal.csv",
        mime="text/csv",
    )

    destino = st.radio(
        "Destino dos dados",
        options=["Projecoes (proj_id do CSV)", "Historico realizado"],
        horizontal=True,
    )
    import_mode = st.radio(
        "Modo de importacao",
        options=["Substituir", "Somar"],
        horizontal=True,
    )
    uploaded_file = st.file_uploader("Arquivo Excel/CSV", type=["xlsx", "xls", "csv"])

    if uploaded_file:
        df, load_errors = _read_import_file(uploaded_file)
        if load_errors:
            for error in load_errors:
                st.error(error)
        elif df is not None:
            use_csv_proj = destino.startswith("Projecoes")
            dest_proj_id = None
            if not use_csv_proj:
                dest_proj_id = _get_or_create_realizado_proj(data)
                st.caption(f"Destino: {dest_proj_id}")

            valid_df, invalid_df, errors = _validate_import_df(
                df, data, use_csv_proj, dest_proj_id
            )

            if errors:
                st.error("Foram encontrados erros no CSV:")
                st.write(errors)
            if not invalid_df.empty:
                st.dataframe(invalid_df, use_container_width=True)

            if not valid_df.empty:
                st.dataframe(valid_df.head(50), use_container_width=True)
                if st.button("Importar dados"):
                    updated, touched = _apply_import_rows(data, valid_df, import_mode)
                    for proj_id in touched:
                        touched_proj = get_or_create_projection(data, proj_id)
                        touched_proj["updated_at"] = dt.date.today().isoformat()
                    _save_data(data)
                    st.success(f"{updated} linhas importadas.")
                    st.rerun()


def _close_import_modal() -> None:
    st.session_state["show_import_modal"] = False


@st.dialog("Importar Excel/CSV mensal", on_dismiss=_close_import_modal)
def _open_import_dialog(data: dict) -> None:
    _render_import_section(data)


def _calc_current_stock_from_relacao(relacao: dict, base_estoque: float) -> float:
    if not isinstance(relacao, dict):
        return float(base_estoque)
    anos = relacao.get("anos", {})
    if not isinstance(anos, dict) or not anos:
        return float(base_estoque)
    total_vendas = 0.0
    total_distratos = 0.0
    for year_data in anos.values():
        if not isinstance(year_data, dict):
            continue
        vendas_total, distratos_total = _calc_annual_totals(year_data)
        total_vendas += vendas_total
        total_distratos += distratos_total
    estoque = float(base_estoque) + total_distratos - total_vendas
    return float(estoque)


def _reset_projection_torre(
    data: dict,
    proj_id: str,
    emp_id: str,
    torre_id: str,
    realized_proj_id: str,
) -> None:
    torre_total = _to_int(get_or_create_torre(data, emp_id, torre_id).get("total_unidades", 0))
    realized_rel = (
        data.get("relacoes", {})
        .get(realized_proj_id, {})
        .get(emp_id, {})
        .get(torre_id, {})
    )
    estoque_atual = _calc_current_stock_from_relacao(realized_rel, torre_total)

    relacao = get_or_create_relacao(data, proj_id, emp_id, torre_id)
    relacao["anos"] = {}
    current_year = _today_year()
    year_data = get_or_create_year(data, proj_id, emp_id, torre_id, current_year)
    year_data["estoque_inicial"] = estoque_atual
    year_data["estoque_inicial_origem"] = "realizado"


def _reset_projection_to_realizado(
    data: dict,
    proj_id: str,
    emp_id: str,
    torre_id: str | None,
    is_aggregate: bool,
    emp_data: dict,
) -> Tuple[bool, str]:
    realized_proj_id = _get_or_create_realizado_proj(data)
    if is_aggregate:
        torres = emp_data.get("torres", {}) if isinstance(emp_data, dict) else {}
        valid_torres = [
            torre_key
            for torre_key in torres.keys()
            if isinstance(torre_key, str) and torre_key and torre_key != "null"
        ]
        if not valid_torres:
            return False, "Empreendimento sem torres validas."
        for torre_key in valid_torres:
            _reset_projection_torre(data, proj_id, emp_id, torre_key, realized_proj_id)
        return True, f"{len(valid_torres)} torres resetadas."

    if not torre_id:
        return False, "Torre nao selecionada."
    _reset_projection_torre(data, proj_id, emp_id, torre_id, realized_proj_id)
    return True, "Projecao resetada."


def main() -> None:

    _inject_metric_styles()
    data = _ensure_data()
    data.setdefault("empreendimentos", {})
    data.setdefault("projecoes", {})
    data.setdefault("relacoes", {})

    if not st.session_state.get("monthly_recalc_done"):
        if _recompute_all_monthly_fields(data):
            _save_data(data)
        st.session_state["monthly_recalc_done"] = True

    proj_id, emp_id, torre_id, is_aggregate = _render_sidebar(data)
    if not proj_id or not emp_id:
        st.info("Crie uma projecao e um empreendimento para iniciar.")
        return
    if not torre_id and not is_aggregate:
        st.info("Crie ou selecione uma torre para iniciar.")
        return

    key_prefix = _key_prefix(proj_id, emp_id, torre_id)

    proj_data = get_or_create_projection(data, proj_id)
    emp_data = get_or_create_empreendimento(data, emp_id)

    proj_label = proj_data.get("nome") or proj_id
    emp_label = emp_data.get("nome") or emp_id

    if is_aggregate:
        st.header(f"{proj_label} - {emp_label} (todas as torres)")
    else:
        torre_data = get_or_create_torre(data, emp_id, torre_id)
        torre_label = torre_data.get("nome") or torre_id
        st.header(f"{proj_label} - {emp_label} - {torre_label}")

    updated_at = proj_data.get("updated_at") or "-"
    st.caption(f"Ultima atualizacao: {updated_at}")

    if st.session_state.pop("request_reset_projection", False):
        ok, message = _reset_projection_to_realizado(
            data,
            proj_id,
            emp_id,
            torre_id,
            is_aggregate,
            emp_data,
        )
        if ok:
            key_prefix = _key_prefix(proj_id, emp_id, torre_id)
            for key in list(st.session_state.keys()):
                if key.startswith(f"{key_prefix}_vendas_anuais_") or key.startswith(
                    f"{key_prefix}_distratos_anuais_"
                ):
                    st.session_state.pop(key, None)
            proj_data["updated_at"] = dt.date.today().isoformat()
            _save_data(data)
            st.success(message)
            st.rerun()
        else:
            st.error(message)

    if st.session_state.get("show_import_modal"):
        _open_import_dialog(data)

    if not is_aggregate:
        relacao = get_or_create_relacao(data, proj_id, emp_id, torre_id)
        base_year = _resolve_base_year(relacao.get("anos", {}))
    else:
        relacoes = _filtered_relacoes(data, proj_id, emp_id, emp_data)
        base_years = [_resolve_base_year(rel.get("anos", {})) for rel in relacoes.values()]
        base_year = min(base_years) if base_years else _today_year()

    years = _year_range(base_year, 7)

    if not is_aggregate:
        year_data_map = {
            year: get_or_create_year(data, proj_id, emp_id, torre_id, year)
            for year in years
        }
        base_data = year_data_map[base_year]
        context_key = _key_prefix("ctx", proj_id, emp_id, torre_id)
        if st.session_state.get("last_context") != context_key:
            st.session_state["last_context"] = context_key
            _seed_year_state(key_prefix, years, base_year, base_data, year_data_map)
    else:
        year_data_map = {}
        base_data = None

    cols = st.columns(len(years), gap="small")

    year_summaries: dict[int, dict] = {}
    if is_aggregate:
        relacoes = _filtered_relacoes(data, proj_id, emp_id, emp_data)
        if not relacoes:
            st.info("Sem dados desta projecao para este empreendimento.")
        base_estoque_inicial = 0.0
        for torre_id, torre_rel in relacoes.items():
            year_data = torre_rel.get("anos", {}).get(str(base_year))
            if not isinstance(year_data, dict):
                year_data = get_or_create_year(data, proj_id, emp_id, torre_id, base_year)
            base_estoque_inicial += _to_number(year_data.get("estoque_inicial", 0))
        prev_final = base_estoque_inicial
        for index, year in enumerate(years):
            total_vendas = 0
            total_distratos = 0
            for torre_rel in relacoes.values():
                year_data = torre_rel.get("anos", {}).get(str(year))
                if not isinstance(year_data, dict):
                    continue
                vendas_total, distratos_total = _calc_annual_totals(year_data)
                total_vendas += vendas_total
                total_distratos += distratos_total

            estoque_inicial = base_estoque_inicial if year == base_year else prev_final
            estoque_final = estoque_inicial - total_vendas + total_distratos
            label_vendas = "Vendas anuais" if year == base_year else "Vendas"
            label_distratos = "Distratos anuais" if year == base_year else "Distratos"

            with cols[index]:
                st.markdown(f"**{year}**")
                _render_stock_metric("Estoque inicial", estoque_inicial)
                _render_stock_metric(label_vendas, total_vendas)
                _render_stock_metric(label_distratos, total_distratos)
                _render_stock_metric("Estoque final", estoque_final)

            year_summaries[year] = {
                "estoque_inicial": estoque_inicial,
                "vendas": total_vendas,
                "distratos": total_distratos,
                "estoque_final": estoque_final,
            }
            prev_final = estoque_final
    else:
        torre_total_unidades = _to_int(
            get_or_create_torre(data, emp_id, torre_id).get("total_unidades", 0)
        )
        if base_data.get("estoque_inicial_origem") != "realizado" and base_data.get(
            "estoque_inicial"
        ) != torre_total_unidades:
            base_data["estoque_inicial"] = torre_total_unidades
            _mark_dirty_projection()
        with cols[0]:
            st.markdown(f"**{base_year}**")
            _render_stock_metric("Estoque inicial", _to_number(base_data.get("estoque_inicial", 0)))

            base_data["vendas_anuais"] = _number_input_stateful(
                "Vendas anuais",
                min_value=0.0,
                step=0.1,
                value=_to_number(base_data.get("vendas_anuais", 0)),
                format="%.2f",
                key=f"{key_prefix}_vendas_anuais_{base_year}",
                disabled=base_data["usar_mensal"],
                on_change=_mark_dirty_projection,
            )
            base_data["distratos_anuais"] = _number_input_stateful(
                "Distratos anuais",
                min_value=0.0,
                step=0.1,
                value=_to_number(base_data.get("distratos_anuais", 0)),
                format="%.2f",
                key=f"{key_prefix}_distratos_anuais_{base_year}",
                disabled=base_data["usar_mensal"],
                on_change=_mark_dirty_projection,
            )

        base_vendas, base_distratos = _calc_annual_totals(base_data)
        base_estoque_inicial = _to_number(base_data.get("estoque_inicial", 0))
        base_estoque_final = base_estoque_inicial - base_vendas + base_distratos

        with cols[0]:
            _render_stock_metric("Estoque final", base_estoque_final)

        year_summaries[base_year] = {
            "estoque_inicial": base_estoque_inicial,
            "vendas": base_vendas,
            "distratos": base_distratos,
            "estoque_final": base_estoque_final,
        }

        prev_final = base_estoque_final
        for index, year in enumerate(years[1:], start=1):
            year_data = year_data_map[year]
            estoque_inicial = prev_final

            with cols[index]:
                st.markdown(f"**{year}**")
                _render_stock_metric("Estoque inicial", estoque_inicial)
                year_data["vendas_anuais"] = _number_input_stateful(
                    "Vendas",
                    min_value=0.0,
                    step=0.1,
                    value=_to_number(year_data.get("vendas_anuais", 0)),
                    format="%.2f",
                    key=f"{key_prefix}_vendas_anuais_{year}",
                    on_change=_mark_dirty_projection,
                )
                year_data["distratos_anuais"] = _number_input_stateful(
                    "Distratos",
                    min_value=0.0,
                    step=0.1,
                    value=_to_number(year_data.get("distratos_anuais", 0)),
                    format="%.2f",
                    key=f"{key_prefix}_distratos_anuais_{year}",
                    on_change=_mark_dirty_projection,
                )

                vendas_total, distratos_total = _calc_annual_totals(year_data)
                estoque_final = estoque_inicial - vendas_total + distratos_total
                _render_stock_metric("Estoque final", estoque_final)

            year_summaries[year] = {
                "estoque_inicial": estoque_inicial,
                "vendas": vendas_total,
                "distratos": distratos_total,
                "estoque_final": estoque_final,
            }

            prev_final = estoque_final

    st.divider()
    _render_sales_mix_chart(
        year_summaries,
        data,
        proj_id,
        emp_id,
        torre_id,
        is_aggregate,
        emp_data,
    )

    save_allowed = True
    if not is_aggregate and base_data:

        if base_data.get("usar_mensal"):
            estoque_mensal = _calc_monthly_stock(base_data)
            negativo_mensal = any(valor < 0 for valor in estoque_mensal)
        else:
            negativo_mensal = False

        negative_years = [
            year for year, summary in year_summaries.items() if summary["estoque_final"] < 0
        ]
        if negative_years:
            years_text = ", ".join(str(year) for year in negative_years)
            st.error(f"Estoque final negativo nos anos: {years_text}.")
        if base_estoque_final < 0:
            st.error("Estoque final negativo no ano base.")
        if base_data.get("usar_mensal") and negativo_mensal:
            st.error("Estoque negativo em pelo menos um mes do ano base.")

        current_tipo = proj_data.get("tipo", "Comitê")
        if current_tipo == "Comite":
            current_tipo = "Comitê"
        proj_data["tipo"] = st.selectbox(
            "Tipo de projecao",
            options=PROJECTION_TYPES,
            index=PROJECTION_TYPES.index(current_tipo) if current_tipo in PROJECTION_TYPES else 0,
            on_change=_mark_dirty_projection,
        )

        valid = (
            base_estoque_final >= 0
            and (not base_data.get("usar_mensal") or not negativo_mensal)
            and not negative_years
        )
        save_allowed = valid
        if not valid and st.session_state.get("dirty"):
            st.caption("Alteracoes pendentes: estoque final negativo.")

        action_col1, = st.columns(1)
        if action_col1.button("Salvar"):
            if valid:
                for year in years[1:]:
                    year_data = year_data_map[year]
                    year_data["estoque_inicial"] = _to_int(
                        year_summaries[year]["estoque_inicial"]
                    )
                proj_data["updated_at"] = dt.date.today().isoformat()
                _save_data(data)
                st.success("Dados salvos.")
            else:
                st.error("Ajuste os dados antes de salvar.")

    if st.session_state.pop("dirty", False):
        dirty_scope = st.session_state.pop("dirty_scope", None)
        if dirty_scope == "projection" and not save_allowed:
            st.warning("Alteracoes nao foram salvas: estoque final negativo.")
        else:
            if dirty_scope == "projection" and proj_data:
                proj_data["updated_at"] = dt.date.today().isoformat()
            _save_data(data)

    st.divider()
    _render_stock_timeline(year_summaries)


if __name__ == "__main__":
    main()
