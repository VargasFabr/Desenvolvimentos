"""Distinct values e filtros por coluna (whitelist)."""
from __future__ import annotations

BOOL_COLS = frozenset({"principal", "permutante"})

EMP_FILTER_COLS = [
    "cod_spe",
    "nome_comercial",
    "cidade",
    "uf",
    "nome_incorporadora",
    "endereco_bairro",
    "endereco_logradouro",
    "empresa_parceira",
    "qtd_fases",
    "qtd_torres",
    "qtd_torres_principais",
    "qtd_torres_vaga",
]

TORRE_FILTER_COLS = [
    "cod_spe",
    "codigo_interno",
    "cod_torre",
    "nome_comercial",
    "nome_torre",
    "segmento",
    "estagio",
    "tipo_empresa",
    "cidade",
    "uf",
    "nome_incorporadora",
    "numero_fase",
    "principal",
    "permutante",
    "endereco_bairro",
    "empresa_parceira",
    "nome_fase",
]

UNIDADE_FILTER_COLS = [
    "cod_spe",
    "codigo_interno",
    "codigo_unidade",
    "cod_torre",
    "nome_comercial",
    "nome_torre",
    "nome",
    "andar",
    "tipo",
    "numero_fase",
    "dormitorios",
    "vagas",
    "id_gc",
]


def fetch_distinct_opcoes(cur, view: str, columns: list[str], limit: int = 500) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for col in columns:
        if col in BOOL_COLS:
            out[col] = ["true", "false"]
            continue
        cur.execute(
            f"SELECT DISTINCT {col}::text AS v FROM {view} "
            f"WHERE {col} IS NOT NULL AND btrim({col}::text) <> '' "
            f"ORDER BY 1 LIMIT %s",
            (limit,),
        )
        out[col] = [r["v"] for r in cur.fetchall()]
    return out


def append_eq_filters(
    sql: str,
    params: list,
    filters: dict[str, str],
    allowed: frozenset[str] | set[str],
    bool_cols: frozenset[str] = BOOL_COLS,
) -> tuple[str, list]:
    for col, val in filters.items():
        if not val or col not in allowed:
            continue
        if col in bool_cols:
            sql += f" AND {col} = %s"
            params.append(val.lower() == "true")
        else:
            sql += f" AND {col}::text = %s"
            params.append(val)
    return sql, params


def filters_from_query(query_params, allowed: frozenset[str] | set[str]) -> dict[str, str]:
    skip = {"limit", "offset", "q"}
    return {
        k: v
        for k, v in query_params.items()
        if k in allowed and k not in skip and v is not None and str(v).strip() != ""
    }
