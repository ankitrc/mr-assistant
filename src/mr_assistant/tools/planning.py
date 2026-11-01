"""Planning: rule-based doctor priority, tour plans, plan approval status, availability, calendar."""

from datetime import date, datetime, time

from mr_assistant.db import Db
from mr_assistant.errors import ToolError
from mr_assistant.tools._base import Out
from mr_assistant.tools.doctors import _visible

CLASS_POINTS = {"A": 30, "B": 20, "C": 10}
WEEKDAYS = {1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday", 5: "Friday", 6: "Saturday", 7: "Sunday"}


class PriorityDoctor(Out):
    doctor_id: int
    doctor_name: str
    territory_id: int
    doctor_class: str
    visits_pending: int
    days_since_last_visit: int | None
    own_rx_trend_pct: float | None
    score: float
    reasons: list[str]


class PlanEntry(Out):
    tour_plan_id: int
    plan_date: date
    activity_type: str
    doctor_id: int | None
    doctor_name: str | None
    patch_name: str | None
    planned_start_time: time | None
    source: str
    status: str
    booking_status: str | None
    is_deviation: bool


class PlanStatus(Out):
    employee_id: int
    employee_name: str | None
    territory_id: int
    year_month: int
    status: str
    version: int
    submitted_at: datetime | None
    approved_by: str | None
    approved_at: datetime | None
    planned_doctor_visits: int
    booked_slots: int
    deviations: int


class AvailabilityDay(Out):
    clinic_name: str
    weekday: int
    weekday_name: str
    opd_hours: list[str]
    rep_visit_hours: list[str]


class CalendarDay(Out):
    calendar_date: date
    day_name: str
    is_working_day: bool
    holiday_name: str | None


def get_priority_doctors(db: Db, limit: int = 10, territory_id: int | None = None) -> list[PriorityDoctor]:
    """Rule-based list of doctors to see next, highest priority first, with the reasons.

    Score = class points (A 30, B 20, C 10) + 8 per visit pending this month
            + 0.5 per day since the last visit (capped at 60 days)
            + 15 if own-brand Rx fell 25% or more vs the previous 3 months (with at least 10 Rx before).
    Only doctors with pending visits or a falling Rx are listed.
    """
    rows = db.all("""SELECT doctor_id, full_name, territory_id, doctor_class, visits_pending_this_month,
                            days_since_last_visit, own_rx_trend_pct, own_rx_prev_3m
                     FROM analytics.doctor_360
                     WHERE %(terr)s::bigint IS NULL OR territory_id = %(terr)s""", {"terr": territory_id})
    out = []
    for r in rows:
        pending = r["visits_pending_this_month"] or 0
        days = r["days_since_last_visit"]
        falling = (r["own_rx_trend_pct"] is not None and r["own_rx_trend_pct"] <= -25
                   and (r["own_rx_prev_3m"] or 0) >= 10)
        if pending == 0 and not falling:
            continue
        score = CLASS_POINTS[r["doctor_class"]] + 8 * pending + 0.5 * min(days if days is not None else 60, 60)
        reasons = [f"{r['doctor_class']}-class doctor"]
        if pending:
            reasons.append(f"{pending} visit(s) pending this month")
        if days is None:
            reasons.append("no completed visit on record")
        elif days >= 21:
            reasons.append(f"not visited for {days} days")
        if falling:
            score += 15
            reasons.append(f"own-brand Rx down {abs(r['own_rx_trend_pct']):.0f}% vs the previous 3 months")
        out.append(PriorityDoctor(doctor_id=r["doctor_id"], doctor_name=r["full_name"], territory_id=r["territory_id"],
                                  doctor_class=r["doctor_class"], visits_pending=pending, days_since_last_visit=days,
                                  own_rx_trend_pct=r["own_rx_trend_pct"], score=round(score, 1), reasons=reasons))
    out.sort(key=lambda p: (-p.score, p.doctor_name))
    return out[:limit]


def get_tour_plan(db: Db, start_date: date, end_date: date, territory_id: int | None = None) -> list[PlanEntry]:
    """Tour plan entries between two dates (inclusive): field visits, leave, meetings, holidays, booked slots."""
    if end_date < start_date:
        raise ToolError("end_date must not be before start_date.")
    rows = db.all("""
        SELECT t.tour_plan_id, t.plan_date, t.activity_type, t.doctor_id, d.full_name AS doctor_name,
               g.patch_name, t.planned_start_time, t.source, t.status, t.booking_status, t.is_deviation
        FROM core.tour_plan t
        LEFT JOIN core.doctor d USING (doctor_id)
        LEFT JOIN core.geography g ON g.patch_id = t.patch_id
        WHERE t.plan_date BETWEEN %(s)s AND %(e)s
          AND (%(terr)s::bigint IS NULL OR t.territory_id = %(terr)s)
        ORDER BY t.plan_date, t.planned_start_time NULLS FIRST, d.full_name""",
        {"s": start_date, "e": end_date, "terr": territory_id})
    return [PlanEntry(**r) for r in rows]


def get_plan_status(db: Db, year_month: int) -> list[PlanStatus]:
    """Monthly tour plan status per visible rep (draft / submitted / approved), with approver and counts."""
    rows = db.all("""
        SELECT t.employee_id, analytics.employee_name(t.employee_id) AS employee_name, t.territory_id, t.year_month,
               MAX(t.status) FILTER (WHERE t.source <> 'booked_slot') AS status,
               MAX(t.version) AS version, MAX(t.submitted_at) AS submitted_at,
               analytics.employee_name(MAX(t.approved_by)) AS approved_by, MAX(t.approved_at) AS approved_at,
               COUNT(*) FILTER (WHERE t.activity_type = 'field_work') AS planned_doctor_visits,
               COUNT(*) FILTER (WHERE t.source = 'booked_slot') AS booked_slots,
               COUNT(*) FILTER (WHERE t.is_deviation) AS deviations
        FROM core.tour_plan t
        WHERE t.year_month = %s
        GROUP BY t.employee_id, t.territory_id, t.year_month
        ORDER BY employee_name""", (year_month,))
    return [PlanStatus(**r) for r in rows]


def get_doctor_availability(db: Db, doctor_id: int, weekday: int | None = None) -> list[AvailabilityDay]:
    """When a doctor can be met: OPD hours and rep-visit hours per clinic and weekday (1 = Monday)."""
    _visible(db, doctor_id)
    rows = db.all("""
        WITH o AS (SELECT c.clinic_name, (w->>'weekday')::int AS weekday,
                          to_char((w->>'start_time')::time, 'HH24:MI') || '-' || to_char((w->>'end_time')::time, 'HH24:MI') AS hrs
                   FROM core.clinic c, jsonb_array_elements(c.opd_schedule) w WHERE c.doctor_id = %(d)s),
             r AS (SELECT c.clinic_name, (w->>'weekday')::int AS weekday,
                          to_char((w->>'start_time')::time, 'HH24:MI') || '-' || to_char((w->>'end_time')::time, 'HH24:MI') AS hrs
                   FROM core.clinic c, jsonb_array_elements(c.rep_visit_window) w WHERE c.doctor_id = %(d)s)
        SELECT clinic_name, weekday,
               COALESCE(ARRAY(SELECT hrs FROM o o2 WHERE o2.clinic_name = k.clinic_name AND o2.weekday = k.weekday ORDER BY hrs), '{}') AS opd_hours,
               COALESCE(ARRAY(SELECT hrs FROM r r2 WHERE r2.clinic_name = k.clinic_name AND r2.weekday = k.weekday ORDER BY hrs), '{}') AS rep_visit_hours
        FROM (SELECT clinic_name, weekday FROM o UNION SELECT clinic_name, weekday FROM r) k
        WHERE %(wd)s::int IS NULL OR weekday = %(wd)s
        ORDER BY weekday, clinic_name""", {"d": doctor_id, "wd": weekday})
    return [AvailabilityDay(weekday_name=WEEKDAYS[r["weekday"]], **r) for r in rows]


def get_calendar(db: Db, start_date: date, end_date: date, territory_id: int | None = None) -> list[CalendarDay]:
    """Working days and holidays between two dates for a territory's state (Sunday is the weekly off)."""
    terr = db.all("SELECT DISTINCT territory_id FROM core.geography")
    if territory_id is None:
        if len(terr) != 1:
            raise ToolError("You can see several territories; pass territory_id.")
        territory_id = terr[0]["territory_id"]
    state = db.scalar("SELECT state FROM core.geography WHERE territory_id = %s ORDER BY patch_id LIMIT 1", (territory_id,))
    if state is None:
        raise ToolError(f"Territory {territory_id} is not visible to you.")
    rows = db.all("""
        SELECT calendar_date, day_name,
               NOT (is_weekend OR is_national_holiday OR COALESCE(%(st)s = ANY (holiday_states), false)) AS is_working_day,
               CASE WHEN is_national_holiday OR %(st)s = ANY (holiday_states) THEN holiday_name END AS holiday_name
        FROM core.calendar_day WHERE calendar_date BETWEEN %(s)s AND %(e)s ORDER BY calendar_date""",
        {"st": state, "s": start_date, "e": end_date})
    return [CalendarDay(**r) for r in rows]
