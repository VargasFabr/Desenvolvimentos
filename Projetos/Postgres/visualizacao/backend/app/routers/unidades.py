from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request

from app.db import get_conn, get_cursor
from app.filter_utils import (
    UNIDADE_FILTER_COLS,
    append_eq_filters,
    fetch_distinct_opcoes,
    filters_from_query,
)
from app.schemas import UnidadeCreate, UnidadeUpdate
from lib.otto_unidades import preview_otto_sync, sync_otto_units
from lib.cad_parsers import codigo_interno
from lib.unidade_parsers import UnidadeImportRow
from lib.unidade_service import resolve_torre, upsert_unidade_row

router = APIRouter(prefix="/api/unidades", tags=["unidades"])

_UNIDADE_ALLOWED = frozenset(UNIDADE_FILTER_COLS)


def _resolve_torre_id(body: UnidadeCreate, cur) -> tuple[str, str]:
    if body.id_torre:
        cur.execute(
            "SELECT id, id_empreendimento FROM cad.torres WHERE id = %s",
            (str(body.id_torre),),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Torre não encontrada")
        return str(row["id"]), str(row["id_empreendimento"])
    if body.codigo_interno:
        torre = resolve_torre(cur, body.codigo_interno.strip())
    elif body.cod_spe and body.cod_torre:
        ci = codigo_interno(body.cod_spe.strip(), body.cod_torre.strip(), body.numero_fase)
        torre = resolve_torre(cur, ci)
    else:
        raise HTTPException(400, "Informe id_torre, codigo_interno ou SPE+cod_torre+fase")
    if not torre:
        raise HTTPException(404, "Torre não encontrada")
    return torre


@router.get("/filtros/opcoes")
def unidades_filtros_opcoes():
    with get_cursor() as (_, cur):
        return fetch_distinct_opcoes(cur, "public.v_unidades_completas", UNIDADE_FILTER_COLS, limit=5000)


@router.get("")
def list_unidades(
    request: Request,
    q: str | None = Query(None),
    limit: int = Query(50000, le=50000),
    offset: int = Query(0, ge=0),
):
    sql = "SELECT * FROM public.v_unidades_completas WHERE 1=1"
    params: list = []
    filters = filters_from_query(request.query_params, _UNIDADE_ALLOWED)
    sql, params = append_eq_filters(sql, params, filters, _UNIDADE_ALLOWED)
    if q:
        sql += " AND (nome ILIKE %s OR id_gc ILIKE %s OR codigo_interno ILIKE %s OR codigo_unidade ILIKE %s)"
        params.extend([f"%{q}%"] * 4)
    sql += " ORDER BY cod_spe, codigo_interno, nome LIMIT %s OFFSET %s"
    params.extend([limit, offset])
    with get_cursor() as (_, cur):
        cur.execute(sql, params)
        return cur.fetchall()


@router.get("/sync/otto/preview")
def otto_sync_preview(spe: str | None = Query(None, description="Filtrar por SPE (ex. 8190)")):
    try:
        with get_conn() as conn:
            stats = preview_otto_sync(conn, spe)
    except RuntimeError as e:
        raise HTTPException(503, str(e)) from e
    return {
        "total_otto": stats.total_otto,
        "mapeadas": stats.mapeadas,
        "sem_torre_cad": stats.sem_torre,
        "parse_erro": stats.parse_erro,
    }


@router.post("/sync/otto")
def otto_sync_confirm(spe: str | None = Query(None, description="Filtrar por SPE (ex. 8190)")):
    try:
        with get_conn() as conn:
            stats = sync_otto_units(conn, spe)
    except RuntimeError as e:
        raise HTTPException(503, str(e)) from e
    return {
        "total_otto": stats.total_otto,
        "importados": stats.importados,
        "sem_torre_cad": stats.sem_torre,
        "parse_erro": stats.parse_erro,
    }


@router.post("", status_code=201)
def create_unidade(body: UnidadeCreate):
    with get_cursor() as (conn, cur):
        id_torre, id_emp = _resolve_torre_id(body, cur)
        item = UnidadeImportRow(
            linha=0,
            spe=body.cod_spe or "",
            cod_torre=body.cod_torre or "",
            fase=body.numero_fase,
            codigo_interno_torre=body.codigo_interno or "",
            nome=body.nome.strip(),
            andar=body.andar,
            area_privativa=body.area_privativa,
            fracao_ideal=body.fracao_ideal,
            tipo=body.tipo,
            dormitorios=body.dormitorios,
            vagas=body.vagas,
            id_gc=body.id_gc,
        )
        uid = upsert_unidade_row(cur, item, id_torre, id_emp)
        conn.commit()
    return get_unidade(UUID(uid))


@router.get("/{unidade_id}")
def get_unidade(unidade_id: UUID):
    with get_cursor() as (_, cur):
        cur.execute(
            "SELECT * FROM public.v_unidades_completas WHERE id_unidade = %s",
            (str(unidade_id),),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Unidade não encontrada")
    return row


@router.put("/{unidade_id}")
def update_unidade(unidade_id: UUID, body: UnidadeUpdate):
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        return get_unidade(unidade_id)
    sets = ", ".join(f"{k} = %s" for k in fields)
    with get_cursor() as (conn, cur):
        cur.execute(
            f"UPDATE cad.unidades SET {sets}, atualizado_em = now() WHERE id = %s",
            [*fields.values(), str(unidade_id)],
        )
        if cur.rowcount == 0:
            raise HTTPException(404, "Unidade não encontrada")
        conn.commit()
    return get_unidade(unidade_id)
