"""employee: field hierarchy BO -> ABM -> RBM -> ZBM, one row per
employee per assignment period.

Story built in:
- Delhi territory handover: Amit Saxena (BO) leaves 30 Jun 2026; Rohit
  Malhotra takes the same territory from 1 Jul 2026 (new-rep profile).
- Pune ABM change: Rahul Joshi leaves 30 Sep 2025; Sneha Patil takes
  over, so Aniket Kulkarni has two assignment rows (manager changed).

Contact details are fictional: emails on example.com (reserved for
examples, never delivered), mobiles start with 0 (not a valid mobile number).
"""

from datetime import date

import pandas as pd

from generator import config

R, D = config.RESPI_BU, config.CARDIO_BU

# employee_id: (code, name, designation, sbu, territory_id, hq_id, joining_date, status)
PEOPLE = {
    # BOs (current)
    990001: ("900101", "Karthikeyan R", "BO", R, 900001, 9201, date(2022, 6, 1), "active"),
    990002: ("900102", "Aniket Kulkarni", "BO", R, 900002, 9202, date(2023, 1, 9), "active"),
    990003: ("900103", "Soumya Banerjee", "BO", R, 900003, 9203, date(2021, 4, 5), "active"),
    990004: ("900104", "Priya Deshpande", "BO", D, 900004, 9211, date(2023, 7, 17), "active"),
    990005: ("900105", "Rohit Malhotra", "BO", D, 900005, 9212, date(2026, 6, 15), "active"),
    # BO (previous, Delhi handover)
    990006: ("900106", "Amit Saxena", "BO", D, 900005, 9212, date(2020, 8, 3), "resigned"),
    # ABMs
    991001: ("900201", "Senthil Kumar M", "ABM", R, None, 9201, date(2017, 3, 1), "active"),
    991002: ("900202", "Rahul Joshi", "ABM", R, None, 9202, date(2016, 11, 14), "resigned"),
    991003: ("900203", "Sneha Patil", "ABM", R, None, 9202, date(2018, 5, 21), "active"),
    991004: ("900204", "Arindam Ghosh", "ABM", R, None, 9203, date(2015, 8, 10), "active"),
    991011: ("900211", "Farhan Shaikh", "ABM", D, None, 9211, date(2016, 2, 1), "active"),
    991012: ("900212", "Gurpreet Singh", "ABM", D, None, 9212, date(2014, 9, 15), "active"),
    # RBMs
    992001: ("900301", "Lakshmi Narayanan S", "RBM", R, None, 9201, date(2010, 7, 1), "active"),
    992002: ("900302", "Nitin Gokhale", "RBM", R, None, 9202, date(2011, 1, 10), "active"),
    992003: ("900303", "Debashis Mukherjee", "RBM", R, None, 9203, date(2009, 6, 1), "active"),
    992011: ("900311", "Meera Nair", "RBM", D, None, 9211, date(2012, 4, 2), "active"),
    992012: ("900312", "Anjali Verma", "RBM", D, None, 9212, date(2011, 8, 22), "active"),
    # ZBMs
    993001: ("900401", "Venkatesh Iyer", "ZBM", R, None, 9201, date(2005, 3, 1), "active"),
    993002: ("900402", "Ashok Mehta", "ZBM", R, None, 9202, date(2006, 1, 16), "active"),
    993003: ("900403", "Sanjay Chatterjee", "ZBM", R, None, 9203, date(2004, 10, 4), "active"),
    993011: ("900411", "Rajesh Shah", "ZBM", D, None, 9211, date(2007, 2, 12), "active"),
    993012: ("900412", "Vikram Sethi", "ZBM", D, None, 9212, date(2005, 11, 7), "active"),
}

# Assignment periods: (employee_id, manager_employee_id, valid_from, valid_to)
ASSIGNMENTS = [
    (990001, 991001, date(2022, 6, 1), None),
    (990002, 991002, date(2023, 1, 9), date(2025, 9, 30)),
    (990002, 991003, date(2025, 10, 1), None),
    (990003, 991004, date(2021, 4, 5), None),
    (990004, 991011, date(2023, 7, 17), None),
    (990006, 991012, date(2020, 8, 3), date(2026, 6, 30)),
    (990005, 991012, date(2026, 7, 1), None),
    (991001, 992001, date(2019, 4, 1), None),
    (991002, 992002, date(2018, 4, 1), date(2025, 9, 30)),
    (991003, 992002, date(2025, 10, 1), None),
    (991004, 992003, date(2017, 4, 1), None),
    (991011, 992011, date(2019, 4, 1), None),
    (991012, 992012, date(2018, 4, 1), None),
    (992001, 993001, date(2016, 4, 1), None),
    (992002, 993002, date(2016, 4, 1), None),
    (992003, 993003, date(2015, 4, 1), None),
    (992011, 993011, date(2017, 4, 1), None),
    (992012, 993012, date(2016, 4, 1), None),
    (993001, None, date(2014, 4, 1), None),
    (993002, None, date(2014, 4, 1), None),
    (993003, None, date(2013, 4, 1), None),
    (993011, None, date(2015, 4, 1), None),
    (993012, None, date(2014, 4, 1), None),
]

# Hidden ground truth - never loaded for agents.
REP_PROFILES = {
    990001: "star", 990002: "coverage_gap", 990003: "declining",
    990004: "busy_but_ineffective", 990005: "new_rep_handover",
}


def build() -> None:
    rows = []
    for i, (emp_id, mgr_id, valid_from, valid_to) in enumerate(ASSIGNMENTS, start=1):
        code, name, desig, sbu, territory_id, hq_id, joined, status = PEOPLE[emp_id]
        rows.append({
            "assignment_id": i,
            "employee_id": emp_id,
            "employee_code": code,
            "employee_name": name,
            "designation": desig,
            "business_unit_id": sbu,
            "territory_id": territory_id,
            "hq_id": hq_id,
            "manager_employee_id": mgr_id,
            "valid_from": valid_from,
            "valid_to": valid_to,
            "is_current": valid_to is None,
            "joining_date": joined,
            "email": ".".join(name.lower().split()) + "@example.com",
            "mobile": f"+910001{code[-6:]}",     # 0-prefix: not a valid Indian mobile number
            "employment_status": status,
        })

    from generator.common import write_parquet
    write_parquet("employee", pd.DataFrame(rows), """
    assignment_id        BIGINT  PRIMARY KEY,
    employee_id          BIGINT  NOT NULL,
    employee_code        VARCHAR NOT NULL,
    employee_name        VARCHAR NOT NULL,
    designation          VARCHAR NOT NULL,
    business_unit_id     BIGINT  NOT NULL,
    territory_id         BIGINT,
    hq_id                BIGINT  NOT NULL,
    manager_employee_id  BIGINT,
    valid_from           DATE    NOT NULL,
    valid_to             DATE,
    is_current           BOOLEAN NOT NULL,
    joining_date         DATE    NOT NULL,
    email                VARCHAR NOT NULL,
    mobile               VARCHAR NOT NULL,
    employment_status    VARCHAR NOT NULL""".strip("\n"))

    # answer key (separate folder, not part of the database)
    import duckdb
    key_dir = config.ROOT / "data" / "answer_key"
    key_dir.mkdir(parents=True, exist_ok=True)
    key = pd.DataFrame([{"employee_id": e, "territory_id": PEOPLE[e][4], "profile": p}
                        for e, p in REP_PROFILES.items()])
    duckdb.connect().execute(
        f"COPY (SELECT employee_id::BIGINT AS employee_id, territory_id::BIGINT AS territory_id, "
        f"profile FROM key) TO '{key_dir / 'rep_profile.parquet'}' (FORMAT PARQUET)")
