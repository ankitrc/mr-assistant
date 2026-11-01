"""Field simulation: tour plan -> calls, per territory per month.

Built once, deterministically. Phase 1 writes the calls (dcr_call);
Phase 2 will write the plan rows (tour_plan) from the same simulation,
so dcr_call.tour_plan_id always matches.

Each BO's behaviour follows their hidden profile (answer key):
coverage, multi-visit compliance, calls per day, call length,
leave, manager joint working and DCR submission delay.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from functools import lru_cache

import numpy as np

from generator import config, world
from generator.employee import REP_PROFILES
from generator.geography import TERRITORIES


@dataclass
class PlanRow:
    tour_plan_id: int
    employee_id: int
    territory_id: int
    plan_date: date
    activity_type: str
    patch_id: int | None = None
    doctor_id: int | None = None
    clinic_id: int | None = None
    planned_start_time: time | None = None


def months():
    d = config.HISTORY_START
    while d <= config.AS_OF_DATE:
        yield d
        d = date(d.year + (d.month == 12), d.month % 12 + 1, 1)


def month_days(m):
    nxt = date(m.year + (m.month == 12), m.month % 12 + 1, 1)
    return [m + timedelta(days=i) for i in range((nxt - m).days)]


def profile(emp, m, rng):
    """Behaviour parameters for a BO in a month."""
    kind = REP_PROFILES.get(emp, "steady")
    idx = (m.year - config.HISTORY_START.year) * 12 + m.month - config.HISTORY_START.month
    last = (config.AS_OF_DATE.year - config.HISTORY_START.year) * 12 + config.AS_OF_DATE.month - config.HISTORY_START.month
    p = {"cov": .94, "mvc": .90, "cpd": 10.8, "dur": (7.0, 2.0), "leave": 1.2, "abm": 3, "late": .06, "priority": True}
    if kind == "star":
        p.update(cov=.99, mvc=.995, cpd=11.2, dur=(8.5, 2.0), leave=1.0, abm=4, late=.03)
    elif kind == "coverage_gap":
        p.update(cov=.86 if idx < last - 5 else .82, mvc=.70, cpd=9.1, dur=(6.5, 2.0), leave=1.6, abm=2, late=.25, priority=False)
    elif kind == "declining":
        recent = idx > last - 4
        p.update(cov=.955 if not recent else .93, mvc=.975 if not recent else .82, cpd=10.4, dur=(7.0, 2.0), leave=1.2, abm=3, late=.05)
    elif kind == "busy_but_ineffective":
        p.update(cov=.98, mvc=.97, cpd=13.3, dur=(3.8, 1.2), leave=1.0, abm=3, late=.04)
    elif kind == "new_rep_handover":
        k = min((m.year - 2026) * 12 + m.month - 7, 3)
        p.update(cov=[.62, .76, .86, .90][k], mvc=[.50, .68, .80, .86][k], cpd=[7.2, 8.6, 9.8, 10.4][k],
                 dur=(8.5, 2.0), leave=[0, 1, 1, 1][k], abm=[6, 5, 4, 4][k], late=.10, priority=k >= 2)
    elif emp == 990006 and m == date(2026, 6, 1):            # previous Delhi BO, notice period
        p.update(cov=.72, mvc=.60, cpd=8.2, leave=3)
    p["cov"] = float(np.clip(p["cov"] + rng.normal(0, .012), 0, 1))
    p["cpd"] = max(4.0, p["cpd"] + rng.normal(0, .3))
    return p


def stp_patch(tid, day):
    """Standard tour plan: weekday -> patch; ex-HQ on Wednesdays of weeks 2 and 4;
    outstation on the 3rd Thursday."""
    week = (day.day - 1) // 7 + 1
    wd = day.isoweekday()
    base = tid * 100
    if wd == 4 and week == 3:
        return base + 8
    if wd == 3 and week in (2, 4):
        return base + 7
    return base + wd                       # Mon..Sat -> patches 1..6


def _spread(cands, k):
    if k >= len(cands):
        return list(cands)
    idx = np.linspace(0, len(cands) - 1, k).round().astype(int)
    return [cands[i] for i in idx]


def _session_time(window, rng):
    w = window if window != "both" else rng.choice(["morning", "evening"])
    return "morning" if w == "morning" else "evening"


@lru_cache(maxsize=1)
def simulate():
    rng = np.random.default_rng(config.SEEDS["field"])
    plan, calls = [], []
    plan_id = 1
    doc_by_id = {d.doctor_id: d for d in world.doctors()}

    for tid in TERRITORIES:
        for m in months():
            days = month_days(m)
            # one BO per month; handovers fall on month boundaries
            emp, _ = world.bo_on(tid, days[0])
            working = [d for d in days if world.is_working_day(d, tid)]
            p = profile(emp, m, rng)

            # planned non-field days
            first_week = [d for d in working if d.day <= 7]
            meeting = {first_week[int(rng.integers(len(first_week)))]} if first_week else set()
            n_leave = int(min(rng.poisson(p["leave"]), 4))
            leave = set(rng.choice([d for d in working if d not in meeting], n_leave, replace=False)) if n_leave else set()
            field = [d for d in working if d not in meeting and d not in leave]
            sick = {d for d in field if rng.random() < .02}              # unplanned absence

            for d in days:
                if d.isoweekday() != 7 and not world.is_working_day(d, tid):
                    plan.append(PlanRow(plan_id, emp, tid, d, "holiday")); plan_id += 1
                elif d in meeting:
                    plan.append(PlanRow(plan_id, emp, tid, d, "meeting")); plan_id += 1
                elif d in leave:
                    plan.append(PlanRow(plan_id, emp, tid, d, "leave")); plan_id += 1

            listed = world.mcl_on(tid, days[0])
            patch_days = {}
            for d in field:
                patch_days.setdefault(stp_patch(tid, d), []).append(d)

            # ---- plan visits
            planned = {}                                            # doctor_id -> [PlanRow]
            plan_load = {d: 0 for d in field}
            order = list(range(len(listed)))
            rng.shuffle(order)
            for i in order:
                r = listed[i]
                f = int(r["visit_frequency"][1])
                cands = patch_days.get(r["patch_id"], [])
                chosen = []
                for _ in range(f):
                    pool = ([d for d in cands if d not in chosen and plan_load[d] < 13]
                            or [d for d in field if d not in chosen and plan_load[d] < 13]
                            or [d for d in field if d not in chosen])
                    # prefer days far from this doctor's other visits, then the least-loaded day
                    pool.sort(key=lambda d: (-min([abs((d - c).days) for c in chosen] or [99]) // 5,
                                             plan_load[d], rng.random()))
                    chosen.append(pool[0])
                    plan_load[pool[0]] += 1
                doc = doc_by_id[r["doctor_id"]]
                rows = []
                for d in sorted(chosen):
                    sess = _session_time(doc.traits["best_window"], rng)
                    st = time(10, 0) if sess == "morning" else time(17, 0)
                    pr = PlanRow(plan_id, emp, tid, d, "field_work", r["patch_id"], r["doctor_id"], r["clinic_id"], st)
                    rows.append(pr); plan_id += 1
                planned[r["doctor_id"]] = rows
            for r in listed:
                plan.extend(planned[r["doctor_id"]])

            # ---- execute (only up to the as-of date)
            live_field = [d for d in field if d <= config.AS_OF_DATE and d not in sick]
            if not live_field:
                continue
            weights = np.array([{"A": 3, "B": 2, "C": 1}[r["doctor_class"]] if p["priority"] else 1 for r in listed], float)
            n_met = int(round(p["cov"] * len(listed)))
            met = set(np.array([r["doctor_id"] for r in listed])[
                rng.choice(len(listed), n_met, replace=False, p=weights / weights.sum())])

            month_calls = []                                        # (day, doctor_id, plan_row|None, status)
            for r in listed:
                rows = [pr for pr in planned[r["doctor_id"]] if pr.plan_date in live_field]
                f = int(r["visit_frequency"][1])
                if r["doctor_id"] in met and rows:
                    k = f if (f == 1 or rng.random() < p["mvc"]) else int(rng.integers(1, f))
                    if config.AS_OF_DATE < max(field):                 # current month: only what's due so far
                        k = min(k, len(rows))
                    for pr in rows[:k]:
                        month_calls.append((pr.plan_date, r["doctor_id"], pr, "completed"))
                    missed = rows[k:]
                    # planned days lost (sick day / month not over): conscientious reps catch up unplanned
                    for _ in range(max(0, k - len(rows))):
                        if rng.random() < p["mvc"]:
                            month_calls.append((live_field[int(rng.integers(len(live_field)))], r["doctor_id"], None, "completed"))
                elif r["doctor_id"] in met:                          # planned days lost: meet on another day
                    month_calls.append((live_field[int(rng.integers(len(live_field)))], r["doctor_id"], None, "completed"))
                    missed = []
                else:
                    missed = rows
                for pr in missed:
                    if rng.random() < .3:
                        month_calls.append((pr.plan_date, r["doctor_id"], pr, "doctor_unavailable"))

            # fill to the BO's calls-per-day level with repeat and off-list calls (unplanned)
            target = int(round(p["cpd"] * len(live_field)))
            done = sum(1 for c in month_calls if c[3] == "completed")
            listed_ids = [r["doctor_id"] for r in listed]
            a_ids = [r["doctor_id"] for r in listed if r["doctor_class"] == "A" and r["doctor_id"] in met] or listed_ids
            off_list = [d.doctor_id for d in world.active_doctors(tid) if d.doctor_id not in set(listed_ids)]
            load = {}
            for c in month_calls:
                load[c[0]] = load.get(c[0], 0) + 1
            day_cap = int(np.ceil(p["cpd"] * 1.35)) + 1
            while done < target:
                doc_id = int(rng.choice(a_ids if rng.random() < .6 else (off_list or a_ids)))
                pid = doc_by_id[doc_id].clinics[0].patch_id
                open_days = [d for d in live_field if load.get(d, 0) < day_cap]
                if not open_days:
                    break
                options = [d for d in patch_days.get(pid, []) if d in open_days] if rng.random() < .7 else []
                pool = options or open_days
                day = pool[int(rng.integers(len(pool)))]
                month_calls.append((day, doc_id, None, "completed"))
                load[day] = load.get(day, 0) + 1
                done += 1

            # manager joint working days
            jw = {}
            for d in rng.choice(live_field, min(p["abm"], len(live_field)), replace=False):
                jw[d] = world.manager_of(emp, d)
            if m.month % 2 == 0 and live_field:
                d = live_field[int(rng.integers(len(live_field)))]
                abm = world.manager_of(emp, d)
                jw[d] = world.manager_of(abm, d)                    # RBM

            # ---- timestamps, places, submission
            by_day = {}
            for c in month_calls:
                dur = None if c[3] != "completed" else max(2, int(round(rng.normal(*p["dur"]))))
                by_day.setdefault(c[0], []).append((*c, dur))
            for day in sorted(by_day):
                sessions = {"morning": [], "evening": []}
                for c in by_day[day]:
                    sessions[_session_time(doc_by_id[c[1]].traits["best_window"], rng)].append(c)
                rng.shuffle(sessions["morning"]); rng.shuffle(sessions["evening"])
                # each session fits ~3.5-4 hours: move overflow to the other session
                cap = {"morning": 230, "evening": 235}
                need = lambda lst: sum((c[4] or 5) + 17 for c in lst)   # 17 = average travel gap + margin
                for a, b in (("morning", "evening"), ("evening", "morning"), ("morning", "evening")):
                    while need(sessions[a]) > cap[a] and need(sessions[b]) < cap[b]:
                        sessions[b].append(sessions[a].pop())
                for name, start, end in (("morning", time(9, 45), time(13, 45)), ("evening", time(17, 0), time(21, 0))):
                    total = need(sessions[name])
                    squeeze = min(1.0, cap[name] / total) if total else 1.0
                    work = sum((c[4] or 5) for c in sessions[name])
                    tight_gap = max(1, int((cap[name] - work) / max(1, len(sessions[name]))))
                    clock = datetime.combine(day, start) + timedelta(minutes=int(rng.integers(0, 15 if squeeze == 1 else 1)))
                    for c in sessions[name]:
                        doc = doc_by_id[c[1]]
                        status = c[3]
                        dur = c[4]
                        clinic = doc.clinics[1] if len(doc.clinics) > 1 and rng.random() < .2 else doc.clinics[0]
                        ctype = "in_clinic"
                        if status == "completed":
                            r_ = rng.random()
                            ctype = "phone" if r_ < .05 else "virtual" if r_ < .08 and doc.traits["digital_affinity"] > .5 else "in_clinic"
                        lat = lon = None
                        if ctype == "in_clinic":
                            lat = round(clinic.latitude + rng.normal(0, .0003), 6)
                            lon = round(clinic.longitude + rng.normal(0, .0003), 6)
                        delay = rng.random()
                        if delay < p["late"]:
                            sub = datetime.combine(day + timedelta(days=int(rng.integers(1, 3))), time(10, 0)) + timedelta(minutes=int(rng.integers(0, 180)))
                        else:
                            sub = datetime.combine(day, time(19, 30)) + timedelta(minutes=int(rng.integers(0, 240)))
                        calls.append({
                            "employee_id": emp, "territory_id": tid, "doctor_id": c[1],
                            "clinic_id": clinic.clinic_id, "patch_id": clinic.patch_id, "call_date": day,
                            "call_start_time": clock.time().replace(second=0), "duration_minutes": dur,
                            "call_type": ctype, "joint_working_employee_id": jw.get(day) if status == "completed" else None,
                            "tour_plan_id": c[2].tour_plan_id if c[2] else None, "is_planned": c[2] is not None,
                            "call_status": status, "submitted_at": min(sub, config.LOAD_TS - timedelta(hours=1)),
                            "checkin_latitude": lat, "checkin_longitude": lon,
                        })
                        gap = int(rng.integers(8, 26)) if squeeze == 1 else min(12, tight_gap)
                        clock += timedelta(minutes=(dur or 5) + gap)

    # one DCR submission per rep per day, after the day's last call (no extra random draws)
    by_rep_day = {}
    for c in calls:
        by_rep_day.setdefault((c["employee_id"], c["call_date"]), []).append(c)
    for (emp, day), day_calls in by_rep_day.items():
        last_end = max(datetime.combine(day, c["call_start_time"]) + timedelta(minutes=c["duration_minutes"] or 5)
                       for c in day_calls)
        submitted = max(max(c["submitted_at"] for c in day_calls), last_end + timedelta(minutes=20))
        for c in day_calls:
            c["submitted_at"] = min(submitted, config.LOAD_TS - timedelta(hours=1))
    calls.sort(key=lambda c: (c["call_date"], c["employee_id"], c["call_start_time"]))
    for i, c in enumerate(calls, 1):
        c["call_id"] = i
    return plan, calls
