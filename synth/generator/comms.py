"""communication: central email newsletters and webinar invites, rep WhatsApp
follow-ups (rep-written before the pilot, agent-drafted and rep-approved
after), a few inbound doctor messages. Consent is always respected; opens
and replies follow each doctor's hidden digital affinity and contact window."""

from datetime import date, datetime, time, timedelta
from functools import lru_cache

import numpy as np

from generator import catalog, config, content_lib, field_sim, notes, world
from generator.catalog import BUSINESS_UNITS
from generator.employee import PEOPLE
from generator.geography import TERRITORIES


def _open_time(day, window, rng):
    if window == "morning":
        t = time(7, 0) if rng.random() < .5 else time(13, 30)
    elif window == "evening":
        t = time(21, 0)
    else:
        t = time(8, 0) if rng.random() < .5 else time(21, 30)
    return datetime.combine(day, t) + timedelta(minutes=int(rng.integers(0, 120)))


@lru_cache(maxsize=1)
def rows():
    rng = np.random.default_rng(config.SEEDS["communication"])
    out = []
    docs = world.active_doctors()
    first_name = lambda d: d.attrs["full_name"].split()[0] if len(d.attrs["full_name"].split()[-1]) <= 2 \
        else d.attrs["full_name"].split()[-1]

    def add(**kw):
        base = {"employee_id": None, "campaign_id": None, "content_id": None, "subject": None, "body": None,
                "consent_checked": True, "approved_by": None, "approved_at": None, "sent_at": None,
                "delivered_at": None, "opened_at": None, "clicked_at": None, "responded_at": None, "response_type": None}
        base.update(kw)
        out.append(base)

    def engagement(rec, d, channel):
        dig = d.traits["digital_affinity"]
        if rng.random() < .02:
            rec["status"] = "failed"
            return
        rec["status"] = "delivered"
        rec["delivered_at"] = rec["sent_at"] + timedelta(seconds=int(rng.integers(5, 600)))
        p_open = (.15 + .6 * dig) if channel == "email" else (.55 + .4 * dig)
        if rng.random() < p_open:
            o = _open_time(rec["sent_at"].date() + timedelta(days=int(rng.integers(0, 3))), d.traits["best_window"], rng)
            rec["opened_at"] = max(o, rec["delivered_at"] + timedelta(minutes=1))
            if rng.random() < .35:
                rec["clicked_at"] = rec["opened_at"] + timedelta(minutes=int(rng.integers(0, 10)))
            p_resp = .05 if channel == "email" else (.15 + .35 * dig)
            if rng.random() < p_resp:
                rec["responded_at"] = rec["opened_at"] + timedelta(minutes=int(rng.integers(1, 240)))
                rec["response_type"] = "unsubscribed" if rng.random() < .03 else str(
                    rng.choice(["reply", "call_back"], p=[.8, .2]))

    # ---- central email newsletters (monthly) and webinar invites (quarterly)
    for m in field_sim.months():
        send_day = date(m.year, m.month, 15)
        if send_day > config.AS_OF_DATE:
            continue
        for d in docs:
            if d.attrs["consent_email"] != "opted_in":
                continue
            sbu = TERRITORIES[d.territory_id][1]
            gb = [b for b in catalog.BRANDS if catalog.BRANDS[b][1] == sbu and catalog.BRANDS[b][4]]
            tmpl = content_lib.valid(gb[m.month % len(gb)], "email_template", send_day)
            rec = dict(doctor_id=d.doctor_id, territory_id=d.territory_id, channel="email", direction="outbound",
                       campaign_id=f"NL-{sbu}-{m:%Y%m}", content_id=tmpl[0]["content_id"] if tmpl else None,
                       subject=f"{BUSINESS_UNITS[sbu][0].title()} update - {m:%B %Y}",
                       body="[Newsletter body from approved template]", generated_by="central",
                       sent_at=datetime.combine(send_day, time(10, 0)))
            engagement(rec, d, "email")
            add(**rec)
            if m.month in (2, 5, 8, 11):
                rec = dict(doctor_id=d.doctor_id, territory_id=d.territory_id, channel="webinar", direction="outbound",
                           campaign_id=f"WB-{sbu}-{m:%Y%m}", subject=f"Invitation: expert webinar, {m:%B %Y}",
                           body="[Webinar invitation from approved template]", generated_by="central",
                           sent_at=datetime.combine(send_day + timedelta(days=3), time(11, 0)))
                engagement(rec, d, "email")
                if rec.get("responded_at"):
                    rec["response_type"] = "registered"
                add(**rec)

    # ---- WhatsApp follow-ups after calls
    _, calls = field_sim.simulate()
    call_by_id = {c["call_id"]: c for c in calls}
    note_calls = {n["call_id"] for n in notes.rows()}
    doc_by_id = {d.doctor_id: d for d in docs}
    from generator import call_product
    first_brand = {}
    for l in call_product.rows():
        if l["line_type"] == "detailing" and l["call_id"] not in first_brand and not catalog.BRANDS[l["brand_code"]][5]:
            first_brand[l["call_id"]] = l["brand_code"]
    for c in calls:
        if c["call_status"] != "completed" or c["call_date"] < date(2025, 1, 1):
            continue
        d = doc_by_id[c["doctor_id"]]
        if d.attrs["consent_whatsapp"] != "opted_in" or c["call_id"] not in first_brand:
            continue
        pilot = c["call_date"] >= config.PILOT_START
        if rng.random() > (.35 if pilot else .15):
            continue
        b = first_brand[c["call_id"]]
        tmpl = content_lib.valid(b, "whatsapp_template", c["call_date"])
        rep = PEOPLE[c["employee_id"]][1]
        body = (f"Dear Dr {first_name(d)}, thank you for your time today. Sharing the {catalog.display(b)} "
                f"leaflet as discussed. Regards, {rep}, {config.COMPANY_NAME}")
        drafted = datetime.combine(c["call_date"], time(19, 0)) + timedelta(minutes=int(rng.integers(0, 90)))
        rec = dict(doctor_id=d.doctor_id, employee_id=c["employee_id"], territory_id=c["territory_id"],
                   channel="whatsapp", direction="outbound", content_id=tmpl[0]["content_id"] if tmpl else None,
                   body=body, generated_by="agent" if pilot else "rep")
        if pilot:
            r = rng.random()
            recent = (config.AS_OF_DATE - c["call_date"]).days <= 1
            if recent and r < .3:
                rec["status"] = "draft"
                add(**rec); continue
            if r < .1:
                rec.update(status="rejected", approved_by=c["employee_id"], approved_at=drafted + timedelta(minutes=5))
                add(**rec); continue
            rec.update(approved_by=c["employee_id"], approved_at=drafted + timedelta(minutes=int(rng.integers(1, 30))))
            rec["sent_at"] = rec["approved_at"] + timedelta(seconds=10)
        else:
            rec["sent_at"] = drafted
        engagement(rec, d, "whatsapp")
        add(**rec)

    # ---- inbound doctor messages
    for d in docs:
        if d.traits["digital_affinity"] < .6 or d.attrs["consent_whatsapp"] != "opted_in":
            continue
        for m in field_sim.months():
            if rng.random() < .05:
                day = m + timedelta(days=int(rng.integers(0, 27)))
                if day > config.AS_OF_DATE:
                    continue
                emp, _ = world.bo_on(d.territory_id, day)
                ts = _open_time(day, d.traits["best_window"], rng)
                add(doctor_id=d.doctor_id, employee_id=emp, territory_id=d.territory_id, channel="whatsapp",
                    direction="inbound", body=str(rng.choice([
                        "Please send the prescribing information again.", "Samples finished, please visit this week.",
                        "Can we meet on Thursday evening?", "Patient asking about availability at the local chemist."])),
                    generated_by="doctor", consent_checked=False, status="delivered", sent_at=ts, delivered_at=ts)

    # events after the snapshot have not happened yet
    for r in out:
        for col in ("opened_at", "clicked_at", "responded_at"):
            if r[col] is not None and r[col] >= config.LOAD_TS:
                r[col] = None
                if col == "responded_at":
                    r["response_type"] = None
        if r["opened_at"] is None:
            r["clicked_at"] = r["responded_at"] = r["response_type"] = None
    out.sort(key=lambda r: (r["sent_at"] or r.get("approved_at") or datetime(2100, 1, 1), r["doctor_id"]))
    for i, r in enumerate(out, 1):
        r["communication_id"] = i
    return out
