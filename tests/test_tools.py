"""Data tools: known answers from the frozen dataset (data-v2).

Employees: 990001 Karthikeyan R (BO Chennai), 990002 Aniket Kulkarni (BO Pune),
990003 Soumya Banerjee (BO Kolkata), 990004 Priya Deshpande (BO Mumbai), 990005 Rohit Malhotra (BO Delhi),
991012 Gurpreet Singh (ABM Delhi), 993011 Rajesh Shah (ZBM, Mumbai line).
"""

from datetime import date

import pytest

from mr_assistant import tools as T
from mr_assistant.db import as_employee
from mr_assistant.errors import NotFound, ToolError, UnknownEmployee

BOS = (990001, 990002, 990003, 990004, 990005)


def test_every_tool_runs_for_every_bo():
    for emp in BOS:
        with as_employee(emp) as db:
            doctor_id = T.list_doctors(db, doctor_class="A")[0].doctor_id
            for f in T.ALL_TOOLS:
                name = f.__name__
                if name in ("get_tour_plan", "get_calendar"):
                    f(db, date(2026, 10, 20), date(2026, 10, 27))
                elif name == "get_plan_status":
                    f(db, 202611)
                elif name == "find_doctor":
                    f(db, "a")
                elif name in ("get_doctor_profile", "get_doctor_clinics", "get_doctor_360", "get_visit_history",
                              "get_doctor_availability", "get_doctor_rx", "get_products_to_detail",
                              "get_formulary_status", "get_call_notes", "get_samples_given", "get_communications",
                              "get_best_contact_time", "get_what_changed"):
                    f(db, doctor_id)
                else:
                    f(db)


def test_snapshot():
    with as_employee(990001) as db:
        s = T.get_snapshot(db)
    assert (s.as_of_date, s.current_year_month, s.previous_year_month, s.history_start_month) == \
           (date(2026, 10, 27), 202610, 202609, 202411)


def test_profile_and_team():
    with as_employee(990001) as db:
        me = T.get_my_profile(db)
        assert (me.employee_name, me.business_unit_name, me.territory_name, me.manager_name) == \
               ("Karthikeyan R", "Respiratory BU", "Chennai T01", "Senthil Kumar M")
        assert T.get_team(db) == []
    with as_employee(993011) as db:
        assert [(t.employee_name, t.level) for t in T.get_team(db)] == \
               [("Meera Nair", 1), ("Farhan Shaikh", 2), ("Priya Deshpande", 3)]


def test_unknown_or_former_employee_is_rejected():
    with pytest.raises(UnknownEmployee):
        with as_employee(990006):          # previous Delhi BO, resigned
            pass


def test_find_doctor_by_name_and_code():
    with as_employee(990001) as db:
        hit = T.find_doctor(db, "Dr. Karthik R")[0]
        assert (hit.full_name, hit.doctor_code) == ("Karthik R", "750411")
        assert T.find_doctor(db, "750411")[0].doctor_id == 9000131
        with pytest.raises(ToolError):
            T.find_doctor(db, "  ")


def test_doctors_outside_territory_are_invisible():
    with as_employee(990001) as db:                       # Chennai BO looks for a Pune doctor
        assert T.find_doctor(db, "Abhijeet Mane") == []
        with pytest.raises(NotFound):
            T.get_doctor_profile(db, 9000232)
        with pytest.raises(NotFound):
            T.get_visit_history(db, 9000232)


def test_call_list_has_120_doctors_per_bo():
    for emp in BOS:
        with as_employee(emp) as db:
            assert len(T.list_doctors(db)) == 120


@pytest.mark.parametrize("emp, mcr, mvc, cpd, band, met", [
    (990001, 100.0, 100.0, 11.3, "above", True),
    (990002, 83.3, 69.2, 9.1, "below", False),
    (990003, 92.5, 82.5, 10.8, "above", False),
    (990004, 96.7, 95.8, 13.3, "above", True),
    (990005, 85.0, 73.3, 9.6, "below", False),
])
def test_rep_kpis_september(emp, mcr, mvc, cpd, band, met):
    with as_employee(emp) as db:
        k = T.get_rep_kpis(db, 202609)[0]
    assert (k.mcr_pct, k.mvc_pct, k.calls_per_day, k.call_band, k.mcr_met) == (mcr, mvc, cpd, band, met)


def test_manager_sees_handover_in_kpis():
    with as_employee(991012) as db:                       # ABM Delhi
        assert [(k.employee_name, k.mcr_pct) for k in T.get_rep_kpis(db, 202605)] == [("Amit Saxena", 93.3)]
        assert [(k.employee_name, k.mcr_pct) for k in T.get_rep_kpis(db, 202607)] == [("Rohit Malhotra", 62.5)]


def test_pending_visits_and_priority():
    with as_employee(990002) as db:
        assert T.get_pending_visits(db, limit=1)[0].doctor_name == "Prashant Gokhale"
        assert sum(r.visits_pending for r in T.get_visit_compliance(db, only_pending=True)) == 83
    with as_employee(990003) as db:
        top = T.get_priority_doctors(db, limit=1)[0]
        assert (top.doctor_name, top.score) == ("Tanushree Sen", 71.5)
        assert any("own-brand Rx down" in r for r in top.reasons)


def test_kolkata_decline_story():
    with as_employee(990003) as db:
        d = T.get_rx_decliners(db, limit=1)[0]
        assert (d.doctor_name, d.own_rx_trend_pct, d.last_receptivity) == ("Tanmoy Mondal", -81.8, "low")
        assert "CA-R1" in d.last_note_objections
        share = T.get_market_share(db)
        assert round(100 * sum(r.own_rx or 0 for r in share) / sum(r.total_rx for r in share), 1) == 23.6
        perf = {b.brand_name: (b.own_rx, b.achievement_pct) for b in T.get_brand_performance(db)}
        assert perf["AX-R2"] == (245, 38.3)


def test_products_to_detail_follow_priority():
    with as_employee(990001) as db:
        brands = [p.brand_name for p in T.get_products_to_detail(db, 9000019)]   # Dinesh A, chest physician
    assert brands == ["AX-R2", "AX-R5", "AX-R3", "AX-R6", "AX-R4"]


def test_plan_status_november():
    expected = {990001: "approved", 990002: "draft", 990003: "approved", 990004: "submitted", 990005: "approved"}
    for emp, status in expected.items():
        with as_employee(emp) as db:
            assert T.get_plan_status(db, 202611)[0].status == status


def test_calendar_and_availability():
    with as_employee(990001) as db:
        cal = {c.calendar_date: (c.is_working_day, c.holiday_name) for c in
               T.get_calendar(db, date(2026, 10, 18), date(2026, 10, 25))}
        assert cal[date(2026, 10, 20)] == (False, "Dussehra")
        assert cal[date(2026, 10, 25)] == (False, None)      # Sunday
        assert cal[date(2026, 10, 21)] == (True, None)
        days = T.get_doctor_availability(db, 9000019)
        assert days and all(d.opd_hours for d in days)


def test_content_only_approved_and_valid():
    with as_employee(990001) as db:
        items = T.get_content(db, brand_code="BR-RES-002")
    assert {i.content_type for i in items} == {"email_template", "leaflet", "study_summary", "visual_aid",
                                               "whatsapp_template"}
    assert all("withdrawn" not in i.title for i in items)


def test_catalog_and_nba():
    with as_employee(990001) as db:
        assert len(T.list_products(db)) == 26 and len(T.list_products(db, own_only=False)) == 42
        recs = T.get_nba_recommendations(db)
        assert len(recs) == 5 and recs[0].generated_at.date() == date(2026, 10, 27)


def test_failed_query_does_not_break_the_session():
    with as_employee(990001) as db:
        with pytest.raises(Exception):
            db.all("SELECT no_such_column FROM core.doctor")
        assert db.scalar("SELECT COUNT(*) FROM core.doctor") > 0
        assert T.get_snapshot(db).current_year_month == 202610
