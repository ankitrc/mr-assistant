"""Settings shared by every table generator."""

from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PARQUET_DIR = ROOT / "data" / "parquet"

# Activity data ends on this date (yesterday relative to the build).
AS_OF_DATE = date(2026, 10, 27)
HISTORY_MONTHS = 24

# Calendar spans whole Indian fiscal years around the history window,
# so planning for upcoming months also has calendar rows.
CALENDAR_START = date(2024, 4, 1)    # FY2024-25
CALENDAR_END = date(2027, 3, 31)     # FY2026-27

# One seed per table: adding or regenerating one table never changes another.
SEEDS = {"calendar_day": 101, "geography": 102, "employee": 103,
         "doctors": 110, "mcl": 111, "field": 112,
         "clinic": 120, "tour_plan": 121, "market": 130, "call_product": 131,
         "content": 140, "notes": 141, "communication": 142, "nba": 143, "action_log": 144}

SOURCE_SYSTEM = "synthetic_generator"
LOAD_BATCH_ID = "BATCH_0001"
LOAD_TS = datetime(2026, 10, 28, 2, 0, 0)

# Fictional company and business units (no real company data anywhere).
COMPANY_NAME = "Example Pharma"
RESPI_BU = 1     # Respiratory BU
CARDIO_BU = 2    # Cardio-Metabolic BU (diabetes, cardio, metabolic)

# First month of activity history (24 full months ending with the as-of month).
HISTORY_START = date(2024, 11, 1)

# The agentic app went live (pilot) on this date: voice notes, agent drafts,
# NBA and the action log start here. Earlier notes are typed DCR remarks.
PILOT_START = date(2026, 9, 1)
