from __future__ import annotations



from uuid import UUID



from fastapi import APIRouter, HTTPException, Query, Request



from app.db import get_cursor

from app.filter_utils import (

    TORRE_FILTER_COLS,

    append_eq_filters,

    fetch_distinct_opcoes,

    filters_from_query,

)

from app.schemas import TorreCreate, TorreUpdate

from lib.cad_parsers import TorreImportRow, codigo_interno

from lib.cad_service import upsert_torre_row



router = APIRouter(prefix="/api/torres", tags=["torres"])



_TORRE_ALLOWED = frozenset(TORRE_FILTER_COLS)





def _torre_to_import(body: TorreCreate) -> TorreImportRow:

    spe = body.cod_spe.strip()

    cod_torre = body.cod_torre.strip()

    fase = body.numero_fase

    return TorreImportRow(

        linha=0,

        empreendimento=(body.nome_comercial or spe).strip(),

        spe=spe,

        torre=body.nome_torre,

        cod_torre=cod_torre,

        fase=fase,

        codigo_interno=codigo_interno(spe, cod_torre, fase),

        segmento=body.segmento,

        estagio=body.estagio,

        tipo_empresa=body.tipo_empresa,

        principal=body.principal,

        permutante=body.permutante,

        lancamento=body.lancamento,

        entrega=body.entrega,

        vgv_bruto=body.vgv_bruto,

        vgv_liquido=body.vgv_liquido,

        unidades_total=body.unidades_total,

        id_orulo=body.id_orulo,

        logradouro=body.logradouro,

        numero=body.numero,

        bairro=body.bairro,

        cidade=body.cidade,

        cep=body.cep,

        latitude=body.latitude,

        longitude=body.longitude,

    )





@router.get("/filtros/opcoes")

def torres_filtros_opcoes():

    with get_cursor() as (_, cur):

        return fetch_distinct_opcoes(cur, "public.v_torres_completas", TORRE_FILTER_COLS)





@router.get("")

def list_torres(

    request: Request,

    q: str | None = Query(None),

    limit: int = Query(500, le=2000),

    offset: int = Query(0, ge=0),

):

    sql = "SELECT * FROM public.v_torres_completas WHERE 1=1"

    params: list = []

    filters = filters_from_query(request.query_params, _TORRE_ALLOWED)

    sql, params = append_eq_filters(sql, params, filters, _TORRE_ALLOWED)

    if q:

        sql += " AND (nome_comercial ILIKE %s OR nome_torre ILIKE %s OR codigo_interno ILIKE %s)"

        params.extend([f"%{q}%"] * 3)

    sql += " ORDER BY nome_comercial, cod_torre LIMIT %s OFFSET %s"

    params.extend([limit, offset])

    with get_cursor() as (_, cur):

        cur.execute(sql, params)

        return cur.fetchall()





@router.post("", status_code=201)

def create_torre(body: TorreCreate):

    item = _torre_to_import(body)

    with get_cursor() as (conn, cur):

        torre_id = upsert_torre_row(cur, item, fonte="manual")

        conn.commit()

    return get_torre(UUID(torre_id))





@router.get("/{torre_id}")

def get_torre(torre_id: UUID):

    with get_cursor() as (_, cur):

        cur.execute(

            "SELECT * FROM public.v_torres_completas WHERE id_torre = %s",

            (str(torre_id),),

        )

        r = cur.fetchone()

    if not r:

        raise HTTPException(404, "Torre não encontrada")

    return r





@router.put("/{torre_id}")

def update_torre(torre_id: UUID, body: TorreUpdate):

    fields = body.model_dump(exclude_unset=True)

    if not fields:

        return get_torre(torre_id)

    sets = ", ".join(f"{k} = %s" for k in fields)

    with get_cursor() as (conn, cur):

        cur.execute(

            f"UPDATE cad.torres SET {sets}, atualizado_em = now() WHERE id = %s",

            [*fields.values(), str(torre_id)],

        )

        if cur.rowcount == 0:

            raise HTTPException(404, "Torre não encontrada")

        conn.commit()

    return get_torre(torre_id)





@router.get("/{torre_id}/unidades")

def list_unidades_torre(torre_id: UUID):

    with get_cursor() as (_, cur):

        cur.execute(

            "SELECT * FROM public.v_unidades_completas WHERE id_torre = %s ORDER BY nome",

            (str(torre_id),),

        )

        return cur.fetchall()


