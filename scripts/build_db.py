"""Build the database: recreate schema `core` from db/schema.sql, load all
Parquet files (data/parquet, data-v2) into it, then create the gold views in
schema `analytics` (db/views.sql), descriptions (db/comments.sql) and row-level
security (db/security.sql) - one command, one transaction.

Every row passes the schema's keys, foreign keys and checks; any violation
aborts the whole build and leaves the previous database untouched.
Naive timestamps in the Parquet files are local India time (IST).

    python scripts/build_db.py
"""

import hashlib
import json
import os
import sys
import time
from pathlib import Path

import duckdb
import psycopg
from dotenv import load_dotenv
from psycopg import sql

ROOT = Path(__file__).resolve().parent.parent
PARQUET = ROOT / "data" / "parquet"
SCHEMA_SQL = ROOT / "db" / "schema.sql"
VIEWS_SQL = ROOT / "db" / "views.sql"
SECURITY_SQL = ROOT / "db" / "security.sql"
COMMENTS_SQL = ROOT / "db" / "comments.sql"
MANIFEST = ROOT / "data" / "DATA_VERSION.json"

# parents before children (foreign-key order)
ORDER = ["calendar_day", "business_unit", "geography", "employee", "product", "content", "doctor", "clinic",
         "chemist", "mcl", "tour_plan", "kpi_target", "dcr_call", "dcr_call_product", "call_note", "rcpa_entry",
         "doctor_brand_plan", "formulary_listing", "communication", "nba_recommendation", "agent_action_log"]


def dsn() -> str:
    load_dotenv(ROOT / ".env")
    e = os.environ
    return (f"host={e['POSTGRES_HOST']} port={e['POSTGRES_PORT']} dbname={e['POSTGRES_DB']} "
            f"user={e['POSTGRES_USER']} password={e['POSTGRES_PASSWORD']}")


def verify_frozen_data() -> str:
    """The dataset is frozen: refuse to build if any Parquet file differs from the manifest."""
    manifest = json.loads(MANIFEST.read_text())
    changed = [name for name, meta in manifest["files"].items()
               if not (PARQUET / name).exists()
               or hashlib.sha256((PARQUET / name).read_bytes()).hexdigest() != meta["sha256"]]
    if changed:
        sys.exit(f"Data differs from {manifest['data_version']} (frozen): {changed}. Restore the original files.")
    return manifest["data_version"]


def main() -> None:
    missing = [t for t in ORDER if not (PARQUET / f"{t}.parquet").exists()]
    if missing:
        sys.exit(f"Missing Parquet files: {missing}")
    version = verify_frozen_data()
    print(f"data version {version}: checksums OK")

    started = time.time()
    duck = duckdb.connect()
    counts = {}
    with psycopg.connect(dsn()) as pg:                 # one transaction for everything
        pg.execute(SCHEMA_SQL.read_text())
        pg.execute("SET TIME ZONE 'Asia/Kolkata'")
        for table in ORDER:
            path = PARQUET / f"{table}.parquet"
            described = duck.execute(f"DESCRIBE SELECT * FROM '{path}'").fetchall()
            names = [d[0] for d in described]
            # list-of-struct columns (clinic timings) go in as JSON text; Postgres parses them into jsonb
            select = ", ".join(f'CAST(to_json("{n}") AS VARCHAR)' if "STRUCT" in t else f'"{n}"'
                               for n, t, *_ in described)
            rows = duck.execute(f"SELECT {select} FROM '{path}'").fetchall()
            cols = ", ".join(f'"{n}"' for n in names)
            with pg.cursor().copy(f"COPY core.{table} ({cols}) FROM STDIN") as copy:
                for row in rows:
                    copy.write_row(row)
            counts[table] = len(rows)
            print(f"core.{table:20s} {len(rows):>8,d}")

        bad = []
        for table, n in counts.items():
            got = pg.execute(f"SELECT COUNT(*) FROM core.{table}").fetchone()[0]
            if got != n:
                bad.append(f"{table}: parquet {n} vs db {got}")
        if bad:
            raise SystemExit("Row count mismatch, nothing committed:\n" + "\n".join(bad))
        pg.execute(VIEWS_SQL.read_text())                 # gold views (schema analytics)
        pg.execute(COMMENTS_SQL.read_text())              # descriptions of every table, view and column
        pg.execute(SECURITY_SQL.read_text())              # role mr_app + row-level security
        pg.execute(sql.SQL("ALTER ROLE mr_app WITH LOGIN PASSWORD {}").format(
            sql.Literal(os.environ["POSTGRES_APP_PASSWORD"])))
        pg.execute("DROP SCHEMA IF EXISTS raw CASCADE")   # staging from earlier experiments, no longer used
        pg.execute("ANALYZE")
    print(f"\nBuilt schema core: {len(counts)} tables, {sum(counts.values()):,} rows, "
          f"all constraints satisfied ({time.time() - started:.0f}s).")


if __name__ == "__main__":
    main()
