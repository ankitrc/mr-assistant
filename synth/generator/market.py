"""Market model: monthly potential and own-brand share per doctor x brand,
then RCPA audits (rcpa_entry), monthly doctor brand plans
(doctor_brand_plan) and hospital formulary listings.

Share responds to: doctor loyalty (hidden trait), visits in the previous
two months vs required frequency, brand launch ramp, respiratory
seasonality, and each territory's story:
  Chennai (star): share grows steadily.
  Pune (coverage gap): doctors not visited lose share (via visit effect).
  Kolkata (declining): from Jul 2026 A/B doctors lose share to one competitor.
  Mumbai (busy): short calls -> share drifts down slowly.
  Delhi (handover): dip in Jul-Aug 2026, recovering from Sep.
"""

from datetime import date, timedelta
from functools import lru_cache

import numpy as np
import pandas as pd

from generator import catalog, config, field_sim, world
from generator.geography import TERRITORIES

POS_WEIGHT = [1.0, .7, .55, .45, .35, .3]
POS_SHARE = [1.0, .85, .75, .7, .65, .6]
BASE_POTENTIAL = {"high": 70, "medium": 35, "low": 14}


def month_index(m):
    return (m.year - config.HISTORY_START.year) * 12 + m.month - config.HISTORY_START.month


def _launch_ramp(brand, m):
    launch = date.fromisoformat(catalog.BRANDS[brand][8])
    months_since = (m.year - launch.year) * 12 + m.month - launch.month
    return float(np.clip((months_since + 1) / 12, 0.05, 1.0))


def _story(tid, m, doctor_class, listed):
    k = month_index(m)
    if tid == 900001:
        return 1 + 0.006 * k
    if tid == 900003 and m >= date(2026, 7, 1) and listed and doctor_class in ("A", "B"):
        return max(0.55, 1 - 0.11 * ((m.year - 2026) * 12 + m.month - 6))
    if tid == 900004:
        return 1 - 0.003 * k
    if tid == 900005:
        return {date(2026, 7, 1): .85, date(2026, 8, 1): .82, date(2026, 9, 1): .9, date(2026, 10, 1): .96}.get(m, 1.0)
    return 1.0


@lru_cache(maxsize=1)
def visit_counts():
    _, calls = field_sim.simulate()
    df = pd.DataFrame(calls)
    df = df[df.call_status == "completed"]
    df["m"] = df.call_date.map(lambda d: date(d.year, d.month, 1))
    return df.groupby(["doctor_id", "m"]).size().to_dict()


def _prev_month(m, n=1):
    for _ in range(n):
        m = date(m.year - (m.month == 1), (m.month - 2) % 12 + 1, 1)
    return m


@lru_cache(maxsize=1)
def model():
    """Monthly potential and share per doctor x brand (dict keyed by (doctor_id, brand, month))."""
    rng = np.random.default_rng(config.SEEDS["market"])
    vc = visit_counts()
    out = {}
    months = list(field_sim.months())
    for tid in TERRITORIES:
        sbu = TERRITORIES[tid][1]
        mcl_by_month = {m: {r["doctor_id"]: r for r in world.mcl_on(tid, m)} for m in months}
        for d in world.active_doctors(tid):
            spec = d.attrs["specialty"]
            brands = catalog.brands_for(sbu, spec, include_device=False)
            size = BASE_POTENTIAL[d.traits["potential"]] * float(rng.lognormal(0, .25))
            s0 = float(np.clip(0.06 + 0.5 * d.traits["loyalty"] + rng.normal(0, .05), .02, .8))
            for pos, b in enumerate(brands):
                pot0 = size * POS_WEIGHT[min(pos, 5)]
                for m in months:
                    rec = mcl_by_month[m].get(d.doctor_id)
                    req = int(rec["visit_frequency"][1]) if rec else 0
                    v = vc.get((d.doctor_id, _prev_month(m)), 0) + vc.get((d.doctor_id, _prev_month(m, 2)), 0)
                    ratio = v / (2 * req) if req else min(v, 2) / 2
                    if _prev_month(m, 2) < config.HISTORY_START:      # no visit history before Nov 2024
                        ratio = 1.0
                    visit_factor = 0.8 + 0.25 * min(ratio, 1.2) / 1.2
                    season = catalog.RESPIRATORY_SEASON[m.month] if sbu == catalog.R else (1 + 0.004 * month_index(m))
                    potential = pot0 * season
                    share = s0 * POS_SHARE[min(pos, 5)] * visit_factor * _launch_ramp(b, m) * \
                        _story(tid, m, rec["doctor_class"] if rec else "C", rec is not None)
                    out[(d.doctor_id, b, m)] = {"potential_rx": potential, "share": float(np.clip(share, 0, .9)),
                                                "pos": pos, "listed": rec is not None,
                                                "class": rec["doctor_class"] if rec else None}
    return out


@lru_cache(maxsize=1)
def rcpa_rows():
    rng = np.random.default_rng(config.SEEDS["market"] + 1)
    mdl = model()
    doc_by_id = {d.doctor_id: d for d in world.doctors()}
    comp_mix = {}
    rows, rid = [], 1
    audit_p = {"A": .85, "B": .6, "C": .35, None: .15}
    for tid in TERRITORIES:
        sbu = TERRITORIES[tid][1]
        for m in field_sim.months():
            days = [x for x in field_sim.month_days(m) if world.is_working_day(x, tid) and x <= config.AS_OF_DATE]
            if not days:
                continue
            frac = len(days) / len([x for x in field_sim.month_days(m) if world.is_working_day(x, tid)])
            mcl_now = {r["doctor_id"]: r for r in world.mcl_on(tid, m)}
            for d in world.active_doctors(tid):
                brands = catalog.brands_for(sbu, d.attrs["specialty"], include_device=False)
                first = mdl[(d.doctor_id, brands[0], m)]
                if rng.random() > audit_p[first["class"]] * frac:
                    continue
                day = days[int(rng.integers(len(days)))]
                emp, _ = world.bo_on(tid, day)
                rec = mcl_now.get(d.doctor_id)
                chem = int(rng.choice(rec["linked_chemist_ids"])) if rec else \
                    int(rng.choice(world.chemists_in_patch(d.clinics[0].patch_id)))
                capture = 0.45 + 0.3 * ((d.doctor_id * 7 + chem) % 10) / 10
                for b in brands:
                    st = mdl[(d.doctor_id, b, m)]
                    total = int(rng.poisson(st["potential_rx"] * capture))
                    z = int(rng.binomial(total, st["share"]))
                    comps = catalog.competitors_of(b)
                    key = (d.doctor_id, b)
                    if key not in comp_mix:
                        comp_mix[key] = rng.dirichlet(np.ones(len(comps) + 1))     # last = unrecorded others
                    mix = comp_mix[key].copy()
                    if tid == 900003 and m >= date(2026, 7, 1) and catalog.AGGRESSIVE_COMPETITOR in comps:
                        mix[comps.index(catalog.AGGRESSIVE_COMPETITOR)] += 0.6
                        mix /= mix.sum()
                    rest = rng.multinomial(total - z, mix) if total - z > 0 else np.zeros(len(mix), int)
                    for code, rx in [(b, z)] + list(zip(comps, rest[:-1])):
                        if rx <= 0:
                            continue
                        units = catalog.BRANDS[b][7]
                        price = catalog.BRANDS[code][6] if code in catalog.BRANDS else catalog.COMPETITORS[code][3]
                        strips = round(rx * units * float(rng.uniform(.85, 1.15)), 1)
                        rows.append({"rcpa_id": rid, "audit_date": day, "year_month": day.year * 100 + day.month,
                                     "employee_id": emp, "territory_id": tid, "chemist_id": chem,
                                     "doctor_id": d.doctor_id, "brand_code": code, "prescriptions": int(rx),
                                     "quantity_strips": strips, "value_inr": round(strips * price, 2)})
                        rid += 1
    return rows


@lru_cache(maxsize=1)
def brand_plan_rows():
    mdl = model()
    rows = []
    for tid in TERRITORIES:
        sbu = TERRITORIES[tid][1]
        doc_by_id = {d.doctor_id: d for d in world.active_doctors(tid)}
        for m in field_sim.months():
            for rec in world.mcl_on(tid, m):
                d = doc_by_id[rec["doctor_id"]]
                spec = d.attrs["specialty"]
                full = catalog.PRIORITY[sbu][spec]
                for b in catalog.brands_for(sbu, spec, include_device=False):
                    st = mdl[(d.doctor_id, b, m)]
                    prev = mdl.get((d.doctor_id, b, _prev_month(m)), st)
                    pos = full.index(b) + 1
                    focus = pos <= 3 or catalog.BRANDS[b][4]
                    units, price = catalog.BRANDS[b][7], catalog.BRANDS[b][6]
                    prx = round(st["potential_rx"], 1)
                    t_rx = round(prx * min(.85, prev["share"] + .12), 1) if focus else None
                    rows.append({
                        "territory_id": tid, "doctor_id": d.doctor_id, "brand_code": b,
                        "year_month": m.year * 100 + m.month,
                        "potential_value_inr": round(prx * units * price, 2), "potential_rx": prx,
                        "potential_strips": round(prx * units, 1),
                        "target_value_inr": round(t_rx * units * price, 2) if focus else None,
                        "target_rx": t_rx, "target_strips": round(t_rx * units, 1) if focus else None,
                        "brand_priority": f"P{pos}", "brand_rank": pos, "is_focus_brand": bool(focus),
                    })
    return rows


@lru_cache(maxsize=1)
def formulary_rows():
    rng = np.random.default_rng(config.SEEDS["market"] + 2)
    rows, lid = [], 1
    start = date(2024, 4, 1)
    for d in world.active_doctors():
        sbu = TERRITORIES[d.territory_id][1]
        for c in d.clinics:
            if c.clinic_type != "hospital":
                continue
            for b in catalog.brands_for(sbu, d.attrs["specialty"], include_device=False)[:3]:
                status = str(rng.choice(["listed", "not_listed", "under_review"], p=[.5, .35, .15]))
                change = None
                if status == "under_review":
                    change = (date(2025, int(rng.integers(1, 13)), 1), str(rng.choice(["listed", "not_listed"], p=[.6, .4])))
                elif status == "not_listed" and rng.random() < .2:
                    change = (date(2026, int(rng.integers(7, 11)), 1), "listed")
                elif status == "listed" and rng.random() < (.25 if d.territory_id == 900003 else .05):
                    change = (date(2026, int(rng.integers(7, 11)), 1), "not_listed")
                if change and change[0] > config.AS_OF_DATE:
                    change = None
                end = change[0] - timedelta(days=1) if change else None
                rows.append({"listing_id": lid, "clinic_id": c.clinic_id, "brand_code": b, "listing_status": status,
                             "effective_from": start, "effective_to": end, "notes": None}); lid += 1
                if change:
                    note = {"listed": "Approved by hospital drug committee",
                            "not_listed": "Removed at formulary review"}[change[1]]
                    rows.append({"listing_id": lid, "clinic_id": c.clinic_id, "brand_code": b,
                                 "listing_status": change[1], "effective_from": change[0], "effective_to": None,
                                 "notes": note}); lid += 1
    return rows
