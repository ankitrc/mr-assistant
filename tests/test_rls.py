"""Row-level security: the database decides what each user can see."""

import psycopg
import pytest

from conftest import as_employee, scalar

CHENNAI, PUNE, KOLKATA, MUMBAI, DELHI = 900001, 900002, 900003, 900004, 900005


def territories_seen(conn, table):
    return {r[0] for r in conn.execute(f"SELECT DISTINCT territory_id FROM core.{table}")}


def test_no_identity_sees_nothing(app_db):
    for table in ("dcr_call", "mcl", "doctor", "employee", "rcpa_entry", "call_note"):
        assert scalar(app_db, f"SELECT COUNT(*) FROM core.{table}") == 0, table


def test_bo_sees_only_own_territory(app_db):
    as_employee(app_db, 990001)                       # Karthikeyan R, BO Chennai
    for table in ("dcr_call", "mcl", "tour_plan", "rcpa_entry", "doctor_brand_plan", "geography"):
        assert territories_seen(app_db, table) == {CHENNAI}, table


def test_bo_cannot_read_another_territory_even_when_asking_directly(app_db):
    as_employee(app_db, 990001)
    assert scalar(app_db, "SELECT COUNT(*) FROM core.dcr_call WHERE territory_id = %s", PUNE) == 0


def test_bo_doctors_are_only_their_own(app_db):
    as_employee(app_db, 990001)
    seen = scalar(app_db, "SELECT COUNT(*) FROM core.doctor")
    outside = scalar(app_db, """SELECT COUNT(*) FROM core.doctor d WHERE NOT EXISTS (
                                  SELECT 1 FROM core.clinic c JOIN core.geography g USING (patch_id)
                                  WHERE c.doctor_id = d.doctor_id AND g.territory_id = %s)""", CHENNAI)
    assert 150 <= seen <= 200 and outside == 0


def test_child_tables_follow_parent(app_db):
    as_employee(app_db, 990002)                       # Aniket Kulkarni, BO Pune
    assert scalar(app_db, """SELECT COUNT(*) FROM core.call_note n
                             JOIN core.dcr_call c USING (call_id) WHERE c.territory_id <> %s""", PUNE) == 0
    assert scalar(app_db, "SELECT COUNT(*) FROM core.dcr_call_product") > 0


def test_managers_see_their_team(app_db):
    cases = {991001: {CHENNAI},                       # ABM Chennai
             992002: {PUNE},                          # RBM over Pune
             993011: {MUMBAI},                        # ZBM over Mumbai
             991012: {DELHI}}                         # ABM Delhi
    for manager, expected in cases.items():
        as_employee(app_db, manager)
        assert territories_seen(app_db, "dcr_call") == expected, manager
        app_db.rollback()


def test_new_rep_sees_handover_history(app_db):
    as_employee(app_db, 990005)                       # Rohit Malhotra took over Delhi on 1 Jul 2026
    before = scalar(app_db, "SELECT COUNT(*) FROM core.dcr_call WHERE call_date < '2026-07-01'")
    assert before > 0                                 # previous rep's calls stay visible in the territory


def test_former_employee_sees_nothing(app_db):
    as_employee(app_db, 990006)                       # previous Delhi BO, resigned
    assert scalar(app_db, "SELECT COUNT(*) FROM core.dcr_call") == 0


def test_reference_tables_are_readable(app_db):
    as_employee(app_db, 990001)
    assert scalar(app_db, "SELECT COUNT(*) FROM core.product") == 42
    assert scalar(app_db, "SELECT COUNT(*) FROM core.calendar_day") == 1095


def test_analytics_view_respects_rls(app_db):
    as_employee(app_db, 990003)                       # Soumya Banerjee, BO Kolkata
    seen = {r[0] for r in app_db.execute("SELECT DISTINCT territory_id FROM analytics.doctor_visit_compliance")}
    assert seen == {KOLKATA}


def test_app_role_cannot_write(app_db):
    as_employee(app_db, 990001)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        app_db.execute("DELETE FROM core.dcr_call")
