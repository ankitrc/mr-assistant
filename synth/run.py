"""Generate all synthetic Parquet files (Phases 1-4), then validate them.

    python run.py            # all phases
    python run.py 1 2        # only the listed phases
"""

import sys

from generator import calendar_day, dcr_call, doctor, employee, geography, later_tables, mcl, validate
from generator.config import PARQUET_DIR

phases = {int(p) for p in sys.argv[1:]} or {1, 2, 3, 4}
if 1 in phases:
    for module in (calendar_day, geography, employee, doctor, mcl, dcr_call):
        module.build()
        print("wrote", module.__name__.split(".")[-1])
for ph in (2, 3, 4):
    if ph in phases:
        for fn in later_tables.PHASES[ph]:
            fn()
            print("wrote", fn.__name__.replace("_table", ""))

print("validating")
validate.run()
print("KPI averages (full months only)")
validate.kpi_report()
print("done ->", PARQUET_DIR)
