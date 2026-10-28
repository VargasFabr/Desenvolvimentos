#!/usr/bin/env python3
"""
Sincroniza imagens de public.media_otto: baixa URLs do JSON midias, grava JPEG
organizado em disco e regista metadados em public.media_otto_imagens_sync.

Conexão Melnick (copiar valores da Connection Airflow `postgres`):
  - Standalone: DATABASE_URL ou PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD
  - Opcional: ficheiro .env nesta pasta (python-dotenv). Variáveis PG* ou DATABASE_URL.
  - Opcional: SYNC_MEDIA_OTTO_OUTPUT_DIR — pasta padrão quando não passa --output-dir.

Dentro de um DAG Airflow: se AIRFLOW_CTX_DAG_ID estiver definido, usa
PostgresHook(postgres_conn_id="postgres") como em AtualizaPostgreSQL3.connect_to_db_Melnick.

Uso n8n / WhatsApp: consulte media_otto_imagens_sync (local_path relativo a
--output-dir ou absoluto se passar --absolute-paths). WhatsApp Cloud API costuma
exigir URL HTTPS ou upload com acesso ao ficheiro pelo n8n.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import unicodedata
from io import BytesIO
from pathlib import Path
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None  # type: ignore[misc, assignment]

import psycopg2
from psycopg2.extensions import connection as PgConnection

from PIL import Image


def _load_env_file() -> None:
    env_path = Path(__file__).resolve().parent / ".env"
    if load_dotenv and env_path.is_file():
        load_dotenv(env_path)


def connect_melnick() -> PgConnection:
    """
    Melnick: Airflow Hook se em contexto de task; senão psycopg2 via env.
    """
    if os.environ.get("AIRFLOW_CTX_DAG_ID"):
        try:
            from airflow.providers.postgres.hooks.postgres import (  # type: ignore[import-untyped]
                PostgresHook,
            )

            hook = PostgresHook(postgres_conn_id="postgres")
            return hook.get_conn()
        except Exception as exc:  # pragma: no cover - runtime Airflow
            print(f"Aviso: PostgresHook falhou ({exc}), a tentar env...", file=sys.stderr)

    _load_env_file()

    dsn = os.environ.get("DATABASE_URL")
    if dsn:
        return psycopg2.connect(dsn)

    required = ("PGHOST", "PGDATABASE", "PGUSER", "PGPASSWORD")
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        raise RuntimeError(
            "Defina DATABASE_URL ou PGHOST/PGDATABASE/PGUSER/PGPASSWORD "
            f"(em falta: {', '.join(missing)}). Dentro do Airflow use a connection postgres."
        )

    return psycopg2.connect(
        host=os.environ["PGHOST"],
        port=os.environ.get("PGPORT", "5432"),
        dbname=os.environ["PGDATABASE"],
        user=os.environ["PGUSER"],
        password=os.environ["PGPASSWORD"],
    )


def _normalize_to_rgb(img: Image.Image) -> Image.Image:
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.split()[-1])
        return background
    return img.convert("RGB")


def _convert_bytes_to_jpeg(
    content: bytes,
    quality: int = 86,
    frame: int = 0,
    max_side: int = 1600,
    max_bytes: int = 4_800_000,
) -> bytes:
    img = Image.open(BytesIO(content))
    if getattr(img, "is_animated", False):
        total_frames = getattr(img, "n_frames", 1)
        safe_frame = max(0, min(frame, total_frames - 1))
        img.seek(safe_frame)
    img = _normalize_to_rgb(img)
    safe_max_side = max(320, min(max_side, 4096))
    if max(img.size) > safe_max_side:
        img.thumbnail((safe_max_side, safe_max_side), Image.Resampling.LANCZOS)
    target_bytes = max(200_000, min(max_bytes, 12_000_000))
    quality_candidates = [
        max(1, min(100, quality)),
        82,
        76,
        70,
        64,
        58,
        52,
        46,
        40,
    ]
    tried: set[int] = set()
    for q in quality_candidates:
        if q in tried:
            continue
        tried.add(q)
        out = BytesIO()
        img.save(out, format="JPEG", quality=q, optimize=True, progressive=True)
        data = out.getvalue()
        if len(data) <= target_bytes:
            return data
    out = BytesIO()
    img.save(out, format="JPEG", quality=35, optimize=True, progressive=True)
    return out.getvalue()


def _download_image_from_url(url: str, timeout: int = 25) -> bytes:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("URL invalida: use http/https")
    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (n8n-image-converter/sync_media_otto)",
            "Accept": "image/*,*/*;q=0.8",
        },
    )
    with urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    if not data:
        raise ValueError("Download vazio")
    return data


def _slug(s: str, max_len: int = 80) -> str:
    if not s:
        return "item"
    nfd = unicodedata.normalize("NFD", s)
    ascii_str = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    lower = ascii_str.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "_", lower)
    slug = re.sub(r"_+", "_", slug).strip("_") or "item"
    return slug[:max_len]


def _fts_to_text(val: Any) -> Optional[str]:
    if val is None:
        return None
    return str(val)


def ensure_table(conn: PgConnection) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS public.media_otto_imagens_sync (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            media_otto_id text NULL,
            empreendimento text NULL,
            bairro text NULL,
            rua text NULL,
            keywords text NULL,
            full_text_search_index text NULL,
            midia text NULL,
            source_url text NOT NULL,
            local_path text NULL,
            file_size_bytes bigint NULL,
            downloaded_at timestamptz NOT NULL DEFAULT now(),
            error text NULL
        );
        """
    )
    cur.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS media_otto_imagens_sync_source_url_key
        ON public.media_otto_imagens_sync (source_url);
        """
    )
    cur.close()
    conn.commit()


def _table_has_column(conn: PgConnection, table: str, column: str) -> bool:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s AND column_name = %s
        """,
        (table, column),
    )
    ok = cur.fetchone() is not None
    cur.close()
    return ok


def _parse_midias(raw: Any) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if isinstance(raw, str):
        raw = raw.strip()
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []
    elif isinstance(raw, (list, tuple)):
        data = raw
    else:
        return []
    out: list[dict[str, Any]] = []
    for item in data:
        if isinstance(item, dict) and item.get("url"):
            out.append(item)
    return out


def _unique_path(base: Path) -> Path:
    if not base.exists():
        return base
    stem, suf = base.stem, base.suffix
    parent = base.parent
    for n in range(2, 10_000):
        cand = parent / f"{stem}_{n}{suf}"
        if not cand.exists():
            return cand
    h = hashlib.sha256(str(base).encode()).hexdigest()[:8]
    return parent / f"{stem}_{h}{suf}"


def upsert_sync_row(
    conn: PgConnection,
    *,
    media_otto_id: Optional[str],
    empreendimento: Optional[str],
    bairro: Optional[str],
    rua: Optional[str],
    keywords: Optional[str],
    full_text_search_index: Optional[str],
    midia: Optional[str],
    source_url: str,
    local_path: Optional[str],
    file_size_bytes: Optional[int],
    error: Optional[str],
) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO public.media_otto_imagens_sync (
            media_otto_id, empreendimento, bairro, rua, keywords,
            full_text_search_index, midia, source_url, local_path,
            file_size_bytes, downloaded_at, error
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now(), %s
        )
        ON CONFLICT (source_url) DO UPDATE SET
            media_otto_id = COALESCE(EXCLUDED.media_otto_id, public.media_otto_imagens_sync.media_otto_id),
            empreendimento = EXCLUDED.empreendimento,
            bairro = EXCLUDED.bairro,
            rua = EXCLUDED.rua,
            keywords = EXCLUDED.keywords,
            full_text_search_index = EXCLUDED.full_text_search_index,
            midia = EXCLUDED.midia,
            local_path = EXCLUDED.local_path,
            file_size_bytes = EXCLUDED.file_size_bytes,
            downloaded_at = now(),
            error = EXCLUDED.error
        """,
        (
            media_otto_id,
            empreendimento,
            bairro,
            rua,
            keywords,
            full_text_search_index,
            midia,
            source_url,
            local_path,
            file_size_bytes,
            error,
        ),
    )
    cur.close()


def run(
    *,
    output_dir: Path,
    absolute_paths: bool,
    limit_rows: Optional[int],
    limit_images: Optional[int],
    dry_run: bool,
    skip_existing: bool,
    batch_commit: int,
    quality: int,
    max_side: int,
    max_bytes: int,
) -> int:
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    conn = connect_melnick()
    try:
        has_id = _table_has_column(conn, "media_otto", "id")
        id_sql = "id, " if has_id else ""
        query = f"""
            SELECT {id_sql}empreendimento, bairro, rua, keywords, full_text_search_index, midias
            FROM public.media_otto
        """
        if limit_rows is not None:
            query += f" LIMIT {int(limit_rows)}"

        cur = conn.cursor()
        cur.execute(query)
        rows = cur.fetchall()
        colnames = [d[0] for d in cur.description]
        cur.close()

        if dry_run:
            print(f"dry-run: {len(rows)} linhas, colunas={colnames}")
            for i, row in enumerate(rows[:5]):
                d = dict(zip(colnames, row))
                midias = _parse_midias(d.get("midias"))
                print(f"  [{i}] empreendimento={d.get('empreendimento')!r} midias={len(midias)}")
            return 0

        ensure_table(conn)

        images_done = 0
        pending_commit = 0

        for row in rows:
            d = dict(zip(colnames, row))
            media_otto_id: Optional[str] = None
            if has_id and "id" in d and d["id"] is not None:
                media_otto_id = str(d["id"])

            emp = d.get("empreendimento")
            emp_str = emp if isinstance(emp, str) else (str(emp) if emp is not None else "")
            slug_emp = _slug(emp_str)
            row_dir = output_dir / slug_emp
            row_dir.mkdir(parents=True, exist_ok=True)

            midias = _parse_midias(d.get("midias"))
            fts_text = _fts_to_text(d.get("full_text_search_index"))

            for idx, item in enumerate(midias, start=1):
                if limit_images is not None and images_done >= limit_images:
                    conn.commit()
                    print(f"Limite --limit-images={limit_images} atingido.")
                    return 0

                url = str(item["url"]).strip()
                midia_label = item.get("midia")
                midia_str = midia_label if isinstance(midia_label, str) else (
                    str(midia_label) if midia_label is not None else ""
                )
                slug_mid = _slug(midia_str, max_len=60)
                fname = f"{idx:03d}_{slug_mid}.jpg"
                dest = row_dir / fname
                dest = _unique_path(dest)

                rel_path = str(dest.relative_to(output_dir))
                store_path = str(dest.resolve()) if absolute_paths else rel_path

                if skip_existing:
                    cur2 = conn.cursor()
                    cur2.execute(
                        """
                        SELECT local_path, error FROM public.media_otto_imagens_sync
                        WHERE source_url = %s
                        """,
                        (url,),
                    )
                    prev = cur2.fetchone()
                    cur2.close()
                    if prev and prev[1] is None and prev[0]:
                        p = output_dir / prev[0] if not os.path.isabs(prev[0]) else Path(prev[0])
                        if p.is_file():
                            images_done += 1
                            continue

                try:
                    raw = _download_image_from_url(url)
                    jpeg = _convert_bytes_to_jpeg(
                        raw, quality=quality, frame=0, max_side=max_side, max_bytes=max_bytes
                    )
                    dest.write_bytes(jpeg)
                    upsert_sync_row(
                        conn,
                        media_otto_id=media_otto_id,
                        empreendimento=d.get("empreendimento") if isinstance(d.get("empreendimento"), str) else (
                            str(d["empreendimento"]) if d.get("empreendimento") is not None else None
                        ),
                        bairro=d.get("bairro") if isinstance(d.get("bairro"), str) else (
                            str(d["bairro"]) if d.get("bairro") is not None else None
                        ),
                        rua=d.get("rua") if isinstance(d.get("rua"), str) else (
                            str(d["rua"]) if d.get("rua") is not None else None
                        ),
                        keywords=d.get("keywords") if isinstance(d.get("keywords"), str) else (
                            str(d["keywords"]) if d.get("keywords") is not None else None
                        ),
                        full_text_search_index=fts_text,
                        midia=midia_str or None,
                        source_url=url,
                        local_path=store_path,
                        file_size_bytes=len(jpeg),
                        error=None,
                    )
                except (HTTPError, URLError, OSError, ValueError, Image.UnidentifiedImageError) as exc:
                    upsert_sync_row(
                        conn,
                        media_otto_id=media_otto_id,
                        empreendimento=d.get("empreendimento") if isinstance(d.get("empreendimento"), str) else (
                            str(d["empreendimento"]) if d.get("empreendimento") is not None else None
                        ),
                        bairro=d.get("bairro") if isinstance(d.get("bairro"), str) else (
                            str(d["bairro"]) if d.get("bairro") is not None else None
                        ),
                        rua=d.get("rua") if isinstance(d.get("rua"), str) else (
                            str(d["rua"]) if d.get("rua") is not None else None
                        ),
                        keywords=d.get("keywords") if isinstance(d.get("keywords"), str) else (
                            str(d["keywords"]) if d.get("keywords") is not None else None
                        ),
                        full_text_search_index=fts_text,
                        midia=midia_str or None,
                        source_url=url,
                        local_path=None,
                        file_size_bytes=None,
                        error=str(exc)[:2000],
                    )
                    print(f"ERRO {url}: {exc}", file=sys.stderr)

                images_done += 1
                pending_commit += 1
                if pending_commit >= batch_commit:
                    conn.commit()
                    pending_commit = 0

            print(f"Processado empreendimento={emp_str!r} ({len(midias)} imagens nesta linha)")

        if pending_commit:
            conn.commit()
        print(f"Concluído. Total imagens processadas (tentativas): {images_done}")
        return 0
    finally:
        conn.close()


def _default_output_dir() -> Path:
    env = os.environ.get("SYNC_MEDIA_OTTO_OUTPUT_DIR")
    if env:
        return Path(env)
    return Path("./data/media_otto_images")


def main() -> int:
    _load_env_file()
    p = argparse.ArgumentParser(description="Sincroniza midias de media_otto para disco + tabela auxiliar.")
    p.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Pasta raiz para gravar JPEG (default: SYNC_MEDIA_OTTO_OUTPUT_DIR ou ./data/media_otto_images)",
    )
    p.add_argument(
        "--absolute-paths",
        action="store_true",
        help="Grava caminho absoluto em local_path em vez de relativo a --output-dir",
    )
    p.add_argument("--limit-rows", type=int, default=None, help="LIMIT no SELECT de media_otto")
    p.add_argument("--limit-images", type=int, default=None, help="Para após N imagens processadas")
    p.add_argument("--dry-run", action="store_true", help="Só lista amostra, sem download nem DDL")
    p.add_argument(
        "--skip-existing",
        action="store_true",
        help="Ignora URL se já existir registo sem erro e ficheiro presente",
    )
    p.add_argument("--batch-commit", type=int, default=20, help="Commit a cada N imagens")
    p.add_argument("--quality", type=int, default=86)
    p.add_argument("--max-side", type=int, default=1600)
    p.add_argument("--max-bytes", type=int, default=4_800_000)
    args = p.parse_args()
    out = args.output_dir if args.output_dir is not None else _default_output_dir()

    return run(
        output_dir=out,
        absolute_paths=args.absolute_paths,
        limit_rows=args.limit_rows,
        limit_images=args.limit_images,
        dry_run=args.dry_run,
        skip_existing=args.skip_existing,
        batch_commit=max(1, args.batch_commit),
        quality=args.quality,
        max_side=args.max_side,
        max_bytes=args.max_bytes,
    )


if __name__ == "__main__":
    raise SystemExit(main())
