"""
Bulk-load NCSBE flat files into PostgreSQL using psycopg v3 COPY.

The loader truncates the target table before loading (full-refresh model) so
each weekly snapshot replaces the previous one entirely.
"""

import time
from pathlib import Path

import psycopg
from django.db import connection

from apps.ncsbe.models import Voter, VoterEvent


def _get_psycopg_conn() -> psycopg.Connection:
    """Return a raw psycopg v3 connection using Django's database settings."""
    db = connection.settings_dict
    return psycopg.connect(
        host=db.get("HOST", "localhost"),
        port=int(db.get("PORT") or 5432),
        dbname=db["NAME"],
        user=db.get("USER", ""),
        password=db.get("PASSWORD", "") or "",
    )


def _copy_tsv_into_table(conn: psycopg.Connection, filepath: Path, table: str) -> int:
    """
    TRUNCATE *table* then stream *filepath* (tab-delimited, quoted, with header)
    into it via PostgreSQL COPY FROM STDIN.

    Returns the number of rows loaded.
    """
    copy_sql = (
        f"COPY {table} ({_column_list(conn, table)}) "
        f"FROM STDIN WITH (FORMAT csv, DELIMITER E'\\t', HEADER true, QUOTE '\"')"
    )

    with conn.cursor() as cur:
        print(f"  Truncating {table} …")
        cur.execute(f"TRUNCATE TABLE {table} RESTART IDENTITY")

        print(f"  Loading {filepath.name} → {table} …")
        with (
            filepath.open("r", encoding="utf-8", errors="replace") as fh,
            cur.copy(copy_sql) as copy,
        ):
            while True:
                data = fh.read(1024 * 1024)  # 1 MB chunks
                if not data:
                    break
                copy.write(data)

        cur.execute(f"SELECT COUNT(*) FROM {table}")
        row = cur.fetchone()
        return row[0] if row else 0


def _column_list(conn: psycopg.Connection, table: str) -> str:
    """
    Return a comma-separated list of non-auto-generated columns for *table*,
    excluding the Django-added 'id' auto-increment column so COPY can map by
    position without including it.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = %s
              AND column_name != 'id'
            ORDER BY ordinal_position
            """,
            (table,),
        )
        cols = [row[0] for row in cur.fetchall()]
    return ", ".join(cols)


def load_voter_file(filepath: Path) -> tuple[int, float]:
    """
    Load ncvoter_Statewide.txt into the Voter table.
    Returns (row_count, elapsed_seconds).
    """
    t0 = time.monotonic()
    with _get_psycopg_conn() as conn:
        count = _copy_tsv_into_table(conn, filepath, Voter._meta.db_table)
        conn.commit()
    elapsed = time.monotonic() - t0
    print(f"  Loaded {count:,} voter registration rows in {elapsed:.1f}s.")
    return count, elapsed


def load_history_file(filepath: Path) -> tuple[int, float]:
    """
    Load ncvhis_Statewide.txt into the VoterEvent table.
    Returns (row_count, elapsed_seconds).
    """
    t0 = time.monotonic()
    with _get_psycopg_conn() as conn:
        count = _copy_tsv_into_table(conn, filepath, VoterEvent._meta.db_table)
        conn.commit()
    elapsed = time.monotonic() - t0
    print(f"  Loaded {count:,} voter history rows in {elapsed:.1f}s.")
    return count, elapsed
