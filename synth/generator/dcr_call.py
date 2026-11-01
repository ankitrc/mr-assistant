"""dcr_call: one row per doctor call (completed or doctor not available)."""

import pandas as pd

from generator import field_sim
from generator.common import write_parquet

DDL = """
    call_id                    BIGINT    PRIMARY KEY,
    employee_id                BIGINT    NOT NULL,
    territory_id               BIGINT    NOT NULL,
    doctor_id                  BIGINT    NOT NULL,
    clinic_id                  BIGINT    NOT NULL,
    patch_id                   BIGINT    NOT NULL,
    call_date                  DATE      NOT NULL,
    call_start_time            TIME      NOT NULL,
    duration_minutes           SMALLINT,
    call_type                  VARCHAR   NOT NULL,
    joint_working_employee_id  BIGINT,
    tour_plan_id               BIGINT,
    is_planned                 BOOLEAN   NOT NULL,
    call_status                VARCHAR   NOT NULL,
    submitted_at               TIMESTAMP NOT NULL,
    checkin_latitude           DOUBLE,
    checkin_longitude          DOUBLE"""


def build() -> None:
    _, calls = field_sim.simulate()
    write_parquet("dcr_call", pd.DataFrame(calls), DDL.strip("\n"))
