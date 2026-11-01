"""doctor: one row per real doctor (plus a few MDM-merged duplicates)."""

import duckdb
import pandas as pd

from generator import config, world
from generator.common import write_parquet

DDL = """
    doctor_id                   BIGINT    PRIMARY KEY,
    doctor_code                 VARCHAR   NOT NULL,
    registration_no             VARCHAR,
    registration_council        VARCHAR,
    full_name                   VARCHAR   NOT NULL,
    gender                      VARCHAR,
    birth_date                  DATE,
    qualification               VARCHAR,
    specialty                   VARCHAR   NOT NULL,
    years_of_practice           SMALLINT,
    mobile                      VARCHAR,
    email                       VARCHAR,
    prescriber_persona          VARCHAR,
    behavioural_persona         VARCHAR,
    loyalty_persona             VARCHAR,
    digital_persona             VARCHAR,
    in_clinic_engagement        BOOLEAN   NOT NULL,
    patient_support             BOOLEAN   NOT NULL,
    scientific_engagement       BOOLEAN   NOT NULL,
    scientific_out_clinic       BOOLEAN   NOT NULL,
    academy_member              BOOLEAN   NOT NULL,
    digital_connect_member          BOOLEAN   NOT NULL,
    patient_program_user          BOOLEAN   NOT NULL,
    consent_email               VARCHAR   NOT NULL,
    consent_whatsapp            VARCHAR   NOT NULL,
    consent_sms                 VARCHAR   NOT NULL,
    consent_phone               VARCHAR   NOT NULL,
    consent_updated_at          TIMESTAMP,
    linkedin_url                VARCHAR,
    x_url                       VARCHAR,
    public_bio                  VARCHAR,
    recent_public_topics        VARCHAR[],
    social_compliance_approved  BOOLEAN,
    mdm_status                  VARCHAR   NOT NULL,
    merged_into_doctor_id       BIGINT"""


def build() -> None:
    docs = world.doctors()
    write_parquet("doctor", pd.DataFrame([d.attrs for d in docs]), DDL.strip("\n"))

    key = pd.DataFrame([{"doctor_id": d.doctor_id, "territory_id": d.territory_id, **d.traits}
                        for d in docs if d.traits])
    out = config.ROOT / "data" / "answer_key" / "doctor_traits.parquet"
    duckdb.connect().execute(f"COPY (SELECT * FROM key) TO '{out}' (FORMAT PARQUET)")
