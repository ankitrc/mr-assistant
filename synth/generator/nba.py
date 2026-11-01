"""nba_recommendation: from the pilot start, each working morning every BO
gets up to 5 rule-based next best actions. Status reflects what the rep
actually did afterwards (calls, details, samples, messages already in the data)."""

from bisect import bisect_left, bisect_right
from datetime import date, datetime, time, timedelta
from functools import lru_cache

import numpy as np
import pandas as pd

from generator import call_product, catalog, comms, config, field_sim, market, notes, world
from generator.geography import TERRITORIES

ENGINE = "rules-v0.3"


@lru_cache(maxsize=1)
def rows():
    rng = np.random.default_rng(config.SEEDS["nba"])
    _, calls = field_sim.simulate()
    cdf = pd.DataFrame([c for c in calls if c["call_status"] == "completed"])
    visits = {k: sorted(v) for k, v in cdf.groupby("doctor_id").call_date.apply(list).items()}
    lines = pd.DataFrame(call_product.rows()).merge(cdf[["call_id", "doctor_id", "call_date"]], on="call_id")
    detailed = {k: sorted(v) for k, v in lines[lines.line_type == "detailing"].groupby(["doctor_id", "brand_code"]).call_date.apply(list).items()}
    sampled = {k: sorted(v) for k, v in lines[lines.line_type == "sample"].groupby("doctor_id").call_date.apply(list).items()}
    cm = pd.DataFrame(comms.rows())
    cm = cm[(cm.direction == "outbound") & cm.sent_at.notna() & cm.generated_by.isin(["rep", "agent"])]
    sent = {k: sorted(v) for k, v in cm.groupby("doctor_id").sent_at.apply(lambda s: [x.date() for x in s]).items()}
    rc = pd.DataFrame(market.rcpa_rows())
    rc = rc[rc.brand_code.isin(list(catalog.BRANDS))]
    nt = pd.DataFrame(notes.rows())
    nt = nt[nt.status == "confirmed"]
    doc_by_id = {d.doctor_id: d for d in world.doctors()}

    def any_between(lst, a, b):
        return lst is not None and bisect_right(lst, b) - bisect_left(lst, a) > 0

    out, rid = [], 1
    for tid in TERRITORIES:
        trc = rc[rc.territory_id == tid].sort_values("audit_date")
        tnt = nt[nt.employee_id.isin([e for e, _ in [world.bo_on(tid, config.AS_OF_DATE)]])]
        day = config.PILOT_START
        recent_shown = {}
        while day <= config.AS_OF_DATE:
            if not world.is_working_day(day, tid):
                day += timedelta(days=1); continue
            emp, _ = world.bo_on(tid, day)
            m0 = date(day.year, day.month, 1)
            listed = world.mcl_on(tid, day)
            cands = []
            for r in listed:
                v = visits.get(r["doctor_id"], [])
                done = bisect_left(v, day) - bisect_left(v, m0)
                if r["doctor_class"] in ("A", "B") and done < int(r["visit_frequency"][1]):
                    cands.append((.55 + (.2 if r["doctor_class"] == "A" else 0) + .05 * (day.day / 30),
                                  r["doctor_id"], "visit", None, ["pending_visit", f"class_{r['doctor_class']}"]))
            # RCPA decline: last two audits per doctor x brand before today
            past = trc[trc.audit_date < day]
            if len(past):
                g = past.groupby(["doctor_id", "brand_code"]).agg(rx=("prescriptions", list), last=("audit_date", "max"))
                for (doc_id, b), row in g.iterrows():
                    lst = row.rx
                    if (day - row["last"]).days <= 45 and len(lst) >= 2 and lst[-2] >= 6 and lst[-1] <= .6 * lst[-2]:
                        cands.append((.7 + min(.2, (lst[-2] - lst[-1]) / max(lst[-2], 1) * .3), doc_id,
                                      "detail_brand", b, ["rcpa_decline"]))
            recent_notes = tnt[(tnt.recorded_at < datetime.combine(day, time(7))) &
                               (tnt.recorded_at >= datetime.combine(day - timedelta(days=30), time(0)))]
            for _, n in recent_notes.iterrows():
                if isinstance(n.doctor_commitments, str) and "try" in n.doctor_commitments \
                        and not any_between(sampled.get(n.doctor_id), n.recorded_at.date(), day):
                    cands.append((.65, n.doctor_id, "give_sample", n.brands_discussed[0], ["trial_commitment"]))
                if isinstance(n.rep_commitments, str) and (day - n.recorded_at.date()).days <= 14:
                    cands.append((.6, n.doctor_id, "follow_up", None, ["open_commitment"]))
            for r in listed:
                d = doc_by_id[r["doctor_id"]]
                if d.attrs["consent_whatsapp"] == "opted_in" and d.traits["digital_affinity"] > .55 \
                        and not any_between(sent.get(d.doctor_id), day - timedelta(days=21), day):
                    cands.append((.5, d.doctor_id, "send_content", None, ["digital_responsive", "no_recent_touch"]))
            # pick top 5 distinct doctors, skipping the same advice shown in the last 3 days
            cands.sort(key=lambda c: -(c[0] + rng.normal(0, .05)))
            chosen, seen = [], set()
            quota = {"visit": 2, "detail_brand": 1, "give_sample": 1, "follow_up": 1, "send_content": 1}
            for sc, doc_id, action, brand, reasons in cands:
                key = (doc_id, action)
                if doc_id in seen or quota[action] == 0 or recent_shown.get(key, date(2000, 1, 1)) > day - timedelta(days=3):
                    continue
                quota[action] -= 1
                chosen.append((sc, doc_id, action, brand, reasons)); seen.add(doc_id); recent_shown[key] = day
                if len(chosen) == 5:
                    break
            if len(chosen) == 5 and not any(c[2] == "send_content" for c in chosen):
                digital = next((c for c in cands if c[2] == "send_content" and c[1] not in seen), None)
                if digital:
                    chosen[-1] = digital; recent_shown[(digital[1], "send_content")] = day
            for sc, doc_id, action, brand, reasons in chosen:
                horizon = min(day + timedelta(days=7), config.AS_OF_DATE)
                if action == "send_content":
                    done = any_between(sent.get(doc_id), day, horizon)
                elif action == "detail_brand":
                    done = any_between(detailed.get((doc_id, brand)), day, horizon)
                elif action == "give_sample":
                    done = any_between(sampled.get(doc_id), day, horizon)
                else:
                    done = any_between(visits.get(doc_id), day, horizon)
                if done:
                    status, at = "completed", datetime.combine(horizon, time(20, 0))
                else:
                    r = rng.random()
                    status = "dismissed" if r < .25 else "accepted" if r < .5 else "shown"
                    at = datetime.combine(day, time(9, int(rng.integers(0, 59))))
                out.append({"recommendation_id": rid, "generated_at": datetime.combine(day, time(7, 30)),
                            "employee_id": emp, "territory_id": tid, "doctor_id": doc_id, "action_type": action,
                            "brand_code": brand, "content_id": None, "reason_codes": reasons, "score": round(sc, 3),
                            "engine_version": ENGINE, "status": status, "status_at": at})
                rid += 1
            day += timedelta(days=1)
    return out
