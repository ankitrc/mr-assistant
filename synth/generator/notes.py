"""call_note: typed DCR remarks before the app pilot; voice notes (audio
path, transcript, extracted fields) from the pilot start. Text is built
from templates and the call's real content (brands detailed, samples)."""

from datetime import date, datetime, timedelta
from functools import lru_cache

import numpy as np

from generator import call_product, catalog, clinics, config, field_sim, world
from generator.employee import REP_PROFILES

OBJECTIONS = {
    "Respiratory": ["patients find inhalers difficult to use", "{he} prefers {comp} because it is cheaper",
                    "{he} is worried about the cost of long-term therapy", "{he} wants more local data on {brand}",
                    "patients stop inhalers once symptoms improve", "{brand} is often out of stock at the nearby chemist"],
    "other": ["patients are price sensitive", "{he} is comfortable with {comp}", "{he} wants long-term outcome data",
              "pill burden is a concern for older patients", "{brand} is often out of stock at the nearby chemist"],
}
DOC_COMMIT = ["will try {brand} in 2-3 new patients", "will review the {brand} prescribing information summary",
              "is open to a patient education camp next month", "will add {brand} for suitable follow-up patients"]
REP_COMMIT = ["share the {brand} prescribing information summary on WhatsApp", "check {brand} stock at the nearby chemist",
              "bring patient leaflets on the next visit", "arrange a call with the medical advisor"]
NEXT_STEP = ["Follow up on the patients started on {brand}", "Detail {brand} with the prescribing information summary",
             "Check feedback on the {brand} samples", "Discuss the patient education camp"]
TOPICS = {"Respiratory": ["inhaler technique", "seasonal cases", "pricing", "stock availability", "patient adherence"],
          "other": ["pricing", "stock availability", "patient adherence", "long-term outcomes", "new patients"]}
NOTE_RATE_TEXT = {"coverage_gap": .15}
NOTE_RATE_VOICE = {"star": .85, "declining": .7, "busy_but_ineffective": .6, "new_rep_handover": .9, "coverage_gap": .25}
FILLERS = ["okay so", "um", "basically", "actually", "you know"]


@lru_cache(maxsize=1)
def rows():
    rng = np.random.default_rng(config.SEEDS["notes"])
    _, calls = field_sim.simulate()
    lines = {}
    for r in call_product.rows():
        lines.setdefault(r["call_id"], []).append(r)
    doc_by_id = {d.doctor_id: d for d in world.doctors()}
    clinic = clinics.by_id()
    sku_name = {s[0]: s[1] for s in catalog.SKUS}
    out, nid = [], 1
    for c in calls:
        if c["call_status"] != "completed":
            continue
        kind = REP_PROFILES.get(c["employee_id"], "steady")
        pilot = c["call_date"] >= config.PILOT_START
        voice = pilot and rng.random() < NOTE_RATE_VOICE.get(kind, .5)
        if not voice and rng.random() >= (NOTE_RATE_TEXT.get(kind, .35) if not pilot else .1):
            continue
        doc = doc_by_id[c["doctor_id"]]
        ls = lines.get(c["call_id"], [])
        detailed = [l["brand_code"] for l in ls if l["line_type"] == "detailing" and not catalog.BRANDS[l["brand_code"]][5]]
        if not detailed:
            continue
        b1 = detailed[0]
        bname = catalog.display(b1)
        therapy = "Respiratory" if catalog.BRANDS[b1][2] == "Respiratory" else "other"
        comps = catalog.competitors_of(b1)
        comp = catalog.display(comps[0]) if comps else "a competitor brand"
        parts = doc.attrs["full_name"].split()
        surname = parts[0] if len(parts[-1]) <= 2 else parts[-1]          # "Senthil T" is addressed as Dr Senthil
        he = "she" if doc.attrs["gender"] == "Female" else "he"
        loyalty = doc.traits["loyalty"]

        objection = None
        competitor_push = (c["territory_id"] == 900003 and c["call_date"] >= date(2026, 7, 1) and rng.random() < .55)
        if competitor_push:
            objection = (f"the {catalog.display(catalog.AGGRESSIVE_COMPETITOR)} rep is visiting often "
                         f"with a patient support programme and {he} has moved some patients")
        elif rng.random() < .35:
            objection = str(rng.choice(OBJECTIONS[therapy])).format(brand=bname, comp=comp, he=he)
        doc_commit = str(rng.choice(DOC_COMMIT)).format(brand=bname) if rng.random() < .4 else None
        rep_commit = str(rng.choice(REP_COMMIT)).format(brand=bname) if rng.random() < .4 else None
        samples = [l for l in ls if l["line_type"] == "sample"]
        f = 2
        nxt = c["call_date"] + timedelta(days=int(30 / f) + int(rng.integers(-3, 4)))
        if nxt.isoweekday() == 7:
            nxt += timedelta(days=1)
        receptivity = ("low" if competitor_push or loyalty < .3 else "high" if loyalty > .6 and not objection else "medium")
        flags = ["off_label_mention"] if voice and rng.random() < .01 else []

        names = ", ".join(catalog.display(b) for b in detailed)
        parts_en = [f"Met Dr {surname} at {clinic[c['clinic_id']]['clinic_name']}.", f"Discussed {names}."]
        if objection:
            parts_en.append(f"Doctor mentioned that {objection}.")
        if doc_commit:
            parts_en.append(f"Doctor {doc_commit}.")
        for s in samples:
            parts_en.append(f"Gave {s['quantity']} units of {sku_name[s['sku_code']]}.")
        if rep_commit:
            parts_en.append(f"I will {rep_commit}.")
        if flags:
            parts_en.append(f"Doctor asked about using {bname} outside its approved use; I said I can only share "
                            f"approved information and will connect the medical team.")
        next_step = str(rng.choice(NEXT_STEP)).format(brand=bname)
        parts_en.append(f"Next visit around {nxt.strftime('%d %b')}.")
        transcript_en = " ".join(parts_en)
        summary = " ".join(parts_en[1:3]) if objection or doc_commit else parts_en[1]

        rec = {"note_id": nid, "call_id": c["call_id"], "employee_id": c["employee_id"], "doctor_id": c["doctor_id"],
               "source": "voice" if voice else "text", "audio_blob_path": None, "audio_duration_sec": None,
               "audio_format": None, "transcription_status": None, "language_detected": None,
               "transcript_raw": None, "transcript_en": None, "summary": summary if voice else transcript_en,
               "brands_discussed": detailed, "topics": list(rng.choice(TOPICS[therapy], 2, replace=False)),
               "objections": objection, "doctor_commitments": doc_commit, "rep_commitments": rep_commit,
               "next_step": next_step, "next_call_date": nxt, "doctor_receptivity": receptivity,
               "compliance_flags": flags or None, "status": "confirmed", "confirmed_at": None, "embedding": None}
        end_of_call = datetime.combine(c["call_date"], c["call_start_time"]) + timedelta(minutes=c["duration_minutes"])
        if voice:
            raw = []
            for i, s in enumerate(parts_en):
                s = s.replace("Met Dr", "met Dr").replace("I will", "I'll")
                raw.append((str(rng.choice(FILLERS)) + ", " if rng.random() < .35 or i == 0 else "") + s)
            rec.update({
                "recorded_at": end_of_call + timedelta(minutes=int(rng.integers(2, 30))),
                "audio_blob_path": f"call-notes/{c['territory_id']}/{c['call_date']:%Y/%m}/{nid}.webm",
                "audio_duration_sec": int(25 + 6 * len(parts_en) + rng.integers(0, 30)), "audio_format": "webm",
                "transcription_status": "done", "language_detected": "en",
                "transcript_raw": " ".join(raw), "transcript_en": transcript_en,
            })
            recent = (config.AS_OF_DATE - c["call_date"]).days <= 1
            if recent and rng.random() < .3:
                rec["status"] = "draft"
            elif rng.random() < .003:
                rec.update(transcription_status="failed", transcript_raw=None, transcript_en=None, status="draft",
                           summary=None, objections=None, doctor_commitments=None, rep_commitments=None,
                           topics=None, brands_discussed=None, next_step=None, next_call_date=None,
                           doctor_receptivity=None, compliance_flags=None)
            if rec["status"] == "confirmed":
                rec["confirmed_at"] = rec["recorded_at"] + timedelta(minutes=int(rng.integers(1, 20)))
        else:
            rec["recorded_at"] = c["submitted_at"]
            rec["confirmed_at"] = c["submitted_at"]
        out.append(rec)
        nid += 1
    return out
