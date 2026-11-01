"""Read-only data tools for agents. Every tool takes `db` (from `as_employee`) as the first argument;
row-level security decides what each user sees, so tools never filter by user themselves.

    from mr_assistant.db import as_employee
    from mr_assistant import tools

    with as_employee(990001) as db:
        tools.get_pending_visits(db)
"""

from mr_assistant.tools.doctors import (find_doctor, get_doctor_360, get_doctor_clinics, get_doctor_profile,
                                        list_doctors)
from mr_assistant.tools.engagement import (get_best_contact_time, get_call_notes, get_channel_effectiveness,
                                           get_communications, get_content, get_nba_recommendations,
                                           get_samples_given, get_what_changed)
from mr_assistant.tools.identity import get_my_profile, get_snapshot, get_team
from mr_assistant.tools.market import (get_brand_performance, get_doctor_rx, get_formulary_status, get_market_share,
                                       get_products_to_detail, get_rx_decliners, list_products)
from mr_assistant.tools.planning import (get_calendar, get_doctor_availability, get_plan_status,
                                         get_priority_doctors, get_tour_plan)
from mr_assistant.tools.visits import (get_kpi_trend, get_pending_visits, get_rep_kpis, get_visit_compliance,
                                       get_visit_history)

ALL_TOOLS = [
    # identity
    get_snapshot, get_my_profile, get_team,
    # doctors
    find_doctor, get_doctor_profile, list_doctors, get_doctor_clinics, get_doctor_360,
    # visits and KPIs
    get_visit_history, get_visit_compliance, get_pending_visits, get_rep_kpis, get_kpi_trend,
    # planning
    get_priority_doctors, get_tour_plan, get_plan_status, get_doctor_availability, get_calendar,
    # market
    get_doctor_rx, get_market_share, get_brand_performance, get_products_to_detail, get_rx_decliners,
    get_formulary_status, list_products,
    # engagement
    get_call_notes, get_samples_given, get_communications, get_channel_effectiveness, get_best_contact_time,
    get_content, get_nba_recommendations, get_what_changed,
]

__all__ = [t.__name__ for t in ALL_TOOLS] + ["ALL_TOOLS"]
