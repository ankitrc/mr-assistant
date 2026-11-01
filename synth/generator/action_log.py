"""agent_action_log: every action taken or proposed through the app since the
pilot start, derived from the rows the app wrote (notes, plans, slots,
messages, NBA). Insert-only."""

from datetime import date, datetime, time, timedelta
from functools import lru_cache

import numpy as np

from generator import comms, config, nba, notes, tour_plan, world


@lru_cache(maxsize=1)
def rows():
    rng = np.random.default_rng(config.SEEDS["action_log"])
    out = []

    def add(ts, emp, agent, action, table, tid, summary, approval, approver=None, approved_at=None,
            outcome="success", error=None):
        out.append({"occurred_at": ts, "employee_id": emp, "agent_name": agent, "action_type": action,
                    "target_table": table, "target_id": tid, "input_summary": summary,
                    "approval_required": approval, "approved_by": approver, "approved_at": approved_at,
                    "outcome": outcome, "error_message": error, "trace_id": f"{int(rng.integers(0, 2**63)):016x}"})

    for n in notes.rows():
        if n["source"] != "voice":
            continue
        add(n["recorded_at"], n["employee_id"], "post_call_agent", "save_note_draft", "call_note", n["note_id"],
            "Voice note transcribed and fields extracted", False,
            outcome="failed" if n["transcription_status"] == "failed" else "success",
            error="Speech-to-text timed out" if n["transcription_status"] == "failed" else None)
        if n["status"] == "confirmed":
            add(n["confirmed_at"], n["employee_id"], "post_call_agent", "confirm_note", "call_note", n["note_id"],
                "Rep confirmed extracted note fields", True, n["employee_id"], n["confirmed_at"])

    plans = tour_plan.rows()
    seen = set()
    for p in plans:
        key = (p["employee_id"], p["year_month"])
        if p["year_month"] < 202610 or key in seen:
            continue
        seen.add(key)
        if p["source"] == "agent_suggested":
            draft_ts = (p["submitted_at"] or datetime.combine(config.AS_OF_DATE, time(18))) - timedelta(hours=3)
            add(draft_ts, p["employee_id"], "call_planning_agent", "draft_tour_plan", "tour_plan", p["tour_plan_id"],
                f"Drafted MTP for {p['year_month']}", False)
        if p["submitted_at"]:
            add(p["submitted_at"], p["employee_id"], "call_planning_agent", "submit_tour_plan", "tour_plan",
                p["tour_plan_id"], f"BO submitted MTP for {p['year_month']}", True, p["employee_id"], p["submitted_at"])
        if p["approved_by"]:
            add(p["approved_at"], p["approved_by"], "call_planning_agent", "review_tour_plan", "tour_plan",
                p["tour_plan_id"], f"ABM approved MTP for {p['year_month']}", True, p["approved_by"], p["approved_at"])
    for p in plans:
        if p["source"] == "booked_slot":
            ts = next(n["confirmed_at"] for n in notes.rows() if n["note_id"] == p["_note_id"]) + timedelta(minutes=2)
            add(ts, p["employee_id"], "scheduling_agent", "book_slot", "tour_plan", p["tour_plan_id"],
                f"Slot proposed for {p['plan_date']} {p['planned_start_time']}", True, p["employee_id"], ts)

    for c in comms.rows():
        if c["generated_by"] != "agent":
            continue
        drafted = (c["approved_at"] or datetime.combine(config.AS_OF_DATE, time(20))) - timedelta(minutes=3)
        add(drafted, c["employee_id"], "engagement_agent", "draft_message", "communication", c["communication_id"],
            "WhatsApp follow-up drafted from approved template; consent checked", False)
        if c["status"] in ("delivered", "failed"):
            add(c["sent_at"], c["employee_id"], "engagement_agent", "send_message", "communication",
                c["communication_id"], "Rep approved and sent", True, c["approved_by"], c["approved_at"],
                outcome="failed" if c["status"] == "failed" else "success",
                error="WhatsApp provider rejected the message" if c["status"] == "failed" else None)
        elif c["status"] == "rejected":
            add(c["approved_at"], c["employee_id"], "engagement_agent", "send_message", "communication",
                c["communication_id"], "Rep rejected the draft", True, c["approved_by"], c["approved_at"],
                outcome="rejected")

    for r in nba.rows():
        if r["status"] in ("accepted", "dismissed"):
            add(r["status_at"], r["employee_id"], "nba_agent", "update_nba", "nba_recommendation",
                r["recommendation_id"], f"Rep {r['status']} recommendation", False)

    out.sort(key=lambda r: r["occurred_at"])
    for i, r in enumerate(out, 1):
        r["action_id"] = i
    return out
