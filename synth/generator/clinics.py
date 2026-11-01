"""clinic rows: names, addresses, pincodes and OPD / rep-visit timings.
Timings follow each doctor's hidden best contact window, so the call times
already in dcr_call fall inside them."""

from datetime import time
from functools import lru_cache

import numpy as np

from generator import config, world
from generator.geography import TERRITORIES

PIN = {"Chennai": "600", "Chengalpattu": "603", "Kanchipuram": "631", "Pune": "411", "Pimpri-Chinchwad": "411",
       "Talegaon Dabhade": "410", "Baramati": "413", "Kolkata": "700", "Howrah": "711", "Barasat": "700",
       "Mumbai": "400", "Thane": "400", "Navi Mumbai": "400", "New Delhi": "110", "Noida": "201", "Gurugram": "122"}
STREETS = ["Main Road", "Station Road", "Hospital Road", "Market Road", "Link Road", "Gandhi Road", "Nehru Street",
           "Temple Street", "Lake Road", "Park Avenue", "1st Cross Street", "2nd Main Road", "College Road"]
SPEC_WORD = {"Chest Physician": "Chest & Allergy Clinic", "Pulmonologist": "Lung Care Clinic", "ENT Specialist": "ENT Centre",
             "Paediatrician": "Child Care Clinic", "Consultant Physician": "Medical Centre", "General Practitioner": "Family Clinic",
             "Diabetologist": "Diabetes Care Centre", "Endocrinologist": "Endocrine & Diabetes Clinic",
             "Cardiologist": "Heart Clinic", "Gastroenterologist": "Gut & Liver Clinic"}
HOSPITAL = ["Hospital H-{n}, {p}"] * 6     # numbered: can never match a real hospital


def _week(days, start, end):
    return [{"weekday": d, "start_time": start, "end_time": end} for d in days]


@lru_cache(maxsize=1)
def rows():
    rng = np.random.default_rng(config.SEEDS["clinic"])
    out = []
    for d in world.active_doctors():
        parts = d.attrs["full_name"].split()
        surname = parts[0] if len(parts[-1]) <= 2 else parts[-1]          # "Senthil T" is addressed as Dr Senthil
        window = d.traits["best_window"]
        for c in d.clinics:
            t = TERRITORIES[d.territory_id]
            p = t[8][c.patch_id % 100 - 1]
            patch_name, city, state = p[0], p[1], p[2] or t[7]
            if c.clinic_type == "private_clinic":
                first, second = rng.random(), rng.random()            # same draws as before
                name = (f"Dr. {surname}'s Clinic" if first < .3
                        else f"{surname} {SPEC_WORD[d.attrs['specialty']]}" if second < .6
                        else f"Dr. {surname} {SPEC_WORD[d.attrs['specialty']]}")
                mon_sat = range(1, 7)
                opd = (_week(mon_sat, time(10, 0), time(13, 30)) if window == "morning"
                       else _week(mon_sat, time(17, 30), time(21, 0)) if window == "evening"
                       else _week(mon_sat, time(10, 0), time(13, 0)) + _week(mon_sat, time(18, 0), time(21, 0)))
                visit = (_week(mon_sat, time(12, 45), time(13, 45)) if window == "morning"
                         else _week(mon_sat, time(17, 0), time(17, 45)) if window == "evening"
                         else _week(mon_sat, time(17, 30), time(18, 0)))
            else:
                name = (str(rng.choice(HOSPITAL)).format(n=f"{c.clinic_id % 100:02d}", p=patch_name)
                        if c.clinic_type == "hospital" else f"{surname} Nursing Home")
                opd = _week(range(1, 6), time(9, 30), time(13, 0))
                visit = _week([2, 4], time(13, 0), time(14, 0))
            pincode = PIN[city] + f"{int(rng.integers(1, 120)):03d}"
            out.append({
                "clinic_id": c.clinic_id, "doctor_id": d.doctor_id, "clinic_name": name, "clinic_type": c.clinic_type,
                "is_primary": c.is_primary,
                "address": f"{int(rng.integers(1, 250))}, {rng.choice(STREETS)}, {patch_name}, {city} {pincode}",
                "city": city, "state": state, "pincode": pincode, "patch_id": c.patch_id,
                "latitude": c.latitude, "longitude": c.longitude, "opd_schedule": opd, "rep_visit_window": visit,
                "timing_source": str(rng.choice(["rep_reported", "doctor_confirmed", "inferred_from_calls"], p=[.7, .2, .1])),
            })
    return out


def by_id():
    return {r["clinic_id"]: r for r in rows()}
