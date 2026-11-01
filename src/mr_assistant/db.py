"""Database access for agents and tools.

Every query runs inside `as_employee(employee_id)`: a read-only transaction on a
pooled connection with the user's identity set for row-level security. Postgres
then returns only rows that user may see - tools never filter by territory themselves.

    with as_employee(990001) as db:
        rows = db.all("SELECT * FROM analytics.rep_monthly_kpi")
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from mr_assistant.config import get_settings
from mr_assistant.errors import UnknownEmployee

_pool: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    """Connection pool for the application role, created on first use."""
    global _pool
    if _pool is None:
        s = get_settings()
        _pool = ConnectionPool(s.app_conninfo, min_size=s.pool_min_size, max_size=s.pool_max_size,
                               kwargs={"row_factory": dict_row}, open=True)
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


class Db:
    """Thin query helper bound to one transaction for one employee.

    Each query runs in its own savepoint: if one query fails, only that query is rolled back
    and the transaction stays usable, so an agent can recover and call the next tool.
    """

    def __init__(self, conn: Connection, employee_id: int):
        self.conn = conn
        self.employee_id = employee_id

    def _run(self, sql: str, params: dict[str, Any] | tuple | None, fetch: str) -> Any:
        with self.conn.transaction():                       # savepoint inside the outer transaction
            cur = self.conn.execute(sql, params)
            return cur.fetchall() if fetch == "all" else cur.fetchone()

    def all(self, sql: str, params: dict[str, Any] | tuple | None = None) -> list[dict[str, Any]]:
        return self._run(sql, params, "all")

    def one(self, sql: str, params: dict[str, Any] | tuple | None = None) -> dict[str, Any] | None:
        return self._run(sql, params, "one")

    def scalar(self, sql: str, params: dict[str, Any] | tuple | None = None) -> Any:
        row = self._run(sql, params, "one")
        return None if row is None else next(iter(row.values()))


@contextmanager
def as_employee(employee_id: int) -> Iterator[Db]:
    """Read-only transaction acting as `employee_id` (row-level security applies)."""
    with get_pool().connection() as conn:
        with conn.transaction():
            conn.execute("SET TRANSACTION READ ONLY")
            conn.execute("SELECT set_config('app.employee_id', %s, true)", (str(employee_id),))
            known = conn.execute("SELECT %s = ANY (core.visible_employee_ids()) AS ok",
                                 (employee_id,)).fetchone()["ok"]
            if not known:
                raise UnknownEmployee(f"Employee {employee_id} has no current assignment.")
            yield Db(conn, employee_id)
