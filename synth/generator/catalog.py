"""Reference catalog for a fictional company (Example Pharma): business units,
own brands and SKUs, competitor brands, brand priority by specialty, and
market parameters. Brand priority is generator configuration, not a table.

Brand names are deliberately synthetic codes (AX-R1, CA-R1, ...) so they can
never match a real product or trademark; business units use plain
descriptive names. Product descriptions avoid clinical claims.
"""

from generator import config

R, D = config.RESPI_BU, config.CARDIO_BU

# business_unit_id: (name, cluster_id, cluster_code, cluster_name, calls/day lower, upper)
BUSINESS_UNITS = {
    1: ("Respiratory BU", 1, "CLS-1", "Specialty", 10.0, 10.0),
    2: ("Cardio-Metabolic BU", 2, "CLS-2", "Chronic", 11.0, 11.0),
    3: ("Dermatology BU", 1, "CLS-1", "Specialty", 11.0, 11.0),
    4: ("Women's Health BU", 3, "CLS-3", "Women's Health", 11.0, 11.0),
    5: ("Neuroscience BU", 2, "CLS-2", "Chronic", 10.0, 10.0),
    6: ("General Medicine BU", 3, "CLS-3", "Mass", 12.0, 12.0),
}

# brand_code: (brand_name, bu, therapy_area, class, growth_brand, is_device, price_per_unit, units_per_rx, launch)
BRANDS = {
    "BR-RES-001": ("AX-R1", R, "Respiratory", "RES_DEVICE", False, True, 150.0, 1.0, "2022-04-01"),
    "BR-RES-002": ("AX-R2", R, "Respiratory", "RES_ICS_LABA", True, False, 395.0, 1.5, "2023-01-15"),
    "BR-RES-003": ("AX-R3", R, "Respiratory", "RES_TRIPLE", False, False, 455.0, 1.5, "2024-02-01"),
    "BR-RES-004": ("AX-R4", R, "Respiratory", "RES_LTRA", False, False, 195.0, 2.0, "2023-05-01"),
    "BR-RES-005": ("AX-R5", R, "Respiratory", "RES_LAMA_LABA", True, False, 410.0, 2.0, "2024-08-01"),
    "BR-RES-006": ("AX-R6", R, "Respiratory", "RES_LAMA_LABA", False, False, 610.0, 1.0, "2024-03-01"),
    "BR-CMT-001": ("AX-C1", D, "Metabolic", "MET_PPAR", True, False, 280.0, 3.0, "2013-09-01"),
    "BR-CMT-002": ("AX-C2", D, "Cardiovascular", "CVS_ARB", False, False, 120.0, 3.0, "2011-06-01"),
    "BR-CMT-003": ("AX-C3", D, "Diabetes", "DIA_SU_MET", False, False, 95.0, 3.0, "2012-02-01"),
    "BR-CMT-004": ("AX-C4", D, "Diabetes", "DIA_DPP4", True, False, 210.0, 3.0, "2022-07-01"),
    "BR-CMT-005": ("AX-C5", D, "Cardiovascular", "CVS_STATIN", False, False, 160.0, 3.0, "2014-01-01"),
    "BR-CMT-006": ("AX-C6", D, "Cardiovascular", "CVS_CCB_COMBO", False, False, 110.0, 3.0, "2015-08-01"),
}
CLASS_DESC = {
    "RES_DEVICE": "Inhalation device", "RES_ICS_LABA": "Inhaled corticosteroid + LABA",
    "RES_TRIPLE": "Inhaled triple combination", "RES_LTRA": "Leukotriene receptor antagonist combination",
    "RES_LAMA_LABA": "LAMA / LABA inhalation", "MET_PPAR": "PPAR agonist", "CVS_ARB": "Angiotensin receptor blocker",
    "DIA_SU_MET": "Sulfonylurea + metformin", "DIA_DPP4": "DPP-4 inhibitor", "CVS_STATIN": "Statin",
    "CVS_CCB_COMBO": "Antihypertensive combination",
}
# Own SKUs: (sku_code, sku_name, pack_size, dosage_form, brand_code, sample_eligible)
SKUS = [
    ("8000101", "AX-R1 INHALER DEVICE 1X1 UNIT", "1X1", "Device", "BR-RES-001", False),
    ("8000201", "AX-R2 100 INHALER 120MDI", "1X120", "Inhaler", "BR-RES-002", True),
    ("8000202", "AX-R2 50 INHALER 120MDI", "1X120", "Inhaler", "BR-RES-002", True),
    ("8000203", "AX-R2 100 RESPICAPS 1X30C", "1X30", "Respicaps", "BR-RES-002", True),
    ("8000204", "AX-R2 200 RESPICAPS 1X30C", "1X30", "Respicaps", "BR-RES-002", True),
    ("8000301", "AX-R3 100 RESPICAPS 1X30C", "1X30", "Respicaps", "BR-RES-003", True),
    ("8000302", "AX-R3 200 RESPICAPS 1X30C", "1X30", "Respicaps", "BR-RES-003", True),
    ("8000303", "AX-R3 50 INHALER 120MDI", "1X120", "Inhaler", "BR-RES-003", True),
    ("8000401", "AX-R4 TABLETS 10X10T", "10X10", "Tablet", "BR-RES-004", True),
    ("8000501", "AX-R5 100 RESPICAPS 1X15C", "1X15", "Respicaps", "BR-RES-005", True),
    ("8000502", "AX-R5 200 RESPICAPS 1X15C", "1X15", "Respicaps", "BR-RES-005", True),
    ("8000601", "AX-R6 INHALER 120MDI", "1X120", "Inhaler", "BR-RES-006", True),
    ("8100101", "AX-C1 4MG TABLETS 10X10T", "10X10", "Tablet", "BR-CMT-001", True),
    ("8100201", "AX-C2 10 TABLETS 10X10T", "10X10", "Tablet", "BR-CMT-002", True),
    ("8100202", "AX-C2 20 TABLETS 10X10T", "10X10", "Tablet", "BR-CMT-002", True),
    ("8100203", "AX-C2 40 TABLETS 10X10T", "10X10", "Tablet", "BR-CMT-002", True),
    ("8100204", "AX-C2 H TABLETS 10X10T", "10X10", "Tablet", "BR-CMT-002", True),
    ("8100301", "AX-C3 1 TABLETS 10X10T", "10X10", "Tablet", "BR-CMT-003", True),
    ("8100302", "AX-C3 2 TABLETS 10X10T", "10X10", "Tablet", "BR-CMT-003", True),
    ("8100401", "AX-C4 50 TABLETS 10X10T", "10X10", "Tablet", "BR-CMT-004", True),
    ("8100402", "AX-C4 100 TABLETS 10X10T", "10X10", "Tablet", "BR-CMT-004", True),
    ("8100403", "AX-C4 M 50/500 TABLETS 10X10T", "10X10", "Tablet", "BR-CMT-004", True),
    ("8100501", "AX-C5 1 TABLETS 10X10T", "10X10", "Tablet", "BR-CMT-005", True),
    ("8100502", "AX-C5 2 TABLETS 10X10T", "10X10", "Tablet", "BR-CMT-005", True),
    ("8100601", "AX-C6 5 TABLETS 10X10T", "10X10", "Tablet", "BR-CMT-006", True),
    ("8100602", "AX-C6 10 TABLETS 10X10T", "10X10", "Tablet", "BR-CMT-006", True),
]
# Fictional competitors: brand_code: (brand_name, manufacturer, class, price_per_unit)
COMPETITORS = {
    "CMP-CA-R1": ("CA-R1", "Competitor A (fictional)", "RES_ICS_LABA", 380.0),
    "CMP-CB-R2": ("CB-R2", "Competitor B (fictional)", "RES_ICS_LABA", 410.0),
    "CMP-CA-R3": ("CA-R3", "Competitor A (fictional)", "RES_TRIPLE", 470.0),
    "CMP-CB-R4": ("CB-R4", "Competitor B (fictional)", "RES_LAMA_LABA", 430.0),
    "CMP-CC-R5": ("CC-R5", "Competitor C (fictional)", "RES_LAMA_LABA", 520.0),
    "CMP-CA-R6": ("CA-R6", "Competitor A (fictional)", "RES_LTRA", 180.0),
    "CMP-CC-R7": ("CC-R7", "Competitor C (fictional)", "RES_LTRA", 170.0),
    "CMP-CB-C1": ("CB-C1", "Competitor B (fictional)", "MET_PPAR", 150.0),
    "CMP-CA-C2": ("CA-C2", "Competitor A (fictional)", "CVS_ARB", 115.0),
    "CMP-CC-C3": ("CC-C3", "Competitor C (fictional)", "CVS_ARB", 105.0),
    "CMP-CB-C4": ("CB-C4", "Competitor B (fictional)", "DIA_SU_MET", 90.0),
    "CMP-CC-C5": ("CC-C5", "Competitor C (fictional)", "DIA_SU_MET", 85.0),
    "CMP-CA-C6": ("CA-C6", "Competitor A (fictional)", "DIA_DPP4", 190.0),
    "CMP-CB-C7": ("CB-C7", "Competitor B (fictional)", "DIA_DPP4", 175.0),
    "CMP-CC-C8": ("CC-C8", "Competitor C (fictional)", "CVS_STATIN", 140.0),
    "CMP-CA-C9": ("CA-C9", "Competitor A (fictional)", "CVS_CCB_COMBO", 100.0),
}
# The competitor that gains share in the 'declining' story (Kolkata, from Jul 2026)
AGGRESSIVE_COMPETITOR = "CMP-CA-R1"

# Brand priority by business unit x specialty (first = P1). Generator configuration.
PRIORITY = {
    R: {
        "Chest Physician": ["BR-RES-002", "BR-RES-005", "BR-RES-003", "BR-RES-006", "BR-RES-004", "BR-RES-001"],
        "Pulmonologist": ["BR-RES-003", "BR-RES-005", "BR-RES-006", "BR-RES-002", "BR-RES-004", "BR-RES-001"],
        "ENT Specialist": ["BR-RES-004", "BR-RES-002"],
        "Paediatrician": ["BR-RES-004", "BR-RES-002", "BR-RES-001"],
        "Consultant Physician": ["BR-RES-002", "BR-RES-004", "BR-RES-005", "BR-RES-001"],
        "General Practitioner": ["BR-RES-004", "BR-RES-002"],
    },
    D: {
        "Diabetologist": ["BR-CMT-004", "BR-CMT-003", "BR-CMT-001", "BR-CMT-002"],
        "Endocrinologist": ["BR-CMT-004", "BR-CMT-001", "BR-CMT-003"],
        "Cardiologist": ["BR-CMT-002", "BR-CMT-005", "BR-CMT-001", "BR-CMT-006"],
        "Gastroenterologist": ["BR-CMT-001"],
        "Consultant Physician": ["BR-CMT-002", "BR-CMT-003", "BR-CMT-004", "BR-CMT-006", "BR-CMT-005", "BR-CMT-001"],
        "General Practitioner": ["BR-CMT-003", "BR-CMT-002", "BR-CMT-006"],
    },
}
RESPIRATORY_SEASON = {1: 1.2, 2: 1.15, 3: 1.0, 4: .9, 5: .85, 6: .95, 7: 1.1, 8: 1.15, 9: 1.1, 10: 1.0, 11: 1.15, 12: 1.2}


def brands_for(bu, specialty, include_device=True):
    lst = PRIORITY[bu][specialty]
    return [b for b in lst if include_device or not BRANDS[b][5]]


def competitors_of(brand_code):
    cls = BRANDS[brand_code][3]
    return [c for c, v in COMPETITORS.items() if v[2] == cls]


def is_own_brand(code):
    return code in BRANDS


def display(code):
    """Brand name as written in text (synthetic codes are already in display form)."""
    return BRANDS[code][0] if code in BRANDS else COMPETITORS[code][0]
