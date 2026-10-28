from __future__ import annotations

import io
from typing import Any

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse

from app.db import get_conn, get_cursor
from app.schemas import ImportConfirmRequest, ImportPreviewResponse, ImportPreviewRow, ImportIssue
from lib.cad_parsers import (
    EXCEL_COLUMNS,
    TorreImportRow,
    parse_csv_bytes,
    parse_excel_bytes,
    row_dict_to_import,
    rows_from_raw_dicts,
    validate_import_rows,
)
from lib.cad_service import upsert_torre_rows
from lib.unidade_parsers import (
    EXCEL_COLUMNS as UNIDADE_EXCEL_COLUMNS,
    parse_csv_bytes as parse_unidade_csv,
    parse_excel_bytes as parse_unidade_excel,
    row_dict_to_import as unidade_row_dict,
    rows_from_raw_dicts as unidade_rows_from_raw,
    validate_import_rows as validate_unidade_rows,
)
from lib.unidade_service import upsert_unidade_rows

router = APIRouter(prefix="/api", tags=["import-export"])


def _preview_from_bytes(content: bytes, filename: str) -> ImportPreviewResponse:
    lower = filename.lower()
    if lower.endswith(".csv"):
        raw = parse_csv_bytes(content)
    elif lower.endswith((".xlsx", ".xlsm")):
        raw = parse_excel_bytes(content)
    else:
        raise HTTPException(400, "Formato não suportado. Use .xlsx ou .csv")

    items = rows_from_raw_dicts(raw)
    valid, issues = validate_import_rows(items)
    erros = [ImportIssue(linha=i.linha, campo=i.campo, mensagem=i.mensagem) for i in issues if i.tipo == "erro"]
    avisos = [ImportIssue(linha=i.linha, campo=i.campo, mensagem=i.mensagem) for i in issues if i.tipo == "aviso"]

    preview_rows = [
        ImportPreviewRow(
            linha=v.linha,
            codigo_interno=v.codigo_interno,
            empreendimento=v.empreendimento,
            spe=v.spe,
            torre=v.torre,
            cod_torre=v.cod_torre,
            fase=v.fase,
        )
        for v in valid
    ]
    payload = [_torre_row_to_dict(v) for v in valid]
    return ImportPreviewResponse(
        total=len(items),
        validos=len(valid),
        erros=erros,
        avisos=avisos,
        rows=preview_rows,
        payload=payload,
    )


def _torre_row_to_dict(item: TorreImportRow) -> dict[str, Any]:
    return {
        "linha": item.linha,
        "Empreendimento": item.empreendimento,
        "SPE": item.spe,
        "Torre": item.torre or "",
        "Cód. Torre": item.cod_torre,
        "Fase": item.fase,
        "Segmento": item.segmento or "",
        "Estágio": item.estagio or "",
        "Empresa": item.tipo_empresa or "",
        "Principal?": "Sim" if item.principal else "Não",
        "Permutante?": "Sim" if item.permutante else "Não",
        "Lançamento": item.lancamento.isoformat() if item.lancamento else "",
        "Entrega": item.entrega.isoformat() if item.entrega else "",
        "VGV Bruto": str(item.vgv_bruto) if item.vgv_bruto else "",
        "VGV Líquido": str(item.vgv_liquido) if item.vgv_liquido else "",
        "Unidades": item.unidades_total or "",
        "ID Órulo": item.id_orulo or "",
        "Logradouro": item.logradouro or "",
        "Número": item.numero or "",
        "Bairro": item.bairro or "",
        "Cidade": item.cidade or "",
        "CEP": item.cep or "",
        "Coordenada": f"{item.latitude},{item.longitude}" if item.latitude and item.longitude else "",
    }


@router.get("/import/template.xlsx")
def download_template():
    from openpyxl import Workbook
    from openpyxl.styles import Font

    wb = Workbook()
    ws = wb.active
    ws.title = "Torres"
    ws.append(EXCEL_COLUMNS)
    ws.append(
        [
            "Exemplo Residencial",
            "9999",
            "Torre A",
            "001",
            1,
            "Residencial",
            "Lançamento",
            "INC",
            "Sim",
            "Não",
            "01/01/2025",
            "01/06/2027",
            "10000000",
            "9500000",
            120,
            "",
            "Rua Exemplo",
            "100",
            "Centro",
            "Porto Alegre",
            "90000-000",
            "-30.0,-51.0",
        ]
    )
    for cell in ws[1]:
        cell.font = Font(bold=True)

    inst = wb.create_sheet("Instruções")
    inst.append(["Coluna", "Obrigatório", "Descrição"])
    hints = [
        ("Empreendimento", "Sim", "Nome comercial"),
        ("SPE", "Sim", "Código SPE único"),
        ("Cód. Torre", "Sim", "Código da torre no GC"),
        ("Fase", "Sim", "Número da fase (default 1)"),
        ("Principal?", "Não", "Sim/Não"),
    ]
    for h in hints:
        inst.append(list(h))

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=template_cadastro_torres.xlsx"},
    )


@router.post("/import/preview", response_model=ImportPreviewResponse)
async def import_preview(file: UploadFile = File(...)):
    content = await file.read()
    return _preview_from_bytes(content, file.filename or "upload.xlsx")


@router.post("/import/confirm")
def import_confirm(body: ImportConfirmRequest):
    items = [row_dict_to_import(r.get("linha", i + 2), r) for i, r in enumerate(body.rows)]
    valid, issues = validate_import_rows(items)
    if issues and any(i.tipo == "erro" for i in issues):
        raise HTTPException(400, detail={"erros": [i.__dict__ for i in issues]})
    with get_conn() as conn:
        count = upsert_torre_rows(conn, valid, fonte="excel")
    return {"importados": count}


@router.get("/export/torres.xlsx")
def export_torres(spe: str | None = Query(None)):
    from openpyxl import Workbook

    sql = "SELECT * FROM public.v_torres_completas"
    params: list = []
    if spe:
        sql += " WHERE cod_spe = %s"
        params.append(spe)
    sql += " ORDER BY nome_comercial, cod_torre"

    with get_cursor() as (_, cur):
        cur.execute(sql, params)
        rows = cur.fetchall()

    wb = Workbook()
    ws = wb.active
    ws.title = "Torres"
    if rows:
        headers = list(rows[0].keys())
        ws.append(headers)
        for r in rows:
            ws.append([r[h] for h in headers])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=torres_export.xlsx"},
    )


@router.get("/busca")
def busca(q: str = Query(..., min_length=2)):
    with get_cursor() as (_, cur):
        cur.execute(
            """
            SELECT
                entidade_tipo AS tipo,
                codigo_interno,
                cod_spe,
                COALESCE(NULLIF(nome_torre, ''), nome_comercial) AS nome,
                alias
            FROM public.v_busca_cadastro
            WHERE alias ILIKE %s
               OR nome_comercial ILIKE %s
               OR nome_torre ILIKE %s
               OR codigo_interno ILIKE %s
               OR cod_spe ILIKE %s
            LIMIT 50
            """,
            (f"%{q}%",) * 5,
        )
        return cur.fetchall()


@router.get("/dashboard")
def dashboard():
    with get_cursor() as (_, cur):
        cur.execute("SELECT count(*)::int AS n FROM cad.empreendimentos")
        emps = cur.fetchone()["n"]
        cur.execute("SELECT count(*)::int AS n FROM cad.torres")
        torres = cur.fetchone()["n"]
        cur.execute("SELECT count(*)::int AS n FROM cad.fases")
        fases = cur.fetchone()["n"]
        cur.execute("SELECT count(*)::int AS n FROM cad.unidades")
        unidades = cur.fetchone()["n"]
    return {"empreendimentos": emps, "torres": torres, "fases": fases, "unidades": unidades}


def _unidade_row_to_dict(item) -> dict[str, Any]:
    return {
        "linha": item.linha,
        "SPE": item.spe,
        "Cód. Torre": item.cod_torre,
        "Fase": item.fase,
        "Unidade": item.nome,
        "Andar": item.andar or "",
        "Área privativa": str(item.area_privativa) if item.area_privativa else "",
        "Fração ideal": str(item.fracao_ideal) if item.fracao_ideal else "",
        "Tipo": item.tipo or "",
        "Dormitórios": item.dormitorios or "",
        "Vagas": str(item.vagas) if item.vagas else "",
        "ID GC": item.id_gc or "",
    }


@router.get("/import/unidades/template.xlsx")
def download_unidades_template():
    from openpyxl import Workbook
    from openpyxl.styles import Font

    wb = Workbook()
    ws = wb.active
    ws.title = "Unidades"
    ws.append(UNIDADE_EXCEL_COLUMNS)
    ws.append(["8190", "001", 1, "101", "1", "75.5", "0.0123", "Apartamento", 2, 1, "GC-101"])
    for cell in ws[1]:
        cell.font = Font(bold=True)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=template_unidades.xlsx"},
    )


@router.post("/import/unidades/preview")
async def import_unidades_preview(file: UploadFile = File(...)):
    content = await file.read()
    fn = (file.filename or "").lower()
    if fn.endswith(".csv"):
        raw = parse_unidade_csv(content)
    elif fn.endswith((".xlsx", ".xlsm")):
        raw = parse_unidade_excel(content)
    else:
        raise HTTPException(400, "Use .xlsx ou .csv")
    items = unidade_rows_from_raw(raw)
    valid, issues = validate_unidade_rows(items)
    erros = [ImportIssue(linha=i.linha, campo=i.campo, mensagem=i.mensagem) for i in issues]
    rows = [
        ImportPreviewRow(
            linha=v.linha,
            codigo_interno=v.codigo_interno_torre,
            empreendimento="",
            spe=v.spe,
            torre=None,
            cod_torre=v.cod_torre,
            fase=v.fase,
        )
        for v in valid
    ]
    return ImportPreviewResponse(
        total=len(items),
        validos=len(valid),
        erros=erros,
        avisos=[],
        rows=rows,
        payload=[_unidade_row_to_dict(v) for v in valid],
    )


@router.post("/import/unidades/confirm")
def import_unidades_confirm(body: ImportConfirmRequest):
    items = [unidade_row_dict(r.get("linha", i + 2), r) for i, r in enumerate(body.rows)]
    valid, issues = validate_unidade_rows(items)
    if issues:
        raise HTTPException(400, detail={"erros": [i.__dict__ for i in issues]})
    with get_conn() as conn:
        count, erros_db = upsert_unidade_rows(conn, valid)
    if erros_db:
        raise HTTPException(400, detail={"erros": erros_db, "importados": count})
    return {"importados": count}
