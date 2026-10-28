from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.db import get_cursor
from app.schemas import FaseCreate, FaseOut
from lib.cad_parsers import uid

router = APIRouter(prefix="/api/fases", tags=["fases"])


@router.post("", response_model=FaseOut, status_code=201)
def create_fase(body: FaseCreate):
    fase_id = uid("fase", f"{body.id_empreendimento}-{body.numero_fase}")
    with get_cursor() as (conn, cur):
        cur.execute("SELECT 1 FROM cad.empreendimentos WHERE id = %s", (str(body.id_empreendimento),))
        if not cur.fetchone():
            raise HTTPException(404, "Empreendimento não encontrado")
        cur.execute(
            """
            INSERT INTO cad.fases (id, id_empreendimento, numero_fase, nome_fase, lancamento, entrega)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (id_empreendimento, numero_fase) DO UPDATE SET
                nome_fase = EXCLUDED.nome_fase,
                lancamento = EXCLUDED.lancamento,
                entrega = EXCLUDED.entrega,
                atualizado_em = now()
            RETURNING id, id_empreendimento, numero_fase, nome_fase, lancamento, entrega
            """,
            (
                fase_id,
                str(body.id_empreendimento),
                body.numero_fase,
                body.nome_fase or f"Fase {body.numero_fase}",
                body.lancamento,
                body.entrega,
            ),
        )
        row = cur.fetchone()
        conn.commit()
    return row
