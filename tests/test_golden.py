"""Every expected answer in evals/golden_questions.jsonl is reproducible from the database."""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from mr_assistant import tools
from mr_assistant.db import as_employee

GOLDEN = [json.loads(line) for line in
          (Path(__file__).resolve().parent.parent / "evals" / "golden_questions.jsonl").read_text().splitlines()]


def _plain(v):
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, date):
        return v.isoformat()
    return v


def test_golden_set_shape():
    assert len(GOLDEN) >= 55
    assert len({q["id"] for q in GOLDEN}) == len(GOLDEN)
    assert {q["check"] for q in GOLDEN} <= {"number", "text", "list", "list_any", "bool", "refusal"}


@pytest.mark.parametrize("q", GOLDEN, ids=[q["id"] for q in GOLDEN])
def test_expected_answer_is_reproducible(q):
    emp = q["persona"]["employee_id"]
    with as_employee(emp) as db:
        if q["check_sql"] is None:                       # rule-based priority answers
            n = len(q["expected"]) if isinstance(q["expected"], list) else 1
            got = [p.doctor_name for p in tools.get_priority_doctors(db, limit=n)]
            got = got if isinstance(q["expected"], list) else got[0]
        else:
            result = [_plain(next(iter(r.values()))) for r in db.all(q["check_sql"])]
            got = result if q["check"] in ("list", "list_any") else (result[0] if result else None)
    assert got == q["expected"], q["question"]
    if q["check"] == "refusal":
        assert got == 0                                  # the persona really cannot see that data
