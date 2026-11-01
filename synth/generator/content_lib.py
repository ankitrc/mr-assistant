"""Approved content library (built here so call product lines can reference
content ids). Key messages and claims are placeholders to be replaced with
medically / regulatorily approved text."""

from datetime import date
from functools import lru_cache

import numpy as np

from generator import catalog, config

LANG_BY_SBU = {catalog.R: ["ta", "mr", "bn"], catalog.D: ["mr", "hi"]}
PATIENT_TOPIC = {
    "Respiratory": "Inhaler technique guide for patients",
    "Metabolic": "Lifestyle and diet guide for patients",
    "Diabetes": "Diabetes self-care and diet chart",
    "Cardiovascular": "Blood pressure and heart health guide",
}


@lru_cache(maxsize=1)
def items():
    rng = np.random.default_rng(config.SEEDS["content"])
    out, cid = [], 600001
    for code, (name, sbu, therapy, cls, gb, device, *_rest) in catalog.BRANDS.items():
        specs = [s for s, lst in catalog.PRIORITY[sbu].items() if code in lst]
        ref = lambda: f"MRA-{int(rng.integers(2024, 2027))}-{int(rng.integers(1000, 9999))}"
        title = name.title()

        def add(ctype, t, msg, approved, expires, lang="en", status="active"):
            nonlocal cid
            out.append({"content_id": cid, "brand_code": code, "title": t, "content_type": ctype,
                        "target_specialties": specs, "key_message": msg,
                        "approved_claims": "[Placeholder: approved claim text to be supplied by medical/regulatory]",
                        "language": lang, "review_reference": ref(), "approved_on": approved, "expires_on": expires,
                        "file_blob_path": f"content/{code}/{cid}.{'mp4' if ctype == 'video' else 'pdf'}",
                        "status": status, "embedding": None})
            cid += 1

        if device:
            add("video", f"{title}: device demonstration", f"How to use the {title} device correctly",
                date(2024, 4, 1), date(2027, 3, 31))
            add("leaflet", f"{title}: patient device guide", "Step-by-step device use for patients",
                date(2024, 4, 1), date(2027, 3, 31))
            continue
        add("visual_aid", f"{title} detailing aid v1", f"[Placeholder key message for {title}]",
            date(2024, 4, 1), date(2025, 6, 30), status="expired")
        add("visual_aid", f"{title} detailing aid v2", f"[Placeholder key message for {title}, 2025 update]",
            date(2025, 7, 1), date(2026, 12, 31))
        add("study_summary", f"{title}: summary of prescribing information", "Approved prescribing information, one page",
            date(2024, 4, 1), date(2027, 3, 31))
        add("leaflet", f"{title}: {PATIENT_TOPIC[therapy].lower()}", PATIENT_TOPIC[therapy],
            date(2024, 6, 1), date(2027, 3, 31))
        add("leaflet", f"{title}: {PATIENT_TOPIC[therapy].lower()} (regional)", PATIENT_TOPIC[therapy],
            date(2024, 6, 1), date(2027, 3, 31), lang=str(rng.choice(LANG_BY_SBU[sbu])))
        add("email_template", f"{title}: doctor update email", f"Short update on {title} with link to prescribing information",
            date(2025, 1, 1), date(2026, 12, 31))
        add("whatsapp_template", f"{title}: follow-up message", f"Thank-you note after a visit, with the {title} leaflet",
            date(2025, 1, 1), date(2026, 12, 31))
        if gb:
            add("visual_aid", f"{title} campaign aid (withdrawn)", f"[Placeholder key message for {title}, campaign]",
                date(2025, 3, 1), date(2026, 3, 31), status="withdrawn")
    return out


def valid(brand, ctype, day):
    return [c for c in items() if c["brand_code"] == brand and c["content_type"] == ctype
            and c["status"] != "withdrawn" and c["approved_on"] <= day <= c["expires_on"]]
