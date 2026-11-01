"""calendar_day: one row per day, Indian fiscal year (April-March).

Working week: Monday-Saturday (standard for Indian pharma field force);
Sunday is the weekly off. Company-wide holidays are flagged national;
state holidays list the states where they apply.

Festival dates follow published Indian holiday calendars; lunar-calendar
dates for 2026-27 are approximate. Replace with the company holiday list
when available.
"""

from datetime import date, timedelta

import pandas as pd

from generator import config

# Company-wide holidays (national + major festivals).
NATIONAL = {
    date(2024, 4, 11): "Eid al-Fitr", date(2024, 8, 15): "Independence Day",
    date(2024, 10, 2): "Gandhi Jayanti", date(2024, 10, 12): "Dussehra",
    date(2024, 10, 31): "Diwali", date(2024, 12, 25): "Christmas",
    date(2025, 1, 26): "Republic Day", date(2025, 3, 14): "Holi",
    date(2025, 3, 31): "Eid al-Fitr", date(2025, 4, 18): "Good Friday",
    date(2025, 8, 15): "Independence Day", date(2025, 10, 2): "Gandhi Jayanti / Dussehra",
    date(2025, 10, 20): "Diwali", date(2025, 12, 25): "Christmas",
    date(2026, 1, 26): "Republic Day", date(2026, 3, 4): "Holi",
    date(2026, 3, 20): "Eid al-Fitr", date(2026, 4, 3): "Good Friday",
    date(2026, 8, 15): "Independence Day", date(2026, 10, 2): "Gandhi Jayanti",
    date(2026, 10, 20): "Dussehra", date(2026, 11, 8): "Diwali",
    date(2026, 12, 25): "Christmas",
    date(2027, 1, 26): "Republic Day", date(2027, 3, 10): "Eid al-Fitr",
    date(2027, 3, 22): "Holi", date(2027, 3, 26): "Good Friday",
}

TN, MH, WB, DL = "Tamil Nadu", "Maharashtra", "West Bengal", "Delhi"

# State holidays: date -> (name, [states]).
REGIONAL = {
    date(2024, 4, 14): ("Tamil New Year / Poila Boishakh", [TN, WB]),
    date(2024, 5, 1): ("Maharashtra Day", [MH]),
    date(2024, 9, 7): ("Ganesh Chaturthi", [MH]),
    date(2024, 10, 10): ("Durga Puja (Saptami)", [WB]),
    date(2024, 10, 11): ("Durga Puja (Ashtami)", [WB]),
    date(2025, 1, 14): ("Pongal", [TN]),
    date(2025, 3, 30): ("Gudi Padwa", [MH]),
    date(2025, 4, 14): ("Tamil New Year", [TN]),
    date(2025, 4, 15): ("Poila Boishakh", [WB]),
    date(2025, 5, 1): ("Maharashtra Day", [MH]),
    date(2025, 8, 27): ("Ganesh Chaturthi", [MH]),
    date(2025, 9, 29): ("Durga Puja (Saptami)", [WB]),
    date(2025, 9, 30): ("Durga Puja (Ashtami)", [WB]),
    date(2025, 10, 1): ("Durga Puja (Navami)", [WB]),
    date(2025, 11, 5): ("Guru Nanak Jayanti", [DL]),
    date(2026, 1, 15): ("Pongal", [TN]),
    date(2026, 3, 19): ("Gudi Padwa", [MH]),
    date(2026, 4, 14): ("Tamil New Year", [TN]),
    date(2026, 4, 15): ("Poila Boishakh", [WB]),
    date(2026, 5, 1): ("Maharashtra Day", [MH]),
    date(2026, 9, 14): ("Ganesh Chaturthi", [MH]),
    date(2026, 10, 17): ("Durga Puja (Saptami)", [WB]),
    date(2026, 10, 19): ("Durga Puja (Navami)", [WB]),
    date(2026, 11, 24): ("Guru Nanak Jayanti", [DL]),
    date(2027, 1, 15): ("Pongal", [TN]),
}


def build() -> None:
    rows = []
    d = config.CALENDAR_START
    while d <= config.CALENDAR_END:
        fy_start = d.year if d.month >= 4 else d.year - 1
        regional = REGIONAL.get(d)
        rows.append({
            "calendar_date": d,
            "year": d.year,
            "month": d.month,
            "year_month": d.year * 100 + d.month,
            "quarter": (d.month - 1) // 3 + 1,
            "fiscal_year": f"FY{fy_start}-{str(fy_start + 1)[-2:]}",
            "fiscal_quarter": ((d.month - 4) % 12) // 3 + 1,
            "week_of_year": d.isocalendar()[1],
            "day_of_week": d.isoweekday(),
            "day_name": d.strftime("%A"),
            "is_weekend": d.isoweekday() == 7,
            "is_national_holiday": d in NATIONAL,
            "holiday_name": NATIONAL.get(d) or (regional[0] if regional else None),
            "holiday_states": regional[1] if regional and d not in NATIONAL else None,
        })
        d += timedelta(days=1)

    from generator.common import write_parquet
    write_parquet("calendar_day", pd.DataFrame(rows), """
    calendar_date        DATE     PRIMARY KEY,
    year                 SMALLINT NOT NULL,
    month                SMALLINT NOT NULL,
    year_month           INTEGER  NOT NULL,
    quarter              SMALLINT NOT NULL,
    fiscal_year          VARCHAR  NOT NULL,
    fiscal_quarter       SMALLINT NOT NULL,
    week_of_year         SMALLINT NOT NULL,
    day_of_week          SMALLINT NOT NULL,
    day_name             VARCHAR  NOT NULL,
    is_weekend           BOOLEAN  NOT NULL,
    is_national_holiday  BOOLEAN  NOT NULL,
    holiday_name         VARCHAR,
    holiday_states       VARCHAR[]""".strip("\n"))
