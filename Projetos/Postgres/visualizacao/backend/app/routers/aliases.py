from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.db import get_cursor
from app.schemas import AliasCreate, IdentificadorCreate

router_aliases = APIRouter(prefix="/api/torres", tags=["aliases"])
router_ids = APIRouter(prefix="/api/torres", tags=["identificadores"])


@router_aliases.post("/{torre_id}/aliases", status_code=201)
def add_alias(torre_id: UUID, body: AliasCreate):
    with get_cursor() as (conn, cur):
        cur.execute("SELECT 1 FROM cad.torres WHERE id = %s", (str(torre_id),))
        if not cur.fetchone():
            raise HTTPException(404, "Torre não encontrada")
        cur.execute(
            """
            INSERT INTO cad.aliases (entidade_tipo, entidade_id, alias, fonte)
            VALUES ('torre', %s, %s, %s)
            ON CONFLICT DO NOTHING
            RETURNING id, alias, fonte
            """,
            (str(torre_id), body.alias.strip(), body.fonte),
        )
        row = cur.fetchone()
        conn.commit()
    return row or {"alias": body.alias, "fonte": body.fonte}


@router_ids.post("/{torre_id}/identificadores", status_code=201)
def add_identificador(torre_id: UUID, body: IdentificadorCreate):
    with get_cursor() as (conn, cur):
        cur.execute("SELECT 1 FROM cad.torres WHERE id = %s", (str(torre_id),))
        if not cur.fetchone():
            raise HTTPException(404, "Torre não encontrada")
        cur.execute(
            """
            INSERT INTO cad.identificadores_externos (entidade_tipo, entidade_id, sistema, id_externo)
            VALUES ('torre', %s, %s, %s)
            ON CONFLICT (entidade_tipo, entidade_id, sistema) DO UPDATE SET id_externo = EXCLUDED.id_externo
            RETURNING id, sistema, id_externo
            """,
            (str(torre_id), body.sistema, body.id_externo.strip()),
        )
        row = cur.fetchone()
        conn.commit()
    return row
