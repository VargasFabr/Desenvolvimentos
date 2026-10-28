"""Persistência transacional no schema cad."""
from __future__ import annotations

import json
from typing import Any

import psycopg2
from psycopg2.extensions import connection as PgConnection

from lib.cad_parsers import (
    MELNICK_INCORPORADORA_ID,
    TorreImportRow,
    uid,
)


def _ensure_estado_rs(cur) -> None:
    cur.execute(
        """
        INSERT INTO cad.estados (id, sigla, nome)
        VALUES (%s, 'RS', 'Rio Grande do Sul')
        ON CONFLICT (sigla) DO NOTHING
        """,
        (uid("estado", "RS"),),
    )


def _ensure_cidade(cur, nome: str | None) -> str | None:
    if not nome:
        return None
    cid = uid("cidade", nome)
    _ensure_estado_rs(cur)
    cur.execute(
        """
        INSERT INTO cad.cidades (id, nome, id_estado)
        VALUES (%s, %s, %s)
        ON CONFLICT (nome, id_estado) DO NOTHING
        """,
        (cid, nome, uid("estado", "RS")),
    )
    cur.execute(
        "SELECT id FROM cad.cidades WHERE nome = %s AND id_estado = %s",
        (nome, uid("estado", "RS")),
    )
    row = cur.fetchone()
    if not row:
        return cid
    return str(row["id"] if isinstance(row, dict) else row[0])


def upsert_torre_row(cur, item: TorreImportRow, fonte: str = "visualizacao") -> str:
    """Upsert empreendimento + fase + torre + aliases básicos. Retorna id_torre."""
    emp_id = uid("empreendimento", item.spe)
    fase_id = uid("fase", f"{item.spe}-{item.fase}")
    torre_id = uid("torre", item.codigo_interno)
    id_cidade = _ensure_cidade(cur, item.cidade)

    cur.execute(
        """
        INSERT INTO cad.empreendimentos (
            id, cod_spe, nome_comercial, id_incorporadora, id_cidade,
            endereco_logradouro, endereco_numero, endereco_bairro, endereco_cep,
            latitude, longitude
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (cod_spe) DO UPDATE SET
            nome_comercial = EXCLUDED.nome_comercial,
            id_cidade = COALESCE(EXCLUDED.id_cidade, cad.empreendimentos.id_cidade),
            endereco_logradouro = COALESCE(EXCLUDED.endereco_logradouro, cad.empreendimentos.endereco_logradouro),
            endereco_numero = COALESCE(EXCLUDED.endereco_numero, cad.empreendimentos.endereco_numero),
            endereco_bairro = COALESCE(EXCLUDED.endereco_bairro, cad.empreendimentos.endereco_bairro),
            endereco_cep = COALESCE(EXCLUDED.endereco_cep, cad.empreendimentos.endereco_cep),
            latitude = COALESCE(EXCLUDED.latitude, cad.empreendimentos.latitude),
            longitude = COALESCE(EXCLUDED.longitude, cad.empreendimentos.longitude),
            atualizado_em = now()
        """,
        (
            emp_id,
            item.spe,
            item.empreendimento,
            MELNICK_INCORPORADORA_ID,
            id_cidade,
            item.logradouro,
            item.numero,
            item.bairro,
            item.cep,
            item.latitude,
            item.longitude,
        ),
    )

    for sistema in ("gc", "controladoria"):
        cur.execute(
            """
            INSERT INTO cad.identificadores_externos (entidade_tipo, entidade_id, sistema, id_externo)
            VALUES ('empreendimento', %s, %s, %s)
            ON CONFLICT (sistema, id_externo) DO NOTHING
            """,
            (emp_id, sistema, item.spe),
        )

    cur.execute(
        """
        INSERT INTO cad.aliases (entidade_tipo, entidade_id, alias, fonte)
        VALUES ('empreendimento', %s, %s, %s)
        ON CONFLICT DO NOTHING
        """,
        (emp_id, item.empreendimento, fonte),
    )

    cur.execute(
        """
        INSERT INTO cad.fases (id, id_empreendimento, numero_fase, nome_fase, lancamento, entrega, inicio_obra)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id_empreendimento, numero_fase) DO UPDATE SET
            lancamento = COALESCE(EXCLUDED.lancamento, cad.fases.lancamento),
            entrega = COALESCE(EXCLUDED.entrega, cad.fases.entrega),
            inicio_obra = COALESCE(EXCLUDED.inicio_obra, cad.fases.inicio_obra),
            atualizado_em = now()
        """,
        (
            fase_id,
            emp_id,
            item.fase,
            f"Fase {item.fase}",
            item.lancamento,
            item.entrega,
            item.inicio_obra,
        ),
    )

    cur.execute(
        """
        INSERT INTO cad.torres (
            id, codigo_interno, cod_torre, nome_torre, id_empreendimento, id_fase,
            segmento, estagio, tipo_empresa, principal, permutante,
            lancamento, entrega, inicio_obra, vgv_bruto, vgv_liquido,
            unidades_total, id_orulo, tags
        ) VALUES (
            %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb
        )
        ON CONFLICT (codigo_interno) DO UPDATE SET
            nome_torre = EXCLUDED.nome_torre,
            segmento = EXCLUDED.segmento,
            estagio = EXCLUDED.estagio,
            tipo_empresa = EXCLUDED.tipo_empresa,
            principal = EXCLUDED.principal,
            permutante = EXCLUDED.permutante,
            lancamento = EXCLUDED.lancamento,
            entrega = EXCLUDED.entrega,
            inicio_obra = EXCLUDED.inicio_obra,
            vgv_bruto = EXCLUDED.vgv_bruto,
            vgv_liquido = EXCLUDED.vgv_liquido,
            unidades_total = EXCLUDED.unidades_total,
            id_orulo = EXCLUDED.id_orulo,
            tags = EXCLUDED.tags,
            atualizado_em = now()
        """,
        (
            torre_id,
            item.codigo_interno,
            item.cod_torre,
            item.torre,
            emp_id,
            fase_id,
            item.segmento,
            item.estagio,
            item.tipo_empresa,
            item.principal,
            item.permutante,
            item.lancamento,
            item.entrega,
            item.inicio_obra,
            item.vgv_bruto,
            item.vgv_liquido,
            item.unidades_total,
            item.id_orulo,
            json.dumps(item.tags, ensure_ascii=False),
        ),
    )

    cur.execute(
        """
        INSERT INTO cad.aliases (entidade_tipo, entidade_id, alias, fonte)
        VALUES ('torre', %s, %s, %s)
        ON CONFLICT DO NOTHING
        """,
        (torre_id, item.empreendimento, fonte),
    )
    if item.torre:
        cur.execute(
            """
            INSERT INTO cad.aliases (entidade_tipo, entidade_id, alias, fonte)
            VALUES ('torre', %s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            (torre_id, f"{item.empreendimento} {item.torre}".strip(), fonte),
        )
    if item.id_orulo:
        cur.execute(
            """
            INSERT INTO cad.identificadores_externos (entidade_tipo, entidade_id, sistema, id_externo)
            VALUES ('torre', %s, 'orulo', %s)
            ON CONFLICT (sistema, id_externo) DO NOTHING
            """,
            (torre_id, item.id_orulo),
        )
    return torre_id


def upsert_torre_rows(conn: PgConnection, rows: list[TorreImportRow], fonte: str = "visualizacao") -> int:
    with conn:
        with conn.cursor() as cur:
            for item in rows:
                upsert_torre_row(cur, item, fonte=fonte)
    return len(rows)
