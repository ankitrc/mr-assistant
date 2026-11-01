"""tour_plan: monthly plans from the field simulation (the same plan rows
dcr_call.tour_plan_id points to), next month's plan (November 2026) in
different approval states, and next-call slots booked from voice notes."""

from datetime import date, datetime, time, timedelta
from functools import lru_cache

import numpy as np
import pandas as pd

from generator import clinics, config, field_sim, notes, world
from generator.employee import REP_PROFILES
from generator.geography import TERRITORIES

NEXT_MONTH = date(2026, 11, 1)
# November plan status per BO (demo states)
NOV_STATUS = {990001: "approved", 990002: "draft", 990003: "approved", 990004: "submitted", 990005: "approved"}
AGENT_DRAFTED = {990001, 990003, 990005}


def _next_month_plan(start_id):
    """Plan for NEXT_MONTH using the same STP / MCL logic, own random stream."""
    rng = np.random.default_rng(config.SEEDS["tour_plan"] + 1)
    out, pid = [], start_id
    days = field_sim.month_days(NEXT_MONTH)
    for tid in TERRITORIES:
        emp, _ = world.bo_on(tid, config.AS_OF_DATE)
        working = [d for d in days if world.is_working_day(d, tid)]
        meeting = {working[int(rng.integers(min(6, len(working))))]}
        leave = {d for d in rng.choice([d for d in working if d not in meeting], int(rng.integers(0, 3)), replace=False)}
        field = [d for d in working if d not in meeting | leave]
        for d in days:
            act = ("holiday" if d.isoweekday() != 7 and not world.is_working_day(d, tid) else
                   "meeting" if d in meeting else "leave" if d in leave else None)
            if act:
                out.append(field_sim.PlanRow(pid, emp, tid, d, act)); pid += 1
        patch_days = {}
        for d in field:
            patch_days.setdefault(field_sim.stp_patch(tid, d), []).append(d)
        load = {d: 0 for d in field}
        for r in world.mcl_on(tid, NEXT_MONTH):
            chosen = []
            for _ in range(int(r["visit_frequency"][1])):
                pool = ([d for d in patch_days.get(r["patch_id"], []) if d not in chosen and load[d] < 13]
                        or [d for d in field if d not in chosen])
                pool.sort(key=lambda d: (-min([abs((d - c).days) for c in chosen] or [99]) // 5, load[d], rng.random()))
                chosen.append(pool[0]); load[pool[0]] += 1
            for d in sorted(chosen):
                out.append(field_sim.PlanRow(pid, emp, tid, d, "field_work", r["patch_id"], r["doctor_id"],
                                             r["clinic_id"], time(10, 0) if rng.random() < .5 else time(17, 0)))
                pid += 1
    return out


@lru_cache(maxsize=1)
def rows():
    rng = np.random.default_rng(config.SEEDS["tour_plan"])
    plan, calls = field_sim.simulate()
    cdf = pd.DataFrame(calls)
    worked = set(zip(cdf.employee_id, cdf.call_date))
    jw = cdf.dropna(subset=["joint_working_employee_id"]).groupby(["employee_id", "call_date"]) \
        .joint_working_employee_id.first().to_dict()
    nov = _next_month_plan(max(p.tour_plan_id for p in plan) + 1)
    all_plan = plan + nov

    # month-level submission / approval per employee
    month_meta = {}
    for p in all_plan:
        key = (p.employee_id, date(p.plan_date.year, p.plan_date.month, 1))
        if key in month_meta:
            continue
        m = key[1]
        kind = REP_PROFILES.get(p.employee_id, "steady")
        prev_end = m - timedelta(days=1)
        late = kind == "coverage_gap" and rng.random() < .3
        submitted = (datetime.combine(m + timedelta(days=int(rng.integers(0, 2))), time(9)) if late
                     else datetime.combine(prev_end - timedelta(days=int(rng.integers(2, 7))), time(18))) \
            + timedelta(minutes=int(rng.integers(0, 180)))
        if m == NEXT_MONTH:                      # next month's plan was submitted before the snapshot
            submitted = min(submitted, datetime.combine(config.AS_OF_DATE - timedelta(days=int(rng.integers(1, 4))),
                                                        time(18, 30)))
        manager = world.manager_of(p.employee_id, m)
        version = 2 if kind == "coverage_gap" and rng.random() < .2 else 1
        status, approved_by, approved_at = "approved", manager, submitted + timedelta(hours=int(rng.integers(6, 48)))
        approved_at = min(approved_at, config.LOAD_TS - timedelta(hours=2))      # nothing after the snapshot
        if m == NEXT_MONTH:
            status = NOV_STATUS[p.employee_id]
            if status == "draft":
                submitted, approved_by, approved_at = None, None, None
            elif status == "submitted":
                approved_by, approved_at = None, None
        pilot_month = m >= date(2026, 10, 1) and p.employee_id in AGENT_DRAFTED
        month_meta[key] = (status, version, submitted, approved_by, approved_at, pilot_month)

    out = []
    for p in all_plan:
        status, version, submitted, approved_by, approved_at, pilot_month = \
            month_meta[(p.employee_id, date(p.plan_date.year, p.plan_date.month, 1))]
        deviation = (p.activity_type == "field_work" and p.plan_date <= config.AS_OF_DATE
                     and (p.employee_id, p.plan_date) not in worked)
        out.append({
            "tour_plan_id": p.tour_plan_id, "employee_id": p.employee_id, "territory_id": p.territory_id,
            "plan_date": p.plan_date, "year_month": p.plan_date.year * 100 + p.plan_date.month,
            "activity_type": p.activity_type, "patch_id": p.patch_id, "doctor_id": p.doctor_id,
            "clinic_id": p.clinic_id, "planned_start_time": p.planned_start_time,
            "source": ("agent_suggested" if pilot_month and p.activity_type == "field_work" else
                       "stp_generated" if p.activity_type == "field_work" and rng.random() < .85 else "rep_created"),
            "status": status, "version": version, "submitted_at": submitted, "approved_by": approved_by,
            "approved_at": approved_at, "joint_working_employee_id": jw.get((p.employee_id, p.plan_date)),
            "is_deviation": deviation, "deviation_reason": "Unplanned leave / absence" if deviation else None,
            "booking_status": None, "booking_confirmed_at": None,
        })

    # booked next-call slots from confirmed voice notes, falling after the as-of date
    clinic = clinics.by_id()
    next_id = max(r["tour_plan_id"] for r in out) + 1
    planned = {(r["doctor_id"], r["plan_date"]) for r in out if r["doctor_id"]}
    territory_of = {world.bo_on(t, config.AS_OF_DATE)[0]: t for t in TERRITORIES}
    for n in notes.rows():
        if n["source"] != "voice" or n["status"] != "confirmed" or not n["next_call_date"]:
            continue
        d = n["next_call_date"]
        if not (config.AS_OF_DATE < d < date(2026, 12, 1)) or (n["doctor_id"], d) in planned:
            continue
        rec_mcl = next((r for r in world.mcl_on(territory_of[n["employee_id"]], d)
                        if r["doctor_id"] == n["doctor_id"]), None)
        if rec_mcl is None or not world.is_working_day(d, rec_mcl["territory_id"]):
            continue
        win = clinic[rec_mcl["clinic_id"]]["rep_visit_window"][0]["start_time"]
        confirmed_at = n["confirmed_at"] + timedelta(hours=int(rng.integers(2, 30)))
        confirmed = rng.random() < .6 and confirmed_at < config.LOAD_TS      # not confirmed yet at snapshot time
        meta = month_meta.get((n["employee_id"], date(d.year, d.month, 1)), ("submitted", 1, None, None, None, True))
        out.append({
            "tour_plan_id": next_id, "employee_id": n["employee_id"], "territory_id": rec_mcl["territory_id"],
            "plan_date": d, "year_month": d.year * 100 + d.month, "activity_type": "field_work",
            "patch_id": rec_mcl["patch_id"], "doctor_id": n["doctor_id"], "clinic_id": rec_mcl["clinic_id"],
            "planned_start_time": win, "source": "booked_slot", "status": meta[0], "version": meta[1],
            "submitted_at": meta[2], "approved_by": meta[3], "approved_at": meta[4],
            "joint_working_employee_id": None, "is_deviation": False, "deviation_reason": None,
            "booking_status": "confirmed" if confirmed else "requested",
            "booking_confirmed_at": confirmed_at if confirmed else None,
            "_note_id": n["note_id"],
        })
        planned.add((n["doctor_id"], d))
        next_id += 1
    return out
