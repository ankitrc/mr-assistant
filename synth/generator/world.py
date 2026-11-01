"""World model: everything the tables are drawn from, built once and
deterministically (fixed seeds). Tables of later phases (clinic,
chemist, tour_plan, ...) are written from the same model, so their IDs
always match what Phase 1 tables already reference.

Nothing here is written to disk by itself; table modules pick what they need.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from functools import lru_cache

import numpy as np

from generator import config, names
from generator.calendar_day import NATIONAL, REGIONAL
from generator.employee import ASSIGNMENTS, PEOPLE
from generator.geography import TERRITORIES

R, D = config.RESPI_BU, config.CARDIO_BU

SPECIALTY_MIX = {
    R: [("Chest Physician", .25), ("Pulmonologist", .10), ("ENT Specialist", .15),
        ("Paediatrician", .15), ("Consultant Physician", .20), ("General Practitioner", .15)],
    D: [("Diabetologist", .20), ("Endocrinologist", .08), ("Cardiologist", .15),
        ("Gastroenterologist", .07), ("Consultant Physician", .30), ("General Practitioner", .20)],
}
QUALIFICATION = {
    "Chest Physician": ["MBBS, MD (Respiratory Medicine)", "MBBS, DNB (Respiratory Diseases)", "MBBS, TDD"],
    "Pulmonologist": ["MBBS, MD (Pulmonary Medicine)", "MBBS, MD, DM (Pulmonary Medicine)"],
    "ENT Specialist": ["MBBS, MS (ENT)", "MBBS, DLO", "MBBS, DNB (ENT)"],
    "Paediatrician": ["MBBS, MD (Paediatrics)", "MBBS, DCH", "MBBS, DNB (Paediatrics)"],
    "Consultant Physician": ["MBBS, MD (General Medicine)", "MBBS, DNB (General Medicine)"],
    "General Practitioner": ["MBBS"],
    "Diabetologist": ["MBBS, MD, Fellowship in Diabetology", "MBBS, PG Diploma in Diabetology", "MBBS, MD (General Medicine)"],
    "Endocrinologist": ["MBBS, MD, DM (Endocrinology)"],
    "Cardiologist": ["MBBS, MD, DM (Cardiology)", "MBBS, DNB (Cardiology)"],
    "Gastroenterologist": ["MBBS, MD, DM (Gastroenterology)", "MBBS, DNB (Gastroenterology)"],
}
CONFERENCES = {
    "Chest Physician": "NAPCON", "Pulmonologist": "NAPCON", "ENT Specialist": "AOICON", "Paediatrician": "PEDICON",
    "Consultant Physician": "APICON", "General Practitioner": "APICON", "Diabetologist": "RSSDI",
    "Endocrinologist": "ESICON", "Cardiologist": "CSI annual conference", "Gastroenterologist": "ISGCON",
}
INTERESTS = {
    "Chest Physician": ["asthma", "COPD", "inhaler technique"], "Pulmonologist": ["severe asthma", "ILD", "COPD"],
    "ENT Specialist": ["allergic rhinitis", "sinusitis"], "Paediatrician": ["childhood asthma", "allergy"],
    "Consultant Physician": ["hypertension", "respiratory infections", "diabetes"],
    "General Practitioner": ["family medicine", "preventive care"],
    "Diabetologist": ["type 2 diabetes", "insulin initiation"], "Endocrinologist": ["diabetes", "thyroid disorders"],
    "Cardiologist": ["dyslipidaemia", "heart failure"], "Gastroenterologist": ["fatty liver disease", "NASH"],
}
COUNCIL = {
    "Tamil Nadu": ("Tamil Nadu Medical Council", "TNMC"), "Maharashtra": ("Maharashtra Medical Council", "MMC"),
    "West Bengal": ("West Bengal Medical Council", "WBMC"), "Delhi": ("Delhi Medical Council", "DMC"),
}
PERSONA = {
    "prescriber": ["Consistent Prescriber", "Occasional Prescriber", "New Prescriber", "Non Prescriber"],
    "behavioural": ["Conventional Doctor", "Evidence Seeker", "Early Adopter", "Relationship Driven"],
    "loyalty": ["Loyalist", "Potential Loyalist", "Brand Switcher", "Competitor Loyalist"],
    "digital": ["Digitally Active", "Digital Explorer", "Digital Inactive"],
}
CLASS_FREQ = {"A": "V3", "B": "V2", "C": "V1"}


@dataclass
class Clinic:
    clinic_id: int
    doctor_id: int
    patch_id: int
    clinic_type: str
    is_primary: bool
    latitude: float
    longitude: float


@dataclass
class Doctor:
    doctor_id: int
    territory_id: int
    attrs: dict                      # columns of the doctor table
    traits: dict                     # hidden ground truth
    clinics: list = field(default_factory=list)
    doctor_class: str = "C"


def _synthetic_reg(council_short, _year, number):
    """Registration numbers carry 'SYN' so they can never match a real doctor's registration."""
    return f"{council_short}-SYN-{number}"


def territory_state(tid):
    return TERRITORIES[tid][7]


def patches(tid):
    return [tid * 100 + i for i in range(1, 9)]


def patch_coords(pid):
    t = TERRITORIES[pid // 100]
    p = t[8][pid % 100 - 1]
    return p[3], p[4]


# ---------------------------------------------------------------- doctors
LISTED_PER_TERRITORY = 120
UNIVERSE_PER_TERRITORY = 172      # 120 listed + quarterly additions + never-listed


@lru_cache(maxsize=1)
def doctors():
    rng = np.random.default_rng(config.SEEDS["doctors"])
    out, used_codes, next_id, next_clinic = [], set(), 9_000_001, 80_000_001
    for tid, t in TERRITORIES.items():
        sbu, state = t[1], territory_state(tid)
        pool = names.BY_TERRITORY[tid]
        specs, weights = zip(*SPECIALTY_MIX[sbu])
        for k in range(UNIVERSE_PER_TERRITORY):
            spec = specs[rng.choice(len(specs), p=weights)]
            gender = "Female" if rng.random() < (0.45 if spec in ("Paediatrician", "General Practitioner") else 0.28) else "Male"
            first = rng.choice(pool["female" if gender == "Female" else "male"])
            full_name = f"{first} {rng.choice(pool['surname'])}"
            years = int(rng.integers(3, 38))
            birth = date(config.AS_OF_DATE.year - years - int(rng.integers(25, 29)), int(rng.integers(1, 13)), int(rng.integers(1, 29)))

            # hidden traits drive behaviour across all tables
            potential = rng.choice(["high", "medium", "low"], p=[.25, .40, .35])
            digital = float(np.clip(rng.normal(0.45 if years < 15 else 0.25, 0.2), 0, 1))
            loyalty = float(np.clip(rng.normal(0.5, 0.2), 0, 1))
            window = rng.choice(["morning", "evening", "both"], p=[.35, .45, .20])
            preferred_channel = ("whatsapp" if digital > .55 else "email" if digital > .35 else "in_person")

            while True:
                code = str(int(rng.integers(300000, 999999)))
                if code not in used_codes:
                    used_codes.add(code)
                    break
            council, short = COUNCIL[state]
            has_email = rng.random() < (0.55 + digital * 0.4)
            has_mobile = rng.random() < 0.9
            social = rng.random() < (0.15 + digital * 0.5) and spec != "General Practitioner"

            def consent(present, affinity):
                if not present:
                    return "unknown"
                r = rng.random()
                return "opted_in" if r < affinity else "opted_out" if r < affinity + 0.08 else "unknown"

            fn = full_name.lower().replace("'", "").split()
            handle = f"dr-{'-'.join(fn)}-{code[-4:]}"
            interests = INTERESTS[spec]
            attrs = {
                "doctor_id": next_id, "doctor_code": code,
                "registration_no": _synthetic_reg(short, int(rng.integers(1990, 2023)), int(rng.integers(10000, 99999))),
                "registration_council": council, "full_name": full_name, "gender": gender, "birth_date": birth,
                "qualification": str(rng.choice(QUALIFICATION[spec])), "specialty": spec, "years_of_practice": years,
                "mobile": f"+910000{next_id % 1_000_000:06d}" if has_mobile else None,   # 0-prefix: not a valid mobile
                "email": f"{'.'.join(fn)}.{code[-3:]}@example.com" if has_email else None,
                "prescriber_persona": str(rng.choice(PERSONA["prescriber"], p=[.4, .3, .1, .2])),
                "behavioural_persona": str(rng.choice(PERSONA["behavioural"])),
                "loyalty_persona": PERSONA["loyalty"][0 if loyalty > .7 else 1 if loyalty > .5 else 2 if loyalty > .3 else 3],
                "digital_persona": PERSONA["digital"][0 if digital > .6 else 1 if digital > .35 else 2],
                "in_clinic_engagement": bool(rng.random() < 0.6),
                "patient_support": bool(rng.random() < 0.25),
                "scientific_engagement": bool(rng.random() < 0.2 + digital * 0.3),
                "scientific_out_clinic": bool(rng.random() < 0.15),
                "academy_member": bool(rng.random() < digital * 0.5),
                "digital_connect_member": bool(rng.random() < 0.15 + digital * 0.4),
                "patient_program_user": bool(rng.random() < (0.10 if sbu == D else 0.02)),
                "consent_email": consent(has_email, 0.3 + digital * 0.5),
                "consent_whatsapp": consent(has_mobile, 0.2 + digital * 0.6),
                "consent_sms": consent(has_mobile, 0.3),
                "consent_phone": consent(has_mobile, 0.6),
                "consent_updated_at": None,
                "linkedin_url": f"https://social.example.com/linkedin/{handle}" if social else None,
                "x_url": f"https://social.example.com/x/{handle}" if social and rng.random() < 0.3 else None,
                "public_bio": (f"{spec} practising in {t[3]}, {years} years of practice; interests in "
                               f"{', '.join(interests[:2])}.") if social else None,
                "recent_public_topics": ([f"Attended {CONFERENCES[spec]} {int(rng.choice([2025, 2026]))}",
                                          f"Shared an article on {rng.choice(interests)}"] if social else None),
                "social_compliance_approved": (bool(rng.random() < 0.85) if social else None),
                "mdm_status": "active", "merged_into_doctor_id": None,
            }
            if any(attrs[c] in ("opted_in", "opted_out") for c in
                   ("consent_email", "consent_whatsapp", "consent_sms", "consent_phone")):
                attrs["consent_updated_at"] = config.LOAD_TS - timedelta(days=int(rng.integers(30, 700)))
            traits = {"potential": str(potential), "digital_affinity": round(digital, 2), "loyalty": round(loyalty, 2),
                      "best_window": str(window), "preferred_channel": preferred_channel}
            doc = Doctor(next_id, tid, attrs, traits)

            # practice locations: primary clinic in one patch; specialists often also at a hospital
            home_patch = int(rng.choice(patches(tid), p=[.155, .155, .155, .155, .155, .155, .05, .02]))
            n_locations = 2 if (spec not in ("General Practitioner",) and rng.random() < 0.35) else 1
            for j in range(n_locations):
                pid = home_patch if j == 0 else int(rng.choice(patches(tid)[:6]))
                lat, lon = patch_coords(pid)
                doc.clinics.append(Clinic(next_clinic, next_id, pid,
                                          "private_clinic" if j == 0 else str(rng.choice(["hospital", "nursing_home"], p=[.7, .3])),
                                          j == 0, round(lat + rng.normal(0, .008), 6), round(lon + rng.normal(0, .008), 6)))
                next_clinic += 1
            out.append(doc)
            next_id += 1

    # MDM duplicates: 4 records later merged into an existing doctor (never used in activity)
    rng2 = np.random.default_rng(config.SEEDS["doctors"] + 1)
    for src in rng2.choice(len(out), 4, replace=False):
        s = out[int(src)]
        dup = dict(s.attrs)
        parts = dup["full_name"].split()
        dup.update({"doctor_id": next_id, "doctor_code": str(int(dup["doctor_code"]) + 1),
                    "full_name": f"{parts[0]} {parts[-1][0]}. {parts[-1]}" if len(parts[-1]) > 1 else dup["full_name"] + ".",
                    "mobile": None, "email": None, "linkedin_url": None, "x_url": None, "public_bio": None,
                    "recent_public_topics": None, "social_compliance_approved": None,
                    "consent_email": "unknown", "consent_whatsapp": "unknown", "consent_sms": "unknown",
                    "consent_phone": "unknown", "consent_updated_at": None,
                    "mdm_status": "merged", "merged_into_doctor_id": s.doctor_id})
        out.append(Doctor(next_id, s.territory_id, dup, {}, []))
        next_id += 1
    return out


def active_doctors(tid=None):
    return [d for d in doctors() if d.attrs["mdm_status"] == "active" and (tid is None or d.territory_id == tid)]


# ---------------------------------------------------------------- chemists (written in phase 3)
@lru_cache(maxsize=1)
def chemists():
    """chemist_id -> patch_id. 6 chemists per patch."""
    out, cid = {}, 70_000_001
    for tid in TERRITORIES:
        for pid in patches(tid):
            for _ in range(6):
                out[cid] = pid
                cid += 1
    return out


def chemists_in_patch(pid):
    return [c for c, p in chemists().items() if p == pid]


# ---------------------------------------------------------------- MCL history
def _quarter_starts():
    d, out = date(2024, 4, 1), []
    while d <= config.AS_OF_DATE:
        out.append(d)
        d = date(d.year + (d.month + 3 > 12), (d.month + 3 - 1) % 12 + 1, 1)
    return out


@lru_cache(maxsize=1)
def mcl_rows():
    """List of dicts: one per territory x doctor x validity period."""
    rng = np.random.default_rng(config.SEEDS["mcl"])
    rows, mcl_id = [], 1
    for tid in TERRITORIES:
        docs = active_doctors(tid)
        # rank by hidden potential so A/B/C classes are meaningful
        pot = {"high": 0, "medium": 1, "low": 2}
        ranked = sorted(docs, key=lambda d: (pot[d.traits["potential"]], rng.random()))
        listed = ranked[:LISTED_PER_TERRITORY]
        pool = [d for d in ranked[LISTED_PER_TERRITORY:]]
        rng.shuffle(pool)
        never_listed = set(d.doctor_id for d in pool[-18:])          # stay off-list (unplanned calls only)
        addable = [d for d in pool if d.doctor_id not in never_listed]

        def klass(d):
            return {"high": "A", "medium": "B", "low": "C"}[d.traits["potential"]]

        current = {}
        for d in listed:
            current[d.doctor_id] = {"doctor": d, "class": klass(d), "from": date(2024, 4, 1), "reason": "initial_list"}

        def close(doc_id, end):
            nonlocal mcl_id
            c = current.pop(doc_id)
            rows.append(_mcl_row(mcl_id, tid, c, end, rng))
            mcl_id += 1

        for q in _quarter_starts()[1:]:
            end = q - timedelta(days=1)
            # 3 removals, 3 additions, 4 reclassifications per quarter
            for doc_id in rng.choice(sorted(current), 3, replace=False):
                close(int(doc_id), end)
            for _ in range(3):
                if addable:
                    d = addable.pop()
                    current[d.doctor_id] = {"doctor": d, "class": klass(d), "from": q, "reason": "added"}
            established = sorted(d for d, c in current.items() if c["from"] < q)   # not added this quarter
            for doc_id in rng.choice(established, 4, replace=False):
                doc_id = int(doc_id)
                old = current[doc_id]
                new_class = {"A": "B", "B": str(rng.choice(["A", "C"])), "C": "B"}[old["class"]]
                close(doc_id, end)
                current[doc_id] = {"doctor": old["doctor"], "class": new_class, "from": q, "reason": "reclassified"}
        for doc_id in sorted(current):
            c = current[doc_id]
            rows.append(_mcl_row(mcl_id, tid, c, None, rng))
            mcl_id += 1
    for d in doctors():
        if d.attrs["mdm_status"] == "active":
            d.doctor_class = next((r["doctor_class"] for r in rows if r["doctor_id"] == d.doctor_id and r["is_current"]), "C")
    # position on the list: by class then name, for current rows
    for tid in TERRITORIES:
        cur = sorted([r for r in rows if r["territory_id"] == tid and r["is_current"]],
                     key=lambda r: (r["doctor_class"], r["_name"]))
        for i, r in enumerate(cur, 1):
            r["mcl_position"] = i
    return rows


def _mcl_row(mcl_id, tid, c, valid_to, rng):
    d = c["doctor"]
    primary = d.clinics[0]
    near = chemists_in_patch(primary.patch_id)
    freq = CLASS_FREQ[c["class"]]
    if c["class"] == "A" and rng.random() < 0.15:
        freq = "V2"
    return {
        "mcl_id": mcl_id, "territory_id": tid, "doctor_id": d.doctor_id, "clinic_id": primary.clinic_id,
        "patch_id": primary.patch_id, "doctor_class": c["class"], "visit_frequency": freq,
        "mcl_position": None, "linked_chemist_ids": [int(x) for x in rng.choice(near, int(rng.integers(1, 4)), replace=False)],
        "valid_from": c["from"], "valid_to": valid_to, "is_current": valid_to is None,
        "change_reason": c["reason"], "_name": d.attrs["full_name"],
    }


def mcl_on(tid, day):
    """MCL rows valid for a territory on a given day."""
    return [r for r in mcl_rows() if r["territory_id"] == tid and r["valid_from"] <= day
            and (r["valid_to"] is None or r["valid_to"] >= day)]


# ---------------------------------------------------------------- calendar helpers
def is_working_day(day, tid):
    if day.isoweekday() == 7 or day in NATIONAL:
        return False
    reg = REGIONAL.get(day)
    return not (reg and territory_state(tid) in reg[1])


def bo_on(tid, day):
    for emp, mgr, vf, vt in ASSIGNMENTS:
        p = PEOPLE[emp]
        if p[2] == "BO" and p[4] == tid and vf <= day and (vt is None or day <= vt):
            return emp, mgr
    return None, None


def manager_of(emp, day):
    for e, mgr, vf, vt in ASSIGNMENTS:
        if e == emp and vf <= day and (vt is None or day <= vt):
            return mgr
    return None
