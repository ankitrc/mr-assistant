"""Visits and KPIs: history, coverage and compliance, pending visits, rep KPIs."""

from datetime import date, time

from mr_assistant.db import Db
from mr_assistant.tools._base import Out, month_or_current
from mr_assistant.tools.doctors import _visible


class VisitRecord(Out):
    call_id: int
    call_date: date
    call_start_time: time
    duration_minutes: int | None
    call_type: str
    call_status: str
    clinic_name: str
    joint_working_with: str | None
    brands_detailed: list[str]
    samples_given: list[str]


class ComplianceRow(Out):
    year_month: int
    territory_id: int
    doctor_id: int
    doctor_name: str
    doctor_class: str
    visit_frequency: str
    required_visits: int
    visits_done: int
    visits_pending: int
    is_covered: bool
    is_compliant: bool
    last_visit_date: date | None


class RepKpi(Out):
    year_month: int
    territory_id: int
    employee_name: str | None
    listed_doctors: int
    covered_doctors: int
    compliant_doctors: int
    visits_pending: int
    mcr_pct: float
    mvc_pct: float
    mcr_target_pct: float | None
    mvc_target_pct: float | None
    mcr_met: bool | None
    mvc_met: bool | None
    calls_completed: int | None
    field_days: int | None
    calls_per_day: float | None
    calls_per_day_target: float
    call_band: str
    avg_call_minutes: float | None
    joint_working_days: int | None
    is_month_to_date: bool


def get_visit_history(db: Db, doctor_id: int, limit: int = 10) -> list[VisitRecord]:
    """Most recent calls to a doctor (newest first): date, time, type, who joined, brands detailed, samples."""
    _visible(db, doctor_id)
    rows = db.all("""
        SELECT c.call_id, c.call_date, c.call_start_time, c.duration_minutes, c.call_type, c.call_status,
               k.clinic_name, analytics.employee_name(c.joint_working_employee_id) AS joint_working_with,
               COALESCE(ARRAY(SELECT b.brand_name FROM core.dcr_call_product p JOIN analytics.brand b USING (brand_code)
                              WHERE p.call_id = c.call_id AND p.line_type = 'detailing' ORDER BY p.sequence_no), '{}')
                   AS brands_detailed,
               COALESCE(ARRAY(SELECT pr.sku_name || ' x' || p.quantity FROM core.dcr_call_product p
                              JOIN core.product pr USING (sku_code)
                              WHERE p.call_id = c.call_id AND p.line_type = 'sample'), '{}') AS samples_given
        FROM core.dcr_call c JOIN core.clinic k USING (clinic_id)
        WHERE c.doctor_id = %s
        ORDER BY c.call_date DESC, c.call_start_time DESC
        LIMIT %s""", (doctor_id, limit))
    return [VisitRecord(**r) for r in rows]


def get_visit_compliance(db: Db, year_month: int | None = None, doctor_class: str | None = None,
                         only_pending: bool = False, territory_id: int | None = None,
                         limit: int = 500) -> list[ComplianceRow]:
    """Per doctor for a month (default: current, month-to-date): required, done and pending visits,
    covered (met at least once) and compliant (met as often as required)."""
    ym = month_or_current(db, year_month)
    rows = db.all("""
        SELECT v.*, d.full_name AS doctor_name
        FROM analytics.doctor_visit_compliance v JOIN core.doctor d USING (doctor_id)
        WHERE v.year_month = %(ym)s
          AND (%(cls)s::text IS NULL OR v.doctor_class = %(cls)s)
          AND (NOT %(pending)s OR v.visits_pending > 0)
          AND (%(terr)s::bigint IS NULL OR v.territory_id = %(terr)s)
        ORDER BY v.doctor_class, v.visits_pending DESC, d.full_name
        LIMIT %(limit)s""", {"ym": ym, "cls": doctor_class, "pending": only_pending, "terr": territory_id,
                             "limit": limit})
    return [ComplianceRow(**{k: r[k] for k in ComplianceRow.model_fields}) for r in rows]


def get_pending_visits(db: Db, year_month: int | None = None, territory_id: int | None = None,
                       limit: int = 20) -> list[ComplianceRow]:
    """Doctors still owed visits this month (or a given month), most overdue first:
    A-class before B and C, then the longest since the last visit."""
    ym = month_or_current(db, year_month)
    rows = db.all("""
        SELECT v.*, d.full_name AS doctor_name
        FROM analytics.doctor_visit_compliance v JOIN core.doctor d USING (doctor_id)
        WHERE v.year_month = %(ym)s AND v.visits_pending > 0
          AND (%(terr)s::bigint IS NULL OR v.territory_id = %(terr)s)
        ORDER BY v.doctor_class, v.last_visit_date NULLS FIRST, d.full_name
        LIMIT %(limit)s""", {"ym": ym, "terr": territory_id, "limit": limit})
    return [ComplianceRow(**{k: r[k] for k in ComplianceRow.model_fields}) for r in rows]


def get_rep_kpis(db: Db, year_month: int | None = None, territory_id: int | None = None) -> list[RepKpi]:
    """KPIs for a month (default: current, month-to-date), one row per visible territory:
    MCR coverage %, multi-visit compliance %, calls per day, each against its target."""
    ym = month_or_current(db, year_month)
    rows = db.all("""SELECT * FROM analytics.rep_monthly_kpi
                     WHERE year_month = %(ym)s AND (%(terr)s::bigint IS NULL OR territory_id = %(terr)s)
                     ORDER BY territory_id""", {"ym": ym, "terr": territory_id})
    return [RepKpi(**{k: r[k] for k in RepKpi.model_fields}) for r in rows]


def get_kpi_trend(db: Db, months: int = 6, territory_id: int | None = None) -> list[RepKpi]:
    """KPIs for the last `months` months (oldest first), per visible territory."""
    rows = db.all("""
        SELECT * FROM analytics.rep_monthly_kpi
        WHERE year_month > analytics.ym_add((SELECT analytics.ym_of(analytics.as_of_date())), -%(m)s)
          AND (%(terr)s::bigint IS NULL OR territory_id = %(terr)s)
        ORDER BY territory_id, year_month""", {"m": months, "terr": territory_id})
    return [RepKpi(**{k: r[k] for k in RepKpi.model_fields}) for r in rows]
