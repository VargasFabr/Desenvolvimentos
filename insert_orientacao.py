import os
import sys
import logging
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

try:
    from tkinter import Tk, filedialog
except ImportError:
    Tk = None  # type: ignore


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


DB_CONFIG = {
    "host": "localhost",
    "database": "otto",
    "user": "postgres",
    "password": "##Melnick2025",
    "port": 5432,
}

COD_EMPREENDIMENTO = "7890"
COD_TORRE = "004"
TARGET_TABLE = "unit"
REQUIRED_COLUMNS = {"cod_unidade", "orientacao"}


def connect_to_db() -> psycopg2.extensions.connection:
    logging.info("Connecting to Otto database...")
    return psycopg2.connect(**DB_CONFIG)


def pick_excel_file() -> str:
    if len(sys.argv) > 1:
        candidate = sys.argv[1]
        if os.path.isfile(candidate):
            logging.info("Using Excel file provided via command line.")
            return candidate
        logging.warning("File provided via command line was not found: %s", candidate)

    if Tk is not None:
        try:
            root = Tk()
            root.withdraw()
            filetypes = [("Excel files", "*.xlsx *.xls"), ("All files", "*.*")]
            selected = filedialog.askopenfilename(title="Selecione o arquivo Excel", filetypes=filetypes)
            root.update()
            root.destroy()
            if selected:
                logging.info("Excel file selected: %s", selected)
                return selected
        except Exception as exc:
            logging.warning("Graphical selection failed, falling back to manual input: %s", exc)

    while True:
        manual = input("Informe o caminho completo do arquivo Excel: ").strip('"').strip()
        if os.path.isfile(manual):
            return manual
        logging.error("Arquivo nao encontrado: %s", manual)


def load_excel_data(path: str) -> pd.DataFrame:
    logging.info("Reading Excel file...")
    df = pd.read_excel(path)
    df.columns = [col.strip().lower() for col in df.columns]
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Colunas obrigatorias ausentes no Excel: {', '.join(sorted(missing))}")
    df = df[list(REQUIRED_COLUMNS)].copy()
    df = df.dropna(subset=["cod_unidade", "orientacao"])
    df["cod_unidade"] = df["cod_unidade"].astype(str).str.strip()
    df["orientacao"] = df["orientacao"].astype(str).str.strip()
    df = df[df["cod_unidade"] != ""]
    df = df[df["orientacao"] != ""]
    logging.info("Excel carregado com %d linhas validas.", len(df))
    return df


def _normalize_key(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = str(value).strip().lower()
    if not value:
        return None
    return value


def build_unit_lookup(rows: Iterable[Tuple[str, ...]]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for row in rows:
        cod_unidade = row[0]
        if cod_unidade is None:
            continue
        key = _normalize_key(cod_unidade)
        if key and key not in mapping:
            mapping[key] = cod_unidade
        # Variante sem zeros à esquerda
        if cod_unidade:
            normalized = _normalize_key(cod_unidade.lstrip("0"))
            if normalized and normalized not in mapping:
                mapping[normalized] = cod_unidade
    return mapping


def fetch_units_lookup(conn: psycopg2.extensions.connection) -> Dict[str, str]:
    logging.info(
        "Buscando unidades com codEmpreendimento=%s e codTorre=%s...",
        COD_EMPREENDIMENTO,
        COD_TORRE,
    )
    query = """
        SELECT
            u.integration_metadata ->> 'codUnidade' AS cod_unidade
        FROM public.unit u
        WHERE u.integration_metadata ->> 'codEmpreendimento' = %s
          AND u.integration_metadata ->> 'codTorre' = %s;
    """
    with conn.cursor() as cur:
        cur.execute(query, (COD_EMPREENDIMENTO, COD_TORRE))
        rows = cur.fetchall()
    logging.info("Foram encontradas %d unidades no filtro solicitado.", len(rows))
    return build_unit_lookup(rows)


def prepare_payload(df: pd.DataFrame, lookup: Dict[str, str]) -> Tuple[List[Tuple[str, str]], List[str]]:
    payload: List[Tuple[str, str]] = []
    unmatched_units: List[str] = []
    seen_units: set[str] = set()

    for _, row in df.iterrows():
        raw_cod = row["cod_unidade"]
        orientacao = row["orientacao"]
        normalized = _normalize_key(raw_cod)

        cod_original = lookup.get(normalized)
        if cod_original is None and normalized:
            cod_original = lookup.get(normalized.lstrip("0"))

        if cod_original is None:
            unmatched_units.append(str(raw_cod))
            continue

        if cod_original in seen_units:
            logging.debug("Codigo %s duplicado, sobrescrevendo orientacao.", raw_cod)
            payload = [item for item in payload if item[0] != cod_original]
        seen_units.add(cod_original)
        payload.append((cod_original, orientacao))

    return payload, unmatched_units


def update_unit_orientation(
    conn: psycopg2.extensions.connection,
    payload: List[Tuple[str, str]],
) -> None:
    if not payload:
        logging.warning("Nenhuma orientacao para atualizar.")
        return

    logging.info("Atualizando orientacao de %d unidades na tabela %s...", len(payload), TARGET_TABLE)
    update_sql = f"""
        UPDATE public.{TARGET_TABLE} AS u
        SET orientacao = data.orientacao
        FROM (VALUES %s) AS data(cod_unidade, orientacao)
        WHERE u.integration_metadata ->> 'codEmpreendimento' = '{COD_EMPREENDIMENTO}'
          AND u.integration_metadata ->> 'codTorre' = '{COD_TORRE}'
          AND u.integration_metadata ->> 'codUnidade' = data.cod_unidade;
    """
    with conn.cursor() as cur:
        execute_values(cur, update_sql, payload)
    conn.commit()
    logging.info("Atualizacao concluida com sucesso.")


def main() -> None:
    try:
        excel_path = pick_excel_file()
        df = load_excel_data(excel_path)
    except Exception as exc:
        logging.error("Falha ao carregar o arquivo Excel: %s", exc)
        sys.exit(1)

    conn: Optional[psycopg2.extensions.connection] = None
    try:
        conn = connect_to_db()
        lookup = fetch_units_lookup(conn)
        payload, unmatched = prepare_payload(df, lookup)
        update_unit_orientation(conn, payload)

        if unmatched:
            logging.warning(
                "Nao foi possivel localizar %d codigos de unidade. Verifique: %s",
                len(unmatched),
                ", ".join(sorted(set(unmatched))),
            )
        else:
            logging.info("Todas as unidades do Excel foram processadas com sucesso.")

        # Exibe amostra atualizada para conferência opcional
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    u.integration_metadata ->> 'codTorre' AS cod_torre,
                    u.integration_metadata ->> 'codUnidade' AS cod_unidade,
                    u.integration_metadata ->> 'codEmpreendimento' AS cod_empreendimento,
                    u.orientacao,
                    b.name
                FROM public.unit u
                JOIN public.building b ON u.building_id = b.id
                WHERE u.integration_metadata ->> 'codEmpreendimento' = %s
                  AND u.integration_metadata ->> 'codTorre' = %s
                  AND (u.integration_metadata ->> 'codUnidade') = ANY(%s)
                ORDER BY u.created_at DESC
                LIMIT 10;
                """,
                (COD_EMPREENDIMENTO, COD_TORRE, [item[0] for item in payload]),
            )
            sample = cur.fetchall()
            if sample:
                logging.info("Amostra de unidades atualizadas (max 10 linhas):")
                for row in sample:
                    logging.info(row)

    except Exception as exc:
        logging.exception("Erro durante a execucao do script: %s", exc)
        if conn is not None:
            conn.rollback()
        sys.exit(1)
    finally:
        if conn is not None:
            conn.close()
            logging.info("Conexao com o banco encerrada.")


if __name__ == "__main__":
    main()
