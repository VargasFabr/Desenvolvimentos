from __future__ import annotations



from uuid import UUID



from fastapi import APIRouter, HTTPException, Query, Request



from app.db import get_cursor

from app.filter_utils import (

    EMP_FILTER_COLS,

    append_eq_filters,

    fetch_distinct_opcoes,

    filters_from_query,

)

from app.schemas import (

    EmpreendimentoCreate,

    EmpreendimentoUpdate,

    FaseOut,

)

from lib.cad_parsers import MELNICK_INCORPORADORA_ID, uid

from lib.cad_service import _ensure_cidade



router = APIRouter(prefix="/api/empreendimentos", tags=["empreendimentos"])



_EMP_ALLOWED = frozenset(EMP_FILTER_COLS)





@router.get("/filtros/opcoes")

def empreendimentos_filtros_opcoes():

    with get_cursor() as (_, cur):

        return fetch_distinct_opcoes(cur, "public.v_empreendimentos_listagem", EMP_FILTER_COLS)





@router.get("")

def list_empreendimentos(

    request: Request,

    q: str | None = Query(None),

    limit: int = Query(500, le=2000),

    offset: int = Query(0, ge=0),

):

    sql = "SELECT * FROM public.v_empreendimentos_listagem WHERE 1=1"

    params: list = []

    filters = filters_from_query(request.query_params, _EMP_ALLOWED)

    sql, params = append_eq_filters(sql, params, filters, _EMP_ALLOWED)

    if q:

        sql += " AND (cod_spe ILIKE %s OR nome_comercial ILIKE %s)"

        params.extend([f"%{q}%", f"%{q}%"])

    sql += " ORDER BY nome_comercial LIMIT %s OFFSET %s"

    params.extend([limit, offset])

    with get_cursor() as (_, cur):

        cur.execute(sql, params)

        return cur.fetchall()





@router.post("", status_code=201)

def create_empreendimento(body: EmpreendimentoCreate):

    emp_id = uid("empreendimento", body.cod_spe.strip())

    with get_cursor() as (conn, cur):

        id_cidade = _ensure_cidade(cur, body.cidade)

        cur.execute(

            """

            INSERT INTO cad.empreendimentos (

                id, cod_spe, nome_comercial, id_incorporadora, id_cidade,

                endereco_logradouro, endereco_numero, endereco_bairro, endereco_cep,

                latitude, longitude

            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)

            RETURNING id

            """,

            (

                emp_id,

                body.cod_spe.strip(),

                body.nome_comercial.strip(),

                MELNICK_INCORPORADORA_ID,

                id_cidade,

                body.endereco_logradouro,

                body.endereco_numero,

                body.endereco_bairro,

                body.endereco_cep,

                body.latitude,

                body.longitude,

            ),

        )

        conn.commit()

    return get_empreendimento(UUID(emp_id))





@router.get("/{emp_id}")

def get_empreendimento(emp_id: UUID):

    with get_cursor() as (_, cur):

        cur.execute(

            "SELECT * FROM public.v_empreendimentos_listagem WHERE id_empreendimento = %s",

            (str(emp_id),),

        )

        row = cur.fetchone()

    if not row:

        raise HTTPException(404, "Empreendimento não encontrado")

    return row





@router.put("/{emp_id}")

def update_empreendimento(emp_id: UUID, body: EmpreendimentoUpdate):

    with get_cursor() as (conn, cur):

        id_cidade = _ensure_cidade(cur, body.cidade) if body.cidade else None

        cur.execute(

            """

            UPDATE cad.empreendimentos SET

                nome_comercial = COALESCE(%s, nome_comercial),

                endereco_logradouro = COALESCE(%s, endereco_logradouro),

                endereco_numero = COALESCE(%s, endereco_numero),

                endereco_bairro = COALESCE(%s, endereco_bairro),

                endereco_cep = COALESCE(%s, endereco_cep),

                id_cidade = COALESCE(%s, id_cidade),

                latitude = COALESCE(%s, latitude),

                longitude = COALESCE(%s, longitude),

                atualizado_em = now()

            WHERE id = %s

            """,

            (

                body.nome_comercial,

                body.endereco_logradouro,

                body.endereco_numero,

                body.endereco_bairro,

                body.endereco_cep,

                id_cidade,

                body.latitude,

                body.longitude,

                str(emp_id),

            ),

        )

        if cur.rowcount == 0:

            raise HTTPException(404, "Empreendimento não encontrado")

        conn.commit()

    return get_empreendimento(emp_id)





@router.get("/{emp_id}/fases", response_model=list[FaseOut])

def list_fases(emp_id: UUID):

    with get_cursor() as (_, cur):

        cur.execute(

            """

            SELECT id, id_empreendimento, numero_fase, nome_fase, lancamento, entrega

            FROM cad.fases WHERE id_empreendimento = %s ORDER BY numero_fase

            """,

            (str(emp_id),),

        )

        return cur.fetchall()


