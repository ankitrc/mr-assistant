"""dcr_call_product: brands detailed in each completed call (with seconds
and content shown) and samples / inputs given."""

from functools import lru_cache

import numpy as np

from generator import catalog, config, content_lib, field_sim, world
from generator.employee import REP_PROFILES
from generator.geography import TERRITORIES

INPUTS = {
    "Respiratory": ["Asthma action plan pad", "Inhaler technique leaflet", "Peak flow diary"],
    "Metabolic": ["Patient diet chart", "Liver health booklet"],
    "Diabetes": ["Diabetes diet chart", "Blood sugar diary"],
    "Cardiovascular": ["BP monitoring diary", "Heart health booklet"],
}


@lru_cache(maxsize=1)
def rows():
    rng = np.random.default_rng(config.SEEDS["call_product"])
    _, calls = field_sim.simulate()
    doc_by_id = {d.doctor_id: d for d in world.doctors()}
    skus_by_brand = {}
    for s in catalog.SKUS:
        if s[5]:
            skus_by_brand.setdefault(s[4], []).append(s[0])
    out, lid = [], 1
    for c in calls:
        if c["call_status"] != "completed":
            continue
        kind = REP_PROFILES.get(c["employee_id"], "steady")
        sbu = TERRITORIES[c["territory_id"]][1]
        brands = catalog.brands_for(sbu, doc_by_id[c["doctor_id"]].attrs["specialty"])
        drugs = [b for b in brands if not catalog.BRANDS[b][5]]
        n = {"star": 3, "busy_but_ineffective": 1 + int(rng.random() < .4)}.get(kind, 2 + int(rng.random() < .4))
        if c["call_type"] == "phone":
            n = 1
        if kind == "coverage_gap":
            chosen = list(rng.choice(drugs, min(n, len(drugs)), replace=False))
        else:
            chosen = drugs[:n]
        if "BR-RES-001" in brands and any(catalog.BRANDS[b][3] != "RES_LTRA" for b in chosen) and rng.random() < .2:
            chosen.append("BR-RES-001")
        total_sec = (c["duration_minutes"] or 0) * 60 * .8
        split = [.5, .3, .2, .1][:len(chosen)]
        split = [x / sum(split) for x in split]
        use_content = {"busy_but_ineffective": .3, "star": .85}.get(kind, .65)
        for seq, (b, w) in enumerate(zip(chosen, split), 1):
            content = None
            if c["call_type"] != "phone" and rng.random() < use_content:
                ctype = "video" if catalog.BRANDS[b][5] else "visual_aid"
                opts = content_lib.valid(b, ctype, c["call_date"])
                content = opts[-1]["content_id"] if opts else None
            out.append({"call_product_id": lid, "call_id": c["call_id"], "line_type": "detailing", "brand_code": b,
                        "sku_code": None, "sequence_no": seq, "detailing_seconds": int(total_sec * w),
                        "content_id": content, "quantity": None, "input_description": None}); lid += 1
        if c["call_type"] == "in_clinic" and rng.random() < .25:
            for b in chosen[:int(rng.integers(1, 3))]:
                if b in skus_by_brand:
                    out.append({"call_product_id": lid, "call_id": c["call_id"], "line_type": "sample", "brand_code": b,
                                "sku_code": str(rng.choice(skus_by_brand[b])), "sequence_no": None,
                                "detailing_seconds": None, "content_id": None,
                                "quantity": int(rng.integers(2, 7)), "input_description": None}); lid += 1
        if c["call_type"] == "in_clinic" and rng.random() < .08:
            b = chosen[0]
            out.append({"call_product_id": lid, "call_id": c["call_id"], "line_type": "input", "brand_code": b,
                        "sku_code": None, "sequence_no": None, "detailing_seconds": None, "content_id": None,
                        "quantity": int(rng.integers(5, 21)),
                        "input_description": str(rng.choice(INPUTS[catalog.BRANDS[b][2]]))}); lid += 1
    return out
