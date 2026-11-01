"""mcl: Master Customer List, one row per territory x doctor x validity period."""

import pandas as pd

from generator import world
from generator.common import write_parquet

DDL = """
    mcl_id              BIGINT    PRIMARY KEY,
    territory_id        BIGINT    NOT NULL,
    doctor_id           BIGINT    NOT NULL,
    clinic_id           BIGINT    NOT NULL,
    patch_id            BIGINT    NOT NULL,
    doctor_class        VARCHAR   NOT NULL,
    visit_frequency     VARCHAR   NOT NULL,
    mcl_position        SMALLINT,
    linked_chemist_ids  BIGINT[],
    valid_from          DATE      NOT NULL,
    valid_to            DATE,
    is_current          BOOLEAN   NOT NULL,
    change_reason       VARCHAR   NOT NULL"""


def build() -> None:
    rows = [{k: v for k, v in r.items() if not k.startswith("_")} for r in world.mcl_rows()]
    write_parquet("mcl", pd.DataFrame(rows).sort_values("mcl_id"), DDL.strip("\n"))
