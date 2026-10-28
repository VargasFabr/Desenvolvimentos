from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Tuple

from projection_models import AnnualTotals, MonthlyPoint


def _safe_month_key(data_value: str) -> Tuple[str, str] | None:
    if not isinstance(data_value, str):
        return None
    parts = data_value.split("-")
    if len(parts) != 2:
        return None
    year, month = parts
    if not year.isdigit() or not month.isdigit():
        return None
    if len(month) != 2:
        month = month.zfill(2)
    return year, month


def _month_has_activity(month_data: dict) -> bool:
    vendas = float(month_data.get("vendas", 0) or 0)
    distratos = float(month_data.get("distratos", 0) or 0)
    return abs(vendas) > 0 or abs(distratos) > 0


def build_indice_data(serie: Iterable[MonthlyPoint]) -> Dict[str, int]:
    ordered = sorted(serie, key=lambda entry: entry.data)
    return {entry.data: idx for idx, entry in enumerate(ordered)}


def build_annuals_from_series(serie: Iterable[MonthlyPoint]) -> Dict[str, AnnualTotals]:
    grouped: Dict[str, List[MonthlyPoint]] = defaultdict(list)
    for entry in serie:
        parsed = _safe_month_key(entry.data)
        if not parsed:
            continue
        year, _ = parsed
        grouped[year].append(entry)

    annuals: Dict[str, AnnualTotals] = {}
    for year, points in grouped.items():
        points_sorted = sorted(points, key=lambda entry: entry.data)
        vendas_total = sum(entry.vendas for entry in points_sorted)
        distratos_total = sum(entry.distratos for entry in points_sorted)
        estoque_inicial = points_sorted[0].estoque_inicial if points_sorted else 0.0
        annuals[year] = AnnualTotals(
            vendas=vendas_total,
            distratos=distratos_total,
            estoque_inicial=estoque_inicial,
        )
    return annuals


def series_to_year_map(
    serie: Iterable[MonthlyPoint],
    annuals: Dict[str, AnnualTotals] | None = None,
) -> Dict[str, dict]:
    grouped: Dict[str, List[MonthlyPoint]] = defaultdict(list)
    for entry in serie:
        parsed = _safe_month_key(entry.data)
        if not parsed:
            continue
        year, month = parsed
        grouped[year].append(entry)

    years_map: Dict[str, dict] = {}
    for year, points in grouped.items():
        year_data = {
            "estoque_inicial": 0.0,
            "estoque_inicial_origem": None,
            "vendas_anuais": 0.0,
            "distratos_anuais": 0.0,
            "usar_mensal": True,
            "mensal": {
                str(month): {
                    "vendas": 0.0,
                    "distratos": 0.0,
                    "estoque_inicial": None,
                    "estoque_final": None,
                }
                for month in range(1, 13)
            },
        }
        points_sorted = sorted(points, key=lambda entry: entry.data)
        if points_sorted:
            year_data["estoque_inicial"] = points_sorted[0].estoque_inicial
            year_data["estoque_inicial_origem"] = points_sorted[0].origem_estoque_inicial
        for entry in points_sorted:
            parsed = _safe_month_key(entry.data)
            if not parsed:
                continue
            _, month = parsed
            month_key = str(int(month))
            year_data["mensal"][month_key]["vendas"] = entry.vendas
            year_data["mensal"][month_key]["distratos"] = entry.distratos
            year_data["mensal"][month_key]["estoque_inicial"] = entry.estoque_inicial
        if annuals and year in annuals:
            year_data["vendas_anuais"] = annuals[year].vendas
            year_data["distratos_anuais"] = annuals[year].distratos
            year_data["estoque_inicial"] = annuals[year].estoque_inicial
        else:
            year_data["vendas_anuais"] = sum(entry.vendas for entry in points_sorted)
            year_data["distratos_anuais"] = sum(entry.distratos for entry in points_sorted)
        years_map[year] = year_data

    if annuals:
        for year, totals in annuals.items():
            if year in years_map:
                continue
            years_map[year] = {
                "estoque_inicial": totals.estoque_inicial,
                "estoque_inicial_origem": None,
                "vendas_anuais": totals.vendas,
                "distratos_anuais": totals.distratos,
                "usar_mensal": False,
                "mensal": {
                    str(month): {
                        "vendas": 0.0,
                        "distratos": 0.0,
                        "estoque_inicial": None,
                        "estoque_final": None,
                    }
                    for month in range(1, 13)
                },
            }
    return years_map


def year_map_to_series_and_annuals(anos: Dict[str, dict]) -> Tuple[List[MonthlyPoint], Dict[str, AnnualTotals]]:
    serie: List[MonthlyPoint] = []
    annuals: Dict[str, AnnualTotals] = {}

    for year_key, year_data in anos.items():
        if not isinstance(year_data, dict):
            continue
        year = str(year_key)
        usar_mensal = bool(year_data.get("usar_mensal"))
        vendas_total = 0.0
        distratos_total = 0.0

        mensal = year_data.get("mensal", {}) if isinstance(year_data.get("mensal"), dict) else {}
        for month in range(1, 13):
            month_key = str(month)
            month_data = mensal.get(month_key, {}) if isinstance(mensal, dict) else {}
            vendas = float(month_data.get("vendas", 0) or 0)
            distratos = float(month_data.get("distratos", 0) or 0)
            vendas_total += vendas
            distratos_total += distratos

            include_month = usar_mensal or _month_has_activity(month_data)
            if not include_month:
                continue

            estoque_inicial = month_data.get("estoque_inicial")
            if estoque_inicial is None and month == 1:
                estoque_inicial = float(year_data.get("estoque_inicial", 0) or 0)
            origem = None
            if month == 1:
                origem = year_data.get("estoque_inicial_origem")
            serie.append(
                MonthlyPoint(
                    data=f"{year}-{month:02d}",
                    vendas=vendas,
                    distratos=distratos,
                    estoque_inicial=float(estoque_inicial or 0),
                    origem_estoque_inicial=origem,
                )
            )

        if not usar_mensal:
            vendas_total = float(year_data.get("vendas_anuais", 0) or 0)
            distratos_total = float(year_data.get("distratos_anuais", 0) or 0)

        annuals[year] = AnnualTotals(
            vendas=vendas_total,
            distratos=distratos_total,
            estoque_inicial=float(year_data.get("estoque_inicial", 0) or 0),
        )

    serie_sorted = sorted(serie, key=lambda entry: entry.data)
    return serie_sorted, annuals
