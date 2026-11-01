"""Writers for Phase 2-4 tables. Each reads from the shared world / market /
field models, so IDs match the Phase 1 tables exactly."""

import json

import numpy as np
import pandas as pd

from generator import (action_log, call_product, catalog, clinics, comms, config, content_lib, market,
                       nba, notes, tour_plan, world)
from generator.common import write_parquet
from generator.geography import TERRITORIES


# ------------------------------------------------------------------ phase 2
def business_unit():
    rows = [{"business_unit_id": k, "business_unit_name": v[0], "cluster_id": v[1], "cluster_code": v[2],
             "cluster_name": v[3], "calls_per_day_lower": v[4], "calls_per_day_upper": v[5], "is_active": True}
            for k, v in catalog.BUSINESS_UNITS.items()]
    write_parquet("business_unit", pd.DataFrame(rows), """
    business_unit_id     BIGINT  PRIMARY KEY,
    business_unit_name   VARCHAR NOT NULL,
    cluster_id           BIGINT  NOT NULL,
    cluster_code         VARCHAR NOT NULL,
    cluster_name         VARCHAR NOT NULL,
    calls_per_day_lower  DOUBLE  NOT NULL,
    calls_per_day_upper  DOUBLE  NOT NULL,
    is_active            BOOLEAN NOT NULL""".strip("\n"))


def kpi_target():
    rows = []
    y, m = config.CALENDAR_START.year, config.CALENDAR_START.month
    while (y, m) <= (config.CALENDAR_END.year, config.CALENDAR_END.month):
        value = 90.0 if (y, m) < (2025, 4) else 95.0
        for kpi in ("MCR_COVERAGE", "MVC"):
            rows.append({"kpi_code": kpi, "year_month": y * 100 + m, "business_unit_id": None,
                         "target_value": value, "unit": "percent", "comparison": "gte"})
        y, m = (y + (m == 12), m % 12 + 1)
    write_parquet("kpi_target", pd.DataFrame(rows), """
    kpi_code          VARCHAR NOT NULL,
    year_month        INTEGER NOT NULL,
    business_unit_id  BIGINT,
    target_value      DOUBLE  NOT NULL,
    unit              VARCHAR NOT NULL,
    comparison        VARCHAR NOT NULL""".strip("\n"))


def tour_plan_table():
    df = pd.DataFrame([{k: v for k, v in r.items() if not k.startswith("_")} for r in tour_plan.rows()])
    write_parquet("tour_plan", df.sort_values("tour_plan_id"), """
    tour_plan_id               BIGINT    PRIMARY KEY,
    employee_id                BIGINT    NOT NULL,
    territory_id               BIGINT    NOT NULL,
    plan_date                  DATE      NOT NULL,
    year_month                 INTEGER   NOT NULL,
    activity_type              VARCHAR   NOT NULL,
    patch_id                   BIGINT,
    doctor_id                  BIGINT,
    clinic_id                  BIGINT,
    planned_start_time         TIME,
    source                     VARCHAR   NOT NULL,
    status                     VARCHAR   NOT NULL,
    version                    SMALLINT  NOT NULL,
    submitted_at               TIMESTAMP,
    approved_by                BIGINT,
    approved_at                TIMESTAMP,
    joint_working_employee_id  BIGINT,
    is_deviation               BOOLEAN   NOT NULL,
    deviation_reason           VARCHAR,
    booking_status             VARCHAR,
    booking_confirmed_at       TIMESTAMP""".strip("\n"))


def clinic():
    df = pd.DataFrame(clinics.rows())
    for col in ("opd_schedule", "rep_visit_window"):
        df[col] = df[col].map(lambda lst: json.dumps([{k: str(v) if k != "weekday" else v for k, v in e.items()}
                                                      for e in lst]))
    struct = "STRUCT(weekday SMALLINT, start_time TIME, end_time TIME)[]"
    shape = '\'[{"weekday":"SMALLINT","start_time":"TIME","end_time":"TIME"}]\''
    write_parquet("clinic", df, f"""
    clinic_id         BIGINT  PRIMARY KEY,
    doctor_id         BIGINT  NOT NULL,
    clinic_name       VARCHAR NOT NULL,
    clinic_type       VARCHAR NOT NULL,
    is_primary        BOOLEAN NOT NULL,
    address           VARCHAR NOT NULL,
    city              VARCHAR NOT NULL,
    state             VARCHAR NOT NULL,
    pincode           VARCHAR NOT NULL,
    patch_id          BIGINT  NOT NULL,
    latitude          DOUBLE  NOT NULL,
    longitude         DOUBLE  NOT NULL,
    opd_schedule      {struct},
    rep_visit_window  {struct},
    timing_source     VARCHAR NOT NULL""".strip("\n"),
                  exprs={"opd_schedule": f"from_json(opd_schedule, {shape})",
                         "rep_visit_window": f"from_json(rep_visit_window, {shape})"})


def agent_action_log():
    write_parquet("agent_action_log", pd.DataFrame(action_log.rows()), """
    action_id          BIGINT    PRIMARY KEY,
    occurred_at        TIMESTAMP NOT NULL,
    employee_id        BIGINT    NOT NULL,
    agent_name         VARCHAR   NOT NULL,
    action_type        VARCHAR   NOT NULL,
    target_table       VARCHAR   NOT NULL,
    target_id          BIGINT    NOT NULL,
    input_summary      VARCHAR,
    approval_required  BOOLEAN   NOT NULL,
    approved_by        BIGINT,
    approved_at        TIMESTAMP,
    outcome            VARCHAR   NOT NULL,
    error_message      VARCHAR,
    trace_id           VARCHAR   NOT NULL""".strip("\n"))


# ------------------------------------------------------------------ phase 3
def product():
    rows = []
    for sku, name, pack, form, b, sample in catalog.SKUS:
        bn, sbu, therapy, cls, gb, device, price, units, launch = catalog.BRANDS[b]
        rows.append({"sku_code": sku, "sku_name": name, "pack_size": pack, "dosage_form": form, "brand_code": b,
                     "brand_name": bn, "manufacturer": config.COMPANY_NAME, "is_own_brand": True,
                     "business_unit_id": sbu, "therapy_area": therapy, "molecule_class": catalog.CLASS_DESC[cls],
                     "is_growth_brand": gb, "is_device": device, "is_sample_eligible": sample,
                     "price_per_strip_inr": price, "launch_date": pd.Timestamp(launch).date(), "is_active": True})
    for code, (bn, maker, cls, price) in catalog.COMPETITORS.items():
        zb = next(b for b, v in catalog.BRANDS.items() if v[3] == cls)
        rows.append({"sku_code": code, "sku_name": bn, "pack_size": None, "dosage_form": None, "brand_code": code,
                     "brand_name": bn, "manufacturer": maker, "is_own_brand": False, "business_unit_id": None,
                     "therapy_area": catalog.BRANDS[zb][2], "molecule_class": catalog.CLASS_DESC[cls],
                     "is_growth_brand": False, "is_device": False, "is_sample_eligible": False,
                     "price_per_strip_inr": price, "launch_date": None, "is_active": True})
    write_parquet("product", pd.DataFrame(rows), """
    sku_code             VARCHAR       PRIMARY KEY,
    sku_name             VARCHAR       NOT NULL,
    pack_size            VARCHAR,
    dosage_form          VARCHAR,
    brand_code           VARCHAR       NOT NULL,
    brand_name           VARCHAR       NOT NULL,
    manufacturer         VARCHAR       NOT NULL,
    is_own_brand         BOOLEAN       NOT NULL,
    business_unit_id     BIGINT,
    therapy_area         VARCHAR       NOT NULL,
    molecule_class       VARCHAR       NOT NULL,
    is_growth_brand      BOOLEAN       NOT NULL,
    is_device            BOOLEAN       NOT NULL,
    is_sample_eligible   BOOLEAN       NOT NULL,
    price_per_strip_inr  DECIMAL(10,2) NOT NULL,
    launch_date          DATE,
    is_active            BOOLEAN       NOT NULL""".strip("\n"))


STATE_CODE = {"Tamil Nadu": "TN", "Maharashtra": "MH", "West Bengal": "WB", "Delhi": "DL", "Uttar Pradesh": "UP", "Haryana": "HR"}


def chemist():
    rng = np.random.default_rng(config.SEEDS["clinic"] + 7)
    rows = []
    for cid, pid in world.chemists().items():
        t = TERRITORIES[pid // 100]
        p = t[8][pid % 100 - 1]
        patch, city, state = p[0], p[1], p[2] or t[7]
        kind = str(rng.choice(["retail", "chain", "hospital_pharmacy"], p=[.78, .16, .06]))
        chain = f"Pharmacy Chain P{int(rng.integers(1, 4))}" if kind == "chain" else None      # numbered chains
        name = (f"{chain}, {patch}" if chain else f"Hospital Pharmacy C-{cid % 1000:03d}, {patch}"
                if kind == "hospital_pharmacy" else f"Chemist C-{cid % 1000:03d}, {patch}")
        lat, lon = p[3] + rng.normal(0, .007), p[4] + rng.normal(0, .007)
        pin = clinics.PIN[city] + f"{int(rng.integers(1, 120)):03d}"
        rows.append({"chemist_id": cid, "chemist_name": name, "chemist_type": kind, "chain_name": chain,
                     "drug_license_no": f"{STATE_CODE[state]}/20B-21B/SYN-{int(rng.integers(10000, 99999))}",
                     "address": f"{int(rng.integers(1, 300))}, {rng.choice(clinics.STREETS)}, {patch}, {city} {pin}",
                     "city": city, "state": state, "pincode": pin, "patch_id": pid,
                     "latitude": round(lat, 6), "longitude": round(lon, 6), "is_active": True})
    write_parquet("chemist", pd.DataFrame(rows), """
    chemist_id       BIGINT  PRIMARY KEY,
    chemist_name     VARCHAR NOT NULL,
    chemist_type     VARCHAR NOT NULL,
    chain_name       VARCHAR,
    drug_license_no  VARCHAR NOT NULL,
    address          VARCHAR NOT NULL,
    city             VARCHAR NOT NULL,
    state            VARCHAR NOT NULL,
    pincode          VARCHAR NOT NULL,
    patch_id         BIGINT  NOT NULL,
    latitude         DOUBLE  NOT NULL,
    longitude        DOUBLE  NOT NULL,
    is_active        BOOLEAN NOT NULL""".strip("\n"))


def rcpa_entry():
    write_parquet("rcpa_entry", pd.DataFrame(market.rcpa_rows()), """
    rcpa_id          BIGINT  PRIMARY KEY,
    audit_date       DATE    NOT NULL,
    year_month       INTEGER NOT NULL,
    employee_id      BIGINT  NOT NULL,
    territory_id     BIGINT  NOT NULL,
    chemist_id       BIGINT  NOT NULL,
    doctor_id        BIGINT  NOT NULL,
    brand_code       VARCHAR NOT NULL,
    prescriptions    INTEGER NOT NULL,
    quantity_strips  DOUBLE  NOT NULL,
    value_inr        DOUBLE  NOT NULL""".strip("\n"))


def doctor_brand_plan():
    write_parquet("doctor_brand_plan", pd.DataFrame(market.brand_plan_rows()), """
    territory_id         BIGINT   NOT NULL,
    doctor_id            BIGINT   NOT NULL,
    brand_code           VARCHAR  NOT NULL,
    year_month           INTEGER  NOT NULL,
    potential_value_inr  DOUBLE   NOT NULL,
    potential_rx         DOUBLE   NOT NULL,
    potential_strips     DOUBLE   NOT NULL,
    target_value_inr     DOUBLE,
    target_rx            DOUBLE,
    target_strips        DOUBLE,
    brand_priority       VARCHAR  NOT NULL,
    brand_rank           SMALLINT NOT NULL,
    is_focus_brand       BOOLEAN  NOT NULL,
    PRIMARY KEY (territory_id, doctor_id, brand_code, year_month)""".strip("\n"))


def dcr_call_product():
    write_parquet("dcr_call_product", pd.DataFrame(call_product.rows()), """
    call_product_id    BIGINT   PRIMARY KEY,
    call_id            BIGINT   NOT NULL,
    line_type          VARCHAR  NOT NULL,
    brand_code         VARCHAR  NOT NULL,
    sku_code           VARCHAR,
    sequence_no        SMALLINT,
    detailing_seconds  INTEGER,
    content_id         BIGINT,
    quantity           INTEGER,
    input_description  VARCHAR""".strip("\n"))


# ------------------------------------------------------------------ phase 4
def call_note():
    write_parquet("call_note", pd.DataFrame(notes.rows()), """
    note_id               BIGINT    PRIMARY KEY,
    call_id               BIGINT    NOT NULL,
    employee_id           BIGINT    NOT NULL,
    doctor_id             BIGINT    NOT NULL,
    recorded_at           TIMESTAMP NOT NULL,
    source                VARCHAR   NOT NULL,
    audio_blob_path       VARCHAR,
    audio_duration_sec    INTEGER,
    audio_format          VARCHAR,
    transcription_status  VARCHAR,
    language_detected     VARCHAR,
    transcript_raw        VARCHAR,
    transcript_en         VARCHAR,
    summary               VARCHAR,
    brands_discussed      VARCHAR[],
    topics                VARCHAR[],
    objections            VARCHAR,
    doctor_commitments    VARCHAR,
    rep_commitments       VARCHAR,
    next_step             VARCHAR,
    next_call_date        DATE,
    doctor_receptivity    VARCHAR,
    compliance_flags      VARCHAR[],
    status                VARCHAR   NOT NULL,
    confirmed_at          TIMESTAMP,
    embedding             FLOAT[]""".strip("\n"))


def communication():
    write_parquet("communication", pd.DataFrame(comms.rows()), """
    communication_id  BIGINT    PRIMARY KEY,
    doctor_id         BIGINT    NOT NULL,
    employee_id       BIGINT,
    territory_id      BIGINT    NOT NULL,
    channel           VARCHAR   NOT NULL,
    direction         VARCHAR   NOT NULL,
    campaign_id       VARCHAR,
    content_id        BIGINT,
    subject           VARCHAR,
    body              VARCHAR,
    generated_by      VARCHAR   NOT NULL,
    consent_checked   BOOLEAN   NOT NULL,
    status            VARCHAR   NOT NULL,
    approved_by       BIGINT,
    approved_at       TIMESTAMP,
    sent_at           TIMESTAMP,
    delivered_at      TIMESTAMP,
    opened_at         TIMESTAMP,
    clicked_at        TIMESTAMP,
    responded_at      TIMESTAMP,
    response_type     VARCHAR""".strip("\n"))


def content():
    write_parquet("content", pd.DataFrame(content_lib.items()), """
    content_id          BIGINT    PRIMARY KEY,
    brand_code          VARCHAR   NOT NULL,
    title               VARCHAR   NOT NULL,
    content_type        VARCHAR   NOT NULL,
    target_specialties  VARCHAR[],
    key_message         VARCHAR,
    approved_claims     VARCHAR,
    language            VARCHAR   NOT NULL,
    review_reference    VARCHAR   NOT NULL,
    approved_on         DATE      NOT NULL,
    expires_on          DATE      NOT NULL,
    file_blob_path      VARCHAR   NOT NULL,
    status              VARCHAR   NOT NULL,
    embedding           FLOAT[]""".strip("\n"))


def formulary_listing():
    write_parquet("formulary_listing", pd.DataFrame(market.formulary_rows()), """
    listing_id      BIGINT  PRIMARY KEY,
    clinic_id       BIGINT  NOT NULL,
    brand_code      VARCHAR NOT NULL,
    listing_status  VARCHAR NOT NULL,
    effective_from  DATE    NOT NULL,
    effective_to    DATE,
    notes           VARCHAR""".strip("\n"))


def nba_recommendation():
    write_parquet("nba_recommendation", pd.DataFrame(nba.rows()), """
    recommendation_id  BIGINT    PRIMARY KEY,
    generated_at       TIMESTAMP NOT NULL,
    employee_id        BIGINT    NOT NULL,
    territory_id       BIGINT    NOT NULL,
    doctor_id          BIGINT    NOT NULL,
    action_type        VARCHAR   NOT NULL,
    brand_code         VARCHAR,
    content_id         BIGINT,
    reason_codes       VARCHAR[],
    score              DOUBLE    NOT NULL,
    engine_version     VARCHAR   NOT NULL,
    status             VARCHAR   NOT NULL,
    status_at          TIMESTAMP""".strip("\n"))


PHASES = {
    2: [business_unit, kpi_target, clinic, tour_plan_table, agent_action_log],
    3: [product, chemist, rcpa_entry, doctor_brand_plan, dcr_call_product],
    4: [content, formulary_listing, call_note, communication, nba_recommendation],
}
