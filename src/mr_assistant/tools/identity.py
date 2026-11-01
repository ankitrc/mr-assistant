"""Who is asking, their team, and the data snapshot."""

from datetime import date

from mr_assistant.db import Db
from mr_assistant.tools._base import Out


class Snapshot(Out):
    as_of_date: date
    current_year_month: int
    previous_year_month: int
    history_start_month: int


class MyProfile(Out):
    employee_id: int
    employee_code: str
    employee_name: str
    designation: str
    business_unit_id: int
    business_unit_name: str
    territory_id: int | None
    territory_name: str | None
    hq_name: str | None
    manager_name: str | None
    manager_designation: str | None
    joining_date: date


class TeamMember(Out):
    employee_id: int
    employee_name: str
    designation: str
    territory_id: int | None
    territory_name: str | None
    reports_to: str | None
    level: int


def get_snapshot(db: Db) -> Snapshot:
    """Data snapshot: as-of date ("today" for this dataset), current and previous month (YYYYMM)."""
    r = db.one("""SELECT analytics.as_of_date() AS as_of_date,
                         (SELECT analytics.ym_of(analytics.as_of_date())) AS current_year_month,
                         analytics.ym_add(analytics.ym_of(analytics.as_of_date()), -1) AS previous_year_month,
                         (SELECT analytics.ym_of(MIN(call_date)) FROM core.dcr_call) AS history_start_month""")
    return Snapshot(**r)


def get_my_profile(db: Db) -> MyProfile:
    """The current user: name, designation, business unit, territory (BOs), HQ and manager."""
    r = db.one("""
        SELECT e.employee_id, e.employee_code, e.employee_name, e.designation, e.business_unit_id,
               b.business_unit_name, e.territory_id,
               (SELECT MAX(territory_name) FROM core.geography g WHERE g.territory_id = e.territory_id) AS territory_name,
               (SELECT MAX(hq_name) FROM core.geography g WHERE g.hq_id = e.hq_id) AS hq_name,
               m.employee_name AS manager_name, m.designation AS manager_designation, e.joining_date
        FROM core.employee e
        JOIN core.business_unit b USING (business_unit_id)
        LEFT JOIN LATERAL analytics.employee_manager(e.employee_id) m ON true
        WHERE e.employee_id = %s AND e.is_current""", (db.employee_id,))
    return MyProfile(**r)


def get_team(db: Db) -> list[TeamMember]:
    """Everyone reporting to the current user (directly or indirectly). Empty for a BO."""
    rows = db.all("""
        WITH RECURSIVE tree AS (
            SELECT employee_id, 0 AS level FROM core.employee WHERE employee_id = %s AND is_current
            UNION ALL
            SELECT e.employee_id, t.level + 1 FROM core.employee e
            JOIN tree t ON e.manager_employee_id = t.employee_id WHERE e.is_current
        )
        SELECT e.employee_id, e.employee_name, e.designation, e.territory_id,
               (SELECT MAX(territory_name) FROM core.geography g WHERE g.territory_id = e.territory_id) AS territory_name,
               analytics.employee_name(e.manager_employee_id) AS reports_to, t.level
        FROM tree t JOIN core.employee e ON e.employee_id = t.employee_id AND e.is_current
        WHERE t.level > 0
        ORDER BY t.level, e.designation, e.employee_name""", (db.employee_id,))
    return [TeamMember(**r) for r in rows]
