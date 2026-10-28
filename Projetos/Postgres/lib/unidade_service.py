"""Persistência de unidades no schema cad."""
from __future__ import annotations

import uuid

from lib.unidade_parsers import UnidadeImportRow

NS = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def uid_unidade(id_torre: str, nome: str) -> str:
    return str(uuid.uuid5(NS, f"unidade:{id_torre}:{nome.strip().lower()}"))


def resolve_torre(cur, codigo_interno_torre: str) -> tuple[str, str] | None:
    cur.execute(
        "SELECT id, id_empreendimento FROM cad.torres WHERE codigo_interno = %s",
        (codigo_interno_torre,),
    )
    row = cur.fetchone()
    if not row:
        return None
    return str(row["id"]), str(row["id_empreendimento"])


def upsert_unidade_row(cur, item: UnidadeImportRow, id_torre: str, id_empreendimento: str) -> str:
    uid = uid_unidade(id_torre, item.nome)
    cur.execute(
        """
        INSERT INTO cad.unidades (
            id, id_torre, id_empreendimento, nome, andar,
            area_privativa, fracao_ideal, tipo, dormitorios, vagas, id_gc
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (id) DO UPDATE SET
            andar = EXCLUDED.andar,
            area_privativa = EXCLUDED.area_privativa,
            fracao_ideal = EXCLUDED.fracao_ideal,
            tipo = EXCLUDED.tipo,
            dormitorios = EXCLUDED.dormitorios,
            vagas = EXCLUDED.vagas,
            id_gc = EXCLUDED.id_gc,
            atualizado_em = now()
        RETURNING id
        """,
        (
            uid,
            id_torre,
            id_empreendimento,
            item.nome,
            item.andar,
            item.area_privativa,
            item.fracao_ideal,
            item.tipo,
            item.dormitorios,
            item.vagas,
            item.id_gc,
        ),
    )
    row = cur.fetchone()
    return str(row["id"]) if row else uid


def upsert_otto_unidade_row(cur, item: UnidadeImportRow, id_torre: str, id_empreendimento: str) -> str:
    uid = upsert_unidade_row(cur, item, id_torre, id_empreendimento)
    if item.otto_unit_id:
        cur.execute(
            """
            INSERT INTO cad.identificadores_externos (entidade_tipo, entidade_id, sistema, id_externo)
            VALUES ('unidade', %s, 'otto', %s)
            ON CONFLICT (sistema, id_externo) DO UPDATE SET entidade_id = EXCLUDED.entidade_id
            """,
            (uid, item.otto_unit_id),
        )
    return uid


def upsert_unidade_rows(conn, rows: list[UnidadeImportRow]) -> tuple[int, list[dict]]:
    erros: list[dict] = []
    count = 0
    with conn:
        with conn.cursor() as cur:
            for item in rows:
                torre = resolve_torre(cur, item.codigo_interno_torre)
                if not torre:
                    erros.append(
                        {"linha": item.linha, "mensagem": f"Torre não encontrada: {item.codigo_interno_torre}"}
                    )
                    continue
                id_torre, id_emp = torre
                upsert_unidade_row(cur, item, id_torre, id_emp)
                count += 1
    return count, erros
