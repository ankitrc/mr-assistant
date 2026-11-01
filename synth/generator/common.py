"""Typed Parquet writer and audit columns."""

import duckdb
import pandas as pd

from generator import config


def add_audit_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["created_at"] = config.LOAD_TS
    df["updated_at"] = config.LOAD_TS
    df["source_system"] = config.SOURCE_SYSTEM
    df["load_batch_id"] = config.LOAD_BATCH_ID
    return df


AUDIT_DDL = """,
    created_at      TIMESTAMP NOT NULL,
    updated_at      TIMESTAMP NOT NULL,
    source_system   VARCHAR   NOT NULL,
    load_batch_id   VARCHAR   NOT NULL"""


def write_parquet(name: str, df: pd.DataFrame, ddl_columns: str, exprs: dict | None = None) -> None:
    """Casts the frame into an explicit DuckDB schema, then writes Parquet,
    so column types in the file are exactly the designed types.
    exprs: optional SQL expression per column (e.g. JSON -> STRUCT[] casts)."""
    df = add_audit_columns(df)
    con = duckdb.connect()
    con.execute(f"CREATE TABLE {name} ({ddl_columns}{AUDIT_DDL})")
    con.register("src", df)
    cols = ", ".join(c.split()[0] for c in (ddl_columns + AUDIT_DDL).split(",\n")
                     if c.strip() and not c.strip().upper().startswith("PRIMARY KEY"))
    select = ", ".join((exprs or {}).get(c, c) for c in cols.split(", "))
    con.execute(f"INSERT INTO {name} ({cols}) SELECT {select} FROM src")
    config.PARQUET_DIR.mkdir(parents=True, exist_ok=True)
    out = config.PARQUET_DIR / f"{name}.parquet"
    con.execute(f"COPY {name} TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    con.close()
